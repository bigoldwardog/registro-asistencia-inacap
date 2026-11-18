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
from .models import Usuarios, AccesoUsuario, RolAcceso
from .permissions import migrar_cuentas
from .views import auditar
from .organizacion import (elegir_perfil, guardar_ambitos, datos_perfil,
                           serializar_ambitos)
from .models import AreaAcademica, SedeAcademica


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
            sede, area = elegir_perfil(request.POST)
            password_valida(password)
            if password != request.POST.get('password2'):
                raise ValidationError('Las contraseñas no coinciden.')
            with transaction.atomic():
                if cuenta_configurada():
                    return redirect('login')
                usuario, _ = Usuarios.objects.update_or_create(correo=correo, defaults={
                    'nombre': nombre, 'rol': 'ADMINISTRADOR', 'activo': 1, 'password_hash': make_password(password)})
                migrar_cuentas()
                AccesoUsuario.objects.filter(superusuario=True).exclude(usuario=usuario).update(superusuario=False)
                AccesoUsuario.objects.filter(usuario=usuario).update(sede=sede, area=area, superusuario=True)
                request.session.flush()
                request.session['usuario_id'] = usuario.id
                request.actor = usuario
                auditar(request, 'CREAR_ADMINISTRADOR_INICIAL', 'usuario', usuario.id)
            return redirect('administrador')
        except ValidationError as exc:
            error = ' '.join(exc.messages)
    return render(request, 'cuenta.html', {'modo': 'inicial', 'titulo': 'Crear cuenta de superusuario', 'error': error, 'sedes': SedeAcademica.objects.order_by('nombre'), 'areas': AreaAcademica.objects.order_by('nombre')})


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
            return redirect('administrador')
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
    origen = 'administrador' if request.GET.get('panel') != 'anfitrion'  else 'anfitrion'
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
        'organizacion': datos_perfil(actor), 'mostrar_datos': mostrar_datos, 'error': error, 'mensaje': mensaje,
    })


