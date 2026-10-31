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


def acceso(admin=False, pagina=False):
    def decorador(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            usuario = usuario_actual(request)
            if not usuario:
                if pagina:
                    return redirect('login' if cuenta_configurada() else 'configuracion_inicial')
                return JsonResponse({'error': 'Inicia sesión para continuar.'}, status=401)
            if admin and usuario.rol != 'ADMINISTRADOR':
                if pagina:
                    return redirect('anfitrion')
                return JsonResponse({'error': 'Se requiere acceso de administrador.'}, status=403)
            request.actor = usuario
            return view(request, *args, **kwargs)
        return wrapped
    return decorador
