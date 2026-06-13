"""
states.py - Estados de la máquina de estados del ConversationHandler
=======================================================================
Bot de Telegram para gestión de vacaciones de RRHH (UTN - TPI).

Estas constantes enteras identifican cada PASO de la conversación. El
`ConversationHandler` de python-telegram-bot guarda, por cada chat/usuario,
en qué estado está; eso es lo que le da "memoria" al bot (requisito de la
consigna: máquina de estados).

Correspondencia con la máquina de estados del PLAN (proceso to-be):

    IDLE
      -> ESPERANDO_LEGAJO        (el bot pide el legajo)
      -> MENU                    (legajo válido; punto de entrada al flujo)
      -> ESPERANDO_FECHA_INICIO  (el bot pide la fecha "desde")
      -> ESPERANDO_FECHA_FIN     (el bot pide la fecha "hasta")
      -> CONFIRMANDO             (el bot muestra resumen y pide Sí/No)
      -> FIN                     (evento de fin del proceso)

Notas de mapeo:
- IDLE es el estado "sin conversación activa": en PTB equivale a NO estar
  dentro del ConversationHandler. No necesita una constante propia.
- FIN se mapea a `ConversationHandler.END` (la constante que PTB usa para
  cerrar la conversación y volver a IDLE). Por eso no se define acá: se usa
  directamente `ConversationHandler.END` en main.py.

Cada estado que ESPERA input del usuario es una "tarea de usuario" del BPMN.
"""

# Estados de la conversación. `range(5)` asigna 0,1,2,3,4 en orden.
# MENU queda disponible para extensiones (p. ej. un menú con /saldo); el flujo
# principal de solicitud va legajo -> fecha_inicio -> fecha_fin -> confirmar.
(
    ESPERANDO_LEGAJO,        # 0 - tarea de usuario: ingresar legajo
    MENU,                    # 1 - punto de entrada al flujo (post-validación)
    ESPERANDO_FECHA_INICIO,  # 2 - tarea de usuario: ingresar fecha desde
    ESPERANDO_FECHA_FIN,     # 3 - tarea de usuario: ingresar fecha hasta
    CONFIRMANDO,             # 4 - tarea de usuario: confirmar (Si/No)
) = range(5)

# El estado FIN del PLAN se mapea a ConversationHandler.END (no es una
# constante de este modulo; se importa desde telegram.ext en main.py).
