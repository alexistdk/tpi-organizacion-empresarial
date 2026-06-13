"""
main.py - Entrypoint del bot de Telegram (máquina de estados / BPMN to-be)
==========================================================================
Bot de Telegram para gestión de vacaciones de RRHH (UTN - TPI).

Implementa el proceso "to-be" del diagrama BPMN usando un
`ConversationHandler` de python-telegram-bot v21 (API async). Cada estado
de la conversación es una TAREA DE USUARIO del BPMN; cada llamada a db.py es
una TAREA DE SERVICIO; y los dos GATEWAYS (compuertas exclusivas) se evalúan
con if/else en el estado CONFIRMANDO usando logic.py.

================================ MAPEO BPMN -> CÓDIGO ======================
(Esto es clave para la evaluación: coherencia modelo <-> implementación.)

  Evento de inicio          -> comandos /start y /vacaciones (entry_points)
  Tarea de usuario          -> estado del ConversationHandler que espera input
      "Ingresar legajo"        -> ESPERANDO_LEGAJO  (handler: recibir_legajo)
      "Ingresar fecha desde"   -> ESPERANDO_FECHA_INICIO (recibir_fecha_inicio)
      "Ingresar fecha hasta"   -> ESPERANDO_FECHA_FIN (recibir_fecha_fin)
      "Confirmar solicitud"    -> CONFIRMANDO (recibir_confirmacion)
  Tarea de servicio (DB)    -> funciones de bot/db.py
      legajo_existe, consultar_empleado, consultar_saldo,
      hay_solapamiento, registrar_solicitud
  Tarea de cálculo          -> logic.calcular_dias()
  GATEWAY 1 (¿saldo?)       -> if logic.tiene_saldo(...)  [en recibir_confirmacion]
  GATEWAY 2 (¿aprobación?)  -> if logic.requiere_aprobacion(...) [en recibir_confirmacion]
  Camino infeliz            -> bot/validators.py (legajo/fechas) + reintentos
  Evento de fin             -> ConversationHandler.END
===========================================================================
"""

import logging
import os
import sys
from datetime import date
from pathlib import Path

# --- Imports de python-telegram-bot v21 (API async) -----------------------
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# --- Imports de los módulos del proyecto (NO se modifican, se consumen) ----
from bot import db
from bot import logic
from bot import validators
from bot.states import (
    ESPERANDO_LEGAJO,
    MENU,
    ESPERANDO_FECHA_INICIO,
    ESPERANDO_FECHA_FIN,
    CONFIRMANDO,
)

# ==========================================================================
# Logging (nivel INFO) - permite seguir el avance por la máquina de estados.
# ==========================================================================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
# Bajamos el ruido de la librería httpx (peticiones HTTP de PTB).
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


# ==========================================================================
# Cargador mínimo de .env (SIN dependencias extra como python-dotenv).
# ==========================================================================
def cargar_dotenv(ruta: str = ".env") -> None:
    """Carga variables de un archivo .env hacia os.environ.

    Parsea línea por línea: ignora vacías y comentarios (#) y procesa
    las que tienen la forma CLAVE=valor. NO pisa variables que ya estén
    definidas en el entorno (el entorno real tiene prioridad).

    Es un parser intencionalmente simple (la consigna pide no agregar
    dependencias): no soporta comillas multilínea ni expansión de vars.
    """
    archivo = Path(ruta)
    if not archivo.exists():
        # No es un error: el token puede venir del entorno directamente.
        return
    for linea in archivo.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        # Ignoramos líneas vacías y comentarios.
        if not linea or linea.startswith("#"):
            continue
        if "=" not in linea:
            continue
        clave, _, valor = linea.partition("=")
        clave = clave.strip()
        valor = valor.strip()
        # Quitamos comillas envolventes si las hubiera.
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in ("'", '"'):
            valor = valor[1:-1]
        # El entorno real tiene prioridad sobre el .env.
        if clave and clave not in os.environ:
            os.environ[clave] = valor


# ==========================================================================
# Texto de ayuda reutilizable.
# ==========================================================================
TEXTO_AYUDA = (
    "Bot de Gestión de Vacaciones (RRHH)\n"
    "-----------------------------------\n"
    "Comandos disponibles:\n"
    "/start o /vacaciones - iniciar una solicitud de vacaciones.\n"
    "/saldo - consultar el saldo de días de un legajo.\n"
    "/cancelar - cancelar la operación en curso.\n"
    "/ayuda - mostrar esta ayuda.\n\n"
    "Flujo de una solicitud:\n"
    "1) Ingresás tu legajo.\n"
    "2) Ingresás la fecha desde (AAAA-MM-DD o DD/MM/AAAA).\n"
    "3) Ingresás la fecha hasta.\n"
    "4) Confirmás (Sí/No) y el bot resuelve la solicitud."
)


