# Decision Room: MVP y primera entrega

**Fecha de actualización:** 18 de septiembre de 2026.  
**Avance del 21 de septiembre de 2026:** implementadas la ingesta CSV persistente, Python aislado, agente con recuperación, investigación, diálogo de revisión e informe HTML. El informe del cliente se separa del registro interno e incorpora gráficos con evidencia y explicaciones de negocio. Las pruebas del controlador pasan; la calidad general de los modelos y el recorrido web siguen pendientes. El detalle vigente está en el [plan de implementación](<Decision Room - Plan de implementacion.md>) y la [guía del informe](../technical/client-report.md). Las notas de aprobación de bloques conservan su contexto de diseño del día 18.  
**Estado:** alcance funcional y arquitectura acordados; recorrido interno implementado hasta el paso 1.6, con evaluación semántica todavía abierta. La evaluación del paso 1.7 ha comprobado variedad y repetibilidad y ha encontrado fallos que impiden aceptar todavía la entrega 1. La aplicación web corresponde a la entrega 2. PostgreSQL sigue siendo la opción inicial; el ejecutor usa Docker dentro de Colima local y conserva evidencia privada.  
**Propósito:** completar y comprobar un análisis que se adapta a los datos de cada tienda, desde su recepción hasta un informe útil y verificable.

## 1. Qué consideramos el MVP

> El dueño describe brevemente su tienda y aporta los Excel/CSV que tiene. El sistema evalúa qué permiten analizar, prepara un plan, pregunta por aclaraciones o información adicional útil y continúa con lo disponible. Entrega un informe en una página sencilla, adaptado a esa tienda y con resultados comprobables.

**Principio acordado: autonomía para decidir qué investigar, con obligación de que los resultados se puedan comprobar.**

La guía de análisis es un punto de partida. No existe una lista cerrada de seis análisis ni una estructura universal de columnas obligatorias. El sistema puede reducir, ampliar o reformular su plan según los datos, el contexto y las herramientas disponibles. Cada análisis concreto sí tiene requisitos de información y verificación.

Este es el **MVP de la primera entrega**. Permite probar el sistema y la utilidad del primer resultado con un alcance pequeño. No implica que la demanda comercial o la disposición a pagar estén validadas.

Los documentos anteriores describen un producto más amplio, con dashboard interactivo, PDF, chat posterior y seguimiento. Esas capacidades siguen en la visión del producto, pero **no son requisitos de esta entrega**. Si una referencia anterior al «MVP» incluye esas funciones, este documento prevalece para el alcance de implementación inmediato.

Documentos relacionados:

- [Producto y experiencia de uso](<Decision Room - Definicion del producto.md>).
- [Servicios y diferenciación](<Decision Room - Servicios y diferenciacion.md>).
- [Investigación de segmentos y datos](<../research/Decision Room - Investigacion de segmentos y datos.md>).
- [Plan de implementación por entregas](<Decision Room - Plan de implementacion.md>).

## 2. Para quién

Dueño o encargado de un pequeño comercio que revende productos no perecederos: por ejemplo, una papelería, bazar, tienda de regalos, artículos del hogar o accesorios.

El caso inicial será una tienda con una ubicación y operativa sencilla, que ya dispone de Excel o CSV, aunque solo contengan totales diarios o semanales. El detalle por ticket o artículo permite profundizar, pero no es un requisito general de entrada. No se requiere información personal de compradores para el análisis inicial.

Los límites de tamaño, número de archivos y tablas se fijarán en la planificación técnica. Se contempla recibir información complementaria durante las aclaraciones y reevaluar el plan. Relacionar tablas exige correspondencias comprobables y evitar duplicaciones; la autonomía no implica importación o combinación universal.

## 3. Guía de análisis y adaptación

El sistema intenta responder preguntas base, sin forzar respuestas cuando no hay evidencia:

1. **¿Qué muestran los datos sobre la actividad del negocio?**
2. **¿Qué cambió y qué componentes explican la variación observada?**
3. **¿Qué merece revisar y con qué evidencia?**

El sistema clasifica cada línea de investigación como posible ahora, pendiente de aclaración, mejorable con datos adicionales, no sustentable o fuera de las capacidades disponibles. Puede proponer análisis adicionales pertinentes y ejecutarlos con herramientas que permitan verificar el resultado.

| Información disponible | Ejemplos de profundidad posible | Límite que se conserva |
|---|---|---|
| Totales diarios o semanales | Evolución y comparaciones de periodos compatibles | No inventar productos, tickets ni compradores |
| Ventas por producto sin ticket | Composición y contribuciones por artículo | No calcular cesta ni ticket medio |
| Detalle de tickets y artículos | Compras, importes medios, composición y contribuciones | Tickets no equivalen a personas |
| Descuentos o devoluciones identificables | Concentraciones, variaciones y efecto contable en ventas | No duplicar ajustes ni deducir causas sin evidencia |
| Costes o existencias pertinentes | Exploraciones descriptivas adicionales si las herramientas y comprobaciones lo permiten | No confundir margen bruto con beneficio ni stock actual con histórico |

Esta tabla ilustra posibilidades, no impone un informe idéntico. Sin periodos comparables se entrega una lectura del periodo disponible. Si no hay ninguna base interpretable, se explica el bloqueo concreto.

El informe no afirma causas que los registros no demuestren. Una caída de ventas puede señalar algo que revisar sin probar una caída de demanda. Menos tickets no significa necesariamente menos clientes.

## 4. Recorrido completo

**Descripción y archivos → evaluación → plan provisional → aclaraciones/datos opcionales → ejecución y verificación → informe.**

Es un recorrido adaptable: una respuesta, un nuevo archivo o un hallazgo pueden hacer volver a evaluar y ajustar el plan. El sistema no repite preguntas resueltas ni investiga indefinidamente.

### 4.1. Descripción breve

El usuario explica qué vende y de dónde sale el archivo. Ejemplo ilustrativo:

> Tengo una papelería y también vendo regalos. Este archivo lo exporto de nuestro programa de caja.

Esta información orienta la interpretación. No obliga a completar un perfil exhaustivo ni a responder preguntas generales sobre todo su sector.

### 4.2. Recepción e inspección del archivo

El sistema comprueba qué puede leer e identifica:

- Hojas y tabla seleccionada, columnas y tipos de datos.
- Qué representa probablemente cada fila.
- Periodo cubierto, nivel de detalle e identificadores existentes, si los hay.
- Importes, cantidades, descuentos y devoluciones reconocibles.
- Valores ausentes, fechas ambiguas, subtotales y posibles duplicados.

Se muestra una interpretación breve y corregible. Los valores negativos o registros repetidos no se eliminan automáticamente: pueden tener un significado válido.

El sistema conserva un mapa de lo disponible, lo dudoso y lo ausente. No descarta una tabla aprovechable por no poder convertirla en líneas de tickets. Un archivo agregado y uno detallado pueden describir la misma actividad: no se suman como si fueran ventas distintas.

### 4.3. Plan provisional y preguntas

El sistema prepara un plan resumido: qué puede estudiar, qué necesita aclarar, qué dato adicional aportaría valor y qué no puede sostener. Las preguntas se derivan de ese plan. Ejemplos:

- «¿Cada fila corresponde a un artículo del ticket o a una compra completa?»
- «¿Este importe incluye impuestos?»
- «¿El descuento ya está aplicado en este importe?»
- «¿Las devoluciones aparecen con cantidades negativas?»
- «Faltan registros de estos días: ¿hubo cierres o falta parte del archivo?»
- «Con los totales puedo analizar la evolución. Si tienes el detalle por artículo, podríamos ver qué productos explican la caída. ¿Lo tienes disponible?»

No se fija una cantidad obligatoria de preguntas. Se agrupan en tandas pequeñas, se evitan las repetidas y se permite corregir una interpretación.

| Tipo de duda | Tratamiento |
|---|---|
| Cambia el significado de un cálculo | Resolverla antes de publicar ese cálculo; si no se puede, omitirlo o limitarlo |
| Ayuda a contextualizar | Permitir continuar y señalar la incertidumbre relevante |
| Dato adicional para un análisis disponible | Explicar qué permitiría averiguar; aceptar que no exista o no se quiera aportar y adaptar el plan |
| Serviría para una ampliación futura | No bloquear el informe ni pedir datos para funciones inexistentes |

