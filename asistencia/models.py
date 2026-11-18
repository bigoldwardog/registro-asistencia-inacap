# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models
from django.utils import timezone

def fecha_actual():
    return timezone.now().isoformat()


class Asistencias(models.Model):
    sesion = models.ForeignKey('Sesiones', models.DO_NOTHING)
    asistente = models.ForeignKey('Asistentes', models.DO_NOTHING)
    nombre_registrado = models.TextField()
    cargo_registrado = models.TextField(default="")
    campos_participante_json = models.TextField(default="{}")
    registro_token = models.TextField(unique=True, null=True, blank=True)
    rut_registrado = models.TextField()
    telefono_registrado = models.TextField()
    correo_registrado = models.TextField()
    estado = models.TextField()
    fecha_registro = models.TextField(default=fecha_actual)
    fecha_firma = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'asistencias'


class Asistentes(models.Model):
    rut = models.TextField(unique=True, null=True, blank=True)
    nombre = models.TextField()
    telefono = models.TextField()
    correo = models.TextField()
    fecha_creacion = models.TextField(default=fecha_actual)
    fecha_actualizacion = models.TextField(default=fecha_actual)

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
    fecha = models.TextField(default=fecha_actual)

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
    fecha_creacion = models.TextField(default=fecha_actual)

    class Meta:
        managed = False
        db_table = 'firmas'


class PlantillasSesion(models.Model):
    nombre = models.TextField(unique=True)
    descripcion = models.TextField(blank=True, null=True)
    activa = models.IntegerField()
    fecha_creacion = models.TextField(default=fecha_actual)

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
    fecha_creacion = models.TextField(default=fecha_actual)

    class Meta:
        managed = False
        db_table = 'sesiones'


class Usuarios(models.Model):
    nombre = models.TextField()
    correo = models.TextField(unique=True)
    telefono = models.TextField(default='')
    password_hash = models.TextField()
    rol = models.TextField()
    activo = models.IntegerField()
    fecha_creacion = models.TextField(default=fecha_actual)

    @property
    def es_superusuario(self):
        from .permissions import permisos_usuario
        return permisos_usuario(self)['superusuario']

    @property
    def puede_crear_sesiones(self):
        from .permissions import permisos_usuario
        return permisos_usuario(self)['crear'] != 'NINGUNA'

    @property
    def puede_exportar(self):
        from .permissions import permisos_usuario
        permisos = permisos_usuario(self)
        return permisos['exportar'] != 'NINGUNA'

    @property
    def puede_gestionar_sesiones(self):
        from .permissions import permisos_usuario
        permisos = permisos_usuario(self)
        return any(permisos[accion] != 'NINGUNA' for accion in ('crear', 'observaciones', 'cerrar'))

    class Meta:
        managed = False
        db_table = 'usuarios'


class FirmasDevolucion(models.Model):
    asistencia = models.OneToOneField(Asistencias, models.DO_NOTHING)
    imagen = models.BinaryField()
    formato = models.TextField(default="image/png")
    fecha_creacion = models.TextField(default=fecha_actual)

    class Meta:
        managed = False
        db_table = 'firmas_devolucion'


class FirmasAdicionales(models.Model):
    asistencia = models.ForeignKey(Asistencias, models.DO_NOTHING)
    tipo = models.TextField()
    imagen = models.BinaryField()
    formato = models.TextField(default='image/png')
    fecha_creacion = models.TextField(default=fecha_actual)

    class Meta:
        managed = False
        db_table = 'firmas_adicionales'
        unique_together = [('asistencia', 'tipo')]


class RolAcceso(models.Model):
    nombre = models.CharField(max_length=80, unique=True)
    ALCANCES = [('NINGUNA', 'Ninguna'), ('PROPIAS', 'Propias'), ('TODAS', 'Todas')]
    consultar = models.CharField(max_length=8, choices=ALCANCES, default='PROPIAS')
    crear = models.CharField(max_length=8, choices=ALCANCES, default='NINGUNA')
    observaciones = models.CharField(max_length=8, choices=ALCANCES, default='NINGUNA')
    cerrar = models.CharField(max_length=8, choices=ALCANCES, default='NINGUNA')
    exportar = models.CharField(max_length=8, choices=ALCANCES, default='NINGUNA')

    class Meta:
        db_table = 'roles_acceso'


class AccesoUsuario(models.Model):
    usuario = models.OneToOneField(Usuarios, models.CASCADE, primary_key=True,
                                  db_constraint=False, related_name='acceso_configurado')
    rol = models.ForeignKey(RolAcceso, models.PROTECT)
    superusuario = models.BooleanField(default=False)

    class Meta:
        db_table = 'accesos_usuarios'
        constraints = [
            models.UniqueConstraint(fields=['superusuario'], condition=models.Q(superusuario=True),
                                    name='un_superusuario_base')
        ]
