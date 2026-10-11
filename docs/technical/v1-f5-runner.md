# F5: ruta del producto y techo compartido

Estado: ejecutor y control de gasto comprobados con proveedores falsos y un piloto técnico real. No acredita F5 ni cambia el motor por defecto.

`scripts/checks/product_trial.py` crea los trabajos con `Workspace.create_batch` y los ejecuta con `Workspace.run_job`. Usa el dispatch real de legacy o de html-v1 (serve + MCP), la recepción durable, la adopción y `reports.derive`. El HTML legacy se exporta por `Workspace.report` y se captura con el mismo navegador contenido. Ningún HTML de informe se ejecuta en el navegador del host.

Cada repetición y brazo tiene un negocio independiente con el mismo perfil y CSV, para que el historial o la extracción de memoria de una ejecución no alteren la siguiente. `meanings`, si se declara en el spec, aplica las mismas definiciones del dueño mediante el servicio del modelo de datos, después de la ingesta compartida y antes del run. Nunca se añade un oráculo al contexto. Los fallos, esperas y entregas parciales se conservan; no hay reintento automático ni respuesta inventada al dueño.

Comandos (desde el worktree de implementación):

```sh
python scripts/checks/product_trial.py init SPEC OUTPUT
python scripts/checks/product_trial.py run OUTPUT CODE
python scripts/checks/product_trial.py accounting OUTPUT CODE
python scripts/checks/product_trial.py status OUTPUT
python scripts/checks/product_trial.py stop OUTPUT
```

El spec privado tiene `version: 1`, `repetitions`, `cap_micro_usd`, `scope_cap_micro_usd`, `budget_path` y `businesses` (key, name, description, goal, files relativos al spec). El piloto y el ensayo comparten exactamente el mismo `budget_path`; una inicialización con otro techo se rechaza. El ejecutor no acepta un techo total superior a 25 USD. Configuración de modelo: gpt-6-luna, low, Standard; legacy admite un techo de salida por llamada registrado en el spec. Los límites de tokens, llamadas y segundos del motor se capturan en cada trabajo.

Los archivos privados (CSV, spec, manifiesto con DSN, storage, logs, registros y HTML) permanecen fuera de Git. La inicialización no llama al proveedor y crea una BD nueva, que se conserva para la auditoría. El ejecutor exige una clave ya presente en el entorno del subproceso; no la lee ni la copia a archivos.

## Reserva en dólares

`agent.api_budget` se activa solo con `DECISION_ROOM_API_BUDGET_PATH`. Ambas fronteras reales de salida (`agent.model` y `engine.proxy`) consultan un ledger SQLite común. Una transacción `BEGIN IMMEDIATE` reserva antes de enviar; comprueba el total y el subtotal del job/run. El techo y la versión se crean una sola vez. El interruptor de parada es durable. La incertidumbre conserva la reserva completa y detiene nuevos envíos; un proceso muerto deja su reserva pendiente, sin recuperarla como saldo libre.

La política `gpt-6-luna-standard-envelope-2026-10-11` permite exclusivamente el origen HTTPS oficial, gpt-6-luna y el servicio Standard. Fuerza `service_tier=default`, exige salida limitada y no reintenta a nivel de transporte. La cuenta de entrada de Responses se conserva como paso previo del producto; no es una generación. Cada generación reserva hasta 1.050.000 tokens de entrada a 0,25 USD/millón y la salida solicitada a 0,75 USD/millón. Son las tarifas máximas publicadas de entrada/escritura de caché y salida para contexto largo. Con uso confirmado, baja la reserva a una cota conservadora: toda la entrada se cobra como escritura de caché, incluso cuando el proveedor no declara cuántos tokens escribió. No se inventa una cifra de caché.

Por eso `charged_nano_usd` es una **cota de gasto bajo el catálogo congelado**, no la factura ni el coste exacto. Las estimaciones de `engine.costs` siguen publicándose aparte y pueden quedar incompletas. Un modelo/tier inesperado, uso ausente o interrumpido, o una respuesta HTTP fallida no se convierte en coste cero. Las credenciales, cuerpos y respuestas no se escriben en el ledger: solo hash, endpoint, identidad del intento y contadores.