# ==========================================================================
# ENTRY POINT del proceso BPMN: /start y /vacaciones (evento de inicio).
# ==========================================================================
async def iniciar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Evento de inicio del proceso: saluda, explica y pide el legajo.

    Devuelve el estado ESPERANDO_LEGAJO (primera tarea de usuario).
    """
    # Limpiamos cualquier dato previo para arrancar el flujo "en limpio".
    context.user_data.clear()
    logger.info("Inicio de conversación (chat_id=%s)", update.effective_chat.id)
    await update.message.reply_text(
        "¡Hola! Soy el bot de gestión de vacaciones de RRHH.\n\n"
        "Te voy a ayudar a cargar una solicitud de vacaciones.\n"
        "Para empezar, ingresá tu número de legajo (p. ej. 1001):"
    )
    return ESPERANDO_LEGAJO


# ==========================================================================
# Estado ESPERANDO_LEGAJO - tarea de usuario "ingresar legajo".
# ==========================================================================
async def recibir_legajo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Valida el legajo (formato + existencia en DB) con reintento guiado.

    Camino infeliz cubierto:
      - formato inválido -> validators.validar_legajo -> reintento.
      - legajo inexistente -> db.legajo_existe -> reintento.
    """
    texto = update.message.text or ""

    # Validación de formato (camino infeliz). Si falla, reintento.
    ok, valor = validators.validar_legajo(texto)
    if not ok:
        await update.message.reply_text(valor)  # mensaje guía del validador
        return ESPERANDO_LEGAJO  # nos quedamos en el mismo estado

    legajo = valor

    # Tarea de servicio: verificar existencia en la base de datos.
    if not db.legajo_existe(legajo):
        await update.message.reply_text(
            f"No encontré el legajo {legajo} (legajo inexistente). "
            "Verificá el número e ingresalo de nuevo:"
        )
        return ESPERANDO_LEGAJO  # reintento

    # Legajo válido: lo guardamos en la "memoria" de la conversación.
    context.user_data["legajo"] = legajo

    # Tarea de servicio: consultar datos del empleado para mostrar el saldo.
    empleado = db.consultar_empleado(legajo)
    context.user_data["jefe_nombre"] = empleado.get("jefe_nombre")

    logger.info("Legajo %s validado (%s)", legajo, empleado.get("nombre"))

    # Mostramos saldo y avanzamos directo a pedir la fecha de inicio.
    # (El estado MENU del PLAN queda como punto conceptual de entrada; el
    #  flujo de solicitud sigue legajo -> fecha_inicio -> fecha_fin -> confirmar.)
    await update.message.reply_text(
        f"Hola {empleado['nombre']}.\n"
        f"Tu saldo actual es de {empleado['saldo_dias']} días.\n\n"
        "Ingresá la fecha DESDE (inicio) en formato AAAA-MM-DD o DD/MM/AAAA:"
    )
    return ESPERANDO_FECHA_INICIO


