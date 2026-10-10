# F2: encargo generado y panorama v1

Fecha: 2026-10-10. Base: `codex/v1-engine-path` en `e2c7032` (F1 cerrada). Rama:
`claude/v1-brief-panorama`. Solo F2. Legacy sigue por defecto. Sin llamadas a modelos, sin
push ni merge.

## Qué cambia

Los trabajos `opencode` ya no reciben el texto provisional de F0. Al crear el run, después de
la ingesta, el producto genera una sola vez:

- el **encargo** (`decision_room/engine/brief.py`);
- el **panorama** (`decision_room/engine/panorama_v1.py`), si los datos lo permiten.

Los dos quedan congelados en `engine_runs`: `prompt`, `input_context` y la nueva columna
`brief` (migración 35, aditiva). `brief` guarda la versión del encargo, el origen y la revisión
del perfil del negocio, la revisión del modelo de datos, las referencias de memoria usadas y la
procedencia del panorama (tabla de ventas, catálogos y sus hashes). Un run reanudado usa lo
guardado; no vuelve a leer la última versión.

**Una sola foto.** El encargo se construye dentro de `admission.create_run`, bajo el mismo lock
de memoria y en la misma transacción que captura la línea base de dependencias del informe
(`engine_report_contexts`). Así el encargo y la vigencia del informe se refieren siempre a las
mismas revisiones de memoria y modelo de datos. El panorama se calcula antes, fuera del lock:
solo depende de las tablas del snapshot, cuyos hashes se vuelven a comprobar al crear el run.

La configuración del trabajo guarda la petición del dueño (`owner_context`, `goal`) con su
hash. El encargo necesita los datos preparados, así que no se genera al crear el trabajo.

**Trabajos de F0/F1.** Los trabajos creados antes conservan su `prompt` provisional capturado:
se comprueba su hash y se usa tal cual, sin panorama. Un run ya enlazado no vuelve a pasar por
la creación.

**Perfil congelado.** Las subidas y los conjuntos preparados guardaron en `web_jobs.context` la
descripción del negocio al crear el trabajo, con su revisión en `business_revision`; el encargo
usa esa. Los trabajos del chat guardan ahí la continuación interna del motor legacy (citas y
punteros), que no es texto del dueño para el encargo: usan el perfil vigente y registran su
revisión.

## Encargo

Los tres últimos párrafos (gráficos, profundidad y verificación) son los del encargo v1 **sin
cambios**: `engine/opencode/prompts/informe.md` tiene el mismo sha-256 (`c9184448…21a6ba`) que
los párrafos 3–5 de los dos encargos del ensayo. Una prueba lo fija.

Los dos primeros se generan a partir de:

| Parte | Fuente |
|---|---|
| Quién es el negocio | Nombre y descripción de «Mi negocio» |
| Dónde están los datos | Frase fija con `/inputs/datos` y `/inputs/manifest.json` |
| Panorama | Frase del ensayo, solo si el panorama queda `available` |
| Significado de tablas, granularidad, columnas y métricas | Solo lo declarado por el dueño en el modelo de datos vigente; columnas homónimas con su tabla; métricas con definición, unidad, tablas y periodo |
| Columnas sin significado confirmado | Frase neutra: no suponer unidad ni base y decirlo como límite |
| Límites y predicciones | Frase fija |
| Memoria | Hechos `declared` vigentes (contexto, prioridad, definición, disponibilidad), citados como declaraciones del dueño, con su periodo efectivo (desde/hasta) |
| Qué quiere el dueño | `goal` del trabajo, más la frase fija «Hazme un informe…» |

**Comparación con los encargos del ensayo.** Con la descripción del negocio y el significado de
«Unidades» declarados como en el ensayo, el encargo generado coincide salvo en cuatro frases,
en Albor y en Bruma:

1. «Los CSV están en la carpeta datos y son datos sintéticos.» pasa a «Los CSV están en la
   carpeta /inputs/datos; /inputs/manifest.json indica qué tabla es cada archivo.» En el
   producto los archivos se llaman por su ID de tabla, y nunca se afirma que los datos son
   sintéticos.
2. «En la carpeta contexto…» pasa a «En la carpeta /inputs/contexto…».
3. «No sé si los importes son por unidad o por fila, así que no uses importes, márgenes ni
   retorno de marketing.» pasa a «Si una columna no tiene aquí un significado confirmado, no
   supongas su unidad ni su base (por ejemplo, si un importe es por unidad o por fila) y dilo
   como límite.»
   - El plan prohíbe frases como «no uses importes» si el dueño no lo declara.
   - Es la diferencia de comportamiento más probable: la prohibición del ensayo era más fuerte.
   - Debe medirse en F5.
4. «Tampoco tengo información adicional…» pasa a «No tengo información adicional…», porque la
   frase anterior ya no es una negación.

Si el dueño no ha declarado significados, falta además la frase sobre «Unidades». Con datos que
no son de ventas, el párrafo fijo de profundidad sigue hablando de «producto, canal y fechas»,
como en v1 (decisión P3: v1 sin panorama, sin cambiar el encargo).

## Panorama

El cálculo es `decision_room/sales_panorama.py`, copiado sin cambios de
`claude/agent-engine-eval` (`sales-panorama-v2`). El renderizador reproduce el formato de los
archivos congelados.

**Comprobación byte a byte por la ruta del producto** (`scripts/checks/v1_panorama_frozen.py`:
importar los CSV del ensayo en una BD desechable, construir y comparar):

| Negocio | Congelado | Producto | Resultado |
|---|---|---|---|
| Bruma | `9c24a81a…` | `9c24a81a…` | Idéntico |
| Albor | `03c61a6a…` | `b3e450fd…` | Difiere en una línea |

