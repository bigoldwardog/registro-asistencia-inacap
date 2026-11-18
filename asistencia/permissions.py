from django.contrib.auth.hashers import identify_hasher
from django.db import transaction
from django.db.models import Q
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
        superusuario = acceso.superusuario or acceso.rol.superusuario
        permisos = {clave: 'TODAS' if superusuario else getattr(acceso.rol, clave) for clave, _ in PERMISOS}
    else:
        # Un perfil incompleto no hereda los permisos del paradigma anterior.
        superusuario = False
        permisos = {clave: 'NINGUNA' for clave, _ in PERMISOS}
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
    programacion = getattr(sesion, 'programacion', None) if sesion else None
    propia = sesion is None or sesion.anfitrion_id == usuario.id or bool(programacion and programacion.creador_id == usuario.id)
    permitido = alcance == 'TODAS' or (alcance == 'PROPIAS' and propia)
    if not permitido or sesion is None or permisos['superusuario']:
        return permitido
    from .organizacion import permite_contexto
    contexto = getattr(sesion, 'contexto', None)
    return permite_contexto(usuario, accion, contexto.sede_id if contexto else None,
                            contexto.area_id if contexto else None)


def sesiones_visibles(usuario, query):
    alcance = permisos_usuario(usuario)['consultar']
    if alcance == 'NINGUNA':
        return query.none()
    from .organizacion import filtro_organizacion
    query = query.filter(filtro_organizacion(usuario, 'consultar'))
    return query if alcance == 'TODAS' else query.filter(Q(anfitrion_id=usuario.id) | Q(programacion__creador_id=usuario.id))


@transaction.atomic
def migrar_cuentas():
    RolAcceso.objects.get_or_create(nombre='Superusuario', defaults={'superusuario': True})
    docente, _ = RolAcceso.objects.get_or_create(
        nombre='Docente', defaults={clave: 'PROPIAS' for clave, _ in PERMISOS})
    RolAcceso.objects.get_or_create(nombre='Consulta propia')
    general, _ = RolAcceso.objects.get_or_create(
        nombre='Administración existente', defaults={
            'consultar': 'TODAS', 'crear': 'PROPIAS', 'observaciones': 'PROPIAS',
            'cerrar': 'PROPIAS', 'exportar': 'TODAS'})
    from .models import AmbitoPermiso
    for rol in RolAcceso.objects.all():
        for accion, _ in PERMISOS:
            AmbitoPermiso.objects.get_or_create(rol=rol, accion=accion, defaults={
                'modo_sedes': 'PERFIL', 'modo_areas': 'PERFIL'})
    primero = primer_administrador()
    existe_superusuario = AccesoUsuario.objects.filter(superusuario=True).exists()
    for usuario in Usuarios.objects.all():
        AccesoUsuario.objects.get_or_create(usuario=usuario, defaults={
            'rol': general if usuario.rol == 'ADMINISTRADOR' else docente,
            'superusuario': bool(not existe_superusuario and primero and usuario.id == primero.id),
        })
