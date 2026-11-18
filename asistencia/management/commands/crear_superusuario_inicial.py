from getpass import getpass
import os
from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.contrib.auth.hashers import make_password
from django.contrib.auth.password_validation import validate_password
from django.db import transaction, IntegrityError
from asistencia.models import Usuarios, AccesoUsuario, RolAcceso, SedeAcademica, AreaAcademica
from asistencia.permissions import migrar_cuentas

class Command(BaseCommand):
    help = 'Crea la primera cuenta de la aplicación sin exponer configuración inicial en internet.'
    def add_arguments(self, parser):
        parser.add_argument('--nombre', required=True)
        parser.add_argument('--correo', required=True)
        parser.add_argument('--sede-id', type=int, required=True)
        parser.add_argument('--area-id', type=int, required=True)
    def handle(self, *args, **options):
        if Usuarios.objects.exists():
            raise CommandError('Ya existen cuentas. No se sobrescribió ninguna.')
        try:
            correo = options['correo'].strip().lower()
            nombre = options['nombre'].strip()
            if not nombre or len(nombre)>150: raise ValidationError('Indica un nombre válido.')
            validate_email(correo)
            sede = SedeAcademica.objects.get(pk=options['sede_id'])
            area = AreaAcademica.objects.get(pk=options['area_id'])
            password = os.environ.get('INITIAL_ADMIN_PASSWORD')
            if password is None:
                password = getpass('Contraseña inicial (no se muestra): ')
                if password != getpass('Repetir contraseña: '): raise ValidationError('Las contraseñas no coinciden.')
            if len(password)>256: raise ValidationError('Contraseña demasiado larga.')
            validate_password(password)
            with transaction.atomic():
                if Usuarios.objects.exists(): raise CommandError('La primera cuenta ya se creó.')
                migrar_cuentas()
                rol = RolAcceso.objects.get(nombre='Superusuario')
                usuario = Usuarios.objects.create(nombre=nombre, correo=correo, password_hash=make_password(password), rol='ADMINISTRADOR', activo=1)
                AccesoUsuario.objects.create(usuario=usuario, rol=rol, superusuario=True, sede=sede, area=area)
        except (ValidationError, SedeAcademica.DoesNotExist, AreaAcademica.DoesNotExist) as error:
            raise CommandError('Datos inválidos: ' + str(error)) from None
        except IntegrityError:
            raise CommandError('La cuenta ya existe o se creó simultáneamente. No se sobrescribió ninguna.') from None
        self.stdout.write(self.style.SUCCESS('Cuenta inicial creada. Inicia sesión en /ingresar/.'))