El script compara los bytes originales. Astra reprodujo los dos resultados por separado.

La línea que difiere es la del recuento de huecos no mostrados:

- Congelado: «Hay otros 9 huecos breves anteriores a 2026, no incluidos aquí.»
- Producto: «Hay otros 342 huecos de registros no incluidos aquí.» Solo afirma que no se
  muestran; no los califica de menores, porque con más de cinco huecos materiales los
  restantes también lo serían.

**Por qué no se reproduce.** La frase del ensayo no es cierta:

- El 9 era el número de huecos listados internamente (los diez primeros por duración en
  producto × canal más uno de canal, menos los dos visibles). El cálculo detecta 344 en total.
- Al menos dos de los omitidos no son anteriores a 2026 (por ejemplo, un producto en
  Hostelería sin registros del 29 de mayo al 28 de junio de 2026).
- No se reconstruye la regla del script perdido. Se declara **variante nueva**,
  `panorama-v1-product-1`, y no se afirma equivalencia con el ensayo.

**Reglas generales, sin años ni nombres en el código:**

- Tabla de ventas: exactamente una tabla con fecha, producto, canal y cantidad reconocibles por
  su cabecera. Si hay cero o más de una, el panorama queda `unavailable` y no se suman tablas.
- Nombres: un catálogo con la misma columna clave y una sola columna `nombre`/`name`, con
  claves únicas, que cubra todos los códigos.
  - Si hay cero o varios catálogos candidatos, no se nombra nada.
  - Los códigos opacos se muestran como «TI (código sin nombre verificado)», para que dos
    canales distintos no parezcan el mismo.
  - Los catálogos solo dan nombres; no se unen cantidades.
- Huecos visibles: la regla de materialidad de eval (abierto al cierre, o reciente y de canal
  entero, con ≥ 7 días esperados ausentes o un mes ausente), hasta cinco.
- Sin panorama parcial: si alguna sección supera el límite de 500 grupos (y por tanto no se
  calculó), el panorama queda `unavailable`, para no afirmar «no se detectan huecos» sin
  haberlo comprobado.
- Tamaño: si el markdown supera 256 KiB (el límite del contexto del motor), queda
  `unavailable`; el trabajo sigue con los CSV.
- Números con agrupación española exacta, sin operaciones que redondeen.
- Fallo cerrado: si no hay panorama, el encargo omite toda referencia a él y el agente no recibe
  ningún diagnóstico. El motivo queda solo en `engine_runs.brief`.

## Pruebas

`tests/test_engine_brief.py` (22):

- párrafos fijos idénticos;
- orden y texto del primer párrafo;
- sin panorama, ninguna mención;
- sin significados inventados, nombres de ensayo ni de herramientas;
- solo memoria declarada;
- fechas desplazadas (2018–2020, 2030);
- regla de comparación según los datos;
- códigos sin catálogo;
- huecos materiales y recuento;
- formato numérico;
- catálogos con nombres, catálogos ambiguos y con claves duplicadas;
- datos que no son de ventas;
- dos tablas de ventas no se fusionan;
- cabeceras en inglés con significado y granularidad declarados;
- granularidad, métricas con definición y columnas homónimas;
- periodos efectivos de la memoria;
- descripción congelada del trabajo frente al perfil vigente del chat;
- encargo y línea base con la misma revisión del modelo de datos, aunque cambie entre el
  panorama y la creación del run;
- trabajos de F0/F1 con su prompt capturado;
- secciones por encima del límite de grupos y panorama demasiado grande: `unavailable`.

**Regresión, en este orden.**

1. Suite completa de Python frente a `e2c7032`, con PG desechable y sin clave, **antes** de los
   dos últimos cambios (definición de métrica en el encargo y límite de 256 KiB del panorama):
   - base: 710 pruebas, 77 failures + 97 errors, 6 omitidas;
   - F2: 731 pruebas, 77 failures + 97 errors, 6 omitidas;
   - las dos listas ordenadas de ERROR/FAIL son idénticas (174). Todas son de entorno: el
     sandbox local no está construido en esas rutas («Build the runtime first»);
   - las 6 omitidas son los smokes Docker nativos, sin `DECISION_ROOM_ENGINE_IMAGE_ID`.
2. Después de esos dos cambios se repitieron las suites afectadas, todas OK salvo el mismo error
   de entorno de la base en `test_data_knowledge`:
   - `test_engine_brief` (22);
   - `test_engine_*` (6 omitidas);
   - `test_report_*`, migraciones y actividad.
3. No se afirma una suite completa sobre `f977a8f`. Astra repitió 54 pruebas PG y una
   reproducción de concurrencia real sobre ese commit.

Frontend: 305/305 y tsc OK (sin cambios de frontend).

**Revisión de Astra (run 7f12a04e).** Sus hallazgos sobre el borrador están corregidos:

- carrera entre encargo y línea base;
- compatibilidad F0/F1;
- descripción y revisión del trabajo;
- precisión numérica;
- granularidad, métricas, homónimos y periodos;
- frase de huecos;
- secciones sin calcular;
- tamaño;
- comparación por bytes.

Se ajustaron pruebas existentes: versión de esquema 35, configuración del trabajo sin
`prompt`, y el fixture de F0 añade la columna `brief` antes de usar el escritor actual.

## Límites

- Equivalencia con el ensayo: parcial y documentada arriba. Es la puerta de F5, por la ruta
  del producto.
- No hay caché del panorama: se calcula una vez por run.
- Sin modelo de datos declarado, el encargo no explica las columnas.
