# TPI Organización Empresarial — Bot de Gestión de Vacaciones (RRHH)

Bot de **Telegram** que automatiza el proceso de **solicitud de vacaciones** de
Recursos Humanos, modelado en **BPMN 2.0**, con **máquina de estados** y
**persistencia en SQLite**.

- **Autor:** Alexis Delgado (trabajo individual).
- **Asignatura:** Organización Empresarial — Trabajo Práctico Integrador (TPI).
- **Institución:** UTN — Tecnicatura Universitaria en Programación a Distancia.
- **Repositorio:** `<URL_DEL_REPO>` (a completar por el autor).

---

## Qué hace

El bot ejecuta de punta a punta el proceso de solicitud de vacaciones que está
modelado en BPMN (versión *to-be*). Cada paso de la conversación es una **tarea
de usuario**, cada acceso a datos es una **tarea de servicio** y las decisiones
del proceso son **gateways** (compuertas exclusivas). El estado de cada
conversación se mantiene con un `ConversationHandler` (la "memoria" del bot) y
todo se persiste en una base de datos **SQLite**.

> **El bot NO usa inteligencia artificial en tiempo de ejecución.** La IA se
> utilizó únicamente como **asistente de desarrollo** (diseño del BPMN y ayuda
> para programar), tal como lo documenta la consigna. El bot en sí es lógica
> determinística: validaciones, `if/else` y SQL.

---

## Proceso (resumen)

1. El empleado inicia el proceso con `/start` o `/vacaciones` (evento de inicio).
2. El bot pide el **legajo** y lo **valida** contra la base de datos.
3. El bot consulta y muestra el **saldo de días** disponibles.
4. El empleado ingresa **fecha desde** y **fecha hasta** (con validación de
   formato, orden y que no sean pasadas).
5. El bot **calcula los días** solicitados (inclusive).
6. **Gateway 1 — ¿Saldo suficiente?**
   - No → la solicitud se registra como `RECHAZADA` y termina.
   - Sí → continúa.
7. **Gateway 2 — ¿Requiere aprobación del jefe?** (días > 10)
   - Sí → queda `PENDIENTE_APROBACION` y se deriva al jefe (simulado).
   - No → **aprobación automática** (`APROBADA`), se descuenta el saldo.
8. El bot confirma el resultado al empleado (evento de fin).

Los diagramas (as-is y to-be, en `.bpmn`, `.png` y Mermaid) están en
[`docs/bpmn/`](docs/bpmn/).

---

## Estructura del proyecto

```
tpi-organizacion-empresarial/
├── bot/
│   ├── __init__.py
│   ├── main.py          # Entrypoint: handlers + ConversationHandler (máquina de estados)
│   ├── states.py        # Constantes de estados de la conversación
│   ├── db.py            # Capa de acceso a SQLite (tareas de servicio)
│   ├── logic.py         # Reglas de negocio = los 2 gateways
│   └── validators.py    # Camino infeliz: parseo/validación de legajo y fechas
├── data/
│   ├── schema.sql       # DDL de tablas (empleados, solicitudes)
│   └── seed.sql         # Empleados de prueba
├── docs/
│   ├── bpmn/
│   │   ├── vacaciones-as-is.bpmn   # Importable en bpmn.io / Camunda Modeler
│   │   ├── vacaciones-to-be.bpmn
│   │   ├── as-is.png / to-be.png   # Export de alta resolución
│   │   └── diagrama.mmd            # Versión Mermaid
│   ├── diccionario_datos.md
│   ├── manual_usuario.md
│   └── pruebas_estres.md
├── requirements.txt     # python-telegram-bot (sqlite3 es stdlib)
├── .env.example         # Plantilla de TELEGRAM_TOKEN
├── .gitignore
└── README.md
```

---

## Requisitos

- **Python 3.10 o superior** (se usan anotaciones de tipo como `dict | None`).
- **`python-telegram-bot`** `>=21,<22` (ver [`requirements.txt`](requirements.txt)).
- **`sqlite3`**: forma parte de la biblioteca estándar de Python; **no** requiere
  instalación adicional.

---

## Instalación y configuración

### 1. Clonar el repositorio

```bash
git clone <URL_DEL_REPO>
cd tpi-organizacion-empresarial
```

### 2. (Recomendado) Crear un entorno virtual

