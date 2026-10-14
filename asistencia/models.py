# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models


class Asistencias(models.Model):
    sesion = models.ForeignKey('Sesiones', models.DO_NOTHING)
    asistente = models.ForeignKey('Asistentes', models.DO_NOTHING)
    nombre_registrado = models.TextField()
    rut_registrado = models.TextField()
    telefono_registrado = models.TextField()
    correo_registrado = models.TextField()
    estado = models.TextField()
    fecha_registro = models.TextField()
    fecha_firma = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'asistencias'


class Asistentes(models.Model):
    rut = models.TextField(unique=True)
    nombre = models.TextField()
    telefono = models.TextField()
    correo = models.TextField()
    fecha_creacion = models.TextField()
    fecha_actualizacion = models.TextField()

    class Meta:
        managed = False
        db_table = 'asistentes'


class Auditoria(models.Model):
    usuario = models.ForeignKey('Usuarios', models.DO_NOTHING, blank=True, null=True)
    accion = models.TextField()
    entidad = models.TextField()
    entidad_id = models.IntegerField(blank=True, null=True)
    datos_anteriores_json = models.TextField(blank=True, null=True)
    datos_nuevos_json = models.TextField(blank=True, null=True)
    fecha = models.TextField()

    class Meta:
        managed = False
        db_table = 'auditoria'


class CamposPlantilla(models.Model):
    plantilla = models.ForeignKey('PlantillasSesion', models.DO_NOTHING)
    nombre = models.TextField()
    etiqueta = models.TextField()
    tipo = models.TextField()
    obligatorio = models.IntegerField()
    orden = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'campos_plantilla'


class Firmas(models.Model):
    asistencia = models.OneToOneField(Asistencias, models.DO_NOTHING)
    imagen = models.BinaryField()
    formato = models.TextField()
    fecha_creacion = models.TextField()

    class Meta:
        managed = False
        db_table = 'firmas'


class PlantillasSesion(models.Model):
    nombre = models.TextField(unique=True)
    descripcion = models.TextField(blank=True, null=True)
    activa = models.IntegerField()
    fecha_creacion = models.TextField()

    class Meta:
        managed = False
        db_table = 'plantillas_sesion'


class Sesiones(models.Model):
    plantilla = models.ForeignKey(PlantillasSesion, models.DO_NOTHING)
    anfitrion = models.ForeignKey('Usuarios', models.DO_NOTHING)
    nombre = models.TextField()
    fecha_inicio = models.TextField()
    fecha_cierre = models.TextField(blank=True, null=True)
    estado = models.TextField()
    token_qr = models.TextField(unique=True)
    campos_definicion_json = models.TextField()
    campos_valores_json = models.TextField()
    fecha_creacion = models.TextField()

    class Meta:
        managed = False
        db_table = 'sesiones'


class Usuarios(models.Model):
    nombre = models.TextField()
    correo = models.TextField(unique=True)
    password_hash = models.TextField()
    rol = models.TextField()
    activo = models.IntegerField()
    fecha_creacion = models.TextField()

    class Meta:
        managed = False
        db_table = 'usuarios'
