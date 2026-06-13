"""
Lógica de negocio pura del proceso de solicitud de vacaciones.

Este módulo implementa los DOS gateways (compuertas exclusivas) del diagrama
BPMN del proceso. Es código PURO: no toca la base de datos ni hace I/O.
Sólo recibe datos ya cargados y devuelve decisiones de negocio.

Mapeo BPMN -> código (clave de la evaluación):
    - Gateway 1 (¿Tiene saldo suficiente?)  -> tiene_saldo()
    - Gateway 2 (¿Requiere aprobación del jefe?) -> requiere_aprobacion()
    - Tarea de cálculo previa a los gateways -> calcular_dias()
"""

from datetime import date

# Umbral de negocio: las solicitudes de MÁS de 10 días requieren la aprobación
# del jefe (Gateway 2). Hasta 10 días inclusive se aprueban automáticamente.
UMBRAL_APROBACION = 10  # días; > 10 requiere aprobación del jefe (Gateway 2)


def calcular_dias(fecha_inicio: date, fecha_fin: date) -> int:
    """Calcula la cantidad de días solicitados, contando AMBOS extremos.

    Tarea previa a los gateways en el BPMN: a partir del rango elegido por el
    empleado se obtiene la cantidad de días a descontar. Es inclusive, es decir
    que del 1/7 al 5/7 son 5 días (no 4).

    Args:
        fecha_inicio: primer día de las vacaciones.
        fecha_fin: último día de las vacaciones.

    Returns:
        Cantidad de días inclusive: (fecha_fin - fecha_inicio).days + 1
    """
    return (fecha_fin - fecha_inicio).days + 1


def tiene_saldo(saldo_dias: int, dias_solicitados: int) -> bool:
    """Gateway 1 del BPMN — ¿El empleado tiene saldo suficiente?

    Compuerta exclusiva: si el saldo alcanza, el flujo continúa hacia el
    Gateway 2; si no alcanza, el flujo va al camino de rechazo por saldo
    insuficiente.

    Args:
        saldo_dias: días disponibles que tiene el empleado.
        dias_solicitados: días que pide en esta solicitud.

    Returns:
        True si el saldo alcanza (dias_solicitados <= saldo_dias), False si no.
    """
    return dias_solicitados <= saldo_dias


def requiere_aprobacion(dias_solicitados: int, umbral: int = UMBRAL_APROBACION) -> bool:
    """Gateway 2 del BPMN — ¿La solicitud requiere aprobación del jefe?

    Compuerta exclusiva que se evalúa SOLO si pasó el Gateway 1 (hay saldo).
    Si la cantidad de días supera el umbral, el flujo va a la tarea de
    "Aprobación del jefe"; si no lo supera, se aprueba automáticamente.

    Args:
        dias_solicitados: días que pide la solicitud.
        umbral: límite a partir del cual se necesita aprobación (por defecto
            UMBRAL_APROBACION = 10).

    Returns:
        True si requiere aprobación (dias_solicitados > umbral), False si no.
    """
    return dias_solicitados > umbral
