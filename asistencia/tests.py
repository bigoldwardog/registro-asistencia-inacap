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
        self.a = self.login(self.admin); self.h = self.login(self.host); self.o = self.login(self.other)
        self.png = firma_png()

    def login(self, usuario):
        client = Client(); session = client.session; session['usuario_id'] = usuario.id; session.save(); return client

    def crear(self, nombre='Entrevista con estudiante', client=None):
        plantilla = PlantillasSesion.objects.get(nombre=nombre)
        values = {c.nombre: {'fecha': timezone.localdate().isoformat(), 'hora': '10:00', 'email': 'test@example.com', 'numero': '1'}.get(c.tipo, 'Dato de prueba') for c in plantilla.camposplantilla_set.all()}
        response = (client or self.h).post('/api/sesiones/crear/', {'nombre': 'Actividad ' + nombre, 'plantilla_id': plantilla.id, 'anfitrion_id': self.host.id, 'campos': values}, content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)
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
        self.assertEqual(self.h.get('/api/administrador/historial/').status_code, 403)
        self.assertEqual(self.o.get(f'/api/sesiones/{s.id}/asistencias/lista/').status_code, 403)
        self.assertEqual(self.o.post(f'/api/sesiones/{s.id}/cerrar/').status_code, 403)
        self.assertEqual(self.a.get(f'/api/sesiones/{s.id}/asistencias/lista/').status_code, 200)
        self.assertEqual(self.o.get('/api/sesiones/').json()['sesiones'], [])
        self.host.activo = 0; self.host.save()
        self.assertEqual(self.h.get('/api/sesiones/').status_code, 401)

    def test_login_logout_y_usuarios(self):
        c = Client()
        r = c.post('/ingresar/', {'correo': self.host.correo, 'password': 'Prueba-valida-2026!'})
        self.assertEqual(r.status_code, 302); self.assertEqual(c.get('/anfitrion/').status_code, 200)
        self.assertEqual(c.get('/salir/').status_code, 405)
        self.assertEqual(c.post('/salir/').status_code, 302); self.assertEqual(c.get('/api/sesiones/').status_code, 401)
        self.assertEqual(self.h.get('/usuarios/').status_code, 302)
        result = self.a.post('/usuarios/', {'nombre': 'Nueva', 'correo': 'nueva@example.com', 'rol': 'ANFITRION', 'password': 'Otra-clave-valida-2026!'})
        self.assertContains(result, 'Usuario creado')
        self.assertNotEqual(Usuarios.objects.get(correo='nueva@example.com').password_hash, 'Otra-clave-valida-2026!')

    def test_configuracion_inicial_solo_local_y_una_vez(self):
        Usuarios.objects.update(activo=0)
        self.assertEqual(self.client.get('/configuracion-inicial/', REMOTE_ADDR='192.168.1.10').status_code, 403)
        result = self.client.post('/configuracion-inicial/', {'nombre': 'Inicial', 'correo': 'inicial@example.com', 'password': 'Cuenta-inicial-segura-2026!', 'password2': 'Cuenta-inicial-segura-2026!'}, REMOTE_ADDR='127.0.0.1')
        self.assertEqual(result.status_code, 302)
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
        self.assertEqual(listado['asistencias'][0]['cargo'], 'CEO')
        self.assertEqual([f['nombre'] for f in listado['sesion']['campos_asistente']], ['nombre', 'cargo'])
        self.assertEqual(self.a.get('/api/administrador/historial/', {'q': 'No existe'}).json()['sesiones'], [])

    def test_exportar_excel_con_imagenes_y_csv_seguro(self):
        s = self.crear(EPP); r, _ = self.registrar(s, nombre='=FORMULA()'); aid = r.json()['asistencia_id']; self.firmar(aid)
        self.h.post(f'/api/asistencias/{aid}/devolucion/firma/', {'firma': self.png}, content_type='application/json')
        query = {'sesiones': str(s.id)}
        csv = self.a.get('/api/administrador/exportar/csv/', query)
        self.assertEqual(csv.status_code, 200); self.assertIn("'=FORMULA()", csv.content.decode('utf-8-sig'))
        xlsx = self.a.get('/api/administrador/exportar/xlsx/', query)
        self.assertEqual(xlsx.status_code, 200)
        book = load_workbook(io.BytesIO(xlsx.content)); sheet = book['Asistencias']
        self.assertEqual(sheet['H2'].value, '=FORMULA()'); self.assertEqual(sheet['H2'].data_type, 's')
        self.assertEqual(len(sheet._images), 2)
        self.assertIn('Actividades', book.sheetnames)
        self.assertEqual(self.h.get('/api/administrador/exportar/csv/', query).status_code, 403)
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
