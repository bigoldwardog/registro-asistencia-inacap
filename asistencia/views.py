import json
import uuid
from datetime import date, time
from functools import wraps

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, OperationalError, transaction
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST, require_http_methods

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


def obtener_sesion(request=None, sesion_id=None, token=None, lock=False, accion='consultar'):
    query = Sesiones.objects.select_related('plantilla', 'anfitrion')
    if lock:
        query = query.select_for_update(of=('self',))
    try:
        sesion = query.get(token_qr=token) if token else query.get(id=sesion_id)
    except (Sesiones.DoesNotExist, ValueError, TypeError):
        raise ErrorFormulario('La sesión no existe.', 404)
    if request and not tiene_permiso(request.actor, accion, sesion):
        raise ErrorFormulario('No tienes permiso para realizar esta acción en la sesión.', 403)
    return sesion


def auditar(request, accion, entidad, entidad_id, antes=None, despues=None):
    Auditoria.objects.create(usuario=getattr(request, 'actor', None), accion=accion,
        entidad=entidad, entidad_id=entidad_id,
        datos_anteriores_json=json.dumps(antes or {}, ensure_ascii=False),
        datos_nuevos_json=json.dumps(despues or {}, ensure_ascii=False))


def definicion_sesion(sesion):
    return campos_por_etapa([c for c in json_guardado(sesion.campos_definicion_json, list)
        if isinstance(c, dict) and all(isinstance(c.get(k), str) for k in ('nombre', 'etiqueta', 'tipo'))])


from .permissions import tiene_permiso, sesiones_visibles, permisos_usuario


def datos_sesion(sesion):
    programacion = getattr(sesion, 'programacion', None)
    contexto = getattr(sesion, 'contexto', None)
    programacion = getattr(sesion, 'programacion', None)
    return dict(sede=contexto.sede.nombre if contexto else 'Sin clasificar',
        area=contexto.area.nombre if contexto else 'Sin clasificar', id=sesion.id, nombre=sesion.nombre, estado=sesion.estado,
        fecha_inicio=fecha_chile(sesion.fecha_inicio), fecha_cierre=fecha_chile(sesion.fecha_cierre),
        fecha_programada=fecha_chile(programacion.fecha_programada) if programacion else '',
        creador=programacion.creador.nombre if programacion else 'No registrado en la versión anterior',
        anfitrion_previsto=programacion.anfitrion_previsto.nombre if programacion and programacion.anfitrion_previsto else '',
        firma_anfitrion_registrada=bool(programacion and programacion.fecha_firma),
        url_publica=settings.PUBLIC_SITE_URL + '/?token=' + sesion.token_qr if settings.PUBLIC_SITE_URL else '',
        fecha_local=fecha_chile(sesion.fecha_inicio or (programacion.fecha_programada if programacion else None), True), token_qr=sesion.token_qr,
        plantilla=sesion.plantilla.nombre, anfitrion=sesion.anfitrion.nombre if sesion.anfitrion else 'Por confirmar al iniciar',
        campos_definicion=definicion_sesion(sesion), campos=json_guardado(sesion.campos_valores_json, dict))


def datos_asistencia(asistencia):
    return dict(id=asistencia.id, nombre=asistencia.nombre_registrado,
        cargo=asistencia.cargo_registrado, rut=asistencia.rut_registrado,
        telefono=asistencia.telefono_registrado, correo=asistencia.correo_registrado,
        campos=json_guardado(asistencia.campos_participante_json, dict), estado=asistencia.estado,
        fecha_registro=fecha_chile(asistencia.fecha_registro), fecha_firma=fecha_chile(asistencia.fecha_firma))


