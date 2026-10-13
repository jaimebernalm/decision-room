# Implementación: cálculo rápido en el chat

Fecha: 12 de octubre de 2026.

Desarrolla el paso 2 del [plan de contexto compartido y cálculo rápido](<../product/contexto-compartido-y-calculo-rapido-plan.md>). El plan lo acordaron Claude y Codex en tres versiones; Codex aprobó la tercera. Claude lo implementa y Codex revisa los cambios. No incluye llamadas de pago; la prueba real final necesita la aprobación del propietario.

**Estado: implementado, revisado y validado con el modelo real.**

- Implementado en `feature/quick-chat-calculation`: un commit por parte (1 a 5), uno de correcciones tras la suite completa, esta documentación y dos rondas de correcciones de la revisión de Codex.
- Codex revisó la implementación en tres versiones y aprobó la última. Sus hallazgos, todos corregidos: un rechazo por falta de espacio repetía el código en el prompt; las definiciones perdían el periodo y el alcance de cada declaración; la recuperación de informes antiguos podía fallar o tocar un cálculo vivo del chat; la observación podía pasarse 2 bytes de su límite; y, si ni el rechazo cabía, el turno fallaba en vez de responder.
- Suite completa: 1043/1044. El único error es el navegador de informes, que no está construido en la máquina local. Interfaz: 341 pruebas, `tsc` y `oxlint` sin errores.
- Las cifras de esta página son las implementadas. Donde la implementación ajustó un número del plan acordado, se dice.

## Principios

- **Un cálculo rápido nunca se presenta como comprobado.** La etiqueta la pone el servidor, no el texto del modelo: «Cálculo rápido, sin comprobación independiente». Aprobar la respuesta del chat no es comprobar sus cifras.
- **El código solo corre en el sandbox aislado que ya existe** (`decision_room/execution.py`, imagen de `sandbox/`). No se crea otro mecanismo de ejecución.
- **El chat nunca crea un informe a partir de una decisión del modelo.** Propone el informe y el propietario lo confirma con un botón. Un mensaje escrito como «hazme un informe» también acaba en una propuesta que se confirma con un clic.
- **Todo es recuperable sin repetir trabajo a ciegas:** la intención de cada cálculo se guarda antes de tocar Docker, y un cálculo terminado nunca se vuelve a ejecutar para leer su resultado.
- **Se mantiene el bucle propio del chat** y las reglas del paso 1: memoria declarada en los informes y encargo del chat solo como orientación.

## Desviaciones del plan de producto

- **Sin contenedor siempre activo.** El plan preveía mantener un contenedor activo durante la conversación. Arrancar el contenedor del sandbox con las mismas restricciones e importar DuckDB y pandas tarda 0,40–0,46 s en este Mac (tres mediciones con `docker run`; no es una medición completa de `execute`). Un contenedor nuevo por cálculo conserva el modelo de seguridad actual: nunca se reutiliza un contenedor ni queda estado entre preguntas o negocios. Medido después con Docker real y un modelo simulado sobre una tabla pequeña (tres turnos): la ejecución completa de `execute` tarda unos 0,59 s y el turno entero unos 0,8 s, sin contar las llamadas al modelo. No se promete una latencia: depende del tamaño de los datos y de la máquina.
- **Imagen del sandbox, no la del agente de informes.** Se usa la imagen de `sandbox/`, que tiene la pila de datos de Python y el protocolo `dr_runtime`, con las mismas restricciones: sin red, sistema de archivos de solo lectura, usuario sin privilegios, sin capacidades, límites de memoria, procesos y disco, y datos montados en solo lectura.

## 2.1 Contrato de decisión

En `chat_agent.py`, con `PROMPT_VERSION` `conversation-v20`:

- **Acción `calculate`** con `calculation`:
  - `purpose`: la pregunta concreta que se calcula, de 1 a 300 caracteres;
  - `tables`: de 1 a 4 tablas, cada una con un alias (`[a-z][a-z0-9_]{0,62}`) y el id de la tabla preparada;
  - `code`: hasta 8192 caracteres y, comprobado aparte, hasta 8 KiB como cadena JSON serializada (escapes incluidos).

  Requiere también `analysis_id`.
