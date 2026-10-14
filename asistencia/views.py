
import base64
import binascii
import json

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django.db.models import Count, Q

import uuid

from .models import (
    Asistencias,
    Asistentes,
    Firmas,
    Sesiones,
    PlantillasSesion,
    CamposPlantilla,
    Usuarios,
)

@require_GET
def historial_sesiones(request):
    sesiones = (
        Sesiones.objects
        .select_related("plantilla", "anfitrion")
        .annotate(
            total_asistencias=Count("asistencias"),
            total_firmadas=Count(
                "asistencias",
                filter=Q(asistencias__estado="FIRMADO"),
            ),
            total_pendientes=Count(
                "asistencias",
                filter=Q(asistencias__estado="PENDIENTE_FIRMA"),
            ),
        )
        .order_by("-id")
    )

    resultados = []

    for sesion in sesiones:
        resultados.append({
            "id": sesion.id,
            "nombre": sesion.nombre,
            "estado": sesion.estado,
            "fecha_inicio": sesion.fecha_inicio,
            "fecha_cierre": sesion.fecha_cierre,
            "plantilla": sesion.plantilla.nombre,
            "anfitrion": sesion.anfitrion.nombre,
            "total_asistencias": sesion.total_asistencias,
            "total_firmadas": sesion.total_firmadas,
            "total_pendientes": sesion.total_pendientes,
        })

    return JsonResponse({"sesiones": resultados})

@require_GET
def listar_sesiones(request):
    sesiones = Sesiones.objects.all().order_by("-id")

    resultados = []

    for sesion in sesiones:
        resultados.append({
            "id": sesion.id,
            "nombre": sesion.nombre,
            "estado": sesion.estado,
            "fecha_inicio": sesion.fecha_inicio,
            "fecha_cierre": sesion.fecha_cierre,
            "token_qr": sesion.token_qr,
        })

    return JsonResponse({"sesiones": resultados})


@require_GET
def listar_asistencias(request, sesion_id):
    try:
        sesion = Sesiones.objects.get(id=sesion_id)
    except Sesiones.DoesNotExist:
        return JsonResponse(
            {"error": "La sesión no existe."},
            status=404,
        )

    asistencias = Asistencias.objects.filter(
        sesion_id=sesion.id
    ).order_by("fecha_registro", "id")

    resultados = []

    for asistencia in asistencias:
        resultados.append({
            "id": asistencia.id,
            "nombre": asistencia.nombre_registrado,
            "rut": asistencia.rut_registrado,
            "telefono": asistencia.telefono_registrado,
            "correo": asistencia.correo_registrado,
            "estado": asistencia.estado,
            "fecha_registro": asistencia.fecha_registro,
        })

    return JsonResponse({
        "sesion": {
            "id": sesion.id,
            "nombre": sesion.nombre,
            "estado": sesion.estado,
        },
        "asistencias": resultados,
    })

@require_GET
def consultar_sesion(request, token):
    try:
        sesion = Sesiones.objects.get(token_qr=token)
    except Sesiones.DoesNotExist:
        return JsonResponse(
            {"error": "La sesión no existe."},
            status=404,
        )

    return JsonResponse({
        "id": sesion.id,
        "nombre": sesion.nombre,
        "estado": sesion.estado,
        "fecha_inicio": sesion.fecha_inicio,
        "fecha_cierre": sesion.fecha_cierre,
    })


def consultar_asistencia_existente(request, token):
    if request.method != "GET":
        return JsonResponse(
            {"error": "Método no permitido."},
            status=405,
        )

    rut = request.GET.get("rut", "").strip().upper()

    if not rut:
        return JsonResponse(
            {"error": "Debes indicar un RUT."},
            status=400,
        )

    try:
        sesion = Sesiones.objects.get(token_qr=token)
    except Sesiones.DoesNotExist:
        return JsonResponse(
            {"error": "La sesión no existe."},
            status=404,
        )

    asistencia = Asistencias.objects.filter(
        sesion_id=sesion.id,
        rut_registrado=rut,
    ).first()

    return JsonResponse({
        "registrada": asistencia is not None,
        "estado": asistencia.estado if asistencia else None,
    })

