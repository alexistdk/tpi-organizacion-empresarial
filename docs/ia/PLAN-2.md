# Plan 2 — Pruebas manuales del bot de vacaciones

Guía para probar de punta a punta el bot en Telegram, verificar la persistencia en SQLite y
capturar evidencias para el PDF y la defensa. Complementa al `PLAN.md` (que cubre el diseño y la
construcción).

## 0. Pre-requisitos y puesta en marcha

1. Crear el bot en Telegram con **@BotFather**: `/newbot` → elegir nombre y username → copiar el token.
2. En la raíz del repo: `cp .env.example .env` y pegar el token en `TELEGRAM_TOKEN=...`.
3. (Recomendado) entorno virtual: `python -m venv .venv && source .venv/bin/activate`.
4. Instalar dependencias: `pip install -r requirements.txt`.
5. Arrancar el bot: `python -m bot.main`.
   - En el primer arranque se crea e inicializa `vacaciones.db` con los 4 empleados semilla.
   - En la terminal deben verse los logs INFO (inicialización de DB, "Bot iniciado...").
6. Abrir el chat del bot en Telegram y enviar `/start`.

### Reseteo de la base entre corridas
Como el happy path descuenta saldo, conviene resetear para repetir pruebas:
- `rm vacaciones.db` y volver a correr `python -m bot.main` (se recrea con los saldos originales).

### Empleados de prueba
| Legajo | Nombre        | Saldo | Jefe        |
|--------|---------------|-------|-------------|
| 1001   | Ana García    | 14    | Carlos Ruiz |
| 1002   | Juan Pérez    | 8     | Carlos Ruiz |
| 1003   | María López   | 25    | Laura Gómez |
| 1004   | Pedro Sánchez | 3     | Laura Gómez |

---

## 1. Camino feliz (happy path) — aprobación automática

Verifica Gateway 1 (saldo OK) + Gateway 2 (≤ 10 días → automático) + persistencia + descuento de saldo.

| Paso | Vos enviás        | El bot responde (literal)                                                                                                   |
|------|-------------------|-----------------------------------------------------------------------------------------------------------------------------|
| 1    | `/vacaciones`     | "¡Hola! Soy el bot de gestión de vacaciones de RRHH. … Para empezar, ingresá tu número de legajo (p. ej. 1001):"            |
| 2    | `1001`            | "Hola Ana García.\nTu saldo actual es de 14 días.\n\nIngresá la fecha DESDE (inicio) en formato AAAA-MM-DD o DD/MM/AAAA:"   |
| 3    | `2026-07-01`      | "Fecha de inicio: 2026-07-01.\nAhora ingresá la fecha HASTA (fin):"                                                          |
| 4    | `2026-07-05`      | "Resumen de tu solicitud:\n  Desde: 2026-07-01\n  Hasta: 2026-07-05\n  Días solicitados: 5\n\n¿Confirmás la solicitud? (Sí / No)" |
| 5    | `Sí`              | "¡Listo! Tu solicitud de 5 días fue APROBADA automáticamente.\nTu nuevo saldo es de 9 días.\nBuen descanso."                |

**Esperado en DB:** 1 fila en `solicitudes` con `estado='APROBADA'`; saldo de 1001 pasa de 14 → 9.

---

## 2. Camino con aprobación del jefe (Gateway 2)

Verifica Gateway 2 (> 10 días → PENDIENTE_APROBACION, NO descuenta saldo).

| Paso | Vos enviás     | El bot responde (literal / resumen)                                                                                          |
|------|----------------|-----------------------------------------------------------------------------------------------------------------------------|
| 1    | `/vacaciones`  | (bienvenida, pide legajo)                                                                                                    |
| 2    | `1003`         | "Hola María López.\nTu saldo actual es de 25 días. …"                                                                        |
| 3    | `2026-08-01`   | "Fecha de inicio: 2026-08-01. …"                                                                                             |
| 4    | `2026-08-15`   | "Resumen … Días solicitados: 15 … ¿Confirmás la solicitud? (Sí / No)"                                                        |
| 5    | `Sí`           | "Tu solicitud de 15 días supera el umbral de 10 días, así que requiere aprobación.\nQuedó PENDIENTE_APROBACION y se derivó a Laura Gómez.\nTe avisaremos cuando se resuelva." |

