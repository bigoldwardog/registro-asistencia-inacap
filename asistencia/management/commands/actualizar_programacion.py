import re
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

class Command(BaseCommand):
    help = 'Permite actividades programadas sin anfitrión ni inicio real, conservando registros.'
    def handle(self, *args, **options):
        if connection.vendor != 'sqlite':
            raise CommandError('Este comando solo adapta bases SQLite antiguas. Usa preparar_sistema para PostgreSQL.')
        connection.ensure_connection()
        db = connection.connection
        original = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='sesiones'").fetchone()[0]
        if 'PROGRAMADA' in original: return
        if db.in_transaction: raise CommandError('Se requiere una conexión sin transacción activa.')
        if db.execute('PRAGMA foreign_key_check').fetchall(): raise CommandError('Hay referencias inválidas; no se modificó la base.')
        db.execute('PRAGMA foreign_keys=OFF')
        try:
            db.execute('BEGIN IMMEDIATE')
            nuevo = re.sub(r'(?i)anfitrion_id\s+INTEGER\s+NOT NULL', 'anfitrion_id INTEGER', original)
            nuevo = re.sub(r'(?i)fecha_inicio\s+TEXT\s+NOT NULL', 'fecha_inicio TEXT', nuevo)
            nuevo = nuevo.replace("'ABIERTA', 'CERRADA'", "'PROGRAMADA', 'ABIERTA', 'CERRADA'")
            if 'PROGRAMADA' not in nuevo: raise CommandError('El esquema de estados no coincide con el esperado.')
            nuevo = re.sub(r'(?i)CREATE TABLE(?: IF NOT EXISTS)?\s+["`\[]?sesiones["`\]]?', 'CREATE TABLE sesiones_programables', nuevo, count=1)
            extras = db.execute("SELECT sql FROM sqlite_master WHERE tbl_name='sesiones' AND type IN ('index','trigger') AND sql IS NOT NULL").fetchall()
            columnas = ', '.join('"'+r[1]+'"' for r in db.execute('PRAGMA table_info(sesiones)'))
            db.execute(nuevo)
            db.execute(f'INSERT INTO sesiones_programables ({columnas}) SELECT {columnas} FROM sesiones')
            db.execute('DROP TABLE sesiones')
            db.execute('ALTER TABLE sesiones_programables RENAME TO sesiones')
            for (sql,) in extras: db.execute(sql)
            if db.execute('PRAGMA foreign_key_check').fetchall(): raise CommandError('Falló la comprobación de relaciones.')
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally: db.execute('PRAGMA foreign_keys=ON')
