from django.core.management.base import BaseCommand
from django.db import connection

class Command(BaseCommand):
    help = "Añade almacenamiento independiente para las firmas de devolución de EPP."
    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            cursor.execute("\nCREATE TABLE IF NOT EXISTS firmas_devolucion (\n    id INTEGER PRIMARY KEY AUTOINCREMENT,\n    asistencia_id INTEGER NOT NULL UNIQUE REFERENCES asistencias(id) ON DELETE RESTRICT,\n    imagen BLOB NOT NULL,\n    formato TEXT NOT NULL DEFAULT 'image/png',\n    fecha_creacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP\n);\n")
        self.stdout.write(self.style.SUCCESS("Firmas de devolución de EPP habilitadas."))
