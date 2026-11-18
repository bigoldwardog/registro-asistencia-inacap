from pathlib import Path
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connection
from asistencia.models import Usuarios, Asistentes
from asistencia.domain import normalizar_rut, ErrorFormulario

class Command(BaseCommand):
    help = 'Inicializa o actualiza el esquema conservando las sesiones existentes. No carga datos de prueba.'
    def handle(self, *args, **options):
        call_command('migrate', interactive=False, verbosity=0)
        connection.ensure_connection()
        connection.connection.executescript((Path(settings.BASE_DIR) / 'database/schema.sql').read_text(encoding='utf-8-sig'))
        call_command('actualizar_formularios')
        call_command('actualizar_programacion')
        with connection.cursor() as c:
            c.execute('PRAGMA table_info(usuarios)')
            if 'telefono' not in {r[1] for r in c.fetchall()}:
                c.execute("ALTER TABLE usuarios ADD COLUMN telefono TEXT NOT NULL DEFAULT ''")
            c.execute('PRAGMA table_info(asistencias)')
            if 'campos_participante_json' not in {r[1] for r in c.fetchall()}:
                c.execute("ALTER TABLE asistencias ADD COLUMN campos_participante_json TEXT NOT NULL DEFAULT '{}'")
        call_command('cargar_plantillas')
        from asistencia.organizacion import cargar_catalogo
        cargar_catalogo()
        Usuarios.objects.filter(password_hash='HASH_SOLO_PARA_PRUEBAS').update(activo=0)
        from asistencia.permissions import migrar_cuentas
        migrar_cuentas()
        conflictos = 0
        for persona in Asistentes.objects.exclude(rut__isnull=True):
            try:
                canonico = normalizar_rut(persona.rut)
            except ErrorFormulario:
                continue
            if Asistentes.objects.filter(rut=canonico).exclude(id=persona.id).exists():
                conflictos += 1
                continue
            persona.rut = canonico
            persona.save(update_fields=['rut'])
        self.stdout.write(self.style.SUCCESS('Sistema preparado. No se cargaron sesiones ni personas de prueba.'))
        if conflictos:
            self.stdout.write(self.style.WARNING(f'{conflictos} perfiles históricos con RUT equivalente se conservaron; las nuevas altas usan el perfil canónico.'))