Tarifas comprobadas el 11-10-2026: [modelo](https://developers.openai.com/api/docs/models/gpt-6-luna) y [catálogo](https://developers.openai.com/api/docs/pricing). El techo presupone esas tarifas Standard, sin recargos regionales, precios negociados ni futuros cambios del proveedor. Un cambio de proveedor/modelo/tarifa requiere otra política antes de enviar. No habilita por sí solo v1 por defecto.

## Comprobaciones previas

- Reserva concurrente en el mismo scope y en scopes distintos; rechazo antes de enviar cuando no cabe la reserva.
- Uso conocido, SSE, interrupción, HTTP fallido, tipos incorrectos y parada durable.
- Reinicio conserva el saldo; no se puede recrear el ledger existente con otro techo.
- Las dos fronteras reales del producto comparten el mismo ledger, con proveedor falso y PostgreSQL real.
- Spec/CSV/códigos del piloto técnico se fijan antes de enviarlo; solo se comprueban entrega, ruta, derivado y consumo. La calidad se evalúa en el ensayo preregistrado.

El preregistro de F5 debe fijar la muestra, orden, denominador de todos los intentos, respuestas a preguntas (si hubiera), límites, pérdidas, lectores y regla de decisión antes del ensayo. La comparación no separará encargo, contexto y runtime como efectos independientes. Legacy sigue por defecto.

## Cuotas y liquidación

El ledger conserva el recibo normalizado y publica el catálogo separado de la cota. Cada scope tiene límites persistidos de 6 M de entrada, 128 k de salida, 60 envíos y 1.200 segundos desde su primer envío. Antes de enviar reserva el máximo de entrada; una llamada confirmada libera la parte no usada. Esta admisión puede rechazar una llamada que después habría cabido por sus tokens reales. El límite temporal impide nuevos envíos; no interrumpe por sí solo una llamada ya en vuelo. El controlador html-v1 conserva sus límites propios. Un simulador del dueño debe compartir el scope del job legacy para no obtener otro presupuesto.

El ejecutor espera hasta 15 segundos a la liquidación del stream al terminar el controlador. Si no acaba, detiene nuevas llamadas. `accounting` lee los contadores sin enviar ni regenerar el informe y guarda un registro adicional; no sustituye el resultado original.

## Piloto técnico y regresión del ejecutor

Un negocio sintético pequeño, independiente de la muestra comparativa, se ejecutó una vez por brazo. Ambos terminaron y guardaron entrega e instantánea: html-v1 en 84,7 segundos y legacy en 289,3 segundos. Cotas respectivas: 0,019558625 y 0,101760625 USD; total 0,12131925 USD, con todos los envíos liquidados y ninguna incertidumbre. Estas cotas cuentan contra el techo total de F5. No se evaluó la calidad del contenido.

El primer registro html-v1 capturó el contador de salida antes de que el hilo del servidor terminase de liquidar el stream. La lectura posterior confirmó 8.297 tokens de salida y conserva el resultado inicial junto al registro final; motivó la espera descrita arriba. Los pilotos preceden a las nuevas cuotas del ledger: no se presentan como validación real de esas cuotas, que tienen pruebas con proveedor falso.

La pasada completa inicial ejecutó 813 tests Python: 812 pasaron y uno falló. Era una regresión del ejecutor: pasar `transport=None` a todos los clientes interfería con un mock legacy que ya suministraba su transporte. Se corrigió pasando ese argumento solo cuando existe el transporte presupuestado. Después, 72 tests focalizados pasaron, incluidos lenguaje, proveedor compartido, cuotas, reinicio, runner, costes, admisión y formatos del modelo.

Regresión completa de `e35d33e`, el 11-10-2026: **815/815 Python**, cero fallos y cero omitidos, con PostgreSQL desechable y las imágenes nativas configuradas; sin clave ni llamadas reales al proveedor. Duración: 634,9 segundos. Incluye los nuevos tests de cuotas y catálogo. El cambio no modifica la UI; la base F4 había pasado sus 313 tests UI, TypeScript, Vite y oxlint. Las ampliaciones posteriores del simulador y del preregistro se revisan por separado en la rama de F5.
