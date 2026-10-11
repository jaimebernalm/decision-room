# F5: ensayo comparativo v1 contra legacy por la ruta del producto. Preregistro

Estado: **congelado** el 2026-10-11 antes de inicializar el ensayo (anexo al final). Antes
era un borrador revisado por Astra, sin datos del lote de ensayo.

- Autor y conducción de la ejecución y las evaluaciones: Claude.
- Ejecutor (`product_trial.py`) y ledger de gasto: Astra, que además revisa.
- Autorización del dueño (2026-10-11): F5 y lo posterior sin más permisos. Gasto máximo:
  «Autorizo gastar hasta 25 USD en la API para F5».

## Pregunta

En la plataforma real (`codex/v1-engine-path`, F0–F4 más el ejecutor y el techo de gasto de
F5), con el encargo y el panorama generados por el producto, ¿es el informe v1 lo bastante
fiable, exacto y preferido frente al informe legacy como para ser el motor por defecto de los
informes nuevos (§7 del plan, decisiones P2, P4 y P6)?

Mide el paquete completo de cada brazo tal como lo recibe un dueño. No separa los efectos del
encargo, el contexto y el runtime.

## Brazos

| | v1 | legacy |
|---|---|---|
| Motor | `engine_kind=opencode`, perfil `html-v1` sin preguntas (el valor que pasaría a ser por defecto) | `engine_kind=legacy`: planificación, investigación y revisión actuales |
| Modelo | `gpt-6-luna`, variante `low`, imagen `decision-room-opencode:1.18.34` (`sha256:cf6973da…`) | `gpt-6-luna`, `reasoning=low`, salida por llamada 8.192 (spec del ejecutor) |
| Entrada | Encargo generado (F2) + panorama v1 si está `available` | Los mismos CSV, la misma descripción y el mismo objetivo |
| Límites del producto | `admission.Limits`: 6 M de entrada, 128 k de salida, 16 k por llamada, 60 llamadas, 1.200 s | Los del producto |
| Preguntas al dueño | Desactivadas por el perfil | Las responde un **dueño simulado** (abajo) |

**Admisión del ensayo.**
- El ledger de Astra reserva antes de cada envío, con la misma política para los dos brazos.
- Cuotas por informe del ledger del ensayo:
  - 40 M de entrada, 1 M de salida, 400 envíos y 3.600 s desde el primer envío;
  - 2,5 USD de cota;
  - antes de cada generación reserva 1,05 M de entrada.
- Por qué son tan amplias: en el piloto, la cuota anterior de 60 envíos (copiada de los
  límites de v1) cortó un informe legacy en su revisión. Legacy no tiene ese límite en el
  producto, así que el ensayo lo habría penalizado de forma artificial.
- v1 sigue limitado por su propia admisión del producto (6 M, 128 k, 60 llamadas, 1.200 s),
  que es más estricta.
- La protección real son los techos en USD. Es una admisión conservadora. No se afirma
  paridad exacta de cómputo entre los brazos.
- El dueño simulado comparte la cuota del informe legacy al que responde.

**Dueño simulado (solo legacy).**
- Por qué: en un piloto técnico, legacy preguntó «¿Qué periodos quieres comparar?» y, con la
  respuesta «No lo sé», se bloqueó en la planificación. Un dueño real habría respondido.
- Quién responde: `gpt-6-luna` con un prompt fijo (`scripts/checks/product_trial.py`,
  `OWNER_PROMPT`).
  - Solo conoce la descripción y el objetivo del spec, nunca el oráculo.
  - Puede expresar preferencias que se deducen de la petición.
  - No inventa hechos.
- Límites: un envío por pregunta, como mucho 6 respuestas por informe, y nunca se repite un
  envío incierto.
- Las preguntas, las respuestas y el coste se registran (`answers.json`) y cuentan para
  legacy.
- Es una ventaja de interacción que v1 no tiene. Se acepta porque así funciona legacy en el
  producto.

## Negocios y datos

Dos negocios sintéticos nuevos, distintos de Albor y Bruma (`scripts/f5/generate.py`, semilla
`20261011`, deterministas):

