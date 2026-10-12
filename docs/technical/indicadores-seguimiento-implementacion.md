# Implementación: indicadores guardados y registro de seguimiento

Fecha: 12 de octubre de 2026.

Desarrolla el paso 3 del [plan de contexto compartido y cálculo rápido](<../product/contexto-compartido-y-calculo-rapido-plan.md>). El plan lo acordaron Claude y Codex en tres versiones; Codex aprobó la tercera. Claude lo implementa y Codex revisa los cambios. La prueba real final necesita la aprobación del propietario.

**Estado: plan acordado; implementación en curso en `feature/saved-indicators`.**

## Decisiones del propietario

Tomadas el 12 de octubre de 2026:

- **Un indicador que falla por la estructura de los datos** queda no disponible, con el motivo detectado, y el propietario tiene una opción de reparación:
  1. el agente propone una fórmula nueva;
  2. se ejecuta sobre los datos anteriores, si existen, y se compara con la cifra guardada;
  3. el propietario confirma con un botón.

  Los fallos pasajeros se reintentan solos con la misma fórmula.
- **El registro de seguimiento no es un resumen de un modelo.** Cada tema es una acción de un informe nativo copiada tal cual («qué comprobar», «si se confirma», «si no»), con el titular y la fecha del informe, el estado que pone el propietario y, si lo hay, el valor del indicador enlazado. Un informe nuevo recibe solo los temas abiertos, los más recientes primero y con un tope de tamaño. Los cerrados solo se cuentan.

## Principios

- **Sin modelo al recalcular.** Un indicador se recalcula con su código fijo y visible, sin llamar a un modelo. No se afirma que un programa de Python arbitrario sea matemáticamente determinista: se pide que la fórmula dependa solo de las tablas y las definiciones (sin reloj ni azar) y el código queda a la vista.
- **Nunca se adapta en silencio.** Si la fórmula deja de cuadrar con los datos o con su significado, el indicador queda no disponible. Solo el propietario activa una versión nueva.
- **Sin comprobación independiente.** Un indicador guardado sale de un cálculo rápido y conserva esa etiqueta: «Indicador guardado · fórmula fija recalculada sin modelo · sin comprobación independiente».
- **Se mantienen las reglas de los pasos 1 y 2:**
  - memoria declarada en los informes;
  - el encargo del chat solo orienta;
  - los informes solo empiezan con una propuesta aceptada;
  - el código solo corre en el sandbox aislado.
- **Cifras de informe.** Una cifra de un informe no puede pasar directamente a indicador, porque el informe no guarda su fórmula (desviación respecto al plan de producto). La interfaz propone pedirla al chat como cálculo rápido.

## 3.1 Esquema

Todas las tablas usan claves foráneas compuestas con el negocio y cada consulta filtra por negocio. El proceso de trabajo usa siempre el negocio de cada elemento, nunca el negocio activo.

- **`saved_indicators`:** negocio, conjunto lógico (`dataset_id`), nombre de hasta 120 caracteres, estado `active` o `retired`, revisión para concurrencia optimista y fechas. Retirar un indicador detiene los intentos nuevos y conserva la historia y los enlaces.
- **`indicator_versions`:**
  - versión y estado: `proposed`, `active`, `superseded` o `discarded`;
  - código y su hash;
  - tablas: alias, clave de archivo normalizada y nombres originales;
  - claves de métrica: de 1 a 10, sin repetir;
  - definiciones: exactamente lo que recibe el programa;
  - firma semántica y su hash (3.3);
  - procedencia: turno, cálculo, ejecución, análisis, versión de datos y hashes;
  - versión de datos desde la que se aplica;
  - recibo de comparación (3.4);
  - fechas.

  Solo una versión activa por indicador.
- **`indicator_values`:**
  - análisis y versión de datos;
  - estado: `pending`, `completed`, `unavailable` o `revoked`;
  - motivo, como código y texto acotado para el propietario;
  - métricas, solo las claves elegidas;
  - ejecución y último intento.

  Único por indicador, versión y análisis.
