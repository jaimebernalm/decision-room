# Contexto compartido y recuperación del agente — 2.5.3

Implementado el 23 de septiembre de 2026. [Validación](../validation/2026-09-23-context-check.md). Continúa el contrato de [memoria](memory.md) y deja preparado el adaptador de conversaciones de 2.5.4.

## Punto de partida y ampliaciones

Al crear una sesión, `memory/context.py` guarda un manifiesto transaccional en PostgreSQL. El punto de partida contiene identidad/nombre del negocio, todos los recuerdos aplicables mientras quepan, dudas y conflictos, periodo de la petición y catálogo del lote. La petición actual permanece en `owner_context`; la web entrega su objetivo allí, sin volver a concatenar la descripción histórica del formulario. Las declaraciones persistentes llegan por la memoria versionada, evitando que una descripción antigua reactive una retirada.

Se filtra por negocio, fuente/análisis y solapamiento temporal. Fechas desconocidas permanecen desconocidas y amplían conservadoramente el ámbito. Los cinco registros de muestra no acreditan cobertura temporal. El catálogo proporciona descripción del lote, nombres, columnas, número de registros y versión del archivo; la inspección añade perfil/muestras y aclaraciones relacionadas. Descubrir otra tabla no autoriza ejecutarla en el lote actual: seleccionar ese conjunto para una nueva pregunta corresponde al adaptador de 2.5.4.

El bucle de herramientas es común a planificación, investigación y revisión. El agente decide cuándo necesita ampliar el contexto, con la acción estructurada `retrieve` y un contrato sin SQL libre:

| Herramienta | Resultado |
|---|---|
| `search_datasets` | Descripciones y referencias de tablas del negocio; búsqueda textual PostgreSQL en título, nombres y columnas |
| `inspect_dataset` | Perfil acotado, versión, cobertura conocida/desconocida y memoria vinculada a esa fuente |
| `search_memory` | Recuerdos aplicables al lote o a una tabla indicada; conserva definiciones, disponibilidad y dudas materiales aunque no coincidan con el texto buscado |
| `search_reports` | Antecedentes aprobados, vigentes y compatibles con el periodo; puede limitarse a una tabla/lote |
| `open_report` | Informe original, ámbito, versión de aprobación y referencias de cálculos; aplica los controles de publicación existentes |
| `open_evidence` | Código, resultado y procedencia del cálculo citado por un informe previamente abierto; comprueba integridad |

Las referencias se comprueban antes de entregar contenido. Los resultados históricos no acreditan cifras nuevas ni sustituyen la revisión de la investigación actual. Un recuerdo `result_reference` entrega un enlace, no su posible prosa numérica: hay que abrir el original vigente. Los recuerdos propuestos/conflictivos o con fechas ambiguas no confirman definiciones. Las referencias de planificación admiten `memory` y `fact-id@revision`; el ID sin revisión solo se acepta cuando es inequívoco. Una aclaración de otra fuente no se acepta como definición del lote actual.

## Manifiesto, evidencia y recuperación

- `context_manifests`: punto de partida inmutable, objetivo, ámbitos, periodo, reglas, límites, metadatos originales y motivo de invalidación.
- `context_retrievals`: peticiones/respuestas y dependencias por decisión y ordinal; no se sobreescriben en un reintento.
- `agent_calls.context_payload`: contexto exacto entregado en cada llamada, incluido el manifiesto y sus ampliaciones. Es información privada, igual que los checkpoints.
- La identidad de conocimiento del cálculo incorpora el contexto inicial. Las ejecuciones conservan `context_manifest_id` y su clave de conocimiento; informes y cálculos enlazan sus sesiones/manifiestos originales.

El manifiesto acredita entrega, no qué utilizó el modelo internamente. Cada fase recibe las mismas versiones iniciales y las ampliaciones previas. Una decisión interrumpida reproduce el contexto de su primera llamada y sus recuperaciones guardadas, sin cambiar claves por consultas posteriores de otros roles. Se conservan llamadas inciertas y el permiso explícito de reintento ya existente.