@csrf_exempt
@require_POST
def registrar_asistencia(request, token):
    try:
        datos = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse(
            {"error": "El cuerpo de la solicitud debe ser JSON válido."},
            status=400,
        )

    if not isinstance(datos, dict):
        return JsonResponse(
            {"error": "Se esperaba un objeto JSON."},
            status=400,
        )

    nombre = datos.get("nombre", "").strip()
    rut = datos.get("rut", "").strip().upper()
    telefono = datos.get("telefono", "").strip()
    correo = datos.get("correo", "").strip()

    if not all([nombre, rut, telefono, correo]):
        return JsonResponse(
            {"error": "Todos los campos son obligatorios."},
            status=400,
        )

    try:
        validate_email(correo)
    except ValidationError:
        return JsonResponse(
            {"error": "El correo electrónico no es válido."},
            status=400,
        )

    try:
        with transaction.atomic():
            sesion = Sesiones.objects.get(token_qr=token)

            if sesion.estado != "ABIERTA":
                return JsonResponse(
                    {"error": "La sesión está cerrada."},
                    status=409,
                )

                        
            asistencia_existente = Asistencias.objects.filter(
                sesion_id=sesion.id,
                rut_registrado=rut,
            ).exists()

            if asistencia_existente:
                return JsonResponse(
                    {
                        "error": "Este RUT ya tiene una asistencia registrada en esta sesión."
                    },
                    status=409,
                )


            asistente, creado = Asistentes.objects.get_or_create(
                rut=rut,
                defaults={
                    "nombre": nombre,
                    "telefono": telefono,
                    "correo": correo,
                },
            )

            if not creado:
                asistente.nombre = nombre
                asistente.telefono = telefono
                asistente.correo = correo
                asistente.save(
                    update_fields=["nombre", "telefono", "correo"]
                )

            asistencia = Asistencias.objects.create(
                sesion_id=sesion.id,
                asistente_id=asistente.id,
                nombre_registrado=nombre,
                rut_registrado=rut,
                telefono_registrado=telefono,
                correo_registrado=correo,
                estado="PENDIENTE_FIRMA",
            )

    except Sesiones.DoesNotExist:
        return JsonResponse(
            {"error": "La sesión no existe."},
            status=404,
        )
    except IntegrityError:
        return JsonResponse(
            {"error": "Este asistente ya tiene una asistencia registrada en esta sesión."},
            status=409,
        )

    return JsonResponse(
        {
            "mensaje": "Asistencia registrada correctamente.",
            "asistencia_id": asistencia.id,
            "estado": asistencia.estado,
        },
        status=201,
    )


@require_GET
def opciones_creacion_sesion(request):
    plantillas = PlantillasSesion.objects.filter(
        activa=1
    ).order_by("nombre")

    anfitriones = Usuarios.objects.filter(
        activo=1
    ).order_by("nombre")

    return JsonResponse({
        "plantillas": [
            {"id": p.id, "nombre": p.nombre}
            for p in plantillas
        ],
        "anfitriones": [
            {"id": u.id, "nombre": u.nombre}
            for u in anfitriones
        ],
    })


@csrf_exempt
@require_POST
def crear_sesion(request):
    try:
        datos = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse(
            {"error": "El cuerpo de la solicitud debe ser JSON válido."},
            status=400,
        )

    if not isinstance(datos, dict):
        return JsonResponse(
            {"error": "Se esperaba un objeto JSON."},
            status=400,
        )

    nombre = datos.get("nombre", "")
    if not isinstance(nombre, str) or not nombre.strip():
        return JsonResponse(
            {"error": "Debes indicar el nombre de la sesión."},
            status=400,
        )

    try:
        plantilla = PlantillasSesion.objects.get(
            id=int(datos.get("plantilla_id")),
            activa=1,
        )
        anfitrion = Usuarios.objects.get(
            id=int(datos.get("anfitrion_id")),
            activo=1,
        )
    except (TypeError, ValueError):
        return JsonResponse(
            {"error": "Debes seleccionar una plantilla y un anfitrión válidos."},
            status=400,
        )
    except PlantillasSesion.DoesNotExist:
        return JsonResponse(
            {"error": "La plantilla no existe o está inactiva."},
            status=400,
        )
    except Usuarios.DoesNotExist:
        return JsonResponse(
            {"error": "El anfitrión no existe o está inactivo."},
            status=400,
        )

    campos = CamposPlantilla.objects.filter(
        plantilla_id=plantilla.id
    ).order_by("orden")

    definicion_campos = [
        {
            "nombre": campo.nombre,
            "etiqueta": campo.etiqueta,
            "tipo": campo.tipo,
            "obligatorio": bool(campo.obligatorio),
        }
        for campo in campos
    ]

    ahora = timezone.now().isoformat()

    sesion = Sesiones.objects.create(
        plantilla_id=plantilla.id,
        anfitrion_id=anfitrion.id,
        nombre=nombre.strip(),
        fecha_inicio=ahora,
        fecha_cierre=None,
        estado="ABIERTA",
        token_qr=uuid.uuid4().hex,
        campos_definicion_json=json.dumps(
            definicion_campos,
            ensure_ascii=False,
        ),
        campos_valores_json="{}",
        fecha_creacion=ahora,
    )

    return JsonResponse({
        "mensaje": "Sesión creada correctamente.",
        "sesion": {
            "id": sesion.id,
            "nombre": sesion.nombre,
            "estado": sesion.estado,
            "fecha_inicio": sesion.fecha_inicio,
            "token_qr": sesion.token_qr,
        },
    }, status=201)