```bash
python -m venv .venv
source .venv/bin/activate      # En Windows: .venv\Scripts\activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Crear el bot con @BotFather

1. Abrí Telegram y buscá a **@BotFather**.
2. Enviá el comando `/newbot`.
3. Elegí un **nombre** para el bot (el que verán los usuarios).
4. Elegí un **username** que termine en `bot` (p. ej. `vacaciones_rrhh_bot`).
5. BotFather te responde con el **token** de acceso. Copialo (es secreto).

### 5. Configurar el token

```bash
cp .env.example .env
```

Editá el archivo `.env` y pegá el token después del `=`:

```
TELEGRAM_TOKEN=123456789:ABCdEfGhIjKlMnOpQrStUvWxYz
```

> El `.env` está ignorado por Git (`.gitignore`), así que el token no se sube al
> repositorio. También podés exportar `TELEGRAM_TOKEN` como variable de entorno;
> el entorno real tiene prioridad sobre el `.env`.

---

## Cómo correr

Desde la **raíz del repositorio**:

```bash
python -m bot.main
```

Al arrancar, el bot:

- Carga el token desde `.env` (o desde el entorno).
- Inicializa la base de datos **`vacaciones.db`** de forma idempotente
  (`init_db`): crea las tablas si no existen y carga los empleados semilla la
  primera vez.
- Arranca en modo **long-polling** y queda esperando mensajes.

---

## Uso

| Comando        | Descripción                                              |
| -------------- | -------------------------------------------------------- |
| `/start`       | Inicia una solicitud de vacaciones.                      |
| `/vacaciones`  | Igual que `/start`: inicia el flujo de solicitud.        |
| `/saldo`       | Consulta el saldo de un legajo (ej.: `/saldo 1001`).     |
| `/cancelar`    | Cancela la operación en curso desde cualquier paso.      |
| `/ayuda`       | Muestra la lista de comandos y el flujo.                 |

Guía paso a paso en [`docs/manual_usuario.md`](docs/manual_usuario.md).

---

## Empleados de prueba

Cargados automáticamente desde [`data/seed.sql`](data/seed.sql) en el primer
arranque:

| Legajo | Nombre        | Saldo (días) | Jefe         |
| ------ | ------------- | ------------ | ------------ |
| 1001   | Ana García    | 14           | Carlos Ruiz  |
| 1002   | Juan Pérez    | 8            | Carlos Ruiz  |
| 1003   | María López   | 25           | Laura Gómez  |
| 1004   | Pedro Sánchez | 3            | Laura Gómez  |

Sirven para probar todos los caminos: por ejemplo, `1004` (saldo 3) dispara el
camino de **saldo insuficiente**, y `1003` (saldo 25) permite pedir **más de 10
días** y disparar el **Gateway 2** (aprobación del jefe).

---

## Modelo de datos

Dos tablas en SQLite (ver [`data/schema.sql`](data/schema.sql)):

- **`empleados`** — `legajo` (PK), `nombre`, `saldo_dias`, `jefe_nombre`.
- **`solicitudes`** — `id` (PK), `legajo` (FK), `fecha_inicio`, `fecha_fin`,
  `dias`, `estado` (`APROBADA` / `PENDIENTE_APROBACION` / `RECHAZADA`),
  `creado_en`.

Las fechas se guardan como strings ISO `YYYY-MM-DD`. Cuando una solicitud queda
`APROBADA`, el descuento del saldo se hace en la **misma transacción** que la
inserción. Detalle campo por campo en
[`docs/diccionario_datos.md`](docs/diccionario_datos.md).

---

## Mapeo BPMN → código

Esta correspondencia es la clave de la evaluación (coherencia modelo ↔
implementación):

| Elemento BPMN              | Implementación en el código                                            |
| -------------------------- | ---------------------------------------------------------------------- |
| Evento de inicio           | Comandos `/start` y `/vacaciones` (`entry_points`) en `bot/main.py`    |
| Tareas de usuario          | Estados del `ConversationHandler` (`bot/states.py`) que esperan input  |
| Tareas de servicio         | Funciones de `bot/db.py` (consultar saldo, registrar, solapamiento)    |
| Tarea de cálculo           | `logic.calcular_dias()` en `bot/logic.py`                              |
| **Gateway 1** (¿saldo?)    | `logic.tiene_saldo()` → `if/else` en `recibir_confirmacion`           |
| **Gateway 2** (¿aprobación?) | `logic.requiere_aprobacion()` (umbral 10) → `if/else`               |
| Camino infeliz             | `bot/validators.py` (legajo/fechas) + reintentos guiados              |
| Persistencia               | 100% SQLite (`bot/db.py`, `data/schema.sql`)                          |
| Evento de fin              | `ConversationHandler.END`                                              |

Máquina de estados:
`IDLE → ESPERANDO_LEGAJO → (MENU) → ESPERANDO_FECHA_INICIO → ESPERANDO_FECHA_FIN → CONFIRMANDO → FIN`.

---

## Pruebas / camino infeliz

El bot maneja entradas inválidas y flujos de excepción con reintentos guiados:
legajo inexistente o no numérico, fecha en formato inválido, fecha en el pasado,
`fecha_fin < fecha_inicio`, saldo insuficiente, fechas solapadas con otra
solicitud y comandos desconocidos / `/cancelar` en cualquier estado.

La tabla completa de casos (entrada → respuesta esperada) está en
[`docs/pruebas_estres.md`](docs/pruebas_estres.md).

---

## Despliegue

El bot usa **long-polling**, por lo que **no necesita un puerto público** ni un
webhook: alcanza con tener salida a internet. Para correrlo en un servidor y
mantener el proceso vivo:

- **`nohup`** (rápido):

  ```bash
  nohup python -m bot.main > bot.log 2>&1 &
  ```

- **`screen`** o **`tmux`**: abrir una sesión, correr `python -m bot.main` y
  desacoplar la terminal.

- **`systemd`** (recomendado en producción): crear un *service* que ejecute
  `python -m bot.main` en el directorio del repo, con el token en `.env` o como
  variable de entorno, y `Restart=on-failure` para reinicios automáticos.

En todos los casos, asegurate de tener el entorno virtual activado (o de apuntar
al Python del `.venv`) y de ejecutar desde la raíz del repositorio para que se
encuentren `data/schema.sql` y `data/seed.sql`.

---

## Repositorio

`<URL_DEL_REPO>` (a completar por el autor).