**Esperado en DB:** fila con `estado='PENDIENTE_APROBACION'`; saldo de 1003 **sigue en 25** (no se descuenta).

---

## 3. Camino infeliz (robustez) — casos a probar

El bot nunca se cae: valida cada dato, da un mensaje guía y mantiene el estado para reintentar.

| #  | Caso                                  | Vos enviás                                  | Bot responde (literal)                                                                                                  | Estado          |
|----|---------------------------------------|---------------------------------------------|------------------------------------------------------------------------------------------------------------------------|-----------------|
| 1  | Legajo no numérico                    | `abc` (en pedido de legajo)                 | "El legajo debe ser numérico, p. ej. 1001. Probá de nuevo:"                                                            | sigue pidiendo legajo |
| 2  | Legajo inexistente                    | `9999`                                      | "No encontré el legajo 9999 (legajo inexistente). Verificá el número e ingresalo de nuevo:"                            | sigue pidiendo legajo |
| 3  | Texto donde se espera fecha           | `mañana` (en fecha inicio)                  | "Fecha inválida. Usá el formato AAAA-MM-DD o DD/MM/AAAA, p. ej. 2026-07-01. Probá de nuevo:"                           | sigue pidiendo fecha inicio |
| 4  | Fecha en el pasado                    | `2020-01-01` (en fecha inicio)              | "La fecha no puede ser anterior a hoy (AAAA-MM-DD de hoy). Probá de nuevo:"                                            | sigue pidiendo fecha inicio |
| 5  | Formato de fecha alternativo (válido) | `01/07/2026` (en fecha inicio)              | "Fecha de inicio: 2026-07-01. …" (acepta DD/MM/AAAA y normaliza a ISO)                                                 | avanza a fecha fin |
| 6  | fecha_fin < fecha_inicio              | inicio `2026-07-10`, fin `2026-07-05`       | "La fecha de fin no puede ser anterior a la de inicio (2026-07-10). Probá de nuevo:"                                   | sigue pidiendo fecha fin |
| 7  | Saldo insuficiente (Gateway 1)        | 1004 (Pedro, saldo 3), 5 días, confirma `Sí`| "Saldo insuficiente.\nPediste 5 días pero tu saldo es de 3.\nLa solicitud quedó registrada como RECHAZADA."            | FIN (RECHAZADA, saldo sigue 3) |
| 8  | Confirmación ambigua                  | `quizas` (en confirmación)                  | "No te entendí. Respondé 'Sí' para confirmar o 'No' para cancelar:"                                                    | sigue en confirmación |
| 9  | Rechazo en confirmación               | `No` (en confirmación)                      | "Solicitud cancelada. No se registró nada.\nUsá /vacaciones cuando quieras volver a empezar."                          | FIN (no registra) |
| 10 | Comando desconocido dentro del flujo  | `/jefe` (en cualquier paso del flujo)       | "No reconozco ese comando dentro del flujo.\nSeguí con lo que te pedí, o usá /cancelar para abortar y /ayuda para ver los comandos." | mantiene el estado |
| 11 | `/cancelar` a mitad de flujo          | `/cancelar` (en cualquier paso)             | "Operación cancelada. Tus datos de esta conversación se borraron.\nUsá /vacaciones para empezar de nuevo."             | FIN (IDLE) |
| 12 | Fechas solapadas                      | ver procedimiento abajo                     | "Esas fechas se solapan con una solicitud que ya tenés registrada (aprobada o pendiente).\nLa operación se canceló. Usá /vacaciones para empezar de nuevo con otras fechas." | FIN |

**Procedimiento del caso 12 (solapamiento):** primero cargar y aprobar una solicitud para un legajo
(p. ej. 1001 del 2026-07-01 al 2026-07-05). Luego iniciar otra solicitud con el mismo legajo y fechas
que se crucen (p. ej. 2026-07-03 al 2026-07-08). Al ingresar la fecha de fin, el bot detecta el cruce.

