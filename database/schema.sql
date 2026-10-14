PRAGMA foreign_keys = ON;

-- =========================================
-- 1. USUARIOS
-- Anfitriones y Administradores
-- =========================================

CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    correo TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    rol TEXT NOT NULL
        CHECK (rol IN ('ANFITRION', 'ADMINISTRADOR')),
    activo INTEGER NOT NULL DEFAULT 1
        CHECK (activo IN (0, 1)),
    fecha_creacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- =========================================
-- 2. PLANTILLAS DE SESION
-- =========================================

CREATE TABLE IF NOT EXISTS plantillas_sesion (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL UNIQUE,
    descripcion TEXT,
    activa INTEGER NOT NULL DEFAULT 1
        CHECK (activa IN (0, 1)),
    fecha_creacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- =========================================
-- 3. CAMPOS DE LAS PLANTILLAS
-- Definen los datos propios de cada Sesion
-- =========================================

CREATE TABLE IF NOT EXISTS campos_plantilla (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plantilla_id INTEGER NOT NULL,
    nombre TEXT NOT NULL,
    etiqueta TEXT NOT NULL,
    tipo TEXT NOT NULL DEFAULT 'texto'
        CHECK (
            tipo IN (
                'texto',
                'numero',
                'fecha',
                'hora',
                'email'
            )
        ),
    obligatorio INTEGER NOT NULL DEFAULT 0
        CHECK (obligatorio IN (0, 1)),
    orden INTEGER NOT NULL DEFAULT 0,

    FOREIGN KEY (plantilla_id)
        REFERENCES plantillas_sesion(id)
        ON DELETE RESTRICT,

    UNIQUE (plantilla_id, nombre)
);


-- =========================================
-- 4. SESIONES
-- =========================================

CREATE TABLE IF NOT EXISTS sesiones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    plantilla_id INTEGER NOT NULL,
    anfitrion_id INTEGER NOT NULL,

    nombre TEXT NOT NULL,
    fecha_inicio TEXT NOT NULL,
    fecha_cierre TEXT,

    estado TEXT NOT NULL DEFAULT 'ABIERTA'
        CHECK (estado IN ('ABIERTA', 'CERRADA')),

    token_qr TEXT NOT NULL UNIQUE,

    -- Copia de la definicion de campos de la
    -- plantilla al crear la Sesion.
    campos_definicion_json TEXT NOT NULL DEFAULT '{}',

    -- Valores concretos de los campos de esta Sesion.
    campos_valores_json TEXT NOT NULL DEFAULT '{}',

    fecha_creacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (plantilla_id)
        REFERENCES plantillas_sesion(id)
        ON DELETE RESTRICT,

    FOREIGN KEY (anfitrion_id)
        REFERENCES usuarios(id)
        ON DELETE RESTRICT
);


-- =========================================
-- 5. ASISTENTES
-- Datos reutilizables entre Sesiones
-- =========================================

CREATE TABLE IF NOT EXISTS asistentes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rut TEXT NOT NULL UNIQUE,
    nombre TEXT NOT NULL,
    telefono TEXT NOT NULL,
    correo TEXT NOT NULL,
    fecha_creacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- =========================================
-- 6. ASISTENCIAS
-- Conservan una copia historica de los datos
-- del Asistente al momento del registro.
-- =========================================

CREATE TABLE IF NOT EXISTS asistencias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    sesion_id INTEGER NOT NULL,
    asistente_id INTEGER NOT NULL,

    nombre_registrado TEXT NOT NULL,
    rut_registrado TEXT NOT NULL,
    telefono_registrado TEXT NOT NULL,
    correo_registrado TEXT NOT NULL,

    estado TEXT NOT NULL DEFAULT 'PENDIENTE_FIRMA'
        CHECK (
            estado IN (
                'PENDIENTE_FIRMA',
                'FIRMADO',
                'ANULADO'
            )
        ),

    fecha_registro TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_firma TEXT,

    FOREIGN KEY (sesion_id)
        REFERENCES sesiones(id)
        ON DELETE RESTRICT,

    FOREIGN KEY (asistente_id)
        REFERENCES asistentes(id)
        ON DELETE RESTRICT,

    -- Un Asistente solo puede registrar
    -- una Asistencia por Sesion.
    UNIQUE (sesion_id, asistente_id)
);


-- =========================================
-- 7. FIRMAS
-- La imagen se almacena como un BLOB.
-- =========================================

CREATE TABLE IF NOT EXISTS firmas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    asistencia_id INTEGER NOT NULL UNIQUE,

    imagen BLOB NOT NULL,
    formato TEXT NOT NULL DEFAULT 'image/png',
    fecha_creacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (asistencia_id)
        REFERENCES asistencias(id)
        ON DELETE RESTRICT
);


-- =========================================
-- 8. AUDITORIA
-- Registro de acciones relevantes.
-- =========================================

CREATE TABLE IF NOT EXISTS auditoria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    usuario_id INTEGER,
    accion TEXT NOT NULL,
    entidad TEXT NOT NULL,
    entidad_id INTEGER,

    datos_anteriores_json TEXT,
    datos_nuevos_json TEXT,

    fecha TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (usuario_id)
        REFERENCES usuarios(id)
        ON DELETE RESTRICT
);


-- =========================================
-- 9. INDICES
-- Optimizan consultas habituales.
-- =========================================

CREATE INDEX IF NOT EXISTS idx_sesiones_fecha
    ON sesiones(fecha_inicio);

CREATE INDEX IF NOT EXISTS idx_sesiones_tipo
    ON sesiones(plantilla_id);

CREATE INDEX IF NOT EXISTS idx_sesiones_anfitrion
    ON sesiones(anfitrion_id);

CREATE INDEX IF NOT EXISTS idx_asistencias_sesion
    ON asistencias(sesion_id);

CREATE INDEX IF NOT EXISTS idx_asistencias_asistente
    ON asistencias(asistente_id);

CREATE INDEX IF NOT EXISTS idx_asistencias_estado
    ON asistencias(estado);

CREATE INDEX IF NOT EXISTS idx_auditoria_fecha
    ON auditoria(fecha);