# ==========================================================================
# Estado ESPERANDO_FECHA_INICIO - tarea de usuario "ingresar fecha desde".
# ==========================================================================
async def recibir_fecha_inicio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Parsea y valida la fecha de inicio (no pasada) con reintento guiado.

    Camino infeliz cubierto:
      - texto que no es fecha -> validators.parsear_fecha -> reintento.
      - fecha en el pasado    -> validators.validar_no_pasado -> reintento.
    """
    texto = update.message.text or ""

    # Parseo de fecha (acepta AAAA-MM-DD y DD/MM/AAAA).
    ok, valor = validators.parsear_fecha(texto)
    if not ok:
        await update.message.reply_text(valor)  # mensaje guía
        return ESPERANDO_FECHA_INICIO

    fecha_inicio = valor  # objeto date

    # Validación: no puede ser anterior a hoy.
    ok, msg = validators.validar_no_pasado(fecha_inicio, date.today())
    if not ok:
        await update.message.reply_text(msg)
        return ESPERANDO_FECHA_INICIO

    # Guardamos la fecha de inicio y pedimos la de fin.
    context.user_data["fecha_inicio"] = fecha_inicio
    logger.info("Fecha inicio %s", fecha_inicio.isoformat())
    await update.message.reply_text(
        f"Fecha de inicio: {fecha_inicio.isoformat()}.\n"
        "Ahora ingresá la fecha HASTA (fin):"
    )
    return ESPERANDO_FECHA_FIN


# ==========================================================================
# Estado ESPERANDO_FECHA_FIN - tarea de usuario "ingresar fecha hasta".
# ==========================================================================
async def recibir_fecha_fin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Parsea/valida fecha fin, calcula días y chequea solapamiento.

    Camino infeliz cubierto:
      - texto que no es fecha       -> parsear_fecha -> reintento.
      - fecha_fin < fecha_inicio    -> validar_orden -> reintento.
      - solapamiento con otra solicitud -> hay_solapamiento -> termina (END).
    """
    texto = update.message.text or ""

    # Parseo de fecha.
    ok, valor = validators.parsear_fecha(texto)
    if not ok:
        await update.message.reply_text(valor)
        return ESPERANDO_FECHA_FIN

    fecha_fin = valor
    fecha_inicio = context.user_data["fecha_inicio"]

    # Validación de orden: fin no puede ser anterior a inicio.
    ok, msg = validators.validar_orden(fecha_inicio, fecha_fin)
    if not ok:
        await update.message.reply_text(msg)
        return ESPERANDO_FECHA_FIN

    # Tarea de cálculo: días solicitados (inclusive).
    dias = logic.calcular_dias(fecha_inicio, fecha_fin)

    legajo = context.user_data["legajo"]

    # Tarea de servicio: verificar solapamiento con solicitudes existentes.
    # db.hay_solapamiento espera las fechas como strings ISO 'YYYY-MM-DD'.
    if db.hay_solapamiento(legajo, fecha_inicio.isoformat(), fecha_fin.isoformat()):
        await update.message.reply_text(
            "Esas fechas se solapan con una solicitud que ya tenés "
            "registrada (aprobada o pendiente).\n"
            "La operación se canceló. Usá /vacaciones para empezar de nuevo "
            "con otras fechas."
        )
        context.user_data.clear()
        return ConversationHandler.END

    # Guardamos fecha_fin y días, y pedimos confirmación (resumen).
    context.user_data["fecha_fin"] = fecha_fin
    context.user_data["dias"] = dias
    logger.info(
        "Resumen legajo=%s %s a %s (%s días)",
        legajo, fecha_inicio.isoformat(), fecha_fin.isoformat(), dias,
    )
    await update.message.reply_text(
        "Resumen de tu solicitud:\n"
        f"  Desde: {fecha_inicio.isoformat()}\n"
        f"  Hasta: {fecha_fin.isoformat()}\n"
        f"  Días solicitados: {dias}\n\n"
        "¿Confirmás la solicitud? (Sí / No)"
    )
    return CONFIRMANDO


