from django.core.management.base import BaseCommand
from django.core.management import call_command

class Command(BaseCommand):
    help = 'Compatibilidad: prepara el esquema completo sin depender del motor de base de datos.'
    def handle(self, *args, **options):
        call_command('preparar_sistema')