- **Acción `offer_report`** (2.5): `analysis_id`, `investigation_brief` obligatorio (con las reglas del paso 1), `text` y `sources`.
- `calculation` es incompatible con cualquier otra acción, incluidas `edit_presentation` y la guía de bienvenida. `investigation_brief` se admite en `offer_report` y en `investigate`.
- `investigate` sigue en el contrato solo para reproducir decisiones ya guardadas. Nunca crea un trabajo (2.5).
- `calculate` no se mezcla con `retrieval` y, como una búsqueda, no se admite cuando ya no quedan pasos (`ordinal >= MAX_RETRIEVALS`).
- `memory.retrieval.Request` no cambia, porque lo comparte el sistema antiguo de investigación.

## 2.2 Registro durable y ejecución

### Tabla `chat_calculations`

Registra la intención y la propiedad de cada cálculo. Tiene estos campos:

- negocio, conversación, turno, intento y ordinal;
- análisis;
- solicitud: propósito, tablas con su alias, id, versión de metadatos y nombres originales, y código;
- `identity_sha256`: hash normalizado del código, los alias, las tablas con sus versiones y las definiciones. Excluye el propósito, que es texto libre;
- definiciones y dependencias congeladas;
- `admission`: `reserved`, `admitted` o `refused`, con el motivo del rechazo;
- `execution_id`, nulo hasta la admisión;
- fecha.

Unicidad por turno, intento y ordinal, y por ejecución. La tabla `executions` sigue siendo el registro del resultado y de los artefactos. `chat_retrievals` con `tool='calculate'` es la observación que ve el modelo y se materializa de forma idempotente a partir de las dos anteriores. La clave de petición de la ejecución es `chat-calc:<id del cálculo>`.

### Flujo de un cálculo

1. **Transacción corta** con `memory.lock` y `dependencies_current`:
   - autoriza el alcance (2.3);
   - congela las definiciones y las dependencias;
   - aplica el presupuesto (2.4);
   - inserta la fila del cálculo, o encuentra la existente para ese ordinal.

   Ningún bloqueo ni transacción sigue abierto mientras corre Docker.
2. **Resolución:**
   - Si existe una fila de `executions` para la clave:
     - si está **terminada**, se lee con `get_execution` y no se vuelve a llamar a `execute`. Así, un Docker caído o una imagen cambiada no impiden recuperar un cálculo que ya terminó;
     - si **no está terminada** (`preparing` o `running`, incluida la limpieza pendiente), el turno falla con el aviso habitual de reintento. La ejecución se deja como está y nunca se marca como interrumpida sin haber retirado su contenedor.
   - Si no existe esa fila, no se ejecutó nada, porque `execute` la inserta antes de preparar archivos o tocar Docker. Se llama a `execute` con la solicitud congelada y se enlaza `execution_id`. Si `execute` rechaza por ocupación o capacidad antes de admitir, la fila queda `refused` y el modelo recibe un error de herramienta.
3. **Transacción corta** con `memory.lock`: se vuelven a validar las dependencias, incluidas las del cálculo, y se inserta la observación si falta. Si algo cambió, se aplica la regla de contexto desactualizado de siempre.

### Límites de la ejecución

- 30 segundos.
- Como máximo 64 MiB de datos de entrada en total. Se comprueba con el tamaño de los Parquet guardados antes de copiar. Es un parámetro opcional nuevo de `execute` que entra en la huella mediante los límites.
- Contenedor nuevo por cálculo.
- `can_quick_calculate` en `runtime_context` indica si existe el manifiesto del sandbox. No se instancia `DockerBackend` en cada snapshot, porque inspecciona Docker y puede esperar 20 s. Los fallos reales de arranque llegan como errores de herramienta.

### Recuperación

