# Implementación: contexto compartido e informes anteriores

Fecha: 12 de octubre de 2026.

Desarrolla el paso 1 del [plan de contexto compartido y cálculo rápido](<../product/contexto-compartido-y-calculo-rapido-plan.md>). El plan lo acordaron Claude y Codex. Claude lo implementa y Codex revisa los cambios. No incluye llamadas de pago; la prueba real final necesita la aprobación del propietario.

**Estado:**

- Implementado en `feature/shared-business-context`, un commit por subpaso (1.1 y 1.2 van juntos).
- Suite completa: 1006/1007. El único error es el navegador de informes, que no está construido en la máquina local.
- Pendiente: la revisión de Codex y la prueba real de pago.

## Principios

- **El núcleo de conocimiento es común:** perfil, alcance seleccionado, memoria declarada aplicable, modelo de datos vigente del análisis y un catálogo acotado. No todo el snapshot del chat.
  - El chat conserva lo que es solo suyo: estados de memoria para gestionarla, `runtime`, `tables`, `revision`, frescura y dependencias.
  - El encargo conserva su renderizado y el perfil congelado de los trabajos de subida.
- **Memoria aplicable no significa confirmada.** `context.effective()`/`scoped()` conservan estados propuestos y alternativas. El núcleo filtra explícitamente `declared`, con alcance temporal resuelto, como ya hace `brief.facts()`. No se cambia `effective()`, porque la gestión de memoria necesita esos estados. Los mensajes literales del propietario van en otro carril, como conversación o hipótesis, no como memoria.
- **Lo que dice un informe anterior es una afirmación de ese informe,** nunca un hecho verificado ahora. Las acciones anteriores son propuestas de ese informe, no «pendientes»: no existe un registro de si se ejecutaron.
- **Lo histórico se congela de forma coherente:** resúmenes, archivos y manifiesto se eligen y se leen en la misma transacción en la que se construye el encargo.
- **Determinista:** ningún modelo resume informes anteriores.

## 1.1 Núcleo de conocimiento del negocio

Nuevo módulo `decision_room/business_knowledge.py`, de solo lectura. No llama a modelos ni importa `conversations`. Recibe `db`, el negocio y una selección explícita (análisis, fuentes y periodo). Devuelve un diccionario versionado con:

- el perfil (nombre y descripción);
- la selección;
- la memoria declarada aplicable, sin alternativas, con su referencia y revisión;
- el modelo de datos vigente del análisis, con cabecera y revisión;
- un catálogo acotado de otros conjuntos, marcado como descubrimiento: no montados ni autorizados para calcular, y sin volcar todos sus modelos;
- `version`.

Quién lo usa:

- **`engine/brief.build()`** lo usa y renderiza como hoy. La procedencia registra las mismas referencias.
- **`conversations.snapshot()`** expone el núcleo en un campo nuevo (`knowledge`). El prompt del chat dice que solo `knowledge.memory` son declaraciones confirmadas.

**Decisión sobre la memoria propuesta en el chat:**

- La restricción del propietario, «la memoria sin confirmar no entra», se aplica al contexto de los **informes** (encargo y comprobador), y allí es absoluta.
- El chat sigue recibiendo `memories` con propuestas y conflictos etiquetados, como hoy, porque los gestiona con el propietario («esto lo tengo pendiente de confirmar»). Su prompt ya prohíbe presentarlos como confirmados.
- Para que no contaminen el encargo:
  - `investigation_brief` solo puede citar ids de memoria declarada, informes, conversaciones o datos;
  - el servidor rechaza un id de memoria propuesta o en conflicto;
  - el texto se presenta siempre como propuesta del asistente.
- El propietario confirmó esta regla el 12 de octubre de 2026: «solo informes».
- El encargo generado por el chat es orientación. Nunca es una fuente nueva de definiciones ni de hechos, y el comprobador recibe las declaraciones confirmadas por separado, no a través de ese texto.

Si el núcleo usa de forma material definiciones de otros análisis, se registran como dependencias. Si solo es descubrimiento, no.

Prueba de igualdad: el núcleo del chat y el del encargo coinciden para el mismo negocio, selección e instante. No se compara el snapshot completo.

## 1.2 Lector de informes anteriores

Nuevo `decision_room/reports/history.py`. Es un lector separado de `reading.chat_document()`, que sigue devolviendo solo informes vigentes.

### Elegibilidad

Entra un informe si cumple todo esto:

- origen `engine_blocks` o `engine_html`;
- la ejecución se entregó;
- ni el documento ni el trabajo están borrados;
- tiene una revisión de cliente seleccionada con presentación permitida;
- tiene un derivado canónico listo y con su identidad íntegra.

