import re
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

class Command(BaseCommand):
    help = "Adapta la base SQLite para formularios sin RUT y para el cargo por asistencia."
    def handle(self, *args, **options):
        if connection.vendor != 'sqlite':
            raise CommandError('Este comando solo adapta bases SQLite antiguas. Usa preparar_sistema para PostgreSQL.')
        connection.ensure_connection()
        db = connection.connection
        if db.in_transaction:
            raise CommandError("La actualización requiere una conexión sin transacción activa.")
        if db.execute("PRAGMA foreign_key_check").fetchall():
            raise CommandError("Existen referencias inválidas; no se modificó el esquema.")
        db.execute("PRAGMA foreign_keys=OFF")
        try:
            db.execute("BEGIN IMMEDIATE")
            columns = {row[1]: row for row in db.execute("PRAGMA table_info(asistentes)")}
            if columns['rut'][3]:
                original = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='asistentes'").fetchone()[0]
                replacement, count = re.subn(r'(?i)\brut\s+TEXT\s+NOT\s+NULL', 'rut TEXT', original)
                if count != 1:
                    raise CommandError("El esquema de asistentes no coincide con el esperado.")
                replacement = re.sub(r'(?i)CREATE TABLE(?: IF NOT EXISTS)?\s+[\"`\[]?asistentes[\"`\]]?', 'CREATE TABLE asistentes_actualizados', replacement, count=1)
                extras = db.execute("SELECT sql FROM sqlite_master WHERE tbl_name='asistentes' AND type IN ('index','trigger') AND sql IS NOT NULL").fetchall()
                db.execute(replacement)
                names = ', '.join('"' + name + '"' for name in columns)
                db.execute(f'INSERT INTO asistentes_actualizados ({names}) SELECT {names} FROM asistentes')
                db.execute('DROP TABLE asistentes')
                db.execute('ALTER TABLE asistentes_actualizados RENAME TO asistentes')
                for (sql,) in extras: db.execute(sql)
            columns = {row[1] for row in db.execute("PRAGMA table_info(asistencias)")}
            if 'cargo_registrado' not in columns:
                db.execute("ALTER TABLE asistencias ADD COLUMN cargo_registrado TEXT NOT NULL DEFAULT ''")
            if 'registro_token' not in columns:
                db.execute('ALTER TABLE asistencias ADD COLUMN registro_token TEXT')
            db.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_asistencias_registro_token ON asistencias(registro_token)')
            if db.execute("PRAGMA foreign_key_check").fetchall():
                raise CommandError("La comprobación de relaciones falló. Se revertirá la actualización.")
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.execute("PRAGMA foreign_keys=ON")
        self.stdout.write(self.style.SUCCESS("Formularios actualizados. Registros y relaciones conservados."))
