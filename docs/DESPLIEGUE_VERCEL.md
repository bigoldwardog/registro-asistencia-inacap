# Demostración en Vercel

Preparación del 18 de noviembre de 2026. Destino: demostración académica pública y temporal, separada del hosting definitivo del cliente. La base Neon production ya está inicializada y auditada; el recorrido de firmas y exportaciones se probó en una rama aislada. Vercel aún no está desplegado.

## Recursos necesarios

1. Crear un proyecto Vercel importando el repositorio personal del proyecto. Usar el preset Django; `vercel.json` declara el framework y la comprobación de configuración.
2. Base PostgreSQL de demostración ya creada en Neon (proyecto still-leaf-50094774, rama production). Obtener la conexión desde el panel del proveedor, con TLS. No copiar contraseñas ni cadenas de conexión al chat o al repositorio.
3. Confirmar el dominio estable asignado por Vercel. Ese dominio será la base de los QR impresos.

Solo hacen falta los enlaces de los paneles de ambos proyectos para coordinar la configuración; las credenciales se introducen directamente en el entorno correspondiente.

## Variables

Configurar antes del primer despliegue:

| Variable | Valor |
|---|---|
| DJANGO_ENV | production |
| DJANGO_DEBUG | 0 |
| DJANGO_SECRET_KEY | Clave aleatoria privada, estable entre despliegues |
| DATABASE_URL | Conexión PostgreSQL del proveedor con TLS |
| PUBLIC_SITE_URL | https://dominio-estable.vercel.app |
| DJANGO_ALLOWED_HOSTS | dominio-estable.vercel.app |
| DJANGO_CSRF_TRUSTED_ORIGINS | https://dominio-estable.vercel.app |

Generar la clave de Django localmente con el módulo `secrets` de Python y guardarla directamente en Vercel. No publicarla. Los archivos `.env` no se cargan automáticamente y están excluidos de Git. Usar base y variables separadas para previews; no aplicar esquemas distintos a la misma base desde ramas de prueba.

## Inicialización privada

Desde el entorno virtual local, establecer las mismas variables de producción y ejecutar, con una conexión que permita migraciones:

```powershell
.\.venv\Scripts\python.exe manage.py preparar_sistema
.\.venv\Scripts\python.exe manage.py auditar_integridad
```

El comando crea las tablas originales y de Django, catálogos y caché compartida. Se puede repetir sin borrar cuentas ni firmas. No usar `seed.sql`. Las migraciones se ejecutan como paso explícito, nunca al importar la aplicación ni durante solicitudes o builds concurrentes. Guardar un respaldo antes de actualizar una base con datos.

Consultar los identificadores del catálogo desde Django y crear la primera cuenta con su sede y área reales:

```powershell
.\.venv\Scripts\python.exe manage.py shell -c "from asistencia.models import SedeAcademica, AreaAcademica; print(list(SedeAcademica.objects.values_list('id','nombre'))); print(list(AreaAcademica.objects.values_list('id','nombre')))"
.\.venv\Scripts\python.exe manage.py crear_superusuario_inicial --nombre "Nombre Apellido" --correo "admin@ejemplo.cl" --sede-id 1 --area-id 1
```

Sustituir los ejemplos por datos elegidos. El comando pide la contraseña sin mostrarla y rechaza ejecutarse si ya existe alguna cuenta. No dejar `INITIAL_ADMIN_PASSWORD` en Vercel. La configuración inicial por navegador no está habilitada en hosting.

## Despliegue y comprobación

Python está fijado a 3.13. El adaptador nativo Django detecta la aplicación y gestiona los archivos estáticos; no hace falta una carpeta API ni usar runserver. Las firmas y sesiones se guardan en PostgreSQL, no en el disco efímero de una función. La caché de autenticación utiliza la tabla compartida.

Tras desplegar, verificar con dos teléfonos y redes diferentes:

- Iniciar sesión y comprobar restricciones de roles, sedes y áreas.
- Programar actividad, descargar afiche y escanear QR: antes del inicio no admite asistentes.
- Iniciar con anfitrión efectivo y firma; registrar y firmar un asistente desde otro teléfono.
- Comprobar persistencia tras redespliegue, QR estable y exportaciones PDF/XLSX con firma del anfitrión primero.
- Cerrar actividad y comprobar rechazo de nuevos registros. Cambiar contraseña y comprobar revocación de otras sesiones.

Vercel limita las respuestas de sus funciones: se aplica un límite preventivo de 4 MB a exportaciones. Si se supera, exportar por actividad; no se eliminan datos. Los documentos grandes necesitarán almacenamiento y descarga externos en una ampliación futura.

La configuración aislada también se prueba con una URL ficticia. Adicionalmente se completó una verificación con Neon real: programación, sustitución de anfitrión, firma inicial, firma de asistente, PDF, XLSX, cierre y restricciones, login y caché compartida. Se inició Django localmente contra Neon y se comprobaron respuestas HTTP. Esto no sustituye el recorrido desde teléfonos en el dominio público definitivo, aún pendiente.

Fuentes: [Django en Vercel](https://vercel.com/docs/frameworks/full-stack/django), [runtime Python](https://vercel.com/docs/functions/runtimes/python), [SQLite en Vercel](https://vercel.com/kb/guide/is-sqlite-supported-in-vercel).

## Conexión local de Neon

La herramienta oficial Neon 9.6.0 quedó autenticada y vinculada a production. `.env.local` conserva las conexiones agrupada y directa y la clave privada Django, excluidas de Git. Se usa psycopg 3, conexiones sin persistencia entre solicitudes, comprobación de salud y cursores del servidor deshabilitados para el pooler. La conexión directa se utilizó para inicializar; la agrupada fue comprobada con login y caché. No se agregó autenticación ni servicios de IA a la aplicación.

El alta privada del superusuario sigue pendiente de elegir sus datos. La base principal contiene cero cuentas, actividades, asistentes, asistencias y firmas. No ejecutar de nuevo una inicialización si solo se necesita arrancar la web; las futuras actualizaciones del esquema se preparan explícitamente.