@acceso()
@require_GET
@errores
def historial_sesiones(request):
    q = request.GET.get('q', '').strip().casefold()
    results = []
    sesiones = Sesiones.objects.select_related('plantilla', 'anfitrion').prefetch_related('asistencias_set').order_by('-id')
    if request.GET.get('estado') in ('PROGRAMADA', 'ABIERTA', 'CERRADA'):
        sesiones = sesiones.filter(estado=request.GET['estado'])
    sesiones = sesiones_visibles(request.actor, sesiones)
    for sesion in sesiones:
        attendees = list(sesion.asistencias_set.all())
        if q and q not in sesion.nombre.casefold() and not any(q in ' '.join([a.nombre_registrado, a.rut_registrado, a.cargo_registrado]).casefold() or q.replace('.', '').replace('-', '') in a.rut_registrado.replace('.', '').replace('-', '').casefold() for a in attendees):
            continue
        row = datos_sesion(sesion)
        firma_anfitrion = int(bool(getattr(sesion, 'programacion', None) and sesion.programacion.fecha_firma))
        row.update(total_asistencias=len(attendees) + firma_anfitrion, total_firmadas=sum(a.estado == 'FIRMADO' for a in attendees) + firma_anfitrion,
            total_pendientes=sum(a.estado == 'PENDIENTE_FIRMA' for a in attendees))
        results.append(row)
    return JsonResponse({'sesiones': results})


@acceso()
@require_GET
def listar_sesiones(request):
    query = Sesiones.objects.select_related('plantilla', 'anfitrion').order_by('-id')
    query = sesiones_visibles(request.actor, query)
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
    programacion = getattr(sesion, 'programacion', None)
    if programacion and programacion.fecha_firma:
        datos = json_guardado(programacion.datos_anfitrion_json, dict)
        rows.insert(0, dict(id=-sesion.pk, nombre=datos.get('nombre',''), cargo='Anfitrión',
            rut=datos.get('rut',''), correo=datos.get('correo',''), telefono=datos.get('telefono',''), campos={},
            estado='FIRMADO', fecha_registro=fecha_chile(programacion.fecha_firma), fecha_firma=fecha_chile(programacion.fecha_firma),
            tiene_firma=True, es_anfitrion=True, devolucion_firmada=False, docente_firmado=False))
    data = datos_sesion(sesion)
    data['permisos'] = {accion: tiene_permiso(request.actor, accion, sesion)
                        for accion in ('crear', 'observaciones', 'cerrar', 'exportar')}
    data.update(es_epp=sesion.plantilla.nombre == EPP, es_panol=sesion.plantilla.nombre == PANOL,
        campos_asistente=campos_asistente(sesion))
    return JsonResponse({'sesion': data, 'asistencias': rows})


@require_GET
@errores
def consultar_sesion(request, token):
    s = obtener_sesion(token=token)
    return JsonResponse(dict(id=s.id, nombre=s.nombre, estado=s.estado,
        fecha_programada=fecha_chile(s.programacion.fecha_programada) if hasattr(s, 'programacion') else '',
        fecha_inicio=fecha_chile(s.fecha_inicio), fecha_cierre=fecha_chile(s.fecha_cierre), campos_asistente=campos_asistente(s), entrega_epp=s.plantilla.nombre == EPP))


@require_http_methods(['GET', 'POST'])
@errores
def consultar_asistencia_existente(request, token):
    sesion = obtener_sesion(token=token)
    envio = cuerpo(request).get('registro_token', '') if request.method == 'POST' else request.GET.get('registro_token', '')
    if not envio:
        raise ErrorFormulario('Se necesita el identificador del registro.')
    a = Asistencias.objects.filter(sesion=sesion, registro_token=envio).first()
    response = JsonResponse({'registrada': a is not None, 'estado': a.estado if a else None,
        'devolucion_firmada': bool(a and FirmasDevolucion.objects.filter(asistencia=a).exists())})
    response['Cache-Control'] = 'no-store'
    return response


