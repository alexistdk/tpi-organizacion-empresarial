-- =====================================================================
-- schema.sql - Definición de la estructura de la base de datos (DDL)
-- Bot de Telegram para gestión de vacaciones de RRHH (UTN - TPI)
-- Persistencia 100% en SQLite. Se usa CREATE TABLE IF NOT EXISTS para
-- que la inicialización sea idempotente (se puede correr muchas veces).
-- =====================================================================

-- Tabla de empleados: representa al personal de la empresa.
-- 'legajo' es la clave primaria (identificador único del empleado).
-- 'saldo_dias' es la cantidad de días de vacaciones disponibles.
-- 'jefe_nombre' identifica al aprobador de las solicitudes.
CREATE TABLE IF NOT EXISTS empleados (
    legajo      TEXT PRIMARY KEY,
    nombre      TEXT NOT NULL,
    saldo_dias  INTEGER NOT NULL,
    jefe_nombre TEXT
);

-- Tabla de solicitudes: representa cada pedido de vacaciones.
-- Cada solicitud referencia a un empleado (clave foránea 'legajo').
-- 'estado' está restringido por CHECK a los 3 estados válidos del flujo.
-- 'creado_en' se completa automáticamente con la fecha/hora local.
CREATE TABLE IF NOT EXISTS solicitudes (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    legajo       TEXT NOT NULL REFERENCES empleados(legajo),
    fecha_inicio TEXT NOT NULL,
    fecha_fin    TEXT NOT NULL,
    dias         INTEGER NOT NULL,
    estado       TEXT NOT NULL CHECK(estado IN ('APROBADA','PENDIENTE_APROBACION','RECHAZADA')),
    creado_en    TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