1. **Herbolario Saúco** (ventas, con otra estructura):
   - `ventas.csv`, 57.862 filas del 1-1-2024 al 21-9-2026, con septiembre parcial;
   - una fila por día × producto × canal, con unidades, precio, % de descuento e importe neto;
   - catálogos `productos.csv` (con coste unitario) y `canales.csv`;
   - el panorama v1 queda `available`.
2. **Clínica de fisioterapia Arce** (sin ventas):
   - `citas.csv`, 12.290 filas del 2-1-2025 al 30-9-2026;
   - además, `encuestas.csv` y `profesionales.csv`;
   - el panorama queda `unavailable`, así que v1 trabaja sin panorama (decisión P3).

- La descripción explica las columnas como lo haría un dueño. El objetivo es una petición
  abierta («qué ha funcionado y qué no este año…», «dónde perdemos citas…»).
- Los textos están en `scripts/f5/generate.py` (`PROFILE`), que también escribe el spec
  privado del ejecutor.
- No se declara un modelo de datos (`meanings`) ni memoria: es la experiencia por defecto.
- Cada repetición y cada brazo tienen un negocio propio en la base de datos del ensayo, con
  el mismo perfil y los mismos CSV, para que ningún informe herede memoria ni historial de
  otro.

**Señales plantadas (oráculo, `oracle.json`).** Cinco por negocio más un señuelo:

- **Herbolario:**
  - S1: la web crece, impulsada por dos productos;
  - S2: el producto más vendido no tiene registros en ningún canal del 6 al 26 de julio de
    2026;
  - S3: el canal de distribuidores cae, concentrado en suplementos;
  - S4: la promoción de marzo sube las unidades pero baja el margen por unidad;
  - S5: el total crece de forma moderada;
  - S6 (señuelo): la estacionalidad de las infusiones y septiembre parcial.
- **Clínica:**
  - S1: los no presentados de la app se disparan desde abril;
  - S2: una profesional pierde satisfacción y tiene más cancelaciones;
  - S3: caen las derivaciones de las mutuas mientras el total crece;
  - S4: el profesional nuevo tiene la agenda a medio llenar;
  - S5: los sábados funcionan muy bien;
  - S6 (señuelo): el cierre de agosto, igual en los dos años.

Las señales describen **patrones de los datos, no causas**. En S2 del herbolario, el juez
acepta que se identifique la interrupción y su magnitud. Afirmar una «rotura de stock» como
hecho no suma puntos y el auditor lo trata como causa no demostrada (véase Exactitud).

El oráculo y los datos quedan fuera de Git (`.local/f5/`) y nunca llegan a un agente.

## Ejecución

- **Ejecutor:** `scripts/checks/product_trial.py` de Astra, con el dueño simulado añadido por
  Claude.
  - `init` crea una base de datos nueva y los 24 trabajos: 2 negocios × 6 repeticiones ×
    2 brazos, mediante `Workspace.create_batch`.
  - `run CODE` ejecuta un trabajo con `Workspace.run_job`: el dispatch real legacy o html-v1
    (`serve` + MCP), la recepción, la adopción y `reports.derive`.
  - El HTML legacy publicado pasa por el mismo navegador aislado.
- **Orden:** el de `.local/f5/order.json`, con la semilla `20261011`, intercalado dentro de
  cada repetición. Los dos negocios corren en paralelo y, dentro de cada negocio, de uno en
  uno.
- **Todos los intentos cuentan.** No hay sustituciones ni repeticiones, tampoco si cae el
  ejecutor: el intento queda como `failure.json` y cuenta como pérdida.
- **Techo de gasto:**
  - un ledger durable reserva antes de cada envío, sea del producto, del motor o del dueño
    simulado. Una respuesta incierta conserva la reserva máxima y detiene los envíos;
  - pilotos sin ledger: los de Astra, con una cota de 0,121 USD, y los de Claude, con una
    cota conservadora de 0,701 USD. Esa cota cuenta toda la entrada como escritura de caché, y
    cada llamada sin uso conocido a su reserva máxima;
  - ledger del piloto técnico (`budget.sqlite`, con la política anterior): se detiene antes
    del ensayo con 0,609 USD de cota y se conserva;
  - ledger del ensayo (`budget-test.sqlite`): **23 USD**, creado una sola vez;
  - en total, ≤ 0,822 + 0,609 + 23 = 24,43 USD ≤ 25.

## Material de los evaluadores (fijado)