@require_POST
@errores
def firmar_desde_dispositivo(request, token):
    data = cuerpo(request)
    try:
        registro = str(uuid.UUID(data.get('registro_token', '')))
    except (ValueError, TypeError, AttributeError):
        raise ErrorFormulario('No se reconoce el registro de este dispositivo.')
    tipo = data.get('tipo')
    if tipo not in ('asistencia', 'devolucion'):
        raise ErrorFormulario('Tipo de firma inválido.')
    imagen = validar_png(data.get('firma'))
    with transaction.atomic():
        sesion = obtener_sesion(token=token, lock=True)
        a = Asistencias.objects.select_for_update().filter(sesion=sesion, registro_token=registro).first()
        if a is None:
            raise ErrorFormulario('No se encontró tu registro en esta actividad.', 404)
        devolucion = tipo == 'devolucion'
        if devolucion and sesion.plantilla.nombre != EPP:
            raise ErrorFormulario('Esta actividad no contempla una firma de devolución.')
        model = FirmasDevolucion if devolucion else Firmas
        previa = model.objects.filter(asistencia=a).first()
        if previa and bytes(previa.imagen) == imagen:
            return JsonResponse({'estado': a.estado, 'devolucion_firmada': devolucion})
        if sesion.estado != 'ABIERTA':
            raise ErrorFormulario('La sesión está cerrada. No se pueden guardar firmas.', 409)
        if previa:
            raise ErrorFormulario('Esta firma ya está guardada.', 409)
        if devolucion:
            if a.estado != 'FIRMADO' or not Firmas.objects.filter(asistencia=a).exists():
                raise ErrorFormulario('Primero debes firmar la recepción.', 409)
            accion = 'FIRMAR_DEVOLUCION'
        else:
            if a.estado != 'PENDIENTE_FIRMA':
                raise ErrorFormulario('Esta asistencia ya no está pendiente de firma.', 409)
            accion = 'FIRMAR_RECEPCION' if sesion.plantilla.nombre == EPP else 'FIRMAR_ASISTENCIA'
        model.objects.create(asistencia=a, imagen=imagen, formato='image/png')
        if not devolucion:
            a.estado, a.fecha_firma = 'FIRMADO', timezone.now().isoformat()
            a.save(update_fields=['estado', 'fecha_firma'])
        auditar(request, accion, 'asistencia', a.id, despues={'sesion_id': sesion.id})
    return JsonResponse({'estado': a.estado, 'devolucion_firmada': devolucion}, status=201)


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
            raise ErrorFormulario('La actividad aún no ha iniciado.' if sesion.estado == 'PROGRAMADA' else 'La sesión está cerrada.', 409)
        rut = valores.get('rut', '')
        programacion = getattr(sesion, 'programacion', None)
        if rut and programacion and programacion.fecha_firma and json_guardado(programacion.datos_anfitrion_json, dict).get('rut') == rut:
            raise ErrorFormulario('El anfitrión ya encabeza la lista con su firma de inicio.', 409)
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
        rut_visible = ''
        if rut:
            cuerpo_rut, verificador = rut.split('-')
            rut_visible = f"{int(cuerpo_rut):,}".replace(',', '.') + '-' + verificador
        a = Asistencias.objects.create(sesion=sesion, asistente=asistente,
            nombre_registrado=valores['nombre'], rut_registrado=rut_visible, cargo_registrado=valores.get('cargo', ''),
            correo_registrado=valores.get('correo', ''), telefono_registrado=valores.get('telefono', ''),
            campos_participante_json=json.dumps(valores, ensure_ascii=False), registro_token=envio, estado='PENDIENTE_FIRMA')
        auditar(request, 'REGISTRAR_ASISTENCIA', 'asistencia', a.id, despues={'sesion_id': sesion.id})
    return JsonResponse({'asistencia_id': a.id, 'estado': a.estado, 'registro_token': envio}, status=201)


@require_GET
def pagina_inicio(request):
    sesion = Sesiones.objects.select_related('plantilla').filter(token_qr=request.GET.get('token', '')).first()
    return render(request, 'index.html', {'campos_asistente': campos_asistente(sesion)})


@acceso(pagina=True, permiso='panel_anfitrion')
def pagina_anfitrion(request):
    return render(request, 'anfitrion.html', {'actor': request.actor})


@acceso(pagina=True)
def pagina_administrador(request):
    return render(request, 'administrador.html', {'actor': request.actor})


def obtener_asistencia(request, asistencia_id):
    try:
        a = Asistencias.objects.get(id=asistencia_id)
    except Asistencias.DoesNotExist:
        raise ErrorFormulario('La asistencia no existe.', 404)
    sesion = obtener_sesion(request, a.sesion_id, lock=True, accion='crear')
    if sesion.estado != 'ABIERTA':
        raise ErrorFormulario('La sesión está cerrada. No se pueden guardar firmas.', 409)
    return Asistencias.objects.select_for_update().get(id=a.id), sesion


