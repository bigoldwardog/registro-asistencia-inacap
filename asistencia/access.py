from functools import wraps

from django.contrib.auth.hashers import identify_hasher
from django.http import JsonResponse
from django.shortcuts import redirect

from .models import Usuarios


def usuario_actual(request):
    uid = request.session.get('usuario_id')
    return Usuarios.objects.filter(id=uid, activo=1).first() if uid else None


def cuenta_configurada():
    for usuario in Usuarios.objects.filter(activo=1):
        try:
            identify_hasher(usuario.password_hash)
            return True
        except ValueError:
            continue
    return False


def acceso(admin=False, pagina=False, permiso=None):
    def decorador(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            usuario = usuario_actual(request)
            if not usuario:
                if pagina:
                    return redirect('login' if cuenta_configurada() else 'configuracion_inicial')
                return JsonResponse({'error': 'Inicia sesión para continuar.'}, status=401)
            from .permissions import tiene_permiso
            if (admin and not tiene_permiso(usuario, 'consultar')) or (permiso and not tiene_permiso(usuario, permiso)):
                if pagina:
                    return redirect('administrador')
                return JsonResponse({'error': 'No tienes permiso para realizar esta acción.'}, status=403)
            request.actor = usuario
            return view(request, *args, **kwargs)
        return wrapped
    return decorador
