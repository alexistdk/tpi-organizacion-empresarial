"""
Validadores y parsers del "camino infeliz" del bot.

Cubre la entrada de datos del usuario por Telegram: legajo y fechas. Cada
función valida un dato y, si está mal, devuelve un mensaje de error en español
orientado al REINTENTO GUIADO (le dice al usuario qué se espera y un ejemplo).

Es código PURO: sólo stdlib (datetime). No importa db.py.

Convención de retorno: tupla (ok, valor_o_mensaje)
    - Si ok es True  -> el segundo elemento es el valor normalizado (o "").
    - Si ok es False -> el segundo elemento es el mensaje de error guía.
"""

from datetime import date, datetime

# Formatos de fecha aceptados, en orden de intento.
FORMATOS_FECHA = ("%Y-%m-%d", "%d/%m/%Y")


def validar_legajo(texto: str) -> tuple[bool, str]:
    """Valida que el legajo sea numérico.

    Se permite que el usuario mande espacios alrededor (se hace strip). El
    legajo debe contener únicamente dígitos.

    Args:
        texto: lo que escribió el usuario.

    Returns:
        (True, legajo_normalizado) si es válido, o
        (False, mensaje_de_error_guía) si no lo es.
    """
    legajo = texto.strip()
    if legajo.isdigit():
        return True, legajo
    return False, "El legajo debe ser numérico, p. ej. 1001. Probá de nuevo:"


def parsear_fecha(texto: str) -> tuple[bool, object]:
    """Parsea una fecha aceptando dos formatos: 'YYYY-MM-DD' y 'DD/MM/YYYY'.

    Args:
        texto: lo que escribió el usuario.

    Returns:
        (True, date) si pudo parsear con alguno de los formatos, o
        (False, mensaje_de_error_guía) indicando el formato esperado.
    """
    valor = texto.strip()
    for formato in FORMATOS_FECHA:
        try:
            return True, datetime.strptime(valor, formato).date()
        except ValueError:
            # Probamos con el siguiente formato.
            continue
    return (
        False,
        "Fecha inválida. Usá el formato AAAA-MM-DD o DD/MM/AAAA, "
        "p. ej. 2026-07-01. Probá de nuevo:",
    )


def validar_no_pasado(fecha: date, hoy: date) -> tuple[bool, str]:
    """Valida que la fecha no esté en el pasado.

    Args:
        fecha: fecha ingresada por el usuario.
        hoy: fecha actual (se inyecta para poder testear).

    Returns:
        (False, mensaje) si fecha < hoy; (True, "") si está OK.
    """
    if fecha < hoy:
        return (
            False,
            "La fecha no puede ser anterior a hoy "
            f"({hoy.isoformat()}). Probá de nuevo:",
        )
    return True, ""


def validar_orden(fecha_inicio: date, fecha_fin: date) -> tuple[bool, str]:
    """Valida que la fecha de fin no sea anterior a la de inicio.

    Args:
        fecha_inicio: primer día solicitado.
        fecha_fin: último día solicitado.

    Returns:
        (False, mensaje) si fecha_fin < fecha_inicio; (True, "") si está OK.
    """
    if fecha_fin < fecha_inicio:
        return (
            False,
            "La fecha de fin no puede ser anterior a la de inicio "
            f"({fecha_inicio.isoformat()}). Probá de nuevo:",
        )
    return True, ""
