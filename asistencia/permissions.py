from django.contrib.auth.hashers import identify_hasher
from django.db import transaction
from .models import AccesoUsuario, RolAcceso, Usuarios

PERMISOS = (
    ('consultar', 'Consultar sesiones'),
    ('crear', 'Crear sesiones'),
    ('observaciones', 'Modificar observaciones'),
    ('cerrar', 'Cerrar sesiones'),
    ('exportar', 'Exportar sesiones'),
)
ALCANCES = ('NINGUNA', 'PROPIAS', 'TODAS')


def primer_administrador():
    for usuario in Usuarios.objects.filter(rol='ADMINISTRADOR', activo=1).order_by('id'):
        try:
            identify_hasher(usuario.password_hash)
            return usuario
        except ValueError:
            continue
    return None


def permisos_usuario(usuario):
    if hasattr(usuario, '_permisos'):
        return usuario._permisos
    acceso = AccesoUsuario.objects.select_related('rol').filter(usuario_id=usuario.id).first()
    if acceso:
        superusuario = acceso.superusuario
        permisos = {clave: 'TODAS' if superusuario else getattr(acceso.rol, clave) for clave, _ in PERMISOS}
    else:
        primero = primer_administrador()
        superusuario = bool(primero and primero.id == usuario.id)
        general = usuario.rol == 'ADMINISTRADOR'
        permisos = {clave: 'TODAS' if general else 'PROPIAS' for clave, _ in PERMISOS}
        if general and not superusuario:
            permisos.update(crear='PROPIAS', observaciones='PROPIAS', cerrar='PROPIAS')
    permisos['superusuario'] = superusuario
    usuario._permisos = permisos
    return permisos


def tiene_permiso(usuario, accion, sesion=None):
    permisos = permisos_usuario(usuario)
    if accion == 'superusuario':
        return permisos['superusuario']
    if accion == 'panel_anfitrion':
        return any(permisos[clave] != 'NINGUNA' for clave in ('crear', 'observaciones', 'cerrar'))
    alcance = permisos.get(accion, 'NINGUNA')
    return alcance == 'TODAS' or (alcance == 'PROPIAS' and
                                 (sesion is None or sesion.anfitrion_id == usuario.id))


def sesiones_visibles(usuario, query):
    alcance = permisos_usuario(usuario)['consultar']
    if alcance == 'NINGUNA':
        return query.none()
    return query if alcance == 'TODAS' else query.filter(anfitrion_id=usuario.id)


@transaction.atomic
def migrar_cuentas():
    docente, _ = RolAcceso.objects.get_or_create(
        nombre='Docente', defaults={clave: 'PROPIAS' for clave, _ in PERMISOS})
    RolAcceso.objects.get_or_create(nombre='Consulta propia')
    general, _ = RolAcceso.objects.get_or_create(
        nombre='Administración existente', defaults={
            'consultar': 'TODAS', 'crear': 'PROPIAS', 'observaciones': 'PROPIAS',
            'cerrar': 'PROPIAS', 'exportar': 'TODAS'})
    primero = primer_administrador()
    existe_superusuario = AccesoUsuario.objects.filter(superusuario=True).exists()
    for usuario in Usuarios.objects.all():
        AccesoUsuario.objects.get_or_create(usuario=usuario, defaults={
            'rol': general if usuario.rol == 'ADMINISTRADOR' else docente,
            'superusuario': bool(not existe_superusuario and primero and usuario.id == primero.id),
        })