@acceso(permiso='crear')
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


@acceso(permiso='crear')
@require_POST
@errores
def guardar_firma_devolucion(request, asistencia_id):
    return firma_extra(request, asistencia_id)


@acceso(permiso='crear')
@require_POST
@errores
def guardar_firma_docente(request, asistencia_id):
    return firma_extra(request, asistencia_id, True)


@acceso(permiso='cerrar')
@require_POST
@errores
def cerrar_sesion(request, sesion_id):
    with transaction.atomic():
        s = obtener_sesion(request, sesion_id, lock=True, accion='cerrar')
        if s.estado == 'PROGRAMADA':
            raise ErrorFormulario('La actividad todavía no ha iniciado.', 409)
        if s.estado != 'CERRADA':
            s.estado, s.fecha_cierre = 'CERRADA', timezone.now().isoformat()
            s.save(update_fields=['estado', 'fecha_cierre'])
            auditar(request, 'CERRAR_SESION', 'sesion', s.id, despues={'fecha_cierre': s.fecha_cierre})
    return JsonResponse({'mensaje': 'Sesión cerrada.', 'sesion_id': s.id, 'estado': s.estado, 'fecha_cierre': fecha_chile(s.fecha_cierre)})


@acceso()
@require_GET
def opciones_sesion(request):
    query = Usuarios.objects.filter(activo=1)
    from .organizacion import datos_perfil
    anfitriones = [{'id': usuario.id, 'nombre': usuario.nombre, **datos_perfil(usuario)} for usuario in query]
    return JsonResponse({'plantillas': [{'id': p.id, 'nombre': p.nombre, 'descripcion': p.descripcion,
        'campos': campos_por_etapa(list(p.camposplantilla_set.order_by('orden', 'id').values('nombre', 'etiqueta', 'tipo', 'obligatorio')))}
        for p in PlantillasSesion.objects.filter(activa=1).prefetch_related('camposplantilla_set').order_by('nombre')], 'anfitriones': anfitriones, 'organizacion_creador': datos_perfil(request.actor), 'puede_crear': tiene_permiso(request.actor, 'crear')})


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


@acceso(permiso='crear')
@require_POST
@errores
def crear_sesion(request):
    data = cuerpo(request)
    nombre = data.get('nombre', '')
    if not isinstance(nombre, str) or not nombre.strip() or len(nombre) > 200:
        raise ErrorFormulario('Indica un nombre de hasta 200 caracteres.')
    from datetime import datetime
    from .domain import CHILE
    from .models import ContextoSesion, ProgramacionSesion
    from .organizacion import datos_perfil, permite_contexto
    try:
        plantilla = PlantillasSesion.objects.get(id=int(str(data.get('plantilla_id'))), activa=1)
        programada = datetime.fromisoformat(data.get('fecha_programada', ''))
        if programada.tzinfo is None: programada = programada.replace(tzinfo=CHILE)
        previsto_id = data.get('anfitrion_id')
        previsto = Usuarios.objects.get(id=int(str(previsto_id)), activo=1) if previsto_id else None
    except (ValueError, TypeError, PlantillasSesion.DoesNotExist, Usuarios.DoesNotExist):
        raise ErrorFormulario('Selecciona una plantilla, una fecha y hora programadas válidas y, opcionalmente, un anfitrión previsto.')
    perfil = datos_perfil(request.actor)
    if not perfil['sede_id'] or not perfil['area_id']:
        raise ErrorFormulario('Completa tu sede y área en Mi cuenta antes de programar actividades.')
    if not permite_contexto(request.actor, 'crear', perfil['sede_id'], perfil['area_id']):
        raise ErrorFormulario('No puedes programar en esta sede o área.', 403)
    campos = campos_por_etapa(list(plantilla.camposplantilla_set.order_by('orden', 'id').values('nombre', 'etiqueta', 'tipo', 'obligatorio', 'orden')))
    valores = validar_campos(campos, data.get('campos', {}), True)
    with transaction.atomic():
        s = Sesiones.objects.create(plantilla=plantilla, anfitrion=None, nombre=nombre.strip(), estado='PROGRAMADA',
            fecha_inicio=None, token_qr=uuid.uuid4().hex,
            campos_definicion_json=json.dumps(campos, ensure_ascii=False), campos_valores_json=json.dumps(valores, ensure_ascii=False))
        ContextoSesion.objects.create(sesion=s, sede_id=perfil['sede_id'], area_id=perfil['area_id'])
        ProgramacionSesion.objects.create(sesion=s, creador=request.actor, fecha_programada=programada, anfitrion_previsto=previsto)
        auditar(request, 'CREAR_SESION', 'sesion', s.id, despues=datos_sesion(s))
    return JsonResponse({'id': s.id, 'nombre': s.nombre, 'estado': s.estado}, status=201)