- Al reintentar explícitamente un turno cuyo intento anterior dejó un cálculo sin resolver, se intenta una recuperación acotada, `recover_execution(config, business, execution_id)`. Toma el bloqueo exclusivo de mantenimiento con un intento no bloqueante, retira el contenedor etiquetado y después marca la ejecución como interrumpida. Si el bloqueo está ocupado o no se confirma la retirada, no hace nada. Nunca vuelve a ejecutar código.
- Si después de ese intento sigue habiendo un cálculo del mensaje sin resolver, el reintento se rechaza con un 409 y no se crea un intento nuevo.
- La recuperación previa de los trabajos antiguos (`web/service.py`) solo considera y solo recupera las ejecuciones que no son del chat (`execution.open_report_runs` y `recover_executions(..., report_runs_only=True)`). Si un cálculo vivo ocupa el bloqueo, el informe espera a la siguiente pasada del proceso de trabajo en vez de fallar, y nunca toca ese cálculo.

## 2.3 Alcance, definiciones y frescura

- **Un análisis por cálculo.** Las tablas autorizadas son:
  - las del catálogo del snapshot del turno;
  - las que hayan entregado en este intento `search_datasets` o `inspect_dataset` con dependencias vigentes.

  Todas deben pertenecer a `analysis_id`. El catálogo del snapshot tiene un máximo de 20 conjuntos, y una tabla encontrada después también debe poder usarse. Si el chat tiene un análisis seleccionado, solo vale ese. Un cálculo nunca vincula un chat sin selección a un análisis.
- **Rechazos sin ejecutar nada:** alias duplicados (antes de construir el diccionario), ids duplicados y tablas ajenas o desconocidas.
- **Definiciones congeladas.** Se pasan a `execute` como `definitions` y quedan visibles como `dr_runtime.DEFINITIONS`, sin cambiar la fórmula:
  - los significados declarados del modelo de datos del análisis calculado, con su revisión y si hay significados desconocidos;
  - las referencias de la memoria declarada aplicable a ese análisis, cada una con su periodo resuelto y su alcance, para que dos declaraciones sucesivas (por ejemplo, total de la fila hasta junio y precio unitario desde julio) sigan distinguiéndose.

  Tienen un máximo de 6 KiB serializados, con la cuenta de los significados y recuerdos omitidos (el plan decía 16 KiB; se bajó para que la proyección del revisor quepa en 24 KiB). Nunca incluyen memoria propuesta o en conflicto ni texto escrito por el chat.
- **Dependencias del cálculo:**
  - la versión de metadatos de cada tabla;
  - el modelo de datos `{analysis_id, revision}`, si existe.

  Se comprueban al congelar, al publicar la observación y al publicar la respuesta.

## 2.4 Presupuesto y tamaños

Todos los límites de esta sección se miden en bytes del JSON real codificado en UTF-8, con claves, metadatos y escapes incluidos, no solo sobre las cadenas de texto.

- **Como máximo 3 cálculos por turno e intento.** Cuentan las filas `reserved`, `admitted` y `refused` por igual. Un cálculo idéntico en el mismo intento no crea fila y devuelve una referencia al `tool/N` anterior. Un intento nuevo, que solo nace de un reintento explícito del propietario, tiene presupuesto nuevo.
- **Antecesor sin resolver:** antes de admitir un cálculo, el servidor busca cálculos anteriores del mismo turno, en cualquier intento, cuya ejecución no haya terminado.
  - Primero intenta la recuperación acotada.
  - Si sigue sin resolver, el cálculo nuevo no arranca: queda `refused` con el motivo `previous_unresolved`.
  - El modelo puede responder sin calcular o proponer un informe.
- **Solicitud en el diario del chat:** el código solo queda en `chat_retrievals.request` si el cálculo se ejecutó, para que el modelo pueda leerlo y corregirlo. Un cálculo rechazado o inválido guarda el propósito, las tablas, el hash y el tamaño del código, nunca el código, para que no llene el contexto por el que se rechazó. `chat_calculations` conserva la solicitud completa.
- **Observación para el modelo:** como máximo 8 KiB en UTF-8, comprobados al final sobre el JSON real. Contiene:
  - estado y error;
  - las métricas, que deben caber enteras en 6 KiB. Si no caben, el estado es `output_too_large` y el cálculo no puede citarse;
  - la evidencia, con cada operación recortada a 600 caracteres, un número máximo de elementos y la cuenta de los omitidos;
  - notas de hasta 1 KiB, con la cuenta de las omitidas;
  - extractos de stdout y stderr de hasta 1 KiB cada uno, solo si el cálculo no terminó bien. Desde `conversation-v23`, un cálculo terminado también devuelve el final de su stdout (hasta 1 KiB), si cabe en el límite de la observación. No se muestra al propietario;
  - los ids de la ejecución y del cálculo;
  - `independent_check: 'none'`.

  `executions` conserva `verification: 'pending'` y nunca se reescribe. Nunca se corta un JSON ni se publican métricas parciales como completas.
