import getpass
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.hashers import make_password
from django.core.exceptions import ValidationError
from asistencia.accounts import password_valida
from asistencia.models import Usuarios

class Command(BaseCommand):
    help = 'Cambia la contraseña de un usuario existente de forma interactiva.'
    def add_arguments(self, parser):
        parser.add_argument('--correo', required=True)
    def handle(self, *args, **options):
        try:
            usuario = Usuarios.objects.get(correo__iexact=options['correo'])
        except Usuarios.DoesNotExist:
            raise CommandError('No existe un usuario con ese correo.')
        password = getpass.getpass('Nueva contraseña: ')
        if password != getpass.getpass('Repite la contraseña: '):
            raise CommandError('Las contraseñas no coinciden.')
        try:
            password_valida(password)
        except ValidationError as exc:
            raise CommandError(' '.join(exc.messages))
        usuario.password_hash = make_password(password)
        usuario.activo = 1
        usuario.save(update_fields=['password_hash', 'activo'])
        self.stdout.write(self.style.SUCCESS('Contraseña actualizada.'))