Límites actuales: 48 KB de memoria/resultado de herramienta, 200 KB de contexto completo y 12 recuperaciones por sesión, dentro de los presupuestos de llamadas de cada fase. El catálogo inicial muestra hasta 20 tablas; las búsquedas muestran hasta 10 resultados por petición; los antecedentes examinan hasta 50 candidatos textuales recientes. Se indican resultados adicionales posibles. No hay paginación general ni compresión automática. Si el contexto material no cabe, se pausa con diagnóstico para acotar fuentes/periodo; no se eliminan dudas para ajustarlo al límite.

## Correcciones, tiempo y publicación

Una escritura de memoria adquiere el bloqueo de la cabecera del negocio. Dentro de la misma transacción comprueba los manifiestos y marca investigaciones e informes afectados como obsoletos. Se revisa el conjunto aplicable, no solo los IDs seleccionados: una duda o definición nueva también puede invalidar una sesión. Las dependencias de informes recuperados se comprueban transitivamente, incluidas retenciones independientes y cambios de fuente. Ante un ámbito desconocido, la invalidación es conservadora.

Las prioridades orientan nuevas consultas sin retirar por sí solas cálculos históricos. Su retirada sí bloquea la reproducción de contextos que las recibieron. Los cambios de otro negocio, fuente o periodo no invalidan el trabajo que queda fuera de su ámbito. Extraer una respuesta ya suministrada en su propia sesión no invalida esa sesión por duplicar conocimiento; una corrección posterior sí lo hace. Otras sesiones reciben la aclaración a través de la misma memoria.

`change(..., action='correct', change_kind='historical')` es el comportamiento predeterminado. Para un cambio que comienza en una fecha conocida, usar `change_kind='future'` y `valid_from`: conserva la revisión previa para el intervalo anterior y abre la nueva desde esa fecha. Exige el mismo tema/ámbito y una declaración previa; no inventa el año de una fecha ambigua. La retirada elimina el recuerdo del contexto activo. No elimina los originales ni las revisiones auditables.

`agent.start` y `agent.replan` aceptan `request_period={'from': 'YYYY-MM-DD', 'until': 'YYYY-MM-DD'}`; omitirlo conserva límites desconocidos. Replanificar hereda el periodo si no se proporciona otro. El formulario actual no tiene selector de periodo: sus sesiones se tratan conservadoramente; el adaptador de chats podrá suministrar este contrato al interpretar o aclarar la petición.

Se comprueba vigencia antes/después de llamadas, antes de Python, al reanudar y al finalizar. Una corrección durante Python conserva la evidencia producida pero impide completar/publicar ese trabajo. El último cambio de estado de publicación comparte el bloqueo con las escrituras de memoria. Las lecturas/exportaciones de informes también verifican vigencia, y mantienen el bloqueo durante la construcción del resultado. Las copias HTML ya descargadas siguen siendo instantáneas históricas: no se pueden retirar retroactivamente del equipo del cliente.

La web oculta el informe obsoleto y ofrece **Recalcular con la memoria actual**. Crea una sesión sucesora y conserva la anterior. La vinculación permite recuperar un cierre entre crear la sesión y actualizar el trabajo web. Durante la cola, la página sigue consultando el progreso. El trabajador procesa primero la cola de memoria pendiente; no reintenta por sí solo peticiones inciertas.

## Migración y límites de esta entrega

La migración 10 añade tablas de contexto, carga de llamada y tipo de cambio temporal sin interpretar ni borrar los checkpoints anteriores. Los informes históricos sin manifiesto no se convierten en antecedentes reutilizables. Para reanudar esas sesiones se exige una replanificación explícita; una modificación de memoria retira conservadoramente sus informes porque no tienen dependencias suficientes. El historial sigue disponible para auditoría.

La recuperación inicial usa relaciones y búsqueda textual. La evaluación registra un fallo con sinónimos y recuperación por catálogo; se aplaza el índice vectorial para este ámbito local pequeño, no se afirma equivalencia semántica. Antes de ampliar el historial se debe medir recuperación con el conjunto de conversaciones de 2.5.4 y añadir búsqueda semántica si no bastan las relaciones/catálogos. Los vectores serían derivados de descripciones y fragmentos, nunca una sustitución de originales ni una vectorización obligatoria de filas.

Aún no hay mensajes persistentes de chat, panel «Mi negocio», nueva navegación ni combinación general de tablas. El contrato de selección y herramientas se reutilizará al añadir esos adaptadores, sin crear otra memoria.