- **`indicator_attempts`** (diario de intentos):
  - qué se calcula: el valor o la comparación;
  - número de intento;
  - identidad congelada: hash del código, correspondencia de tablas con su versión de metadatos, hash de definiciones y de firma;
  - entorno de ejecución efectivo;
  - clave `indicator:<id del intento>`;
  - admisión (`reserved`, `admitted` o `refused`);
  - resultado (`completed`, `transient` o `structural`) y motivo;
  - ejecución y fecha del siguiente intento.
- **Recibos de petición:** las peticiones de crear, proponer, confirmar y cambiar de estado guardan su clave, el hash de la solicitud estática y el resultado. La misma clave con otra solicitud da 409.
- **`knowledge_heads`:** revisión del conocimiento de indicadores y de seguimiento por negocio. Sube bajo `memory.lock` cuando cambia lo que ve el chat, decidido por el hash de esa proyección, nunca por reclamar o aplazar un intento.

## 3.2 Crear un indicador

Lo hace siempre el propietario, con un botón, a partir de un cálculo ya publicado.

- **Petición:** `POST /api/indicators` con negocio, clave de petición, turno, cálculo, nombre y claves de métrica.
- **Condiciones:**
  - el cálculo aparece en las cifras publicadas de ese turno, y el chat no está borrado y es del mismo negocio;
  - el cálculo fue admitido y su ejecución terminó, sobre el mismo análisis;
  - coinciden los hashes del código y de las definiciones;
  - las claves elegidas están en las métricas publicadas.
- **Revalidación,** bajo el mismo orden de bloqueos:
  - las tablas siguen vigentes y el análisis no está corregido;
  - la semántica aplicable ahora es compatible con la firma congelada.

  Un análisis sustituido por una actualización sirve: su valor es la historia de esa versión.
- **El primer valor se copia de esa ejecución,** sin repetirla. Después, la reconciliación (3.3) encola las versiones de datos posteriores que correspondan.

## 3.3 Recálculo

### Proceso de trabajo

- Primero los trabajos de informe, como hoy.
- Después, de forma alterna y acotada, un turno de chat y un solo intento de indicador por pasada.
- Los reintentos se aplazan con `next_attempt_at`, sin bucles de espera activa.
- Ningún bloqueo ni transacción sigue abierto mientras corre Docker.

### Intentos

Se aplica el principio de reservar y resolver del paso 2:

- **La fila del intento,** con su identidad congelada y su clave, se escribe antes de tocar Docker.
- **Al recuperar:**
  - un intento admitido se lee con `get_execution`, sin recalcular su huella contra el entorno instalado;
  - un intento reservado sin ejecución puede admitirse;
  - una ejecución abierta nunca se reetiqueta y bloquea ese valor hasta que se recupera.
- **Fallo pasajero** (sandbox no disponible u ocupado antes de admitir, ejecución interrumpida y recuperada, fallo de Docker o de transporte después de admitir): se crea un intento nuevo, con clave nueva y la misma fórmula, tras el aplazamiento.
- **Fallo estructural** (error del programa, resultado que no cumple el contrato, métrica ausente, fallo de correspondencia o de semántica): el valor queda no disponible con su motivo.
- **Tiempo o recursos agotados:** se reintenta una vez y después queda no disponible (`resource_limit`).
- **Clasificación:** se hace por la causa (estado, problema y admisión de la ejecución), no buscando texto en el error, que solo se guarda como detalle acotado.

### Correspondencia de tablas

Cada alias se empareja con la tabla de la versión nueva cuyos nombres originales contienen exactamente un nombre con la misma clave de archivo:

- ninguna coincidencia: `missing_table`;
- varias coincidencias: `ambiguous_table`.

Nunca se toma la primera de una lista, y la correspondencia debe ser uno a uno.

### Firma semántica

Es conservadora y cubre todas las columnas de cada tabla emparejada:

- nombres y esquema de las columnas;
- significado declarado, unidad, conversión y estado semántico;
- descripción y grano de la tabla;
- la memoria declarada de definición o disponibilidad aplicable a esas tablas, con su periodo, y con su alcance trasladado solo a través de la correspondencia explícita.

Lo desconocido y lo omitido se registran de forma explícita. Los identificadores y las revisiones van en la procedencia, no en la firma.

- Cualquier diferencia: `meanings_changed`.
- Algo declarado antes que ahora es desconocido: `meanings_unknown`.
- Omisiones que impiden comparar: `meanings_unverifiable`.