# ==========================================================================
# Estado CONFIRMANDO - tarea de usuario "confirmar" + LOS DOS GATEWAYS.
# ==========================================================================
async def recibir_confirmacion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Procesa la confirmación y resuelve la solicitud.

    Aquí viven los DOS GATEWAYS del BPMN (if/else con funciones de logic.py):
      - GATEWAY 1: logic.tiene_saldo(saldo, dias)          (¿hay saldo?)
      - GATEWAY 2: logic.requiere_aprobacion(dias)         (¿requiere jefe?)
    y las tareas de servicio db.registrar_solicitud(...) que persisten el
    resultado (APROBADA / PENDIENTE_APROBACION / RECHAZADA).
    """
    respuesta = (update.message.text or "").strip().lower()

    # --- Camino "No / cancelar": el usuario no confirma -> fin sin registrar.
    if respuesta in ("no", "n", "cancelar"):
        await update.message.reply_text(
            "Solicitud cancelada. No se registró nada.\n"
            "Usá /vacaciones cuando quieras volver a empezar."
        )
        context.user_data.clear()
        return ConversationHandler.END

    # --- Cualquier respuesta que no sea claramente "sí" -> reintento guiado.
    if respuesta not in ("si", "sí", "s", "ok", "dale", "confirmar"):
        await update.message.reply_text(
            "No te entendí. Respondé 'Sí' para confirmar o 'No' para cancelar:"
        )
        return CONFIRMANDO  # nos quedamos esperando una respuesta válida

    # --- Confirmado: recuperamos datos de la "memoria" de la conversación.
    legajo = context.user_data["legajo"]
    fecha_inicio = context.user_data["fecha_inicio"]
    fecha_fin = context.user_data["fecha_fin"]
    dias = context.user_data["dias"]
    fi = fecha_inicio.isoformat()
    ff = fecha_fin.isoformat()

    # Tarea de servicio: saldo actual del empleado (dato para el Gateway 1).
    saldo = db.consultar_saldo(legajo)

    # ============================ GATEWAY 1 ============================
    # ¿Tiene saldo suficiente? -> logic.tiene_saldo() (compuerta exclusiva).
    if not logic.tiene_saldo(saldo, dias):
        # Camino NO: rechazo por saldo insuficiente. Se registra RECHAZADA.
        db.registrar_solicitud(legajo, fi, ff, dias, "RECHAZADA")
        logger.info("Legajo %s: RECHAZADA (saldo=%s, dias=%s)", legajo, saldo, dias)
        await update.message.reply_text(
            "Saldo insuficiente.\n"
            f"Pediste {dias} días pero tu saldo es de {saldo}.\n"
            "La solicitud quedó registrada como RECHAZADA."
        )
        context.user_data.clear()
        return ConversationHandler.END  # evento de fin

    # ============================ GATEWAY 2 ============================
    # ¿Requiere aprobación del jefe? -> logic.requiere_aprobacion() (umbral).
    if logic.requiere_aprobacion(dias):
        # Camino SÍ: queda PENDIENTE_APROBACION y se deriva al jefe (simulado).
        db.registrar_solicitud(legajo, fi, ff, dias, "PENDIENTE_APROBACION")
        jefe = context.user_data.get("jefe_nombre") or "tu jefe/a"
        logger.info("Legajo %s: PENDIENTE_APROBACION (dias=%s)", legajo, dias)
        await update.message.reply_text(
            f"Tu solicitud de {dias} días supera el umbral de "
            f"{logic.UMBRAL_APROBACION} días, así que requiere aprobación.\n"
            f"Quedó PENDIENTE_APROBACION y se derivó a {jefe}.\n"
            "Te avisaremos cuando se resuelva."
        )
        context.user_data.clear()
        return ConversationHandler.END  # evento de fin

    # Camino NO del Gateway 2: aprobación automática. Se descuenta saldo
    # dentro de registrar_solicitud (estado 'APROBADA').
    db.registrar_solicitud(legajo, fi, ff, dias, "APROBADA")
    nuevo_saldo = db.consultar_saldo(legajo)
    logger.info("Legajo %s: APROBADA (dias=%s, nuevo_saldo=%s)", legajo, dias, nuevo_saldo)
    await update.message.reply_text(
        f"¡Listo! Tu solicitud de {dias} días fue APROBADA automáticamente.\n"
        f"Tu nuevo saldo es de {nuevo_saldo} días.\n"
        "Buen descanso."
    )
    context.user_data.clear()
    return ConversationHandler.END  # evento de fin


# ==========================================================================
# Comando /saldo - tarea de servicio suelta (consultar saldo).
# ==========================================================================
async def cmd_saldo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra el saldo. Usa el legajo guardado o lo pide en el argumento.

    Uso simple: /saldo  (si hay legajo en user_data) o /saldo 1001.
    No participa de la máquina de estados (es un comando independiente).
    """
    # 1) ¿Vino un legajo como argumento? (ej: /saldo 1001)
    legajo = None
    if context.args:
        ok, valor = validators.validar_legajo(context.args[0])
        if ok:
            legajo = valor
    # 2) Si no, usamos el legajo guardado en la conversación, si existe.
    if legajo is None:
        legajo = context.user_data.get("legajo")

    if legajo is None:
        await update.message.reply_text(
            "Pasame el legajo así: /saldo 1001\n"
            "(o iniciá una solicitud con /vacaciones para que lo recuerde)."
        )
        return

    # Tarea de servicio: consultar saldo en la DB.
    if not db.legajo_existe(legajo):
        await update.message.reply_text(f"El legajo {legajo} no existe.")
        return

    empleado = db.consultar_empleado(legajo)
    await update.message.reply_text(
        f"Empleado: {empleado['nombre']} (legajo {empleado['legajo']})\n"
        f"Saldo disponible: {empleado['saldo_dias']} días."
    )