«No lo sé», «No lo tengo» y «Prefiero continuar» son respuestas válidas. Se conserva esa respuesta para no insistir sin una razón nueva. Si queda una base útil, se genera un informe adecuado a ella, sin tratar un archivo básico como un error. Si no puede sostenerse ningún resultado, se explica qué impide avanzar.

### 4.4. Ejecución, verificación y ajuste del plan

El sistema elige qué análisis realizar, con qué herramientas y qué líneas abandonar o ampliar. Los cálculos se ejecutan de forma reproducible con definiciones explícitas y aclaradas cuando sea necesario. La redacción se apoya en resultados ejecutados y comprobados.

La base de análisis orienta la exploración hacia:

- Ventas registradas por periodo, con definición explícita de impuestos, descuentos, anulaciones y devoluciones.
- Comparaciones entre periodos compatibles y contribuciones de productos o categorías.
- Número de tickets e importe medio cuando los identificadores y la definición lo permitan.
- Descuentos y devoluciones cuando sean distinguibles sin duplicación.
- Limitaciones o incidencias de datos que afecten al resultado.

Estos ejemplos no cierran la exploración. Un análisis adicional necesita una pregunta pertinente, datos suficientes, definiciones y operaciones trazables, y comprobaciones antes de publicarse. El bloque 4 acuerda herramientas reutilizables, consultas SQL y Python generado por el agente desde la primera entrega, con ejecución aislada y validación externa.

La base de herramientas tendrá reglas verificadas; una extensión debe superar el mismo estándar. No se inventan costes, clientes, stock ni días con cero ventas. No basta con que un segundo agente esté de acuerdo: la verificación debe contrastar cálculos, fuentes, cobertura y supuestos.

Si una comprobación falla, el sistema puede corregir y reintentar dentro de límites definidos, preguntar si hace falta o retirar el resultado afectado. Entrega el resto si conserva utilidad. Habrá límites de tiempo, coste e iteraciones y un criterio de parada: cobertura útil de las preguntas abordables y ausencia de otra exploración prioritaria dentro del presupuesto. Sus valores se decidirán técnicamente.

### 4.5. Informe en una página sencilla

La página contiene:

1. Negocio, periodo, fecha de generación y cobertura relevante.
2. Resumen breve de lo observado.
3. Pocos hallazgos priorizados, sin una cantidad obligatoria.
4. Cifras y gráficos sencillos cuando ayuden a entenderlos.
5. Evidencia accesible: cálculo, fuente y registros pertinentes.
6. Limitaciones y siguientes comprobaciones propuestas.

Se explica brevemente qué se pudo investigar, qué quedó sin resolver y qué información opcional permitiría ampliar el análisis. No se obliga a llenar secciones sin evidencia ni se muestra el razonamiento interno del modelo.

El usuario puede consultar el sustento de un hallazgo sin iniciar un chat. No hace falta un editor de gráficos, paneles configurables ni una navegación compleja.

Si no hay cambios relevantes, el informe puede ser breve. Si falta información, no se fabrica contenido para aparentar profundidad.

## 5. Qué información debemos conservar

Esta sección define necesidades lógicas. La opción inicial de persistencia y sus alternativas se concretan en la sección 7.5; los proveedores siguen pendientes.

| Información | Qué debe permitir |
|---|---|
| Archivo original y procedencia | Volver a la fuente y localizar de dónde salió un dato |
| Datos preparados para analizar | Calcular sin reinterpretar manualmente el archivo en cada paso y conservar relación con el original |
| Interpretación del archivo | Saber qué representa cada fila y columna, qué reglas se confirmaron y qué sigue siendo una hipótesis |
| Descripción y respuestas del usuario | Recuperar el texto original y su significado estructurado, corregible y vinculado al negocio/análisis correspondiente |
| Disponibilidad de información | Distinguir datos ausentes, ambiguos, no aportados o incompatibles y evitar peticiones repetidas |
| Plan de análisis y sus revisiones | Conservar objetivos, requisitos, estados y motivos operativos de cambios sin registrar razonamiento interno |
| Ejecución y resultados | Saber qué datos, reglas, filtros y cálculos produjeron cada cifra |
| Comprobaciones y límites de ejecución | Saber qué verificaciones pasaron, qué resultados se retiraron y por qué terminó el análisis |
| Informe generado | Recuperar la revisión junto con su periodo, fuentes, supuestos y limitaciones |

Se distingue lo inferido por el sistema de lo confirmado por el usuario. Cuando una aclaración tiene aplicación temporal, se conserva ese alcance.

Las correcciones pueden dar lugar a un análisis nuevo sin reescribir silenciosamente el anterior. La persistencia permite recuperar trabajo y evidencia; no obliga a construir todavía una interfaz completa de historial ni importaciones incrementales.

## 6. Qué queda fuera de esta entrega

- Predicciones y machine learning predictivo.
- Gestión integral de margen/inventario, beneficio neto y recomendaciones de compra. Un análisis histórico o descriptivo adicional con costes o existencias puede entrar si hay datos y herramientas verificables; no es un módulo obligatorio para terminar esta entrega ni una capacidad prometida universalmente.
- Chat libre después del informe. Las preguntas guiadas para interpretar el archivo sí forman parte del MVP.
- Exportación PDF: la primera salida es la página sencilla.
- Dashboard avanzado, filtros abiertos y paneles personalizables.
- Guardar decisiones y darles seguimiento entre periodos.
- Conectores, sincronización automática e informes programados.
- Importación universal, OCR de documentos o combinación general de múltiples archivos.
- Cambios autónomos en precios, compras o sistemas externos.
- Ontología empresarial completa o interacción con agentes de otras organizaciones.

El registro de cuentas, los controles de acceso y el modo de despliegue se concretarán según cómo se pruebe la entrega. No se presupone una plataforma comercial completa para la primera prueba, ni acceso sin aislamiento a datos de distintas tiendas.

## 7. Cuándo consideramos terminada la primera entrega

| Comprobación | Resultado esperado |
|---|---|
| Se aporta una tabla interpretable dentro de los límites admitidos | El sistema adapta el plan y llega a un informe sin intervención manual del desarrollador en cada paso |
| Solo hay totales diarios | Entrega lo que puede respaldar; no exige tickets o productos para todo análisis |
| Hay datos detallados y útiles | Profundiza donde aporta valor sin quedarse obligatoriamente en la guía base |
| Falta un dato que permitiría profundizar | Lo pide explicando su utilidad; si no se aporta, continúa con el plan ajustado |
| Hay una ambigüedad que afecta a ventas | Pregunta o limita el cálculo; no adopta una interpretación silenciosa |
| El usuario corrige una interpretación | Los cálculos posteriores utilizan la corrección y su procedencia se conserva |
| Falta un dato no imprescindible | Se entrega la parte respaldada y se explica el límite |
| Se comprueba una cifra | Coincide con el cálculo de referencia y se localiza su evidencia |
| Un ticket tiene varias líneas | No se cuentan como varias compras |
| El archivo contiene devoluciones, descuentos o posibles duplicados | Se interpretan con reglas explícitas y no se suman o eliminan indiscriminadamente |
| Los periodos no son comparables | Se explica la cobertura y no se presenta una conclusión engañosa |
| Se pide una conclusión imposible con esos datos | El sistema reconoce el límite y no inventa información |
| Falla un paso | Se muestra un siguiente paso y se conserva el trabajo aceptado que corresponda |
| Se recupera el informe | Conserva el periodo, datos y supuestos de su revisión |
| Se plantea un análisis adicional | Quedan documentados objetivo, operaciones, evidencia y comprobaciones; no se publica por parecer plausible |
| Un nuevo archivo o respuesta cambia el análisis | Revisa el plan y los resultados afectados sin sumar dos veces la misma actividad |
| Se agota el presupuesto de investigación | Entrega los resultados verificados disponibles y sus límites, sin bucles ni falsa apariencia de completitud |
| Los datos o el contexto se contradicen | Identifica la discrepancia, pide aclaración si afecta al resultado y no inventa una reconciliación |
| No hay cambios relevantes | Entrega un informe breve y fiel sin fabricar alertas |

