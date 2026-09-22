# Decision Room: plan de implementación por entregas

**Fecha:** 18 de septiembre de 2026.  
**Estado:** casos de referencia, ingesta CSV y ejecución aislada de Python implementados y comprobados el 21 de septiembre de 2026. PostgreSQL conserva metadatos y evidencia; los archivos son privados. Se probaron las 48 tablas de WWI juntas. El paso 1.4 tiene implementación experimental con LangGraph, preguntas y recuperación; falta superar la evaluación semántica del modelo. El paso 1.5 conecta Python generado, evidencia y recuperación; sus resultados siguen siendo candidatos. El paso 1.6 añade conversación persistente con revisor, controles e informe HTML privado. La matriz real del paso 1.7 se ha ejecutado y ha encontrado fallos semánticos y de continuidad; la entrega 1 todavía no está aceptada.  
**Propósito:** conservar la secuencia de trabajo, el motivo de cada paso y qué debemos poder comprobar antes de darlo por terminado.

## 1. Relación con el MVP

El [documento del MVP](<Decision Room - MVP.md>) define el alcance y las decisiones de los siete bloques. Este documento define el orden para construirlo. Los bloques funcionales no son entregas consecutivas de software: cada entrega combina partes de varios bloques.

En este plan, **entrega 1** significa el primer recorrido interno completo; no equivale al MVP completo descrito en el otro documento. Las cinco entregas y la preparación conducen al MVP probado en un piloto privado.

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

## 6. Entrega 3: adaptación y ampliación de cobertura

**Construir por escenarios completos:**

- Excel `.xlsx`, varias hojas y selección de tablas.
- Detalle de tickets, descuentos y devoluciones.
- Archivos complementarios durante las aclaraciones.
- Relaciones comprobables entre tablas y fuentes agregadas/detalladas de la misma actividad.
- Corrección de interpretaciones, invalidación y recálculo de resultados dependientes.
- Investigaciones adicionales cuando los datos más ricos las permiten.

**Cierre:** superar la matriz del MVP: continuar sin datos opcionales, profundizar al recibirlos, evitar duplicaciones, revisar conclusiones al cambiar premisas y entregar informes breves cuando corresponda. Cada capacidad se comprueba desde la interpretación hasta su explicación en el informe.

**Por qué aquí:** ampliar una base completa permite localizar si un problema viene de la capacidad nueva o del recorrido básico. CSV primero es una secuencia de implementación, no un recorte del soporte Excel acordado para el MVP.

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
- Revisor, comprobaciones y evidencia forman parte del primer recorrido completo.
- Las pruebas acompañan cada paso; el control de calidad no se aplaza a la entrega 4.
- El almacenamiento registra procedencia y versiones; no obliga a un esquema universal de ventas.
- ML predictivo, chat libre posterior, PDF, dashboard avanzado, conectores y automatización periódica siguen fuera del MVP.
- Modelos, proveedores, entorno de ejecución, framework web, componentes reutilizables y límites numéricos se concretan cuando desbloquean la entrega correspondiente. No se fijan plazos sin estimar el trabajo y medir los primeros pasos.

## 10. Punto de inicio

**Primer avance del 21 de septiembre de 2026:** los [tres casos de referencia](../../data/reference-cases/README.md) tienen CSV, contexto, variantes de columnas y respuestas numéricas separadas del material del agente. Las referencias se contrastaron con los datos originales mediante un cálculo independiente. Esto validó los casos antes de implementar el agente; sus capacidades y evaluaciones posteriores se registran a continuación. La revisión independiente de preguntas, conclusiones y utilidad sigue siendo necesaria.

**Avance de implementación del 21 de septiembre de 2026:** se han materializado las primeras estructuras del paso 1.1 —negocio, análisis, fuente y tabla preparada— y la ingesta y persistencia del paso 1.2. PostgreSQL local conserva metadatos; los originales y Parquet se guardan por separado. El lote WWI conserva 48 tablas y 4.713.833 filas. Se comprobaron todos los valores, reenvío sin duplicación del lote y recuperación tras reiniciar PostgreSQL. Las estructuras de preguntas, investigaciones, ejecuciones y resultados se incorporarán con sus capacidades. Ver [implementación](../technical/ingestion.md) y [resultados de la prueba](../validation/2026-09-21-ingestion-check.md).

