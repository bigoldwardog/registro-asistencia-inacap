
PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

-- 1. Usuarios de prueba
INSERT OR IGNORE INTO usuarios
    (nombre, correo, password_hash, rol)
VALUES
    ('Juan Perez', 'juan.prueba@example.com', 'HASH_SOLO_PARA_PRUEBAS', 'ANFITRION'),
    ('Administrador de prueba', 'admin.prueba@example.com', 'HASH_SOLO_PARA_PRUEBAS', 'ADMINISTRADOR');

-- 2. Plantilla de sesion
INSERT OR IGNORE INTO plantillas_sesion
    (nombre, descripcion)
VALUES
    ('Seminario de Informatica', 'Plantilla de prueba para seminarios');

-- 3. Campos de la plantilla
INSERT OR IGNORE INTO campos_plantilla
    (plantilla_id, nombre, etiqueta, tipo, obligatorio, orden)
SELECT id, 'nombre', 'Nombre completo', 'texto', 1, 1
FROM plantillas_sesion
WHERE nombre = 'Seminario de Informatica';

INSERT OR IGNORE INTO campos_plantilla
    (plantilla_id, nombre, etiqueta, tipo, obligatorio, orden)
SELECT id, 'rut', 'RUT', 'texto', 1, 2
FROM plantillas_sesion
WHERE nombre = 'Seminario de Informatica';

INSERT OR IGNORE INTO campos_plantilla
    (plantilla_id, nombre, etiqueta, tipo, obligatorio, orden)
SELECT id, 'telefono', 'Telefono', 'texto', 1, 3
FROM plantillas_sesion
WHERE nombre = 'Seminario de Informatica';

INSERT OR IGNORE INTO campos_plantilla
    (plantilla_id, nombre, etiqueta, tipo, obligatorio, orden)
SELECT id, 'correo', 'Correo electronico', 'email', 1, 4
FROM plantillas_sesion
WHERE nombre = 'Seminario de Informatica';

-- 4. Sesion de prueba
INSERT OR IGNORE INTO sesiones
    (plantilla_id, anfitrion_id, nombre, fecha_inicio,
     estado, token_qr, campos_definicion_json, campos_valores_json)
SELECT
    p.id,
    u.id,
    'Seminario de Informatica - Prueba',
    '2026-10-14 10:00:00',
    'ABIERTA',
    'token-prueba-seminario-001',
    '{"nombre":"texto","rut":"texto","telefono":"texto","correo":"email"}',
    '{}'
FROM plantillas_sesion p
JOIN usuarios u ON u.correo = 'juan.prueba@example.com'
WHERE p.nombre = 'Seminario de Informatica';

-- 5. Asistentes ficticios
INSERT OR IGNORE INTO asistentes
    (rut, nombre, telefono, correo)
VALUES
    ('11.111.111-1', 'Maria Gonzalez', '+56911111111', 'maria.prueba@example.com'),
    ('22.222.222-2', 'Pedro Soto', '+56922222222', 'pedro.prueba@example.com');

-- 6. Asistencias de prueba
INSERT OR IGNORE INTO asistencias
    (sesion_id, asistente_id, nombre_registrado, rut_registrado,
     telefono_registrado, correo_registrado, estado)
SELECT
    s.id,
    a.id,
    a.nombre,
    a.rut,
    a.telefono,
    a.correo,
    'PENDIENTE_FIRMA'
FROM sesiones s
JOIN asistentes a
    ON a.rut IN ('11.111.111-1', '22.222.222-2')
WHERE s.token_qr = 'token-prueba-seminario-001';

-- 7. Auditoria de prueba, sin duplicar el evento
INSERT INTO auditoria
    (usuario_id, accion, entidad, entidad_id, datos_nuevos_json)
SELECT
    u.id,
    'CREACION_DATOS_PRUEBA',
    'sesiones',
    s.id,
    '{"origen":"seed.sql"}'
FROM usuarios u
JOIN sesiones s
    ON s.token_qr = 'token-prueba-seminario-001'
WHERE u.correo = 'juan.prueba@example.com'
AND NOT EXISTS (
    SELECT 1
    FROM auditoria au
    WHERE au.accion = 'CREACION_DATOS_PRUEBA'
      AND au.entidad = 'sesiones'
      AND au.entidad_id = s.id
);

COMMIT;
