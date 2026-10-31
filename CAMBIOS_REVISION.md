# Correcciones de la revisión integral

Se implementaron los cambios del informe de revisión y se conservaron los colores, fuentes y navegación por pestañas.

- RUT canónico y verificación del dígito antes de registrar; detección de equivalencias con perfiles anteriores, sin fusionar ni borrar su historia.
- Fechas de Chile en consultas, filtros y exportaciones. Excel recibe valores de fecha, no solo cadenas de texto.
- Búsqueda por persona, RUT, cargo y actividad; detalle por plantilla con campos de asistente, observaciones y ambas firmas de EPP.
- Visualización autorizada de imágenes de firma en los paneles de anfitrión y administración.
- CSV detallado de asistentes y XLSX con imágenes, horarios, estados y hoja separada de datos de la actividad.
- Validación completa de PNG, tamaño y contenido no vacío antes de marcar una asistencia como firmada.
- Identificador de envío guardado antes de transmitir para recuperar respuestas perdidas y evitar duplicados tras recargar.
- Advertencia de borradores al cambiar de sesión y al abandonar la página. Cambiar de pestaña conserva los formularios.
- Historial con autor, fecha y valores anteriores/nuevos; control de modificaciones simultáneas de observaciones.
- Formularios de asistentes específicos para las diez plantillas; en Pañol, firma adicional del docente.
- Login/logout reales, cuentas administradoras y de anfitrión, acceso por propietario, gestión de usuarios y cambio de contraseña.
- Primer administrador creado por el usuario desde el servidor, sin contraseña predeterminada y sin configuración inicial pública en la red.
- Protección CSRF en las operaciones de escritura, incluidas las del formulario público.
- QR generado por Django y Excel generado en el servidor: sin bibliotecas externas de CDN.
- Desactivación de la plantilla y las cuentas de ejemplo, enlace vacío oculto y descripción de EPP actualizada.
- Perfil opcional recordado, confirmación con nombre y correo parcialmente ocultos, corrección y borrado local de datos.
- Instalador, dependencias fijadas, preparación repetible del esquema, recuperación de usuario y documentación de pruebas.

## Verificación

Pasaron 15 pruebas Django y las pruebas de lógica JavaScript de recuperación de envíos y conservación/descarte de borradores. Se verificó además una actualización repetida sobre una copia de la base real, conservando las cantidades y las relaciones existentes.

En un servidor separado se verificaron acceso, fechas locales, detalle con cargo, recuperación visual de la firma, QR local y descarga real del XLSX. El archivo descargado se abrió con openpyxl: contiene las hojas Asistencias y Actividades, la firma incrustada y fechas de Excel. Las sesiones y cuentas de ese servidor de prueba no se copian al proyecto real.

La comprobación física con dos celulares y el lápiz de la tablet sigue pendiente. También debe comprobarse la presentación del XLSX en la versión de Microsoft Excel del cliente. Las pruebas automáticas no sustituyen esas comprobaciones. El cuadro de borradores tiene pruebas de lógica; el navegador automatizado presentó un bloqueo de interacción durante su verificación, por lo que conservar/descartar también debe incluirse en la comprobación manual final.

## Primer acceso después de actualizar

Reinicia con `./INICIAR_LOCAL.ps1`. Desde el computador del servidor abre http://127.0.0.1:8000/configuracion-inicial/ y crea tu cuenta administradora. Luego crea anfitriones desde Usuarios o usa tu cuenta administradora para abrir el panel del anfitrión. Para escanear desde celulares, abre el panel con la IP local que muestra el iniciador y entra con esa cuenta.

Las instrucciones completas están en [README.md](README.md).
