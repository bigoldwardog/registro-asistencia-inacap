import json
from pathlib import Path
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from .models import AccesoUsuario, AmbitoPermiso, AreaAcademica, ContextoSesion, SedeAcademica

MODOS = ('PERFIL', 'SELECCION', 'TODAS')


@transaction.atomic
def cargar_catalogo():
    datos = json.loads((Path(settings.BASE_DIR) / 'database/catalogo_organizacion.json').read_text(encoding='utf-8'))
    for clave, modelo, campo in (('sedes', SedeAcademica, 'sede'), ('areas', AreaAcademica, 'area')):
        for nombre in datos[clave]:
            existentes = list(modelo.objects.filter(nombre__iexact=nombre).order_by('id'))
            principal = existentes[0] if existentes else modelo.objects.create(nombre=nombre)
            for duplicado in existentes[1:]:
                AccesoUsuario.objects.filter(**{campo: duplicado}).update(**{campo: principal})
                ContextoSesion.objects.filter(**{campo: duplicado}).update(**{campo: principal})
                for regla in AmbitoPermiso.objects.filter(**{clave: duplicado}):
                    getattr(regla, clave).add(principal)
                duplicado.delete()
            if principal.nombre != nombre:
                principal.nombre = nombre
                principal.save(update_fields=['nombre'])


def perfil_usuario(usuario):
    return AccesoUsuario.objects.select_related('sede', 'area').filter(usuario_id=usuario.id).first()


def datos_perfil(usuario):
    perfil = perfil_usuario(usuario)
    return {'sede_id': perfil.sede_id if perfil else None, 'area_id': perfil.area_id if perfil else None,
            'sede': perfil.sede.nombre if perfil and perfil.sede_id else 'Sin sede asignada',
            'area': perfil.area.nombre if perfil and perfil.area_id else 'Sin área asignada'}


def elegir_perfil(datos):
    try:
        return SedeAcademica.objects.get(pk=datos.get('sede')), AreaAcademica.objects.get(pk=datos.get('area'))
    except (ValueError, TypeError, SedeAcademica.DoesNotExist, AreaAcademica.DoesNotExist):
        raise ValidationError('Selecciona una sede y un área académica válidas.')


def filtro_organizacion(usuario, accion):
    perfil = perfil_usuario(usuario)
    if perfil and (perfil.superusuario or perfil.rol.superusuario):
        return Q()
    regla = AmbitoPermiso.objects.filter(rol_id=perfil.rol_id, accion=accion).first() if perfil else None
    if regla is None:
        return (Q(contexto__sede_id=perfil.sede_id, contexto__area_id=perfil.area_id)
                if perfil and perfil.sede_id and perfil.area_id else Q(pk__in=[]))
    filtro = Q()
    for dimension in ('sedes', 'areas'):
        singular = 'sede' if dimension == 'sedes' else 'area'
        modo = getattr(regla, 'modo_' + dimension)
        campo = 'contexto__' + singular + '_id'
        if modo == 'PERFIL':
            identificador = getattr(perfil, singular + '_id')
            filtro &= Q(**{campo: identificador}) if identificador else Q(pk__in=[])
        elif modo == 'SELECCION':
            filtro &= Q(**{campo + '__in': getattr(regla, dimension).values('id')})
    return filtro


def permite_contexto(usuario, accion, sede_id, area_id):
    perfil = perfil_usuario(usuario)
    if perfil and (perfil.superusuario or perfil.rol.superusuario):
        return True
    regla = AmbitoPermiso.objects.filter(rol_id=perfil.rol_id, accion=accion).first() if perfil else None
    if regla is None:
        return bool(perfil and sede_id and area_id and
                    perfil.sede_id == sede_id and perfil.area_id == area_id)
    for dimension, singular, valor in (('sedes', 'sede', sede_id), ('areas', 'area', area_id)):
        modo = getattr(regla, 'modo_' + dimension)
        if modo == 'PERFIL' and (not valor or valor != getattr(perfil, singular + '_id')):
            return False
        if modo == 'SELECCION' and not getattr(regla, dimension).filter(pk=valor).exists():
            return False
    return True


def guardar_ambitos(rol, datos, acciones):
    for accion, _ in acciones:
        modos = {dimension: datos.get(accion + '_' + dimension + '_modo', 'PERFIL')
                 for dimension in ('sedes', 'areas')}
        if any(modo not in MODOS for modo in modos.values()):
            raise ValidationError('Selecciona un ámbito válido para cada acción.')
        regla, _ = AmbitoPermiso.objects.get_or_create(rol=rol, accion=accion)
        for dimension, modelo in (('sedes', SedeAcademica), ('areas', AreaAcademica)):
            valores = datos.getlist(accion + '_' + dimension)
            try:
                ids = {int(valor) for valor in valores}
            except (ValueError, TypeError):
                raise ValidationError('Selecciona sedes y áreas del catálogo.')
            opciones = modelo.objects.filter(pk__in=ids)
            if opciones.count() != len(ids):
                raise ValidationError('Hay sedes o áreas que ya no existen.')
            if modos[dimension] == 'SELECCION' and not ids:
                raise ValidationError('Selecciona al menos una sede o área para el ámbito seleccionado.')
            setattr(regla, 'modo_' + dimension, modos[dimension])
            getattr(regla, dimension).set(opciones if modos[dimension] == 'SELECCION' else [])
        regla.save()


def serializar_ambitos(rol):
    return {regla.accion: {'sedes_modo': regla.modo_sedes, 'areas_modo': regla.modo_areas,
                          'sedes': list(regla.sedes.values_list('id', flat=True)),
                          'areas': list(regla.areas.values_list('id', flat=True))}
            for regla in rol.ambitos.prefetch_related('sedes', 'areas')}

