"""Comprobaciones de preparación de hosting sin usar credenciales ni bases externas."""
import os
import sys
import subprocess
import tempfile
from pathlib import Path
from django.conf import settings
from django.test import SimpleTestCase


class PreparacionHostingTests(SimpleTestCase):
    def entorno(self):
        env = os.environ.copy()
        for key in ('VERCEL','DJANGO_ENV','DJANGO_DEBUG','DJANGO_SECRET_KEY','DATABASE_URL','PUBLIC_SITE_URL','VERCEL_URL','VERCEL_PROJECT_PRODUCTION_URL','DJANGO_ALLOWED_HOSTS','DJANGO_CSRF_TRUSTED_ORIGINS','DJANGO_DATABASE_PATH','INITIAL_ADMIN_PASSWORD'):
            env.pop(key,None)
        return env

    def ejecutar(self, argumentos, env):
        return subprocess.run([sys.executable,'manage.py',*argumentos],cwd=settings.BASE_DIR,env=env,capture_output=True,text=True,timeout=60)

    def test_produccion_exige_postgresql_y_secreto(self):
        env=self.entorno(); env.update(DJANGO_ENV='production',PUBLIC_SITE_URL='https://demo.example.invalid')
        respuesta=self.ejecutar(['check'],env)
        self.assertNotEqual(respuesta.returncode,0)
        self.assertIn('DJANGO_SECRET_KEY',respuesta.stderr)
        env['DJANGO_SECRET_KEY']='clave-sintetica-de-pruebas-mayor-de-cincuenta-caracteres-2026'
        respuesta=self.ejecutar(['check'],env)
        self.assertNotEqual(respuesta.returncode,0)
        self.assertIn('DATABASE_URL',respuesta.stderr)

    def test_configuracion_postgresql_y_build_sin_conectar(self):
        env=self.entorno(); env.update(VERCEL='1',DJANGO_DEBUG='0',DJANGO_SECRET_KEY='clave-sintetica-de-pruebas-mayor-de-cincuenta-caracteres-2026',PUBLIC_SITE_URL='https://demo.example.invalid',DATABASE_URL='postgresql://prueba:prueba@127.0.0.1:1/demo')
        respuesta=self.ejecutar(['check','--deploy','--fail-level','ERROR'],env)
        self.assertEqual(respuesta.returncode,0,respuesta.stderr)
        respuesta=self.ejecutar(['shell','-c',"from django.conf import settings; d=settings.DATABASES['default']; assert d['ENGINE'].endswith('postgresql'); assert d['OPTIONS']['sslmode']=='require'; assert d['CONN_MAX_AGE']==0; assert d['DISABLE_SERVER_SIDE_CURSORS']; assert settings.SESSION_COOKIE_SECURE; assert settings.CSRF_COOKIE_SECURE"],env)
        self.assertEqual(respuesta.returncode,0,respuesta.stderr)
        env['DATABASE_URL']='sqlite:///:memory:'
        self.assertNotEqual(self.ejecutar(['check'],env).returncode,0)

    def test_instalacion_sqlite_vacia_alta_unica_y_estaticos(self):
        with tempfile.TemporaryDirectory() as carpeta:
            env=self.entorno(); env['DJANGO_DATABASE_PATH']=str(Path(carpeta)/'instalacion.db')
            for _ in range(2):
                r=self.ejecutar(['preparar_sistema'],env)
                self.assertEqual(r.returncode,0,r.stderr)
            env['INITIAL_ADMIN_PASSWORD']='Clave-ficticia-inicial-2026!'
            args=['crear_superusuario_inicial','--nombre','Cuenta de prueba','--correo','prueba@example.invalid','--sede-id','1','--area-id','1']
            r=self.ejecutar(args,env)
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertNotIn(env['INITIAL_ADMIN_PASSWORD'],r.stdout+r.stderr)
            self.assertNotEqual(self.ejecutar(args,env).returncode,0)
            r=self.ejecutar(['auditar_integridad'],env)
            self.assertEqual(r.returncode,0,r.stderr)
            r=self.ejecutar(['collectstatic','--noinput'],env)
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertTrue((Path(settings.BASE_DIR)/'staticfiles/img/inacap-60.png').exists())