Un cambio que quizá no afecta a la fórmula también detiene el indicador; la reparación del propietario es la salida.

### Cola y reconciliación

- **Al subir datos:** `dossier.upload` encola valores pendientes en su misma transacción, solo para una versión nueva lista (no reutilizada ni parcial).
- **Reconciliación:** `reconcile(db, business)` es idempotente y solo rellena huecos. Se ejecuta después de crear o confirmar y desde el proceso de trabajo: cada versión activa por cada versión de datos elegible desde su `applies_from` que no tenga valor.
- **Versiones anteriores:** conservan la historia de la fórmula anterior.

### Correcciones

- Los valores de un análisis corregido pasan a `revoked`. Se conservan para auditoría, pero nunca son el valor vigente ni sirven de base de comparación. Se comprueba antes y después de ejecutar.
- **Valor vigente:** el de la última versión de datos elegible, no el calculado más tarde. Un resultado antiguo que termina tarde no desplaza a uno pendiente o no disponible más nuevo.
- **Para publicar un resultado** debe seguir siendo cierto que la versión está activa, el análisis es elegible y la firma coincide. Se vuelve a comprobar bajo bloqueo.
- **`library_hidden`** solo afecta a la visibilidad: no retira indicadores.

## 3.4 Reparación

- **El chat** ve un catálogo acotado de indicadores y tiene una herramienta nueva, `inspect_indicator(id)`, que devuelve el código, las definiciones, la correspondencia y los últimos valores de uno solo, con un tamaño acotado. Con eso propone un cálculo rápido nuevo.
- **Proponer una versión:** `POST /api/indicators/{id}/versions` con negocio, clave, turno, cálculo y `expected_active_version_id`. Crea una versión propuesta, validada como en 3.2, y encola una comparación. No se ejecuta Docker dentro de la petición HTTP ni bajo bloqueos.
- **Comparación:**
  - la base es el último valor completado y elegible de la versión activa, por versión de datos;
  - se ejecuta el código nuevo, con sus definiciones nuevas, sobre las tablas de esa base emparejadas por la versión nueva;
  - para cada métrica, los booleanos, textos y nulos se comparan solo con el mismo tipo y de forma exacta, y los enteros entre sí de forma exacta. Un entero con un decimal, o dos decimales, se comparan como números con la política fija `indicator-compare-1`: |a−b| ≤ máx(1e−9, 1e−9·máx(|a|,|b|)). Un booleano nunca es un número: 1 y 1,0 pueden coincidir; verdadero y 1, no;
  - se guardan los valores originales y las diferencias, con el estado `pending`, `match`, `mismatch` o `unavailable` y su motivo (por ejemplo, que las columnas nuevas no existían en esos datos);
  - el recibo queda congelado con su hash.
- **Confirmar:** `POST .../versions/{v}/confirm` con clave, `expected_active_version_id` y el hash del recibo vigente.
  - Se puede confirmar con resultado igual, distinto o imposible de comparar: el botón es la decisión del propietario, no una prueba superada.
  - Al confirmar se vuelve a validar como al crear.
  - Si el cálculo nuevo ha perdido vigencia (datos corregidos, una definición retirada, un cambio de unidad), se rechaza la activación y se pide un cálculo actualizado.
  - Si la base de comparación se corrige después de la comparación, el recibo antiguo se conserva para auditoría pero deja de valer: se encola otra comparación con la siguiente base elegible o se crea un recibo `unavailable` con el motivo. La confirmación exige el hash del recibo vigente.
  - Con dos propuestas, cuando una se confirma, la otra ya no puede sustituirla con la versión activa antigua.
  - Al activar, la versión anterior queda sustituida, `applies_from` pasa a ser la versión de datos del cálculo nuevo, se copia su valor y la reconciliación encola las versiones posteriores.
  - Nada se activa solo porque coincida.

## 3.5 Registro de seguimiento

- **`follow_up_actions`:** instantánea inmutable por revisión y posición:
  - documento, revisión y `block_id` (posicional);
  - título de la prioridad;
  - contenido completo de cada rama, con la semántica de `blocks._content_lines`, sin colapsar espacios;
  - rótulos;
  - `content_sha` de rótulos, contenido y título de la prioridad;
  - titular y fecha del informe, conjunto y análisis;
  - avisos de la comprobación y caducidad, como metadatos.
