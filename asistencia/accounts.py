from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.core.cache import cache
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST
from django.db import transaction
from .access import acceso, cuenta_configurada
from .models import Usuarios
from .views import auditar


def password_valida(password):
    if len(password) > 256:
        raise ValidationError('La contraseña es demasiado larga.')
    validate_password(password)


def configuracion_inicial(request):
    if cuenta_configurada():
        return redirect('login')
    if request.META.get('REMOTE_ADDR') not in ('127.0.0.1', '::1'):
        return render(request, 'cuenta.html', {'modo': 'local', 'titulo': 'Configuración inicial',
            'error': 'Abre http://127.0.0.1:8000/configuracion-inicial/ desde el computador del servidor para crear la primera cuenta.'}, status=403)
    error = ''
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        correo = request.POST.get('correo', '').strip().lower()
        password = request.POST.get('password', '')
        try:
            if not nombre or len(nombre) > 150:
                raise ValidationError('Indica un nombre de hasta 150 caracteres.')
            validate_email(correo)
            password_valida(password)
            if password != request.POST.get('password2'):
                raise ValidationError('Las contraseñas no coinciden.')
            with transaction.atomic():
                if cuenta_configurada():
                    return redirect('login')
                usuario, _ = Usuarios.objects.update_or_create(correo=correo, defaults={
                    'nombre': nombre, 'rol': 'ADMINISTRADOR', 'activo': 1, 'password_hash': make_password(password)})
                request.session.flush()
                request.session['usuario_id'] = usuario.id
                request.actor = usuario
                auditar(request, 'CREAR_ADMINISTRADOR_INICIAL', 'usuario', usuario.id)
            return redirect('administrador')
        except ValidationError as exc:
            error = ' '.join(exc.messages)
    return render(request, 'cuenta.html', {'modo': 'inicial', 'titulo': 'Crear cuenta administradora', 'error': error})


def login(request):
    if not cuenta_configurada():
        return redirect('configuracion_inicial')
    error = ''
    if request.method == 'POST':
        correo = request.POST.get('correo', '').strip().lower()
        key = 'login:' + request.META.get('REMOTE_ADDR', '')
        intentos = cache.get(key, 0)
        usuario = Usuarios.objects.filter(correo__iexact=correo, activo=1).first()
        if intentos >= 10:
            error = 'Demasiados intentos. Intenta nuevamente en diez minutos.'
        elif usuario and check_password(request.POST.get('password', ''), usuario.password_hash):
            cache.delete(key)
            request.session.flush()
            request.session['usuario_id'] = usuario.id
            request.session.set_expiry(8 * 60 * 60)
            return redirect('administrador' if usuario.rol == 'ADMINISTRADOR' else 'anfitrion')
        else:
            cache.set(key, intentos + 1, 600)
            error = 'Correo o contraseña incorrectos.'
    return render(request, 'cuenta.html', {'modo': 'login', 'titulo': 'Iniciar sesión', 'error': error})


@require_POST
def logout(request):
    request.session.flush()
    return redirect('login')


@acceso(admin=True, pagina=True)
def usuarios(request):
    error, mensaje = '', ''
    if request.method == 'POST':
        try:
            if request.POST.get('accion') == 'desactivar':
                usuario = Usuarios.objects.get(id=request.POST.get('id'))
                if usuario.id == request.actor.id:
                    raise ValidationError('No puedes desactivar tu propia cuenta.')
                usuario.activo = 0
                usuario.save(update_fields=['activo'])
                auditar(request, 'DESACTIVAR_USUARIO', 'usuario', usuario.id)
                mensaje = 'Usuario desactivado.'
            else:
                correo = request.POST.get('correo', '').strip().lower()
                nombre = request.POST.get('nombre', '').strip()
                rol = request.POST.get('rol')
                password = request.POST.get('password', '')
                validate_email(correo)
                password_valida(password)
                if not nombre or len(nombre) > 150 or rol not in ('ANFITRION', 'ADMINISTRADOR'):
                    raise ValidationError('Completa nombre y rol correctamente.')
                if Usuarios.objects.filter(correo__iexact=correo).exists():
                    raise ValidationError('Ya existe un usuario con ese correo.')
                usuario = Usuarios.objects.create(nombre=nombre, correo=correo, rol=rol, activo=1, password_hash=make_password(password))
                auditar(request, 'CREAR_USUARIO', 'usuario', usuario.id, despues={'nombre': nombre, 'correo': correo, 'rol': rol})
                mensaje = 'Usuario creado.'
        except (ValidationError, Usuarios.DoesNotExist, ValueError) as exc:
            error = ' '.join(exc.messages) if isinstance(exc, ValidationError) else 'Usuario no válido.'
    return render(request, 'usuarios.html', {'actor': request.actor, 'usuarios': Usuarios.objects.all().order_by('nombre'), 'error': error, 'mensaje': mensaje})


@acceso(pagina=True)
def mi_cuenta(request):
    error, mensaje = '', ''
    if request.method == 'POST':
        password = request.POST.get('password', '')
        try:
            if not check_password(request.POST.get('actual', ''), request.actor.password_hash):
                raise ValidationError('La contraseña actual no es correcta.')
            password_valida(password)
            if password != request.POST.get('password2'):
                raise ValidationError('Las contraseñas nuevas no coinciden.')
            request.actor.password_hash = make_password(password)
            request.actor.save(update_fields=['password_hash'])
            request.session.cycle_key()
            auditar(request, 'CAMBIAR_PASSWORD', 'usuario', request.actor.id)
            mensaje = 'Contraseña actualizada.'
        except ValidationError as exc:
            error = ' '.join(exc.messages)
    return render(request, 'cuenta.html', {'actor': request.actor, 'modo': 'password', 'titulo': 'Mi cuenta', 'error': error, 'mensaje': mensaje})
