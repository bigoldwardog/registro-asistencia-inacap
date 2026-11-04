# Pruebas locales

Las instrucciones actualizadas de instalación, primer acceso, pruebas y exportación están en [README.md](README.md).

Para iniciar desde PowerShell:

    .\INICIAR_LOCAL.ps1

En el primer uso crea la cuenta administradora desde el computador del servidor:

    http://127.0.0.1:8000/configuracion-inicial/

Después abre el panel mediante la IP de tu conexión para generar un QR accesible desde el celular. El celular y el computador deben estar en la misma red, con comunicación entre dispositivos permitida. Mantén el servidor ejecutándose.

Pruebas automáticas:

    .\.venv\Scripts\python.exe manage.py test asistencia --noinput
    node tests_frontend.cjs

Prueba física pendiente: dos personas desde celulares distintos en la misma sesión abierta, y firma con el lápiz de la tablet. La exportación XLSX incorpora las imágenes; CSV contiene los datos tabulares.
