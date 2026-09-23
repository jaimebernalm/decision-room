# Decision Room: plan de implementación por entregas

**Fecha de actualización:** 23 de septiembre de 2026.  
**Estado vigente:** entrega 2 implementada y comprobada como recorrido web local. La ronda de evaluación previa a ampliar cobertura terminó el 22 de septiembre, con correcciones y límites documentados; no equivale a aceptación general del MVP. La entrega 2.5 tiene los pasos 2.5.1–2.5.3 implementados y comprobados; los pasos 2.5.4–2.5.7 de memoria compartida y experiencia cotidiana siguen pendientes y preceden a la ampliación de cobertura de la entrega 3. Los resultados históricos de cada paso se conservan en la sección 10.  
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

**Estado, 23 de septiembre de 2026:** pasos 2.5.1–2.5.3 implementados y comprobados; resto de implementación y evaluación integrada pendientes. El [diagnóstico del código y diseño técnico](../technical/business-memory-plan.md) detalla estructuras, migración, mantenimiento de memoria, contexto del agente, UX y escenarios de aceptación.

**Guía para implementarlo poco a poco:** el [desglose de los siete pasos](../technical/business-memory-implementation.md) define cuatro incrementos por paso, dependencias, zonas de código, contratos de salida, demostraciones y pruebas. Ejecutar un paso por vez y registrar su validación y commit al cerrarlo. Los doce incrementos de 2.5.1–2.5.3 están completados; los restantes están pendientes; el paso 2.5.3 está probado con sesiones actuales y el chat se introduce después, en 2.5.4, sin dependencias circulares.

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

**Construir:** selección acotada de memoria, mensajes, fuentes y resultados pertinentes por negocio, pregunta y periodo. Registrar el manifiesto de versiones utilizado por planificador, analista y revisor. Integrar las versiones de memoria en la comprobación de vigencia y extender dependencias e invalidación entre sesiones, respuestas e informes. Conservar históricos sin reescribirlos y distinguir cambio futuro, dato nuevo y corrección de un error pasado. Revalidar las dependencias antes de publicar, también si el trabajo se interrumpió.

**Comprobar:** dos sesiones reutilizan contexto sin repetir preguntas resueltas; una corrección material afecta a todas las dependencias conocidas, incluso en otra conversación; un cambio futuro no invalida un periodo previo sin motivo; una edición irrelevante no recalcula todo; los resultados retirados no vuelven a usarse como evidencia vigente. Probar selección con historial largo, datos de otro negocio y contenido adversarial recuperado. Si no se puede acotar el impacto, ampliar la revisión de forma explícita.

### 2.5.4. Conversaciones del cliente conectadas al análisis

**Construir:** conversaciones y mensajes persistentes, turnos recuperables y referencia al negocio, fuentes, memoria e investigaciones. Permitir explicar evidencia existente, aportar contexto, explorar una decisión o iniciar un cálculo; no exigir un informe ni un CSV nuevo por mensaje. Integrar cambios de memoria desde el chat con aviso/corrección para declaraciones claras y aclaración cuando haya ambigüedad material. Crear un informe independiente cuando se solicite, reutilizando evidencia vigente y revisando contenido nuevo. Mantener la conversación interna de revisión separada del chat del cliente.

**Comprobar:** una pregunta breve obtiene respuesta con fuente y periodo; una pregunta nueva ejecuta y verifica el cálculo; una pregunta sin datos suficientes explica el límite; una declaración se utiliza en otro chat y al reabrir uno antiguo. Recargar/reintentar no duplica mensajes, hechos ni trabajos. Las respuestas nuevas no eluden las comprobaciones por presentarse en chat en vez de en un informe.

### 2.5.5. «Mi negocio» y actualización de datos

**Construir:** ficha progresiva y editable con información, prioridades, definiciones, fuentes/periodos y cambios; mostrar procedencia, vigencia y propuestas/conflictos donde ayuden. Las ediciones usan el mismo servicio de memoria del chat. Reutilizar archivos ya aceptados; permitir aportar otro CSV y seleccionar su uso sin iniciar otro negocio. Mantener conjuntos/versiones explícitos, detectar reenvíos exactos y aclarar sustitución o solapamiento; no implementar fusión universal de tablas.

**Comprobar:** editar una definición tiene el mismo efecto desde la ficha que desde una aclaración; una corrección histórica retira los resultados afectados; el usuario encuentra el origen y alcance de lo guardado; un archivo nuevo no se agrega dos veces ni hace parecer actualizado un informe anterior. Sin datos suficientes se conserva el trabajo y se explica el siguiente paso.

### 2.5.6. Inicio del negocio, informes y navegación cotidiana

**Construir:** separar onboarding de visitas posteriores. Barra lateral con Inicio, Informes, Mi negocio, Nueva conversación y chats recientes. Inicio muestra un resumen, pocos hallazgos y gráficos respaldados, con periodo visible, detalle/evidencia y selección de revisión. Añadir prompt inferior y preguntas sugeridas pertinentes; enviar abre un chat y «Preguntar sobre esto» conserva la referencia al hallazgo. Biblioteca de informes con estados y vínculo a conversaciones; navegación adaptable a móvil y teclado.

**Comprobar:** el primer acceso guía el onboarding y los siguientes abren Inicio; escribir desde Inicio crea un chat durable; una sugerencia es abordable con las capacidades/datos presentes; no se mezclan revisiones incompatibles. Verificar estados sin datos, análisis en curso, datos nuevos sin informe nuevo, informe retirado y fallo recuperable. Comprobar visualmente escritorio/móvil, foco, teclado y que el prompt no oculte contenido.

### 2.5.7. Evaluación integrada y cierre

**Ejecutar:** matriz de memoria y conversación con referencias independientes, pruebas de persistencia, aislamiento, concurrencia y recuperación, conversaciones con el modelo real y recorrido visual. Incluir regresión del flujo de la entrega 2 y medir repetición de preguntas, propagación de correcciones, exactitud, selección de contexto, latencia y consumo. Registrar resultados, versiones y límites; corregir fallos materiales antes del cierre.

**Cierre:** una persona completa el onboarding una vez, pregunta desde Inicio, recibe evidencia, aporta información que otro chat reutiliza, la corrige desde «Mi negocio», ve revisados los resultados afectados, guarda un informe y recupera todo tras reiniciar. No se mezclan negocios, fuentes incompatibles ni versiones de contexto, y las respuestas no presentan hipótesis como hechos. Un dashboard dibujado o un único chat funcionando no cierran la entrega.

**Orden de trabajo:** identidad → memoria → contexto y dependencias → conversación → ficha/datos → Inicio y navegación → evaluación integrada. Cada paso se comprueba, revisa y guarda en un commit local según `AGENTS.md`; no se marca completo por tener únicamente su diseño.

**Fuera de 2.5:** PDF, Excel y combinación general de tablas, búsqueda web de contexto, predicciones, editor libre de dashboards, conectores, automatización, equipos y despliegue comercial. Continúan en su entrega o roadmap correspondiente. La memoria entre conversaciones y el Inicio interactivo acotado sí forman parte de 2.5.

## 6. Entrega 3: adaptación y ampliación de cobertura

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
