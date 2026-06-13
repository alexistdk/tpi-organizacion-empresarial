-- =====================================================================
-- seed.sql - Datos iniciales de prueba (DML)
-- Carga 4 empleados con saldos de días distintos y distintos jefes.
-- Se usa INSERT OR IGNORE para que la carga sea idempotente: si el
-- legajo ya existe (clave primaria), simplemente no se vuelve a insertar.
-- =====================================================================

INSERT OR IGNORE INTO empleados (legajo, nombre, saldo_dias, jefe_nombre) VALUES
    ('1001', 'Ana García',    14, 'Carlos Ruiz'),
    ('1002', 'Juan Pérez',     8, 'Carlos Ruiz'),
    ('1003', 'María López',   25, 'Laura Gómez'),
    ('1004', 'Pedro Sánchez',  3, 'Laura Gómez');
