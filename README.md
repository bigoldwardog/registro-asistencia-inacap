# Sistema de registro de asistencia

Aplicación web Django para anfitriones, asistentes y administración. Los asistentes se registran mediante un QR y firman desde su propio dispositivo. Los registros de cada actividad se pueden consultar y exportar. Las capturas de la interfaz están en [la galería](docs/capturas/GALERIA.html).

La galería conserva las capturas de la primera versión y muestra la interfaz actual con Roboto, el logo de INACAP y las vistas de sesiones en curso y búsqueda. La [demo interactiva](docs/propuesta-asistencia/index.html) usa datos ficticios e incluye la propuesta de roles y permisos.

## Primer uso en este computador

1. Desde la carpeta del proyecto ejecuta `./INICIAR_LOCAL.ps1` en PowerShell.
2. En el computador del servidor abre http://127.0.0.1:8000/configuracion-inicial/ y crea tu cuenta administradora. No existe una contraseña predeterminada. Este formulario solo funciona desde el servidor y deja de estar disponible al crear la primera cuenta.
3. El administrador puede abrir el panel del anfitrión y crear actividades.
4. Abre el panel mediante la IP de la red que muestra el iniciador y accede con tu cuenta. Genera el QR y descarga el afiche PDF desde esa dirección para que los celulares de la misma red puedan abrir el formulario.

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
- Si la plantilla solicita RUT, el formulario valida el dígito verificador y aplica el formato con puntos y guion. El asistente aparece como pendiente de firma hasta que confirma su firma desde su dispositivo.
- En EPP, el asistente firma la recepción y luego puede volver a abrir el formulario en el mismo navegador para firmar la devolución mientras la sesión siga abierta. En Pañol, el alumno firma en su dispositivo y el docente agrega su firma por separado en el panel.
- El anfitrión usa **Gestionar sesión** para consultar el QR y descargar el afiche PDF, **Lista actual** para revisar participantes y exportar, y **Desarrollo** para completar los campos que correspondan a la plantilla.
- Cerrar solicita confirmación y registra el término. Ya no permite nuevos registros ni firmas. Las observaciones pueden completarse posteriormente; quedan registradas en el historial con usuario, fecha, valores anteriores y nuevos.
- Cambiar de sesión con un borrador o firma sin guardar permite conservarlo o descartarlo. Al cerrar la pestaña, el navegador también advierte que hay cambios pendientes. Si otro anfitrión actualizó las notas, se evita sobrescribirlas silenciosamente.

## Consultas y exportación

Administración permite buscar por nombre, RUT, cargo o actividad y filtrar por plantilla, anfitrión y fecha de Chile. El detalle muestra campos del participante, datos de la actividad y firmas disponibles. Los botones de firma abren la imagen original.

CSV contiene una fila por asistencia con datos del participante, contexto de sesión, estados y horarios. No incorpora imágenes. XLSX incluye esos datos, fechas de Excel, imágenes de recepción/asistencia, devolución y docente cuando existen, y una segunda hoja con los campos de las actividades. Desde Administración se puede exportar una sesión o todas las que coincidan con los filtros. El anfitrión puede exportar sus propias sesiones desde **Lista actual**.

Las imágenes se validan con Pillow antes de almacenarse. Los valores introducidos por personas se exportan como texto, sin ejecutar fórmulas.

## Accesos

- Asistente: acceso público únicamente al formulario y a la recuperación y firma de su propio registro mediante el identificador del envío.
- Anfitrión: solo sus sesiones, participantes, notas, firmas y QR.
- Administrador: todas las sesiones, búsquedas y exportaciones.
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

Casos cubiertos: diez plantillas, RUT y duplicados, fechas Chile, CSRF, acceso por rol y propietario, login/logout, configuración inicial, registro idempotente, notas con historial/conflictos, imágenes inválidas o vacías, firmas de EPP y docente, bloqueo tras el cierre, QR local y exportaciones con imágenes.

Pruebas físicas pendientes para la entrega: dos personas desde celulares distintos en una misma sesión abierta; firma de recepción y devolución de EPP desde el navegador del asistente; comprobar el Excel descargado en la versión de Microsoft Excel utilizada por el cliente. Se verificó la estructura del XLSX con openpyxl, pero eso no sustituye comprobar la presentación en el Excel del cliente.

## Configuración y respaldos

Los respaldos se guardan junto a `asistencia.db` con fecha y hora en su nombre. Para restaurar uno, detén el servidor y conserva primero una copia de la base actual antes de reemplazarla.

Variables opcionales: `DJANGO_DATABASE_PATH`, `DJANGO_ALLOWED_HOSTS` (separadas por comas), `DJANGO_SECRET_KEY` y `DJANGO_DEBUG` (`1` para desarrollo, `0` para desactivarlo). El iniciador configura las IP locales sin usar un comodín en ALLOWED_HOSTS. QR y exportación funcionan sin CDN. El servidor `runserver` es para desarrollo y demostraciones; un despliegue definitivo requiere su configuración de producción.