@acceso(pagina=True, permiso='superusuario')
@never_cache
def roles_permisos(request):
    from .permissions import PERMISOS, ALCANCES, migrar_cuentas
    migrar_cuentas()
    error = mensaje = ''
    if request.method == 'POST':
        try:
            with transaction.atomic():
                accion = request.POST.get('accion')
                if accion == 'rol':
                    nombre = request.POST.get('nombre', '').strip()
                    if not nombre or len(nombre) > 80:
                        raise ValidationError('Indica un nombre de rol de hasta 80 caracteres.')
                    rol_id = request.POST.get('rol_id')
                    rol = RolAcceso.objects.select_for_update().get(pk=rol_id) if rol_id else RolAcceso()
                    if RolAcceso.objects.filter(nombre__iexact=nombre).exclude(pk=rol.pk).exists():
                        raise ValidationError('Ya existe un rol con ese nombre. Selecciónalo para modificarlo.')
                    rol.nombre = nombre
                    rol.superusuario = request.POST.get('superusuario') == 'on'
                    for clave, _ in PERMISOS:
                        alcance = request.POST.get(clave, 'NINGUNA')
                        if alcance not in ALCANCES:
                            raise ValidationError('Selecciona un alcance válido para cada permiso.')
                        setattr(rol, clave, alcance)
                    rol.save()
                    guardar_ambitos(rol, request.POST, PERMISOS)
                    auditar(request, 'GUARDAR_ROL', 'rol', rol.pk,
                            despues={'nombre': nombre, **{clave: getattr(rol, clave) for clave, _ in PERMISOS}})
                    mensaje = 'Rol guardado.'
                elif accion == 'usuario':
                    nombre = request.POST.get('nombre', '').strip()
                    correo = request.POST.get('correo', '').strip().lower()
                    password = request.POST.get('password', '')
                    if not nombre or len(nombre) > 150:
                        raise ValidationError('Indica un nombre de hasta 150 caracteres.')
                    validate_email(correo)
                    password_valida(password)
                    sede, area = elegir_perfil(request.POST)
                    if Usuarios.objects.filter(correo__iexact=correo).exists():
                        raise ValidationError('Ya existe una cuenta con ese correo.')
                    rol = RolAcceso.objects.get(pk=request.POST.get('rol'))
                    usuario = Usuarios.objects.create(nombre=nombre, correo=correo,
                        password_hash=make_password(password), rol='ANFITRION', activo=1)
                    AccesoUsuario.objects.create(usuario=usuario, rol=rol, sede=sede, area=area)
                    auditar(request, 'CREAR_USUARIO', 'usuario', usuario.pk,
                            despues={'nombre': nombre, 'correo': correo, 'rol': rol.nombre})
                    mensaje = 'Cuenta creada. El usuario puede actualizar sus datos y contraseña desde Mi cuenta.'
                elif accion == 'perfil':
                    acceso_usuario = AccesoUsuario.objects.select_for_update().get(usuario_id=request.POST.get('usuario'))
                    sede, area = elegir_perfil(request.POST)
                    acceso_usuario.sede, acceso_usuario.area = sede, area
                    acceso_usuario.save(update_fields=['sede', 'area'])
                    auditar(request, 'ASIGNAR_ORGANIZACION', 'usuario', acceso_usuario.usuario_id,
                            despues={'sede_id': sede.id, 'area_id': area.id})
                    mensaje = 'Sede y área guardadas.'
                elif accion == 'asignar':
                    acceso_usuario = AccesoUsuario.objects.select_for_update().get(usuario_id=request.POST.get('usuario'))
                    if acceso_usuario.superusuario:
                        raise ValidationError('El superusuario base conserva todos sus permisos.')
                    rol = RolAcceso.objects.get(pk=request.POST.get('rol'))
                    acceso_usuario.rol = rol
                    acceso_usuario.save(update_fields=['rol'])
                    auditar(request, 'ASIGNAR_ROL', 'usuario', acceso_usuario.usuario_id,
                            despues={'rol': rol.nombre})
                    mensaje = 'Rol asignado.'
                else:
                    raise ValidationError('Acción no disponible.')
        except ValidationError as exc:
            error = ' '.join(exc.messages)
        except (ValueError, TypeError, RolAcceso.DoesNotExist, AccesoUsuario.DoesNotExist):
            error = 'Selecciona un usuario y un rol válidos.'
        except IntegrityError:
            error = 'No se pudo guardar. Revisa el correo y el nombre del rol.'
        if not error:
            from django.contrib import messages
            messages.success(request, mensaje)
            if accion == 'rol':
                from django.urls import reverse
                return redirect(reverse('roles_permisos') + '?rol=' + str(rol.pk))
            from django.urls import reverse
            seccion = 'crear' if accion == 'usuario' else 'usuarios'
            return redirect(reverse('roles_permisos') + '?seccion=' + seccion)
    roles = list(RolAcceso.objects.order_by('nombre'))
    for rol in roles:
        rol.permisos_visibles = [{'clave': clave, 'etiqueta': etiqueta, 'activo': getattr(rol, clave)}
                                for clave, etiqueta in PERMISOS]
    return render(request, 'roles_permisos.html', {
        'seccion_roles': ({'usuario': 'crear', 'asignar': 'usuarios', 'perfil': 'usuarios'}.get(request.POST.get('accion'), 'configuracion') if request.method == 'POST' else request.GET.get('seccion', 'configuracion')),
        'actor': request.actor, 'roles': roles, 'permisos': PERMISOS, 'alcances': RolAcceso.ALCANCES,
        'roles_datos': [{**{clave: getattr(rol, clave) for clave in ('id', 'nombre', 'superusuario', *[p[0] for p in PERMISOS])},
                         'ambitos': serializar_ambitos(rol)} for rol in roles],
        'sedes': SedeAcademica.objects.order_by('nombre'), 'areas': AreaAcademica.objects.order_by('nombre'),
        'usuarios_datos': list(AccesoUsuario.objects.values('usuario_id', 'rol_id', 'superusuario', 'sede_id', 'area_id')),
        'cuentas': AccesoUsuario.objects.select_related('usuario', 'rol').order_by('usuario__nombre'),
        'error': error,
    })
