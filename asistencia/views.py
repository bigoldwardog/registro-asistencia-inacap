
import json

from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .models import Sesiones


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
