# F5: ensayo comparativo v1 contra legacy por la ruta del producto. Preregistro

Estado: **borrador** para la revisión previa de Astra, sin datos del lote de ensayo. Se
congela con un anexo al final antes de crear el primer informe del ensayo.

- Autor: Claude.
- Ejecutor y techo de gasto: Astra.
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
- El ledger de Astra impone a cada informe sus propias cuotas, con la misma política para los
  dos brazos:
  - 6 M de entrada, 128 k de salida, 60 envíos y 1.200 s desde el primer envío;
  - 1,5 USD de cota por informe;
  - antes de cada generación reserva 1,05 M de entrada.
- Es una admisión conservadora y puede rechazar una llamada que habría cabido. No se afirma
  paridad exacta de presupuesto de cómputo entre los brazos.
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
- Los textos están en `scripts/f5/runner.py` (`PROFILE`) y se copian al spec privado del
  ejecutor.
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
  - techo del ledger: **24 USD**. El dólar restante cubre los pilotos sin ledger: los de
    Astra, con una cota de 0,121 USD, y los de Claude, con una cota conservadora de
    0,701 USD. Esa cota cuenta toda la entrada como escritura de caché, y cada llamada sin
    uso conocido a su reserva máxima;
  - en total, ≤ 25 USD.

## Material de los evaluadores (fijado)

Todos los roles usan el **mismo material para los dos brazos**: la instantánea del navegador
aislado (`informe.html` → páginas PNG) y su texto (`informe.txt`: el texto canónico en v1 y el
inventario del mismo navegador en legacy). No se usa el PDF paginado de legacy.

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
   - Un subagente nuevo agrupa, a ciegas y antes de desvelar, los errores materiales
     distintos de cada informe.
   - **Se publican siempre** las tasas de cifras correctas de las prioridades y del resto,
     con sus denominadores. **Esto sustituye** a la puerta de P3 (100 % y ≥ 95 %) por la
     condición (b), que es más permisiva. No se transfiere la puerta antigua.
3. **Señales.** Un juez (Opus) por informe, con el texto y el oráculo de su negocio:
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
- Una respuesta «No lo sé» se envía como `unknown`.
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
