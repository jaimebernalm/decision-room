# Decision Room: plan de implementación por entregas

**Fecha de actualización:** 23 de septiembre de 2026.  
**Estado vigente:** entrega 2 implementada y comprobada como recorrido web local. La ronda de evaluación previa a ampliar cobertura terminó el 22 de septiembre, con correcciones y límites documentados; no equivale a aceptación general del MVP. La entrega 2.5 tiene los pasos 2.5.1–2.5.7 implementados y comprobados dentro del alcance local; su evaluación integrada se cerró el 24 de septiembre antes de ampliar la cobertura de la entrega 3. Los resultados históricos de cada paso se conservan en la sección 10.  
**Propósito:** conservar la secuencia de trabajo, el motivo de cada paso y qué debemos poder comprobar antes de darlo por terminado.

## 1. Relación con el MVP

El [documento del MVP](<Decision Room - MVP.md>) define el alcance y las decisiones de los siete bloques. Este documento define el orden para construirlo. Los bloques funcionales no son entregas consecutivas de software: cada entrega combina partes de varios bloques.

En este plan, **entrega 1** significa el primer recorrido interno completo; no equivale al MVP completo descrito en el otro documento. Las entregas 1, 2, 2.5, 3, 4 y 5 y la preparación conducen al MVP probado en un piloto privado.

**Cambio de prioridad del 23 de septiembre de 2026:** adelantar negocio persistente, memoria entre conversaciones, chat posterior, Inicio con prompt y «Mi negocio». Se añade una entrega 2.5 para conservar las referencias existentes a las entregas 3–5, que pasan a ejecutarse después. Esta ampliación reemplaza su aplazamiento anterior; no reabre el cierre de implementación web de la entrega 2 ni incorpora PDF, automatización o predicciones.