# ==========================================================================
# Comando /ayuda - lista de comandos y explicación.
# ==========================================================================
async def cmd_ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra la ayuda con los comandos disponibles."""
    await update.message.reply_text(TEXTO_AYUDA)


# ==========================================================================
# Fallback /cancelar - cancela en CUALQUIER estado y limpia la memoria.
# ==========================================================================
async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancela la operación en curso desde cualquier estado -> END.

    Camino infeliz cubierto: el usuario abandona el flujo a mitad de camino.
    """
    logger.info("Operación cancelada por el usuario (chat_id=%s)", update.effective_chat.id)
    context.user_data.clear()
    await update.message.reply_text(
        "Operación cancelada. Tus datos de esta conversación se borraron.\n"
        "Usá /vacaciones para empezar de nuevo."
    )
    return ConversationHandler.END


# ==========================================================================
# Fallback de entrada no reconocida DENTRO del flujo: guía sin romper estado.
# ==========================================================================
async def fallback_desconocido(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mensaje guía ante un comando desconocido dentro del flujo.

    Devuelve None -> el ConversationHandler MANTIENE el estado actual, así no
    se rompe la conversación (el usuario sigue donde estaba).
    """
    await update.message.reply_text(
        "No reconozco ese comando dentro del flujo.\n"
        "Seguí con lo que te pedí, o usá /cancelar para abortar y /ayuda "
        "para ver los comandos."
    )


# ==========================================================================
# Construcción de la aplicación y registro de handlers.
# ==========================================================================
def construir_app(token: str) -> "Application":
    """Crea la Application de PTB y registra el ConversationHandler.

    El ConversationHandler ES la máquina de estados: mapea cada estado a su
    handler (tarea de usuario) y define entry_points (evento de inicio) y
    fallbacks (camino infeliz / cancelación).
    """
    app = Application.builder().token(token).build()

    # --- ConversationHandler: máquina de estados del proceso BPMN ----------
    conv = ConversationHandler(
        # Evento de inicio del BPMN: /start o /vacaciones.
        entry_points=[
            CommandHandler("start", iniciar),
            CommandHandler("vacaciones", iniciar),
        ],
        # Mapeo ESTADO -> HANDLER (cada estado = tarea de usuario del BPMN).
        states={
            ESPERANDO_LEGAJO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_legajo),
            ],
            # MENU queda definido por completitud (entrada conceptual al flujo).
            # En el flujo actual no se permanece en MENU; se documenta para
            # mantener la correspondencia 1:1 con la máquina de estados del PLAN.
            MENU: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_fecha_inicio),
            ],
            ESPERANDO_FECHA_INICIO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_fecha_inicio),
            ],
            ESPERANDO_FECHA_FIN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_fecha_fin),
            ],
            CONFIRMANDO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_confirmacion),
            ],
        },
        # Fallbacks disponibles en TODOS los estados (camino infeliz).
        fallbacks=[
            CommandHandler("cancelar", cancelar),
            CommandHandler("ayuda", cmd_ayuda),
            CommandHandler("saldo", cmd_saldo),
            # Cualquier otro comando dentro del flujo: guía sin romper estado.
            MessageHandler(filters.COMMAND, fallback_desconocido),
        ],
    )

    app.add_handler(conv)

    # --- Comandos sueltos fuera del flujo (estado IDLE) --------------------
    app.add_handler(CommandHandler("saldo", cmd_saldo))
    app.add_handler(CommandHandler("ayuda", cmd_ayuda))

    return app


# ==========================================================================
# main() - punto de entrada del programa.
# ==========================================================================
def main() -> None:
    """Carga el token, inicializa la DB y arranca el bot (polling)."""
    # 1) Cargar variables del .env (si existe) hacia el entorno.
    cargar_dotenv()

    # 2) Obtener el token de Telegram. Si no está, error claro y salida.
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        print(
            "ERROR: falta el token de Telegram.\n"
            "Definí TELEGRAM_TOKEN como variable de entorno o en un archivo "
            ".env con la línea:\n"
            "    TELEGRAM_TOKEN=tu_token_de_botfather\n",
            file=sys.stderr,
        )
        sys.exit(1)

    # 3) Tarea de servicio: inicializar la base de datos (idempotente).
    db.init_db()
    logger.info("Base de datos inicializada.")

    # 4) Construir la app y arrancar el polling (bloqueante).
    app = construir_app(token)
    logger.info("Bot iniciado. Esperando mensajes...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