Se verificará con una matriz de escenarios: datos agregados, detalle sin tickets, tickets completos, información enriquecida, ambigüedades y rechazo a aportar más datos. Cada caso tendrá conclusiones admisibles, afirmaciones prohibidas y cálculos de referencia cuando proceda; no un único texto o camino obligatorio. Se incluirán formatos desconocidos y errores deliberados. Se evaluará adaptación, calidad de las preguntas, utilidad, exactitud, trazabilidad y consumo de recursos. Las pruebas no sustituyen observar si un propietario entiende el informe y encuentra algo útil.

La primera entrega no se da por terminada únicamente porque funcione el onboarding: debe completar el recorrido hasta el informe comprobable.

### 7.1. Decisiones acordadas del bloque 1: comportamiento y escenarios

Estas decisiones han sido aceptadas por el usuario. Definen el comportamiento esperado; no fijan aún su implementación ni prueban que el sistema ya lo cumpla.

1. **Misión con libertad de investigación.** Encontrar qué merece atención en la tienda utilizando la información disponible y explicar los resultados con evidencia. La guía orienta, pero se pueden omitir preguntas irrelevantes y añadir otras pertinentes. No se exige descubrir algo sorprendente.
2. **Evaluación por investigación.** Determinar significado, cobertura, nivel de detalle, relaciones comprobables y dudas. Una tabla puede servir para una pregunta y no para otra; no se rechaza globalmente por no cumplir requisitos ajenos al análisis posible.
3. **Plan resumido y revisable.** Cada investigación conserva pregunta, utilidad, datos necesarios, situación y siguiente paso. Se puede añadir, reformular o abandonar una línea. El usuario no debe aprobar cada paso ni supervisar técnicamente al agente; se le explica el plan cuando ayude a entender una pregunta o limitación.
4. **Preguntas según su efecto.** Resolver las dudas que cambian un cálculo antes de publicarlo; pedir información para profundizar de forma opcional y explicando el beneficio; no preguntar por datos que no cambian ninguna investigación útil. Usar tandas pequeñas, conservar respuestas y continuar cuando el cliente no aporte datos opcionales.
5. **Análisis nuevos con comprobaciones obligatorias.** Documentar qué pregunta responden, por qué importa, qué datos los sostienen, qué operaciones se ejecutaron, qué comprobaciones pasaron y qué límites tienen. El acuerdo de otro agente no sustituye comprobar números, relaciones y comparaciones. La autonomía permanece dentro del análisis histórico del MVP.
6. **Finalización explícita.** Terminar cuando las preguntas prioritarias abordables estén investigadas, los resultados seleccionados comprobados, las dudas identificadas y no haya otra investigación con suficiente valor dentro del presupuesto. Al alcanzar un límite de tiempo, coste o reintentos, entregar lo verificado y explicar lo pendiente. Los valores de esos límites siguen por definir y probar.
7. **Evaluación por resultados defendibles.** Medir adaptación, utilidad, calidad de las preguntas, exactitud, trazabilidad y recursos consumidos. Los cálculos conocidos deben coincidir con sus referencias y las afirmaciones con la evidencia. Dos planes o textos distintos pueden ser válidos; no se exige una secuencia única de agentes.

Los escenarios aceptados para preparar la evaluación son: totales diarios; productos sin tickets; tickets completos; importes ambiguos; negativa a aportar información; llegada de archivos adicionales; datos más ricos de lo previsto; contradicciones o insuficiencia; ausencia de cambios relevantes; y fallos de herramientas o agotamiento del presupuesto. Sus expectativas están recogidas en la tabla de esta sección y en las reglas anteriores.

**Pendiente de ejecución:** preparar los archivos concretos, los resultados de referencia, los criterios de medición y ejecutar las pruebas cuando exista el sistema. La aprobación del comportamiento no equivale a haber superado esas pruebas.

### 7.2. Decisiones acordadas del bloque 2: evaluación de datos y planificación

Estas decisiones han sido aceptadas por el usuario, igual que las del bloque 1. Este bloque define el mecanismo lógico para preparar y actualizar la investigación. La coordinación y el framework se concretan posteriormente en el bloque 3; el almacenamiento sigue pendiente.

#### A. Ficha de la información disponible

El sistema construye una ficha cuya estructura es estable y cuyo contenido se adapta a los archivos y contexto de cada tienda:

| Aspecto | Información que conservar |
|---|---|
| Contenido | Tablas disponibles y qué representa cada una |
| Nivel de detalle | Totales diarios o semanales, ventas por producto, líneas de tickets u otro nivel identificado |
| Significado | Interpretación de fechas, cantidades, importes y estados |
| Cobertura | Periodos, huecos y posibles exclusiones |
| Calidad | Valores ambiguos, duplicados potenciales e inconsistencias |
| Relaciones | Qué tablas podrían relacionarse y con qué evidencia |
| Contexto | Información declarada por el propietario |
| Información ausente | Qué falta y si el cliente puede o quiere aportarlo |

No se transforma obligatoriamente toda entrada en una tabla universal de ventas. Los datos agregados pueden conservar su estructura y servir para investigaciones distintas de las que permiten los tickets.

Cada interpretación distingue su estado: **observado**, **inferido**, **confirmado** o **sin resolver**, con su procedencia. Por ejemplo, observar columnas de fecha e importe no confirma por sí solo que cada fila sea el total de un día. Una inferencia no se convierte silenciosamente en un hecho.

#### B. Investigaciones candidatas

El sistema combina la guía de preguntas habituales, las posibilidades de los datos y las preocupaciones del propietario. Puede proponer otras investigaciones pertinentes si encuentra información que las justifique. No está obligado a ejecutar todas las candidatas.

Ejemplos: comparar evolución semanal, examinar concentración de devoluciones o comprobar si una aparente caída coincide con días ausentes del archivo.

#### C. Plan de investigación

Cada investigación conserva:

- Pregunta y utilidad para el negocio.
- Datos y definiciones necesarios.
- Situación actual y dependencias.
- Operación prevista.
- Comprobación necesaria para publicar el resultado.
- Siguiente paso.

Los estados de trabajo acordados son: **propuesta**, **necesita aclaración**, **lista para ejecutar**, **en ejecución**, **verificada** o **descartada con motivo**. Las dependencias y limitaciones permiten distinguir una espera por aclaración, un dato opcional ausente o una capacidad no disponible. El detalle de implementación de las transiciones queda pendiente.
         h
#### D. Priorización de investigaciones y preguntas

Priorizar según utilidad para la preocupación del cliente, evidencia disponible, magnitud potencial cuando pueda estimarse, esfuerzo/coste y dependencias. Una aclaración que desbloquea varias investigaciones puede ir primero.

No se fija aún una puntuación matemática rígida. Se conserva una justificación breve y revisable de la prioridad, sin registrar razonamiento interno del modelo.

Preguntar cuando la respuesta pueda cambiar una conclusión, desbloquear una investigación útil o evitar un error importante. Reutilizar una respuesta en todas las investigaciones donde aplique. Si solo permite profundizar, la petición es opcional y no detiene innecesariamente el trabajo que ya tiene base.

#### E. Actualización ante respuestas, archivos o resultados nuevos

1. Actualizar la ficha de información.
2. Identificar las investigaciones y resultados afectados.
3. Desbloquear, modificar o descartar esas investigaciones.
4. Recalcular los resultados anteriores si cambió una premisa utilizada.
5. Conservar qué cambió y por qué.

Si el dueño aclara que un importe ya incluía el descuento, deben revisarse los cálculos que lo habían restado; no basta con guardar la respuesta para el futuro. Si llegan ventas detalladas junto a totales diarios de la misma actividad, no se suman ambos: puede usarse una fuente para analizar y otra para contrastar, tras comprobar su relación.

#### F. Caso de referencia aceptado

Con un archivo de fecha e importe diario, el sistema identifica posibilidades de evolución, aclara el significado del importe si hace falta, propone comparaciones con cobertura suficiente y ofrece profundizar con detalle por artículo.

- Si el cliente no tiene el detalle, continúa con el análisis agregado.
- Si lo aporta, comprueba su relación con lo existente y amplía el plan.
- Si hay días ausentes cuyo motivo se desconoce, limita las comparaciones afectadas y conserva otras conclusiones respaldadas.