Todos los roles usan el **mismo material para los dos brazos**: la instantánea del navegador
aislado (`informe.html` → páginas PNG) y su texto (`informe.txt`: el texto canónico en v1 y el
inventario del mismo navegador en legacy). No se usa el PDF paginado de legacy.

**Presentación congelada:**
- política `v1-snapshot-only-1`;
- renderizador `v1-container-raster-1` con la imagen
  `sha256:a6a51acbee08be2dfef6cdc578b78dd83c3f5e123dab5dbf32a5ce2945ce1b8a` y las fuentes
  incluidas en esa imagen;
- ancho de 1280 px, páginas de hasta 2000 px de alto y como mucho 24.000 px en total;
- legacy usa `Workspace.report` con la presentación del producto.

Antes de que empiece cualquier evaluador:
- los materiales completos se copian a kits con códigos aleatorios y se sellan con un hash;
- el mapa para desvelar los brazos queda fuera de los kits;
- las evaluaciones se sellan con un hash antes de desvelar.

## Medidas

Las hacen subagentes nuevos de Claude, sin contexto de esta conversación ni del brazo. El
estilo puede delatar el brazo; es un límite.

1. **Fiabilidad.** Un intento se pierde si el dueño no recibe un informe visible:
   - v1: no se entrega, o la instantánea no queda lista;
   - legacy: no se publica (`blocked`, `failed`, `waiting` final o caída) o no se puede
     capturar.
2. **Exactitud.** Un auditor (Opus) por informe, con el texto, las páginas y los CSV, que
   puede calcular con Python:
   - Lista cada cifra y afirmación cuantitativa o causal, y marca si pertenece a una
     prioridad o conclusión principal o al resto.
   - Clasifica cada una como correcta, error menor, error material, crítico o no
     comprobable.
     - Material: una cifra, comparación o conclusión equivocada que cambiaría lo que el dueño
       entiende o decide. También lo es una causa presentada como hecho sin base en los datos
       ni en la descripción.
     - Crítico: un error material en una prioridad o recomendación principal.
   - **Esquema del auditor** (JSON por informe), con una entrada por afirmación:
     - `texto`;
     - `seccion`: prioridad o resto;
     - `tipo`: cifra, comparación, causa o recomendación;
     - `calculable`: si se puede comprobar con los CSV;
     - `veredicto`;
     - `valor_correcto`;
     - `nota`.

     Las afirmaciones no calculables (por ejemplo, recomendaciones) no entran en el
     denominador de las tasas de cifras, salvo que afirmen un hecho falso.
   - Un subagente nuevo agrupa, a ciegas y antes de desvelar, los errores materiales
     distintos de cada informe.
   - **Se publican siempre** las tasas de cifras correctas de las prioridades y del resto,
     con sus denominadores. **Esto sustituye** a la puerta de P3 (100 % y ≥ 95 %) por la
     condición (b), que es más permisiva. No se transfiere la puerta antigua.
3. **Señales.** Un juez (Opus) por informe, con el texto, las páginas y el oráculo de su
   negocio:
   - S1–S5 se puntúan de 0 a 2: 0 ausente, 1 parcial o vaga, 2 con la magnitud y el segmento
     correctos. Total sobre 10.
   - S6 vale 1 si el informe cae en el señuelo.
4. **Lectura.** Cada pareja (v1 *i*, legacy *i*) de un negocio, 6 por negocio, la leen dos
   lectores nuevos. Cada lector abre una sesión por pareja, recibe las páginas como imágenes y
   el orden A/B es aleatorio.
   - **R1, el dueño:** recibe la descripción y el objetivo. Pregunta: «¿cuál preferirías
     recibir para decidir?».
   - **R2, un asesor externo:** solo sabe que es un «informe para el dueño de este negocio».
     Pregunta: «¿cuál es más útil y fiable?».
   - **Imágenes:** todas las páginas de los dos informes, como mucho 12 por pareja, cada una
     leída una sola vez y sin componer ni reescalar.
     - En el piloto, las parejas sumaban 8–9 páginas de 1280 px.
     - Si una pareja supera 12, no se trunca, porque las páginas quitadas dependerían de la
       posición A/B aleatoria. Su lectura queda **incompleta**: (c) no se acredita en ese
       negocio y el ensayo no puede ser candidato. Lo aplican `kits.py` y `prompts.py`, no
       solo esta prosa.
     - El texto completo acompaña siempre a las imágenes.
   - Puntuación: 1 si elige v1, 0,5 si declara un empate explícito, 0 si elige legacy.
   - Si una pareja tiene una pérdida, la regla está en (c).
   - Si un lector no responde, se repite una vez con un lector nuevo. Si vuelve a fallar, la
     pareja queda **incompleta** y (c) no se acredita en ese negocio.