def pagina_inicio(request):
    return render(request, "index.html")


def pagina_anfitrion(request):
    return render(request, "anfitrion.html")


def pagina_administrador(request):
    return render(request, "administrador.html")


@csrf_exempt
@require_POST
def guardar_firma(request, asistencia_id):
    try:
        datos = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse(
            {"error": "El cuerpo de la solicitud debe ser JSON válido."},
            status=400,
        )

    if not isinstance(datos, dict):
        return JsonResponse(
            {"error": "Se esperaba un objeto JSON."},
            status=400,
        )

    firma_data = datos.get("firma", "")

    if not isinstance(firma_data, str) or not firma_data.startswith(
        "data:image/png;base64,"
    ):
        return JsonResponse(
            {"error": "La firma debe ser una imagen PNG válida."},
            status=400,
        )

    try:
        imagen_bytes = base64.b64decode(
            firma_data.split(",", 1)[1],
            validate=True,
        )
    except (binascii.Error, ValueError):
        return JsonResponse(
            {"error": "No se pudo interpretar la imagen de la firma."},
            status=400,
        )

    if not imagen_bytes or len(imagen_bytes) > 2 * 1024 * 1024:
        return JsonResponse(
            {"error": "La firma está vacía o supera el límite de 2 MB."},
            status=400,
        )

    try:
        with transaction.atomic():
            asistencia = Asistencias.objects.select_for_update().get(
                id=asistencia_id
            )

            if asistencia.estado != "PENDIENTE_FIRMA":
                return JsonResponse(
                    {"error": "Esta asistencia ya no está pendiente de firma."},
                    status=409,
                )

            Firmas.objects.create(
                asistencia_id=asistencia.id,
                imagen=imagen_bytes,
                formato="image/png",
            )

            asistencia.estado = "FIRMADO"
            asistencia.fecha_firma = timezone.now()
            asistencia.save(
                update_fields=["estado", "fecha_firma"]
            )

    except Asistencias.DoesNotExist:
        return JsonResponse(
            {"error": "La asistencia no existe."},
            status=404,
        )
    except IntegrityError:
        return JsonResponse(
            {"error": "Ya existe una firma para esta asistencia."},
            status=409,
        )

    return JsonResponse({
        "mensaje": "Firma guardada correctamente.",
        "asistencia_id": asistencia.id,
        "estado": asistencia.estado,
    })

@csrf_exempt
@require_POST
def cerrar_sesion(request, sesion_id):
    try:
        with transaction.atomic():
            sesion = Sesiones.objects.select_for_update().get(
                id=sesion_id
            )

            if sesion.estado == "CERRADA":
                return JsonResponse({
                    "mensaje": "La sesión ya estaba cerrada.",
                    "sesion_id": sesion.id,
                    "estado": sesion.estado,
                    "fecha_cierre": sesion.fecha_cierre,
                })

            sesion.estado = "CERRADA"
            sesion.fecha_cierre = timezone.now()
            sesion.save(
                update_fields=["estado", "fecha_cierre"]
            )

    except Sesiones.DoesNotExist:
        return JsonResponse(
            {"error": "La sesión no existe."},
            status=404,
        )

    return JsonResponse({
        "mensaje": "Sesión cerrada correctamente.",
        "sesion_id": sesion.id,
        "estado": sesion.estado,
        "fecha_cierre": sesion.fecha_cierre,
    })
