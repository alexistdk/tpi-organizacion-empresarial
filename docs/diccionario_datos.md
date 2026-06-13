# Diccionario de datos

Bot de Telegram para la gestión de vacaciones de RRHH (UTN — TPI Organización
Empresarial). La persistencia es 100% **SQLite**. El esquema completo está en
`data/schema.sql` y los datos iniciales en `data/seed.sql`.

El modelo tiene dos tablas: `empleados` (el personal) y `solicitudes` (cada
pedido de vacaciones). La relación es **uno a muchos**: un empleado puede tener
muchas solicitudes; cada solicitud pertenece a un único empleado.

---

## Tabla `empleados`

Representa al personal de la empresa. El `legajo` es el identificador único de
cada empleado y la clave primaria.

| Campo         | Tipo    | Restricciones    | Descripción                                                        |
|---------------|---------|------------------|--------------------------------------------------------------------|
| `legajo`      | TEXT    | PRIMARY KEY      | Identificador único del empleado (numérico almacenado como texto). |
| `nombre`      | TEXT    | NOT NULL         | Nombre y apellido del empleado.                                    |
| `saldo_dias`  | INTEGER | NOT NULL         | Cantidad de días de vacaciones disponibles. Se descuenta al aprobar una solicitud. |
| `jefe_nombre` | TEXT    | (puede ser NULL) | Nombre del jefe aprobador, usado cuando la solicitud requiere aprobación. |

---

## Tabla `solicitudes`

Representa cada pedido de vacaciones realizado a través del bot. Cada fila
referencia a un empleado mediante la clave foránea `legajo`.

| Campo          | Tipo    | Restricciones                                              | Descripción                                                                 |
|----------------|---------|-----------------------------------------------------------|-----------------------------------------------------------------------------|
| `id`           | INTEGER | PRIMARY KEY AUTOINCREMENT                                  | Identificador único autoincremental de la solicitud.                        |
| `legajo`       | TEXT    | NOT NULL, FOREIGN KEY → `empleados(legajo)`               | Empleado que realiza la solicitud.                                          |
| `fecha_inicio` | TEXT    | NOT NULL                                                   | Primer día de las vacaciones, en formato ISO `YYYY-MM-DD`.                  |
| `fecha_fin`    | TEXT    | NOT NULL                                                   | Último día de las vacaciones, en formato ISO `YYYY-MM-DD`.                  |
| `dias`         | INTEGER | NOT NULL                                                   | Cantidad de días solicitados (inclusive ambos extremos).                   |
| `estado`       | TEXT    | NOT NULL, CHECK(estado IN ('APROBADA','PENDIENTE_APROBACION','RECHAZADA')) | Estado de la solicitud (ver valores posibles abajo).        |
| `creado_en`    | TEXT    | NOT NULL, DEFAULT `datetime('now','localtime')`           | Fecha y hora de creación de la solicitud (se completa automáticamente).    |

### Valores posibles del campo `estado`

El campo `estado` está restringido por un `CHECK` a tres valores:

| Valor                  | Significado                                                                                 |
|------------------------|--------------------------------------------------------------------------------------------|
| `APROBADA`             | Solicitud aprobada automáticamente (≤ 10 días y con saldo suficiente). Descuenta el saldo. |
| `PENDIENTE_APROBACION` | Solicitud que supera el umbral de 10 días y queda a la espera de la aprobación del jefe.    |
| `RECHAZADA`            | Solicitud rechazada (p. ej. por saldo insuficiente).                                        |

---

## Datos semilla (`seed.sql`)

Los cuatro empleados de prueba cargados al inicializar la base por primera vez
(la carga es idempotente: usa `INSERT OR IGNORE`).

| Legajo | Nombre        | Saldo de días | Jefe        |
|--------|---------------|---------------|-------------|
| 1001   | Ana García    | 14            | Carlos Ruiz |
| 1002   | Juan Pérez    | 8             | Carlos Ruiz |
| 1003   | María López   | 25            | Laura Gómez |
| 1004   | Pedro Sánchez | 3             | Laura Gómez |

---

## Relaciones

- **`empleados` 1 — N `solicitudes`**: un empleado puede generar muchas
  solicitudes a lo largo del tiempo; cada solicitud pertenece a exactamente un
  empleado. La integridad se garantiza con la clave foránea
  `solicitudes.legajo → empleados.legajo` y con `PRAGMA foreign_keys = ON`
  activado en cada conexión (ver `bot/db.py`).
- Al **aprobar** una solicitud (`estado = 'APROBADA'`), la inserción de la fila
  en `solicitudes` y el descuento de `saldo_dias` en `empleados` se ejecutan en
  la **misma transacción**, garantizando atomicidad.
