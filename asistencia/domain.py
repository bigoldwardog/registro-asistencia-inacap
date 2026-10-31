import base64
import binascii
import io
import json
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from PIL import Image, UnidentifiedImageError
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

CHILE = ZoneInfo('America/Santiago')
EPP = 'Entrega de elementos de protección personal'
PANOL = 'Solicitud de materiales y equipo a Pañol'


class ErrorFormulario(Exception):
    def __init__(self, mensaje, status=400):
        self.mensaje, self.status = mensaje, status


def json_guardado(texto, tipo):
    try:
        valor = json.loads(texto)
    except (ValueError, TypeError):
        return tipo()
    return valor if isinstance(valor, tipo) else tipo()


def normalizar_rut(valor):
    limpio = re.sub(r'[.\s-]', '', valor).upper()
    if not re.fullmatch(r'[0-9]{1,9}[0-9K]', limpio):
        raise ErrorFormulario('El RUT debe incluir un dígito verificador válido.')
    cuerpo, dv = limpio[:-1].lstrip('0'), limpio[-1]
    suma = sum(int(n) * (2 + i % 6) for i, n in enumerate(reversed(cuerpo)))
    verificador = 11 - suma % 11
    esperado = '0' if verificador == 11 else 'K' if verificador == 10 else str(verificador)
    if not cuerpo or dv != esperado:
        raise ErrorFormulario('El dígito verificador del RUT no es válido.')
    return f'{cuerpo}-{dv}'


def fecha_chile(valor, solo_fecha=False):
    if not valor:
        return ''
    try:
        fecha = datetime.fromisoformat(str(valor))
        # Los registros SQLite anteriores sin zona se generaban en UTC.
        if fecha.tzinfo is None:
            fecha = fecha.replace(tzinfo=ZoneInfo('UTC'))
        local = fecha.astimezone(CHILE)
        return local.date().isoformat() if solo_fecha else local.isoformat()
    except ValueError:
        return ''


def validar_png(data):
    if not isinstance(data, str) or not data.startswith('data:image/png;base64,') or len(data) > 2800000:
        raise ErrorFormulario('Se requiere una firma PNG de hasta 2 MB.')
    try:
        contenido = base64.b64decode(data.split(',', 1)[1], validate=True)
        if len(contenido) > 2 * 1024 * 1024:
            raise ValueError()
        with Image.open(io.BytesIO(contenido)) as imagen:
            if imagen.format != 'PNG' or imagen.width * imagen.height > 4000000:
                raise ValueError()
            imagen.verify()
        with Image.open(io.BytesIO(contenido)) as imagen:
            rgba = imagen.convert('RGBA')
            # La superficie vacía puede ser transparente o blanca.
            pixeles = rgba.get_flattened_data()
            if not any(a > 10 and min(r, g, b) < 245 for r, g, b, a in pixeles):
                raise ValueError()
    except (ValueError, binascii.Error, UnidentifiedImageError, OSError, Image.DecompressionBombError, SyntaxError):
        raise ErrorFormulario('La firma está vacía, incompleta o no es una imagen PNG válida.')
    return contenido


def campo(nombre, etiqueta, tipo='text', obligatorio=True):
    return dict(nombre=nombre, etiqueta=etiqueta, tipo=tipo, obligatorio=obligatorio)


def campos_asistente(sesion):
    nombre = sesion.plantilla.nombre if sesion else ''
    comunes = [campo('nombre', 'Nombre completo'), campo('rut', 'RUT')]
    contacto = [campo('correo', 'Correo electrónico', 'email', False), campo('telefono', 'Teléfono', 'tel', False)]
    if nombre == 'Entrevista con estudiante':
        return [comunes[0], campo('cargo', 'Cargo / Carrera')]
    if nombre in ('Acta de reunión', 'Acta de reunión detallada'):
        return [comunes[0], campo('cargo', 'Cargo'), campo('rut', 'RUT', obligatorio=False)] + contacto
    if nombre == 'Registro de participación en actividades' or nombre == EPP:
        return comunes + [campo('cargo', 'Cargo')] + contacto
    if nombre == 'Solicitud de seguro para proyecto de título':
        return comunes + [campo('correo', 'Correo electrónico', 'email'), campo('telefono', 'Teléfono', 'tel'), campo('carrera', 'Carrera')]
    if nombre == PANOL:
        return comunes + [campo('carrera', 'Carrera'), campo('jornada', 'Jornada'), campo('seccion', 'Sección')] + contacto
    if nombre == 'Registro de asistencia':
        return comunes + [campo('telefono', 'Teléfono', 'tel'), campo('correo', 'Correo electrónico', 'email', False)]
    return comunes + contacto


def validar_persona(datos, sesion):
    valores = {}
    for campo_actual in campos_asistente(sesion):
        nombre = campo_actual['nombre']
        valor = datos.get(nombre, '')
        if not isinstance(valor, str) or len(valor) > 500:
            raise ErrorFormulario(f"Valor inválido en {campo_actual['etiqueta']}.")
        valor = valor.strip()
        if not valor and campo_actual['obligatorio']:
            raise ErrorFormulario(f"Completa {campo_actual['etiqueta']}.")
        if valor and nombre == 'rut':
            valor = normalizar_rut(valor)
        if valor and campo_actual['tipo'] == 'email':
            try:
                validate_email(valor)
            except ValidationError:
                raise ErrorFormulario('El correo electrónico no es válido.')
        valores[nombre] = valor
    return valores