- **Contexto del autor:** el límite total de 200 000 bytes (`ctx.CONTEXT_BYTES`) sigue cubriendo todo. Antes de admitir un cálculo se reserva margen: si el tamaño del contexto actual más 28 KiB supera el límite, el cálculo queda `refused` con el motivo `context_full`. Esos 28 KiB son la solicitud con su código de hasta 8 KiB y su propósito, y dos copias de 8 KiB de la observación (el plan decía 24 KiB; no contaba el propósito ni los metadatos de la solicitud). El modelo recibe un error de herramienta que le pide responder con lo que tiene o proponer un informe. Un cálculo nunca es lo que rompe el límite: antes de seguir se mide el siguiente contexto completo con la observación añadida, y si ni siquiera el rechazo cabe, el propietario recibe una respuesta fija, sin cifras y sin otra llamada al modelo, que le propone una pregunta más concreta o un informe. La observación y la auditoría quedan guardadas.
- **Contexto de la revisión:** límite nuevo y explícito de 200 000 bytes sobre `check_context`.
  - Por cada cálculo citado, la proyección para el revisor tiene un máximo de 24 KiB serializados: código hasta 8 KiB, definiciones hasta 6 KiB con marca de omitidas, observación hasta 8 KiB y metadatos. Si aun así no cupiera, las definiciones se sustituyen enteras por una marca de omitidas.
  - Los significados declarados del análisis calculado se añaden una vez y acotados.
  - Si se omitieron definiciones, la proyección lo declara con su número. El revisor no puede suponer su contenido: un cálculo cuya interpretación dependa de una definición omitida no se aprueba.
  - Si aun así se excede el límite, el borrador se rechaza sin llamar al revisor, con el aviso «cita menos fuentes o más pequeñas». Cuenta como un intento de revisión, como los demás problemas de fuentes.

## 2.5 Informes solo con confirmación explícita

### Propuesta

- La decisión `offer_report` publica su texto tras la revisión de respuestas, como cualquier respuesta. El texto explica por qué hace falta un informe, que tarda unos cinco minutos y que sus cifras pasan una comprobación independiente. Puede incluir antes la respuesta de un cálculo rápido.
- El servidor guarda la propuesta en la tabla nueva `chat_report_offers`:
  - negocio, conversación, turno que la ofrece y análisis;
  - objetivo;
  - encargo validado, con sus informes fijados;
  - continuación congelada: referencia a hallazgo, referencias de contexto, citas históricas del propietario (incluidas las de `search_chats`), punteros a resultados revisados y la regla;
  - dependencias congeladas, igual que las construye hoy `_job`;
  - `offer_sha256` sobre todo lo anterior;
  - estado `open` o `accepted`, turno que la acepta, trabajo y fecha.

  Unicidad por turno que la ofrece.
- La respuesta incluye `report_offer`: id, objetivo, análisis y hash.
- Una decisión `investigate` ya guardada se convierte en una propuesta con un texto escrito por el servidor, sin trabajo.

### Aceptación

Es un punto de entrada aparte, no un mensaje de chat: `POST /api/chats/{chat}/accept-offer` con `business_id`, `request_key`, `offer_id` y `objective`. El propietario puede editar el objetivo, de 1 a 600 caracteres.

Todo ocurre en una sola transacción, con este orden de bloqueos:

