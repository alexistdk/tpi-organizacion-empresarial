"""
db.py - Capa de acceso a datos (SQLite)
=======================================================================
Bot de Telegram para gestión de vacaciones de RRHH (UTN - TPI).

Esta capa encapsula TODO el acceso a la base de datos SQLite usando
únicamente el módulo `sqlite3` de la biblioteca estándar.

Convenciones del contrato (NO cambiar las firmas, otras etapas dependen):
- Las fechas se manejan como strings en formato ISO 'YYYY-MM-DD'.
- Los estados válidos son: 'APROBADA', 'PENDIENTE_APROBACION', 'RECHAZADA'.
- La base de datos por defecto es 'vacaciones.db' en la raíz del repo.
"""

import sqlite3
import os
from pathlib import Path

# Ruta por defecto de la base de datos (en la raíz del repositorio).
DB_PATH_DEFAULT = "vacaciones.db"

# Rutas a los scripts SQL (schema y seed) ubicados en la carpeta data/.
# Se calculan en forma absoluta a partir de la ubicación de este archivo.
_SCHEMA = Path(__file__).resolve().parent.parent / "data" / "schema.sql"
_SEED = Path(__file__).resolve().parent.parent / "data" / "seed.sql"


def get_conn(db_path: str = DB_PATH_DEFAULT) -> sqlite3.Connection:
    """
    Abre y devuelve una conexión a la base de datos SQLite.

    - row_factory = sqlite3.Row -> permite acceder a las columnas por nombre
      (ej: fila['nombre']) y convertir filas a dict fácilmente.
    - PRAGMA foreign_keys = ON -> activa la verificación de claves foráneas
      (por defecto SQLite las trae desactivadas).
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: str = DB_PATH_DEFAULT) -> None:
    """
    Inicializa la base de datos de forma idempotente.

    1. Ejecuta SIEMPRE schema.sql (usa CREATE TABLE IF NOT EXISTS, por lo
       que es seguro correrlo múltiples veces).
    2. Si la tabla 'empleados' está vacía, ejecuta seed.sql para cargar
       los datos de prueba.

    Al ser idempotente, se puede llamar en cada arranque del bot sin riesgo.
    """
    # Leemos los scripts SQL desde disco.
    schema_sql = _SCHEMA.read_text(encoding="utf-8")
    seed_sql = _SEED.read_text(encoding="utf-8")

    with get_conn(db_path) as conn:
        # 1) Creamos las tablas si no existen.
        conn.executescript(schema_sql)

        # 2) Verificamos si ya hay empleados cargados.
        cur = conn.execute("SELECT COUNT(*) AS total FROM empleados;")
        total = cur.fetchone()["total"]

        # Solo sembramos datos si la tabla está vacía (primera vez).
        if total == 0:
            conn.executescript(seed_sql)


def legajo_existe(legajo: str, db_path: str = DB_PATH_DEFAULT) -> bool:
    """
    Tarea de servicio (BPMN): verificar existencia de empleado.

    Devuelve True si existe un empleado con el legajo dado, False si no.
    """
    with get_conn(db_path) as conn:
        cur = conn.execute(
            "SELECT 1 FROM empleados WHERE legajo = ? LIMIT 1;",
            (legajo,),
        )
        return cur.fetchone() is not None


def consultar_empleado(legajo: str, db_path: str = DB_PATH_DEFAULT) -> dict | None:
    """
    Tarea de servicio (BPMN): consultar datos del empleado.

    Devuelve un dict con {'legajo','nombre','saldo_dias','jefe_nombre'}
    o None si el legajo no existe.
    """
    with get_conn(db_path) as conn:
        cur = conn.execute(
            "SELECT legajo, nombre, saldo_dias, jefe_nombre "
            "FROM empleados WHERE legajo = ?;",
            (legajo,),
        )
        fila = cur.fetchone()
        # Convertimos la fila (sqlite3.Row) a dict, o devolvemos None.
        return dict(fila) if fila is not None else None


def consultar_saldo(legajo: str, db_path: str = DB_PATH_DEFAULT) -> int | None:
    """
    Tarea de servicio (BPMN): consultar saldo de días de vacaciones.

    Devuelve la cantidad de días disponibles (int) o None si no existe
    el empleado.
    """
    with get_conn(db_path) as conn:
        cur = conn.execute(
            "SELECT saldo_dias FROM empleados WHERE legajo = ?;",
            (legajo,),
        )
        fila = cur.fetchone()
        return fila["saldo_dias"] if fila is not None else None


def hay_solapamiento(
    legajo: str,
    fecha_inicio: str,
    fecha_fin: str,
    db_path: str = DB_PATH_DEFAULT,
) -> bool:
    """
    Tarea de servicio (BPMN): verificar solapamiento de fechas.

    Devuelve True si el rango [fecha_inicio, fecha_fin] se solapa con
    alguna solicitud existente del mismo legajo cuyo estado sea
    'APROBADA' o 'PENDIENTE_APROBACION'.

    Condición de solapamiento (dos rangos se solapan salvo que uno
    termine antes de que empiece el otro):
        NOT (fecha_fin < f.fecha_inicio OR fecha_inicio > f.fecha_fin)

    Las fechas se comparan como strings ISO 'YYYY-MM-DD', cuyo orden
    lexicográfico coincide con el orden cronológico.
    """
    with get_conn(db_path) as conn:
        cur = conn.execute(
            """
            SELECT 1
            FROM solicitudes AS f
            WHERE f.legajo = ?
              AND f.estado IN ('APROBADA', 'PENDIENTE_APROBACION')
              AND NOT (? < f.fecha_inicio OR ? > f.fecha_fin)
            LIMIT 1;
            """,
            (legajo, fecha_fin, fecha_inicio),
        )
        return cur.fetchone() is not None


def registrar_solicitud(
    legajo: str,
    fecha_inicio: str,
    fecha_fin: str,
    dias: int,
    estado: str,
    db_path: str = DB_PATH_DEFAULT,
) -> int:
    """
    Tarea de servicio (BPMN): registrar una solicitud de vacaciones.

    Inserta una fila en 'solicitudes' y devuelve el id generado.

    Si el estado es 'APROBADA', descuenta `dias` del saldo del empleado
    dentro de la MISMA transacción, garantizando atomicidad: o se inserta
    la solicitud y se actualiza el saldo, o no ocurre nada.
    """
    with get_conn(db_path) as conn:
        # Insertamos la solicitud.
        cur = conn.execute(
            """
            INSERT INTO solicitudes (legajo, fecha_inicio, fecha_fin, dias, estado)
            VALUES (?, ?, ?, ?, ?);
            """,
            (legajo, fecha_inicio, fecha_fin, dias, estado),
        )
        nuevo_id = cur.lastrowid

        # Si queda aprobada, descontamos los días del saldo en la misma
        # transacción (el bloque 'with' hace commit al salir sin error,
        # o rollback automático si se produce una excepción).
        if estado == "APROBADA":
            conn.execute(
                "UPDATE empleados SET saldo_dias = saldo_dias - ? WHERE legajo = ?;",
                (dias, legajo),
            )

        return nuevo_id


def listar_solicitudes(legajo: str, db_path: str = DB_PATH_DEFAULT) -> list[dict]:
    """
    Tarea de servicio (BPMN): listar solicitudes de un empleado.

    Devuelve una lista de dicts con todas las solicitudes del legajo,
    ordenadas de la más reciente a la más antigua.
    """
    with get_conn(db_path) as conn:
        cur = conn.execute(
            """
            SELECT id, legajo, fecha_inicio, fecha_fin, dias, estado, creado_en
            FROM solicitudes
            WHERE legajo = ?
            ORDER BY id DESC;
            """,
            (legajo,),
        )
        # Convertimos cada fila (sqlite3.Row) a dict.
        return [dict(fila) for fila in cur.fetchall()]
