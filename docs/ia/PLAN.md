# Plan — TPI Organización Empresarial: Bot de Gestión de Vacaciones

## Contexto

El **Trabajo Práctico Integrador (TPI)** de *Organización Empresarial* (UTN – Tecnicatura
Universitaria en Programación a Distancia) pide actuar como consultor tecnológico: identificar un
proceso administrativo, modelarlo en **BPMN 2.0** y automatizarlo con un **chatbot funcional** que
ejecute el proceso de punta a punta. No se evalúa la complejidad tecnológica sino **la coherencia
entre el modelo BPMN y la lógica implementada**.

Decisiones tomadas (Alexis Delgado, individual):
- **Proceso:** Gestión de vacaciones (RRHH).
- **Stack:** Telegram + Python (`python-telegram-bot`), persistencia 100% en **SQLite** (sin Excel).
- **Sin capa de IA dentro del bot** (era opcional → se omite). La IA solo se documenta como *asistente de desarrollo*.
- **Alcance:** generamos código del bot, base de datos, README, diagrama BPMN (as-is / to-be) y el PDF de entrega.

El directorio (`/home/alexis/utn/organizacion-empresarial/tpi/`) está vacío salvo el PDF de consigna,
así que es un proyecto greenfield.

## Requisitos de la consigna (checklist de entrega)

1. **Diagrama BPMN 2.0** as-is y to-be, alta resolución, con: lanes (Usuario / Sistema-Bot),
   eventos de inicio y fin, y **al menos 2 gateways** con caminos lógicos distintos.
2. **Chatbot funcional** que ejecute el proceso: no respuestas estáticas → integra una base de datos.
3. **Máquina de estados**: el bot "tiene memoria" y sabe en qué paso está cada usuario.
4. **Camino infeliz (robustez)**: maneja errores de entrada y flujos de excepción, con ejemplos.
5. **Persistencia obligatoria**: base de datos para registrar y consultar estados.
6. **Documentación**: diccionario de datos, manual de usuario, pruebas de estrés.
7. **Repositorio Git** con código limpio, comentado y `README.md` con instrucciones de despliegue.
8. **Herramientas de IA**: justificar elección y prompts usados, con capturas de pantalla.
9. **PDF de entrega**: 4–8 páginas A4, Times New Roman 11pt, títulos 12PT BOLD UPPERCASE,
   figuras/tablas con aclaraciones centradas debajo.
10. **Defensa/demo en vivo**: bot funcionando siguiendo el flujo del BPMN.

## Diseño del proceso (vacaciones)

**As-is (manual):** empleado manda mail/planilla a RRHH → RRHH revisa saldo a mano → jefe aprueba
por mail → se notifica. Lento, sin trazabilidad, propenso a errores.

**To-be (automatizado con bot):**
- Evento inicio: `/start` o `/vacaciones`.
- El bot pide **legajo** y lo valida contra la DB (camino infeliz: legajo inexistente).
- El bot consulta y muestra **saldo de días disponibles** (tarea de servicio).
- El usuario ingresa **fecha desde** y **fecha hasta** (tareas de usuario; validación de formato/orden/pasado).
- El bot calcula **días solicitados**.
- **Gateway 1 — ¿saldo suficiente?**
  - No → informa saldo y rechaza → fin.
  - Sí → continúa.
- **Gateway 2 — ¿requiere aprobación del jefe?** (días > umbral, p. ej. 10)
  - Sí → estado `PENDIENTE_APROBACION`, deriva a jefe (simulado) → fin.
  - No → **aprobación automática**, descuenta saldo, registra solicitud → fin.
- Evento fin: confirma resultado al empleado.

**Lanes:** Empleado (Usuario) / Bot (Sistema). Opcional tercer lane Jefe-RRHH para la derivación.

**Máquina de estados (por usuario):**
`IDLE → ESPERANDO_LEGAJO → MENU → ESPERANDO_FECHA_INICIO → ESPERANDO_FECHA_FIN → CONFIRMANDO → FIN`

**Camino infeliz a cubrir (con ejemplos en el PDF):**
- Legajo inexistente / formato inválido.
- Se pide fecha y el usuario manda texto → reintento guiado.
- `fecha_fin < fecha_inicio`.
- Fecha en el pasado.
- Saldo insuficiente.
- Fechas solapadas con una solicitud existente.
- Comando desconocido / `/cancelar` en cualquier estado.

## Arquitectura del código

