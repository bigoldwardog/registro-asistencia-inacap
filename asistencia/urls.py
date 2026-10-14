
from django.urls import path

from . import views

urlpatterns = [
    path(
        "api/sesiones/<str:token>/",
        views.consultar_sesion,
        name="consultar_sesion",
    ),
]
