# Pruebas de estrés / camino infeliz

Esta sección documenta el comportamiento del bot ante entradas inválidas y
flujos de excepción. El objetivo es demostrar la **robustez**: el bot nunca se
cae, valida cada dato y guía al usuario al reintento. Las validaciones se
implementan en `bot/validators.py`, las reglas de negocio (gateways) en
`bot/logic.py` y el acceso a datos en `bot/db.py`.

| #  | Caso de prueba                              | Entrada del usuario                                  | Respuesta esperada del bot                                                                                                            | Estado resultante                          |
|----|---------------------------------------------|-----------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------|
| 1  | Legajo inexistente                          | `9999`                                              | "No encontré ningún empleado con el legajo 9999. Verificá e ingresalo de nuevo:"                                                     | ESPERANDO_LEGAJO (reintento)               |
| 2  | Legajo con formato inválido (letras)        | `abc` / `Ana`                                       | "El legajo debe ser numérico, p. ej. 1001. Probá de nuevo:"                                                                          | ESPERANDO_LEGAJO (reintento)               |
| 3  | Se pide fecha y el usuario manda texto       | `mañana` (en ESPERANDO_FECHA_INICIO)                | "Fecha inválida. Usá el formato AAAA-MM-DD o DD/MM/AAAA, p. ej. 2026-07-01. Probá de nuevo:"                                         | ESPERANDO_FECHA_INICIO (reintento guiado)  |
| 4  | `fecha_fin < fecha_inicio`                   | inicio `2026-07-10`, fin `2026-07-05`               | "La fecha de fin no puede ser anterior a la de inicio (2026-07-10). Probá de nuevo:"                                                 | ESPERANDO_FECHA_FIN (reintento)            |
| 5  | Fecha en el pasado                          | `2020-01-01` (hoy es 2026-06-12)                    | "La fecha no puede ser anterior a hoy (2026-06-12). Probá de nuevo:"                                                                 | ESPERANDO_FECHA_INICIO (reintento)         |
| 6  | Saldo insuficiente (Gateway 1)              | legajo `1004` (Pedro, saldo 3), pide 5 días         | "Tu saldo es de 3 días y estás pidiendo 5. ❌ Solicitud **RECHAZADA** por saldo insuficiente."                                       | FIN — solicitud `RECHAZADA`                |
| 7  | Fechas solapadas con solicitud existente    | rango que se cruza con una solicitud APROBADA/PENDIENTE del mismo legajo | "Ya tenés una solicitud que se superpone con esas fechas. Elegí otro rango. Ingresá la fecha de inicio:"            | ESPERANDO_FECHA_INICIO (reintento)         |
| 8  | Comando desconocido en medio del flujo      | `/jefe` (en ESPERANDO_FECHA_FIN)                    | "No reconozco ese comando. Estás cargando la fecha de fin (AAAA-MM-DD), o escribí /cancelar para salir."                            | Se mantiene el estado actual               |
| 9  | `/cancelar` en distintos estados            | `/cancelar` (en cualquier estado)                   | "Operación cancelada. Podés empezar de nuevo cuando quieras con /vacaciones."                                                        | IDLE                                        |
| 10 | Solicitud > 10 días → derivación al jefe (Gateway 2) | legajo `1003` (María, saldo 25), del 2026-08-01 al 2026-08-15 (15 días) | "Tu solicitud supera los 10 días, requiere aprobación de tu jefe Laura Gómez. Estado: **PENDIENTE_APROBACION**."  | FIN — solicitud `PENDIENTE_APROBACION` (saldo NO se descuenta) |
| 11 | Happy path: ≤ 10 días con saldo (G1 + G2 + persistencia) | legajo `1001` (Ana, saldo 14), del 2026-07-01 al 2026-07-05 (5 días) | "✅ Solicitud **APROBADA** automáticamente. Se descontaron 5 días. Nuevo saldo: 9 días."         | FIN — solicitud `APROBADA`, saldo 14 → 9   |

---

## Detalle de validaciones y reglas verificadas

- **Casos 1–2 (legajo):** `validar_legajo()` exige que el texto sea numérico;
  `legajo_existe()` / `consultar_empleado()` confirman contra la base. Un legajo
  que no es número ni existe nunca avanza el flujo.
- **Casos 3–5 (fechas):** `parsear_fecha()` acepta `YYYY-MM-DD` y `DD/MM/YYYY`;
  `validar_no_pasado()` rechaza fechas anteriores a hoy; `validar_orden()`
  rechaza `fecha_fin < fecha_inicio`. Todos devuelven un mensaje guía y mantienen
  al usuario en el mismo paso.
- **Caso 6 (Gateway 1):** `tiene_saldo(saldo, dias)` evalúa
  `dias_solicitados <= saldo_dias`. Pedro (saldo 3) pidiendo 5 días no pasa, la
  solicitud se registra como `RECHAZADA` y el saldo no se toca.
- **Caso 7 (solapamiento):** `hay_solapamiento()` consulta solicitudes
  `APROBADA` o `PENDIENTE_APROBACION` del mismo legajo y detecta cruces de rango.
- **Caso 10 (Gateway 2):** `requiere_aprobacion(dias)` evalúa `dias > 10`. María
  (15 días) supera el umbral, por lo que la solicitud queda
  `PENDIENTE_APROBACION` y **no** se descuenta saldo.
- **Caso 11 (happy path + persistencia):** pasa Gateway 1 (14 ≥ 5) y Gateway 2
  (5 ≤ 10), por lo que `registrar_solicitud()` inserta la fila como `APROBADA` y
  descuenta los días en la **misma transacción** (saldo 14 → 9).

---

## Resultado esperado de la prueba

En todos los casos el bot **nunca se cae**: ante cualquier entrada inválida
responde con un mensaje claro en español, indica qué se espera (con un ejemplo)
y **mantiene la conversación** en el paso correspondiente para que el usuario
reintente, o permite salir con `/cancelar`. Las decisiones de negocio
(saldo suficiente y umbral de aprobación) se resuelven en los dos gateways y la
persistencia en SQLite queda consistente: el saldo sólo se descuenta cuando la
solicitud queda `APROBADA`, y la inserción más el descuento son atómicos.