1. Se bloquean, en este orden, la bienvenida (`onboarding.current`), la conversación, la memoria y la propuesta.
2. **Idempotencia** por conversación y `request_key`:
   - la misma clave con el mismo objetivo y la misma propuesta devuelve el mismo turno y el mismo trabajo;
   - la misma clave con otra propuesta u otro objetivo da 409;
   - otra clave sobre una propuesta ya aceptada también da 409.
3. Se inserta el turno de aceptación, con el texto «Preparar informe: <objetivo>» y `report_acceptance` (propuesta, hash y objetivo). No captura memoria ni tiene `chat_calls`.
4. La propuesta pasa a `accepted`, con el turno que la acepta.
5. Se llama a `_job(db, chat, turn, offer)`.
6. Se guarda el trabajo en la propuesta.

Cualquier fallo deshace todo.

### Nuevo `_job`

- Nunca lee `chat_calls`.
- Exige que la propuesta esté `accepted` por este mismo turno.
- Vuelve a validar las dependencias congeladas:
  - las del turno que hizo la propuesta (snapshot y eventos);
  - la frescura de cada conversación citada;
  - que el conjunto de datos siga disponible;
  - que el análisis del chat no haya cambiado.
- Usa el objetivo confirmado por el propietario como objetivo del informe, el encargo congelado como orientación y la continuación congelada como contexto.

### Otras reglas

- `run()` deja de tener un camino que cree trabajos. Un turno que ya tiene trabajo se reanuda como hoy, sin pedir otra confirmación.
- La guía de bienvenida conserva su botón explícito «Crear mi informe».
- **Interfaz:** debajo de la respuesta aparece una tarjeta con el objetivo editable y el botón «Preparar informe». La clave de petición se guarda en el borrador local, para que un doble clic la reutilice. Una vez aceptada, la tarjeta enlaza el trabajo.

## 2.6 Respuesta, revisión, presentación e historia

### Qué puede sostener una cifra

Solo un cálculo terminado del mismo turno e intento, con las métricas completas y las dependencias vigentes. Uno fallido, sin resolver o demasiado grande puede citarse para explicar el fallo, pero nunca sostiene cifras. Los cálculos solo se adjuntan a la respuesta cuando han terminado bien.

### Revisión

- Para cada cálculo citado, `_answer` añade a la proyección del revisor:
  - propósito y código;
  - tablas, con los nombres originales de sus alias;
  - definiciones congeladas;
  - métricas, evidencia, notas y etiqueta.
- La proyección de cada cálculo citado lleva `declared_meanings`: los significados declarados congelados del análisis calculado, aunque el autor no haya citado el modelo de datos.
- **Nuevas reglas de `REVIEW_SYSTEM`:**
  - Comprobación ligera de coherencia entre el propósito y el código: fechas, filtros, unidades, grano, precio por unidad frente a total de la fila y uniones declaradas.
  - Se aprueban la paráfrasis y el redondeo de las métricas devueltas.
  - Una operación nueva sobre esos resultados necesita otro cálculo.
  - Nunca se dice «comprobado» ni «verificado de forma independiente».
- Se revisan enteras las prohibiciones repartidas por `SYSTEM` (cálculo en prosa, nuevas cifras con `investigate`) y por `REVIEW_SYSTEM` (sumas y tendencias solo con informe revisado), no una sola frase.

### Presentación

- `response.calculations` contiene, por cada cálculo citado y terminado:
  - ids del cálculo y de la ejecución;
  - propósito y código;
  - tablas, con sus nombres originales;
  - métricas, evidencia recortada y notas;
  - la etiqueta «Cálculo rápido, sin comprobación independiente».

  Queda guardado en la respuesta del turno. Es el registro privado del negocio y del turno, con fórmula, resultado, fuentes y versiones, para poder responder después a «qué calculaste ayer y cómo». `executions` conserva el registro completo.
- **Interfaz:**
  - La etiqueta se ve junto al resultado aunque el código esté plegado.
  - El código va en un `<pre>` escapado: nunca se ejecuta ni se interpreta como HTML o Markdown.
  - Funciona en modo oscuro, en anchura de móvil y en español e inglés con `tr()`.

### Historia

