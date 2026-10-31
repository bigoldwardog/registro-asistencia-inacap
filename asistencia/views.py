import json
import uuid
from datetime import date, time
from functools import wraps

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, OperationalError, transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .access import acceso
from .catalogo_plantillas import campos_por_etapa
from .domain import (EPP, PANOL, ErrorFormulario, campos_asistente, fecha_chile,
                     json_guardado, normalizar_rut, validar_persona, validar_png)
from .models import (Asistencias, Asistentes, Auditoria, Firmas, FirmasAdicionales,
                     FirmasDevolucion, PlantillasSesion, Sesiones, Usuarios)


def errores(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        try:
            return view(*args, **kwargs)
        except ErrorFormulario as error:
            return JsonResponse({'error': error.mensaje}, status=error.status)
        except OperationalError as error:
            if 'locked' not in str(error).lower():
                raise
            response = JsonResponse({'error': 'La base está ocupada. Reintenta el mismo envío en unos segundos.'}, status=503)
            response['Retry-After'] = '2'
            return response
        except IntegrityError:
            return JsonResponse({'error': 'El registro ya existe o cambió durante el envío. Recarga su estado.'}, status=409)
    return wrapped


def cuerpo(request):
    try:
        data = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        raise ErrorFormulario('Se esperaba JSON válido.')
    if not isinstance(data, dict):
        raise ErrorFormulario('Se esperaba un objeto JSON.')
    return data


def obtener_sesion(request=None, sesion_id=None, token=None, lock=False):
    query = Sesiones.objects.select_related('plantilla', 'anfitrion')
    if lock:
        query = query.select_for_update()
    try:
        sesion = query.get(token_qr=token) if token else query.get(id=sesion_id)
    except (Sesiones.DoesNotExist, ValueError, TypeError):
        raise ErrorFormulario('La sesión no existe.', 404)
    if request and request.actor.rol != 'ADMINISTRADOR' and sesion.anfitrion_id != request.actor.id:
        raise ErrorFormulario('No tienes acceso a esta sesión.', 403)
    return sesion


def auditar(request, accion, entidad, entidad_id, antes=None, despues=None):
    Auditoria.objects.create(usuario=getattr(request, 'actor', None), accion=accion,
        entidad=entidad, entidad_id=entidad_id,
        datos_anteriores_json=json.dumps(antes or {}, ensure_ascii=False),
        datos_nuevos_json=json.dumps(despues or {}, ensure_ascii=False))


def definicion_sesion(sesion):
    return campos_por_etapa([c for c in json_guardado(sesion.campos_definicion_json, list)
        if isinstance(c, dict) and all(isinstance(c.get(k), str) for k in ('nombre', 'etiqueta', 'tipo'))])


def datos_sesion(sesion):
    return dict(id=sesion.id, nombre=sesion.nombre, estado=sesion.estado,
        fecha_inicio=fecha_chile(sesion.fecha_inicio), fecha_cierre=fecha_chile(sesion.fecha_cierre),
        fecha_local=fecha_chile(sesion.fecha_inicio, True), token_qr=sesion.token_qr,
        plantilla=sesion.plantilla.nombre, anfitrion=sesion.anfitrion.nombre,
        campos_definicion=definicion_sesion(sesion), campos=json_guardado(sesion.campos_valores_json, dict))


def datos_asistencia(asistencia):
    return dict(id=asistencia.id, nombre=asistencia.nombre_registrado,
        cargo=asistencia.cargo_registrado, rut=asistencia.rut_registrado,
        telefono=asistencia.telefono_registrado, correo=asistencia.correo_registrado,
        campos=json_guardado(asistencia.campos_participante_json, dict), estado=asistencia.estado,
        fecha_registro=fecha_chile(asistencia.fecha_registro), fecha_firma=fecha_chile(asistencia.fecha_firma))


@acceso(admin=True)
@require_GET
@errores
def historial_sesiones(request):
    q = request.GET.get('q', '').strip().casefold()
    results = []
    sesiones = Sesiones.objects.select_related('plantilla', 'anfitrion').prefetch_related('asistencias_set').order_by('-id')
    for sesion in sesiones:
        attendees = list(sesion.asistencias_set.all())
        if q and q not in sesion.nombre.casefold() and not any(q in ' '.join([a.nombre_registrado, a.rut_registrado, a.cargo_registrado]).casefold() or q.replace('.', '').replace('-', '') in a.rut_registrado.replace('.', '').replace('-', '').casefold() for a in attendees):
            continue
        row = datos_sesion(sesion)
        row.update(total_asistencias=len(attendees), total_firmadas=sum(a.estado == 'FIRMADO' for a in attendees),
            total_pendientes=sum(a.estado == 'PENDIENTE_FIRMA' for a in attendees))
        results.append(row)
    return JsonResponse({'sesiones': results})


@acceso()
@require_GET
def listar_sesiones(request):
    query = Sesiones.objects.select_related('plantilla', 'anfitrion').order_by('-id')
    if request.actor.rol != 'ADMINISTRADOR':
        query = query.filter(anfitrion=request.actor)
    return JsonResponse({'sesiones': [datos_sesion(s) for s in query]})


@acceso()
@require_GET
@errores
def listar_asistencias(request, sesion_id):
    sesion = obtener_sesion(request, sesion_id)
    devoluciones = {f.asistencia_id: fecha_chile(f.fecha_creacion) for f in FirmasDevolucion.objects.filter(asistencia__sesion=sesion).defer('imagen')}
    docentes = {f.asistencia_id: fecha_chile(f.fecha_creacion) for f in FirmasAdicionales.objects.filter(asistencia__sesion=sesion, tipo='DOCENTE').defer('imagen')}
    firmas = set(Firmas.objects.filter(asistencia__sesion=sesion).values_list('asistencia_id', flat=True))
    rows = []
    for a in Asistencias.objects.filter(sesion=sesion).order_by('fecha_registro', 'id'):
        row = datos_asistencia(a)
        row.update(devolucion_firmada=a.id in devoluciones, fecha_firma_devolucion=devoluciones.get(a.id),
            docente_firmado=a.id in docentes, fecha_firma_docente=docentes.get(a.id), tiene_firma=a.id in firmas)
        rows.append(row)
    data = datos_sesion(sesion)
    data.update(es_epp=sesion.plantilla.nombre == EPP, es_panol=sesion.plantilla.nombre == PANOL,
        campos_asistente=campos_asistente(sesion))
    return JsonResponse({'sesion': data, 'asistencias': rows})


@require_GET
@errores
def consultar_sesion(request, token):
    s = obtener_sesion(token=token)
    return JsonResponse(dict(id=s.id, nombre=s.nombre, estado=s.estado,
        fecha_inicio=fecha_chile(s.fecha_inicio), fecha_cierre=fecha_chile(s.fecha_cierre), campos_asistente=campos_asistente(s)))


@require_GET
@errores
def consultar_asistencia_existente(request, token):
    sesion = obtener_sesion(token=token)
    envio = request.GET.get('registro_token', '')
    if not envio:
        raise ErrorFormulario('Se necesita el identificador del registro.')
    a = Asistencias.objects.filter(sesion=sesion, registro_token=envio).first()
    return JsonResponse({'registrada': a is not None, 'estado': a.estado if a else None})


@require_POST
@errores
def registrar_asistencia(request, token):
    data = cuerpo(request)
    try:
        envio = str(uuid.UUID(data.get('registro_token', '')))
    except (ValueError, TypeError, AttributeError):
        raise ErrorFormulario('Recarga el formulario para generar un identificador de envío válido.')
    with transaction.atomic():
        sesion = obtener_sesion(token=token, lock=True)
        valores = validar_persona(data, sesion)
        previa = Asistencias.objects.filter(registro_token=envio).first()
        if previa:
            if previa.sesion_id != sesion.id or json_guardado(previa.campos_participante_json, dict) != valores:
                raise ErrorFormulario('Ese envío corresponde a otros datos. Usa Registrar a otra persona.', 409)
            return JsonResponse({'asistencia_id': previa.id, 'estado': previa.estado, 'registro_token': envio})
        if sesion.estado != 'ABIERTA':
            raise ErrorFormulario('La sesión está cerrada.', 409)
        rut = valores.get('rut', '')
        asistente = None
        if rut:
            for existente in Asistencias.objects.filter(sesion=sesion).exclude(rut_registrado=''):
                try:
                    duplicado = normalizar_rut(existente.rut_registrado) == rut
                except ErrorFormulario:
                    duplicado = False
                if duplicado:
                    raise ErrorFormulario('Este RUT ya está registrado en esta sesión.', 409)
            candidatos = []
            for persona in Asistentes.objects.exclude(rut__isnull=True):
                try:
                    if normalizar_rut(persona.rut) == rut:
                        candidatos.append(persona)
                except ErrorFormulario:
                    continue
            candidatos.sort(key=lambda p: (p.rut == rut, p.id), reverse=True)
            asistente = candidatos[0] if candidatos else None
        if not asistente:
            asistente = Asistentes(rut=rut or None)
        asistente.rut = rut or None
        asistente.nombre = valores['nombre']
        asistente.correo, asistente.telefono = valores.get('correo', ''), valores.get('telefono', '')
        asistente.fecha_actualizacion = timezone.now().isoformat()
        asistente.save()
        a = Asistencias.objects.create(sesion=sesion, asistente=asistente,
            nombre_registrado=valores['nombre'], rut_registrado=rut, cargo_registrado=valores.get('cargo', ''),
            correo_registrado=valores.get('correo', ''), telefono_registrado=valores.get('telefono', ''),
            campos_participante_json=json.dumps(valores, ensure_ascii=False), registro_token=envio, estado='PENDIENTE_FIRMA')
        auditar(request, 'REGISTRAR_ASISTENCIA', 'asistencia', a.id, despues={'sesion_id': sesion.id})
    return JsonResponse({'asistencia_id': a.id, 'estado': a.estado, 'registro_token': envio}, status=201)


@require_GET
def pagina_inicio(request):
    sesion = Sesiones.objects.select_related('plantilla').filter(token_qr=request.GET.get('token', '')).first()
    return render(request, 'index.html', {'campos_asistente': campos_asistente(sesion)})


@acceso(pagina=True)
def pagina_anfitrion(request):
    return render(request, 'anfitrion.html', {'actor': request.actor})


@acceso(admin=True, pagina=True)
def pagina_administrador(request):
    return render(request, 'administrador.html', {'actor': request.actor})


def obtener_asistencia(request, asistencia_id):
    try:
        a = Asistencias.objects.get(id=asistencia_id)
    except Asistencias.DoesNotExist:
        raise ErrorFormulario('La asistencia no existe.', 404)
    sesion = obtener_sesion(request, a.sesion_id, lock=True)
    if sesion.estado != 'ABIERTA':
        raise ErrorFormulario('La sesión está cerrada. No se pueden guardar firmas.', 409)
    return Asistencias.objects.select_for_update().get(id=a.id), sesion


@acceso()
@require_POST
@errores
def guardar_firma(request, asistencia_id):
    imagen = validar_png(cuerpo(request).get('firma'))
    with transaction.atomic():
        a, sesion = obtener_asistencia(request, asistencia_id)
        if a.estado != 'PENDIENTE_FIRMA':
            raise ErrorFormulario('Esta asistencia ya no está pendiente de firma.', 409)
        Firmas.objects.create(asistencia=a, imagen=imagen, formato='image/png')
        a.estado, a.fecha_firma = 'FIRMADO', timezone.now().isoformat()
        a.save(update_fields=['estado', 'fecha_firma'])
        auditar(request, 'FIRMAR_RECEPCION' if sesion.plantilla.nombre == EPP else 'FIRMAR_ASISTENCIA', 'asistencia', a.id, despues={'sesion_id': sesion.id})
    return JsonResponse({'mensaje': 'Firma guardada.', 'asistencia_id': a.id, 'estado': a.estado})


def firma_extra(request, asistencia_id, docente=False):
    imagen = validar_png(cuerpo(request).get('firma'))
    with transaction.atomic():
        a, sesion = obtener_asistencia(request, asistencia_id)
        if sesion.plantilla.nombre != (PANOL if docente else EPP):
            raise ErrorFormulario('Esta firma no corresponde a la plantilla de la sesión.')
        if a.estado != 'FIRMADO' or not Firmas.objects.filter(asistencia=a).exists():
            raise ErrorFormulario('Primero debe firmar el participante.', 409)
        model = FirmasAdicionales if docente else FirmasDevolucion
        args = {'asistencia': a, **({'tipo': 'DOCENTE'} if docente else {})}
        if model.objects.filter(**args).exists():
            raise ErrorFormulario('Esta firma ya está guardada.', 409)
        f = model.objects.create(**args, imagen=imagen)
        auditar(request, 'FIRMAR_DOCENTE' if docente else 'FIRMAR_DEVOLUCION', 'asistencia', a.id, despues={'sesion_id': sesion.id, 'fecha': f.fecha_creacion})
    return JsonResponse({'mensaje': 'Firma guardada correctamente.', 'fecha_firma_devolucion': fecha_chile(f.fecha_creacion)}, status=201)


@acceso()
@require_POST
@errores
def guardar_firma_devolucion(request, asistencia_id):
    return firma_extra(request, asistencia_id)


@acceso()
@require_POST
@errores
def guardar_firma_docente(request, asistencia_id):
    return firma_extra(request, asistencia_id, True)


@acceso()
@require_POST
@errores
def cerrar_sesion(request, sesion_id):
    with transaction.atomic():
        s = obtener_sesion(request, sesion_id, lock=True)
        if s.estado != 'CERRADA':
            s.estado, s.fecha_cierre = 'CERRADA', timezone.now().isoformat()
            s.save(update_fields=['estado', 'fecha_cierre'])
            auditar(request, 'CERRAR_SESION', 'sesion', s.id, despues={'fecha_cierre': s.fecha_cierre})
    return JsonResponse({'mensaje': 'Sesión cerrada.', 'sesion_id': s.id, 'estado': s.estado, 'fecha_cierre': fecha_chile(s.fecha_cierre)})


@acceso()
@require_GET
def opciones_sesion(request):
    query = Usuarios.objects.filter(activo=1)
    query = query.filter(rol='ANFITRION') if request.actor.rol == 'ADMINISTRADOR' else query.filter(id=request.actor.id)
    anfitriones = list(query.values('id', 'nombre'))
    if request.actor.rol == 'ADMINISTRADOR':
        anfitriones.append({'id': request.actor.id, 'nombre': request.actor.nombre + ' (yo)'})
    return JsonResponse({'plantillas': [{'id': p.id, 'nombre': p.nombre, 'descripcion': p.descripcion,
        'campos': campos_por_etapa(list(p.camposplantilla_set.order_by('orden', 'id').values('nombre', 'etiqueta', 'tipo', 'obligatorio')))}
        for p in PlantillasSesion.objects.filter(activa=1).prefetch_related('camposplantilla_set').order_by('nombre')], 'anfitriones': anfitriones})


def validar_campos(campos, valores, apertura=False):
    if not isinstance(valores, dict):
        raise ErrorFormulario('Los campos deben ser un objeto.')
    resultado = {}
    for c in campos:
        valor = valores.get(c['nombre'], '') if not apertura or c['etapa'] == 'apertura' else ''
        if not isinstance(valor, str) or len(valor) > 10000:
            raise ErrorFormulario(f"Valor inválido en {c['etiqueta']}.")
        valor = valor.strip()
        if c.get('obligatorio') and (not apertura or c['etapa'] == 'apertura') and not valor:
            raise ErrorFormulario(f"Completa {c['etiqueta']}.")
        if valor:
            try:
                if c['tipo'] == 'fecha': date.fromisoformat(valor)
                elif c['tipo'] == 'hora': time.fromisoformat(valor)
                elif c['tipo'] == 'email': validate_email(valor)
                elif c['tipo'] == 'numero': float(valor)
            except (ValueError, ValidationError):
                raise ErrorFormulario(f"Formato inválido en {c['etiqueta']}.")
        resultado[c['nombre']] = valor
    if resultado.get('fecha_inicio_proyecto') and resultado.get('fecha_termino_proyecto') and resultado['fecha_inicio_proyecto'] > resultado['fecha_termino_proyecto']:
        raise ErrorFormulario('El término del proyecto no puede ser anterior al inicio.')
    return resultado


@acceso()
@require_POST
@errores
def crear_sesion(request):
    data = cuerpo(request)
    nombre = data.get('nombre', '')
    if not isinstance(nombre, str) or not nombre.strip() or len(nombre) > 200:
        raise ErrorFormulario('Indica un nombre de hasta 200 caracteres.')
    try:
        if isinstance(data.get('plantilla_id'), bool) or isinstance(data.get('anfitrion_id'), bool):
            raise ValueError()
        plantilla = PlantillasSesion.objects.get(id=int(str(data.get('plantilla_id'))), activa=1)
        anfitrion = Usuarios.objects.get(id=int(str(data.get('anfitrion_id'))), activo=1)
    except (ValueError, TypeError, PlantillasSesion.DoesNotExist, Usuarios.DoesNotExist):
        raise ErrorFormulario('Selecciona una plantilla y un anfitrión activos.')
    if request.actor.rol != 'ADMINISTRADOR' and anfitrion.id != request.actor.id:
        raise ErrorFormulario('Solo puedes crear sesiones a tu cargo.', 403)
    campos = campos_por_etapa(list(plantilla.camposplantilla_set.order_by('orden', 'id').values('nombre', 'etiqueta', 'tipo', 'obligatorio', 'orden')))
    valores = validar_campos(campos, data.get('campos', {}), True)
    with transaction.atomic():
        s = Sesiones.objects.create(plantilla=plantilla, anfitrion=anfitrion, nombre=nombre.strip(), estado='ABIERTA',
            fecha_inicio=timezone.now().isoformat(), token_qr=uuid.uuid4().hex,
            campos_definicion_json=json.dumps(campos, ensure_ascii=False), campos_valores_json=json.dumps(valores, ensure_ascii=False))
        auditar(request, 'CREAR_SESION', 'sesion', s.id, despues=datos_sesion(s))
    return JsonResponse({'id': s.id, 'nombre': s.nombre, 'estado': s.estado}, status=201)


@acceso()
@require_POST
@errores
def guardar_desarrollo(request, sesion_id):
    data = cuerpo(request)
    cambios, base = data.get('campos'), data.get('base')
    if not isinstance(cambios, dict) or not isinstance(base, dict):
        raise ErrorFormulario('Falta la versión original de las observaciones. Recarga antes de editar.')
    with transaction.atomic():
        s = obtener_sesion(request, sesion_id, lock=True)
        campos = [c for c in definicion_sesion(s) if c['etapa'] == 'desarrollo']
        if set(cambios) - {c['nombre'] for c in campos}:
            raise ErrorFormulario('Solo puedes editar campos de desarrollo y cierre.')
        try:
            anteriores = json.loads(s.campos_valores_json) if s.campos_valores_json and s.campos_valores_json.strip() else {}
        except (ValueError, TypeError):
            raise ErrorFormulario('Esta sesión contiene datos antiguos ilegibles. No se sobrescribieron; solicita revisión antes de editar.', 409)
        if not isinstance(anteriores, dict):
            raise ErrorFormulario('Los datos antiguos requieren revisión antes de editarlos. No se sobrescribieron.', 409)
        if any(base.get(k, '') != anteriores.get(k, '') for k in cambios):
            raise ErrorFormulario('Otra persona actualizó estas observaciones. Conserva tu borrador y recarga la sesión antes de guardar.', 409)
        nuevos = validar_campos([c for c in campos if c['nombre'] in cambios], cambios)
        if nuevos.get('fecha_de_devolucion') and nuevos['fecha_de_devolucion'] < fecha_chile(s.fecha_inicio, True):
            raise ErrorFormulario('La devolución no puede ser anterior al inicio de la actividad.')
        valores = {**anteriores, **nuevos}
        s.campos_valores_json = json.dumps(valores, ensure_ascii=False)
        s.save(update_fields=['campos_valores_json'])
        auditar(request, 'GUARDAR_DESARROLLO', 'sesion', s.id, antes=anteriores, despues=valores)
    return JsonResponse({'mensaje': 'Desarrollo y observaciones guardados.', 'campos': valores})


@acceso()
@require_GET
@errores
def historial_cambios(request, sesion_id):
    s = obtener_sesion(request, sesion_id)
    nombres = dict(s.asistencias_set.values_list('id', 'nombre_registrado'))
    asistencias = list(nombres)
    from django.db.models import Q
    rows = Auditoria.objects.filter(Q(entidad='sesion', entidad_id=s.id) | Q(entidad='asistencia', entidad_id__in=asistencias)).select_related('usuario').order_by('-id')
    return JsonResponse({'historial': [dict(accion=r.accion, fecha=fecha_chile(r.fecha),
        usuario=r.usuario.nombre if r.usuario else 'Asistente: ' + nombres.get(r.entidad_id, ''), anteriores=json_guardado(r.datos_anteriores_json, dict),
        nuevos=json_guardado(r.datos_nuevos_json, dict)) for r in rows]})


@acceso()
@require_GET
@errores
def imagen_firma(request, asistencia_id, tipo):
    try:
        a = Asistencias.objects.get(id=asistencia_id)
    except Asistencias.DoesNotExist:
        raise ErrorFormulario('La asistencia no existe.', 404)
    obtener_sesion(request, a.sesion_id)
    if tipo == 'recepcion': f = Firmas.objects.filter(asistencia=a).first()
    elif tipo == 'devolucion': f = FirmasDevolucion.objects.filter(asistencia=a).first()
    elif tipo == 'docente': f = FirmasAdicionales.objects.filter(asistencia=a, tipo='DOCENTE').first()
    else: f = None
    if not f:
        raise ErrorFormulario('La firma no existe.', 404)
    response = HttpResponse(bytes(f.imagen), content_type='image/png')
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@acceso()
@require_GET
@errores
def codigo_qr(request, sesion_id):
    import io
    import qrcode
    s = obtener_sesion(request, sesion_id)
    url = request.build_absolute_uri('/?token=' + s.token_qr)
    buffer = io.BytesIO()
    qrcode.make(url).save(buffer, format='PNG')
    return HttpResponse(buffer.getvalue(), content_type='image/png')