La caducidad se etiqueta, no excluye. Un informe bloqueado o sin derivado seguro no entra. El HTML del agente nunca se lee ni se renderiza en el host: se usa el texto canónico del derivado.

### Orden, con un máximo de 3

1. Referencias explícitas válidas del encargo del chat (1.5).
2. Mismo conjunto lógico (`dataset_versions.dataset_id`), cualquier versión.
3. Mismo análisis.
4. Otros informes recientes del negocio.

Dentro de cada grupo, por fecha de entrega descendente y luego por id. Si no hay conjunto lógico, se declara el criterio de respaldo que se ha usado. La relevancia nunca se infiere de nombres. La consulta SQL de candidatos tiene su propio límite.

### Resumen determinista

Se construye a partir de la proyección guardada en `native_store.result()`, sin volver a parsear con el proyector actual:

- titular y texto de portada;
- títulos y textos breves de las prioridades;
- acciones con `action_label()`.

Para `engine_html`, un extracto acotado del texto canónico. El resumen conserva los avisos de comprobación que `reading.derived_for()` incorpora.

Cada resumen lleva:

- fecha del informe;
- periodo declarado del conjunto, o «desconocido»;
- análisis, conjunto y versión;
- motivo de caducidad;
- revisión y hashes;
- estado de la comprobación.

### Límites

| Qué | Límite |
|---|---|
| Resúmenes en total | 6 KiB UTF-8 |
| Cada archivo | 64 KiB |
| Archivos en conjunto | 192 KiB |
| Metadatos (manifiesto y etiquetas) | 8 KiB UTF-8 en total |

Si un texto excede su límite, se trunca de forma explícita con el hash del texto completo y del fragmento, y nunca se presenta como completo.

Al recortar un resumen se conservan siempre etiqueta, revisión, caducidad y avisos de comprobación. Se recorta por secciones enteras, desde el final de las prioridades, y se marca qué sección no cabe. Nunca se deja un resumen con cifras y sin sus avisos.

La consulta de candidatos ordena por grupo (referencia explícita, mismo conjunto lógico, mismo análisis, resto) y por fecha antes de aplicar su `LIMIT`. Tiene un cupo de 50 candidatos, para que el límite no descarte un informe relevante antes de ordenarlo.

### Bloqueos

Los informes se leen bajo `memory.lock` y con bloqueos compartidos de documento, en orden estable de id. No se abre otra conexión ni se hace renderizado, embeddings o entrada/salida grande bajo el bloqueo.

### Consumidores

- El encargo y el chat reciben el **mismo** resumen y manifiesto seleccionados y acotados en `knowledge.history`.
- En el chat son antecedentes. No pasan a ser evidencia vigente, y los lectores y citas de informes vigentes no cambian.
- Las dependencias históricas tienen su propia validación (1.3).

## 1.3 Entradas del motor

- **El builder devuelve un resultado tipado:** prompt, procedencia y archivos de contexto generados en la misma transacción. `admission` lo valida ahí y lo incluye en `fingerprint` e `input_sha256`. El panorama puede seguir precalculado.
- **`profile.context_files()`** admite una lista exacta:
  - `panorama.md`;
  - `informes-anteriores/01.txt` a `03.txt`;
  - `informes-anteriores/manifest.json`.

  Rechaza rutas absolutas, recorridos de ruta y colisiones con `formato-informe.txt`, y comprueba los bytes por archivo y en conjunto.
- **Idempotencia:** antes de ejecutar el builder se busca un `request_key` existente.
  - Si existe, se verifican el negocio, el análisis, la selección de tablas y la solicitud original estática: owner context, objetivo, `investigation_brief`, modelo, límites y configuración. La solicitud estática se guarda con su propio hash.
  - Reutilizar una clave con otra solicitud sigue fallando. Lo único que no se recompone son las entradas dinámicas ya congeladas: memoria, informes anteriores y prompt resultante.
  - Las pruebas de `admission` que detectan entradas distintas no se relajan.
  - Esto corrige también el caso actual en que la memoria cambia entre reintentos.
- **Texto del encargo:** un párrafo «Informes anteriores» con el encuadre de afirmaciones históricas. Si el agente retoma algo, lo recalcula con los datos actuales y dice qué ha cambiado. Sube la versión del encargo en ambos formatos que cambien.
- **Tamaños:**
  - la procedencia lleva el manifiesto con hashes;
  - `checker_context` lleva el mismo resumen de hasta 6 KiB y el manifiesto, no los textos completos;
  - los textos viajan en `input_context`;
  - se respetan los límites existentes: prompt de 256 KiB y procedencia de 64 KiB.
- **Dependencias:** los informes anteriores se registran como dependencia histórica separada. Sirven para comprobar identidad y permiso hasta congelar el encargo, pero su caducidad posterior no retira el informe nuevo. No se registran como `engine_report` corriente, porque `dependencies_current` → `engine_current` los invalidaría al instante. El informe nuevo mantiene sus dependencias normales.