- `dialogue_reply` añade por cada cálculo una línea acotada: «cálculo rápido histórico, sin comprobación independiente: propósito = métricas». Respeta su límite de 4000 caracteres, con recorte explícito.
- `open_chat` devuelve la misma proyección.
- El prompt explica que un cálculo histórico dice qué se calculó entonces. Una cifra vigente necesita un cálculo nuevo.

## 2.7 Consumidores

- **Adaptación de decisiones en `conversations.run`:** los campos nuevos son opcionales y sus incompatibilidades se comprueban. `Action` recibe `calculation` y `report_offer`.
- **`sources_for`:** etiqueta «Cálculo rápido (sin comprobación independiente)» para `calculate`. El adjunto de `open_report` en `_answer` no cambia. Las ramas antiguas `catalog` y `recall` siguen filtrando por herramienta.
- **Actividad (`observability/collector.py`):**
  - las observaciones `calculate` llevan una etiqueta según su estado («Cálculo rápido terminado» o «Cálculo rápido fallido»);
  - las ejecuciones con clave `chat-calc:` cuelgan del turno, a través de `chat_calculations`, con rol de chat y la etiqueta «Cálculo rápido».

  La propiedad y la recuperación nunca dependen de los enlaces de actividad.
- **Monitor interno:** muestra la procedencia del chat en estas ejecuciones. La observación del modelo nunca incluye `runtime` ni `host_config`.
- **Evaluaciones (`evaluation/runner.py`, `quality_runner.py`):** las ejecuciones `chat-calc:` no cuentan como ejecuciones de investigación.
- **Recuperación previa de trabajos antiguos:** solo ejecuciones que no son del chat (2.2).

## Pruebas

- **Puntos de interrupción:**
  - antes y después de crear la fila de `executions`;
  - con el cálculo terminado pero sin observación;
  - recuperación de un cálculo terminado con Docker caído o con el manifiesto cambiado, sin llamar a `execute`;
  - `preparing` y limpieza pendiente nunca pasan a interrumpidas sin retirar el contenedor;
  - recuperación acotada al reintentar, con el bloqueo libre y ocupado;
  - antecesor sin resolver que bloquea cálculos nuevos;
  - dos procesos de trabajo.
- **Alcance y datos:**
  - datos o significados cambiados entre la decisión, la ejecución y la publicación;
  - tablas descubiertas fuera de las 20 del catálogo;
  - alias o ids duplicados y tablas ajenas;
  - límite de 64 MiB de entrada;
  - límite UTF-8 del código.
- **Tamaños:**
  - sobre un contexto base cargado (memoria en su límite de 48 000 bytes, catálogo completo, 12 respuestas del diálogo en su límite y resultados de herramientas grandes), un cálculo sin margen queda `context_full` en vez de romper el límite;
  - tres cálculos citados en el peor caso caben en la revisión o producen el aviso determinista;
  - un resultado de más de 8 KiB se recorta o queda `output_too_large`;
  - un cálculo fallido no se adjunta;
  - presupuesto con fallos, duplicados e intentos.
- **Propuestas:**
  - una respuesta con propuesta no crea trabajo;
  - se rechaza la aceptación de una propuesta de otro chat o de otro negocio, desactualizada o ya consumida;
  - el doble clic lleva al mismo trabajo;
  - la misma clave con otro objetivo da 409;
  - una decisión `investigate` reproducida se convierte en propuesta, sin trabajo;
  - `_job` sin propuesta aceptada falla.
- **Consumidores:** etiquetas y padres en la actividad, y la recuperación de trabajos antiguos con un cálculo vivo.
- **Integración con Docker real:** un modelo programado que calcula y luego responde; se omite si el sandbox no está disponible.
- **Interfaz:** etiqueta visible con el código plegado, código escapado y tarjeta de propuesta.
- El aislamiento del sandbox ya lo cubre `tests/test_execution.py`.

## Validación real

**Hecha el 12 de octubre de 2026,** con aprobación de gasto y el Mac despierto. Un negocio de prueba con tres archivos (citas, encuestas y profesionales), en una base de datos aparte, con el modelo real del chat y un límite de gasto de 3 USD. Las cifras se compararon con un cálculo hecho a mano sobre los mismos CSV.