- **`follow_ups`:** el tema del propietario:
  - documento e instantánea actual;
  - estado del propietario (`proposed`, `checked` o `closed`) y disponibilidad del sistema (`available` o `withdrawn`), por separado;
  - nota;
  - enlace a un indicador con su versión, valor, clave de métrica y cifra, congelado al comprobar;
  - revisión.

  `follow_up_events` guarda la auditoría.
- **Un tema por cada aparición de una acción.** No hay unicidad por documento y `content_sha`: dos acciones idénticas son dos temas.
- **Paso a una revisión nueva:** el tema y su estado solo pasan con una correspondencia exacta e inequívoca:
  - primero, misma posición y mismo `content_sha`;
  - después, para movimientos, un `content_sha` que aparece una sola vez entre las instantáneas antiguas sin emparejar y una sola vez entre las nuevas.

  Ante cualquier duplicidad o ambigüedad nacen temas propuestos nuevos y los antiguos quedan retirados con su estado. Nunca se copia un estado a dos temas, ni se empareja por parecido ni con un modelo.
- **Sincronización:**
  - incremental, en las mismas transacciones que publican una revisión de un informe nativo y que lo borran o restauran;
  - más una reconciliación determinista paginada, con una marca por documento y revisión, para los informes existentes y los eventos perdidos. No se usa la selección del paso 1, que tiene un tope de 50.
  - La retirada se decide por documento, nunca por no aparecer en una página.
  - Al borrar un informe, sus temas se retiran conservando el estado. Al restaurarlo, vuelven con el estado anterior.
- **Estados:**
  - abierto significa propuesto o comprobado;
  - solo el propietario cierra;
  - «comprobado» es una declaración del propietario, nunca una comprobación del sandbox;
  - petición: `POST /api/follow-ups/{id}/state` con clave, estado, nota, enlace opcional y revisión esperada.

## 3.6 Consumidores

- **Núcleo compartido** (`business-knowledge-3`):
  - **Indicadores:** catálogo de hasta 4 KiB serializados, con nombre, id, último valor elegible por métrica con su versión de datos y periodo, estado, motivo y etiqueta. Entran elementos enteros o se cuentan los omitidos. Un último estado no disponible nunca se esconde detrás de un valor anterior.
  - **Temas abiertos:** hasta 6 KiB serializados, del informe más reciente al más antiguo, con elementos enteros y sus ramas completas o la cuenta de omitidos y la marca de texto parcial. Cerrados y retirados solo se cuentan.
- **Resumen histórico del paso 1:** deja de listar las acciones («sus acciones están en el registro de seguimiento») para no presentar como pendientes las ya cerradas. Los archivos de informes anteriores siguen como fuentes atribuidas.
- **Encargo** (`blocks-brief-6`):
  - párrafo «Indicadores guardados»: fórmula fija confirmada por el propietario, recalculada sin modelo y sin comprobación independiente;
  - párrafo «Temas abiertos»: propuestas de informes anteriores con el estado que les dio el propietario, para que el informe diga qué muestran los datos actuales;
  - la procedencia congela lo recibido: ids, versiones y métricas de los valores, e ids y estados de los temas;
  - `checker_context` recibe las mismas proyecciones.
- **Comprobador:** una cifra de indicador o un tema citados como tales son una atribución. Solo se confirman recalculando el mismo periodo y filtros desde los CSV. El código del indicador no se le entrega y no se montan archivos nuevos.
- **Chat** (`conversation-v22`):
  - el núcleo va en el snapshot;
  - `fresh()` compara `knowledge_heads`;
  - las observaciones de `inspect_indicator` añaden dependencias;
  - se valida antes de publicar la respuesta y antes de aceptar una propuesta.

  Los informes entregados y los trabajos en curso no se invalidan por cambios posteriores de estado de un tema.
- **`inspect_indicator`:** herramienta solo del chat.
  - `Request` gana el nombre para que el chat pueda pedirla, `retrieval.retrieve` la rechaza de forma explícita (el agente antiguo nunca la usa) y `conversations` la despacha.
  - Tamaño máximo de 12 KiB serializados, con la misma medición del siguiente contexto que los cálculos: si no cabe, una observación mínima de rechazo; si ni eso cabe, la respuesta fija sin cifras. También funciona al recuperar el diario.