```
tpi/
├── bot/
│   ├── main.py          # entrypoint: handlers de Telegram + ConversationHandler (máquina de estados)
│   ├── states.py        # constantes de estados de la conversación
│   ├── db.py            # capa de acceso a SQLite (consultar saldo, registrar solicitud, etc.)
│   ├── logic.py         # reglas de negocio = gateways (saldo suficiente, requiere aprobación)
│   └── validators.py    # camino infeliz: parseo/validación de legajo y fechas
├── data/
│   ├── schema.sql       # DDL de tablas
│   └── seed.sql         # empleados de ejemplo
├── docs/
│   ├── bpmn/
│   │   ├── vacaciones-as-is.bpmn   # importable en bpmn.io / Camunda Modeler
│   │   ├── vacaciones-to-be.bpmn
│   │   ├── as-is.png  /  to-be.png # export de alta resolución para el PDF
│   │   └── diagrama.mmd            # versión Mermaid para visualización rápida
│   ├── diccionario_datos.md
│   ├── manual_usuario.md
│   └── pruebas_estres.md
├── requirements.txt     # python-telegram-bot (sin dependencias extra: sqlite3 es stdlib)
├── .env.example         # TELEGRAM_TOKEN
├── .gitignore           # .env, *.db, __pycache__
└── README.md            # qué es, cómo configurar token, cómo correr, cómo desplegar
```

**Modelo de datos (SQLite):**
- `empleados(legajo PK, nombre, saldo_dias, jefe_nombre)`
- `solicitudes(id PK, legajo FK, fecha_inicio, fecha_fin, dias, estado, creado_en)`
  - `estado ∈ {APROBADA, PENDIENTE_APROBACION, RECHAZADA}`

**Mapeo BPMN → código (clave de la evaluación):**
- Tareas de usuario → estados del `ConversationHandler` que esperan input.
- Tareas de servicio → funciones en `db.py` (consultar saldo, registrar).
- Gateways → `if/else` en `logic.py` (`tiene_saldo()`, `requiere_aprobacion()`).
- Persistencia → 100% SQLite.

**IA (solo documentación):** la consigna exige justificar las "Herramientas de IA utilizadas" con
capturas de prompts. Se cumple documentando el uso de IA como **asistente de desarrollo** (prompts
usados para diseñar el BPMN y programar el bot, con capturas). **No** se integra IA dentro del bot.

## Pasos de ejecución

1. **Scaffold del proyecto**: crear estructura de carpetas, `.gitignore`, `requirements.txt`,
   `.env.example`, `git init` + README inicial.
2. **Base de datos**: `schema.sql` + `seed.sql` (3–4 empleados con distintos saldos) y `db.py`
   con las funciones de acceso (inicializa la DB SQLite desde los `.sql`).
3. **Lógica de negocio y validadores**: `logic.py` (los 2 gateways) y `validators.py` (camino infeliz).
4. **Bot de Telegram**: `main.py` + `states.py` con el `ConversationHandler` que implementa la
   máquina de estados y enlaza cada paso con db/logic/validators. Comandos `/start`, `/vacaciones`,
   `/saldo`, `/cancelar`, `/ayuda`.
5. **Documentación markdown**: diccionario de datos, manual de usuario (comandos), pruebas de estrés
   (tabla de inputs inválidos → respuesta esperada).
6. **Diagrama BPMN**: generar `.bpmn` (XML válido para bpmn.io) as-is y to-be + versión Mermaid;
   abrir en bpmn.io / draw.io y exportar PNG de alta resolución para el PDF.
7. **README**: descripción, requisitos, cómo crear el bot con @BotFather y obtener el token,
   cómo correr (`pip install -r requirements.txt` + `python -m bot.main`), y cómo desplegar.
8. **PDF de entrega**: usar el skill **`utn-assignment-pdf`** para generar el documento académico
   (portada UTN, Times New Roman 11pt, títulos 12pt bold uppercase, 4–8 págs A4) con:
   fundamento/proceso elegido, BPMN as-is y to-be (con captura y aclaración centrada), stack y
   justificación, herramientas de IA + capturas de prompts, diccionario de datos, manual,
   pruebas de estrés, y link al repo.

## Verificación

- **Bot**: crear un bot real con @BotFather, poner el token en `.env`, correr `python -m bot.main`
  y recorrer en Telegram el **happy path** (solicitud que se aprueba) y al menos 3 ramas del
  **camino infeliz** (legajo malo, fecha inválida, saldo insuficiente). Confirmar que la solicitud
  queda registrada en la DB y el saldo se descuenta.
- **Coherencia BPMN↔código**: revisar que cada gateway del diagrama tenga su `if/else` en `logic.py`
  y que los estados del diagrama coincidan con los del `ConversationHandler`.
- **DB**: inspeccionar `vacaciones.db` (tabla `solicitudes`) tras las pruebas.
- **PDF**: verificar 4–8 páginas, tipografía y que las figuras tengan aclaración centrada debajo.

## Pendientes a confirmar durante la ejecución
- Usuario/URL del repositorio (GitHub) para el README y el PDF.
- Umbral de días para disparar el Gateway 2 (propuesta: > 10 días).