## 1.4 Comprobador

- **`native_checks.inputs`** recibe la identidad y los textos históricos congelados, además del manifiesto. Hoy descarta todo salvo definiciones, datos y manifiesto, así que cambiar solo `checker_context` no basta.
- **Regla del prompt:**
  - Una cifra atribuida a un informe anterior que no se pueda recalcular queda `unverifiable` («cita del informe X; no recalculada con los datos actuales»), con `independent_value` a null, y no dispara corrección.
  - Si el periodo y el filtro de la cita se pueden recalcular exactamente con los CSV actuales, puede quedar `confirmed`, pero solo por ese cálculo.
  - Nunca se confirma por coincidencia textual.
  - Una atribución falsa (el informe anterior no decía eso) genera un aviso preciso.
- **Pruebas:** estados, cobertura y offsets.

## 1.5 Encargo redactado por el chat

- **Campo opcional `investigation_brief`,** permitido solo en `investigate`, con un máximo de 4096 bytes UTF-8 serializado. Tiene tres partes:
  - `objective`, de hasta 600 caracteres;
  - `reason`, de hasta 600 caracteres;
  - `background`, una lista de hasta 6 elementos. Cada elemento tiene un texto de hasta 300 caracteres y como mucho 4 ids de fuente, que deben salir del contexto realmente entregado.
- **Validación en el servidor:** comprueba negocio, versión y frescura de esos ids. El campo es una propuesta generada: no convierte hipótesis ni frases del asistente en hechos, no cambia la memoria y no autoriza otros conjuntos. La intención literal del propietario y las definiciones confirmadas prevalecen.
- **Cambios simultáneos** en el contrato (`chat_agent`), el adaptador de decisión a acción (`conversations`) y `_job()`. `_job()` lo guarda una vez en el trabajo, cubierto por un hash, y la recuperación reutiliza la decisión guardada.
- **Texto del encargo:** incluye el mensaje literal del propietario y, aparte, «Resumen del chat (propuesta del asistente, no hechos)».
- **Compatibilidad:** las decisiones antiguas y los trabajos sin el campo siguen usando el objetivo literal. Sube `PROMPT_VERSION`.
- **Trabajos de subida (sin chat):** usan el mismo núcleo e informes anteriores, sin ningún resumen de conversación. `web_jobs.context` no se interpreta como diálogo.

## 1.6 Privacidad y exportes

- No se amplían `run.json` ni los exportes de uso con el encargo o con textos históricos.
- El texto del propietario sigue siendo privado (`inspect_run`).
- Las pruebas y la documentación pública usan datos sintéticos, nunca trazas reales.

## Pruebas

- **Memoria:** declarada, propuesta, en conflicto, retirada, por periodo y por alcance. Solo entra la declarada aplicable.
- **Aislamiento:** nunca se mezclan datos de dos negocios.
- **Selección de informes anteriores:**
  - datos reemplazados dentro del mismo conjunto lógico;
  - un informe caducado entra con su etiqueta;
  - uno borrado o bloqueado no entra;
  - un HTML se lee desde su derivado, sin renderizador;
  - proyecciones antiguas, rótulos propios y avisos de comprobación.
- **Límites:** bytes UTF-8, truncado explícito y rutas permitidas o rechazadas.
- **Concurrencia:** revisión o borrado durante la construcción. La aparición de un informe nuevo durante una recuperación no cambia la entrada.
- **Compatibilidad:** decisiones y trabajos antiguos.
- **Comprobador:**
  - el resumen y el manifiesto son iguales para el autor y para el comprobador;
  - una cita histórica correcta queda `unverifiable` aunque la cifra actual sea distinta;
  - una atribución falsa genera aviso.
- **Pruebas existentes que hay que actualizar:**
  - `test_engine_brief.py`: orden de párrafos, línea base y modelo;
  - `test_conversations.py`: contexto y acción `investigate`;
  - `test_engine_jobs.py`;
  - idempotencia de `admission`.
- Suite completa al final de cada subpaso.

## Orden de trabajo y commits

1. 1.1 Núcleo.
2. 1.2 Lector de informes anteriores.
3. 1.3 Entradas del motor e idempotencia.
4. 1.4 Comprobador.
5. 1.5 Encargo del chat.
6. Revisión de Codex sobre el conjunto y correcciones.
7. Con aprobación de gasto y el Mac despierto: dos informes seguidos sobre un negocio de prueba. El segundo debe retomar las propuestas del primero y distinguir lo citado de lo recalculado.

Cada subpaso es un commit local en `feature/shared-business-context`. Nada se sube sin que el propietario lo pida.
