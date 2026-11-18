import io
import json
import re
from datetime import datetime
from django.http import HttpResponse
from django.views.decorators.http import require_GET
from openpyxl import Workbook
from openpyxl.drawing.image import Image as ExcelImage
from openpyxl.styles import Font, PatternFill, Alignment
from .access import acceso
from .permissions import tiene_permiso
from .domain import ErrorFormulario, fecha_chile, json_guardado
from .models import Asistencias, Firmas, FirmasDevolucion, FirmasAdicionales
from .views import errores, obtener_sesion


def texto_excel(valor):
    # Los datos introducidos por personas siempre son texto, nunca fórmulas.
    return re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', '', str(valor or ''))


@acceso()
@require_GET
@errores
def exportar(request, formato):
    if formato not in ('pdf', 'xlsx'):
        raise ErrorFormulario('Formato de exportación no disponible.', 404)
    ids = request.GET.get('sesiones', '')
    try:
        seleccion = [int(v) for v in ids.split(',') if v]
    except ValueError:
        raise ErrorFormulario('La selección de sesiones no es válida.')
    if not seleccion:
        raise ErrorFormulario('Selecciona al menos una sesión para exportar.')
    sesiones = [obtener_sesion(request, sid, accion='exportar') for sid in dict.fromkeys(seleccion)]
    for sesion in sesiones:
        if not tiene_permiso(request.actor, 'exportar', sesion):
            raise ErrorFormulario('No tienes permiso para exportar esta sesión.', 403)
    from .domain import EPP, PANOL
    from .documentos import construir_documento, pdf_documentos, xlsx_documentos
    especiales = any(s.plantilla.nombre in (EPP, PANOL) for s in sesiones)
    if especiales and any(s.plantilla.nombre not in (EPP, PANOL) for s in sesiones):
        raise ErrorFormulario('Exporta pañol y EPP por separado de las demás actividades mientras se adapta su formato.', 409)
    if formato == 'pdf' or not especiales:
        documentos = [construir_documento(s) for s in sesiones]
        contenido = pdf_documentos(documentos) if formato == 'pdf' else xlsx_documentos(documentos)
        tipo = 'application/pdf' if formato == 'pdf' else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        response = HttpResponse(contenido, content_type=tipo)
        response['Content-Disposition'] = f'attachment; filename="registros-asistencia.{formato}"'
        response['Cache-Control'] = 'private, no-store'
        return response
    headers = ['ID sesión', 'Sesión', 'Tipo', 'Anfitrión', 'Inicio (Chile)', 'Término (Chile)',
        'Estado sesión', 'Nombre', 'RUT', 'Cargo / Carrera', 'Carrera', 'Jornada', 'Sección',
        'Correo', 'Teléfono', 'Registro (Chile)', 'Estado asistencia', 'Firma recepción (Chile)',
        'Firma devolución (Chile)', 'Firma docente (Chile)', 'Datos actividad', 'Otros datos participante']
    firmas = {f.asistencia_id: f for f in Firmas.objects.filter(asistencia__sesion_id__in=seleccion)}
    devoluciones = {f.asistencia_id: f for f in FirmasDevolucion.objects.filter(asistencia__sesion_id__in=seleccion)}
    docentes = {f.asistencia_id: f for f in FirmasAdicionales.objects.filter(asistencia__sesion_id__in=seleccion, tipo='DOCENTE')}
    rows, images = [], []
    for s in sesiones:
        participantes = list(Asistencias.objects.filter(sesion=s).order_by('fecha_registro', 'id'))
        for a in participantes or [None]:
            datos = json_guardado(a.campos_participante_json, dict) if a else {}
            f = firmas.get(a.id) if a else None
            d = devoluciones.get(a.id) if a else None
            docente = docentes.get(a.id) if a else None
            rows.append([s.id, s.nombre, s.plantilla.nombre, s.anfitrion.nombre,
                fecha_chile(s.fecha_inicio), fecha_chile(s.fecha_cierre), s.estado,
                a.nombre_registrado if a else '', a.rut_registrado if a else '', a.cargo_registrado if a else '',
                datos.get('carrera', ''), datos.get('jornada', ''), datos.get('seccion', ''),
                a.correo_registrado if a else '', a.telefono_registrado if a else '',
                fecha_chile(a.fecha_registro) if a else '', a.estado if a else '',
                fecha_chile(f.fecha_creacion) if f else '', fecha_chile(d.fecha_creacion) if d else '',
                fecha_chile(docente.fecha_creacion) if docente else '',
                json.dumps(json_guardado(s.campos_valores_json, dict), ensure_ascii=False),
                json.dumps(datos, ensure_ascii=False) if a else ''])
            images.append([f, d, docente])
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = 'Asistencias'
    sheet.append(headers + ['Imagen recepción', 'Imagen devolución', 'Imagen docente'])
    from openpyxl.utils import get_column_letter
    for index, row in enumerate(rows, start=2):
        for col, value in enumerate(row, start=1):
            cell = sheet.cell(index, col, texto_excel(value))
            cell.data_type = 's'
            if col in (5, 6, 16, 18, 19, 20) and value:
                cell.value = datetime.fromisoformat(str(value)).replace(tzinfo=None)
                cell.number_format = 'dd-mm-yyyy hh:mm:ss'
            cell.alignment = Alignment(vertical='center', wrap_text=True)
        for offset, firma in enumerate(images[index - 2], start=len(headers) + 1):
            if firma:
                try:
                    image = ExcelImage(io.BytesIO(bytes(firma.imagen)))
                    ratio = min(180 / image.width, 85 / image.height, 1)
                    image.width *= ratio
                    image.height *= ratio
                    sheet.add_image(image, f'{get_column_letter(offset)}{index}')
                except (OSError, ValueError, SyntaxError):
                    sheet.cell(index, offset, 'Imagen anterior ilegible: requiere revisión')
        sheet.row_dimensions[index].height = 75 if any(images[index - 2]) else 34
    for cell in sheet[1]:
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor='222222')
        cell.alignment = Alignment(wrap_text=True, vertical='center')
    sheet.row_dimensions[1].height = 34
    for col in range(1, len(headers) + 4):
        sheet.column_dimensions[get_column_letter(col)].width = 28 if col > 1 else 12
    sheet.column_dimensions['U'].width = 65
    sheet.column_dimensions['V'].width = 45
    sheet.freeze_panes = 'H2'
    sheet.auto_filter.ref = sheet.dimensions
    # Hoja separada para leer campos de cada actividad sin interpretar JSON.
    activity = workbook.create_sheet('Actividades')
    activity.append(['ID', 'Actividad', 'Campo', 'Valor'])
    for s in sesiones:
        labels = {c.get('nombre'): c.get('etiqueta') for c in json_guardado(s.campos_definicion_json, list) if isinstance(c, dict)}
        for key, value in json_guardado(s.campos_valores_json, dict).items():
            activity.append([str(s.id), texto_excel(s.nombre), texto_excel(labels.get(key, key)), texto_excel(value)])
    for row in activity:
        for cell in row:
            cell.data_type = 's'
            cell.alignment = Alignment(wrap_text=True, vertical='top')
    for col, width in [('A', 12), ('B', 35), ('C', 35), ('D', 90)]:
        activity.column_dimensions[col].width = width
    activity.freeze_panes = 'A2'
    stream = io.BytesIO()
    workbook.save(stream)
    response = HttpResponse(stream.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="registros-asistencia.{formato}"'
    response['Cache-Control'] = 'private, no-store'
    return response


@acceso()
def exportar_administrador(request, formato):
    return exportar(request, formato)