5. **Secundarias:**
   - la cota en USD (ledger) y la estimación de catálogo por informe;
   - el tiempo de cada intento (`result.json`, desde el inicio persistido);
   - el número de páginas;
   - las preguntas y respuestas del dueño simulado;
   - en el herbolario, si se usan importes y márgenes con el significado que declaró el dueño
     (diferencia 3 de la validación de F2).

## Regla de decisión (fijada antes del ensayo)

- **(a) Fiabilidad:** v1 pierde como mucho 1 de 12, y no más que legacy.
  - Sustituye, de forma más permisiva, a «cero pérdidas» del plan.
- **(b) Exactitud:**
  - v1 tiene cero errores críticos;
  - en cada negocio, la media de errores materiales distintos por informe v1 entregado es
    ≤ 0,5;
  - y no supera la de legacy en más de 0,25.
- **(c) Lectura:** en cada negocio, la media de v1 es > 0,5 para R1 y ≥ 0,5 para R2.
  - R2 ≥ 0,5 sustituye, de forma más permisiva, al > 0,5 de P3 en las dos medidas.
  - Si solo un brazo entregó en una pareja, cuenta como preferencia por el que entregó.
  - Si ninguno entregó, cuenta 0,5. Ese caso ya cuenta en (a).
  - Una pareja incompleta deja (c) sin acreditar.
- **(d) Señales:**
  - en cada negocio, la media del juez en v1 es ≥ la de legacy menos 1 (sobre 10);
  - y v1 no cae en el señuelo en más informes que legacy + 1.
- Si legacy no entrega ningún informe en un negocio, las comparaciones de (b) y (d) en ese
  negocio quedan **sin acreditar**; nunca se ponen a 0.
- **(e) Coste y tiempo:**
  - cota media por informe v1 ≤ 0,50 USD y máxima ≤ 1,00 USD, sin llamadas inciertas;
  - mediana de tiempo de v1 ≤ 15 min.

**Ensayo completo.** El ensayo está completo cuando:
- se intentaron los 24 informes;
- las 12 parejas tienen lectura válida de R1 y R2, o su regla de pérdida;
- y la auditoría y el juez cubren todos los informes entregados.

Si el techo de gasto (el stop del ledger es durable y nunca se crea otro), un fallo de un
evaluador u otra causa impide completarlo, el resultado es **incompleto**. Un ensayo incompleto
no puede ser candidato ni justificar el cambio de valor por defecto con medias de un
subconjunto.

**Dueño simulado: reglas del ciclo.**
- Antes de cada envío se registra el intento, con el ID de la pregunta y su hash.
- La respuesta se guarda antes de enviarla al producto. Si el envío falla después de tener la
  respuesta, no se vuelve a pedir otra.
- El dueño simulado responde en JSON estricto: `disposition`, que puede ser `answered`,
  `unknown` o `declined`, y `text`.
  - Solo `answered` lleva texto.
  - Una respuesta truncada, malformada o de más de 1.500 caracteres se rechaza, nunca se
    repara. El intento cuenta como fallo de ese informe.
- Al llegar a 6 respuestas se detiene el ciclo. Una espera que queda sin salida es una
  pérdida y no cambia los denominadores.

**Clasificación exclusiva** (para un ensayo completo):
1. **No candidato:** falla (a), o fallan dos o más de (b), (c) y (d).
2. **Mixto:** (a) se cumple y falla exactamente una de (b), (c) y (d); o solo falla (e); o
   alguna condición queda sin acreditar.
3. **Candidato:** se cumplen (a)–(e).

**Qué se hace con cada resultado:**
- **Candidato:** se prepara en una rama local el cambio de valor por defecto, con el techo
  duro en USD (P4). No se fusiona ni se publica; decide el dueño.
- **Mixto** o **No candidato:** legacy sigue por defecto. Se documenta qué falla y qué arreglo
  se propone.