**Comandos sueltos a probar (fuera del flujo):**
- `/saldo 1001` → "Empleado: Ana García (legajo 1001)\nSaldo disponible: 14 días." (o el saldo vigente)
- `/saldo` sin argumento y sin legajo en memoria → "Pasame el legajo así: /saldo 1001 …"
- `/ayuda` → muestra el bloque de ayuda con todos los comandos.

> Nota: para reiniciar el flujo a mitad de camino, usar `/cancelar` y luego `/vacaciones` (reenviar
> `/vacaciones` dentro del flujo cae en el fallback de comando desconocido).

---

## 4. Verificación de la persistencia en SQLite

Tras correr las pruebas, inspeccionar `vacaciones.db` (desde otra terminal, en la raíz del repo).

**Con el cliente `sqlite3`** (si está instalado):
```bash
sqlite3 vacaciones.db ".headers on" ".mode column" "SELECT * FROM solicitudes;"
sqlite3 vacaciones.db "SELECT legajo, nombre, saldo_dias FROM empleados;"
```

**Alternativa con Python (sin instalar nada):**
```bash
python -c "import sqlite3; c=sqlite3.connect('vacaciones.db'); \
[print(dict(zip([d[0] for d in cur.description], r))) \
 for cur in [c.execute('SELECT * FROM solicitudes')] for r in cur]"
```

**Qué confirmar:**
- Cada solicitud confirmada quedó registrada con el `estado` correcto (APROBADA / PENDIENTE_APROBACION
  / RECHAZADA).
- El `saldo_dias` del empleado bajó **solo** en los casos APROBADA (no en PENDIENTE ni RECHAZADA).
- `dias` coincide con el rango (extremos inclusive) y `creado_en` tiene fecha/hora.

---

## 5. Coherencia BPMN ↔ código (para la defensa)

Checklist para defender el mapeo modelo–implementación:
- [ ] Evento de inicio del TO-BE = entry_points `/start` y `/vacaciones`.
- [ ] Cada tarea de usuario del diagrama = un estado del `ConversationHandler`
      (ESPERANDO_LEGAJO → ESPERANDO_FECHA_INICIO → ESPERANDO_FECHA_FIN → CONFIRMANDO).
- [ ] Gateway 1 "¿saldo suficiente?" = `if logic.tiene_saldo(...)` en `recibir_confirmacion`.
- [ ] Gateway 2 "¿días > 10?" = `if logic.requiere_aprobacion(...)` en `recibir_confirmacion`.
- [ ] Tareas de servicio = funciones de `bot/db.py` (consultar, registrar, solapamiento).
- [ ] Eventos de fin = `ConversationHandler.END` en cada rama (rechazo, pendiente, aprobada, cancelar).
- [ ] Camino infeliz del diagrama = validaciones de `bot/validators.py` con reintento.

---

## 6. Captura de evidencias (para el PDF y la defensa)

Sacar capturas de pantalla de cada prueba para pegar en el PDF (sección de pruebas y de IA) y tener
material de respaldo en la defensa.

Checklist de capturas:
- [ ] Logs de la terminal al arrancar (init de DB + "Bot iniciado").
- [ ] Happy path completo (legajo 1001 → APROBADA, saldo 14 → 9).
- [ ] Camino Gateway 2 (legajo 1003 → PENDIENTE_APROBACION).
- [ ] Saldo insuficiente (legajo 1004 → RECHAZADA).
- [ ] Al menos 3 errores del camino infeliz (legajo inválido/inexistente, fecha inválida, fecha pasada,
      orden de fechas, solapamiento).
- [ ] `/cancelar` y `/ayuda` funcionando.
- [ ] Salida de la consulta SQLite mostrando las filas en `solicitudes` y el saldo descontado.

Sugerencia: guardar las capturas en `docs/evidencias/` para tenerlas ordenadas junto al repo.

---

## 7. Checklist final de entrega

- [ ] Bot probado en Telegram: happy path + al menos 3 ramas del camino infeliz.
- [ ] Persistencia verificada en `vacaciones.db` (estados correctos, saldo descontado solo en APROBADA).
- [ ] Capturas tomadas e insertadas en el PDF (incluyendo las del uso de IA).
- [ ] `<URL_DEL_REPO>` completada en `README.md` y en el PDF.
- [ ] Diagramas BPMN revisados (opcional: exportar PNG de alta resolución desde bpmn.io).