| Pregunta | Resultado | Tiempo | Coste |
|---|---|---|---|
| Total de citas y cuántas se realizaron | Correcto (12 290 y 10 790) | 19,1 s | 0,007 USD |
| Porcentaje de «no presentado» | **Incorrecto: 0 %** (ver abajo) | 16,2 s | 0,009 USD |
| Citas realizadas por profesional en marzo de 2025 | Correcto (172, 181 y 141) | 12,3 s | 0,007 USD |
| Puntuación media de las encuestas | Correcto (8,50) | 6,6 s | 0,003 USD |
| Por qué perdemos pacientes y qué cambiar | Propuesta de informe, sin trabajo creado | 24,2 s | 0,009 USD |
| Comparar profesionales por mes, canal y tipo, con causas | Propuesta de informe, sin trabajo creado | 7,9 s | 0,002 USD |
| Porcentaje de «no presentado», repetida con la corrección | Correcto (4,78 %) | 15,3 s | 0,009 USD |

- **El fallo:** el modelo filtró por «no presentado», como lo escribe el propietario en su descripción, pero en los datos el valor guardado es `no_presentado`. El filtro no encontró nada y la respuesta dijo 0 %, aunque avisando de que solo había buscado esa escritura exacta. La revisión lo rechazó una vez y aprobó la segunda redacción.
- **La corrección** (`conversation-v21`): antes de filtrar por un texto, el programa lee los valores realmente guardados de esa columna y filtra por los encontrados, y un filtro que no encuentra nada se trata como un error que hay que corregir, no como un resultado. La revisión rechaza una cifra que dependa de un filtro de texto sin coincidencias si el código no leyó los valores guardados.
- **Repetida en un chat nuevo,** el programa leyó los valores, falló a propósito al no encontrar «no presentado», leyó en el error los valores guardados y corrigió el filtro: 4,78 %, correcto.
- Cada ejecución en el sandbox tardó entre 0,44 y 0,53 s. El resto del tiempo son llamadas al modelo: la decisión, la respuesta, su revisión y la extracción de memoria.
- Las dos preguntas grandes acabaron en una propuesta con el objetivo redactado y no crearon ningún trabajo. Una de ellas no mencionó en su texto los cinco minutos ni la comprobación independiente; la tarjeta de la propuesta los muestra siempre.
- **Coste total:** 0,044 USD según el límite de gasto (0,033 USD según el catálogo de precios), 33 llamadas al proveedor, sin llamadas de uso incierto.

**Prueba real del paso 3 (13 de octubre de 2026):** se repitió el fallo del filtro de texto. El programa imprimió los valores guardados de `estado`, pero la observación de un cálculo terminado no incluía stdout. Ni el modelo ni la revisión los vieron: el modelo filtró por `no presentado`, cuando los datos tienen `no_presentado`, y la revisión aprobó 0,0 %, porque el código «había leído» los valores. Corrección (`conversation-v23`):

- la observación incluye el final de lo que imprime el programa;
- el chat debe imprimir los valores por los que filtra y comprobarlos antes de responder;
- la revisión rechaza un filtro de texto cuyo valor no aparece entre los valores impresos.

En la misma prueba, cuando el modelo devolvía una propuesta de informe incompleta, el turno fallaba. Ahora esa decisión se rechaza sin llamar al revisor y se devuelve al modelo para que la corrija, como una respuesta rechazada.

## Orden de trabajo y commits

1. Esquema, módulo de cálculo rápido, límite de entrada de `execute` y recuperación acotada.
2. Contrato del chat, integración en el bucle, presupuestos y observación.
3. Respuesta, revisión, presentación e historia, con los cálculos en la interfaz.
4. Propuestas, punto de aceptación, nuevo `_job` y tarjeta en la interfaz.
5. Consumidores: actividad, monitor, evaluaciones y recuperación antigua.
6. Documentación y resultado.

Cada parte es un commit local en `feature/quick-chat-calculation`. Nada se sube sin que el propietario lo pida.