Siempre se publican los resultados por negocio, las diferencias absolutas y todos los
intentos.

## Límites

- Seis parejas por negocio indican una dirección, no prueban nada.
- Los datos son sintéticos y las señales las plantó quien diseña el ensayo.
- Los evaluadores y el dueño simulado son modelos.
- El estilo puede delatar el brazo.
- Los evaluadores ven el **contenido publicado** de cada brazo: la instantánea del informe v1 y
  la exportación HTML de legacy, capturadas con el mismo navegador. No ven la pantalla completa
  del producto (cabecera, estado, fuentes alrededor). El ensayo acredita la preferencia por ese
  contenido, no toda la experiencia de pantalla.
- Piloto técnico con el ejecutor común (`pilot/`, `pilot2/`, sin mirar la calidad):
  - v1 entregó en 127 y 142 s;
  - legacy del herbolario se bloqueó en la planificación (fecha, abajo);
  - legacy de la clínica falló en la revisión por la cuota de 60 envíos del ledger (cuotas,
    arriba);
  - con la fecha corregida, legacy del herbolario entregó en 243 s (`pilot2/`).
- La fecha de hoy del dueño simulado (`owner_today`) se añadió después del primer piloto
  técnico, en el que legacy se bloqueó porque el simulado no sabía qué año era. El intento
  bloqueado se conserva (`pilot/`), y la nueva calibración (`pilot2/`) se declara aquí; no lo
  sustituye en silencio. No se cambiaron los datos, las fechas ni el encargo v1 por nada de lo
  observado.

## Anexo de congelación (2026-10-11)

- Código del ensayo: `claude/v1-f5` en `74ccb21`, sobre `codex/v1-engine-path` `e35d33e`, que
  incluye F0–F4, el ledger y el ejecutor.
- Spec privado (`.local/f5/spec.json`): `a3d196040ba7874609f4532bd7150a92e78ab933ffdb41aa9d24cf4380d31d5b`.
- Orden (`.local/f5/order.json`): `f3f453963bfe9f31fc1a5be51dee63d7a1246cabf1e3376cb4cf424e6f8f7db0`.
- Oráculo (`.local/f5/oracle.json`): `4780fc6274f0e03d62867c71f92b56668918580dbb554b0d79f00a2b93997463`.
- Ledger del piloto `budget.sqlite`: detenido, 127 llamadas liquidadas, cota 0,609275750 USD.
  Ledger del ensayo: `budget-test.sqlite`, que crea `init`.
- Revisión de Astra: conformidad técnica con los cambios del piloto (cuotas ampliadas, ledger
  nuevo de 23 USD, kits, juez y agrupador, esquema del auditor). Su última condición (no
  truncar parejas de más de 12 imágenes) está aplicada en `74ccb21`.
- Comprobación ciega posterior: `scripts/checks/product_trial_verify.py` de Astra (`f95638d`),
  que no cambia la rúbrica.

## Incidente del lote 1 y enmienda F5b (2026-10-11, antes de ver calidad)

**Lote 1 (`.local/f5/test`), incompleto según la regla congelada.**
- A las 06:18 UTC, una llamada de extracción de memoria de `clinica-1-legacy` recibió una
  respuesta del proveedor que el ledger trató como incierta.
  - La causa más probable es un rechazo HTTP con los dos negocios en paralelo. El ledger no
    guardaba el código de estado.
  - El ledger aplicó su parada global durable.
- Intentos del lote 1, todos conservados:
  - `herbolario-1-legacy`: completo, con instantánea.
  - `clinica-1-opencode`: entregado, pero el navegador aislado falla de forma reproducible con
    «Rendered pixels do not stabilize». Es una **pérdida real de v1**.
  - `herbolario-1-opencode`: bloqueado porque la parada global rechazó su tercera llamada.
  - `clinica-1-legacy`: fallido por la llamada incierta («La información del negocio aún no
    está preparada»).
  - Los 20 restantes no llegaron a empezar, porque el ledger ya estaba parado antes de
    `started.json`.
- Como la parada es durable y no se reinicia, el lote 1 es **incompleto** y no puede dar
  candidato.

**Enmienda F5b.** Se decide antes de mirar ningún informe, auditoría ni lectura, con la
conformidad de Astra.
- La parada global por un rechazo HTTP explícito es un artefacto del ensayo: en el producto no
  existe una parada global.