- **Límites:** se miden en bytes del JSON real. Hay una prueba del peor caso con el contexto base del chat cerca del límite de 200 000 bytes y en el contexto de la revisión de respuestas.
- **Inicio:**
  - tipo de fuente propio, `indicator`, sin ids de informe ni de trabajo inventados;
  - ids de tarjeta estables, `indicator:<id>:<métrica>`, para que lo fijado sobreviva al recálculo;
  - sin color favorable salvo que esté declarado;
  - con la etiqueta;
  - los no disponibles se muestran con su motivo;
  - citar y editar quedan desactivados donde no se admiten.
- **Interfaz:**
  - bajo un cálculo rápido, «Guardar como indicador» (nombre y casillas de métricas) y «Guardar como nueva versión de…»;
  - en Inicio, una sección «Indicadores y seguimiento» con los indicadores (valor, versión, estado, motivo, versión propuesta con su comparación y botón de confirmar) y los temas abiertos con botones de estado.
- **Ejecuciones que no son de informes:** un único ayudante con los prefijos `chat-calc:` e `indicator:`, que usan `open_report_runs` y `recover_executions(report_runs_only=True)`, más la recuperación acotada de los intentos de indicador. Llega en el primer commit que encola intentos. Las etiquetas de actividad y la documentación vienen después.

## Pruebas

- **Interrupciones:** después de reservar, de admitir, de terminar Docker y antes de persistir.
  - Al recuperar no se repite nada.
  - Un fallo pasajero ya terminado crea un intento nuevo; uno sin resolver u ocupado, no.
  - Un informe antiguo nunca toca una ejecución de indicador.
- **Correspondencia y firma:**
  - nombres duplicados, colisiones, renombres y alias;
  - la firma con SQL dentro de una cadena, una columna a través de una variable, `SELECT *` y nombres construidos;
  - un cambio de significado o de unidad sin cambiar las cabeceras detiene el indicador.
- **Concurrencia:**
  - subida simultánea con crear o confirmar;
  - dos propuestas con una confirmación desfasada;
  - corrección mientras corre Docker;
  - retirada y actualizaciones fuera de orden;
  - confirmar después de corregir el objetivo, de corregir la base, de retirar una declaración o de cambiar una unidad.
- **Registro:**
  - más de 50 informes con una acción antigua abierta;
  - acción larga con una condición al final;
  - mismo `bN` con contenido distinto;
  - rótulos propios;
  - dos acciones idénticas, una cerrada y otra propuesta, y luego reordenar, borrar una o insertar una tercera;
  - borrar y restaurar conservando el estado;
  - un tema cerrado nunca aparece como abierto.
- **Métricas y comparación:**
  - métricas nulas, booleanas, de texto y decimales;
  - estados de comparación;
  - definiciones omitidas o desconocidas;
  - datos corregidos excluidos como base.
- **Aislamiento:** negocio ajeno en cada punto de entrada, enlace y clave, y huellas de solicitud estática.
- **Inicio:** estabilidad de lo fijado y tipo de fuente.
- **Límites:** límites reales en bytes con Unicode y frescura al publicar.

## Validación real

Requiere aprobación de gasto y el Mac despierto.

1. Subir una versión nueva de los datos de prueba: los indicadores se recalculan sin modelo.
2. Romper una columna a propósito: el indicador queda no disponible, se repara con el chat y se confirma la versión 2.
3. Un informe recibe los indicadores y los temas abiertos y los trata como lo que son.

## Orden de trabajo y commits

1. Esquema, creación, intentos y proceso de recálculo, correspondencia y firma, correcciones y el ayudante de ejecuciones que no son de informes.
2. Reparación: versión propuesta, cola de comparación y confirmación.
3. Registro de seguimiento: instantáneas, temas, sincronización, reconciliación, estados y auditoría.
4. Consumidores: núcleo, cambio del resumen histórico, encargo y comprobador, herramienta del chat y revisiones de conocimiento.
5. Puntos de entrada e interfaz: botones del chat y tarjetas y sección de Inicio.
6. Observabilidad y documentación.

Cada parte es un commit local en `feature/saved-indicators`. Nada se sube sin que el propietario lo pida.