**Avance del paso 1.3, 21 de septiembre de 2026:** ejecutor Docker dentro de Colima local, bibliotecas versionadas, entradas de solo lectura, sin red ni credenciales y límites de recursos. Nuevas estructuras de ejecuciones, resultados candidatos y artefactos con código, hashes y procedencia. Cálculo de referencia y cálculo sobre las 48 tablas WWI contrastados; recuperación y fallos deliberados comprobados. Ver [guía](../technical/sandbox.md), [plan técnico](../technical/sandbox-plan.md) e [informe](../validation/2026-09-21-sandbox-check.md).

**Avance del paso 1.4, 21 de septiembre de 2026:** agente principal con LangGraph, catálogo y perfiles, planes provisionales, preguntas materiales, respuestas desde terminal y checkpoints PostgreSQL. La recuperación se comprobó con procesos distintos y un modelo simulado. La prueba real con Qwen en LM Studio detectó una definición monetaria inventada, por lo que este paso no se considera aceptado todavía. Ver [guía y mapa de archivos](../technical/agent.md), [plan técnico](../technical/agent-plan.md) y [resultados con sus límites](../validation/2026-09-21-agent-check.md).

**Avance del paso 1.5, 21 de septiembre de 2026:** por decisión del usuario se avanza con Python manteniendo abierto [DR-001](../validation/known-agent-errors.md). El principal elige investigaciones, genera y ejecuta código, recibe errores, registra candidatos y conserva evidencia. Cambiar el contexto invalida resultados anteriores y permite recalcular. Ver [guía](../technical/research.md), [plan técnico](../technical/research-plan.md) y [validación](../validation/2026-09-21-research-check.md).

**Avance del paso 1.6, 21 de septiembre de 2026:** analista y revisor intercambian informes, reparos y justificaciones con contexto persistente. Ambos pueden ejecutar Python; el revisor controla la aprobación. Las preguntas al propietario pausan el grafo, y sus respuestas invalidan evidencia anterior. La aplicación comprueba referencias y relaciones numéricas y genera HTML escapado con evidencia y conversación. La prueba adversarial corrigió DR-001, pero otra prueba detectó DR-002: aprobación incorrecta del revisor, bloqueada por un control independiente. La implementación está disponible; la calidad del revisor no se da por aceptada. Ver [guía](../technical/review.md), [plan técnico](../technical/review-plan.md) y [validación con límites](../validation/2026-09-21-review-check.md).

**Ampliación del paso 1.6:** separar el HTML interno del informe del cliente. Incorporar contexto de negocio, cobertura, interpretaciones, siguientes comprobaciones y gráficos de barras/líneas/tablas con valores provenientes de métricas guardadas. El revisor examina ese contenido antes de aprobarlo. Ver [contrato y presentación](../technical/client-report.md). La entrega 2 integra este informe en la aplicación web; no aplaza su contenido.

**Trabajo realizado, 22 de septiembre de 2026:** construida y ejecutada la evaluación del paso 1.7. Se implementaron el ejecutor reproducible, las referencias independientes y la rúbrica que distingue aprobación del modelo de aceptación. La matriz real aceptó 11 de 24 casos; la serie posterior con correcciones del controlador aceptó 6 de 9. Las tres correcciones del propietario invalidaron la aprobación anterior y recalcularon, pero solo uno de los tres informes nuevos pasó. Las 101 pruebas automatizadas pasan. Se conservan fallos, versiones, tiempos y evidencia. Ver [método y comandos](../technical/evaluation-plan.md) y [resultados de las pruebas](../validation/2026-09-21-evaluation-check.md). Solo se ha evaluado Qwen local; no se atribuyen resultados a otro modelo sin probarlo.

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