- F5b repite el diseño con dos cambios técnicos:
  1. El ledger trata un rechazo HTTP explícito (estado ≥ 400 sin uso) como `rejected`.
     - Conserva cargada la reserva completa, de forma conservadora, y guarda el código.
     - No detiene el resto. Rigen los reintentos y fallos propios del producto.
     - Lo incierto de verdad sigue deteniendo todo: stream interrumpido, uso ausente con 200,
       o modelo o servicio inesperados.
  2. Un solo informe a la vez en todo el ensayo, primero un negocio y después el otro, en el
     orden congelado.
- Lo demás no cambia: el spec, salvo la ruta y el techo del ledger nuevo; las indicaciones de
  los evaluadores; la presentación y la regla. El techo del ledger nuevo es 23 USD menos la cota
  cargada en `budget-test.sqlite`, así que el total sigue ≤ 25 USD.
- **F5 sigue siendo incompleto** y conserva todas sus pérdidas, incluidas las dos cortadas por
  la parada global: no se sabe qué habría hecho el producto sin ella. **F5b es un ensayo nuevo
  de 24 intentos**, separado.
  - La regla congelada se aplica a F5b por sí solo.
  - Además se publica un análisis acumulado con todos los intentos originales.
- **Condición añadida para F5b:** aunque salga candidato, v1 no pasa a ser el valor por
  defecto mientras no se resuelva la pérdida real de render de F5 (`clinica-1-opencode`, «Rendered
  pixels do not stabilize»).
  - Se resuelve con un cambio del renderizador que muestre correctamente ese HTML exacto,
    conservado intacto, sin perder las garantías de F4.
  - O con una explicación verificada de por qué no puede repetirse.
- El ledger nuevo lo implementa Astra en su rama (`rejected` con `http_status`), con pruebas
  con un proveedor falso.
- `scripts/f5/analyze.py` se corrigió antes de ver ningún resultado. Una comparación sin
  entregas legacy queda sin acreditar, no fallida. Una evaluación o lectura ausente da
  incompleto. Lo prueba `tests/test_f5_analyze.py`.

**Congelación de F5b (2026-10-11):**
- Código: `claude/v1-f5` en `0e1f46d`, sobre `codex/v1-engine-path` `4c5405f` (ledger con
  rechazos explícitos de Astra).
- Spec `.local/f5/spec-f5b.json`: `284014278ce74215e202762c082217a8cf85ad584a3af8c10aeab4e42b9a6386`.
  - Igual que el de F5, salvo `explicit_http_rejections=true`, `ledger_version`
    `gpt-6-luna-standard-envelope-2026-10-11-http-rejections-1`,
    el techo de 22.627.757 µUSD (23 USD menos la cota del ledger del lote 1, redondeada hacia
    abajo) y la ruta `budget-f5b.sqlite`.
- Orden `.local/f5/order-f5b.json`: `0fa54b056a53a3965adcd7255465cca3900d8922a8ff04b695bfe4b05cdd30d2`. Es el orden congelado del herbolario seguido del
  de la clínica, con un solo informe a la vez.
- Mismo oráculo, mismas indicaciones de los evaluadores y misma regla (`scripts/f5/analyze.py`).

**Desviación técnica durante F5b (07:20 UTC), declarada antes de ver ningún informe.**
- `herbolario-5-legacy` terminó la ejecución con estado `queued`. Tras una respuesta del dueño
  simulado, legacy replanificó y volvió a la cola.
  - En el producto, el worker web lo retoma solo. El ejecutor lo daba por terminado.
  - `queued` no es un estado final ni figura entre las pérdidas definidas («blocked»,
    «failed», «waiting» final o caída).
- Cambios en el ejecutor:
  - continúa el mismo trabajo mientras siga en `queued`/`running`, hasta 8 veces, sin
    reenviar nada;
  - un nuevo comando `continue` retoma una sola vez un intento ya registrado como no final, y
    conserva `result-initial.json`;
  - lo prueba `tests/test_product_trial.py` (7/7).
- No afecta a v1: su motor no pasa por la cola legacy.
- Los intentos posteriores usan el ejecutor corregido. `herbolario-5-legacy` se continúa con
  `continue`.
