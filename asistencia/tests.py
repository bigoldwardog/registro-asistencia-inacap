import base64
import io
import json
import uuid
import zipfile
from datetime import datetime

from PIL import Image, ImageDraw
from django.contrib.auth.hashers import make_password
from django.db import connection
from django.test import Client, TransactionTestCase, override_settings
from django.utils import timezone
from openpyxl import load_workbook

from .catalogo_plantillas import cargar_catalogo, CATALOGO
from .domain import EPP, PANOL, ErrorFormulario, fecha_chile, normalizar_rut
from .models import (Asistencias, Asistentes, Auditoria, Firmas, FirmasAdicionales,
                     FirmasDevolucion, PlantillasSesion, Sesiones, Usuarios)


def firma_png(vacia=False):
    imagen = Image.new('RGBA', (300, 100), 'white')
    if not vacia:
        ImageDraw.Draw(imagen).line([(20, 70), (60, 20), (120, 80), (240, 30)], fill='black', width=4)
    buffer = io.BytesIO(); imagen.save(buffer, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(buffer.getvalue()).decode()


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class SistemaTests(TransactionTestCase):
    def setUp(self):
        from pathlib import Path
        from django.conf import settings
        connection.ensure_connection()
        connection.connection.executescript((Path(settings.BASE_DIR) / 'database/schema.sql').read_text(encoding='utf-8-sig'))
        for table in ['firmas_adicionales', 'firmas_devolucion', 'firmas', 'auditoria', 'asistencias', 'sesiones', 'asistentes', 'campos_plantilla', 'plantillas_sesion', 'usuarios']:
            connection.connection.execute('DELETE FROM ' + table)
        cargar_catalogo()
        self.admin = Usuarios.objects.create(nombre='Administradora', correo='admin@example.com', rol='ADMINISTRADOR', activo=1, password_hash=make_password('Prueba-valida-2026!'))
        self.host = Usuarios.objects.create(nombre='Anfitrión', correo='host@example.com', rol='ANFITRION', activo=1, password_hash=make_password('Prueba-valida-2026!'))
        self.other = Usuarios.objects.create(nombre='Otro anfitrión', correo='otro@example.com', rol='ANFITRION', activo=1, password_hash=make_password('Prueba-valida-2026!'))
        from .organizacion import cargar_catalogo as cargar_organizacion
        from .permissions import migrar_cuentas
        from .models import SedeAcademica, AreaAcademica, AccesoUsuario
        cargar_organizacion()
        migrar_cuentas()
        self.sede = SedeAcademica.objects.order_by('id').first()
        self.area = AreaAcademica.objects.order_by('id').first()
        AccesoUsuario.objects.update(sede=self.sede, area=self.area)

        self.a = self.login(self.admin); self.h = self.login(self.host); self.o = self.login(self.other)
        self.png = firma_png()

    def login(self, usuario):
        client = Client(); session = client.session; session['usuario_id'] = usuario.id; session.save(); return client

    def crear(self, nombre='Entrevista con estudiante', client=None):
        plantilla = PlantillasSesion.objects.get(nombre=nombre)
        values = {c.nombre: {'fecha': timezone.localdate().isoformat(), 'hora': '10:00', 'email': 'test@example.com', 'numero': '1'}.get(c.tipo, 'Dato de prueba') for c in plantilla.camposplantilla_set.all()}
        response = (client or self.h).post('/api/sesiones/crear/', {'nombre': 'Actividad ' + nombre, 'plantilla_id': plantilla.id, 'anfitrion_id': self.host.id, 'fecha_programada': '2026-11-20T10:00', 'campos': values}, content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)
        inicio = (client or self.h).post(f"/api/sesiones/{response.json()['id']}/iniciar/", {'anfitrion_id': self.host.pk, 'rut': '12345678-5', 'firma': self.png}, content_type='application/json')
        self.assertEqual(inicio.status_code, 200, inicio.content)
        return Sesiones.objects.get(id=response.json()['id'])

    def registrar(self, sesion, **extra):
        from .domain import campos_asistente
        values = {f['nombre']: {'rut': '12345678-5', 'correo': 'test@example.com', 'telefono': '+56912345678'}.get(f['nombre'], 'Persona de prueba') for f in campos_asistente(sesion)}
        values.update(extra)
        values.setdefault('registro_token', str(uuid.uuid4()))
        return self.client.post(f'/api/sesiones/{sesion.token_qr}/asistencias/', values, content_type='application/json'), values

    def firmar(self, asistencia_id, client=None):
        response = (client or self.h).post(f'/api/asistencias/{asistencia_id}/firma/', {'firma': self.png}, content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)

    def test_creacion_y_cierre_diez_plantillas(self):
        for nombre, _, _ in CATALOGO:
            with self.subTest(plantilla=nombre):
                s = self.crear(nombre); inicio = s.fecha_inicio
                self.assertTrue(inicio); self.assertIsNone(s.fecha_cierre)
                response, _ = self.registrar(s)
                self.assertEqual(response.status_code, 201, response.content)
                self.firmar(response.json()['asistencia_id'])
                self.assertEqual(self.h.post(f'/api/sesiones/{s.id}/cerrar/').status_code, 200)
                s.refresh_from_db(); cierre = s.fecha_cierre
                self.h.post(f'/api/sesiones/{s.id}/cerrar/'); s.refresh_from_db()
                self.assertEqual((s.fecha_inicio, s.fecha_cierre), (inicio, cierre))
                response, _ = self.registrar(s)
                self.assertEqual(response.status_code, 409)
        self.assertEqual(PlantillasSesion.objects.filter(activa=1).count(), 10)

    def test_firmas_desde_dispositivo_y_alcance_de_exportacion(self):
        sesion = self.crear(EPP)
        registro, valores = self.registrar(sesion)
        self.assertEqual(registro.status_code, 201, registro.content)
        url = f'/api/sesiones/{sesion.token_qr}/asistencias/firma/'
        data = {'registro_token': valores['registro_token'], 'firma': self.png}
        csrf_client = Client(enforce_csrf_checks=True)
        self.assertEqual(csrf_client.post(url, dict(data, tipo='asistencia'), content_type='application/json').status_code, 403)
        self.assertEqual(self.client.post(url, dict(data, tipo='devolucion'), content_type='application/json').status_code, 409)
        otra = self.crear()
        self.assertEqual(self.client.post(f'/api/sesiones/{otra.token_qr}/asistencias/firma/',
            dict(data, tipo='asistencia'), content_type='application/json').status_code, 404)
        self.assertEqual(self.client.post(url, dict(data, tipo='asistencia'), content_type='application/json').status_code, 201)
        self.assertEqual(self.client.post(url, dict(data, tipo='asistencia'), content_type='application/json').status_code, 200)
        self.assertEqual(self.client.post(url, dict(data, tipo='devolucion'), content_type='application/json').status_code, 201)
        export = f'/api/sesiones/exportar/xlsx/?sesiones={sesion.id}'
        self.assertEqual(self.o.get(export).status_code, 403)
        self.assertEqual(self.h.get(export).status_code, 200)
        poster = self.h.get(f'/api/sesiones/{sesion.id}/afiche.pdf')
        self.assertEqual(poster.status_code, 200)
        self.assertTrue(poster.content.startswith(b'%PDF'))
        self.assertEqual(self.o.get(f'/api/sesiones/{sesion.id}/afiche.pdf').status_code, 403)
        segunda, otros = self.registrar(sesion, rut='11111111-1')
        self.assertEqual(segunda.status_code, 201, segunda.content)
        self.h.post(f'/api/sesiones/{sesion.id}/cerrar/')
        self.assertEqual(self.client.post(url, dict(data, tipo='asistencia',
            registro_token=otros['registro_token']), content_type='application/json').status_code, 409)

    def test_panol_mantiene_firma_docente_separada(self):
        sesion = self.crear(PANOL)
        registro, valores = self.registrar(sesion)
        self.assertEqual(registro.status_code, 201, registro.content)
        id_asistencia = registro.json()['asistencia_id']
        url = f'/api/sesiones/{sesion.token_qr}/asistencias/firma/'
        datos = {'registro_token': valores['registro_token'], 'firma': self.png}
        self.assertEqual(self.client.post(url, dict(datos, tipo='docente'), content_type='application/json').status_code, 400)
        self.assertEqual(self.client.post(url, dict(datos, tipo='asistencia'), content_type='application/json').status_code, 201)
        docente = f'/api/asistencias/{id_asistencia}/docente/firma/'
        self.assertEqual(self.client.post(docente, datos, content_type='application/json').status_code, 401)
        self.assertEqual(self.h.post(docente, datos, content_type='application/json').status_code, 201)

    def test_rut_canonico_digito_y_duplicado(self):
        self.assertEqual(normalizar_rut('12.345.678-5'), '12345678-5')
        self.assertEqual(normalizar_rut('123456785'), '12345678-5')
        for value in ['12345678-9', '123', 'abcdefgh-k']:
            with self.assertRaises(ErrorFormulario): normalizar_rut(value)
        s = self.crear('Registro de asistencia')
        r, _ = self.registrar(s, rut='12.345.678-5'); self.assertEqual(r.status_code, 201)
        r, _ = self.registrar(s, rut='12345678-5'); self.assertEqual(r.status_code, 409)
        self.assertEqual(s.asistencias_set.count(), 1)

    def test_idempotencia_y_recuperacion_incluso_tras_cierre(self):
        s = self.crear(); result, values = self.registrar(s)
        self.assertEqual(result.status_code, 201)
        self.h.post(f'/api/sesiones/{s.id}/cerrar/')
        repeated = self.client.post(f'/api/sesiones/{s.token_qr}/asistencias/', values, content_type='application/json')
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(result.json()['asistencia_id'], repeated.json()['asistencia_id'])
        self.assertEqual(s.asistencias_set.count(), 1)
        check = self.client.get(f'/api/sesiones/{s.token_qr}/asistencias/consultar/', {'registro_token': values['registro_token']})
        self.assertTrue(check.json()['registrada'])
        repeated = self.client.post(f'/api/sesiones/{s.token_qr}/asistencias/', {**values, 'nombre': 'Otra'}, content_type='application/json')
        self.assertEqual(repeated.status_code, 409)

    def test_png_incompleto_vacio_y_valido(self):
        s = self.crear(); r, _ = self.registrar(s); aid = r.json()['asistencia_id']
        url = f'/api/asistencias/{aid}/firma/'
        invalidos = ['data:image/png;base64,' + base64.b64encode(b'\x89PNG\r\n\x1a\n').decode(), firma_png(True), 'incorrecto']
        for firma in invalidos:
            self.assertEqual(self.h.post(url, {'firma': firma}, content_type='application/json').status_code, 400)
        self.assertFalse(Firmas.objects.filter(asistencia_id=aid).exists())
        self.firmar(aid)
        self.assertEqual(self.h.post(url, {'firma': self.png}, content_type='application/json').status_code, 409)

    def test_roles_propiedad_y_desactivacion(self):
        s = self.crear()
        self.assertEqual(self.client.get('/anfitrion/').status_code, 302)
        self.assertEqual(self.client.get('/api/sesiones/').status_code, 401)
        self.assertEqual([item['id'] for item in self.h.get('/api/administrador/historial/').json()['sesiones']], [s.id])
        self.assertEqual(self.o.get(f'/api/sesiones/{s.id}/asistencias/lista/').status_code, 403)
        self.assertEqual(self.o.post(f'/api/sesiones/{s.id}/cerrar/').status_code, 403)
        self.assertEqual(self.a.get(f'/api/sesiones/{s.id}/asistencias/lista/').status_code, 200)
        self.assertEqual(self.o.get('/api/sesiones/').json()['sesiones'], [])
        self.host.activo = 0; self.host.save()
        self.assertEqual(self.h.get('/api/sesiones/').status_code, 401)

    def test_login_logout_y_ruta_retirada(self):
        c = Client()
        r = c.post('/ingresar/', {'correo': self.host.correo, 'password': 'Prueba-valida-2026!'})
        self.assertEqual(r.status_code, 302); self.assertEqual(c.get('/anfitrion/').status_code, 200)
        self.assertEqual(c.get('/salir/').status_code, 405)
        self.assertEqual(c.post('/salir/').status_code, 302); self.assertEqual(c.get('/api/sesiones/').status_code, 401)
        self.assertEqual(self.a.get('/usuarios/').status_code, 404)


    def test_telefono_opcional_en_perfil_propio(self):
        url = '/mi-cuenta/'
        datos = {
            'accion': 'guardar', 'actual': 'Prueba-valida-2026!',
            'nombre': self.host.nombre, 'correo': 'perfil@example.com',
            'usuario_id': self.admin.id,
        }
        numero = '+56 9 0000 0010'
        self.assertContains(self.h.post(url, dict(datos, telefono=numero)), 'Información actualizada.')
        self.host.refresh_from_db()
        self.admin.refresh_from_db()
        self.assertEqual(self.host.telefono, numero)
        self.assertEqual(self.host.correo, datos['correo'])
        self.assertEqual(self.admin.telefono, '')
        self.assertContains(self.h.get(url), numero)
        self.assertContains(self.h.post(url, {'accion': 'ver', 'actual': datos['actual']}), numero)
        self.h.post(url, datos)
        self.host.refresh_from_db()
        self.assertEqual(self.host.telefono, numero)
        self.h.post(url, dict(datos, telefono=''))
        self.host.refresh_from_db()
        self.assertEqual(self.host.telefono, '')

    def test_configuracion_inicial_solo_local_y_una_vez(self):
        Usuarios.objects.update(activo=0)
        self.assertEqual(self.client.get('/configuracion-inicial/', REMOTE_ADDR='192.168.1.10').status_code, 403)
        result = self.client.post('/configuracion-inicial/', {'nombre': 'Inicial', 'correo': 'inicial@example.com', 'password': 'Cuenta-inicial-segura-2026!', 'password2': 'Cuenta-inicial-segura-2026!', 'sede': self.sede.id, 'area': self.area.id}, REMOTE_ADDR='127.0.0.1')
        self.assertEqual(result.status_code, 302)
        from .models import AccesoUsuario
        self.assertTrue(AccesoUsuario.objects.get(usuario__correo='inicial@example.com').superusuario)
        self.assertEqual(self.client.get('/configuracion-inicial/').status_code, 302)

    def test_csrf_publico_y_privado(self):
        s = self.crear(); c = Client(enforce_csrf_checks=True)
        page = c.get('/', {'token': s.token_qr}); self.assertContains(page, 'csrfmiddlewaretoken')
        data = {'nombre': 'Estudiante', 'cargo': 'Informática', 'registro_token': str(uuid.uuid4())}
        url = f'/api/sesiones/{s.token_qr}/asistencias/'
        self.assertEqual(c.post(url, data, content_type='application/json').status_code, 403)
        self.assertEqual(c.post(url, data, content_type='application/json', HTTP_X_CSRFTOKEN=c.cookies['csrftoken'].value).status_code, 201)
        protected = Client(enforce_csrf_checks=True); session = protected.session; session['usuario_id'] = self.host.id; session.save()
        self.assertEqual(protected.post(f'/api/sesiones/{s.id}/cerrar/').status_code, 403)

    def test_observaciones_historial_y_conflicto(self):
        s = self.crear(); key = 'desarrollo_de_la_entrevista'
        url = f'/api/sesiones/{s.id}/desarrollo/'
        base = json.loads(s.campos_valores_json)
        result = self.h.post(url, {'campos': {key: 'Primera versión'}, 'base': base}, content_type='application/json')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(self.h.post(url, {'campos': {key: 'Versión obsoleta'}, 'base': base}, content_type='application/json').status_code, 409)
        self.h.post(f'/api/sesiones/{s.id}/cerrar/')
        self.assertEqual(self.h.post(url, {'campos': {key: 'Versión final'}, 'base': result.json()['campos']}, content_type='application/json').status_code, 200)
        historial = self.a.get(f'/api/sesiones/{s.id}/historial/').json()['historial']
        guardados = [row for row in historial if row['accion'] == 'GUARDAR_DESARROLLO']
        self.assertEqual(len(guardados), 2)
        self.assertEqual(guardados[0]['anteriores'][key], 'Primera versión')
        self.assertEqual(guardados[0]['nuevos'][key], 'Versión final')

    def test_epp_docente_y_bloqueo_tras_cierre(self):
        for nombre, tipo in [(EPP, 'devolucion'), (PANOL, 'docente')]:
            with self.subTest(nombre=nombre):
                s = self.crear(nombre); r, _ = self.registrar(s); aid = r.json()['asistencia_id']
                url = f'/api/asistencias/{aid}/{tipo}/firma/'
                self.assertEqual(self.h.post(url, {'firma': self.png}, content_type='application/json').status_code, 409)
                self.firmar(aid)
                self.assertEqual(self.h.post(url, {'firma': self.png}, content_type='application/json').status_code, 201)
                self.assertEqual(self.h.post(url, {'firma': self.png}, content_type='application/json').status_code, 409)
                self.h.post(f'/api/sesiones/{s.id}/cerrar/')
                self.assertEqual(self.h.post(url, {'firma': self.png}, content_type='application/json').status_code, 409)
                self.assertEqual(self.h.get(f'/api/asistencias/{aid}/imagen/{tipo}/').status_code, 200)
                self.assertEqual(self.o.get(f'/api/asistencias/{aid}/imagen/{tipo}/').status_code, 403)
        s = self.crear(); r, _ = self.registrar(s); aid = r.json()['asistencia_id']; self.h.post(f'/api/sesiones/{s.id}/cerrar/')
        self.assertEqual(self.h.post(f'/api/asistencias/{aid}/firma/', {'firma': self.png}, content_type='application/json').status_code, 409)

    def test_fecha_chile_busqueda_y_cargo(self):
        s = self.crear(); Sesiones.objects.filter(id=s.id).update(fecha_inicio='2026-10-31T00:30:00+00:00')
        self.registrar(s, nombre='Ronald de prueba', cargo='CEO')
        response = self.a.get('/api/administrador/historial/', {'q': 'Ronald'})
        self.assertEqual(response.json()['sesiones'][0]['fecha_local'], '2026-10-30')
        self.assertEqual(fecha_chile('2026-10-31T00:30:00+00:00', True), '2026-10-30')
        listado = self.a.get(f'/api/sesiones/{s.id}/asistencias/lista/').json()
        self.assertEqual(listado['asistencias'][1]['cargo'], 'CEO')
        self.assertEqual([f['nombre'] for f in listado['sesion']['campos_asistente']], ['nombre', 'cargo'])
        self.assertEqual(self.a.get('/api/administrador/historial/', {'q': 'No existe'}).json()['sesiones'], [])

    def test_excel_especial_con_firmas_y_csv_retirado(self):
        s = self.crear(EPP); r, _ = self.registrar(s, nombre='=FORMULA()'); aid = r.json()['asistencia_id']; self.firmar(aid)
        self.h.post(f'/api/asistencias/{aid}/devolucion/firma/', {'firma': self.png}, content_type='application/json')
        query = {'sesiones': str(s.id)}
        self.assertEqual(self.a.get('/api/administrador/exportar/csv/', query).status_code, 404)
        xlsx = self.a.get('/api/administrador/exportar/xlsx/', query)
        self.assertEqual(xlsx.status_code, 200)
        book = load_workbook(io.BytesIO(xlsx.content)); sheet = book['Asistencias']
        self.assertEqual(sheet['H2'].value, '=FORMULA()'); self.assertEqual(sheet['H2'].data_type, 's')
        self.assertEqual(len(sheet._images), 2)
        self.assertIn('Actividades', book.sheetnames)
        self.assertEqual(self.h.get('/api/administrador/exportar/pdf/', query).status_code, 409)
        self.assertEqual(self.client.get('/api/administrador/exportar/xlsx/', query).status_code, 401)

    def test_qr_local_sin_cdn_y_datos_antiguos(self):
        s = self.crear(); r = self.h.get(f'/api/sesiones/{s.id}/qr.png')
        self.assertEqual(r.status_code, 200); self.assertEqual(Image.open(io.BytesIO(r.content)).format, 'PNG')
        self.assertNotContains(self.h.get('/anfitrion/'), 'cdnjs.cloudflare')
        for definition, values in [('', ''), ('null', '[]'), ('[null,3,{}]', 'malformado')]:
            Sesiones.objects.filter(id=s.id).update(campos_definicion_json=definition, campos_valores_json=values)
            self.assertEqual(self.h.get('/api/sesiones/').status_code, 200)
        self.assertEqual(connection.connection.execute('PRAGMA foreign_key_check').fetchall(), [])


    def test_perfiles_antiguos_con_rut_equivalente_no_bloquean_altas(self):
        primero = Asistentes.objects.create(rut='12.345.678-5', nombre='Histórico', correo='', telefono='')
        canonico = Asistentes.objects.create(rut='12345678-5', nombre='Canónico', correo='', telefono='')
        sesion = self.crear('Registro de asistencia')
        response, _ = self.registrar(sesion, rut='12.345.678-5')
        self.assertEqual(response.status_code, 201, response.content)
        asistencia = Asistencias.objects.get(id=response.json()['asistencia_id'])
        self.assertEqual(asistencia.asistente_id, canonico.id)
        primero.refresh_from_db()
        self.assertEqual(primero.nombre, 'Histórico')
        self.assertEqual(Asistentes.objects.count(), 2)
        self.assertEqual(normalizar_rut('1-9'), '1-9')


    def test_notas_antiguas_ilegibles_no_se_sobrescriben(self):
        s = self.crear()
        Sesiones.objects.filter(id=s.id).update(campos_valores_json='contenido antiguo ilegible')
        result = self.h.post(f'/api/sesiones/{s.id}/desarrollo/', {'campos': {'desarrollo_de_la_entrevista': 'Nuevo texto'}, 'base': {}}, content_type='application/json')
        self.assertEqual(result.status_code, 409)
        s.refresh_from_db()
        self.assertEqual(s.campos_valores_json, 'contenido antiguo ilegible')


    def test_roles_configurables_y_cuentas_solo_superusuario(self):
        from .models import AccesoUsuario, RolAcceso
        from .permissions import migrar_cuentas
        from django.contrib.auth.hashers import check_password
        migrar_cuentas()
        self.assertTrue(AccesoUsuario.objects.get(usuario=self.admin).superusuario)
        self.assertFalse(AccesoUsuario.objects.get(usuario=self.host).superusuario)
        self.assertEqual(self.h.post('/roles-permisos/', {'accion': 'rol', 'nombre': 'Intruso'}).status_code, 302)
        self.assertFalse(RolAcceso.objects.filter(nombre='Intruso').exists())
        self.assertEqual(self.a.get('/roles-permisos/').status_code, 200)
        response = self.a.post('/roles-permisos/', {
            'accion': 'rol', 'nombre': 'Solo consulta', 'consultar': 'TODAS'})
        self.assertEqual(response.status_code, 302)
        rol = RolAcceso.objects.get(nombre='Solo consulta')
        response = self.a.post('/roles-permisos/', {
            'accion': 'usuario', 'nombre': 'Docente nuevo', 'correo': 'nuevo@example.com',
            'password': 'Clave-inicial-valida-2026!', 'rol': rol.id, 'sede': self.sede.id, 'area': self.area.id})
        self.assertEqual(response.status_code, 302)
        usuario = Usuarios.objects.get(correo='nuevo@example.com')
        self.assertTrue(check_password('Clave-inicial-valida-2026!', usuario.password_hash))
        self.assertFalse(AccesoUsuario.objects.get(usuario=usuario).superusuario)
        self.assertEqual(self.a.post('/roles-permisos/', {
            'accion': 'asignar', 'usuario': self.admin.id, 'rol': rol.id}).status_code, 200)
        self.assertTrue(AccesoUsuario.objects.get(usuario=self.admin).superusuario)

    def test_roles_revocacion_efectiva_en_servidor(self):
        from .models import AccesoUsuario, RolAcceso
        from .permissions import migrar_cuentas
        migrar_cuentas()
        sesion = self.crear()
        consulta = RolAcceso.objects.get(nombre='Consulta propia')
        self.a.post('/roles-permisos/', {'accion': 'asignar', 'usuario': self.host.id, 'rol': consulta.id})
        self.assertEqual(self.h.post(f'/api/sesiones/{sesion.id}/cerrar/').status_code, 403)
        self.assertEqual(self.h.post('/api/sesiones/crear/', {}, content_type='application/json').status_code, 403)
        self.assertEqual(self.h.get('/api/administrador/exportar/pdf/', {'sesiones': sesion.id}).status_code, 403)
        self.assertEqual(self.h.get(f'/api/sesiones/{sesion.id}/asistencias/lista/').status_code, 200)
        self.assertEqual(self.o.get(f'/api/sesiones/{sesion.id}/asistencias/lista/').status_code, 403)
        consulta.consultar = 'TODAS'
        consulta.save()
        self.assertEqual(self.h.get('/roles-permisos/').status_code, 302)
        self.a.post('/roles-permisos/', {'accion': 'asignar', 'usuario': self.other.id, 'rol': consulta.id})
        self.assertEqual(self.o.get(f'/api/sesiones/{sesion.id}/asistencias/lista/').status_code, 200)
        self.assertEqual(self.o.get('/api/administrador/exportar/pdf/', {'sesiones': sesion.id}).status_code, 403)
        self.assertEqual(self.o.post(f'/api/sesiones/{sesion.id}/cerrar/').status_code, 403)

    def test_rol_duplicado_y_correo_duplicado_no_cambian_cuentas(self):
        from .models import RolAcceso, AccesoUsuario
        from .permissions import migrar_cuentas
        migrar_cuentas()
        rol = RolAcceso.objects.get(nombre='Docente')
        self.assertEqual(self.a.post('/roles-permisos/', {
            'accion': 'rol', 'nombre': 'docente'}).status_code, 200)
        rol.refresh_from_db()
        self.assertEqual(rol.crear, 'PROPIAS')
        cantidad = Usuarios.objects.count()
        self.a.post('/roles-permisos/', {
            'accion': 'usuario', 'nombre': 'Duplicado', 'correo': self.host.correo.upper(),
            'password': 'Clave-inicial-valida-2026!', 'rol': rol.id, 'sede': self.sede.id, 'area': self.area.id})
        self.assertEqual(Usuarios.objects.count(), cantidad)
        self.a.post('/roles-permisos/', {
            'accion': 'rol', 'rol_id': rol.id, 'nombre': rol.nombre, 'consultar': 'PROPIAS', 'exportar': 'PROPIAS'})
        rol.refresh_from_db()
        self.assertEqual(rol.crear, 'NINGUNA')
        self.assertEqual(rol.exportar, 'PROPIAS')
        self.assertEqual(self.h.post('/api/sesiones/crear/', {}, content_type='application/json').status_code, 403)


    def test_matriz_alcances_por_accion(self):
        from .models import RolAcceso, AccesoUsuario
        from .permissions import migrar_cuentas
        migrar_cuentas()
        propia = self.crear()
        ajena = self.crear()
        ajena.programacion.creador = self.other
        ajena.programacion.save()
        ajena.anfitrion = self.other
        ajena.save(update_fields=['anfitrion'])
        rol = RolAcceso.objects.create(nombre='Matriz', consultar='TODAS')
        AccesoUsuario.objects.filter(usuario=self.host).update(rol=rol)
        for accion in ('observaciones', 'cerrar', 'exportar'):
            for alcance in ('NINGUNA', 'PROPIAS', 'TODAS'):
                setattr(rol, accion, alcance)
                rol.save()
                for sesion in (propia, ajena):
                    with self.subTest(accion=accion, alcance=alcance, propia=sesion.id == propia.id):
                        if accion == 'observaciones':
                            respuesta = self.h.post(f'/api/sesiones/{sesion.id}/desarrollo/',
                                                    {'campos': {}, 'base': {}}, content_type='application/json')
                        elif accion == 'cerrar':
                            respuesta = self.h.post(f'/api/sesiones/{sesion.id}/cerrar/')
                        else:
                            respuesta = self.h.get('/api/sesiones/exportar/pdf/', {'sesiones': sesion.id})
                        permitido = alcance == 'TODAS' or (alcance == 'PROPIAS' and sesion.id == propia.id)
                        self.assertEqual(respuesta.status_code, 200 if permitido else 403, respuesta.content)
                setattr(rol, accion, 'NINGUNA')
                rol.save()
        for alcance, ids in [('NINGUNA', []), ('PROPIAS', [propia.id]), ('TODAS', [ajena.id, propia.id])]:
            rol.consultar = alcance
            rol.save()
            self.assertEqual([s['id'] for s in self.h.get('/api/sesiones/').json()['sesiones']], ids)
            esperado = 200 if alcance == 'TODAS' else 403
            self.assertEqual(self.h.get(f'/api/sesiones/{ajena.id}/asistencias/lista/').status_code, esperado)
        rol.consultar = 'TODAS'
        for alcance in ('NINGUNA', 'PROPIAS', 'TODAS'):
            rol.crear = alcance
            rol.save()
            for anfitrion in (self.host, self.other):
                plantilla = PlantillasSesion.objects.get(nombre='Acta de reunión')
                valores = {c.nombre: 'Dato de prueba' for c in plantilla.camposplantilla_set.all()}
                respuesta = self.h.post('/api/sesiones/crear/', {
                    'nombre': 'Prueba de alcance', 'fecha_programada': '2026-11-20T10:00', 'plantilla_id': plantilla.id,
                    'anfitrion_id': anfitrion.id, 'campos': valores}, content_type='application/json')
                permitido = alcance != 'NINGUNA'
                self.assertEqual(respuesta.status_code, 201 if permitido else 403, respuesta.content)


    def test_aislamiento_organizacional_y_clasificacion_inmutable(self):
        from .models import AccesoUsuario, AreaAcademica, SedeAcademica, AmbitoPermiso, RolAcceso
        sesion = self.crear()
        otra_area = AreaAcademica.objects.exclude(id=self.area.id).first()
        otra_sede = SedeAcademica.objects.exclude(id=self.sede.id).first()
        acceso = AccesoUsuario.objects.get(usuario=self.other)
        acceso.area = otra_area
        acceso.save()
        rol = RolAcceso.objects.create(nombre='Coordinación de prueba', consultar='TODAS',
            observaciones='TODAS', cerrar='TODAS', exportar='TODAS')
        for accion in ('consultar', 'observaciones', 'cerrar', 'exportar'):
            AmbitoPermiso.objects.create(rol=rol, accion=accion, modo_sedes='PERFIL', modo_areas='PERFIL')
        acceso.rol = rol
        acceso.save()
        self.assertEqual(self.o.get('/api/sesiones/').json()['sesiones'], [])
        self.assertEqual(self.o.get(f'/api/sesiones/{sesion.id}/asistencias/lista/').status_code, 403)
        self.assertEqual(self.o.post(f'/api/sesiones/{sesion.id}/cerrar/').status_code, 403)
        self.assertEqual(self.o.get('/api/administrador/exportar/pdf/', {'sesiones': sesion.id}).status_code, 403)
        for ambito in rol.ambitos.all():
            ambito.modo_areas = 'SELECCION'
            ambito.save()
            ambito.areas.add(self.area)
        self.assertEqual(self.o.get(f'/api/sesiones/{sesion.id}/asistencias/lista/').status_code, 200)
        self.assertEqual(self.o.get('/api/administrador/exportar/pdf/', {'sesiones': sesion.id}).status_code, 200)
        acceso.sede = otra_sede
        acceso.save()
        self.assertEqual(self.o.get(f'/api/sesiones/{sesion.id}/asistencias/lista/').status_code, 403)
        AccesoUsuario.objects.filter(usuario=self.host).update(area=otra_area)
        sesion.refresh_from_db()
        self.assertEqual(sesion.contexto.area_id, self.area.id)
        self.assertEqual(sesion.contexto.sede_id, self.sede.id)

    def test_no_es_posible_autocambiar_area_y_creacion_fuera_de_ambito(self):
        from .models import AccesoUsuario, AreaAcademica, AmbitoPermiso
        otra_area = AreaAcademica.objects.exclude(id=self.area.id).first()
        acceso = AccesoUsuario.objects.get(usuario=self.other)
        acceso.area = otra_area
        acceso.save()
        self.assertEqual(self.h.post('/roles-permisos/', {
            'accion': 'perfil', 'usuario': self.host.id,
            'sede': self.sede.id, 'area': otra_area.id}).status_code, 302)
        self.assertEqual(AccesoUsuario.objects.get(usuario=self.host).area_id, self.area.id)
        rol = AccesoUsuario.objects.get(usuario=self.host).rol
        rol.crear = 'TODAS'
        rol.save()
        plantilla = PlantillasSesion.objects.get(nombre='Acta de reunión')
        respuesta = self.h.post('/api/sesiones/crear/', {
            'nombre': 'Fuera del área', 'fecha_programada': '2026-11-20T10:00', 'plantilla_id': plantilla.id,
            'anfitrion_id': self.other.id, 'campos': {c.nombre: 'Dato' for c in plantilla.camposplantilla_set.all()}}, content_type='application/json')
        self.assertEqual(respuesta.status_code, 201)
        inicio = self.h.post(f"/api/sesiones/{respuesta.json()['id']}/iniciar/", {'anfitrion_id': self.other.pk, 'rut': '12345678-5', 'firma': self.png}, content_type='application/json')
        self.assertEqual(inicio.status_code, 400)

    def test_guardar_varias_sedes_y_areas_de_rol(self):
        from .models import RolAcceso, SedeAcademica, AreaAcademica
        sedes = list(SedeAcademica.objects.values_list('pk', flat=True)[:2])
        areas = list(AreaAcademica.objects.values_list('pk', flat=True)[:2])
        datos = {'accion': 'rol', 'nombre': 'Coordinación múltiple', 'consultar': 'TODAS',
                 'consultar_sedes_modo': 'SELECCION', 'consultar_areas_modo': 'SELECCION',
                 'consultar_sedes': sedes, 'consultar_areas': areas}
        respuesta = self.a.post('/roles-permisos/', datos)
        rol = RolAcceso.objects.get(nombre=datos['nombre'])
        self.assertRedirects(respuesta, '/roles-permisos/?rol=' + str(rol.pk))
        regla = rol.ambitos.get(accion='consultar')
        self.assertSetEqual(set(regla.sedes.values_list('pk', flat=True)), set(sedes))
        self.assertSetEqual(set(regla.areas.values_list('pk', flat=True)), set(areas))
        datos.update(rol_id=rol.pk, consultar_sedes=sedes[:1], consultar_areas=areas[1:])
        self.a.post('/roles-permisos/', datos)
        self.assertSetEqual(set(regla.sedes.values_list('pk', flat=True)), set(sedes[:1]))
        self.assertSetEqual(set(regla.areas.values_list('pk', flat=True)), set(areas[1:]))

    def test_superusuario_delegado_por_rol_y_revocacion(self):
        from .models import RolAcceso, AccesoUsuario
        from .permissions import tiene_permiso
        from .organizacion import permite_contexto
        datos = {'accion': 'rol', 'nombre': 'Docente con administración', 'superusuario': 'on'}
        respuesta = self.a.post('/roles-permisos/', datos)
        self.assertEqual(respuesta.status_code, 302)
        rol = RolAcceso.objects.get(nombre=datos['nombre'])
        self.assertTrue(rol.superusuario)
        respuesta = self.a.post('/roles-permisos/', {'accion': 'asignar', 'usuario': self.host.pk, 'rol': rol.pk})
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(self.h.get('/roles-permisos/').status_code, 200)
        actor = Usuarios.objects.get(pk=self.host.pk)
        self.assertTrue(tiene_permiso(actor, 'superusuario'))
        self.assertTrue(permite_contexto(actor, 'consultar', None, None))
        # El administrador delegado puede crear otro rol y conceder administración.
        self.assertEqual(self.h.post('/roles-permisos/', {
            'accion': 'rol', 'nombre': 'Administración delegada', 'superusuario': 'on'}).status_code, 302)
        # La cuenta inicial conserva sus facultades aunque intenten cambiarle el rol.
        base = AccesoUsuario.objects.get(usuario=self.admin)
        self.h.post('/roles-permisos/', {'accion': 'asignar', 'usuario': self.admin.pk, 'rol': rol.pk})
        base.refresh_from_db()
        self.assertTrue(base.superusuario)
        self.assertNotEqual(base.rol_id, rol.pk)
        datos.update(rol_id=rol.pk)
        datos.pop('superusuario')
        self.a.post('/roles-permisos/', datos)
        rol.refresh_from_db()
        self.assertFalse(rol.superusuario)
        self.assertEqual(self.h.get('/roles-permisos/').status_code, 302)
        self.assertFalse(tiene_permiso(Usuarios.objects.get(pk=self.host.pk), 'superusuario'))

    def test_documentos_pdf_y_excel_ocho_plantillas(self):
        from .documentos import construir_documento
        for nombre, _, _ in CATALOGO:
            if nombre in (EPP, PANOL): continue
            with self.subTest(plantilla=nombre):
                sesion = self.crear(nombre)
                respuesta, _ = self.registrar(sesion)
                self.firmar(respuesta.json()['asistencia_id'])
                query = {'sesiones': sesion.pk}
                pdf = self.h.get('/api/sesiones/exportar/pdf/', query)
                self.assertEqual(pdf.status_code, 200, pdf.content[:200])
                self.assertTrue(pdf.content.startswith(b'%PDF-'))
                excel = self.h.get('/api/sesiones/exportar/xlsx/', query)
                self.assertEqual(excel.status_code, 200)
                libro = load_workbook(io.BytesIO(excel.content))
                self.assertEqual(len(libro.worksheets), 1)
                hoja = libro.active
                self.assertEqual(len(hoja._images), 2 if sesion.plantilla.nombre == 'Registro de asistencia' else 3)
                self.assertEqual(hoja.page_setup.fitToWidth, 1)
                self.assertEqual(hoja.page_setup.fitToHeight, 0)
                self.assertTrue(hoja.print_area)
                self.assertTrue(any('Persona de prueba' in str(c.value) for fila in hoja for c in fila))

    def test_documento_sesenta_asistentes_y_observacion_extensa(self):
        from .documentos import construir_documento, pdf_documentos, xlsx_documentos
        sesion = self.crear('Registro de asistencia')
        for i in range(60):
            persona = Asistentes.objects.create(nombre=f'Asistente {i+1}', telefono='', correo='')
            a = Asistencias.objects.create(sesion=sesion, asistente=persona, nombre_registrado=persona.nombre,
                rut_registrado='', correo_registrado='', telefono_registrado='', estado='FIRMADO')
            Firmas.objects.create(asistencia=a, imagen=base64.b64decode(self.png.split(',')[1]), formato='image/png')
        doc = construir_documento(sesion)
        pdf = pdf_documentos([doc])
        import re
        self.assertGreater(len(re.findall(rb'/Type /Page\b',pdf)), 1)
        hoja = load_workbook(io.BytesIO(xlsx_documentos([doc]))).active
        self.assertEqual(len(hoja._images), 61)
        self.assertEqual(hoja['B69'].value, 'Asistente 60')
        self.assertEqual(hoja.print_title_rows, '$1:$8')
        sesion = self.crear('Entrevista con estudiante')
        sesion.campos_valores_json = json.dumps({'desarrollo_de_la_entrevista': 'Observación extensa. ' * 450})
        self.assertTrue(pdf_documentos([construir_documento(sesion)]).startswith(b'%PDF-'))

    def test_mi_cuenta_visible_sin_reconfirmar_pero_cambios_protegidos(self):
        respuesta = self.h.get('/mi-cuenta/')
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, self.host.correo)
        self.assertContains(respuesta, 'Guardar cambios')
        self.assertNotContains(respuesta, 'Ver información')
        respuesta = self.h.post('/mi-cuenta/', {'accion': 'guardar', 'nombre': 'Cambio no autorizado', 'correo': 'otro@example.org'})
        self.host.refresh_from_db()
        self.assertNotEqual(self.host.nombre, 'Cambio no autorizado')
        self.assertContains(respuesta, 'La contraseña actual no es correcta.')
        self.assertEqual(self.client.get('/mi-cuenta/').status_code, 302)

    def test_cambiar_sede_area_en_mi_cuenta(self):
        from .models import SedeAcademica, AreaAcademica, AccesoUsuario
        sede = SedeAcademica.objects.exclude(pk=self.sede.pk).first()
        area = AreaAcademica.objects.exclude(pk=self.area.pk).first()
        datos = {'accion': 'guardar', 'nombre': self.host.nombre, 'correo': self.host.correo,
                 'actual': 'Prueba-valida-2026!', 'sede': sede.pk, 'area': area.pk}
        sesion = self.crear()
        respuesta = self.h.post('/mi-cuenta/', datos)
        self.assertContains(respuesta, 'Información actualizada.')
        perfil = AccesoUsuario.objects.get(usuario=self.host)
        self.assertEqual((perfil.sede_id,perfil.area_id),(sede.pk,area.pk))
        self.assertFalse(perfil.superusuario)
        sesion.refresh_from_db()
        self.assertEqual(sesion.contexto.area_id,self.area.pk)
        datos['area'] = '9999999'
        self.assertContains(self.h.post('/mi-cuenta/',datos),'Selecciona una sede y un área académica válidas.')
        perfil.refresh_from_db()
        self.assertEqual(perfil.area_id,area.pk)

    def test_programar_cambiar_anfitrion_firmar_y_conservar_qr(self):
        from .models import ProgramacionSesion
        plantilla = PlantillasSesion.objects.get(nombre='Registro de asistencia')
        datos = {'nombre': 'Charla del viernes', 'plantilla_id': plantilla.pk, 'anfitrion_id': self.host.pk,
                 'fecha_programada': '2026-11-20T10:00', 'campos': {'tema':'Redes','lugar':'Auditorio'}}
        respuesta = self.h.post('/api/sesiones/crear/', datos, content_type='application/json')
        self.assertEqual(respuesta.status_code,201,respuesta.content)
        s = Sesiones.objects.get(pk=respuesta.json()['id'])
        qr = s.token_qr
        self.assertEqual(s.estado,'PROGRAMADA')
        self.assertIsNone(s.fecha_inicio)
        self.assertIsNone(s.anfitrion_id)
        self.assertEqual(s.programacion.creador_id,self.host.pk)
        self.assertEqual(self.h.get(f'/api/sesiones/{s.pk}/afiche.pdf').status_code,200)
        publico = self.client.get(f'/api/sesiones/{qr}/').json()
        self.assertEqual(publico['estado'],'PROGRAMADA')
        self.assertEqual(self.registrar(s)[0].status_code,409)
        self.assertEqual(self.h.post(f'/api/sesiones/{s.pk}/cerrar/').status_code,409)
        sin_firma = self.h.post(f'/api/sesiones/{s.pk}/iniciar/', {'anfitrion_id':self.other.pk,'rut':'12345678-5'}, content_type='application/json')
        self.assertEqual(sin_firma.status_code,400)
        s.refresh_from_db(); self.assertEqual(s.estado,'PROGRAMADA')
        # Un usuario ajeno no puede iniciar la programación de otro.
        self.assertEqual(self.o.post(f'/api/sesiones/{s.pk}/iniciar/', {'anfitrion_id':self.other.pk,'rut':'12345678-5','firma':self.png}, content_type='application/json').status_code,403)
        inicio = self.h.post(f'/api/sesiones/{s.pk}/iniciar/', {'anfitrion_id':self.other.pk,'rut':'12345678-5','firma':self.png}, content_type='application/json')
        self.assertEqual(inicio.status_code,200,inicio.content)
        s.refresh_from_db()
        self.assertEqual(s.anfitrion_id,self.other.pk)
        self.assertEqual(s.token_qr,qr)
        self.assertTrue(s.fecha_inicio)
        self.assertEqual(s.programacion.creador_id,self.host.pk)
        self.assertEqual(s.programacion.iniciada_por_id,self.host.pk)
        self.assertTrue(s.programacion.firma_anfitrion)
        self.assertEqual(self.h.post(f'/api/sesiones/{s.pk}/iniciar/', {'anfitrion_id':self.host.pk,'rut':'12345678-5','firma':self.png}, content_type='application/json').status_code,409)
        self.assertEqual(self.o.get(f'/api/sesiones/{s.pk}/asistencias/lista/').status_code,200)
        respuesta,_ = self.registrar(s)
        self.assertEqual(respuesta.status_code,201)
        listado = self.h.get(f'/api/sesiones/{s.pk}/asistencias/lista/').json()['asistencias']
        self.assertTrue(listado[0]['es_anfitrion'])
        self.assertEqual(listado[0]['nombre'],self.other.nombre)
        self.assertEqual(listado[0]['estado'],'FIRMADO')
        from .documentos import construir_documento
        documento = construir_documento(s)
        self.assertEqual(documento['asistentes'][0].nombre_registrado,self.other.nombre)
        self.assertEqual(documento['asistentes'][0].cargo_registrado,'Anfitrión')
        self.assertEqual(len(documento['asistentes']),2)
        self.assertEqual(self.h.get('/api/sesiones/exportar/pdf/',{'sesiones':s.pk}).status_code,200)
        self.assertEqual(self.h.get('/api/sesiones/exportar/xlsx/',{'sesiones':s.pk}).status_code,200)
