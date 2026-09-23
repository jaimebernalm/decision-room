# Entrega 2.5: memoria del negocio y experiencia cotidiana

**Fecha:** 23 de septiembre de 2026.  
**Estado:** paso 2.5.1 implementado y [comprobado](../validation/2026-09-23-business-identity-check.md); paso 2.5.2 de memoria versionada también [comprobado](../validation/2026-09-23-memory-check.md); paso 2.5.3 de contexto compartido [comprobado](../validation/2026-09-23-context-check.md); pasos 2.5.4–2.5.7 pendientes de construir y evaluar.  
**Alcance:** negocio persistente, memoria compartida entre conversaciones, chat con evidencia, Inicio e interfaz «Mi negocio». Los pasos y criterios de cierre están en el [plan de implementación](<../product/Decision Room - Plan de implementacion.md#51-entrega-25-memoria-del-negocio-y-experiencia-cotidiana>).

El [desglose de ejecución incremental](business-memory-implementation.md) concreta cada uno de los siete pasos en incrementos pequeños, zonas de código, contratos entre pasos, demostraciones y comprobaciones de cierre. Este documento conserva el diagnóstico y las reglas comunes del diseño.

## 1. Diagnóstico previo a 2.5.1

| Componente revisado | Comportamiento actual | Consecuencia para el uso habitual |
|---|---|---|
| [`web/service.py`](../../decision_room/web/service.py), `Workspace.create` | Cada envío crea un nuevo `businesses` y un `web_jobs`; exige nombre, descripción y CSV | Dos análisis del mismo cliente no comparten automáticamente identidad ni contexto |
| [`schema.sql`](../../decision_room/schema.sql) | Negocios, análisis, fuentes, ejecuciones y sesiones ya tienen relaciones y ámbito de negocio; respuestas ligadas a preguntas/sesiones | Existe una base reutilizable, pero no entidades de conversación de cliente ni memoria transversal versionada |
| [`agent/context.py`](../../decision_room/agent/context.py), `snapshot` | Congela `owner_context` y catálogo del análisis seleccionado | No consulta un perfil vigente ni recupera conocimiento de otras conversaciones |
| [`agent/research.py`](../../decision_room/agent/research.py), `knowledge` y `mark_stale` | La huella incluye propuesta, respuestas de la sesión y fuentes; invalida investigación/revisión de esa sesión | Una corrección en otro chat o en un perfil futuro no se propagaría por sí sola |
| [`agent/service.py`](../../decision_room/agent/service.py), `replan` | Crea una sesión sucesora y deja obsoleta la investigación anterior | Reutilizable para recalcular, pero todavía no gestiona cambios de memoria entre sesiones |
| [`agent/review_context.py`](../../decision_room/agent/review_context.py) y [`agent/review.py`](../../decision_room/agent/review.py) | Reconstruyen diálogo analista/revisor, evidencia, respuestas y aprobación | Ese diálogo interno no es un chat del cliente; la revisión y sus controles deben seguir protegiendo las nuevas respuestas |
| [`web/static/app.js`](../../decision_room/web/static/app.js) | Vistas de inicio, lista de análisis, formulario, detalle y archivos | La navegación organiza trabajos; falta Inicio del negocio con prompt, chats e información editable |
| [`web/service.py`](../../decision_room/web/service.py), `listing` | Lista todos los trabajos web del espacio local | Al introducir un negocio activo habrá que filtrar también listados, búsquedas y referencias |
| [`storage.py`](../../decision_room/storage.py) y [`database.py`](../../decision_room/database.py) | Archivos privados por negocio; migración SQL transaccional con bloqueo | Conservar la separación de archivos y base de datos; planificar la compatibilidad de identidades, rutas y checkpoints |

La entrega 2 está implementada y comprobada como recorrido web local. La evaluación previa a ampliar cobertura terminó el 22 de septiembre, con límites documentados. Esos resultados no prueban todavía memoria transversal ni conversaciones posteriores: esta entrega requiere su propia evaluación.

## 2. Organización propuesta

Mantener PostgreSQL como fuente de verdad del estado del producto y el almacenamiento privado para originales, tablas preparadas y artefactos. Los checkpoints de LangGraph siguen dedicados a recuperación de ejecución. No introducir Obsidian, una base de grafos, otro proveedor ni un agente adicional como requisito.

Un negocio tiene un perfil y una memoria compartida, múltiples conversaciones, conjuntos de datos versionados y análisis con informes. Una conversación puede consultar varios resultados o iniciar varias investigaciones; una investigación puede originarse en un chat, pero no todo mensaje genera un análisis o un informe.

Estructuras lógicas a concretar en las migraciones de los pasos 2.5.1–2.5.3:

| Estructura | Responsabilidad |
|---|---|
| Negocio y acceso al espacio | Identidad estable, perfil básico y resolución del negocio autorizado en el servidor |
| Hechos y revisiones de memoria | Declaraciones, objetivos, definiciones, disponibilidad y dudas, con procedencia, vigencia y estado |
| Conversaciones y mensajes | Texto del cliente, respuestas publicadas, estado de cada turno y referencias a hechos, fuentes e investigaciones |
| Fuentes y conjuntos de datos versionados | Originales, preparación y selección explícita para cada investigación; reutilizan las estructuras existentes |
| Manifiesto de contexto de cada ejecución | Versiones de hechos, fuentes, mensajes y resultados utilizados; permite reproducir la selección y detectar cambios |
| Dependencias y estado de publicación | Relación entre cambios de conocimiento y resultados afectados, incluyendo respuestas de chat y tarjetas de Inicio |

Se pueden combinar tablas relacionadas y JSON validado para contenido variable. Evitar un único documento creciente que reescriba toda la memoria. El esquema físico se decide por paso; esta lista no obliga a crear todos los nombres o tablas antes del primer recorrido.

### Migración y compatibilidad

- Separar crear un negocio de crear un análisis. Conservar el onboarding recuperable y permitir preguntas sin archivo nuevo después de entrar al espacio.
- No fusionar negocios históricos por coincidencia de nombre: pueden ser pruebas o negocios diferentes. Mantener los ámbitos anteriores consultables, con sus identificadores, archivos y evidencia intactos; no incorporarlos todos al dashboard de un supuesto negocio único.
- El negocio activo para el nuevo recorrido se selecciona explícitamente. Migrar contexto de su registro y ofrecer solo candidatos de memoria con procedencia para aclaraciones antiguas; no elevar automáticamente todas las respuestas históricas a hechos generales.
- La primera entrega no necesita una herramienta general de fusión de negocios históricos. Una consolidación posterior deberá mapear fuentes, sesiones, hashes y rutas y comprobarse por separado.
- Probar la migración tanto sobre una base vacía como sobre una copia controlada de la estructura anterior. Si un checkpoint antiguo no es compatible, conservarlo y explicar la recuperación disponible; no reanudarlo con contexto cambiado silenciosamente.
- La web sigue siendo local para un propietario. Comprobar pertenencia en todas las operaciones y probar dos negocios desde el principio; cuentas, equipos y despliegue comercial siguen en la entrega 4.

## 3. Qué significa memoria compartida

Cada hecho conserva identificador y revisión, contenido, tipo, fuente original, momento de registro, periodo de aplicación cuando corresponda, ámbito y estado. El ámbito puede ser el negocio, una fuente/formato comprobado, un periodo o una conversación. Si la vigencia es desconocida se registra como desconocida; no se inventa.

Los tipos distinguen contexto declarado, prioridades, definiciones de datos, disponibilidad y preguntas pendientes. Los resultados calculados conservan referencias a su evidencia y periodo; no se transforman en atributos permanentes del negocio. Las hipótesis y los planes hipotéticos no pasan a hechos confirmados.

Estados mínimos: propuesto, declarado/confirmado por el cliente, en conflicto, sustituido y retirado. «Confirmado por el cliente» identifica la procedencia, no acredita comprobación externa. Mantener separadas esa confirmación y la verificación de los cálculos.

### Incorporación y mantenimiento

1. Recibir una edición de «Mi negocio», una respuesta del onboarding o un mensaje del cliente y conservar su origen.
2. Extraer candidatos de información duradera, sin guardar como perfil cada comentario incidental. Distinguir una declaración de una pregunta, una cita o una posibilidad.
3. Validar estructura, ámbito, fecha y contradicciones en el servicio. El modelo propone cambios mediante herramientas acotadas; no recibe escritura SQL libre ni decide los permisos.
4. Aplicar declaraciones claras de contexto de bajo impacto con aviso visible y opción de corregir/retirar. Una edición explícita de la ficha ya expresa la intención del usuario y no requiere doble confirmación.
5. Pedir una aclaración breve antes de activar una interpretación ambigua, una contradicción material o una definición inferida que cambie cálculos. Una respuesta explícita a una pregunta que ya fija definición y ámbito puede quedar confirmada directamente.
6. Guardar la nueva revisión, conservar la anterior y registrar las dependencias afectadas. Solo anunciar «guardado» después de persistirlo.
7. Reconstruir la siguiente respuesta con la selección de memoria aplicable, incluso al continuar una conversación antigua.

Las escrituras serán idempotentes y comprobarán la revisión de origen: dos chats abiertos no pueden sobrescribir cambios silenciosamente. El fallo de extracción o de guardado deja el mensaje recuperable y el cambio pendiente, sin fingir una actualización. Resolver conflictos de forma explícita; el último mensaje no gana automáticamente.

«No lo tengo» y «ahora no» también conservan ámbito y fecha. Evitar repetir la misma petición sin motivo, pero permitir reconsiderarla cuando lleguen nuevas fuentes o cambie el contexto.

### Ejemplos que deben pasar

- «Desde septiembre abrimos los domingos»: conservar la fecha de aplicación; no reinterpretar junio con el horario nuevo.
- «Estoy pensando en abrir los domingos»: propuesta del cliente, no horario vigente.
- «Este CSV incluye impuestos»: definición de esa fuente; no extenderla a todos los archivos.
- «Antes dije que incluía impuestos, pero estaba equivocado»: corrección histórica; identificar resultados afectados y exigir su revisión.
- «No tengo costes»: no insistir en cada chat ni deducir beneficio a partir de ventas.

### Retirar información

«Mi negocio» permite corregir y retirar hechos de la memoria activa. Retirar evita su reutilización por el agente y por resúmenes derivados; un hecho retirado no puede reaparecer al recuperar el mensaje de origen. Conservar las revisiones necesarias para explicar resultados anteriores, indicando su estado. Retirar un recuerdo no equivale a borrar el mensaje o los archivos originales: la interfaz debe distinguirlo. La política general de borrado del espacio y retención se concreta para el piloto en la entrega 4.

## 4. Recuperación de contexto y vigencia de resultados

La memoria compartida no significa incluir todos los chats en cada llamada. Construir un contexto limitado a partir de:

- Perfil y hechos aplicables a la pregunta, periodo y fuentes elegidos.
- Mensajes recientes del chat y referencias explícitas a otros trabajos del negocio.
- Definiciones, dudas y conflictos relevantes, que no se omiten para ahorrar contexto.
- Resultados revisados y todavía utilizables, con evidencia, cobertura y fecha.

Empezar con selección por negocio, ámbito, estado, periodo y referencias, más búsqueda acotada en PostgreSQL cuando sea necesaria. Medir omisiones y ruido antes de introducir búsqueda semántica. Los resúmenes son ayudas reconstruibles con enlaces a sus fuentes; nunca autoridad superior al hecho corregido o retirado. Fuentes, mensajes recuperados y resúmenes se tratan como contenido, no como instrucciones que puedan modificar permisos o reglas del sistema.

### 4.1. RAG y relaciones entre datos, memoria e informes

**Decisión acordada con el usuario, 23 de septiembre de 2026.** Aplicar este diseño al implementar 2.5.3 y conectar las conversaciones en 2.5.4. La base con datos, memoria e informes está implementada en 2.5.3: véanse el [contrato](context-retrieval.md) y la [validación](../validation/2026-09-23-context-check.md). El adaptador de chats sigue pendiente en 2.5.4.

Combinar recuperación dirigida por el agente, relaciones explícitas y búsqueda. La búsqueda semántica es una herramienta posible dentro de ese recorrido; no sustituye los originales ni exige convertir todas las tablas y mensajes en vectores. PostgreSQL mantiene la autoridad del estado y las relaciones; los datos tabulares conservan su estructura y se calculan mediante SQL/Python sobre las fuentes autorizadas.

| Elemento | Representación para búsqueda | Original y relaciones que se conservan |
|---|---|---|
| Conjunto de datos/tablas | Descripción de contenido, columnas, significado, periodo, cobertura y limitaciones | Fuentes y tablas preparadas con identidad y versión; no vectorizar cada fila del CSV como requisito |
| Memoria | Contenido de recuerdos individuales y metadatos de ámbito/vigencia | Hechos, revisiones, originales y estado en PostgreSQL |
| Informes | Resumen, hallazgos y secciones con referencias | Informe/revisión, cálculos, evidencia y versiones de datos utilizados |
| Chats, desde 2.5.4 | Fragmentos pertinentes con contexto suficiente para interpretar la conversación | Mensajes completos y ordenados, referencias a negocio, fuentes, recuerdos, investigaciones e informes |

**Recorrido que debe construirse:**

1. Entregar un contexto inicial pequeño: perfil, petición actual, restricciones materiales y catálogo resumido de datos disponibles. Con poca memoria, incluir todos los recuerdos aplicables antes de introducir una selección demasiado estrecha.
2. Ofrecer herramientas acotadas para buscar conjuntos de datos, inspeccionar su estructura, consultar memoria aplicable, buscar antecedentes y abrir evidencia. El agente puede solicitar detalle adicional según lo que encuentre; los resultados iniciales incluyen descripciones y referencias estables.
3. Resolver relaciones explícitas: una aclaración define una fuente/columna; una investigación utiliza una versión de datos; un informe deriva de esa investigación; un mensaje aporta un recuerdo o discute un resultado. Recuperar antecedentes ligados a esas relaciones, además del conocimiento general pertinente del negocio.
4. No incorporar un chat entero por compartir una tabla. Seleccionar mensajes relacionados con el asunto y contexto adyacente cuando sea necesario. Compartir tabla tampoco acredita que una conclusión anterior sea aplicable al nuevo periodo o pregunta.
5. Comprobar negocio y ámbito antes de recuperar contenido; verificar estado, vigencia y versión del original antes de entregarlo como contexto utilizable. Una coincidencia textual o semántica no acredita validez ni suficiencia. Distinguir antecedentes conversacionales de evidencia numérica revisada; calcular y revisar cuando hagan falta cifras nuevas.
6. Registrar cada ampliación del contexto en el manifiesto, sin cambiar silenciosamente las versiones ya utilizadas. Las dudas y contradicciones materiales son obligatorias, aunque su similitud con la pregunta sea baja. Si el contexto imprescindible no cabe o hay ambigüedad material sobre fuentes/periodo, acotar o aclarar antes de continuar.

**Introducción gradual de búsqueda semántica:** en 2.5.3 construir las referencias, descripciones, contrato de recuperación y búsqueda textual acotada en PostgreSQL. Preparar casos de preguntas reformuladas para medir omisiones y ruido. Añadir un índice semántico cuando esos resultados justifiquen su utilidad; no elegir proveedor ni motor vectorial como requisito previo. Registrar la decisión y los resultados de evaluación: no introducirlo ni aplazarlo silenciosamente.

Si se añade ese índice, indexar descripciones y fragmentos seleccionados con identificador de origen y versión. Es una representación derivada y reconstruible. Corregir o retirar información debe actualizar o invalidar también sus resúmenes/fragmentos/indexaciones. Mientras se actualiza el índice, contrastar cada resultado recuperado con el original vigente para impedir reutilizar contenido obsoleto. Un fragmento de un mensaje original no puede reactivar un recuerdo retirado.

**Reparto entre pasos:** 2.5.3 implementa el mecanismo con memoria, datos e informes existentes; 2.5.4 añade mensajes y fragmentos de chats mediante el mismo contrato. No crear un segundo buscador o una segunda memoria independientes para las conversaciones. La ficha de 2.5.5 muestra y modifica los mismos registros.

### 4.2. Manifiesto y efectos de cambios

Cada turno/ejecución registra el manifiesto de contexto seleccionado. Planificador, analista y revisor deben recibir las mismas versiones relevantes. Los checkpoints fijan la versión con la que se inició el trabajo. Antes de publicar, comprobar que no hubo una corrección material concurrente; si la hubo, retirar la candidatura y replanificar/revisar lo afectado. Evitar mezclar mitades de dos versiones. El manifiesto acredita qué contenido y versiones se entregaron al modelo, no qué utilizó internamente en su razonamiento. Registrar también reglas de selección, límites y contexto pendiente. Comprobar cambios relevantes en el ámbito seleccionado, incluida información nueva que todavía no aparecía en la lista de identificadores del manifiesto.

Extender la invalidación actual, limitada a una sesión, a las dependencias del negocio:

| Cambio | Comportamiento |
|---|---|
| Nuevo horario desde una fecha posterior al informe | Actualizar memoria actual; conservar como válida la revisión del periodo anterior si no le afecta |
| Corrección de una definición usada en varios chats | Marcar sus resultados afectados como pendientes de revisión y dejar de reutilizarlos como evidencia vigente |
| Nuevo archivo de otro periodo | Conservar informes anteriores como históricos; no aparentar que ya incluyen el nuevo archivo |
| Corrección sin dependencias suficientemente precisas | Marcar un conjunto más amplio para revisión, sin asumir que no afecta |
| Cambio de una prioridad sin efecto en cálculos | Cambiar la orientación de próximas consultas; no recalcular todo el histórico |

Los mensajes e informes anteriores conservan su contenido y versión para trazabilidad. Si han quedado invalidados, su vista muestra el aviso y no sirve sus conclusiones como resultados vigentes en Inicio, búsquedas ni nuevas respuestas. Un informe histórico válido es distinto de un informe retirado por error. Reutilizar los controles existentes de aprobación y retención independiente; no publicar una respuesta porque un informe previo fue aprobado en otro contexto.

## 5. Chat conectado con el análisis

El usuario puede escribir una pregunta libre sobre su negocio, sus datos y decisiones. El sistema identifica la respuesta necesaria dentro de sus capacidades:

| Intención | Recorrido |
|---|---|
| Explicar una cifra ya revisada | Recuperar evidencia vigente y responder con referencia al resultado y periodo |
| Investigar algo nuevo o aplicar un filtro que cambia cifras | Seleccionar fuentes, aclarar dudas materiales, ejecutar y revisar antes de publicar |
| Aportar contexto | Registrar candidatos/cambios de memoria con las reglas anteriores y mostrar su estado |
| Explorar una decisión | Separar observaciones, hipótesis, opciones y datos faltantes; no prometer predicciones ni ejecutar acciones externas |
| Preparar un informe | Crear una revisión independiente vinculada al chat, con resultado estructurado y comprobaciones |

No exigir informe completo para una respuesta breve. Tampoco crear una vía de chat que publique cifras nuevas sin evidencia: los controles de afirmaciones y referencias se adaptan a respuestas cortas y la revisión se aplica al contenido nuevo antes de mostrarlo como definitivo. Guardar como informe una respuesta puede reutilizar evidencia vigente; las afirmaciones o redacción materialmente nuevas vuelven a revisión.

Los turnos y trabajos tienen identidad, estado persistente, reintentos idempotentes y recuperación al recargar o reiniciar. Mientras se calcula se muestra progreso real; aclaraciones dentro del chat conservan la relación con la investigación. No exponer el diálogo interno del revisor como conversación del cliente.

Primero reutilizar conjuntos de datos admitidos y permitir seleccionar uno para una pregunta. La subida manual de otro CSV crea una versión/conjunto identificable; preguntar si sustituye una fuente o se usa por separado cuando sea necesario. Detectar reenvíos exactos y no sumar archivos solapados automáticamente. La combinación general, Excel y relaciones entre tablas continúan en la entrega 3. No es necesario implementar esa combinación para compartir contexto entre chats.

## 6. Experiencia de la web

Separar onboarding y uso cotidiano. Un espacio nuevo conduce a descripción y primer archivo; guarda el avance si se interrumpe. Al volver a un negocio preparado se abre Inicio, sin repetir el formulario del análisis.

Barra lateral: **Inicio**, **Informes**, **Mi negocio**, acción **Nueva conversación** y chats recientes. «Mi negocio» agrupa inicialmente **Información**, **Datos y archivos** y **Cambios**, evitando dos entradas distintas para el mismo perfil. En móvil la navegación se repliega, manteniendo accesibles conversación, evidencias y edición.

- **Inicio:** resumen y pocos hallazgos de la revisión publicable seleccionada, gráficos útiles, periodo visible, fecha de datos y acceso a evidencia. Si existen varias revisiones de temas o periodos distintos, identificar la seleccionada y permitir cambiarla; no mezclar tarjetas incompatibles como si fueran una única revisión.
- **Prompt inferior:** visible al entrar, con espacio reservado para que no tape contenido; enviar crea una conversación durable. Cerca aparecen pocas preguntas sugeridas derivadas de los datos y hallazgos disponibles. «Preguntar sobre esto» incluye la referencia al hallazgo y revisión.
- **Interacción inicial:** explorar detalle y evidencia, seleccionar revisiones y abrir preguntas. Cualquier interacción que requiera nuevas cifras se convierte en investigación comprobada; no implica un editor de dashboards ni filtros universales.
- **Informes:** biblioteca de revisiones por tema, periodo y estado, con vínculo a su conversación cuando exista. Distinguir publicable, histórico, pendiente y retirado. Los borradores no se presentan como informes aprobados.
- **Mi negocio:** ficha legible y editable que se completa progresivamente. Mostrar procedencia, vigencia y estado cuando ayuden a entender/corregir una información; permitir resolver propuestas y conflictos. No exigir completar campos ajenos a una necesidad real.
- **Conversaciones:** historial recuperable, título útil, referencias a fuentes/informes y estados de trabajo. Abrir un chat antiguo mantiene sus mensajes e incorpora memoria vigente aplicable en los nuevos turnos.
- **Sin datos/resultados:** explicar qué falta y ofrecer el siguiente paso. Si hay datos nuevos sin informe nuevo, avisarlo sin sustituir el resumen anterior por cifras inventadas. Si se retira un informe, retirar también sus tarjetas y sugerencias dependientes.

## 7. Evaluación de la entrega

Preparar casos públicos pequeños y ficticios, con conocimiento esperado y afirmaciones prohibidas independientes del agente. Combinar pruebas deterministas de persistencia/aislamiento con conversaciones del modelo real y verificación visual del navegador. Medir repeticiones de preguntas, correcciones propagadas, exactitud, recuperación de contexto relevante, uso de hechos fuera de ámbito, latencia y consumo.

La matriz debe incluir dos conversaciones que comparten contexto, un chat antiguo reabierto, cambio temporal, corrección histórica, conflicto concurrente, definición específica de archivo, información retirada, negativa previa y dato nuevo que la cambia, contexto largo, caída/reintento, fuentes solapadas, ausencia de informe publicable, dos negocios y contenido adversarial en archivos/mensajes recuperados. Verificar también una regresión de archivo → preguntas → cálculo → revisión → informe.

El cierre requiere un recorrido observado completo: onboarding una vez → Inicio → pregunta sugerida → respuesta con evidencia → dato nuevo guardado → otro chat que lo utiliza → corrección desde «Mi negocio» → resultados afectados revisados → informe guardado → reinicio y recuperación. Publicar los resultados y límites de la evaluación antes de marcar la entrega completa; el diseño aprobado no equivale a implementación.
