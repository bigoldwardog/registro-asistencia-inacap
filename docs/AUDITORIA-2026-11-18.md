# Revisión de persistencia y preparación de hosting

## Incoherencias corregidas

- Vercel no puede conservar la base SQLite local entre ejecuciones: PostgreSQL es obligatorio en hosting; SQLite se conserva para desarrollo.
- Las tablas originales no eran creadas por las migraciones de modelos no gestionados: se incorpora inicialización explícita y un esquema PostgreSQL congelado para instalaciones nuevas.
- Relaciones gestionadas carecían de restricciones físicas hacia tablas originales: la migración 0006 agrega claves foráneas. Correos únicos sin distinguir mayúsculas.
- La ausencia de perfil podía conceder capacidades heredadas: ahora se deniega acceso.
- Cambios de contraseña no revocaban otras sesiones: las credenciales de sesión se vinculan al hash vigente.
- Bloqueo por IP perjudicaba a una clase tras una misma red: el límite de intentos se vincula al correo normalizado y usa caché compartida en hosting.
- La configuración inicial pública podía quedar expuesta mediante el proxy: en hosting se crea la cuenta inicial por comando privado.
- La imagen de firma aún tenía una ruta de consulta: retirada; imágenes solo en exportación autorizada.
- El anfitrión podía registrarse otra vez como asistente: se impide duplicar su RUT en la actividad iniciada.
- El bloqueo de filas con una unión opcional podía fallar en PostgreSQL: se limita a la tabla de sesión.
- QR dependiente del dominio de la solicitud: se admite una URL pública canónica estable. Exportaciones sobredimensionadas devuelven un aviso explícito.
- Se incorpora auditoría de referencias, estados, fechas y consistencia de firmas sin modificar registros.

## Validación y límites

Las pruebas Django cubren persistencia, permisos, programación, firmas, exportaciones y preparación repetible de bases nuevas. Las pruebas adicionales de hosting comprueban rechazo de configuraciones incompletas, selección PostgreSQL con TLS, bootstrap privado y estáticos. PostgreSQL real ya se verificó en Neon: inicialización, auditoría, programación, firmas, PDF/XLSX y autenticación con pooler y caché compartida. Las pruebas funcionales se ejecutaron en una rama temporal y se revirtieron. Vercel y el recorrido público desde teléfonos siguen pendientes.

La revisión no implica ausencia absoluta de errores. Se requiere recorrido con teléfonos reales y revisar la presentación de documentos en el software del cliente. Subsesiones, adaptación de EPP/pañol y equivalencia visual exacta de formatos Word continúan pendientes; no se presentan como implementados.
