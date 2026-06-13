# Manual de usuario

## ¿Qué hace el bot?

Es un bot de **Telegram** que automatiza la **gestión de solicitudes de
vacaciones** de RRHH. Reemplaza el circuito manual (mail/planilla a RRHH +
aprobación por mail del jefe) por una conversación guiada que:

1. Identifica al empleado por su **legajo** contra la base de datos.
2. Muestra su **saldo de días** disponibles.
3. Toma las **fechas** de inicio y fin del período solicitado.
4. Calcula los **días** pedidos y aplica las reglas de negocio:
   - **Gateway 1 — ¿hay saldo suficiente?** Si no alcanza, rechaza.
   - **Gateway 2 — ¿supera 10 días?** Si los supera, deriva al jefe
     (`PENDIENTE_APROBACION`); si no, aprueba automáticamente (`APROBADA`) y
     descuenta el saldo.
5. Registra todo en SQLite, por lo que el estado queda persistido y consultable.

El bot tiene **memoria por usuario** (máquina de estados): siempre sabe en qué
paso de la conversación está cada persona.

---

## Comandos

| Comando       | Descripción                                                              |
|---------------|--------------------------------------------------------------------------|
| `/start`      | Inicia el bot y muestra el mensaje de bienvenida.                        |
| `/vacaciones` | Inicia el flujo para solicitar vacaciones (pide legajo y fechas).       |
| `/saldo`      | Consulta el saldo de días disponibles de un empleado por su legajo.     |
| `/cancelar`   | Cancela la operación en curso y vuelve al estado inicial.               |
| `/ayuda`      | Muestra la lista de comandos y una breve explicación de uso.            |

---

## Estados de la conversación

```
IDLE → ESPERANDO_LEGAJO → (MENU) → ESPERANDO_FECHA_INICIO → ESPERANDO_FECHA_FIN → CONFIRMANDO → FIN
```

---

## Recorrido paso a paso — HAPPY PATH (aprobación automática)

Ejemplo con **legajo 1001 (Ana García, saldo 14 días)** que pide del
**2026-07-01 al 2026-07-05 = 5 días** (≤ 10 → aprobación automática).

| Paso | Estado                  | Usuario escribe        | Bot responde                                                                                                 |
|------|-------------------------|------------------------|-------------------------------------------------------------------------------------------------------------|
| 1    | IDLE → ESPERANDO_LEGAJO | `/vacaciones`          | "¡Hola! Vamos a cargar tu solicitud de vacaciones. Por favor, ingresá tu **legajo** (p. ej. 1001):"        |
| 2    | ESPERANDO_LEGAJO        | `1001`                 | "Empleado: **Ana García**. Saldo disponible: **14 días**. Ingresá la **fecha de inicio** (AAAA-MM-DD):"    |
| 3    | ESPERANDO_FECHA_INICIO  | `2026-07-01`           | "Perfecto. Ahora ingresá la **fecha de fin** (AAAA-MM-DD):"                                                  |
| 4    | ESPERANDO_FECHA_FIN     | `2026-07-05`           | "Vas a solicitar **5 días** (del 2026-07-01 al 2026-07-05). ¿Confirmás? (sí / no)"                          |
| 5    | CONFIRMANDO             | `sí`                   | "✅ Solicitud **APROBADA** automáticamente. Se descontaron 5 días. Nuevo saldo: **9 días**. (Solicitud #1)" |
| 6    | FIN                     | —                      | Fin del flujo. El bot vuelve a IDLE.                                                                         |

Resultado en la base: una fila en `solicitudes` con `estado = 'APROBADA'` y el
saldo de Ana García pasa de 14 a 9.

---

## Recorrido con aprobación del jefe (PENDIENTE_APROBACION)

Ejemplo con **legajo 1003 (María López, saldo 25 días)** que pide del
**2026-08-01 al 2026-08-15 = 15 días** (> 10 → Gateway 2 deriva al jefe).

| Paso | Estado                  | Usuario escribe | Bot responde                                                                                                            |
|------|-------------------------|-----------------|------------------------------------------------------------------------------------------------------------------------|
| 1    | ESPERANDO_LEGAJO        | `1003`          | "Empleado: **María López**. Saldo disponible: **25 días**. Ingresá la **fecha de inicio** (AAAA-MM-DD):"               |
| 2    | ESPERANDO_FECHA_INICIO  | `2026-08-01`    | "Perfecto. Ahora ingresá la **fecha de fin** (AAAA-MM-DD):"                                                             |
| 3    | ESPERANDO_FECHA_FIN     | `2026-08-15`    | "Vas a solicitar **15 días** (del 2026-08-01 al 2026-08-15). ¿Confirmás? (sí / no)"                                    |
| 4    | CONFIRMANDO             | `sí`            | "📨 Tu solicitud supera los 10 días, por lo que requiere la aprobación de tu jefe **Laura Gómez**. Estado: **PENDIENTE_APROBACION**. (Solicitud #2)" |
| 5    | FIN                     | —               | Fin del flujo.                                                                                                          |

Resultado en la base: una fila en `solicitudes` con
`estado = 'PENDIENTE_APROBACION'`. **El saldo NO se descuenta** hasta que el
jefe apruebe (sólo se descuenta cuando el estado es `APROBADA`).

---

## Cómo cancelar

En **cualquier momento** del flujo se puede escribir `/cancelar`. El bot
interrumpe la operación en curso, descarta los datos parciales y vuelve al
estado inicial (IDLE):

> "Operación cancelada. Podés empezar de nuevo cuando quieras con /vacaciones."

---

## Formato de fechas aceptado

El bot acepta **dos formatos** de fecha (ver `bot/validators.py`):

- **ISO**: `AAAA-MM-DD` — por ejemplo `2026-07-01`.
- **Día/Mes/Año**: `DD/MM/AAAA` — por ejemplo `01/07/2026`.

Internamente todas las fechas se normalizan y se guardan en formato ISO
`YYYY-MM-DD`. Si el texto no coincide con ninguno de los dos formatos, el bot
explica el error y pide reintentar (reintento guiado), sin cortar la
conversación. Reglas adicionales sobre fechas:

- La fecha **no puede estar en el pasado** (anterior a la fecha actual).
- La **fecha de fin no puede ser anterior** a la de inicio.
