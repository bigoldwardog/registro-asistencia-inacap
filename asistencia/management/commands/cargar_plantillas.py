from django.core.management.base import BaseCommand
from asistencia.catalogo_plantillas import cargar_catalogo

class Command(BaseCommand):
    help = "Carga o actualiza las plantillas del cliente sin borrar sesiones existentes."
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS(f"{cargar_catalogo()} plantillas cargadas correctamente."))