**Resultado de este bloque:** quedan acordadas la ficha de información, la estructura del plan y las reglas de actualización. Sus esquemas técnicos, implementación y pruebas siguen pendientes. Estas decisiones no constituyen una evaluación ya ejecutada.

### 7.3. Decisiones acordadas del bloque 3: coordinación de IA y verificación

Estas decisiones han sido aceptadas por el usuario. Definen la arquitectura inicial que se implementará y evaluará; no afirman que varios agentes mejoren por sí solos la calidad ni que la solución ya haya superado pruebas.

#### A. LangGraph para coordinar, lógica de dominio propia

Usar LangGraph como infraestructura de orquestación: estado de ejecución, transiciones, ciclos de investigación, persistencia mediante checkpoints e interrupciones para pedir respuestas al usuario. No implica adoptar LangChain, un servicio de alojamiento concreto ni un modelo determinado.

Desarrollar a medida la ficha de información, el plan, la interpretación de datos, las preguntas, las herramientas analíticas, las comprobaciones, los criterios de revisión y el informe. Mantener cálculos, validadores y estructuras de dominio separados del framework para probarlos y poder sustituir la coordinación sin rehacer el producto.

La infraestructura no garantiza por sí sola la exactitud, el aislamiento, los presupuestos ni la recuperación correcta. Hay que configurar almacenamiento duradero, controlar operaciones repetidas al reanudar y aplicar nuestras reglas de versiones e invalidación. La elección del almacenamiento corresponde al bloque 5.

#### B. Un agente principal que planifica y ejecuta

El agente principal mantiene la responsabilidad sobre el caso: inspecciona, interpreta, prepara preguntas, planifica, utiliza herramientas, examina resultados, modifica o abandona investigaciones y prepara conclusiones con evidencia.

Planificación y ejecución son funciones explícitas, pero no requieren dos agentes independientes para el MVP. Pueden implementarse con fases, nodos o instrucciones distintas, conservando el mismo estado del caso. El plan se guarda como información estructurada y revisable; no queda implícito en la conversación ni se congela antes de ejecutar.

No se crean inicialmente agentes separados para limpieza, ventas, categorías o redacción. Un bloque funcional o nodo no equivale automáticamente a un agente.

#### C. Revisor con responsabilidad separada

Un revisor examina las conclusiones propuestas junto con sus evidencias, definiciones y limitaciones. Puede consultar las fuentes autorizadas y pedir comprobaciones. Debe detectar diferencias entre cifras y afirmaciones, periodos incompatibles, hipótesis presentadas como hechos, causalidad no demostrada y recomendaciones sin sustento.

Sus observaciones deben indicar el problema y la corrección o comprobación necesaria. No inventa sustitutos para datos ausentes ni aprueba una cifra por plausibilidad. Puede utilizar el mismo modelo que el analista con contexto e instrucciones separados; esto no garantiza independencia de errores.

#### D. Herramientas, controlador y condiciones de publicación

Las herramientas ejecutan operaciones reproducibles. Un controlador de software mantiene el estado autorizado, aplica permisos y presupuestos, coordina pausas y reintentos, y exige las comprobaciones previstas antes de publicar. El agente no puede saltarse estas condiciones declarando que un resultado es correcto.

Combinar comprobaciones programáticas —ejecución, versión de datos, conciliaciones pertinentes, cardinalidad de relaciones y correspondencia entre cifras y resultados— con revisión del significado, cobertura, supuestos y alcance de las conclusiones. El acuerdo entre agentes no sustituye la comprobación numérica.

Flujo inicial: **inspección y plan → ejecución y revisión del plan → resultados e informe candidato → comprobaciones y revisión → corrección o publicación**. Los bucles responden a lo encontrado; no obligan a ejecutar un menú fijo de análisis. La presentación utiliza resultados aprobados; cualquier cambio posterior en cifras o afirmaciones requiere volver a validar lo afectado.

#### E. Estado compartido, recuperación y límites

Conservar archivos y versiones, interpretaciones con procedencia, respuestas del dueño, disponibilidad de información, plan, resultados, evidencias y comprobaciones. Los agentes reciben la parte necesaria del caso mediante herramientas y contexto seleccionado; no todos los archivos ni todo el historial en cada llamada.

El controlador aplica cambios propuestos sobre el estado. El revisor registra observaciones sin reescribir fuentes o declaraciones del usuario. Una aclaración o archivo nuevo invalida los resultados dependientes cuando corresponda.

Si una pregunta es esencial, guardar el trabajo y permitir continuar cuando llegue la respuesta; las investigaciones independientes pueden avanzar. Ante datos opcionales no aportados, ajustar el plan. Ante un fallo, distinguir reintento técnico, corrección analítica o necesidad de aclaración. Retirar lo que no se pueda verificar y entregar lo demás si conserva utilidad.

Habrá límites globales de tiempo, coste, iteraciones y correcciones. Sus valores quedan pendientes de medición: la referencia de dos rondas de corrección por problema discutida durante la propuesta no es un límite numérico cerrado.

#### F. Cuándo separar planificación y ejecución o añadir investigadores

