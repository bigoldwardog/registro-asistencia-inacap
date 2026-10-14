from django.urls import path
from . import views

urlpatterns = [
    path("", views.pagina_inicio, name="inicio"),
    path("anfitrion/", views.pagina_anfitrion, name="anfitrion"),
    path("administrador/", views.pagina_administrador, name="administrador"),

    # Listar todas las sesiones
    path(
        "api/sesiones/",
        views.listar_sesiones,
        name="listar_sesiones",
    ),

    # Consultar una sesión mediante su token QR
    path(
        "api/sesiones/<str:token>/",
        views.consultar_sesion,
        name="consultar_sesion",
    ),

    # Registrar una asistencia mediante el token QR
    path(
        "api/sesiones/<str:token>/asistencias/",
        views.registrar_asistencia,
        name="registrar_asistencia",
    ),

    # Listar las asistencias de una sesión
    path(
        "api/sesiones/<int:sesion_id>/asistencias/lista/",
        views.listar_asistencias,
        name="listar_asistencias",
    ),

    # Guardar la firma de una asistencia
    path(
        "api/asistencias/<int:asistencia_id>/firma/",
        views.guardar_firma,
        name="guardar_firma",
    ),

    # Cerrar una sesión
    path(
        "api/sesiones/<int:sesion_id>/cerrar/",
        views.cerrar_sesion,
        name="cerrar_sesion",
    ),


    path(
        "api/sesiones/<str:token>/asistencias/consultar/",
        views.consultar_asistencia_existente,
        name="consultar_asistencia_existente",
    ),

    path(
    "api/administrador/historial/",
    views.historial_sesiones,
    name="historial_sesiones",
    ),
]