from django.views.decorators.cache import never_cache
from django.db import IntegrityError
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


@acceso(pagina=True)
@never_cache
def mi_cuenta(request):
    actor = request.actor
    origen = 'administrador' if request.GET.get('panel') != 'anfitrion' and actor.rol == 'ADMINISTRADOR' else 'anfitrion'
    seccion = 'password' if request.GET.get('seccion') == 'password' else 'informacion'
    error = mensaje = ''
    mostrar_datos = False
    if request.method == 'POST':
        clave = request.POST.get('actual', '')
        clave_intentos = f'cuenta:confirmacion:{actor.id}'
        intentos = cache.get(clave_intentos, 0)
        try:
            if intentos >= 10:
                raise ValidationError('Demasiados intentos. Intenta nuevamente en diez minutos.')
            if len(clave) > 256 or not check_password(clave, actor.password_hash):
                cache.set(clave_intentos, intentos + 1, 600)
                raise ValidationError('La contraseña actual no es correcta.')
            cache.delete(clave_intentos)
            accion = request.POST.get('accion')
            if seccion == 'password' and accion == 'password':
                password = request.POST.get('password', '')
                password_valida(password)
                if password != request.POST.get('password2'):
                    raise ValidationError('Las contraseñas nuevas no coinciden.')
                with transaction.atomic():
                    actor.password_hash = make_password(password)
                    actor.save(update_fields=['password_hash'])
                    auditar(request, 'CAMBIAR_PASSWORD', 'usuario', actor.id)
                request.session.cycle_key()
                mensaje = 'Contraseña actualizada.'
            elif seccion == 'informacion' and accion in ('ver', 'guardar'):
                mostrar_datos = True
                if accion == 'guardar':
                    nombre = request.POST.get('nombre', '').strip()
                    correo = request.POST.get('correo', '').strip().lower()
                    if not nombre or len(nombre) > 150:
                        raise ValidationError('Indica un nombre de hasta 150 caracteres.')
                    validate_email(correo)
                    telefono = request.POST.get('telefono')
                    if telefono is not None:
                        telefono = telefono.strip()
                    if telefono and (len(telefono) > 32 or any(c not in '0123456789+ ()-' for c in telefono)
                                     or not any(c.isdigit() for c in telefono)):
                        raise ValidationError('Indica un teléfono válido o deja el campo vacío.')
                    with transaction.atomic():
                        if Usuarios.objects.filter(correo__iexact=correo).exclude(pk=actor.pk).exists():
                            raise ValidationError('Ya existe una cuenta con ese correo.')
                        actor.nombre, actor.correo = nombre, correo
                        campos = ['nombre', 'correo']
                        if telefono is not None:
                            actor.telefono = telefono
                            campos.append('telefono')
                        actor.save(update_fields=campos)
                        auditar(request, 'ACTUALIZAR_CUENTA', 'usuario', actor.id)
                    mensaje = 'Información actualizada.'
            else:
                raise ValidationError('Acción no disponible.')
        except ValidationError as exc:
            error = ' '.join(exc.messages)
        except IntegrityError:
            actor.refresh_from_db()
            error = 'No se pudo guardar la información. Comprueba el correo e inténtalo de nuevo.'
    return render(request, 'perfil.html', {
        'actor': actor, 'origen': origen, 'seccion': seccion,
        'mostrar_datos': mostrar_datos, 'error': error, 'mensaje': mensaje,
    })