La [organización multiagente objetivo del producto completo](<Decision Room - Definicion del producto.md#186-organización-multiagente-del-producto-final>) separa negocio, analítica y revisión. Es una evolución posterior que deberá implementarse y compararse con el MVP. Los pasos 1.4–1.6 de este plan mantienen un agente principal que planifica y ejecuta, más un revisor; no se añade ahora otro agente al recorrido inicial.

**Principio de construcción:** completar pronto un recorrido pequeño de archivo a informe y ampliarlo con comprobaciones en cada paso.

**Principio del producto:** autonomía para decidir qué investigar, con resultados comprobables. Los casos iniciales limitan la cobertura que probamos, no imponen un esquema universal ni una lista cerrada de análisis.

Las entregas son hitos comprobables, no necesariamente despliegues públicos. El avance construido y sus pruebas se registran en la sección 10; el resto conserva su carácter de plan.

## 2. Orden general

| Orden | Entrega | Resultado comprobable | Motivo |
|---|---|---|---|
| Preparación | Casos de referencia y decisiones necesarias | Archivos, resultados esperados y estructuras mínimas | Saber qué significa que el sistema funcione |
| 1 | Recorrido interno completo | Archivo → interpretación → pregunta si hace falta → Python → revisión → informe con evidencia | Probar el núcleo autónomo de principio a fin |
| 2 | Recorrido web mínimo | Una persona completa el análisis desde el navegador | Detectar pronto problemas de comprensión y uso |
| 2.5 | Memoria del negocio y experiencia cotidiana | Onboarding una vez → Inicio → chats con contexto compartido → «Mi negocio» editable → informes con evidencia | Resolver continuidad antes de ampliar formatos y capacidades |
| 3 | Adaptación a archivos y situaciones distintas | Ampliar cobertura sin depender de una estructura concreta | Construir nuevas capacidades sobre un recorrido probado |
| 4 | Preparación operativa del piloto | Versión privada con recuperación, aislamiento y límites comprobados | Comprobar el funcionamiento conjunto antes de usar datos reales |
| 5 | Piloto con comercios y correcciones | Evidencia de comprensión, utilidad e intervención necesaria | Contrastar el producto con su público |

Las evaluaciones acompañan al primer código. La entrega 4 concentra las pruebas operativas del conjunto, pero los controles esenciales de acceso, aislamiento, recursos y evidencia se incorporan cuando aparece la capacidad que los necesita.

## 3. Preparación breve

Preparar tres casos pequeños:

1. **Ventas diarias:** evolución posible, sin atribución a productos.
2. **Ventas por artículo sin tickets:** análisis por producto posible, sin ticket medio.
3. **Ambigüedad material:** requiere aclaración antes de publicar el cálculo afectado.

Cada caso conserva datos, respuestas del propietario, resultados de referencia calculados independientemente, afirmaciones prohibidas y comportamiento esperado. Incluir variaciones que eviten ajustar el sistema únicamente a un archivo exacto.

Resolver las decisiones necesarias para empezar: modelo inicial del analista y del revisor; entorno aislado de Python; configuración inicial de PostgreSQL; estructuras mínimas de fuentes, interpretaciones, preguntas, investigaciones, ejecuciones y resultados; y límites iniciales y registro de costes.

No cerrar todo el esquema futuro de datos ni todos los proveedores del producto. La preparación debe producir archivos y comprobaciones ejecutables, no una fase extensa adicional de documentación. El diseño mínimo de estructuras de esta preparación se concreta al comenzar la entrega 1; no es un trabajo duplicado.

## 4. Entrega 1: recorrido interno completo

### Objetivo

Ejecutar el sistema desde una herramienta interna sencilla, aportar datos, responder aclaraciones y obtener un informe correcto y trazable sin modificar manualmente el código generado o las conclusiones.

Meta concreta: **aportar archivos de estructuras distintas, responder una aclaración cuando corresponda y recibir informes adaptados, correctos y trazables, sin arreglarlos a mano.**

### 1.1. Caso de referencia y estructuras mínimas

**Construir:** seleccionar el primer CSV pequeño de ventas diarias con una ambigüedad relevante. Concretar las estructuras de análisis, fuente, interpretación, pregunta/respuesta, investigación, ejecución, resultado y evidencia. Reutilizar los casos y referencias de la preparación.

**Comprobar:** cada pieza tiene entradas y salidas entendibles y conocemos los resultados admisibles. Las referencias numéricas son independientes del agente.

**Por qué primero:** fija los intercambios entre componentes antes de diseñar las tablas. No exige modelar todavía toda la aplicación.

### 1.2. Guardar y recuperar un archivo real

**Construir:** introducir PostgreSQL y almacenamiento de archivos con lo mínimo para crear un análisis, registrar su fuente y versión, conservar el original, leer el CSV, generar la tabla preparada en Parquet y guardar su descripción y referencia. Separar datos por negocio y análisis desde el inicio, aunque sean casos ficticios.

**Comprobar:** cerrar y abrir el programa permite recuperar el mismo archivo y descripción, conservando su identidad y procedencia.

**Por qué ahora:** el agente necesita una fuente identificable y persistente sobre la que investigar.

### 1.3. Ejecutar Python en aislamiento

**Construir:** probar primero el entorno con un script escrito por nosotros que recibe los datos autorizados, realiza un cálculo conocido y produce una salida estructurada. DuckDB está disponible. Registrar código, resultado y fuente; aplicar límites de tiempo y memoria, originales de solo lectura y ausencia de credenciales del sistema.

**Comprobar:** el resultado coincide con la referencia, su evidencia se recupera y el proceso respeta las restricciones del entorno.

**Por qué antes del agente:** permite distinguir fallos de infraestructura de errores del código generado. El script inicial comprueba la herramienta; no sustituye la capacidad autónoma de la entrega.

### 1.4. Inspeccionar, planificar, preguntar y recuperar

**Construir:** conectar LangGraph y el agente principal con el perfil y muestras del archivo. Permitir interpretación, plan provisional, pregunta material, persistencia y pausa. Responder desde terminal o interfaz interna; actualizar el conocimiento estructurado y continuar.

**Comprobar:** detener el proceso durante la espera y reanudarlo sin perder información ni repetir preguntas ya resueltas. El agente no publica el cálculo dependiente mientras la ambigüedad siga abierta.

**Por qué ahora:** comprueba la conexión entre interpretación, preguntas y estado antes de ampliar la investigación.

Este paso proporciona evidencia concreta para mantener PostgreSQL o reconsiderar Convex. Convex sigue siendo una opción abierta; si se propone un cambio, hay que comprobar también cómo persisten y se recuperan los checkpoints. La prueba completa de integración culmina al mostrar el resultado en los pasos siguientes.

### 1.5. Investigación con Python generado

**Construir:** conectar al agente con el entorno del paso 1.3. Permitir elegir una investigación abordable, escribir y ejecutar Python, examinar salidas o errores, corregir dentro del presupuesto, actualizar el plan y registrar resultados candidatos con evidencia. Añadir funciones reutilizables según necesidades observadas.

**Comprobar:** el agente obtiene resultados admisibles sin que editemos su código y adapta la investigación cuando cambia una respuesta del propietario.

**Por qué ahora:** el agente dispone de datos, contexto, recuperación y una herramienta de ejecución ya comprobada. Los resultados siguen siendo candidatos hasta pasar la revisión.

### 1.6. Comprobaciones, revisor e informe

**Construir:** integrar comprobaciones programáticas pertinentes; informe estructurado; revisión de afirmaciones y evidencias; corrección o retirada de resultados; y una presentación HTML sencilla con acceso a la evidencia. El agente produce contenido estructurado y la aplicación lo presenta, conforme al bloque 6.

**Comprobar:** abrir el informe, seleccionar una cifra y localizar datos y operación. El revisor examina también la redacción final: un cálculo correcto puede acompañar una conclusión incorrecta. Los cambios materiales vuelven a validarse.

**Resultado del paso:** primera demostración completa de archivo a informe. No se necesita aún la aplicación web de subida y preguntas de la entrega 2.

### 1.7. Variar los casos y cerrar la entrega

**Construir y evaluar:** incorporar los otros casos de la preparación, variaciones de nombres y orden de columnas y respuestas alternativas del propietario.

**Comprobar:** el sistema cambia el análisis según los datos; continúa sin información opcional; no inventa productos, tickets o causas; recupera trabajo interrumpido; y produce resultados admisibles en las repeticiones previstas en el bloque 7.

**Criterio de cierre de la entrega 1:** recorrido completo en varios casos sin correcciones manuales nuestras, con resultados comprobables y evidencia. Un único archivo funcionando es un avance, no el cierre.

### Orden resumido de la entrega 1

**Caso y estructuras → persistencia mínima e ingesta → Python aislado → agente con preguntas y recuperación → investigación autónoma → revisión e informe → variedad de casos.**

La base de datos crece con el recorrido: primero análisis y fuentes; después interpretaciones y respuestas; luego ejecuciones, resultados e informes. Cada paso tiene comprobaciones y una demostración interna, no un despliegue público independiente.

## 5. Entrega 2: recorrido web mínimo

**Estado, 22 de septiembre de 2026:** implementada y comprobada como recorrido
web local por petición del usuario, manteniendo abierta la aceptación analítica
de la entrega 1. Incluye inicio, contexto, CSV, preguntas, ejecución duradera,
recuperación, archivos e informe integrado. La prueba real llegó a aprobación
por el modelo y permitió comprobar gráficos y evidencia; la revisión independiente
retuvo después el informe por errores semánticos (DR-015). Se distingue el cierre
de la implementación web del cierre de calidad del agente. Ver
[guía de uso](../technical/web.md), [diseño](../technical/web-plan.md) y
[resultados](../validation/2026-09-22-web-check.md).

**Construir:** descripción del negocio, subida de archivos, preguntas con opciones y texto libre, progreso real, recuperación al volver, informe con resumen/secciones/evidencia y acceso restringido para pruebas. La web utiliza el sistema de la entrega 1; la lógica analítica continúa en el servicio Python.

**Cierre:** una persona que no conoce el código puede completar el recorrido y localizar la fuente de una cifra sin terminal ni instrucciones técnicas.

**Por qué aquí:** comprobar pronto la comprensión de preguntas e informes. Se puede probar inicialmente con datos controlados sin considerarlo todavía listo para comercios.

## 5.1. Entrega 2.5: memoria del negocio y experiencia cotidiana

**Estado, 23 de septiembre de 2026:** pasos 2.5.1–2.5.4 implementados y comprobados; resto de implementación y evaluación integrada pendientes. El [diagnóstico del código y diseño técnico](../technical/business-memory-plan.md) detalla estructuras, migración, mantenimiento de memoria, contexto del agente, UX y escenarios de aceptación.

**Guía para implementarlo poco a poco:** el [desglose de los siete pasos](../technical/business-memory-implementation.md) define cuatro incrementos por paso, dependencias, zonas de código, contratos de salida, demostraciones y pruebas. Ejecutar un paso por vez y registrar su validación y commit al cerrarlo. Los dieciséis incrementos de 2.5.1–2.5.4 están completados; los restantes están pendientes. El chat utiliza la memoria, selección de contexto y recuperación compartidas, sin duplicar sus mecanismos.

**Objetivo:** que el cliente tenga un negocio persistente y pueda volver a consultar, aportar contexto, actualizar datos y guardar informes sin repetir el onboarding. La memoria debe funcionar entre todos sus chats y análisis, con procedencia y ámbito, sin mezclar negocios ni presentar resultados antiguos como actuales.

**Base reutilizable:** PostgreSQL, archivos privados, ámbitos de negocio, ejecución aislada, checkpoints, evidencia y revisión. Actualmente cada envío web crea un negocio distinto; el contexto y la invalidación se limitan a la sesión del análisis. Compartir memoria exige cambiar esas relaciones y su recuperación, además de la interfaz.

**Alcance inicial:** un propietario y un negocio activo por espacio; conservar otros ámbitos históricos aislados. Chat libre sobre el negocio dentro de las capacidades verificables existentes, con reutilización de datos admitidos y subida manual de CSV. No se requiere cambiar de base de datos ni desplegar la organización multiagente futura.

### 2.5.1. Identidad persistente y transición de los datos existentes

**Completado, 23 de septiembre de 2026:** [cambios, pruebas y límites](../validation/2026-09-23-business-identity-check.md).

**Construir:** separar creación del negocio, onboarding, análisis y trabajos de ejecución. Resolver el negocio autorizado en el servidor y reutilizarlo al crear trabajos; preparar las relaciones para conversaciones y fuentes. Conservar originales, evidencia, identificadores y checkpoints anteriores. Mantener ámbitos históricos separados; no fusionar negocios por nombre ni asociar automáticamente todas las pruebas locales al nuevo espacio.

**Comprobar:** migraciones sobre una base vacía y otra con registros anteriores; dos análisis nuevos del mismo negocio comparten identidad sin perder su independencia; reinicio recupera el onboarding; listados, lecturas y mutaciones rechazan cruces entre dos negocios. Los trabajos históricos siguen siendo localizables y sus estados de publicación se conservan.

### 2.5.2. Memoria versionada y mantenimiento desde el contexto del cliente

**Completado, 23 de septiembre de 2026:** [cambios, pruebas y límites](../validation/2026-09-23-memory-check.md).

**Construir:** hechos, prioridades, definiciones, disponibilidad y dudas con texto original, procedencia, revisiones, estado, ámbito y vigencia. Incorporar contexto del onboarding y respuestas explícitas mediante un servicio común, reutilizable después por el chat y «Mi negocio». Separar declaraciones, inferencias, propuestas y resultados calculados. Permitir corregir/retirar; resolver contradicciones materiales antes de usarlas. Registrar escrituras idempotentes y comprobar revisiones para evitar sobrescrituras concurrentes.

**Comprobar:** declaración clara frente a hipótesis; horario con fecha de inicio; definición aplicable solo a un archivo; respuestas «no lo sé/no lo tengo»; dos cambios simultáneos; fallo y reintento del guardado. La información retirada deja de recuperarse como memoria activa y no reaparece desde un resumen o mensaje antiguo. El sistema no anuncia un cambio que no llegó a persistirse.

### 2.5.3. Contexto compartido del agente y propagación de correcciones

**Decisión de recuperación acordada:** [RAG y relaciones explícitas](../technical/business-memory-plan.md#41-rag-y-relaciones-entre-datos-memoria-e-informes). Combinar contexto inicial acotado y herramientas de búsqueda/inspección para el agente. Preparar descripciones de datos y antecedentes vinculados; mantener originales estructurados y utilizar índices semánticos derivados solo cuando la evaluación lo justifique. Los chats se incorporan al mismo mecanismo en 2.5.4.

**Ampliación semántica de 2.5.3:** tras evaluar omisiones con sinónimos, se incorpora
búsqueda híbrida con embeddings de OpenAI y pgvector antes de 2.5.4. Mantiene
versiones, filtros y comprobación de originales; véanse el [contrato](../technical/semantic-retrieval.md)
y la [validación](../validation/2026-09-23-semantic-check.md).

**Construir:** selección acotada de memoria, mensajes, fuentes y resultados pertinentes por negocio, pregunta y periodo. Registrar el manifiesto de versiones utilizado por planificador, analista y revisor. Integrar las versiones de memoria en la comprobación de vigencia y extender dependencias e invalidación entre sesiones, respuestas e informes. Conservar históricos sin reescribirlos y distinguir cambio futuro, dato nuevo y corrección de un error pasado. Revalidar las dependencias antes de publicar, también si el trabajo se interrumpió.

**Comprobar:** dos sesiones reutilizan contexto sin repetir preguntas resueltas; una corrección material afecta a todas las dependencias conocidas, incluso en otra conversación; un cambio futuro no invalida un periodo previo sin motivo; una edición irrelevante no recalcula todo; los resultados retirados no vuelven a usarse como evidencia vigente. Probar selección con historial largo, datos de otro negocio y contenido adversarial recuperado. Si no se puede acotar el impacto, ampliar la revisión de forma explícita.

### 2.5.4. Conversaciones del cliente conectadas al análisis

**Ampliación completada, 25 de septiembre:** consultas dirigidas por el agente y redacción propia con fuentes y revisión persistente; memoria automática, comprobación de vigencia, bloqueo de consultas idénticas e informes originales conservados. Verificados 39 casos dirigidos, 15 de interfaz, recorridos con modelo real y el seguimiento al CSV en navegador. Véanse el [plan aplicado](../technical/autonomous-chat-plan.md) y la [validación con límites](../validation/2026-09-25-autonomous-chat-check.md).

**Construir:** conversaciones y mensajes persistentes, turnos recuperables y referencia al negocio, fuentes, memoria e investigaciones. Permitir explicar evidencia existente, aportar contexto, explorar una decisión o iniciar un cálculo; no exigir un informe ni un CSV nuevo por mensaje. Integrar cambios de memoria desde el chat con aviso/corrección para declaraciones claras y aclaración cuando haya ambigüedad material. Crear un informe independiente cuando se solicite, reutilizando evidencia vigente y revisando contenido nuevo. Mantener la conversación interna de revisión separada del chat del cliente.

**Comprobar:** una pregunta breve obtiene respuesta con fuente y periodo; una pregunta nueva ejecuta y verifica el cálculo; una pregunta sin datos suficientes explica el límite; una declaración se utiliza en otro chat y al reabrir uno antiguo. Recargar/reintentar no duplica mensajes, hechos ni trabajos. Las respuestas nuevas no eluden las comprobaciones por presentarse en chat en vez de en un informe.

**Corrección de pertinencia, 24 de septiembre:** respuestas de fecha y capacidades,
consulta de información reciente sin iniciar un análisis innecesario y explicación
breve antes de la evidencia desplegable. Se comprueban los casos observados con
modelo real, navegador y regresión automatizada. Véase la [validación y límites](../validation/2026-09-24-conversation-relevance-check.md).

**Corrección de continuidad, 24 de septiembre:** se incluyen las respuestas previas
del asistente en el contexto reciente y se distinguen saludos, cortesía y
agradecimientos. Véase la [validación del diálogo](../validation/2026-09-24-dialogue-context-check.md).

### 2.5.5. «Mi negocio» y actualización de datos

**Construir:** ficha progresiva y editable con información, prioridades, definiciones, fuentes/periodos y cambios; mostrar procedencia, vigencia y propuestas/conflictos donde ayuden. Las ediciones usan el mismo servicio de memoria del chat. Reutilizar archivos ya aceptados; permitir aportar otro CSV y seleccionar su uso sin iniciar otro negocio. Mantener conjuntos/versiones explícitos, detectar reenvíos exactos y aclarar sustitución o solapamiento; no implementar fusión universal de tablas.

**Comprobar:** editar una definición tiene el mismo efecto desde la ficha que desde una aclaración; una corrección histórica retira los resultados afectados; el usuario encuentra el origen y alcance de lo guardado; un archivo nuevo no se agrega dos veces ni hace parecer actualizado un informe anterior. Sin datos suficientes se conserva el trabajo y se explica el siguiente paso.

**Ajuste de presentación, 30 de septiembre de 2026:** implementada y comprobada
una ficha organizada por grupos y filas compactas, con presentación original
plegada y acciones/detalles a petición. Se conserva edición, historial y selección
de contexto con versiones. Pasan 125 pruebas de frontend, compilación y lint sin
errores; escritorio y móvil comprobados con datos ficticios. Véanse la
[secuencia de ejecución](../technical/business-dossier-ui-plan.md) y la
[validación con sus límites](../validation/2026-09-30-dossier-ui-check.md).
El refinamiento visual posterior separa los grupos en cajas, destaca las
cabeceras y usa el acento de la barra lateral al pasar el cursor o enfocar las
filas. Se comprueban 32 pruebas de ficha/chat contextual, compilación, lint,
alineación, móvil y temas claro/oscuro en la misma validación.
Las propuestas incorporan confirmar/descartar directamente en la fila y los
conflictos un recorrido explícito para comparar versiones y guardar la solución.
Pasan 132 pruebas de frontend y la demo incluye texto largo para comprobar lectura
en escritorio y móvil; se conserva el contrato de memoria e historial existente.
La elección de conflictos se marca con opciones de radio y guardado siempre
visible. Se añaden grupos propios persistentes por negocio, renombrado, orden,
asignaciones y eliminación sin pérdida de recuerdos; Actualizar queda junto a
las pestañas. Pasan 138 pruebas frontend y 40 de PostgreSQL/API/migraciones/memoria,
además de compilación, lint y comprobaciones de escritorio/móvil. No se altera
la aceptación analítica de otras entregas.
El siguiente refinamiento amplía las pestañas, convierte Añadir información en un
botón circular y muestra los menús de fila con cursor/foco. Las descripciones de
grupos se guardan y el extractor las usa para asignar recuerdos nuevos mediante
IDs acotados al negocio, respetando movimientos manuales y cambios concurrentes.
Pasan 139 pruebas frontend y 47 de PostgreSQL, compilación y lint; la validación
visual continúa en una demo con datos ficticios.
Añadir información se traslada a cada cabecera, con formulario de grupo fijo y
sin selector de tipo para nuevos recuerdos. El destino y el original se guardan
atómicamente, con validación e idempotencia. Los grupos vacíos permiten empezar;
Por revisar crea propuestas y Sin grupo conserva una asignación explícita.
Las pestañas bajan 16 px y comparten el radio de las cajas. Pasan 142 pruebas
frontend y 50 de PostgreSQL, compilación, lint y comprobaciones de móvil/escritorio.
El botón individual se refina después a 36 px (44 con puntero táctil), símbolo
de 20 px y sombra suave solo al interactuar. Compilación, lint y apertura del
formulario comprobados en la demo.
La etiqueta permanente se sustituye por un tooltip Añadir información con cursor
o foco, manteniendo solo el «+» y el nombre accesible del grupo. Compilación, lint,
tooltip y apertura con teclado comprobados.

**Lectura compacta, 2 de octubre de 2026:** cada declaración muestra una línea
con puntos suspensivos y abre el texto completo en los detalles al pulsarla o
con teclado. Información y Datos comparten ancho; las cabeceras responden al
cursor/foco también en la zona del +, situado antes de la flecha. Pasan 205
pruebas frontend, compilación y lint sin errores; se comprueban escritorio,
móvil y desplazamiento del lector. Véase la
[validación de lectura y sus límites](../validation/2026-10-02-dossier-reading.md).
El siguiente incremento permite confirmar, descartar y corregir desde el detalle,
con resolución del conflicto en esa misma ventana. Personalizar grupos permite
arrastre con recolocación, flechas y teclado, conservando guardado explícito y
asignaciones. Pasan 211 pruebas frontend, compilación y lint sin errores;
se comprueban arrastre, persistencia y cancelación en escritorio y ancho móvil.
Véase la [validación de decisiones y orden](../validation/2026-10-02-dossier-actions-order.md).

### 2.5.6. Inicio del negocio, informes y navegación cotidiana

**Construir:** separar onboarding de visitas posteriores. Barra lateral con Inicio, Informes, Mi negocio, Nueva conversación y chats recientes. Inicio muestra un resumen, pocos hallazgos y gráficos respaldados, con periodo visible, detalle/evidencia y selección de revisión. Añadir prompt inferior y preguntas sugeridas pertinentes; enviar abre un chat y «Preguntar sobre esto» conserva la referencia al hallazgo. Biblioteca de informes con estados y vínculo a conversaciones; navegación adaptable a móvil y teclado.

**Comprobar:** el primer acceso guía el onboarding y los siguientes abren Inicio; escribir desde Inicio crea un chat durable; una sugerencia es abordable con las capacidades/datos presentes; no se mezclan revisiones incompatibles. Verificar estados sin datos, análisis en curso, datos nuevos sin informe nuevo, informe retirado y fallo recuperable. Comprobar visualmente escritorio/móvil, foco, teclado y que el prompt no oculte contenido.

**Avance integrado, 23 de septiembre:** se incorpora el dashboard desarrollado en paralelo y se conecta con los chats y la memoria hasta 2.5.4: prompt con primer mensaje durable, conversaciones reales en la barra lateral, biblioteca y acceso al chat de origen, edición del perfil y reutilización de informes vigentes. El orden se adelanta por disponibilidad de la interfaz; **2.5.5 se completó después de esta integración**, incluyendo los estados de versiones de datos. Quedan pendientes la vinculación estructurada de preguntas a hallazgos y la validación conjunta del recorrido antes de cerrar 2.5.6. Véase [integración del dashboard](../technical/dashboard-ui.md).

**Cierre, 23 de septiembre:** se completan referencias verificables a hallazgos, envío unificado de preguntas, gráficos y cifras legibles en chat, selección visible de versiones, actividad y biblioteca con estados explícitos, cabecera compacta y compositor sin superposición. Se comprueban onboarding y visitas posteriores, escritorio/móvil, teclado, borradores y referencias con Luna real. Pasan 243 pruebas Python y 12 JavaScript. Véase [validación de 2.5.6](../validation/2026-09-23-daily-ux-check.md). La aceptación integrada sigue correspondiendo a 2.5.7.

**Refinamiento de avisos, 2 de octubre de 2026:** los errores usan una cápsula
de fondo rojo suave, texto rojo, esquinas redondeadas y ancho ajustado al mensaje.
Se conservan contenido y rol de alerta; los mensajes se envuelven en móvil.
Pasan 211 pruebas frontend, compilación y lint sin errores; se comprueban avisos
de conexión y errores dentro de detalles. Véase la
[validación visual](../validation/2026-10-02-error-notices.md).

### 2.5.7. Evaluación integrada y cierre

**Ejecutar:** matriz de memoria y conversación con referencias independientes, pruebas de persistencia, aislamiento, concurrencia y recuperación, conversaciones con el modelo real y recorrido visual. Incluir regresión del flujo de la entrega 2 y medir repetición de preguntas, propagación de correcciones, exactitud, selección de contexto, latencia y consumo. Registrar resultados, versiones y límites; corregir fallos materiales antes del cierre.

**Cierre:** una persona completa el onboarding una vez, pregunta desde Inicio, recibe evidencia, aporta información que otro chat reutiliza, la corrige desde «Mi negocio», ve revisados los resultados afectados, guarda un informe y recupera todo tras reiniciar. No se mezclan negocios, fuentes incompatibles ni versiones de contexto, y las respuestas no presentan hipótesis como hechos. Un dashboard dibujado o un único chat funcionando no cierran la entrega.

**Cierre, 24 de septiembre:** evaluación integrada con 23 comprobaciones HTTP y modelo real, 24 casos de memoria, 30 consultas semánticas y 12 escenarios analíticos revisados independientemente. Se corrigen conflictos de fuente ocultos en el chat y trabajos pendientes ocultos en Inicio. Pasan 245 pruebas Python y 12 JavaScript; comprobados onboarding, edición concurrente, versiones históricas, caída/reenvío y recuperación desde otro proceso. Véanse [resultados, versiones y límites](../validation/2026-09-24-integrated-check.md).

### 2.5.8. Entrada y primer informe guiado

**Nota de integración, 27 de septiembre:** los cierres del 24 y 25 siguientes
documentan la interfaz anterior, conservada en el historial. La interfaz vigente
es la migración React y el onboarding validado el 27 de septiembre. Se mantienen
los datos y las API anteriores por compatibilidad; el límite actual de las
entregas CSV/Excel es 2.000.000.000 bytes.

**Construir:** separar el primer recorrido de la navegación cotidiana. Desde la landing y el acceso local, pedir nombre y contexto del negocio, un CSV inicial y una elección entre exploración general o pregunta concreta. Utilizar el trabajo duradero del agente para las aclaraciones, el cálculo, la revisión y el informe. Guardar el trabajo de onboarding por negocio para reanudarlo tras recargar; mostrar el informe revisado antes de abrir Inicio. No inscribir automáticamente los negocios existentes en el nuevo recorrido.

**Comprobar:** acceso y navegación sin mostrar el dashboard antes del informe; borrador y envío idempotente; una pregunta real del agente y su respuesta; recuperación tras recargar; bloqueo de la salida sin informe publicable; reintento o cambio de archivo cuando el trabajo se detiene; llegada al dashboard después de aceptar el primer informe. Verificar escritorio y móvil. La primera versión usa un CSV UTF-8; registro por correo, cuentas multiusuario y combinación automática de archivos quedan fuera de este paso.

**Cierre, 24 de septiembre:** recorrido separado y persistente implementado. Pasan 33 pruebas web Python y 15 JavaScript; el navegador confirma una aclaración de Qwen, recuperación al recargar y reintento tras un timeout local, y un caso controlado confirma informe → Inicio → regreso directo a Inicio. La ejecución con Qwen no se cuenta como informe terminado. Véase [validación y límites](../validation/2026-09-24-guided-onboarding-check.md).

### 2.5.9. Aclaraciones con los datos a la vista

**Construir:** hacer excluyentes las opciones, la respuesta libre y «No lo sé» en las preguntas del primer informe y de los análisis posteriores. Mostrar durante el onboarding una tabla paginada del CSV original junto a la pregunta, con las columnas citadas por la evidencia del agente resaltadas; usar coincidencia textual solo cuando la pregunta no traiga referencias de columna. Mantener la navegación guiada con una barra de progreso superior segmentada y sin abrir el dashboard antes del informe.

**Comprobar:** rechazo de acceso ajeno al CSV, paginación y delimitadores; referencias de columna validadas y ausencia de falsos resaltados; selección excluyente y borradores recuperados sin respuestas contradictorias; diseño en escritorio y móvil. La tabla muestra treinta filas por página y corta las celdas a 200 caracteres; el CSV original se puede descargar.

**Cierre, 25 de septiembre:** pasan 34 pruebas web Python y 17 JavaScript. En navegador con datos ficticios se verifican pregunta y tabla juntas, columna citada resaltada, opciones excluyentes, respuesta libre sin duplicados y diseño a 390 px. Véase [validación](../validation/2026-09-25-contextual-questions-check.md).

**Ajuste de recorrido, 25 de septiembre:** el formulario inicial se divide en nombre, descripción, tipo de informe, pregunta opcional y archivo. Se reemplaza la barra lateral por tramos de progreso superiores; la descripción conserva borrador al recargar. Véase [comprobación del recorrido](../validation/2026-09-25-segmented-onboarding-check.md).

**Ampliación del onboarding, 25 de septiembre:** centrar el contenido en escritorio y admitir varios CSV en un mismo primer análisis. El límite de la selección es de 2 GiB en total, sin cupo por cantidad de archivos; las subidas y las vistas previas se procesan por partes para no cargar un lote grande entero en memoria. Conservar los nombres originales y mostrar cada tabla en las aclaraciones. La ingesta conjunta permite investigar las tablas del lote; no presupone que tengan una relación ni une automáticamente filas de fuentes distintas.

**Orden de trabajo:** identidad → memoria → contexto y dependencias → conversación → ficha/datos → Inicio y navegación → evaluación integrada → primer informe guiado → aclaraciones con datos a la vista. Cada paso se comprueba, revisa y guarda en un commit local según `AGENTS.md`; no se marca completo por tener únicamente su diseño.

**Fuera de 2.5:** PDF, Excel y combinación general de tablas, búsqueda web de contexto, predicciones, editor libre de dashboards, conectores, automatización, equipos y despliegue comercial. Continúan en su entrega o roadmap correspondiente. La memoria entre conversaciones y el Inicio interactivo acotado sí forman parte de 2.5.

### 2.5.8. Migración visual a React y componentes oficiales

**Completado, 26 de septiembre de 2026:** sustituida toda la interfaz web por React con componentes reales de shadcn/ui y AI Elements, incluidos navegación, formularios, gráficos y chat. Conservar los servicios Python y los contratos durables existentes. Véase [análisis de migración](../technical/react-ui-migration.md).

**Orden:** (1) preparar compilación y componentes oficiales; (2) migrar recorridos y contratos del cliente; (3) comprobar integración, teclado, escritorio/móvil y recuperación, revisar y guardar un commit local. La migración no amplía las capacidades analíticas de la entrega 3.

**Cierre:** todos los recorridos existentes se pueden completar en React, los componentes provienen de sus registros oficiales y la aplicación se sirve desde el lanzador local. Compilación correcta, 20 pruebas de frontend, 275 pruebas de regresión Python y 3 de proyección adicionales aprobadas; comprobación visual en escritorio/móvil y acceso al espacio existente. [Validación](../validation/2026-09-26-react-ui-check.md).

### 2.5.9. Asistente flotante y compacto

**Completado, 26 de septiembre de 2026:** (1) revisar Prompt Input y controles
oficiales; (2) trasladar el compositor a una barra inferior superpuesta, redondeada
y plegable, retirando el selector de datos; (3) comprobar borradores, contexto,
foco, navegación y escritorio/móvil. Disponible en las pantallas del negocio;
el chat abierto conserva su propio compositor persistente.

**Cierre:** 22 pruebas de frontend, compilación y lint sin errores, revisión visual
de scroll y plegado en escritorio y móvil. Véase [validación](../validation/2026-09-26-floating-assistant-check.md).

### 2.5.10. Continuidad entre nuevo chat y conversación

**Completado, 26 de septiembre de 2026:** compositor compacto y redondeado también
en conversaciones abiertas; pantalla de nuevo chat centrada, con transición de
la barra y las cuatro conversaciones más recientes debajo. Cabecera de chat sin
título visible y flecha accesible hacia el listado de conversaciones.

**Cierre:** 24 pruebas de frontend aprobadas, compilación y lint sin errores,
comprobación de navegación y diseño en escritorio y móvil.
Véase [validación](../validation/2026-09-26-floating-assistant-check.md#continuidad-del-chat-paso-2510).

### 2.5.11. Superficies compactas y acento de color

**Completado, 26 de septiembre de 2026:** tarjetas de conversaciones más compactas,
redondeadas y sin contorno, con fondo neutro y estados de interacción; control de
minimizar separado del envío, envío más pequeño y espaciado, y azul petróleo como
acento de acciones principales con variante para tema oscuro.

**Cierre:** 24 pruebas de frontend, compilación y lint sin errores; revisión de
escritorio/móvil, plegado, foco y ambos temas. Véase
[validación](../validation/2026-09-26-floating-assistant-check.md#superficies-y-color-paso-2511).

### 2.5.12. Acceso a informes y transición de nuevo chat

**Completado, 26 de septiembre de 2026:** tabla sin relleno exterior que recorte
el hover; apertura directa de informes disponibles, progreso para trabajos en
curso y apertura automática al aprobarse; cabecera simplificada y flechas de
vuelta coherentes. En nuevo chat, la barra llega primero y después se revela
el título y las conversaciones recientes.

**Cierre:** 27 pruebas de frontend, compilación y lint sin errores; comprobación
en navegador de apertura directa, regreso, tabla y secuencia visual.
Véase [validación](../validation/2026-09-26-report-navigation-check.md).

### 2.5.13. Unificar informes y análisis en la interfaz

**Completado, 26 de septiembre de 2026:** «Informes» es la única biblioteca de
resultados, incluidos los que están en preparación o necesitan respuesta. Las
acciones y formularios usan «Crear informe», y los accesos recientes usan
«Informes recientes». Se reserva «análisis» para describir el proceso de la IA.
La navegación principal queda en Inicio, Conversaciones, Informes y Mi negocio.

**Cierre:** 28 pruebas de frontend, compilación y lint sin errores; comprobación
de navegación y formulario en el navegador. La ruta antigua del listado sigue
abriendo Informes. Véase [validación](../validation/2026-09-26-report-navigation-check.md#nomenclatura-unificada-paso-2513).

### 2.5.14. Inicio como dashboard personalizable

**Completado, 26 de septiembre de 2026:** Inicio presenta indicadores, gráficos,
hallazgos y pendientes con periodo y fuente. Selección persistente por negocio,
tarjetas fijadas u ocultas y propuestas reales del agente con aceptación explícita.
La evidencia retirada no permanece en el dashboard. Los gráficos comparten una
gama azul coherente con el acento de la interfaz, en claro y oscuro.

**Cierre:** regresión de 284 pruebas Python, 7 pruebas dirigidas tras el último
ajuste, 31 pruebas de frontend, compilación, lint sin errores y recorrido en
navegador de escritorio/móvil y ambos temas. Dos propuestas con Luna real;
conservación de fijados y aplicación explícita verificadas. Véanse
[validación y límites](../validation/2026-09-26-home-dashboard-check.md).

**Corrección del acceso vacío:** el + abre Personalizar mediante clic o teclado.
Verificado en navegador, con 31 pruebas de frontend y compilación correctas.

### 2.5.15. Bienvenida y onboarding antes del dashboard

**Completado, 27 de septiembre de 2026:** página de bienvenida con presentación
del producto y acceso al espacio; recorrido independiente por negocio, datos y
primer informe, con navegación atrás, borradores y progreso real. La interfaz
habitual se abre al publicarse el primer resultado.

**Cierre:** comprobadas entrada sin sesión, regreso, respuestas perdidas,
aislamiento y diseño en escritorio/móvil. Recorrido HTTP con datos sintéticos,
aclaraciones y publicación, incluida la integración con las entregas de archivos.
Pruebas React y del servicio web aprobadas, compilación y lint sin errores propios.
Véase [validación](../validation/2026-09-27-onboarding-check.md).

El acceso utiliza la autenticación local existente; el registro comercial no se
implementa en este paso. La bienvenida se puede abrir desde un espacio existente
sin crear ni editar negocios. La carga de datos reutiliza el servicio disponible.

**Ajuste de identidad y ejemplo:** bienvenida y dashboard reutilizan el mismo
componente de marca, con icono, color y tipografía Geist idénticos. Se añade una
[papelería ficticia](../../data/onboarding-example/README.md) con textos para el
recorrido y 12 filas CSV. Compilación y lint de los componentes modificados
correctos; totales del CSV comprobados y bienvenida revisada en navegador.

**Navegación al añadir un negocio:** el onboarding oculta el botón «Bienvenida»
cuando ya existe otro negocio en el espacio. La condición se mantiene al guardar
el nuevo negocio y recargar sus pasos. La primera alta conserva ese acceso.
Validado con las ocho pruebas de onboarding, compilación y lint focalizado.

### 2.5.16. Selección de contexto y chat acoplado

**Completado, 27 de septiembre de 2026:** herramienta de selección en el chat,
adjuntos visuales de bloques de Inicio e informes y conversación lateral ajustable.
Plegar, ampliar y recargar conservan la misma conversación y los gráficos enviados.
La página completa permite ampliar cada adjunto y regresar al bloque de origen.
Referencias versionadas, validación por negocio, retirada y recuperación del agente
incluyen todos los elementos seleccionados.

**Cierre:** 290 pruebas de regresión Python, dos pruebas adicionales de resolución
y 45 pruebas de frontend correctas; compilación y lint sin errores. Recorrido en
navegador de escritorio/móvil y con el modelo real, incluidas cifras contrastadas
independientemente y corrección de fallos encontrados. Véanse el
[plan técnico](../technical/contextual-chat-plan.md) y la
[validación y límites](../validation/2026-09-27-contextual-chat-check.md).

**Ajuste de desplazamiento:** el dashboard y los informes muestran un indicador
fino solo mientras se desplaza el contenido, sin carril permanente. Validado con
el chat lateral abierto en navegador, 45 pruebas de frontend, compilación y lint.

**Ampliación transversal:** chat y borrador persistentes entre Inicio, Mi negocio
e Informes; selección de presentación, hechos activos y resúmenes de informes.
Referencias resueltas y versionadas por el servidor, con retirada de contenido
obsoleto. Menú ordenado Inicio, Mi negocio, Informes y Conversaciones, con icono
propio para el listado de chats. Pruebas de continuidad, alcance y vigencia, más
recorrido en navegador con modelo real, registrados en la validación del paso.

**Correcciones tras uso con adjuntos:** una sola acción «Abrir en panel» desde la
conversación completa, con destino Inicio. Seleccionar la fila adjunta el informe
completo con título y tipo; la memoria aporta procedencia para contrastar su origen.
Selección sobre toda la fila, estados rojo/verde y papelera recuperable por negocio.
Validado con 299 pruebas Python, 57 frontend, compilación, lint y navegador con
modelo real. Véase [comprobación](../validation/2026-09-27-report-context-fixes.md).

**Corrección del inicio y continuidad del chat:** «Nuevo chat» abre una vista
vacía independiente en `#ask`, con el compositor abajo y sin redirigir a Inicio.
«Preguntar algo» abre directamente el panel derecho, sin barra intermedia.
El panel conserva conversación, borrador y adjuntos entre Inicio, Mi negocio,
Informes y Conversaciones. En el listado se muestra «Continuar conversación»
solo si hay una conversación o borrador que retomar; «Nuevo chat» sigue siendo
la acción principal. Se revierte la redirección introducida en el ajuste anterior.
Validado con 61 pruebas frontend, compilación, lint y navegador con modelo real;
detalle en la validación de 2.5.16.

**Conversaciones como contexto:** selección de tarjetas del listado, adjuntos con
vista previa y acceso al original. Lectura por fragmentos y búsqueda dentro de una
captura versionada, también en seguimientos; historial distinguido de evidencia.
Preguntar algo abre el panel desde el listado. El borde de la última fila de
Informes sigue las esquinas de la tarjeta. Validación automática y con modelo
real descrita en [la comprobación](../validation/2026-09-27-conversation-context-check.md).

### 2.5.17. Aclaraciones con vista de datos y recuperación

**Completado, 27 de septiembre de 2026:** las preguntas del informe, onboarding y
chat abren una tabla paginada de sus datos y destacan las columnas referenciadas.
Se impide enviar texto junto con «No dispongo de ese dato». Un bloqueo por una
aclaración no disponible permite confirmarla y crear un informe con los mismos
archivos, conservando el intento anterior. Validación HTTP, React, compilación,
lint y navegador documentada en [la comprobación de aclaraciones](../validation/2026-09-27-clarification-data-check.md).

**Ajuste de controles:** abrir la navegación pliega el chat; retomarlo vuelve a
acoplarlo. El botón + conserva el panel para escribir una conversación nueva y
los tres controles muestran etiquetas. Navegador, 51 pruebas frontend, compilación
y lint comprobados; detalle en la validación de 2.5.16.

**Conversaciones existentes:** «Abrir en panel» está disponible en la cabecera y
los menús del listado y la navegación. Conserva la conversación y el borrador,
con el informe/dashboard actual o el último origen visitado. Verificado en
navegador; 54 pruebas frontend, compilación y lint correctos.

**Distribución de las barras:** el chat pasa fuera de la tarjeta central, con fondo
gris de navegación y cabecera superior. Apertura y cierre coordinados con la barra
izquierda, respetando movimiento reducido. Revisión visual en escritorio/móvil y
ambos temas; 54 pruebas frontend, nueve dirigidas, compilación y lint correctos.

**Contraste:** gris algo más oscuro y compartido para mensajes del usuario y
resaltado activo/hover de navegación en tema claro. Revisión visual, compilación
y lint correctos.

**Navegación compacta estable:** al plegar la barra, logo, selector, accesos,
chats, informes y ayuda conservan la misma altura y posición vertical. Los
títulos «Chats recientes» e «Informes recientes» se sustituyen por separadores
en sus propias filas, y los iconos quedan en 18 px. La lista central mantiene
su desplazamiento en ventanas bajas. Verificado visualmente en el navegador,
con compilación, lint y 65 pruebas frontend correctos.

### 2.5.18. Nombres del catálogo y edición compartida de la presentación

**Completado, 30 de septiembre de 2026:** nombres automáticos del catálogo,
edición contextual desde Inicio/informe y acciones equivalentes desde el chat.
Revisiones de presentación persistentes, sincronización, historial y deshacer,
conservando cálculos, fuentes y aprobación analítica original. No se permite
cambiar el significado de una unidad mediante una edición de texto.

**Orden y comprobaciones:** seguir los pasos 2.5.18.1–2.5.18.3 del
[plan de edición de presentación](../technical/presentation-editing-plan.md).
Los tres pasos están implementados y comprobados con pruebas automatizadas,
GPT-6 Luna y navegador en escritorio/móvil. Véase la
[validación de edición compartida](../validation/2026-09-30-presentation-editing.md).

**2.5.18.4 completado:** el propietario puede aclarar la unidad visible de un
recuento sin especificar, por ejemplo «unidades registradas (paquete)», mediante
el editor o el chat. Se conserva la unidad original, sin convertir cifras.
Las acciones Editar, Fijar/Desfijar y Ocultar se agrupan en tres puntos por tarjeta.
44 pruebas backend, 120 frontend, build, lint y aceptación real con GPT-6 Luna
correctos.

### 2.5.19. Navegación sin duplicados y controles coherentes del chat

**Completado:** Inicio y Mi negocio como accesos principales; grupos únicos
Chats e Informes, nuevo chat mediante +, apertura/cierre superior del panel y
controles inversos de ampliar/reducir con retorno a la página y posición de origen.
Menú inferior de apariencia y selector superior de negocios adaptados de
`sidebar-07`, conservando el resto de la UI. Los seis pasos del
[plan separado](../technical/navigation-and-chat-plan.md) se han implementado,
probado y guardado por función. Pasan 133 pruebas frontend, compilación y lint
sin errores; revisión visual en escritorio, móvil, iconos y temas claro/oscuro.
Véanse [comprobaciones y límites](../validation/2026-09-30-navigation-and-chat.md).

### 2.5.20. Idioma, menú local y barra para preguntar

**Implementado:** + simple y alineado en la cabecera compacta de Chats; Apariencia e Idioma
como opciones del menú local; interfaz en inglés/español y barra inferior flotante centrada
para preguntar desde las páginas del negocio, compartiendo borrador y conversación
con el panel. Los cuatro pasos del [plan separado](../technical/language-and-composer-plan.md)
se implementan con pruebas, revisión y commits locales. El ajuste **2.5.20.5**
unifica chat/chats en ambas lenguas y sustituye el icono duplicado de la cabecera
de Informes por una rayita accesible. **2.5.20.6** convierte la barra en una isla
con laterales transparentes y espacio final según su altura, y elimina el halo del
campo de mensaje ([validación](../validation/2026-10-01-composer-island.md)). Pasan 161 pruebas frontend
y 128 backend seleccionadas, compilación y lint sin errores; comprobación visual
en escritorio/móvil y ambos temas. Se conserva el historial en su idioma original.
La prueba real del proveedor recibe HTTP 429; véanse [validación y límites](../validation/2026-09-30-language-and-composer.md).

**Integración de UI1 y UI2, 1 de octubre de 2026:** se unen navegación,
idioma y compositor (2.5.18–2.5.20) con la ficha y sus grupos (2.5.5) en una rama
local de integración. Se conservan ambas migraciones de datos (presentación 27,
grupos 28) y las dos responsabilidades del extractor (`memory-v7`). La ficha y
su editor de grupos usan el idioma seleccionado sin traducir el contenido del
propietario; la elección de conflicto mantiene su identidad al cambiar de idioma.
Véanse [comprobaciones de integración](../validation/2026-10-01-ui-integration.md).
La rama de calidad de informes no forma parte de esta integración.

### 2.5.21. Accesos de biblioteca, chats fijados e informes coherentes

**Alcance solicitado, 2 de octubre de 2026:** hacer reconocibles los enlaces
Chats e Informes en la barra lateral, permitir fijar/desfijar chats desde sus
tres puntos y adaptar las filas de Informes a la estética de Chats.

1. Enlaces de biblioteca con superficie amplia, flecha, hover, foco y página
   activa, conservando la acción independiente de nuevo chat.
2. Fijación persistente por negocio en PostgreSQL (migración 29). Los chats
   fijados aparecen primero en navegación y biblioteca; desfijar recupera el
   orden por último mensaje. Validar acceso, aislamiento, reintentos y recarga.
3. Informes en filas redondeadas separadas, icono circular de borde fino y
   cabeceras Estado/Creado conservadas. Mantener búsqueda, selección de contexto,
   acceso según estado, papelera y restauración; revisar escritorio y móvil.

**Completado:** 215 pruebas frontend y 21 pruebas backend dirigidas pasan;
compilación y lint sin errores, revisión en localhost de fijación/recarga y
desfijación, navegación y filas de informes en escritorio y móvil. Véanse
[comprobaciones y límites](../validation/2026-10-02-ui-ux-refinements.md).

### 2.5.22. Búsqueda de chats por contenido

1. Añadir lupa al buscador de la biblioteca de Chats y retirar el halo azul de
   foco, conservando un borde neutro para reconocer el campo activo.
2. Buscar por título, mensajes del propietario y respuestas visibles del
   asistente dentro del negocio activo; conservar fijados y excluir eliminados.
   Mostrar un fragmento de la coincidencia sin cargar historiales completos en
   el navegador ni consultar modelos.
3. Comprobar aislamiento, caracteres literales, solicitudes obsoletas, errores,
   ausencia de coincidencias, idiomas y comportamiento visual en localhost.

**Completado:** 219 pruebas frontend y 6 backend dirigidas pasan, compilación
y lint sin errores. Búsqueda por contenido y campo enfocado sin halo azul
comprobados en localhost, en escritorio y móvil. Véanse
[comprobaciones y límites](../validation/2026-10-02-chat-search.md).

## 6. Entrega 3: adaptación y ampliación de cobertura

**Avance, 27 de septiembre de 2026:** completados **3.1** (medición inicial),
**3.2** (catálogo versionado, relaciones y diagrama ER compartidos por ficha, chat
e informes) y **3.3** (investigación adaptativa por rondas, prioridades, presupuestos
y resultados parciales con cobertura de entrega). Véanse [validación de 3.2](../validation/2026-09-27-data-knowledge.md)
y [secuencia vigente](onboarding-e-informes-plan.md#8-secuencia-de-implementación-y-criterios-de-cierre).
La [validación de 3.3](../validation/2026-09-27-research-rounds.md) conserva también
los fallos de modelo, revisión y proveedor encontrados; no declara resuelta la
evaluación general de calidad prevista en 3.6. También queda completado **3.3.1: estabilización del revisor**: reparos materiales
frente a sugerencias, registro de resolución, auditoría de entrega y reintentos
acotados de 429. Se contrastan un informe completo (2/2), uno parcial (2/3),
49 valores y recuperación sin duplicaciones. La prueba adversarial bloquea una
cifra falsa y un adjunto inexistente en la misma revisión. Véanse
[contrato](../technical/reviewer-stability.md) y [validación, fallos y límites](../validation/2026-09-27-reviewer-stability.md).
Completado **3.4: onboarding conversacional y elección abierta del objetivo**, con
confirmación de alcance y continuidad en el mismo chat ([contrato](../technical/conversational-onboarding-plan.md),
[validación](../validation/2026-09-27-conversational-onboarding.md)).
La prueba manual posterior corrige el progreso dentro del onboarding, la exposición
de contexto interno y la recuperación explícita de revisiones agotadas, conservando
borrador, reparos y cálculos; el primer informe de prueba se recupera y contrasta
sin nuevas ejecuciones numéricas.
Completado **3.4.1: conocimiento de datos y utilidad del informe**,
según el [plan de mejora](../technical/agent-data-discovery-plan.md), motivado por la prueba manual de Bruma Café.
Incluye propuestas de relaciones por el agente, comprobaciones completas, auditoría de utilidad
y citas a series guardadas. Véase la [validación, intentos fallidos y límites](../validation/2026-09-27-agent-data-and-insights.md).
Completado **3.5: analistas en paralelo**, con delegación dirigida, expansión desde
la evidencia de las ramas, cuotas globales, recuperación y síntesis priorizada.
El informe de Bruma profundiza ahora en productos dentro del canal que disminuye;
los gráficos acompañan a sus hallazgos. Véanse el [contrato](../technical/parallel-analysts-plan.md)
y la [validación, iteraciones y límites](../validation/2026-09-27-parallel-analysts.md).
**3.6: implementación y evaluación terminadas, 28 de septiembre.** Se compararon
16 intentos en modo secuencial y paralelo: ocho aprobados internamente, cuatro
aceptados independientemente. Se conservan fallos, recursos y referencias históricas;
se corrigen contratos, cobertura, preservación de evidencia y entrega parcial.
El lote posterior acepta 1/4 y dos revisiones fallidas se recuperan con 2/2 aceptadas,
sin repetir investigación. Pasan 209 pruebas backend y 78 frontend, más controles
específicos posteriores. Véanse [protocolo](../technical/quality-evaluation-plan.md)
y [resultados y límites](../validation/2026-09-27-quality-evaluation.md).
La aceptación general de calidad sigue abierta: falta profundidad y cobertura
consistentes; no está demostrada una mejora general de tiempo o coste del paralelismo.
El antiguo paso 3.5 de evaluación conserva su nueva numeración 3.6.

**3.7 implementado y evaluado, 28 de septiembre:** planificador de negocio especializado, encargo compartido,
diálogo con el analista y preguntas al cliente durante la investigación. Presupuesto
orientado a calidad y comparación controlada con el planificador desactivado.
Véanse el [plan técnico y registro de continuidad](../technical/business-planner-plan.md)
y los [resultados de 24 intentos y tres recuperaciones](../validation/2026-09-28-business-planner.md).
La capacidad funciona; no queda demostrada una mejora consistente de calidad ni de
latencia. Se mantienen abiertos los criterios de aceptación general del producto.

**3.8.9, correcciones de auditoría validadas:** preparación de memoria antes del
manifiesto, recuperación conservando versiones, proceso visible del chat, tiempos
reales y monitor con intercambios legibles. Bruma recuperado y aprobado con
contexto vigente. Ver [evidencia y límites](../validation/2026-09-28-live-investigation-fixes.md).

**3.8 implementado y validado, 28 de septiembre:** actividad del cliente con
historial persistente y datos relacionados; monitor interno con actores reales,
intercambios, cálculos, revisión y recursos. Autorización interna independiente,
eventos ordenados por commit, recuperación etiquetada y GET sin efectos.
Bruma real: tres subanalistas, 22 llamadas y tres cálculos; 92 pruebas de interfaz
y suites de PostgreSQL/sandbox pasan. Medida local hasta pantalla: 1,54 s.
Véanse [uso y contratos](../technical/live-investigation.md), [plan completado](../technical/live-investigation-plan.md)
y [validación con límites](../validation/2026-09-28-live-investigation.md).
Su cierre no implica aceptación de calidad analítica.

**3.9 en evaluación, actualizado el 2 de octubre:** [calidad de la entrega y autonomía de
investigación y presentación](../technical/report-quality-plan.md). El planificador
prioriza preguntas de negocio y el analista decide métodos, desgloses y visuales;
el código garantiza integridad y el revisor comprueba utilidad. Profundizar en el
segmento y periodo de la señal, cuantificar sus componentes y entregar prioridades,
comprobaciones y reacciones condicionales concretas. Ampliar representaciones
temporales y de varias series, interacción y cobertura del encargo del propietario.
Seis incrementos implementados y verificados: regresión final de 533 pruebas Python
y 117 web previamente verificadas; [resultados originales](../validation/2026-09-30-report-quality.md)
y [reanudación tras recarga](../validation/2026-10-01-report-quality.md).
Comparación original en Bruma/WWI ejecutada sin mejora consistente demostrada.
Tras restablecer saldo se conservan los fallos anteriores y se obtienen dos
entregas aceptadas de seis intentos nuevos. La aceptación conjunta sigue abierta. La consulta
web queda como propuesta posterior 3.95, con alcance específico todavía pendiente.
El [ajuste del 2 de octubre](../validation/2026-10-02-report-quality.md) estabiliza
el encargo original, distingue bloqueos de mejoras opcionales y verifica los grupos
entregados. Pasan 547 pruebas Python más una de persistencia, 62 dirigidas del
ajuste final y 117 web. Los pilotos mejoran profundidad y comprobaciones, pero dos
descubrimientos no pasan utilidad; Bruma pasa como parcial y organización se
recupera sin sustituir el fallo original. 3.9.7 sigue abierto.

El [diagnóstico posterior de 429](../validation/2026-10-02-provider-diagnostics.md)
añade motivo y cabeceras de límites a los intentos persistidos, distingue saldo o
cuota de rechazos temporales y respeta esperas sin acortarlas. Pasan 555 pruebas
Python. Una petición mínima confirma 200.000 TPM y 500 RPM; la presión histórica
de tokens es una hipótesis, sin causa específica guardada para cada rechazo.
La dosificación compartida de tokens sigue pendiente. El experimento manual Luna
directo se amplía, con autorización del propietario, a [dos rondas de tres informes](../validation/2026-10-02-codex-luna-comparison.md):
mejora la profundidad con instrucciones explícitas, pero ninguna de las seis
entregas pasa todos los criterios. Una pasa descubrimiento como análisis parcial;
quedan defectos de presentación. No se altera la aceptación de 3.9.7.


**Planificación ampliada, 27 de septiembre de 2026:** el
[plan de onboarding e informes](onboarding-e-informes-plan.md) concreta la secuencia
3.1–3.6: evaluación con una base sustancial, catálogo y relaciones,
investigación por rondas, onboarding conversacional, analistas en paralelo y
selección, revisión y evaluación orientadas al objetivo. Incorpora una pregunta abierta con opciones para descubrir oportunidades,
organizar un dashboard, seguir la evolución o resolver una pregunta. Las
predicciones se reservan como capacidad futura. El estado de ejecución vigente
se indica en el avance anterior y en el plan enlazado.

**Prioridad actualizada, 23 de septiembre de 2026:** iniciar las ampliaciones siguientes después de cerrar la entrega 2.5. La evaluación del 22 de septiembre descrita a continuación ya se realizó; no se presenta como trabajo pendiente ni sustituye la regresión exigida por los cambios de memoria y conversación.

**Orden acordado:** antes de incorporar nuevas capacidades, repetir la evaluación
del recorrido actual con GPT-6 Luna sobre casos variados del paso 1.7, incluyendo
datos problemáticos, ambigüedad, correcciones y recuperación. Registrar exactitud,
utilidad del informe, preguntas, revisiones, tiempo y coste; corregir los fallos
repetidos y dejar documentados los límites de la base. Después, ampliar por
escenarios comprobables. La investigación web de contexto descrita abajo es una
de esas ampliaciones; no se añade a la ronda de validación inicial.

**Validación realizada, 22 de septiembre de 2026:** 27/36 aceptados en la matriz
inicial de Luna; tras corregir preguntas redundantes y contratos del informe,
18/18 en la repetición dirigida, 3/3 correcciones del propietario y recuperación
de una sesión interrumpida. Pasan 141 pruebas automatizadas. La ronda previa
queda terminada; persisten ineficiencias y límites de generalización que se
mantienen explícitos al ampliar. Ver [resultados, costes y límites](../validation/2026-09-22-luna-validation.md).

**Construir por escenarios completos:**

- Excel `.xlsx`, varias hojas y selección de tablas.
- Detalle de tickets, descuentos y devoluciones.
- Archivos complementarios durante las aclaraciones.
- Relaciones comprobables entre tablas y fuentes agregadas/detalladas de la misma actividad.
- Corrección de interpretaciones, invalidación y recálculo de resultados dependientes.
- Investigaciones adicionales cuando los datos más ricos las permiten.
- Investigación web de contexto de negocio, comenzando por festivos y eventos
  de una localidad y periodo concretos, con fuentes y límites verificables.

**Cierre:** superar la matriz del MVP: continuar sin datos opcionales, profundizar al recibirlos, evitar duplicaciones, revisar conclusiones al cambiar premisas y entregar informes breves cuando corresponda. Cada capacidad se comprueba desde la interpretación hasta su explicación en el informe.

**Por qué aquí:** ampliar una base completa permite localizar si un problema viene de la capacidad nueva o del recorrido básico. CSV primero es una secuencia de implementación, no un recorte del soporte Excel acordado para el MVP.

### Investigación web de contexto de negocio

**Estado:** ampliación acordada, pendiente de implementar y evaluar después de la
ronda de validación del recorrido actual. No requiere construir primero toda la
organización multiagente objetivo.

**Objetivo:** investigar hechos externos pertinentes para las preguntas del
negocio y contrastarlos con los datos aportados. Por ejemplo, comprobar si una
variación de ventas coincide con un festivo local o un evento cercano. La
información externa puede aportar contexto o sugerir una investigación; una
coincidencia temporal no demuestra que el evento haya causado el cambio.

**Primer escenario:** festivos y eventos públicos en una localidad durante las
fechas del archivo. Pedir municipio, barrio o dirección solo con el nivel de
precisión necesario y sin adivinar la ubicación. Distinguir fecha de publicación
de la fuente y fecha del hecho; no aplicar eventos actuales a datos históricos.
Si falta ubicación, no hay fuentes fiables o la búsqueda falla, continuar con el
análisis del archivo y explicar qué contexto no se pudo comprobar.

**Construir:** una herramienta acotada de búsqueda y consulta de fuentes públicas,
preferentemente oficiales, fuera del sandbox de Python, que conserva su aislamiento
sin red. Enviar a la búsqueda solo el contexto necesario, no el CSV ni cifras
privadas del negocio. Tratar el contenido recuperado como información no confiable,
nunca como instrucciones para los agentes. Fijar límites de consultas, tiempo y
coste, y guardar resultados para recuperar el trabajo sin repetir búsquedas ya
resueltas innecesariamente.

Cada hecho externo debe conservar URL, fuente, fecha de consulta, fecha o periodo
del hecho, ámbito geográfico y evidencia pertinente. El analista debe distinguir
datos calculados, hechos externos documentados e hipótesis. El revisor comprueba
la correspondencia de lugar y periodo, la solidez de las fuentes y que el informe
no transforme asociaciones en causas. El informe muestra citas y limitaciones
junto a las afirmaciones que dependen de esas fuentes.

Esta capacidad encaja con el futuro agente de contexto de negocio: investigaría
y entregaría hechos documentados al analista. Su separación en un agente propio
se decidirá al evaluar la arquitectura, sin hacerla requisito de la primera prueba.

**Comprobar antes de ampliar:** comparar el mismo caso con y sin contexto web;
evaluar utilidad añadida, precisión geográfica y temporal, atribución de fuentes,
tiempo y coste. Incluir un evento confirmado, otro municipio con un nombre similar,
información histórica, fuentes contradictorias o ausentes y contenido con
instrucciones maliciosas. El sistema debe expresar incertidumbre y continuar sin
información opcional. Solo ampliar a otros factores de negocio cuando esta primera
investigación aporte valor sin degradar la exactitud del informe.

## 7. Entrega 4: preparación operativa del piloto

**Construir y comprobar:** despliegue privado; interrupciones y reintentos; peticiones duplicadas; trabajos y usuarios concurrentes sin mezclar datos; agotamiento de recursos; archivos defectuosos e instrucciones maliciosas en celdas; permisos; borrado; copias de seguridad y restauración; registros; costes y tiempos; detención de trabajos; y vuelta a una versión compatible.

Repetir escenarios y probar formatos reservados no utilizados para ajustar el sistema. Fijar los límites del piloto a partir de las mediciones.

**Cierre:** condiciones del bloque 7 cumplidas: casos obligatorios superados, sin fallos críticos conocidos pendientes, recuperación y aislamiento comprobados y límites establecidos. Superar la batería no demuestra ausencia universal de errores.

**Por qué aquí:** ya existe suficiente recorrido y variedad para medir el comportamiento del conjunto. Los controles esenciales se han incorporado antes; esta entrega verifica su funcionamiento integrado.

## 8. Entrega 5: piloto y correcciones

**Realizar:** piloto con los 3–5 comercios previstos, todavía por reclutar. Observar si aportan datos, entienden preguntas, reconocen su negocio en el informe, comprueban cifras y encuentran una observación o siguiente paso útil. Medir la intervención manual necesaria.

Revisar inicialmente los informes conforme al bloque 7, registrar las correcciones y convertir los fallos en nuevos casos de evaluación. No confundir ayuda manual con capacidad autónoma del producto.

**Resultado esperado:** evidencia de utilidad y comprensión, problemas observados y correcciones verificadas. Las intervenciones manuales habituales indican que falta cumplir el objetivo de autonomía. El piloto no valida por sí solo demanda comercial ni disposición a pagar.

**Por qué aquí:** evita que problemas básicos de lectura, acceso o recuperación dominen la prueba con comercios. La preparación del reclutamiento puede avanzar antes del piloto.

## 9. Decisiones y límites que se mantienen

- Python generado y ejecución aislada pertenecen a la entrega 1, no a una ampliación posterior.
- PostgreSQL es la opción inicial; se mantiene abierta la posibilidad de Convex tras comprobar la integración.
- La entrega 2.5 mantiene PostgreSQL y almacenamiento privado; cambiar de proveedor no es un requisito de memoria compartida.
- Revisor, comprobaciones y evidencia forman parte del primer recorrido completo.
- Las pruebas acompañan cada paso; el control de calidad no se aplaza a la entrega 4.
- El almacenamiento registra procedencia y versiones; no obliga a un esquema universal de ventas.
- Chat posterior, memoria entre conversaciones, «Mi negocio» e Inicio interactivo acotado pasan a la entrega 2.5. ML predictivo, PDF, editor de dashboards/filtros abiertos, conectores y automatización periódica siguen fuera de esa ampliación.
- Modelos, proveedores, entorno de ejecución, framework web, componentes reutilizables y límites numéricos se concretan cuando desbloquean la entrega correspondiente. No se fijan plazos sin estimar el trabajo y medir los primeros pasos.

## 10. Punto de inicio

**Primer avance del 21 de septiembre de 2026:** los [tres casos de referencia](../../data/reference-cases/README.md) tienen CSV, contexto, variantes de columnas y respuestas numéricas separadas del material del agente. Las referencias se contrastaron con los datos originales mediante un cálculo independiente. Esto validó los casos antes de implementar el agente; sus capacidades y evaluaciones posteriores se registran a continuación. La revisión independiente de preguntas, conclusiones y utilidad sigue siendo necesaria.

**Avance de implementación del 21 de septiembre de 2026:** se han materializado las primeras estructuras del paso 1.1 —negocio, análisis, fuente y tabla preparada— y la ingesta y persistencia del paso 1.2. PostgreSQL local conserva metadatos; los originales y Parquet se guardan por separado. El lote WWI conserva 48 tablas y 4.713.833 filas. Se comprobaron todos los valores, reenvío sin duplicación del lote y recuperación tras reiniciar PostgreSQL. Las estructuras de preguntas, investigaciones, ejecuciones y resultados se incorporarán con sus capacidades. Ver [implementación](../technical/ingestion.md) y [resultados de la prueba](../validation/2026-09-21-ingestion-check.md).

**Avance del paso 1.3, 21 de septiembre de 2026:** ejecutor Docker dentro de Colima local, bibliotecas versionadas, entradas de solo lectura, sin red ni credenciales y límites de recursos. Nuevas estructuras de ejecuciones, resultados candidatos y artefactos con código, hashes y procedencia. Cálculo de referencia y cálculo sobre las 48 tablas WWI contrastados; recuperación y fallos deliberados comprobados. Ver [guía](../technical/sandbox.md), [plan técnico](../technical/sandbox-plan.md) e [informe](../validation/2026-09-21-sandbox-check.md).

**Avance del paso 1.4, 21 de septiembre de 2026:** agente principal con LangGraph, catálogo y perfiles, planes provisionales, preguntas materiales, respuestas desde terminal y checkpoints PostgreSQL. La recuperación se comprobó con procesos distintos y un modelo simulado. La prueba real con Qwen en LM Studio detectó una definición monetaria inventada, por lo que este paso no se considera aceptado todavía. Ver [guía y mapa de archivos](../technical/agent.md), [plan técnico](../technical/agent-plan.md) y [resultados con sus límites](../validation/2026-09-21-agent-check.md).

**Avance del paso 1.5, 21 de septiembre de 2026:** por decisión del usuario se avanza con Python manteniendo abierto [DR-001](../validation/known-agent-errors.md). El principal elige investigaciones, genera y ejecuta código, recibe errores, registra candidatos y conserva evidencia. Cambiar el contexto invalida resultados anteriores y permite recalcular. Ver [guía](../technical/research.md), [plan técnico](../technical/research-plan.md) y [validación](../validation/2026-09-21-research-check.md).

**Avance del paso 1.6, 21 de septiembre de 2026:** analista y revisor intercambian informes, reparos y justificaciones con contexto persistente. Ambos pueden ejecutar Python; el revisor controla la aprobación. Las preguntas al propietario pausan el grafo, y sus respuestas invalidan evidencia anterior. La aplicación comprueba referencias y relaciones numéricas y genera HTML escapado con evidencia y conversación. La prueba adversarial corrigió DR-001, pero otra prueba detectó DR-002: aprobación incorrecta del revisor, bloqueada por un control independiente. La implementación está disponible; la calidad del revisor no se da por aceptada. Ver [guía](../technical/review.md), [plan técnico](../technical/review-plan.md) y [validación con límites](../validation/2026-09-21-review-check.md).

**Ampliación del paso 1.6:** separar el HTML interno del informe del cliente. Incorporar contexto de negocio, cobertura, interpretaciones, siguientes comprobaciones y gráficos de barras/líneas/tablas con valores provenientes de métricas guardadas. El revisor examina ese contenido antes de aprobarlo. Ver [contrato y presentación](../technical/client-report.md). La entrega 2 integra este informe en la aplicación web; no aplaza su contenido.

**Trabajo realizado, 22 de septiembre de 2026:** construida y ejecutada la evaluación del paso 1.7. Se implementaron el ejecutor reproducible, las referencias independientes y la rúbrica que distingue aprobación del modelo de aceptación. La matriz real aceptó 11 de 24 casos; la serie posterior con correcciones del controlador aceptó 6 de 9. Las tres correcciones del propietario invalidaron la aprobación anterior y recalcularon, pero solo uno de los tres informes nuevos pasó. Las 101 pruebas automatizadas pasan. Se conservan fallos, versiones, tiempos y evidencia. Ver [método y comandos](../technical/evaluation-plan.md) y [resultados de las pruebas](../validation/2026-09-21-evaluation-check.md). Hasta ese momento solo se había evaluado Qwen local; los resultados posteriores con Luna se documentan más abajo.

La entrega 1 completa todavía no está aceptada: ya existe el recorrido interno desde la ingesta hasta un informe revisado, pero las pruebas del paso 1.7 todavía muestran fallos semánticos y de continuidad. La ejecución de la evaluación ha terminado; el criterio de aceptación sigue abierto. Las pruebas realizadas no equivalen a validación general del producto.

**Avance de entrega 2, 22 de septiembre de 2026:** aplicación web local sobre el
backend existente, con 117 pruebas automatizadas correctas y validación mediante
Computer Use en escritorio y móvil. Se comprobaron las preguntas del modelo real,
recuperación tras reiniciar el servidor, informe con gráficos y evidencia, y su
retirada tras la detección independiente de DR-015. La aplicación queda utilizable
para explorar la experiencia; no se acepta la calidad analítica ni se habilita el
piloto comercial. Ver [validación](../validation/2026-09-22-web-check.md).

**Prueba de proveedor, 22 de septiembre de 2026:** integración OpenAI con GPT-6
Luna y recorrido web real sobre ventas diarias. Las 127 pruebas automatizadas
pasan. El resumen coincide con las cifras independientes; la suma de llamadas
al modelo baja a 72,27 segundos frente a 1.007,90 del recorrido local anterior,
con menor contenido y sin gráfico. Esta prueba única no sustituye la matriz de
1.7 ni cierra su aceptación. Ver [comparación y límites](../validation/2026-09-22-openai-check.md).

**Ampliación visual de entrega 2, 22 de septiembre de 2026:** series con evidencia
guardadas desde Python, tarjetas y gráficos integrados, cobertura explícita de las
investigaciones y revisión de utilidad. La prueba real con GPT-6 Luna sobre 36.331
líneas y 219 productos produjo dos gráficos contrastados con referencias
independientes en 72,82 segundos; el revisor devolvió el primer borrador y aprobó
su corrección. Una prueba dirigida también rechazó un informe temporal incompleto.
La aceptación general de 1.7 sigue abierta. Ver [validación y límites](../validation/2026-09-22-visual-report-check.md).

**Validación previa a entrega 3, 22 de septiembre de 2026:** ampliados los casos
de 1.7 a doce escenarios, con duplicados, importes ausentes, devoluciones y
fechas/importes inválidos. La matriz inicial de Luna acepta 27/36; se conserva
un informe retenido por retirada indebida de resultados monetarios. Se corrigen
preguntas redundantes, emparejamiento de unidad/serie y cobertura de investigaciones
bloqueadas, y se mejora la guía de series de un punto. La repetición dirigida
acepta 18/18 y las correcciones del propietario 3/3; la recuperación real conserva
las respuestas y la evidencia. Pasan 141 pruebas. La ronda queda completada y
permite ampliar por escenarios; no equivale a aceptación general del MVP.
DR-019 sigue parcialmente mitigado: hay intentos innecesarios recuperables.
Ver [validación completa](../validation/2026-09-22-luna-validation.md) e
[incidencias](../validation/known-agent-errors.md).

**Planificación de entrega 2.5, 23 de septiembre de 2026:** revisados esquema, creación de trabajos web, contexto de planificación/investigación/revisión, invalidación y navegación. Se añaden siete pasos para identidad persistente, memoria, contexto transversal, chat, «Mi negocio», Inicio y evaluación. Se actualizan alcance y definición del producto para adelantar estas capacidades. Este avance corresponde solo a análisis y documentación: ninguno de los pasos 2.5.1–2.5.7 está implementado o aceptado por esta actualización.

**Cierre de 2.5.1, 23 de septiembre de 2026:** identidad y selección persistentes, perfil guardado antes del análisis, migración compatible y rutas limitadas al negocio activo. Dos preguntas reales reutilizaron negocio y lote con cifras verificadas independientemente; perfil e informes sobrevivieron a reinicio y cambio de negocio. Pasan 155 pruebas automatizadas, sintaxis JavaScript y revisión de diferencias. Los pasos 2.5.2–2.5.7 siguen pendientes. Ver [validación y alcance](../validation/2026-09-23-business-identity-check.md).

**Cierre de 2.5.2, 23 de septiembre de 2026:** memoria estructurada en PostgreSQL, revisiones, corrección/retirada, extracción desde perfil y nuevas aclaraciones, recuperación y estado web. Pasan 181 pruebas y 24/24 escenarios de extracción real tras corregir el tratamiento de fechas ambiguas. Se conservan resultados previos y límites; reutilización en el agente, chat y ficha siguen pendientes. Ver [validación](../validation/2026-09-23-memory-check.md).

**Decisión de arquitectura registrada, 23 de septiembre de 2026:** acordada recuperación dirigida por el agente, relaciones explícitas entre fuentes, recuerdos, investigaciones, informes y futuros mensajes, y búsqueda gradual sobre descripciones/fragmentos. Se concretan el tratamiento de índices derivados, manifiestos y controles de vigencia, y se añaden comprobaciones de cierre a 2.5.3–2.5.4. Este cambio solo registra el diseño para su aplicación posterior; no implementa ni cierra esos pasos.


**Cierre de 2.5.3, 23 de septiembre de 2026:** contexto inicial persistente, recuperación dirigida por el agente sobre datos/memoria/antecedentes, manifiesto de lo entregado y correcciones entre sesiones. Se comprueba vigencia al reanudar y publicar, se conservan periodos históricos y la web permite recalcular con la memoria actual. Pruebas automatizadas, casos reales y límites de búsqueda documentados en la [validación](../validation/2026-09-23-context-check.md). El chat se implementa a continuación en 2.5.4.

**Cierre de ampliación semántica de 2.5.3, 23 de septiembre de 2026:** OpenAI embeddings + pgvector y búsqueda híbrida integrados en datos, memoria e informes, con caché versionada y degradación textual explícita. Pasan 214 pruebas; 60 búsquedas reales sitúan el esperado entre los tres primeros en todos los casos del corpus pequeño; Luna reutiliza un antecedente y respeta la corrección de 80 a 30. Ver [validación y límites](../validation/2026-09-23-semantic-check.md). El siguiente paso sigue siendo 2.5.4.


**Cierre de 2.5.4, 23 de septiembre de 2026:** conversaciones persistentes, memoria entre chats, antecedentes semánticos con referencias originales, investigación sobre datos existentes y respuestas breves basadas en evidencia revisada. Incluye aclaraciones, reintento explícito, conservación de intentos e informe vinculado bajo petición. El recorrido real con Luna comprueba un total de 80, explicación sin recalcular, corrección de memoria y recuperación de una hipótesis reformulada. Véanse [implementación](../technical/conversations.md) y [validación y límites](../validation/2026-09-23-conversations-check.md). El siguiente paso es **2.5.5: Mi negocio y datos reutilizables**.


**Cierre de 2.5.5, 23 de septiembre de 2026:** ficha consultable y editable con origen, vigencia y revisiones; carga independiente de CSV, reenvíos exactos, conjuntos/versiones explícitos y conservación de originales. Una actualización conserva los informes históricos; una corrección retira los resultados afectados y requiere un cálculo nuevo. Pasan 241 pruebas Python, 7 JavaScript y 6 comprobaciones con Luna real, incluido el cambio de total revisado de 80 a 100 al corregir datos. Véanse [contratos](../technical/business-dossier.md) y [validación](../validation/2026-09-23-dossier-check.md). El siguiente paso previsto entonces era cerrar **2.5.6**.


**Cierre de 2.5.6, 23 de septiembre de 2026:** Inicio y navegación cotidiana completos dentro del alcance local: preguntas vinculadas a revisión/hallazgo/fuentes, chat con gráficos y versión de datos, actividad real previa al informe, biblioteca filtrable y compositor sin ocultar resultados. Se valida con 243 pruebas Python, 12 JavaScript y recorrido con Luna sobre un informe histórico v2, sin cambiar a v3 ni crear otro cálculo. Se corrige también el refresco que reemplazaba el onboarding. Véase [validación](../validation/2026-09-23-daily-ux-check.md). El siguiente paso es **2.5.7**, evaluación integrada.

**Cierre de 2.5.7, 24 de septiembre de 2026:** completada la evaluación integrada y corregidos los dos fallos de presentación reproducidos. Memoria y antecedentes entre chats, selección de datos, invalidación por corrección, cifras y series independientes, aislamiento y recuperación comprobados con Luna real y navegador; 245 pruebas Python y 12 JavaScript pasan. El alcance local de la entrega 2.5 queda cerrado. Véase [validación integrada](../validation/2026-09-24-integrated-check.md); la ampliación de cobertura de la entrega 3 sigue pendiente.

**Ajuste de experiencia tras 2.5.7, 25 de septiembre de 2026:** se incorpora desplazamiento hacia nuevos mensajes, indicador de respuesta y cola persistente, eliminación recuperable de chats, panel lateral ajustable y barra de desplazamiento discreta. La cola conserva el orden de respuesta y pospone la memoria de cada mensaje hasta su turno. Véanse [alcance y comprobaciones](../validation/2026-09-25-chat-ux-check.md). Este ajuste no cierra la entrega 3.

**Correcciones explícitas y superficies, 25 de septiembre de 2026:** una petición inequívoca del propietario para sustituir un dato vigente se guarda como nueva revisión antes de contestar; si el texto antiguo solo aparece en el perfil, se sustituye allí de forma acotada y se declara un recuerdo específico. Las contradicciones sin una instrucción clara siguen requiriendo revisión. El chat muestra una sola acción para los casos pendientes, y las cajas pierden el borde permanente y los tonos amarillos del texto. Véanse [comprobaciones](../validation/2026-09-25-explicit-correction-check.md). La entrega 3 sigue pendiente.

**Historial visible tras cambios de contexto, 25 de septiembre de 2026:** las respuestas anteriores permanecen en el chat como historial y una línea discreta señala desde qué mensaje rige el contexto actualizado. Los resultados vinculados a informes antiguos se identifican como anteriores y solo pueden recalcularse mediante la acción correspondiente. El agente continúa filtrando el historial antiguo para no tratarlo como evidencia actual. Véanse [comprobaciones](../validation/2026-09-25-chat-history-check.md).

**Orden de chats y ficha compacta, 25 de septiembre de 2026:** las conversaciones se ordenan por el último mensaje enviado por el propietario; abrir una conversación no modifica el orden. «Mi negocio» agrupa la información vigente en negocio, preferencias, datos y asuntos por revisar, con búsqueda, edición al interactuar y procedencia desplegable. Véanse [comprobaciones](../validation/2026-09-25-dossier-ux-check.md). No cambia el estado de aceptación de la entrega 3.

**Ajuste de conversación, 25 de septiembre de 2026:** se distingue visualmente el chat abierto incluso si queda fuera de los seis más recientes, sin cambiar su orden. El resaltado al pasar el cursor abarca la fila completa, incluida la X, que no tiene fondo propio. «En cola» solo aparece si hay otro turno anterior pendiente de ejecución o respuesta; los resultados anteriores caducados, fallidos o completados no generan una cola ficticia. Las respuestas breves del agente se ajustan a su texto, mientras que los resultados con métricas o gráficos conservan el ancho necesario. Véanse [comprobaciones](../validation/2026-09-25-chat-bubbles-check.md).

**Listado de conversaciones, 25 de septiembre de 2026:** la biblioteca de chats muestra tarjetas separadas y más compactas, con título y fecha del último mensaje. Toda la tarjeta es un enlace y cambia de fondo al pasar el cursor o recibir foco; la acción de eliminar permanece independiente. Se elimina el texto redundante «Abrir conversación». Véanse [comprobaciones](../validation/2026-09-25-conversation-list-check.md).

**Confirmación de eliminación y centrado, 25 de septiembre de 2026:** el listado de conversaciones se centra dentro del área de contenido. La eliminación usa un diálogo de la aplicación con título del chat, aviso de que ya no se podrá acceder a la conversación y acciones de cancelar o eliminar, en lugar de la confirmación del navegador. No se muestra una sección de chats eliminados ni se ofrece restauración al usuario. Véanse [comprobaciones](../validation/2026-09-25-delete-dialog-check.md).

**Gráficos y continuidad del chat, 28 de septiembre de 2026 (3.8.10):** dimensiones
explícitas para comparaciones agrupadas, leyendas coherentes, actividad pública
compacta y presentación progresiva del texto ya revisado. Metadatos de aprobación
accesibles al asistente. Ver [validación](../validation/2026-09-28-charts-and-chat-flow.md).

**Lectura breve y descarga, 28 de septiembre de 2026 (3.8.12):** resumen compacto,
contexto/hallazgos desplegables e icono de descarga con PDF completo, sin secciones
ocultas en la exportación. Se conservan aprobación, referencias y paleta.
Ver [plan](../technical/report-reading-plan.md) y
[validación](../validation/2026-09-28-report-reading-and-pdf.md).

**Lectura progresiva, 2 de octubre de 2026 (3.8.12.1):** cada hallazgo reúne su
conclusión y gráficos en una tarjeta; el detalle se abre debajo, sin desplazar
el gráfico. Contexto mediante «Sobre este informe», tres indicadores iniciales
y advertencias completas visibles. Inicio relaciona gráfico y conclusión de la
misma revisión y enlaza al hallazgo exacto, conservando selección y personalización.
Se comprueban 202 pruebas frontend, 18 pruebas finales de los componentes tocados,
3 pruebas de PDF, compilación, lint y recorrido en escritorio/móvil.
Véanse [incremento del plan](../technical/report-reading-plan.md#38121-lectura-progresiva-del-informe-y-de-inicio)
y [validación y límites](../validation/2026-10-02-report-reading-progressive.md).


**Integración de UI y calidad, 2 de octubre de 2026:** se fusiona primero
`feature/ui-integration` (incluye producto UX) en `master` mediante el
[PR #7](https://github.com/jaimebernalm/decision-room/pull/7), y se incorpora esa base
a `feature/report-quality`. La resolución conserva lectura progresiva,
orientación de decisiones, interacción y evidencia exacta de 3.9.
Véanse [secuencia y comprobaciones](../validation/2026-10-02-ui-quality-integration.md).
La aceptación analítica **3.9.7 sigue abierta**.

**Primera lectura y síntesis conjunta, 2 de octubre de 2026 (3.9.8):** resumen
revisado completo al inicio, índice de hallazgos, orientación en bloques y fechas
localizadas; tooltips y periodos largos legibles en móvil. Planificador, analista
y revisor reciben instrucciones de síntesis y diagnóstico editorial sin alterar
evidencia ni aprobación. Pasan 607 pruebas Python, 223 frontend, compilación y
lint; tres redacciones sobre evidencia congelada pasan controles y revisión del
experimento. Bruma reduce la primera lectura de 759 a 578 palabras; en WWI el
cambio es mínimo. No demuestra mejora analítica consistente ni cierra 3.9.7.
Véanse [incremento del plan](../technical/report-reading-plan.md#398-primera-lectura-y-síntesis-sobre-la-interfaz-integrada)
y [validación](../validation/2026-10-02-report-reading-and-synthesis.md).

**Bruma Café en la web habitual, 2 de octubre de 2026 (3.9.8.1):** rama
`codex/feature/bruma-web-integration`, con calidad, los ajustes terminados de UI y
la búsqueda de chats. La aplicación local habitual ofrece el informe original y
una síntesis corregida con aprobación real como entrega parcial; conserva las
cuatro visualizaciones y la evidencia congelada. Se resuelve la compatibilidad
de informes históricos sin modificar aprobaciones. Los intentos de revisión
limitados o inválidos quedan registrados y 3.9.7 permanece abierto. Véanse
[pasos](../technical/report-reading-plan.md#3981-bruma-café-en-la-web-habitual) y
[validación](../validation/2026-10-02-bruma-web-integration.md).

**Jerarquía y leyenda del informe, 2 de octubre de 2026 (3.9.8.2):** títulos
de hallazgos mayores que los títulos de gráficos, series visibles oscuras y
ocultas atenuadas con texto tachado y ojo cerrado. La leyenda explica la acción
y permite restaurar una serie con clic o teclado. El selector de puntos deja
de aparecer cuando no hay un desglose guardado; si existe, queda en un detalle
plegado. Pasan 233 pruebas frontend, compilación y lint; verificado en Bruma
en la web habitual. Véanse [pasos](../technical/report-reading-plan.md#3982-jerarquía-de-hallazgos-y-control-de-series)
y [validación](../validation/2026-10-02-report-hierarchy-and-legend.md).

**Lectura continua y leyenda discreta, 2 de octubre de 2026 (3.9.8.3):** se
retira el fondo oscuro de las series y se utiliza gris al señalar la leyenda.
Curvas y nombres se resaltan entre sí; las series ocultas tienen un ojo cerrado.
Los hallazgos se presentan como secciones con separadores y un enlace discreto
a datos y fuentes. Método, evidencia y cifras exactas se abren juntos, sin la
cadena de desplegables. Pasan 236 pruebas frontend, compilación y lint, y se
comprueba Bruma en el puerto habitual. Véanse [pasos](../technical/report-reading-plan.md#3983-lectura-continua-y-leyenda-discreta)
y [validación](../validation/2026-10-02-report-continuous-reading.md).

**Expresividad de agentes y comparación nueva con Luna (3.9.9):** ampliación
solicitada para que el analista elija capas observadas, derivadas o de referencia
con estilos explícitos. La media móvil es una posibilidad verificada, no un
formato obligatorio. Después se investiga de nuevo con el mismo encargo y los
mismos CSV de Luna ronda 2, run 3, conservando errores y recursos. Se siguen
[los pasos de implementación y evaluación](../technical/report-quality-plan.md#399-expresividad-de-los-agentes-y-nueva-comparación-con-luna).
Estado: capacidad implementada y comprobada, con piloto nuevo en la aplicación
habitual. 25 referencias correctas; 18/24 en evaluación independiente, sin aceptar
la entrega ni demostrar mejora consistente. El agente no utilizó las capas nuevas.
Se conservan el intento interrumpido y la repetición. Véanse
[resultados y límites](../validation/2026-10-02-agent-visual-freedom-pilot.md).
3.9.7 sigue abierto.

**3.9.10.1 — Contratos previos a los ensayos, 3 de octubre de 2026:** reparación
acotada desde `4815b68`: capas accesibles en el esquema productor, estado de entrega
y errores precisos, etiquetas completas, peticiones efectivas auditables y
comprobación de cálculos ante inversión del orden físico de las filas. Se siguen
[los seis pasos de fase 1](../technical/report-quality-contracts-plan.md) y se
registran [garantías, pruebas y límites](../validation/2026-10-03-report-quality-contracts.md).
Sin llamadas reales al modelo durante la línea base de Opus. La comparación de
calidad y la aceptación 3.9.7 permanecen pendientes.

**Fase experimental 2 — Continuidad (3.9.10.2), 3 de octubre:** desde `baa0bbb`,
se permite seguir una señal en la misma tarea, conservar evidencia de varias
ejecuciones y series y cerrar con el cálculo pendiente que cambiaría la decisión.
Opción independiente y desactivada por defecto; sin reglas de negocio específicas
ni llamadas reales al modelo. [Plan](../technical/research-continuity-plan.md) y
[activación y validación](../validation/2026-10-03-research-continuity.md).
La aceptación analítica y la comparación del candidato permanecen abiertas.

**Fase experimental P3 — Presentación (3.9.10.3), 3 de octubre:** desde `b47c9da`,
redacción y revisión para lectores no técnicos, formato de cifras y nombres del
catálogo, límites en una sección y evidencia técnica bajo demanda/anexo. Opción
independiente y desactivada por defecto. [Plan](../technical/report-presentation-plan.md)
y [activación, pruebas y límites](../validation/2026-10-03-owner-presentation.md).
Sin llamadas reales al modelo; aceptación de calidad y comparación ciega pendientes.

**P3b — Corrección experimental de lectura (3.9.10.3), 4 de octubre:** sobre
`b91aefb`, misma opción P3: evidencia fuera del HTML del dueño y auditoría aparte,
etiquetas de capas comprensibles, reacciones idénticas en una frase y notas de
software fuera de límites del negocio. Instrucciones editoriales v2 para retirar
jerga y cautelas repetidas. [Validación y límites](../validation/2026-10-04-owner-presentation-p3b.md).
Sin llamadas reales al modelo. Pendiente volver a redactar sobre investigaciones
congeladas y comparar por parejas; no supone aceptar P3 ni cerrar 3.9.7.

**P1a — Panorama determinista (3.9.10.4), 4 de octubre:** desde `929d142`,
opción `sales_panorama` independiente y apagada por defecto. Calcula al importar
totales de cantidades, ventanas comparables, cambios por dimensión y huecos de
registros, con reglas y evidencia trazables. Las importaciones antiguas usan el
mismo cálculo al iniciar una revisión nueva. Solo redactor y revisor reciben el
panorama; investigación y sus prioridades guardadas permanecen intactas.
[Plan](../technical/sales-panorama-plan.md) y
[activación, pruebas y límites](../validation/2026-10-04-sales-panorama-p1a.md).
Implementado con pruebas sintéticas y modelos simulados; pendiente evaluar por
parejas sobre las nueve investigaciones. P1b y P2 quedan para fases posteriores;
no se acepta todavía la mejora de utilidad ni se cierra 3.9.7.

**Corrección de P3 — Notas del controlador, 4 de octubre:** contador de cobertura
fuera del borrador P3 y conservado en auditoría; el revisor distingue esas notas
sistemáticas de la prosa editable. Mantiene comprobaciones de cobertura sustantiva.
[Prueba del bucle y corrección](../validation/2026-10-04-controller-review-ownership.md).
15 pruebas locales con modelos simulados; evaluación real pendiente.

**P3c — Limpieza adicional de lectura, 4 de octubre:** sobre `f740c0b`, misma opción
P3: contadores de selección y notas de navegador fuera de la prosa del dueño,
auditoría conservada, cautelas generales reconocibles una vez en límites e
instrucciones editoriales v3 para jerga y razones de comparación.
[Validación y límites](../validation/2026-10-04-owner-presentation-p3c.md).
51 pruebas locales con modelos simulados; sin llamadas reales. Pendiente volver
a redactar y comparar por parejas. P2 continúa pendiente.

**Corrección de P1a — Fechas con hora, 4 de octubre:** sobre `c8a42c5`, calculador
v2 admite fechas ISO con hora, fracción y zona, y parquet con fechas tipadas.
Agrupa todas las horas por día y detalla las filas rechazadas por regla.
[Validación y política de zona](../validation/2026-10-04-sales-panorama-iso-dates.md).
21 pruebas, incluida la importación real de un CSV sintético entrecomillado;
sin llamadas reales al modelo. Pendiente repetir la medición por parejas.

**Transporte para los ensayos P1 — 5 de octubre:** resets de tokens completos,
reintentos acotados tras rechazo, deadline cancelable y admisión local por TPM
compartida entre roles/procesos. [Plan de los tres pasos](../technical/panorama-contracts-next-plan.md)
y [garantías y límites](../validation/2026-10-05-model-transport-budget.md).
Sin llamadas reales al proveedor; medición de escala pendiente.

**P1a v2 — 5 de octubre:** apertura Panorama determinista en web/HTML/PDF,
catálogos congelados, disposición obligatoria de huecos y comparación estructurada
de prioridades con evidencia del panorama. Contexto compacto al principio de la
petición efectiva. [Validación y alcance del contrato](../validation/2026-10-05-panorama-contract-v2.md).
Sin llamadas reales; pendiente medición por parejas. P1b permanece separado.

**Corrección P1a v2 — Guardián de revisión, 5 de octubre:** opción independiente,
por defecto apagada, para cerrar repeticiones editoriales con entrega limitada y
resolución del controlador auditada. Integridad permanece bloqueante. Capacidades
del esquema visibles y un foco declarado por hallazgo. 29 pruebas locales con
modelos simulados; [garantías y alcance](../technical/review-loop-panorama-corrections.md).
Pendiente medir utilidad; no cierra 3.9 ni incorpora P1b.

**Correcciones de P1a v2 — 5 de octubre:** misma opción `sales_panorama`, materialidad
explícita y cinco alertas como máximo; descartes con fuentes verificables y enlaces
al foco existente; comparación y prioridad estructuradas obligatorias; explicación
visible de ventanas alternativas. 97 pruebas offline, incluidas importación real,
esquemas con 1.200 métricas, exportación y reanudación tras caída. Véanse
[garantías, límites y activación](../technical/review-loop-panorama-corrections.md).
Pendiente nueva medición por parejas; P1b se mantiene fuera de esta cadena.

**Contexto de revisión — 5 de octubre:** opción de presupuesto local en tokens para
la petición completa, vista compacta, instrucciones específicas de revisión y lectura
paginada de originales auditada. 25 pruebas offline; [plan y límites](../technical/review-context-cache-plan.md).
Pendiente medición de calidad/coste real; no cierra 3.9.

**Prefijo de revisión — 5 de octubre:** opción independiente de esquema/prefijo
estable, referencias validadas localmente y adaptación de disposiciones sin perder
el contrato persistido. Telemetría y comparador de caché preparados; HTTP simulado
y persistencia local verificados. Véase el [plan](../technical/review-context-cache-plan.md).
Ahorro y calidad pendientes del ensayo real; no se han llamado modelos.

**Obligaciones del panorama — 5 de octubre:** inventario exacto de huecos materiales
y guardián independiente contra demandas estructuradas que el contrato prohíbe.
Conserva objeciones y prueba del controlador en auditoría, con integridad real aún
bloqueante. 47 pruebas offline de esta entrega y regresiones; [alcance y activación](../technical/review-context-cache-plan.md).

**Corrección de series compactadas — 5 de octubre:** metadatos completos explícitos,
muestra identificada y gráficos por referencia a originales. 14 pruebas offline,
incluido payload HTTP y superposición completa; [detalle](../technical/review-context-cache-plan.md).

**Caché del piloto — 5 de octubre:** clave por revisión y evidencia antes del sufijo
variable, con hashes y tamaños auditados. 14 pruebas offline; ahorro pendiente de
lote, [detalle](../technical/review-context-cache-plan.md).

**Lint estricto y citas — 5 de octubre:** citas por ID de mensaje y fragmento literal
con espacios normalizados; textos del dueño fuera de enums. Lint antes de HTTP
sobre todos los productores y matriz de opciones/contextos grandes. 112 pruebas
aprobadas de esta cadena, sin modelos reales; [detalle](../technical/review-context-cache-plan.md).

**Contratos congelados de revisión — 5 de octubre:** enums de cobertura/panorama
restaurados sin variar al añadir cálculos; inventarios visibles completos. 18 pruebas
offline aprobadas. [Registro](../technical/review-context-cache-plan.md).

**Correcciones exactas — 5 de octubre:** errores de cobertura/prioridad con faltantes,
claves inválidas y listas completas; sin truncado de estos diagnósticos. 13 pruebas
locales de contratos/correcciones; [registro](../technical/review-context-cache-plan.md).

**Presupuesto revisado — 5 de octubre:** objetivo de 110.000, estimación sin doble
escape, tercer nivel de compactación y ampliación auditada dentro del techo TPM.
14 pruebas locales aprobadas; [alcance](../technical/review-context-cache-plan.md).