@acceso(permiso='observaciones')
@require_POST
@errores
def guardar_desarrollo(request, sesion_id):
    data = cuerpo(request)
    cambios, base = data.get('campos'), data.get('base')
    if not isinstance(cambios, dict) or not isinstance(base, dict):
        raise ErrorFormulario('Falta la versión original de las observaciones. Recarga antes de editar.')
    with transaction.atomic():
        s = obtener_sesion(request, sesion_id, lock=True, accion='observaciones')
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


def url_registro(request, sesion):
    ruta = '/?token=' + sesion.token_qr
    return settings.PUBLIC_SITE_URL + ruta if settings.PUBLIC_SITE_URL else request.build_absolute_uri(ruta)


@acceso()
@require_GET
@errores
def codigo_qr(request, sesion_id):
    import io
    import qrcode
    s = obtener_sesion(request, sesion_id)
    url = url_registro(request, s)
    buffer = io.BytesIO()
    qrcode.make(url).save(buffer, format='PNG')
    return HttpResponse(buffer.getvalue(), content_type='image/png')


@acceso()
@require_GET
@errores
def afiche_qr(request, sesion_id):
    import io
    import qrcode
    from django.contrib.staticfiles import finders
    from PIL import Image, ImageDraw, ImageFont

    sesion = obtener_sesion(request, sesion_id)
    url = url_registro(request, sesion)
    ancho, alto = 1240, 1754
    centro = ancho // 2
    rojo, negro, gris = '#cc0000', '#151515', '#515151'
    pagina = Image.new('RGB', (ancho, alto), 'white')
    dibujo = ImageDraw.Draw(pagina)

    def texto_centrado(valor, y, tamano, color, max_lineas=1):
        for nombre_fuente in ('DejaVuSans.ttf', 'arial.ttf'):
            try:
                fuente = ImageFont.truetype(nombre_fuente, tamano)
                break
            except OSError:
                continue
        else:
            fuente = ImageFont.load_default(size=tamano)
        palabras = str(valor).split()
        lineas = []
        linea = ''
        for palabra in palabras:
            candidato = f'{linea} {palabra}'.strip()
            if linea and dibujo.textlength(candidato, font=fuente) > 1040:
                lineas.append(linea)
                linea = palabra
            else:
                linea = candidato
        if linea:
            lineas.append(linea)
        for indice, linea in enumerate(lineas[:max_lineas]):
            sufijo = '…' if indice == max_lineas - 1 and len(lineas) > max_lineas else ''
            while dibujo.textlength(linea + sufijo, font=fuente) > 1040:
                linea = linea[:-1]
                sufijo = '…'
            dibujo.text((centro, y), linea + sufijo, fill=color, font=fuente, anchor='mt')
            y += tamano + 12
        return y

    dibujo.rectangle((0, 0, ancho, 168), fill='#1e1e1e')
    dibujo.rectangle((0, 168, ancho, 176), fill='#cc0000')
    with Image.open(finders.find('img/inacap-60.png')) as imagen:
        logo = imagen.convert('RGBA')
        logo.thumbnail((420, 76), Image.Resampling.LANCZOS)
        pagina.paste(logo, (centro - logo.width // 2, 26), logo)
    texto_centrado('Registro de asistencia', 111, 32, 'white')
    texto_centrado('ESCANEA PARA REGISTRAR TU ASISTENCIA', 218, 34, rojo)

    datos = json_guardado(sesion.campos_valores_json, dict)
    tema = datos.get('tema') or datos.get('tema_o_asunto')
    y = texto_centrado(sesion.nombre, 292, 66, negro, max_lineas=2)
    y = texto_centrado(sesion.plantilla.nombre, y + 20, 38, gris, max_lineas=2)
    if tema:
        y = texto_centrado(tema, y + 4, 34, gris, max_lineas=2)
    if hasattr(sesion, 'programacion'):
        y = texto_centrado('Programada: ' + fecha_chile(sesion.programacion.fecha_programada).replace('T', ' ')[:16], y + 8, 30, gris)
    y = texto_centrado(f'Anfitrión: {sesion.anfitrion.nombre if sesion.anfitrion else "Se confirma al iniciar"}', y + 8, 32, gris, max_lineas=2)

    codigo = qrcode.QRCode(border=4)
    codigo.add_data(url)
    codigo.make(fit=True)
    codigo.box_size = max(1, 620 // (codigo.modules_count + 2 * codigo.border))
    qr = codigo.make_image().convert('RGB')
    y_qr = max(660, y + 48)
    x_qr = (ancho - qr.width) // 2
    dibujo.rounded_rectangle(
        (x_qr - 18, y_qr - 18, x_qr + qr.width + 18, y_qr + qr.height + 18),
        radius=30, outline='#dddddd', width=3,
    )
    pagina.paste(qr, (x_qr, y_qr))
    texto_centrado('Completa tus datos y firma desde tu dispositivo.',
                   y_qr + qr.height + 80, 36, negro)
    buffer = io.BytesIO()
    pagina.save(buffer, format='PDF', resolution=150)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="afiche-asistencia-{sesion.id}.pdf"'
    response['Cache-Control'] = 'private, no-store'
    return response


@acceso(permiso='crear')
@require_POST
@errores
def iniciar_sesion(request, sesion_id):
    from .models import ProgramacionSesion
    from .organizacion import datos_perfil, permite_contexto
    data = cuerpo(request)
    with transaction.atomic():
        s = obtener_sesion(request, sesion_id, lock=True, accion='crear')
        if s.estado != 'PROGRAMADA':
            raise ErrorFormulario('La actividad ya inició o está cerrada. No se reemplazó el anfitrión ni su firma.', 409)
        try:
            anfitrion = Usuarios.objects.get(id=int(str(data.get('anfitrion_id'))), activo=1)
        except (ValueError, TypeError, Usuarios.DoesNotExist):
            raise ErrorFormulario('Selecciona el anfitrión que está presente.')
        contexto = s.contexto
        perfil = datos_perfil(anfitrion)
        if (perfil['sede_id'],perfil['area_id']) != (contexto.sede_id,contexto.area_id):
            raise ErrorFormulario('El anfitrión debe pertenecer a la sede y área de esta actividad.')
        firma = validar_png(data.get('firma'))
        if not isinstance(data.get('rut'), str):
            raise ErrorFormulario('Indica un RUT válido para el anfitrión.')
        rut = normalizar_rut(data.get('rut', ''))
        ahora = timezone.now()
        programacion = ProgramacionSesion.objects.select_for_update().get(sesion=s)
        programacion.iniciada_por = request.actor
        programacion.firma_anfitrion = firma
        programacion.fecha_firma = ahora
        programacion.datos_anfitrion_json = json.dumps({'nombre': anfitrion.nombre, 'rut': rut,
            'correo': anfitrion.correo, 'telefono': anfitrion.telefono, 'cargo': 'Anfitrión'}, ensure_ascii=False)
        programacion.save()
        s.anfitrion = anfitrion
        s.estado = 'ABIERTA'
        s.fecha_inicio = ahora.isoformat()
        s.save(update_fields=['anfitrion','estado','fecha_inicio'])
        auditar(request, 'INICIAR_ACTIVIDAD', 'sesion', s.pk,
                despues={'creador_id': programacion.creador_id, 'anfitrion_id': anfitrion.pk, 'inicio_real': s.fecha_inicio})
    return JsonResponse(datos_sesion(s))