**Evolución acordada para el producto completo (21 de septiembre de 2026):** separar un agente de negocio, un agente analítico y un revisor, con colaboración iterativa y entregas estructuradas. Sus responsabilidades, estado compartido y relación con informe/dashboard están en la [sección 18.6 de la definición del producto](<Decision Room - Definicion del producto.md#186-organización-multiagente-del-producto-final>). Esta arquitectura objetivo no cambia el alcance del MVP: aquí se mantiene el agente principal que planifica y ejecuta, más el revisor separado.

Considerar agentes especializados cuando haya investigaciones suficientemente independientes, problemas medidos de contexto o ventajas comprobables de especialización. Compartir definiciones y usar entregas estructuradas antes de paralelizar. La autonomía no exige maximizar el número de agentes.

Evaluar la arquitectura inicial frente a una referencia de agente principal con comprobaciones programáticas, y frente a más investigadores solo cuando exista una razón concreta. Medir errores, utilidad, preguntas innecesarias, coste y tiempo con los escenarios del bloque 1.

**Estado actualizado el 21 de septiembre de 2026:** ingesta y herramienta de Python aislado implementadas con estructuras, contrato y límites iniciales. Pendientes: modelos y proveedor, agente y revisor, backend de checkpoints, presupuestos globales y evaluación del recorrido completo. Ver el avance de la sección 9.

Referencias técnicas consultadas para la elección: [visión general de LangGraph](https://docs.langchain.com/oss/python/langgraph/overview) e [interrupciones y reanudación](https://docs.langchain.com/oss/python/langgraph/interrupts). Describen capacidades de infraestructura, no validan la calidad de nuestro producto.

### 7.4. Decisiones acordadas del bloque 4: ingesta, herramientas de análisis y consultas

Estas decisiones han sido aceptadas por el usuario, incluida la ejecución de Python desde el MVP. Sustituyen la propuesta inicial de posponer el código Python generado. Las tecnologías y controles están elegidos a nivel de diseño; aún no están implementados ni evaluados.

#### A. Recepción, inspección y preparación

Admitir CSV y Excel `.xlsx`, incluidas varias hojas y archivos complementarios dentro de límites físicos por definir. No se promete interpretar cualquier disposición de hoja, formato antiguo, documento escaneado o archivo arbitrario.

Conservar el original, inspeccionar su estructura y preparar tablas para el análisis registrando las transformaciones. Identificar encabezados, separadores, tipos, cobertura, valores ausentes y problemas de lectura. Mantener referencias al archivo, hoja y registros de origen. Ningún límite o fallo de lectura debe producir un análisis parcial presentado como completo.

Separar las transformaciones técnicas de la interpretación del negocio. Convertir un importe con formato conocido no confirma si incluye impuestos; detectar filas repetidas no autoriza a borrarlas. No eliminar negativos, deduplicar ni rellenar días sin registros con ceros de forma indiscriminada. Las ambigüedades materiales requieren aclaración o limitar el resultado afectado.

Tratar explícitamente las fórmulas de Excel: distinguir fórmula y valor guardado y no presentar este último como recién recalculado. Conservar los problemas relevantes y pedir una exportación actualizada cuando sea necesario.

#### B. Acceso progresivo a los datos

El agente recibe inicialmente catálogo de tablas y columnas, perfil de cobertura/calidad, muestras e interpretaciones disponibles. Puede recuperar registros concretos y ejecutar cálculos sobre las tablas autorizadas completas. Las muestras sirven para inspección; las cifras publicadas se calculan sobre el conjunto pertinente, con filtros y exclusiones explícitos.

El código generado no obtiene acceso general al almacenamiento o a otras tiendas. Las herramientas entregan únicamente los datos autorizados para el caso. Las condiciones de acceso y las definiciones confirmadas no se delegan al criterio del agente.

#### C. Python desde el MVP y herramientas reutilizables

El agente puede escribir y ejecutar Python personalizado desde la primera entrega, además de consultas SQL. Puede elegir y combinar estas capacidades según la investigación. No se exige traducir toda exploración a un catálogo cerrado de métricas ni utilizar SQL para todo.

Ofrecer una base pequeña de herramientas y funciones propias: acceso a datos y definiciones, perfilado, filtros y agrupaciones, comparaciones, comprobación de relaciones, conciliaciones y recuperación de evidencia. Las funciones reutilizables pueden estar disponibles dentro del entorno Python; no todas necesitan ser herramientas separadas visibles al modelo.

El agente puede proponer transformaciones y cálculos nuevos, pero no omitir los controles de ejecución, el registro de evidencia ni las condiciones de publicación. Un script sin errores no demuestra que su interpretación o sus cálculos sean correctos.

Python facilita futuras capacidades de ML y nuevos cálculos desde el chat; no incorpora predicciones ni chat posterior al alcance del MVP. El futuro chat podrá reutilizar resultados verificados sin ejecutar código nuevo para cada pregunta.

#### D. Tecnología inicial

| Componente | Elección acordada | Función |
|---|---|---|
| Ingesta y herramientas | Python | Preparación y operaciones de análisis |
| Lectura de Excel | openpyxl | Inspección de archivos `.xlsx`, incluidas fórmulas y valores guardados |
| Consultas analíticas | DuckDB | Consultas SQL sobre tablas; disponible también desde Python |
| Tablas preparadas | Parquet | Archivos tabulares reutilizables para las ejecuciones |
| Código personalizado | Python en un entorno aislado | Exploraciones adaptadas a cada caso |

DuckDB se utiliza inicialmente como motor integrado en los trabajos analíticos, sin exigir un servidor analítico independiente. Esta elección no determina dónde se guardan usuarios, respuestas, planes, informes o checkpoints. No se exige una estructura universal de ventas para las tablas Parquet.

Convex queda como candidato para la aplicación en el bloque 5. ClickHouse se pospone hasta que volumen, concurrencia, ingesta continua u otras necesidades medidas lo justifiquen. Temporal no se incorpora por defecto; la recuperación y ejecución duradera se concretarán sin duplicar responsabilidades entre coordinadores. Los checkpoints de LangGraph no sustituyen por sí solos al servicio que ejecuta y recupera trabajos.

#### E. Ejecución controlada y evidencia

Ejecutar SQL y Python generado en un entorno aislado, con librerías preinstaladas y versiones registradas, originales de solo lectura, salidas separadas, sin credenciales del sistema ni acceso de red por defecto, y límites de tiempo, memoria, disco y tamaño de resultados. No basta con filtrar instrucciones SQL por su primera palabra ni confiar en restricciones escritas en el prompt. La tecnología concreta del entorno y los valores de los límites siguen pendientes.

Registrar fuentes y versiones, definiciones, filtros, periodos, código o consulta, resultados, errores, cobertura y referencias a evidencia. El controlador registra la ejecución y valida las salidas; el código generado no puede declarar por sí solo que un hallazgo está aprobado. Conservar el entorno necesario para repetir cálculos y controlar aleatoriedad cuando proceda.

Combinar verificaciones numéricas pertinentes con revisión semántica: cobertura comparable, relaciones que no multipliquen registros, componentes conciliables y correspondencia entre cifras y resultados. Repetir la misma consulta no prueba por sí solo que esté bien planteada. Si una definición cambia, se invalidan y recalculan los resultados dependientes.

#### F. Caso de referencia y pendientes

Un archivo de ventas diarias más un catálogo de productos no permite atribuir ventas a categorías sin una relación sustentada. El agente puede analizar la evolución, pedir detalle por artículo y ampliar si llega información relacionable; si no llega, conserva el análisis agregado. Python no autoriza a inventar esa relación.

**Pendiente:** contratos técnicos, librerías adicionales, entorno de ejecución, límites de archivos/hojas/filas y recursos, tratamiento detallado de errores, casos de prueba y mediciones. La siguiente decisión es la persistencia y el estado del bloque 5. No se inicia la implementación.

Referencias consultadas: [DuckDB](https://duckdb.org/why_duckdb), [Parquet en DuckDB](https://duckdb.org/docs/current/data/parquet/overview), [aislamiento de consultas](https://duckdb.org/docs/current/operations_manual/securing_duckdb/overview) y [lectura de Excel con openpyxl](https://openpyxl.readthedocs.io/en/stable/api/openpyxl.reader.excel.html). Estas capacidades documentadas no constituyen pruebas de rendimiento de Decision Room.

### 7.5. Decisiones acordadas del bloque 5: persistencia y estado

Estas decisiones han sido aceptadas por el usuario. **PostgreSQL es la opción inicial, con la posibilidad explícitamente abierta de cambiar a Convex.** La decisión se contrastará mediante una prueba de integración y recuperación antes de consolidar el backend. No se ha ejecutado esa prueba ni se inicia la implementación al registrar este acuerdo.

#### A. Separación de información y archivos

| Información | Persistencia inicial propuesta y aceptada |
|---|---|
| Excel/CSV originales y tablas preparadas en Parquet | Almacenamiento privado de archivos, con referencias y versiones |
| Negocios, usuarios y permisos | PostgreSQL |
| Catálogo de fuentes, tablas, columnas y relaciones | PostgreSQL, con referencias a los archivos analíticos |
| Interpretaciones, preguntas, respuestas y disponibilidad de información | PostgreSQL |
| Planes, investigaciones, trabajos y estados | PostgreSQL |
| Resultados, comprobaciones y referencias a evidencia | PostgreSQL; salidas grandes como archivos referenciados |
| Código ejecutado, gráficos e informes | Contenido pequeño en PostgreSQL; archivos grandes mediante referencias |
| Checkpoints de LangGraph | PostgreSQL, en tablas dedicadas y separados lógicamente de los datos del producto |

No copiar todas las filas de cada Excel a la base de datos de la aplicación ni crear en ella una tabla física por cada archivo del cliente. El catálogo describe los datos; DuckDB y Python analizan las tablas preparadas. El proveedor concreto de PostgreSQL y del almacenamiento privado sigue pendiente.

#### B. PostgreSQL inicial y alternativa Convex

La preferencia inicial por PostgreSQL se apoya en su integración documentada con los checkpoints de LangGraph y en poder utilizar un servicio de base de datos para la aplicación y la recuperación, con tablas separadas. Se pueden combinar relaciones estables con campos JSON para información variable, sin dejar de validar su estructura.

Convex sigue siendo una alternativa seria por sus funciones de backend y actualización reactiva de la interfaz. La integración de PostgreSQL con LangGraph es una ventaja, pero no debe decidir por sí sola el backend completo. No se presupone que Convex sea incompatible con un servicio Python.

Si se cambia a Convex, el reparto previsto sería: Convex para estado del producto, respuestas, permisos y referencias; almacenamiento privado para archivos; servicio Python con LangGraph para investigación; entorno aislado con DuckDB para cálculos. Habrá que resolver explícitamente la persistencia de checkpoints y la coordinación con el estado visible en Convex, sin duplicar responsabilidades ni asumir una integración ya comprobada.

Admitir nuevas tablas, actualizaciones o futuros conectores a ERP/CRM es posible con ambas alternativas y no decide por sí solo la elección. La reactividad de la interfaz no sustituye la lógica de sincronización de fuentes externas.

#### C. Conocimiento del negocio con procedencia y alcance

Guardar el texto original de cada respuesta y su interpretación estructurada: significado, procedencia, estado, alcance temporal y tablas o investigaciones a las que aplica. Mantener separado lo observado, inferido, confirmado por el usuario y sin resolver.

Ejemplo: «Desde julio, los importes exportados ya incluyen el descuento» se aplica a las exportaciones y fechas indicadas, no automáticamente a archivos anteriores o de otro sistema. Confirmado por el usuario no equivale a comprobado contra los registros; conservar y resolver las discrepancias materiales.

El historial de conversación sirve de respaldo, pero no es la única memoria. Las preguntas pendientes y las respuestas de no disponibilidad se conservan para evitar repeticiones.

#### D. Versiones, dependencias e incorporación de fuentes

Cada análisis referencia versiones explícitas de archivos, reglas de preparación, definiciones, respuestas aplicables, código y resultados. Ante un archivo nuevo, determinar si sustituye, complementa o solapa información existente. No sumar automáticamente fuentes que describen la misma actividad.

Registrar dependencias entre fuentes, definiciones y resultados. Una corrección invalida los resultados afectados y exige recalcularlos antes de volver a publicarlos. Si no se puede acotar con seguridad el efecto, revisar un conjunto más amplio. No construir en el MVP una plataforma general de gestión de dependencias.

Los informes conservan las fuentes y supuestos de su revisión. Las nuevas revisiones no reescriben silenciosamente las anteriores; identificar las sustituidas cuando corresponda. Esta trazabilidad no exige todavía una interfaz completa de historial.

Preparar un proceso común de identificación, preparación y versionado para las fuentes: Excel/CSV ahora y conectores en el futuro. Las integraciones futuras deberán distinguir registros nuevos, correcciones y eliminaciones, conservar la procedencia y evitar duplicaciones. No se implementan conectores ni sincronización automática en este MVP.

#### E. Estado del producto y recuperación de ejecución

Distinguir el estado del producto —preguntas, planes, resultados verificados e informes— de los checkpoints técnicos de LangGraph. Los checkpoints contienen contexto y referencias necesarios para continuar, no tablas completas ni la única copia del conocimiento del negocio.

Disponer de un registro duradero de trabajos y un proceso en segundo plano que los ejecute y permita recuperar intentos interrumpidos. Evitar que dos ejecutores publiquen simultáneamente para el mismo trabajo y que los reintentos dupliquen respuestas, resultados o informes. Los mecanismos concretos de toma de trabajos, reintento y publicación se diseñarán y probarán durante la implementación.

Un checkpoint no conserva por sí solo una sesión Python completa. El entorno debe poder reconstruirse con los archivos, código y resultados persistidos; repetir el paso incompleto cuando corresponda y reutilizar únicamente resultados compatibles con las versiones actuales.

Temporal no se incorpora por defecto. El enfoque inicial necesita probar su recuperación real antes de concluir que cubre las necesidades; no se confunde almacenar checkpoints con supervisar y recuperar trabajos.

#### F. Recuperación selectiva y aislamiento

Recuperar información mediante identificadores, relaciones e índices: definiciones de una tabla, respuesta a una pregunta, resultados de una investigación o archivos autorizados. No introducir una base vectorial para el MVP; reconsiderar búsqueda semántica cuando exista una necesidad concreta de recuperar documentación.

Comprobar pertenencia y permisos antes de entregar datos, resultados o accesos a archivos. El código generado recibe únicamente los archivos autorizados y no credenciales generales del almacenamiento o PostgreSQL. Usar almacenamiento privado y accesos temporales emitidos tras comprobar permisos, sin asumir que conocer un identificador autoriza su lectura.

#### G. Prueba técnica y criterios pendientes

Antes de consolidar el backend, comprobar este recorrido: **subir archivo → iniciar análisis Python → guardar una pregunta → interrumpir el proceso → recibir respuesta → recuperar el análisis → mostrar el resultado**. Evaluar el trabajo de integración, la recuperación y la sincronización del estado para mantener PostgreSQL o cambiar a Convex. No hace falta implementar un conector ERP para esta comparación.

Comprobar además que cerrar la aplicación no pierde preguntas ni trabajo; interrumpir un cálculo no duplica resultados; corregir respuestas invalida las cifras dependientes; volver a subir el mismo archivo no duplica ventas; los informes conservan sus fuentes y definiciones; y un usuario o ejecución no accede a otra tienda.

**Pendiente:** esquemas técnicos e índices, proveedores, integración elegida, coordinación de escrituras y checkpoints, recuperación y controles de acceso implementados, y ejecución de las pruebas. Las decisiones de este bloque están acordadas, pero su funcionamiento no se ha demostrado.

Referencias consultadas: [checkpoints de LangGraph con PostgreSQL](https://docs.langchain.com/oss/python/langgraph/add-memory), [JSON en PostgreSQL](https://www.postgresql.org/docs/current/datatype-json.html), [Convex](https://docs.convex.dev/understanding/overview) y [accesos temporales a archivos en S3](https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-presigned-url.html).

### 7.6. Decisiones acordadas del bloque 6: informe e interfaz mínima

Estas decisiones han sido aceptadas por el usuario. Definen cómo convertir resultados comprobados en un informe y presentar el recorrido completo. La estructura del contenido queda acordada; no se ha construido ni probado la interfaz ni elegido su framework.

#### A. Cuatro momentos del recorrido

| Momento | Experiencia |
|---|---|
| Describe y aporta | Explicar brevemente el negocio y subir archivos |
| Aclara | Ver la interpretación inicial y responder las preguntas necesarias |
| Espera el análisis | Consultar progreso real y saber si se necesita una respuesta |
| Consulta el informe | Leer conclusiones, explorar evidencia y entender limitaciones |

Son estados del recorrido, no necesariamente cuatro páginas separadas. El propietario no configura agentes, herramientas ni métricas antes de empezar.

Cada archivo muestra un estado comprensible: recibido, preparado o necesita atención. Los errores explican el problema y un siguiente paso concreto. Las preguntas se presentan en tandas pequeñas, con su motivo y opciones o texto libre según corresponda. Los datos adicionales se piden explicando su utilidad y permitiendo continuar sin ellos. Corregir interpretaciones no exige revisar un formulario técnico exhaustivo.

#### B. Progreso real y continuidad

Mostrar estados derivados de la ejecución: revisando archivos, necesita aclaración, analizando, comprobando conclusiones e informe disponible. No inventar porcentajes ni tiempos restantes, ni mostrar razonamiento interno.

Permitir cerrar y volver sin perder respuestas. Una duda importante descubierta durante el análisis puede generar otra pregunta. Distinguir pregunta pendiente, fallo técnico recuperable y datos insuficientes, con mensajes y siguientes pasos adecuados a cada situación.

#### C. Página de informe adaptable

Mantener una página con resumen y secciones seleccionadas según el análisis sustentado. La cabecera identifica negocio, periodo, fecha de generación y cobertura. Una limitación que cambie la lectura del conjunto debe ser visible desde el comienzo; por ejemplo, un mes con registros solo hasta cierto día.

Presentar primero hallazgos y explicación breve; después las cifras y gráficos que los sostienen. Priorizar según preocupación del propietario, magnitud observable, solidez de evidencia y utilidad de una siguiente comprobación. No imponer un número de tarjetas ni fabricar alertas si no aparecen cambios relevantes.

Cada hallazgo incluye:

- Qué se ha observado, con una afirmación concreta.
- Cifras y comparación pertinente que lo sostienen.
- Interpretación y límites de lo que se puede concluir.
- Siguiente comprobación cuando esté justificada.
- Acceso «Ver cómo se ha calculado».

Ejemplo ilustrativo con periodos comparables: ventas de 10.000 € frente a 8.000 €, de cuya diferencia 1.200 € corresponde a regalos. Se puede afirmar que la categoría concentra el 60 % de la caída registrada; no que se haya demostrado su causa ni que los 1.200 € sean dinero recuperable. Una comprobación de disponibilidad o surtido sería un siguiente paso, no una explicación ya probada.

#### D. Evidencia comprensible

«Ver cómo se ha calculado» abre un detalle dentro de la página: archivos y hojas, periodos y filtros, definiciones, explicación sencilla del cálculo, tabla de resultados, registros pertinentes y exclusiones o problemas relevantes.

El código ejecutado se conserva para trazabilidad y revisión técnica, pero no constituye la explicación principal para el cliente. Las limitaciones aparecen junto al hallazgo afectado, además de en el resumen general cuando corresponda. Consultar evidencia no requiere iniciar un chat.

#### E. Contenido estructurado y presentación controlada

El agente propone un informe estructurado: resumen, secciones, hallazgos vinculados a resultados, referencias a cifras y evidencias, gráficos, limitaciones y siguientes comprobaciones. La aplicación lo presenta mediante componentes conocidos. No generar una página HTML arbitraria por cliente.

El agente mantiene autonomía sobre qué comunicar y cómo organizar el contenido pertinente. La aplicación controla presentación, accesibilidad y coherencia. Empezar con líneas, barras y tablas; seleccionar gráficos solo cuando aporten comprensión.

Los valores se obtienen de resultados verificados, evitando que el modelo los vuelva a transcribir como una fuente independiente. Comprobar la correspondencia entre representación y datos. Revisar también las afirmaciones de la redacción final; cálculos correctos no bastan para aprobar una interpretación. Cualquier cambio posterior en cifras o afirmaciones requiere revalidar lo afectado.

#### F. Resultados finales y alcance

| Situación | Entrega |
|---|---|
| Investigaciones útiles completadas | Informe con resultados respaldados |
| Parte del análisis no se puede completar | Lo verificado y límites explícitos |
| No hay base para ninguna conclusión | Bloqueo explicado y datos o aclaraciones necesarios |
| No hay cambios relevantes | Informe breve sin alertas artificiales |

Terminado significa concluido para el alcance declarado, no conocimiento completo del negocio. Mantener fuera de esta entrega PDF, chat libre posterior, filtros abiertos y configuración de dashboards. La navegación por secciones y la evidencia desplegable aportan la interacción del MVP.

#### G. Comprobación de la experiencia

Observar si un propietario puede explicar un hallazgo con sus palabras, distinguir observación e hipótesis, encontrar la fuente de una cifra, identificar una limitación, saber qué comprobar después y retomar el proceso tras cerrar la aplicación.

Revisar lectura en móvil, uso con teclado y gráficos que no dependan solo del color. El criterio de éxito es comprender mejor el negocio y poder comprobar el informe sin conocimientos de análisis de datos.

**Pendiente:** diseño visual, componentes y framework, contrato técnico del informe, implementación y pruebas con usuarios. No se inicia la construcción de la interfaz al registrar este acuerdo.

### 7.7. Decisiones acordadas del bloque 7: evaluación y despliegue

Estas decisiones han sido aceptadas por el usuario. Concretan cómo medir el comportamiento definido en el bloque 1 y bajo qué condiciones entregar versiones. La aprobación del plan no implica haber ejecutado las evaluaciones, desplegado el sistema ni validado utilidad o demanda comercial.

#### A. Batería de escenarios y referencias

Preparar los escenarios acordados con dos tipos de datos: archivos controlados pequeños, con resultados calculados y revisados independientemente; y archivos realistas de formatos variados, procedentes de datos públicos adecuados y posteriormente de comercios participantes. Los primeros permiten localizar errores; los segundos comprueban adaptación fuera de nuestros ejemplos.

Cada caso define datos disponibles, respuestas del propietario, resultado mínimo esperado, conclusiones prohibidas, referencias numéricas y comportamiento esperado. No exige un plan, texto o secuencia de herramientas únicos. Reservar formatos no utilizados para ajustar el sistema antes de su evaluación.

Ejemplo: con ventas diarias sin productos y un propietario que no dispone de más detalle, analizar evolución si hay periodos comparables, no atribuir cambios a artículos e insistir únicamente si aparece una razón nueva pertinente. Las referencias de totales y variaciones se calculan de forma independiente del agente evaluado.

#### B. Dimensiones de evaluación

| Dimensión | Comprobaciones |
|---|---|
| Exactitud y evidencia | Cifras frente a referencias; filtros, periodos y exclusiones; relaciones sin duplicaciones; correspondencia entre cifras, gráficos y evidencia; versiones correctas |
| Adaptación y análisis | Aclarar ambigüedades materiales, continuar sin datos opcionales, aprovechar información adicional, distinguir observación e hipótesis, evitar conclusiones sin sustento y abstenciones innecesarias |
| Utilidad y comprensión | Entender el resultado, localizar su evidencia y saber qué revisar después |
| Recursos y operación | Tiempo, coste, reintentos, recuperación y finalización dentro de límites |

No condensar estas dimensiones en una única cifra de «accuracy». Definir precisión, tolerancias pertinentes y redondeo para importes y porcentajes antes de comparar resultados.

Combinar comprobaciones programáticas, revisión humana y, cuando ayude, evaluación por modelos con criterios explícitos contrastados con valoraciones humanas. El revisor del producto no es el único evaluador ni sustituye referencias independientes.

#### C. Repeticiones y fallos deliberados

Empezar la evaluación inicial con tres ejecuciones por escenario y aumentar repeticiones en casos variables o problemáticos. Es un punto de partida operativo, no una garantía estadística ni prueba de ausencia de errores.

Incluir interrupciones durante cálculos; respuestas o peticiones duplicadas; correcciones posteriores a un cálculo; archivos repetidos o solapados; agotamiento de tiempo o memoria; intentos de acceder a otra tienda; y texto en celdas que intente dar instrucciones al agente. El contenido de archivos se trata como datos, sin autoridad para cambiar instrucciones o permisos.

Probar la recuperación y los efectos repetidos al reanudar nodos de LangGraph. No confundir un checkpoint guardado con una ejecución recuperada correctamente.

#### D. Registro y medición de ejecuciones

Conservar versiones de datos, instrucciones, modelos y herramientas; investigaciones realizadas y abandonadas; preguntas; código y resultados; comprobaciones y observaciones del revisor; errores y reintentos; motivo de finalización; y tiempo y coste por etapa.

Separar tiempo de procesamiento y espera del usuario. Medir coste por informe útil, incluyendo fallos y reintentos, además del coste de llamadas individuales. Los registros operativos referencian evidencias y evitan copiar indiscriminadamente datos del cliente. No se necesita guardar razonamiento interno del modelo para medir estos aspectos.

#### E. Condiciones de publicación y presupuestos

Para publicar cada informe, sus cifras deben apuntar a resultados comprobados, no puede utilizar resultados invalidados y las limitaciones materiales deben ser visibles. Corregir o retirar conclusiones pendientes.

Para publicar una versión, los casos obligatorios deben cumplir sus criterios, recuperación y aislamiento deben superar sus pruebas, no debe haber fallos críticos conocidos sin resolver y el tiempo y coste deben quedar dentro del presupuesto fijado para el piloto.

Se consideran críticos, entre otros, mezclar tiendas, inventar evidencia, publicar cifras materialmente incorrectas o perder respuestas necesarias para continuar. Una media favorable no compensa esos fallos. Superar la batería no demuestra que el sistema nunca se equivoca.

Disponer de límites configurables desde las primeras ejecuciones. Fijar los valores concretos de tiempo y presupuesto usando mediciones iniciales antes de abrir el piloto; no inventar objetivos de rendimiento sin datos ni permitir ejecución ilimitada mientras se mide.

#### F. Despliegue del piloto privado

| Componente | Responsabilidad |
|---|---|
| Aplicación web y API | Archivos, preguntas, estados e informes |
| Proceso de análisis en segundo plano | Ejecutar LangGraph y recuperar trabajos |
| Entorno aislado | Ejecutar Python generado y DuckDB |
| PostgreSQL inicial y almacenamiento privado | Estado, archivos y resultados, manteniendo abierta la alternativa Convex del bloque 5 |

La petición del navegador inicia un trabajo y no mantiene abierta una conexión durante todo el análisis. Separar desarrollo, pruebas y piloto. Antes de utilizar datos reales, comprobar acceso, borrado, copias de seguridad y restauración. Permitir detener nuevas ejecuciones y volver a una versión anterior compatible si una actualización falla.

Los proveedores se elegirán comprobando primero los requisitos de aislamiento y ejecución duradera. No incorporar ClickHouse o Temporal únicamente para desplegar el piloto.

#### G. Prueba con propietarios

Plantear un piloto inicial con 3–5 comercios del perfil elegido, todavía por reclutar. Observar el recorrido completo sin explicar cada pantalla; comprobar qué entienden, qué pueden verificar y si el informe aporta algo que antes les costaba obtener.

Revisar manualmente los primeros informes antes de entregarlos y registrar cualquier intervención. Esta supervisión es temporal: si las correcciones manuales son habituales, el MVP aún no cumple su objetivo de autonomía. El piloto puede detectar problemas y señales de utilidad; no demuestra por sí solo demanda comercial o disposición a pagar.

#### H. Resultado esperado y pendientes

El bloque se materializa en una batería ejecutable, registros que permiten investigar fallos y un piloto privado del recorrido completo. Las evaluaciones empiezan con el primer código y acompañan los cambios, no se dejan para el final del desarrollo.

**Pendiente:** archivos y referencias concretos, criterios ejecutables y tolerancias, mediciones iniciales, límites numéricos, proveedores y despliegue, reclutamiento, implementación y resultados de pruebas. No se inicia el despliegue ni el contacto con comercios al registrar este acuerdo.

Referencias consultadas: [evaluación de agentes](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) y [reanudación de LangGraph](https://docs.langchain.com/oss/python/langgraph/interrupts).

## 8. Cómo abordaremos la parte técnica

Los siete bloques quedan acordados en las secciones 7.1–7.7. El [plan de implementación por entregas](<Decision Room - Plan de implementacion.md>) concreta su orden de construcción, con pruebas desde el inicio. Un bloque funcional **no equivale automáticamente a un agente** ni a una entrega de software independiente.

| Orden | Bloque | Decisiones y estado | Resultado de la planificación |
|---|---|---|---|
| 1 | Comportamiento y escenarios de evaluación | Acordado: misión, autonomía, evaluación por investigación, plan revisable, preguntas, verificación y finalización. Pendientes: archivos de prueba, medición y límites numéricos | Reglas aceptadas en la sección 7.1 y escenarios de la sección 7; ningún esquema de ventas universal obligatorio |
| 2 | Evaluación de datos y planificación | Acordado: ficha de información, estados de interpretación, candidatas, estructura del plan, priorización y actualización de resultados afectados. Pendientes: esquemas técnicos, implementación y pruebas | Decisiones aceptadas en la sección 7.2; modelo lógico de información disponible y plan revisable |
| 3 | Coordinación de IA y verificación | Acordado: LangGraph, agente principal que planifica y ejecuta, revisor separado, herramientas y controlador con comprobaciones obligatorias. Pendientes: modelos, implementación, límites numéricos y evaluación | Arquitectura inicial aceptada en la sección 7.3; no se ha demostrado aún su rendimiento |
| 4 | Ingesta, herramientas de análisis y consultas | Acordado: CSV/Excel, Python generado desde el MVP, herramientas reutilizables, SQL con DuckDB, Parquet, acceso progresivo y ejecución aislada con evidencia. Pendientes: contratos, entorno, límites y pruebas | Decisiones aceptadas en la sección 7.4; no se ha implementado ni medido el sistema |
| 5 | Persistencia y estado | Acordado: PostgreSQL inicial con opción abierta a Convex, archivos privados separados, conocimiento estructurado con procedencia, versiones, dependencias, recuperación y aislamiento. Pendientes: prueba de integración, proveedores, esquemas e implementación | Decisiones aceptadas en la sección 7.5; la elección inicial se contrastará antes de consolidar el backend |
| 6 | Informe e interfaz mínima | Acordado: cuatro momentos, progreso real, resumen y secciones adaptables, evidencia desplegable, informe estructurado y revisión final. Pendientes: diseño, framework, implementación y pruebas de comprensión | Decisiones aceptadas en la sección 7.6; recorrido mínimo sin PDF, chat posterior ni dashboard avanzado |
| 7 | Evaluación y despliegue | Acordado: escenarios con referencias, evaluación por dimensiones, repeticiones, fallos deliberados, registros y presupuestos, condiciones de publicación y piloto privado. Pendientes: preparación y ejecución de pruebas, valores numéricos, proveedores y reclutamiento | Decisiones aceptadas en la sección 7.7; ninguna evaluación o validación comercial se considera realizada |

Las pruebas y el control de errores se diseñan desde el primer bloque. Los bloques 3–5 se refinan conjuntamente: la arquitectura inicial se concretará con los datos, las operaciones y el almacenamiento necesarios.

### Agentes y recuperación de información

La arquitectura inicial incluye un agente principal y un revisor separado. Planificación y ejecución permanecen dentro del agente principal. No se añaden investigadores especializados sin una necesidad concreta y una mejora evaluable.

«Que los agentes extraigan los datos rápidamente» se descompone en qué consultas hacen, sobre qué volumen, qué resultados se pueden reutilizar y qué tiempo de respuesta necesita el usuario. DuckDB y Parquet quedan elegidos para el trabajo analítico, junto con Python. El bloque 5 propone PostgreSQL inicialmente para aplicación y checkpoints, con archivos privados separados y alternativa Convex abierta. Se recupera el contexto por identificadores, relaciones e índices; no se introduce una base vectorial en el MVP.

### Reutilización y boilerplates

Se estudiará qué base existente encaja una vez fijado el recorrido y los requisitos. Compararemos lo que realmente ahorra frente a lo que obliga a adaptar y mantener. La elección no debe determinar por accidente el producto ni la arquitectura analítica.

## 9. Próximo paso acordado

**Primer avance del 21 de septiembre de 2026:** se prepararon los [tres casos CSV de referencia](../../data/reference-cases/README.md), las estructuras iniciales, la ingesta persistente CSV y la ejecución aislada de Python. La prueba con las 48 tablas de WWI verificó datos, cálculos conocidos, evidencia y recuperación. El [ejecutor local](../technical/sandbox.md) usa Docker dentro de Colima, límites de recursos y resultados candidatos pendientes de revisión. En ese primer hito todavía no se había implementado el agente; los avances posteriores se registran en el plan de implementación.

**Estado actual, 22 de septiembre de 2026:** el agente, las preguntas y recuperación (1.4), Python autónomo (1.5) y el diálogo con el revisor e informe para el cliente (1.6) están implementados. Se ha construido y ejecutado la evaluación integrada del paso 1.7: variantes de datos, respuestas y repeticiones reales. Pasan 101 pruebas automatizadas; se aceptaron independientemente 11 de 24 casos de la matriz y 6 de 9 de la serie posterior, conservando ambas versiones. Las correcciones del propietario invalidan los informes anteriores, pero los nuevos todavía pueden contener errores semánticos. La implementación del evaluador está terminada; la entrega 1 no está aceptada. Ver [resultados y límites](../validation/2026-09-21-evaluation-check.md) y el [plan de implementación](<Decision Room - Plan de implementacion.md>).

El orden es: preparación → recorrido interno completo → web mínima → ampliación de cobertura → preparación operativa → piloto. Dentro de la entrega 1: caso y estructuras → persistencia e ingesta → Python aislado → agente con preguntas y recuperación → investigación autónoma → revisión e informe → variedad de casos. Las evaluaciones acompañan el primer código. Proveedores, modelos, componentes reutilizables y criterios ejecutables se concretarán al abordar cada entrega.

LangGraph, el reparto de responsabilidades, las tecnologías analíticas, el diseño inicial de persistencia, el informe e interfaz mínima y la estrategia de evaluación y despliegue quedan acordados. PostgreSQL se mantiene como opción inicial con cambio a Convex abierto tras comprobar la integración. Los pasos implementados se distinguen arriba del alcance todavía planificado; las pruebas de infraestructura no demuestran autonomía, calidad del informe ni utilidad comercial.


**Avance web, 22 de septiembre de 2026:** por decisión del usuario se construyó
la entrega 2 sin cerrar los fallos analíticos conocidos de la entrega 1. La
aplicación local permite completar el recorrido desde el navegador, recuperar
preguntas y progreso, y consultar informes publicables con evidencia. Las 117
pruebas automatizadas y Computer Use verifican la integración. Un caso con el
modelo real completó el flujo, pero su informe fue retenido al detectar DR-015;
no se confunde la interfaz funcional con la aceptación de sus conclusiones.
Ver [guía web](../technical/web.md) y [validación](../validation/2026-09-22-web-check.md).
