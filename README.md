# Sistema de registro de asistencia

Aplicación web Django para anfitriones, asistentes y administración. Mantiene una firma presencial en la tablet del anfitrión y permite recuperar los datos y las firmas de cada actividad.

## Primer uso en este computador

1. Desde la carpeta del proyecto ejecuta `./INICIAR_LOCAL.ps1` en PowerShell.
2. En el computador del servidor abre http://127.0.0.1:8000/configuracion-inicial/ y crea tu cuenta administradora. No existe una contraseña predeterminada. Este formulario solo funciona desde el servidor y deja de estar disponible al crear la primera cuenta.
3. En Administración → Usuarios crea las cuentas de anfitrión. El administrador también puede abrir el panel del anfitrión y crear actividades.
4. Abre el panel mediante la IP de la red que muestra el iniciador y accede con tu cuenta. Genera el QR desde esa dirección, no desde localhost, para que los celulares de la misma red puedan abrirlo.

Las cuentas antiguas con `HASH_SOLO_PARA_PRUEBAS` se desactivan al preparar el sistema; no tenían una contraseña funcional. Los datos de personas y sus registros históricos se conservan. Los perfiles históricos con RUT equivalente no se fusionan automáticamente; las nuevas altas usan el perfil canónico y la comprobación de duplicados contempla todas las representaciones anteriores.

## Instalación en otro computador

Requiere Python 3.13 compatible con las dependencias fijadas en `requirements.txt`.

```powershell
cd "RUTA\registro-asistencia-inacap"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py preparar_sistema
.\INICIAR_LOCAL.ps1
```

También puedes ejecutar `./INSTALAR.ps1`. Este crea el entorno si falta, instala dependencias y prepara el esquema. Si ya hay una base, crea primero un respaldo SQLite.

`preparar_sistema` se puede repetir: aplica las migraciones internas de Django, crea o adapta las tablas de asistencia y carga las diez plantillas. No carga estudiantes, reuniones ni usuarios de ejemplo. No uses `database/seed.sql` para instalar: ese archivo se conserva únicamente como referencia histórica de pruebas.

## Flujo

- Nueva sesión: seleccionar plantilla, completar contexto de apertura y crear. El servidor registra fecha y hora de inicio.
- Los asistentes entran por QR sin cuenta. El formulario corresponde a la plantilla. Pueden recordar sus datos opcionalmente y confirmarlos parcialmente ocultos en otra reunión.
- Los envíos pendientes se conservan antes de enviarse. Tras perder una respuesta y recargar, se consulta el mismo identificador para no duplicar la asistencia.
- El anfitrión selecciona al participante y recoge su firma. En EPP hay firmas independientes de recepción y devolución. En Pañol, firmas independientes de alumno y docente.
- Cerrar solicita confirmación y registra el término. Ya no permite nuevos registros ni firmas. Las observaciones pueden completarse posteriormente; quedan registradas en el historial con usuario, fecha, valores anteriores y nuevos.
- Cambiar de sesión con un borrador o firma sin guardar permite conservarlo o descartarlo. Al cerrar la pestaña, el navegador también advierte que hay cambios pendientes. Si otro anfitrión actualizó las notas, se evita sobrescribirlas silenciosamente.

## Consultas y exportación

Administración permite buscar por nombre, RUT, cargo o actividad y filtrar por plantilla, anfitrión y fecha de Chile. El detalle muestra campos del participante, datos de la actividad y firmas disponibles. Los botones de firma abren la imagen original.

CSV contiene una fila por asistencia con datos del participante, contexto de sesión, estados y horarios. No incorpora imágenes. XLSX incluye esos datos, fechas de Excel, imágenes de recepción/asistencia, devolución y docente cuando existen, y una segunda hoja con los campos de las actividades. Puede exportarse una sesión o todas las que coincidan con los filtros.

Las imágenes se validan con Pillow antes de almacenarse. Los valores introducidos por personas se exportan como texto, sin ejecutar fórmulas.

## Accesos

- Asistente: acceso público únicamente al formulario y a la comprobación mediante el identificador aleatorio de su propio envío.
- Anfitrión: solo sus sesiones, participantes, notas, firmas y QR.
- Administrador: todas las sesiones, búsquedas, exportaciones y gestión de usuarios.
- Salir elimina la sesión de acceso. Una cuenta desactivada pierde acceso al siguiente pedido.
- Cambiar la contraseña propia: Mi cuenta.
- Recuperación desde el servidor:

```powershell
.\.venv\Scripts\python.exe manage.py recuperar_usuario --correo usuario@ejemplo.cl
```

Solicita y confirma la nueva contraseña sin mostrarla en la consola.

## Pruebas

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test asistencia --noinput
node tests_frontend.cjs
```

Node solo es necesario para las pruebas de lógica de JavaScript, no para ejecutar la aplicación. Las pruebas Django crean una base aparte; no escriben en `asistencia.db`.

Casos cubiertos: diez plantillas, RUT y duplicados, fechas Chile, CSRF, acceso por rol y propietario, alta de usuarios, login/logout, configuración inicial, registro idempotente, notas con historial/conflictos, imágenes inválidas o vacías, firmas de EPP y docente, bloqueo tras el cierre, QR local y exportaciones con imágenes.

Pruebas físicas pendientes para la entrega: dos personas desde celulares distintos en una misma sesión abierta; recepción y devolución con el lápiz de la tablet; comprobar el Excel descargado en la versión de Microsoft Excel utilizada por el cliente. Se verificó la estructura del XLSX con openpyxl, pero eso no sustituye comprobar la presentación en el Excel del cliente.

## Configuración y respaldos

Los respaldos se guardan junto a `asistencia.db` con fecha y hora en su nombre. Para restaurar uno, detén el servidor y conserva primero una copia de la base actual antes de reemplazarla.

Variables opcionales: `DJANGO_DATABASE_PATH`, `DJANGO_ALLOWED_HOSTS` (separadas por comas), `DJANGO_SECRET_KEY` y `DJANGO_DEBUG` (`1` para desarrollo, `0` para desactivarlo). El iniciador configura las IP locales sin usar un comodín en ALLOWED_HOSTS. QR y exportación funcionan sin CDN. El servidor `runserver` es para desarrollo y demostraciones; un despliegue definitivo requiere su configuración de producción.
