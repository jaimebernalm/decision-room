# Decision Room: definición del producto y experiencia de uso

**Actualizado:** 23 de septiembre de 2026.  
**Estado:** visión del producto completo y organización multiagente objetivo; su implementación y evaluación siguen el alcance acotado del MVP.  
**Base:** decisiones de experiencia del 15 de septiembre, selección de segmento del 17, organización multiagente futura del 21 y continuidad del negocio, memoria compartida y UX cotidiana acordadas el 23 de septiembre. Esta versión actualiza la definición anterior.

Este documento define la experiencia del cliente: cómo empieza, qué aporta, qué recibe y por qué vuelve. Recoge las decisiones acordadas y señala las propuestas de diseño pendientes. La guía de investigación, las capacidades, la diferenciación y sus criterios de validación se concretan en [Servicios y diferenciación](<Decision Room - Servicios y diferenciacion.md>). La sección 18.6 define los roles y la colaboración multiagente del producto final. Las tecnologías y la secuencia de construcción se concretan en el MVP y su plan de implementación.

**Principio transversal:** autonomía para decidir qué investigar, con resultados comprobables. La guía base orienta un plan que se adapta a los datos y respuestas del cliente. Se puede ofrecer valor con información agregada, profundizar con detalle y ampliar la investigación cuando existan datos y herramientas verificables.

**Alcance actualizado de implementación:** el recorrido web mínimo de la entrega 2 está implementado. La siguiente prioridad es la entrega 2.5 del [plan](<Decision Room - Plan de implementacion.md#51-entrega-25-memoria-del-negocio-y-experiencia-cotidiana>): negocio persistente, memoria entre conversaciones, chat, «Mi negocio» e Inicio con prompt. Los pasos 2.5.1–2.5.2 de identidad persistente y memoria versionada están implementados y comprobados; su uso transversal por el agente, conversaciones y nueva navegación siguen pendientes. [MVP y primera entrega](<Decision Room - MVP.md>) conserva el alcance del primer recorrido y recoge esta ampliación. PDF, dashboard libremente configurable y seguimiento de decisiones siguen en el roadmap.

Los textos de pantalla y ejemplos son ilustrativos, no resultados validados ni promesas de rendimiento.

## 1. Visión y propósito

Decision Room ayuda a dueños de pequeños comercios que revenden productos no perecederos a entender los cambios en sus ventas, identificar qué merece atención y explorar decisiones con evidencia, sin tener que aprender a utilizar IA, formular instrucciones o preparar el análisis por su cuenta.

El usuario conoce su negocio, pero puede no saber qué preguntar a sus datos ni qué herramientas utilizar. La plataforma conduce el proceso: recibe contexto y archivos, aclara lo importante y entrega un análisis comprensible que se puede explorar y sobre el que se puede conversar.

**Reducir la fricción forma parte del valor principal del producto**, junto con la calidad del análisis. El dueño no necesita configurar agentes ni dirigir el trabajo técnico.

Propuesta de experiencia:

> Trae los archivos que tienes de tu tienda. Adaptamos el análisis a esa información, aclaramos contigo lo necesario y te ayudamos a entender qué merece atención. Puedes comprobar las cifras y, cuando haya más detalle, profundizar.

La primera visita parte de «Ayúdame a entender mi tienda». Después, hay dos motivos de regreso igualmente importantes: consultar dudas y aportar nuevos datos para obtener una revisión actualizada. Se propone además guardar explícitamente asuntos para revisar, con un seguimiento manual sencillo al actualizar.

## 2. Público y punto de partida del MVP

### 2.1. Usuario principal

Dueño o encargado de una pequeña tienda de productos no perecederos, sin conocimientos necesarios de IA o análisis de datos, que **ya dispone de Excel o CSV aprovechables**, aunque sean totales por día o semana. El detalle por producto y ticket permite análisis adicionales, pero no es un requisito general de entrada. El primer análisis no exige datos personales de compradores.

Se conserva como límite inicial un negocio de una ubicación y un usuario principal. No hace falta resolver colaboración compleja ni consolidación de varias sedes.

Los archivos pueden contener huecos, encabezados ambiguos o información parcial. No se exige perfección, pero sí alguna tabla aprovechable dentro de los formatos que finalmente se admitan.

### 2.2. Varios sectores con una operativa común

El foco inicial incluye candidatos como bazares, papelerías, regalos, artículos del hogar y accesorios. La entrada depende de la operativa y de que exista alguna base interpretable, no solo del nombre del sector ni de tener un catálogo o tickets detallados. La profundidad se decide por análisis.

Restauración, fabricación, perecederos, venta a peso y operaciones complejas quedan fuera del foco inicial. La descripción orienta el análisis, pero no amplía automáticamente las capacidades del producto. Los pilotos comprobarán qué análisis se reutilizan entre tiendas y dónde hace falta acotar más.

### 2.3. Personas que todavía no tienen archivos

El MVP más básico no tiene que ayudar a exportar información de otros programas, conectarse a sistemas externos ni transformar papel o fotografías en tablas.

Si alguien no tiene un archivo utilizable, se explica qué admite la versión actual y qué información necesita para empezar. El acompañamiento para obtener archivos y comenzar a registrar actividad queda en el roadmap.

No se presupone qué programas utilizan estos negocios. Habrá que investigarlo antes de elegir integraciones. Tampoco se exige al cliente una base de datos técnica ni una cuenta de infraestructura.

## 3. Decisiones acordadas

| Tema | Decisión |
|---|---|
| Segmento | Pequeños comercios de productos no perecederos con datos básicos o detallados aprovechables |
| Intención inicial | Recibir ayuda general, sin tener que formular una pregunta |
| Primer paso | Explicar a qué se dedica el negocio y cómo funciona |
| Datos iniciales | Subida manual de Excel y CSV de ventas en formatos compatibles |
| Interpretación | Mostrar qué se ha entendido antes de publicar conclusiones |
| Plan de análisis | Guía base y plan revisable según datos, contexto, hallazgos y herramientas |
| Preguntas | Formato mixto: opciones, campos breves y texto libre |
| Información incompleta | Continuar con un informe parcial cuando haya una base útil y fiable |
| Datos adicionales | Pedirlos con un beneficio concreto; si no se aportan, continuar con lo disponible |
| Apertura del informe | Primero hallazgos y explicación breve; después cifras y gráficos |
| Navegación | Resumen y secciones según los datos disponibles |
| Dashboard / Inicio | Página de regreso al negocio con hallazgos y gráficos de una revisión identificada, evidencia y acceso a conversar |
| PDF | Botón «Descargar como PDF», con la misma información sustantiva |
| Chat | Conversaciones persistentes del negocio desde Inicio o un hallazgo; pueden explicar, investigar o generar un informe |
| Evidencia | Mostrar de dónde salen las afirmaciones del informe y del chat |
| Regreso | Conversar o actualizar datos y generar otra revisión |
| Seguimiento propuesto | Guardar un hallazgo para revisar, con nota manual opcional; comparar al actualizar |
| Contexto guardado | Memoria versionada compartida entre onboarding, conversaciones, análisis y «Mi negocio», con ámbito y vigencia |
| Aprender contexto desde el chat | Incluido en 2.5: declaraciones claras con aviso/corrección; inferencias o contradicciones materiales requieren aclaración |
| Mi negocio | Ficha progresiva y editable, archivos/periodos y cambios de memoria |
| Datos enriquecidos | Exploraciones históricas adicionales si son verificables; módulos completos de margen/inventario en ampliaciones |
| Predicciones | Ampliación acotada de ventas/unidades, con evaluación e incertidumbre |
| Automatización | Posterior a validar la utilidad del recorrido manual |

## 4. Principios de experiencia

1. **Conducir el primer análisis.** No exigir que el dueño sepa preguntar a una IA.
2. **Entender el negocio antes de interpretar.** Utilizar su descripción para orientar las aclaraciones.
3. **Permitir corregir.** Las interpretaciones del sistema no son hechos confirmados por defecto.
4. **Preguntar lo que cambia el análisis.** No intentar conocer toda la empresa antes de ofrecer valor.
5. **Avanzar con información parcial.** Limitar los resultados afectados sin bloquear todo innecesariamente.
6. **Explicar antes de mostrar detalle.** Primero qué merece atención; después, cifras y comprobación.
7. **Distinguir hechos, hipótesis y propuestas.** No presentar una posible causa como demostrada.
8. **Recordar lo útil.** Evitar preguntas repetidas cuando el contexto sigue aplicando.
9. **Mantener coherencia.** Web, PDF y respuestas sobre el informe comparten cifras y definiciones.
10. **Hablar en términos del negocio.** No mostrar agentes internos, ontologías o técnicas de modelado.
11. **Hacer visible la vigencia.** Fecha de subida, periodo de datos y fecha de informe son cosas distintas.
12. **Proteger el alcance.** Completar el recorrido manual antes de añadir automatización o predicciones.
13. **Adaptar la investigación.** La guía base no obliga a producir el mismo informe ni cierra las preguntas posibles.
14. **Comprobar antes de publicar.** Una interpretación plausible o el acuerdo entre agentes no sustituye evidencia y cálculos contrastables.

## 5. Primera visita: recorrido detallado

**Explicar el negocio → subir archivos → evaluar información y preparar un plan → aclarar o aportar datos opcionales → ejecutar, comprobar y adaptar el análisis → explorar el informe.**

El recorrido puede volver a la evaluación cuando llega información nueva. PDF y conversación posterior completan la experiencia ampliada, después de la primera entrega.

### 5.1. Bienvenida y descripción del negocio

La entrada explica el beneficio y pide una descripción breve, antes de interpretar los datos.

Pregunta orientativa:

> ¿Qué ofrece tu negocio y cómo funciona en el día a día?

Ejemplo de ayuda:

> «Tengo una papelería. Vendemos material escolar y artículos de regalo, y registramos cada venta en la caja».

Se propone texto libre breve con ejemplos. El nombre puede recogerse junto a la descripción. No se exige un formulario exhaustivo sobre empleados, costes, horarios y objetivos.

El producto devuelve una interpretación corta y corregible. Saber que es una papelería orienta las preguntas, pero no permite asumir qué incluyen los importes ni cómo se registran descuentos, devoluciones o variantes de producto.

El mecanismo de registro e inicio de sesión queda pendiente. Debe permitir volver al mismo espacio sin una configuración empresarial compleja.

### 5.2. Subir la información existente

El usuario aporta uno o varios Excel o CSV y puede explicar brevemente qué contienen.

Se pide aportar los datos existentes dentro de los formatos y límites admitidos, sin exigir una plantilla universal ni «todos los datos de la empresa». Los totales permiten análisis agregado; los tickets y artículos permiten más profundidad. Si un archivo adicional puede habilitar una investigación pertinente y disponible, se explica el beneficio y se ofrece aportarlo. Si no se aporta, se continúa con lo aprovechable. No se solicitan datos para funciones inexistentes.

La pantalla muestra archivos recibidos, cuáles se pueden leer y cuáles necesitan corrección. Si uno falla, se conserva el resto del trabajo y se continúa con lo aprovechable.

No se promete relacionar automáticamente cualquier combinación de archivos.

### 5.3. Mostrar qué se ha entendido

Antes de las preguntas de detalle y del informe, el sistema devuelve una lectura inicial.

Ejemplo:

> Tenemos ventas de los últimos seis meses. Cada ticket ocupa varias filas, una por artículo. Necesitamos confirmar cómo aparecen las devoluciones antes de calcular las ventas netas.

Cuando sea relevante, explica:

- Qué hoja o tabla se utilizará.
- Qué representa cada fila.
- Qué significan los campos que afectan al análisis.
- Qué periodo parece cubrirse.
- Qué archivos pueden relacionarse y cuáles siguen separados.
- Qué parece posible analizar y qué necesita aclaración.

No obliga a revisar todas las columnas manualmente. Sí pide confirmar ambigüedades que puedan cambiar los resultados.

### 5.4. Preguntas adaptadas

Las preguntas surgen de combinar la descripción del negocio con los archivos.

El sistema prepara un plan provisional: qué puede estudiar, qué requiere aclaración y qué información opcional permitiría profundizar. Lo comunica brevemente cuando ayude al usuario; no requiere aprobar un plan técnico ni enseña razonamiento interno. Las preguntas pueden ajustar ese plan y también surgir durante la ejecución si aparece una ambigüedad nueva que afecta al resultado.

Ejemplos:

- «¿Cada fila representa un artículo del ticket o una compra completa?»
- «¿Estos importes incluyen impuestos?»
- «¿Las devoluciones aparecen como cantidades negativas o en otro archivo?»
- «¿Cierras los lunes o faltan registros de esos días?»
- «Con estos totales puedo analizar la evolución. ¿Tienes detalle por artículo para investigar qué productos explican la diferencia? Puedes continuar sin él».

El formato mezcla opciones, números, fechas y texto libre según lo que resulte más fácil. Debe permitir añadir matices cuando una opción no describa la situación.

Como propuesta de diseño, se usan tandas pequeñas, por ejemplo hasta tres preguntas prioritarias. No es una cuota obligatoria; la cantidad y distribución se comprobarán con usuarios.

### 5.5. Cierre del onboarding

El onboarding termina cuando hay una base suficiente para el análisis disponible, no cuando se ha recogido toda la información imaginable.

Si falta información útil, se permite continuar y se explica qué resultados serán limitados. El dueño no tiene que esperar días para conseguir datos adicionales si ya puede obtener algo útil.

Durante la generación se muestra un estado comprensible, sin pasos internos de agentes ni tiempos garantizados sin comprobar. Si falla, se conservan archivos aceptados y respuestas para reintentar.

### 5.6. Primer resultado

El usuario llega al resumen del análisis: hallazgos destacados, explicación breve y después las cifras y gráficos que los sostienen.

Desde ahí puede explorar secciones, comprobar fuentes, descargar el PDF, preguntar al agente y consultar qué datos mejorarían una próxima revisión. Se propone una acción explícita «Guardar para revisar» sobre un hallazgo, sin necesidad de iniciar una conversación.

No necesita iniciar el chat para recibir valor.

## 6. Preguntas y datos incompletos

### 6.1. Prioridad de las preguntas

| Tipo | Tratamiento |
|---|---|
| Imprescindible para interpretar | Preguntar antes de publicar el resultado afectado; si no se resuelve, limitarlo u omitirlo |
| Útil para profundizar | Explicar el beneficio y permitir continuar sin responder |
| Archivo adicional para profundizar | Explicar qué análisis habilita; aceptar que no exista o no se quiera compartir y ajustar el plan |
| Para revisiones futuras | Plantearla después del resultado disponible, sin alargar el onboarding |

«No lo sé», «No lo tengo» y «Ahora no» son respuestas válidas. Si ninguna parte puede interpretarse con seguridad, se explica el bloqueo concreto.

La negativa a aportar información opcional queda registrada y no se vuelve a pedir sin una razón nueva. Recibir un archivo adicional obliga a revisar su relación con lo existente para no sumar dos veces la misma actividad.

Cada pregunta debe justificar su utilidad. Por ejemplo:

> **¿Cierras los lunes?** Hay cuatro lunes sin registros. Saberlo ayuda a distinguir cierres de posibles datos pendientes.

No se recoge información sobre empleados, horarios o costes simplemente por completar un perfil.

### 6.2. Respuestas persistentes y corregibles

La descripción y las aclaraciones se guardan como información organizada y consultable del negocio. No quedan únicamente en una lista de preguntas y respuestas. En la entrega 2.5 esta memoria se comparte entre todas sus conversaciones y análisis; cada ejecución selecciona la parte aplicable y registra sus versiones.

El usuario puede corregirlas desde «Mi negocio», una ficha que reúne información del negocio, prioridades, definiciones, datos/archivos y cambios. Se completa progresivamente, sin exigir un formulario exhaustivo. Permite consultar el origen y estado de una información, corregirla o retirarla de la memoria activa. Cuando importa para el análisis histórico, se aclara desde cuándo aplica un cambio. El horario de hoy no se aplica automáticamente a todo el pasado.

Las preguntas pendientes deben seguir teniendo una utilidad clara. Se pueden posponer y no deben reaparecer insistentemente sin una razón nueva.

### 6.3. Resultados posibles

- **Información suficiente:** hallazgos y próximos pasos respaldados.
- **Información parcial:** resultados útiles, límites visibles y datos adicionales sugeridos.
- **Información insuficiente:** diagnóstico breve y aclaración o formato necesario para continuar.

No se fabrica un informe largo para aparentar valor cuando no existe una base útil.

## 7. Informe interactivo: resumen y secciones

### 7.1. Inicio del negocio e informes individuales

**Decisión del 23 de septiembre de 2026:** Inicio pasa a ser la página cotidiana del negocio. Presenta un resumen, pocos hallazgos y gráficos respaldados por una revisión identificada; permite explorar detalle, evidencia y preguntar. Los informes individuales se conservan en su biblioteca con tema, periodo, fuentes y estado. Inicio no genera una interpretación paralela ni combina automáticamente métricas de revisiones incompatibles.

La barra lateral contiene **Inicio, Informes, Mi negocio, Nueva conversación y chats recientes**. En Inicio hay un prompt inferior visible y preguntas sugeridas pertinentes. Enviar una pregunta crea un chat del mismo negocio; «Preguntar sobre esto» conserva el contexto del hallazgo. Dentro de cada informe se mantiene la navegación por resumen y secciones según los datos disponibles. Los detalles visuales se comprobarán en escritorio y móvil.

El Inicio de 2.5 permite explorar resultados existentes y seleccionar revisiones. Una interacción que requiere cifras nuevas inicia una investigación comprobada. No incluye un editor libre de gráficos ni filtros universales. Los asuntos guardados para seguimiento continúan en el roadmap.

### 7.2. Identificación y acciones

El usuario debe encontrar fácilmente:

- Negocio y periodo analizado.
- Fecha de generación.
- Cobertura parcial o dudas relevantes.
- Acciones para preguntar, guardar un asunto para revisar, actualizar datos y descargar el PDF.

Un archivo subido hoy puede contener datos del mes pasado. Esa diferencia debe quedar clara.

### 7.3. Resumen: primero los hallazgos

La apertura explica qué está pasando, qué merece atención y qué conviene revisar cuando exista base. Se propone destacar hasta tres prioridades, sin rellenar tarjetas artificialmente. Magnitud, cobertura y utilidad de la comprobación pesan más que mostrar muchos porcentajes llamativos.

Ejemplo ilustrativo:

> Las ventas registradas han bajado y hay menos tickets. El importe medio por ticket apenas ha cambiado. Esta categoría concentra la mayor parte de la caída.

Solo se mostraría si el tipo de registros y la comparación permiten sostenerlo. La cifra y el cálculo se pueden consultar.

Los indicadores y gráficos acompañan la explicación. No se empieza por una cuadrícula de números sin contexto ni por un chat vacío.

### 7.4. Secciones adaptadas a la información

Las secciones se derivan del plan ejecutado y sus resultados verificados. La guía contempla evolución, productos si los hay, devoluciones y descuentos cuando sean interpretables; se pueden añadir otras investigaciones históricas pertinentes y comprobables. Con datos agregados no aparecen secciones vacías de productos o tickets. El seguimiento corresponde al producto ampliado; previsiones y módulos especializados siguen su roadmap.

Cada sección ofrece:

1. Explicación de lo más relevante.
2. Métricas y gráficos útiles.
3. Hallazgos ampliables.
4. Limitaciones y próximos pasos respaldados.

Si solo hay ventas, no se rellena una sección de rentabilidad con suposiciones. Se explica en un lugar pertinente qué falta.

No se necesita personalización libre de paneles, widgets ni múltiples dashboards sectoriales para el MVP ni para la entrega 2.5.

### 7.5. Detalle y comprobación

Desde un hallazgo se puede consultar:

- Qué se observa y en qué periodo.
- Qué cifras, archivos y registros relevantes lo respaldan.
- Cómo se calculó, con lenguaje comprensible.
- Qué filtros, exclusiones, aclaraciones o supuestos influyeron.
- Qué limitación afecta a la interpretación.
- Una opción para preguntar sobre ese hallazgo.

El detalle se muestra a petición para no sobrecargar la lectura inicial.

### 7.6. Hallazgos y próximos pasos

El informe combina observaciones, asuntos a investigar y acciones cuando haya evidencia.

Debe distinguir:

- **Observación:** lo que muestran los registros.
- **Hipótesis:** explicación que todavía requiere comprobación.
- **Próximo paso:** qué revisar, aclarar o hacer a partir de lo disponible.

La guía base contempla cambios de actividad, contribuciones, tickets, devoluciones y descuentos cuando los datos lo permiten. El sistema puede elegir investigaciones adicionales con sustento, herramientas y comprobaciones, o abandonar otras que no aportan valor. No se fuerza una cantidad de hallazgos, acciones ni estimaciones de ahorro. Una contribución a una caída no demuestra su causa ni una pérdida recuperable. Los límites de ejecución impiden una investigación indefinida.

### 7.7. Guardar para revisar: propuesta acotada

El dueño puede guardar un hallazgo desde el informe y añadir una nota opcional sobre qué quiere comprobar. Si declara haber hecho un cambio, puede indicar su fecha. El hallazgo conserva su revisión de origen.

Al aportar datos nuevos, el sistema recupera el asunto y compara la métrica pertinente cuando sea válido. Separa el cambio observado de las causas posibles. No atribuye automáticamente una mejora a la acción declarada.

Esta propuesta no introduce recordatorios, notificaciones, ejecución externa ni memoria automática del chat. Si no hay datos suficientes, el asunto puede seguir pendiente sin producir una conclusión ficticia.

## 8. Descargar como PDF

El informe incluye un botón visible: **«Descargar como PDF»**.

Contiene la misma información sustantiva de la revisión web: resumen, secciones, métricas, gráficos relevantes, hallazgos, limitaciones y próximos pasos. No es una segunda interpretación generada por separado.

La presentación se adapta a lectura continua y páginas estáticas. El lector puede entender las conclusiones y su sustento sin depender de interacciones. Esto no obliga a adjuntar todos los registros originales.

El documento identifica negocio, periodo y fecha. Descargar una revisión antigua no la convierte en un análisis actualizado.

La acción descarga el documento; no requiere envío por correo, publicación ni compartición automática. El PDF forma parte del producto inicial acordado.

## 9. Chat después del análisis

### 9.1. Papel y acceso

El chat se implementará en la entrega 2.5 y comparte memoria del negocio entre conversaciones: contexto aplicable, fuentes seleccionadas, aclaraciones, métricas y hallazgos vigentes. Cada conversación tiene su propio historial; compartir memoria no implica incluir todos los mensajes de todos los chats en cada respuesta.

El usuario puede hacer una pregunta libre o iniciar una consulta desde un hallazgo. No debe volver a explicar su empresa ni copiar lo ya aportado.

Se abre desde el prompt de Inicio, «Nueva conversación», un chat reciente o «Preguntar sobre esto» en un hallazgo. Las preguntas sugeridas reflejan las fuentes y capacidades disponibles. Una conversación puede resolver una duda breve, iniciar una investigación o generar un informe independiente; no exige describir de nuevo el negocio ni aportar otro archivo.

### 9.2. Amplitud acordada

Puede ayudar a:

- Explicar una cifra o conclusión y mostrar su origen.
- Responder preguntas concretas sobre los datos dentro de las capacidades admitidas.
- Explorar posibles decisiones y qué conviene comprobar antes de tomarlas.
- Explicar qué información falta para responder con más fundamento.

Ejemplos:

> «¿Qué productos explican esta diferencia?»  
> «¿De dónde has sacado esa cifra?»  
> «¿Qué debería revisar antes de subir precios?»

La última pregunta cabe en la intención del producto. No implica prometer una predicción numérica del efecto de subir precios ni ejecutar el cambio.

En la futura conversación posterior, filtros, agregaciones y desgloses son operaciones base, no una lista cerrada de preguntas. El agente puede componer investigaciones pertinentes que sus herramientas permitan ejecutar y comprobar. Si no dispone de medios fiables o de información suficiente, explica el límite. Este criterio de autonomía se aplica desde el MVP al sistema que prepara el informe.

### 9.3. Evidencia y límites

Las respuestas basadas en archivos permiten consultar su fuente, cálculo o resultado correspondiente. Las cifras proceden de operaciones reproducibles: un enlace genérico al archivo no basta si no respalda la afirmación. Si usan contexto declarado por el dueño, lo distinguen.

Una orientación general no se presenta como un hecho demostrado sobre ese negocio. Si faltan datos, el chat explica qué puede contestar y qué no, sin inventar cifras.

Debe indicar la revisión o periodo utilizado cuando afecte a la respuesta. Hablar hoy con el agente no significa que tenga datos de hoy.

La conversación no reescribe silenciosamente el informe. Los análisis adicionales se distinguen de la revisión publicada; cuando el usuario pide un informe, se guarda una revisión independiente vinculada a la conversación, con evidencia y comprobaciones. Las respuestas breves también deben sostener sus afirmaciones; el chat no evita la revisión de cálculos o conclusiones nuevas.

### 9.4. Actualizar conocimiento desde el chat: entrega 2.5

El chat, el onboarding y «Mi negocio» alimentan la misma memoria versionada. Se guardan hechos útiles con fuente, ámbito, estado y fecha de aplicación cuando corresponda. Una declaración clara de bajo impacto puede incorporarse con un aviso visible y opción de corregir/retirar; una edición explícita de la ficha no requiere volver a confirmar lo mismo. Solo se anuncia el guardado cuando ha terminado correctamente.

Ejemplo:

> «Desde septiembre cerramos los lunes».  
> «He guardado que cerráis los lunes desde septiembre». La ficha permite corregir la fecha o retirar el dato.

Si falta una fecha relevante, hay una contradicción material o la interpretación inferida cambia cálculos, se pide aclaración antes de aplicarla. «Estamos pensando en cerrar los lunes» es una posibilidad, no un horario confirmado. «Este archivo incluye impuestos» se limita a esa fuente hasta comprobar otro ámbito.

Las correcciones se propagan a las próximas respuestas de todos los chats y marcan los resultados afectados para revisión. El historial conserva las versiones anteriores y su estado, sin servir conclusiones invalidadas como evidencia vigente. Retirar un hecho evita su reutilización en memoria, aunque borrar el mensaje o el archivo original sea una acción diferente. Mientras esta función esté pendiente de implementación, la web no debe afirmar que ya recuerda cambios entre conversaciones.

## 10. Regreso y actualización

### 10.1. Dos entradas igualmente importantes

El dueño puede volver a preguntar sin aportar datos nuevos, o actualizar la información y obtener otra revisión.

Al volver se abre **Inicio del negocio**, con el resumen disponible, su periodo, el prompt y acceso a los chats, informes y «Mi negocio». Se puede preguntar sin datos nuevos o actualizar archivos desde «Mi negocio» y generar otra revisión. Si hay varias revisiones, la seleccionada queda identificada; si no hay una publicable, se explica el estado y el siguiente paso.

No se repite el onboarding para conversar ni se exige un archivo nuevo para usar el chat.

### 10.2. Actualización manual

1. Subir archivos actualizados o del nuevo periodo.
2. Revisar qué información se usará y qué periodo cubre.
3. Aclarar únicamente dudas nuevas.
4. Generar una nueva revisión.
5. Explorar los hallazgos y los cambios cuando sea válida la comparación.
6. Recuperar asuntos guardados y revisar su evolución si hay evidencia suficiente.

Se reutilizan formatos conocidos y contexto confirmado. Si cambia el archivo, se pregunta por las diferencias que afectan a su interpretación.

### 10.3. Archivos repetidos o solapados

Subir otra vez un conjunto no debe duplicar operaciones. Si los archivos se solapan, el usuario entiende cuál se usará y si sustituye información.

No se promete una fusión universal. Cuando haga falta elegir una fuente o aportar un conjunto consolidado, se explica.

La regla de incorporación o sustitución se definirá según los formatos admitidos. No se impone en esta versión un Excel maestro generado por la aplicación. Cualquier sustitución que reduzca información de forma relevante debe advertirse antes de aplicarla.

### 10.4. Coherencia entre revisiones

Datos recién subidos e informe generado son estados diferentes. La interfaz no presenta un informe anterior como si incorporara automáticamente la última subida.

Cada revisión conserva el periodo, fuentes y supuestos con los que se elaboró. Editar el perfil actual no cambia el pasado. La consulta del historial puede ser sencilla y queda por concretar.

**Criterio de experiencia:** actualizar requiere menos explicación del negocio que la primera visita.

## 11. Interpretación guardada de los datos

La idea de extraer una ontología se incorpora con un alcance pequeño: **guardar el significado necesario para analizar correctamente y evitar preguntas repetidas**.

Para el usuario se presenta como información del negocio e interpretación de sus datos. No necesita conocer el término ontología ni editar un modelo técnico.

| Qué conservar | Ejemplo |
|---|---|
| Descripción | Papelería que revende material escolar y regalos |
| Unidad de registro | Una fila es un artículo dentro de un ticket |
| Significado de columnas | El importe incluye impuestos |
| Definiciones | Cómo se descuentan devoluciones y se excluyen tickets anulados |
| Relaciones validadas | Una referencia identifica el mismo pedido en dos tablas |
| Contexto declarado | Horario habitual y fecha desde la que aplica |
| Dudas | No sabemos si están incluidos todos los gastos |
| Nivel de detalle | Totales diarios sin identificadores de ticket; no permite calcular cesta |
| Información no aportada | El dueño no dispone de detalle por producto; no volver a pedirlo sin motivo nuevo |
| Plan y comprobaciones | Qué se investigó, qué se reformuló y qué resultados quedaron verificados |

Se distingue lo registrado, lo declarado, lo estimado y lo pendiente de confirmar. No se convierten automáticamente inferencias en hechos confirmados.

Las definiciones conservan procedencia y aplicación temporal cuando son necesarias. Una interpretación de un archivo no se extiende a otro incompatible sin comprobarla.

**Regla de alcance:** conservar un concepto si ayuda a interpretar un dato, calcular un análisis admitido o evitar repetir una pregunta.

Quedan fuera la reconstrucción de todos los procesos de la empresa, la exportación de una ontología universal y la operación de agentes externos sobre sus sistemas. No se decide aquí la tecnología para guardar ese conocimiento.

## 12. Límites de interpretación visibles

Se mantienen los siguientes criterios de confianza, independientemente de la implementación:

- Ausencia de registros no equivale a cero.
- Totales diarios no permiten contar tickets individuales.
- Varias líneas de un ticket no son varias compras; tickets tampoco equivale a personas.
- Ingresos no equivalen a beneficio si faltan costes.
- Desglosar una caída por categoría no demuestra su causa.
- Cero ventas no demuestra que hubiera stock disponible ni baja demanda.
- El coste actual de un artículo no acredita el coste de todas sus ventas históricas.
- Horarios declarados no sustituyen turnos reales ni disponibilidad.
- Número de empleados no proporciona horas trabajadas ni costes.
- Estimaciones de memoria no son registros comprobados.
- Periodos incompletos no se comparan con completos sin explicar cobertura.
- Negativos, subtotales y posibles duplicados se interpretan antes de eliminarlos o sumarlos.
- Monedas y unidades diferentes no se agregan como equivalentes.

El documento de servicios orienta las investigaciones y sus requisitos de datos. La planificación técnica definirá herramientas, comprobaciones y escenarios con distinta riqueza de información. La IA puede elegir y componer análisis, pero debe explicitar sus definiciones y dejar operaciones reproducibles; no cambia el significado de una métrica entre respuestas sin indicarlo.

## 13. Ayudar a mejorar los datos

### 13.1. En el MVP: orientación

Cuando falta información relevante, se explica qué dato ayudaría, para qué serviría y qué conclusión todavía no puede obtenerse.

Ejemplo:

> Con estos datos podemos analizar la evolución de ventas. El detalle por artículo permitiría investigar qué productos contribuyen al cambio. Si no lo tienes, seguimos con esta información.

Se proponen mejoras concretas y proporcionadas, no una lista de todo lo que falta para tener datos perfectos. No se pide información personal innecesaria para el análisis disponible.

### 13.2. Después: facilitar el registro

Se contempla ofrecer plantillas de Excel sencillas y ayudar a mantener datos que antes no se registraban, aprovechando formatos existentes cuando sea posible.

Esta ayuda **no es un requisito del MVP más básico acordado ahora**. La prioridad es crear una buena experiencia con archivos ya disponibles.

Cuando se añada, cada campo tendrá un beneficio claro, instrucciones comprensibles y relación con una capacidad real. No se inventarán valores para completar huecos ni se mezclarán ejemplos con registros reales.

No se pretende convertir esta extensión en un sistema completo de caja, agenda, inventario o contabilidad.

## 14. Estados y situaciones que resolver

| Situación | Respuesta del producto |
|---|---|
| No hay archivos | Explicar qué admite el MVP sin prometer funciones futuras |
| Un archivo falla | Identificarlo y conservar el resto del trabajo |
| Una tabla o fecha es ambigua | Solicitar la aclaración necesaria antes de usarla |
| Parte de los datos no sirve | Analizar lo válido y explicar exclusiones relevantes |
| El usuario no sabe responder | Continuar con resultados fiables y límites visibles |
| Respuesta y archivo se contradicen | Pedir aclaración |
| Los datos adicionales tardarán días | Entregar lo útil ahora y explicar cómo completarlo |
| No hay base útil | Dar un diagnóstico breve y un siguiente paso |
| El análisis falla | Permitir reintentar sin repetir información aceptada |
| Se repite un archivo | Evitar duplicación y novedades ficticias |
| Hay solapamientos o sustituciones | Explicar qué datos se usarán antes de aplicarlos |
| Hay subida pendiente de analizar | Distinguirla del informe anterior |
| El chat no puede responder | Explicar el límite y qué permitiría avanzar |
| Se pregunta sobre actualidad con datos antiguos | Hacer visible el periodo disponible |
| Pide una función todavía no implementada | Explicar que no está disponible; no pedir datos como si fueran el único impedimento |
| No hay ningún cambio relevante | Entregar una revisión breve sin fabricar alertas |
| Quiere revisar una acción anterior | Mostrar evolución y límites de comparación; no inventar causalidad |
| Aporta datos agregados aprovechables | Preparar un análisis a ese nivel; no exigir tickets ni columnas ajenas a la pregunta |
| No aporta información opcional | Continuar y conservar el límite sin insistir |
| Una exploración adicional no supera comprobaciones | Corregir dentro de límites o retirar el resultado afectado |
| Se alcanza el límite de investigación | Presentar lo verificado y explicar lo pendiente, sin fingir cobertura completa |
| Falla la descarga del PDF | Permitir reintentar conservando el informe web |

Los errores necesitan un siguiente paso comprensible. «No se puede procesar» sin explicación no basta.

## 15. Ejemplos completos de experiencia

### 15.1. Papelería con ventas por artículo

La dueña sube un CSV donde cada ticket ocupa varias filas. El sistema confirma impuestos, descuentos, devoluciones y cobertura. Cuenta compras mediante el identificador del ticket.

El resumen destaca las categorías que contribuyen a un cambio de ventas. La dueña abre la evidencia y pregunta si el resultado se mantiene sin devoluciones. El chat muestra el nuevo filtro y cálculo como análisis adicional. Puede descargar el PDF de la revisión publicada.

### 15.2. Bazar con una caída concentrada en pocos productos

El informe muestra una caída observada en varios artículos y su peso en el total. Ante «¿Se han dejado de vender porque ya no gustan?», el agente explica que faltan pruebas sobre disponibilidad y demanda.

El dueño guarda el asunto para revisar existencias. Puede anotar que comprobó un agotamiento y su fecha; la nota es contexto declarado. Al cargar el siguiente periodo se compara la evolución sin presentar automáticamente una recuperación como efecto causal de su intervención.

### 15.3. Tienda de regalos con un archivo incompleto

La dueña sube datos de una semana que parece tener menos ventas, pero faltan días de cobertura. El sistema destaca primero esa limitación y evita una alerta comercial engañosa.

Si aporta solo totales diarios, recibe un informe adaptado a ese nivel. El sistema ofrece profundizar con detalle por artículo y continúa si la dueña dice que no lo tiene. No considera ese caso un incumplimiento de una plantilla de entrada. Si llegan datos más ricos, revisa el plan y explora lo que pueda ejecutar y comprobar; si una capacidad aún no existe, lo explica sin prometerla.

## 16. Tono y control del usuario

La interfaz habla con claridad a una persona que conoce su negocio y tiene poco tiempo.

| Evitar | Preferir |
|---|---|
| «Ejecuta el agente analista» | «Preparar análisis» |
| «Completa tu perfil al 100 %» | «Confirmar el horario ayuda a entender estos días sin registros» |
| «Tu negocio funciona mal» | «Los ingresos registrados han bajado en este periodo» |
| «Optimiza tus recursos» | Una comprobación o próximo paso concreto |
| «Es el producto más rentable» sin costes | «Aporta más ventas; para comparar margen necesitamos costes compatibles y esa capacidad disponible» |

La confianza se apoya en fuentes y cuentas verificables. No se necesita mostrar razonamiento interno del modelo ni porcentajes de confianza sin significado defendible.

El usuario debe poder saber qué archivos se utilizan, corregir contexto, descargar el informe y entender qué se conserva. La política de conservación y borrado se definirá antes de trabajar con datos reales y será coherente con la continuidad prometida. Retirar una fuente no debe dejar una evidencia inaccesible presentada como disponible.

No se necesitan enlaces públicos, envío automático a terceros ni colaboración entre empresas en el primer recorrido.

## 17. Alcance del producto inicial ampliado

Este apartado conserva la visión ampliada. Para construir, aplicar [MVP y primera entrega](<Decision Room - MVP.md>) y el plan: chat posterior, memoria compartida e Inicio se adelantan a 2.5; PDF y seguimiento permanecen aplazados.

### 17.1. Núcleo acordado

1. Espacio persistente sencillo del negocio.
2. Descripción inicial antes de interpretar archivos.
3. Subida manual de Excel y CSV existentes.
4. Interpretación breve y corregible.
5. Preguntas adaptadas, mixtas y con respuestas reutilizables.
6. Informe suficiente o parcial según la evidencia.
7. Resumen de hallazgos y secciones pertinentes.
8. Cifras, gráficos, fuentes y límites consultables.
9. Hallazgos, asuntos a investigar y próximos pasos cuando exista base.
10. PDF del mismo análisis.
11. Chat contextual para explicar y explorar decisiones.
12. Regreso para conversar o actualizar manualmente los datos.
13. Estados claros de errores, datos insuficientes y revisiones pendientes.
14. Propuesta nueva: guardar explícitamente un asunto para revisar, con nota opcional y recuperación al actualizar.
15. Memoria compartida con procedencia y vigencia, mantenida desde onboarding, conversaciones y «Mi negocio»; prioridad de entrega 2.5.

El desarrollo puede dividirse en entregas. Ese orden no convierte el chat o el PDF en funciones descartadas del producto acordado.

La guía de investigación está definida en Servicios y diferenciación y el MVP: comprender la actividad, sus cambios y lo que merece revisión. No es un catálogo cerrado ni exige detalle por artículo. Los formatos físicos y herramientas concretas siguen pendientes. Se validará con comercios y archivos de distintos niveles de detalle, incluyendo datos agregados y rechazo a aportar más información.

### 17.2. Fuera del núcleo inicial

- Ayuda detallada para exportar datos e integraciones externas.
- Ingesta universal de papel, fotos, documentos, correo o audio.
- Plantillas generadas y herramientas para comenzar a registrar actividad.
- Sincronización automática con archivos o servicios.
- Informes programados, avisos y envíos automáticos.
- Módulos completos de margen e inventario: ampliaciones especializadas. No excluye una exploración histórica adicional si hay información y herramientas verificables.
- Predicciones y simulaciones cuantitativas abiertas.
- Cambios autónomos en precios, turnos o compras.
- Gestión completa, varias sedes, equipos y paneles personalizables.
- Ontologías empresariales completas o interacción con agentes externos.

Conversar sobre una decisión sí cabe en el chat inicial. Predecir numéricamente sus consecuencias o ejecutarla no forma parte del compromiso inicial.

## 18. Roadmap de experiencia

La prioridad inmediata es completar memoria compartida y experiencia cotidiana en la entrega 2.5. Las ampliaciones siguientes quedan registradas sin fechas: capacidades especializadas de margen/inventario, previsiones condicionadas a evaluación y automatización tras demostrar recurrencia. Esto no impide aprovechar antes datos enriquecidos para una exploración histórica que las herramientas ya permitan ejecutar y comprobar. La ayuda de exportación puede adelantarse si los pilotos muestran que es el principal obstáculo.

### 18.1. Ayudar a obtener y registrar datos

- Investigar qué programas utilizan los primeros negocios.
- Guiar la exportación desde herramientas concretas.
- Ofrecer plantillas de Excel fáciles de rellenar.
- Ayudar a registrar información que hoy no se guarda.

El objetivo es ampliar el acceso progresivamente. Las primeras guías y conexiones se elegirán según los formatos y programas que realmente utilicen las tiendas piloto, comprobando permisos y requisitos de exportación.

### 18.2. Completar contexto desde el chat

Adelantado a la entrega 2.5, según la sección 9.4. Detectar información útil y mantenerla con procedencia, ámbito, vigencia, correcciones y retirada. Pedir aclaración cuando sea material, sin repetir confirmaciones sobre ediciones explícitas. Las conversaciones mejoran las próximas revisiones sin cambiar silenciosamente el pasado.

### 18.3. Automatizar continuidad, en etapas posteriores

- Recibir datos automáticamente de fuentes compatibles tras su configuración.
- Preparar informes periódicos, por ejemplo semanales.
- Avisar cuando haya una revisión o cambio relevante, con preferencias por definir.

La llegada automática de datos y la programación de informes son funciones distintas. Habrá que diseñar qué ocurre si no llega información nueva, está incompleta o cambia el formato.

Se consideran de las últimas etapas planteadas, después de comprobar que el recorrido manual aporta valor.

### 18.4. Predicciones y machine learning

Existe interés en complementar el análisis histórico con capacidades para anticipar aspectos del negocio.

La primera candidata es una previsión acotada de ventas o unidades para las próximas semanas, al nivel que los datos permitan. Debe superar una evaluación temporal frente a referencias sencillas y mostrar incertidumbre y error histórico. No todos los negocios ni productos tendrán base suficiente.

La UX separará histórico, previsión y escenario hipotético. Una previsión de ventas no implica una cantidad de compra recomendada: esa ampliación requiere existencias, entradas y plazos, entre otros datos. Los criterios funcionales están en Servicios y diferenciación; modelos e implementación siguen pendientes. Esta línea no bloquea el MVP.

### 18.5. Margen e inventario: primera ampliación funcional

Añadir tablas de costes y existencias en formatos concretos con relaciones confirmadas. Mostrar margen bruto, baja salida y cobertura únicamente con datos suficientes y definiciones compatibles. El coste actual no se presenta como histórico real; el margen bruto no se llama beneficio neto.

El piloto determinará si esta ampliación es necesaria para que el producto aporte valor comercial suficiente. La facilidad de producir un informe de ventas no garantiza que el propietario quiera pagarlo.

### 18.6. Organización multiagente del producto final

**Decisión del 21 de septiembre de 2026:** el producto completo tendrá como organización objetivo un agente de negocio, un agente analítico y un revisor con responsabilidades separadas. Esta decisión define una evolución posterior al MVP; no afirma que esté construida ni que su ventaja se haya demostrado. El MVP mantiene un agente principal que planifica y ejecuta, más un revisor separado.

El objetivo de esta separación es combinar una investigación orientada a las necesidades del propietario con profundidad analítica y conclusiones comprobables. El cliente interactúa con un único producto: explica su negocio, responde las aclaraciones pertinentes y recibe resultados; no tiene que dirigir a los agentes.

| Rol | Responsabilidad | Entrega a los demás |
|---|---|---|
| Agente de negocio | Mantener el objetivo del caso, entender prioridades y restricciones del cliente, proponer y priorizar investigaciones, coordinar aclaraciones y preparar la explicación final | Preguntas de investigación con su utilidad, contexto, definiciones y criterios de respuesta; contenido candidato del informe o dashboard |
| Agente analítico | Inspeccionar datos y relaciones, evaluar si una pregunta es abordable, elegir métodos, generar y ejecutar cálculos con las herramientas autorizadas y examinar sus resultados | Resultados con fuentes, operaciones, comprobaciones y limitaciones; necesidades de aclaración y nuevas líneas de investigación justificadas |
| Revisor | Examinar resultados, afirmaciones, recomendaciones y redacción final frente a sus evidencias y al contexto del negocio | Observaciones concretas y solicitudes de corrección o comprobación; valoración explícita de lo que puede sostenerse |

El agente de negocio representa las prioridades declaradas del propietario y comunica también hallazgos que contradigan sus expectativas. El agente analítico puede cuestionar una premisa, indicar que los datos no permiten responder o proponer una investigación adicional. La especialización consiste en responsabilidades, contexto y herramientas; no presupone que cada rol requiera un modelo o proveedor distinto.

**Ciclo de investigación:** negocio plantea una pregunta → analítica investiga y devuelve evidencia → negocio examina su relevancia y puede pedir una ampliación o reformular la pregunta → revisión de los resultados y del contenido propuesto → corrección, publicación de lo comprobado o cierre con límites explícitos. Una observación del revisor puede requerir un nuevo cálculo o una corrección de la explicación. Los cambios materiales vuelven a comprobarse.

Por ejemplo, ante «vendo más unidades pero ingreso menos», negocio pide separar los efectos que permitan los datos. Analítica podría observar una mayor proporción de artículos baratos y señalar que falta examinar descuentos. Negocio solicita ese desglose si aporta valor; analítica devuelve el cálculo o la limitación correspondiente. El informe distingue los efectos cuantificados de las explicaciones todavía hipotéticas. Es un ejemplo de comportamiento esperado, no un resultado ya obtenido.

**Estado y entregas compartidas:** cada petición registra la pregunta, su utilidad, las fuentes y versiones autorizadas, el periodo, las definiciones, las dependencias y las comprobaciones esperadas. Cada respuesta conserva los resultados y su procedencia, las operaciones ejecutadas, los supuestos y lo que sigue sin resolver. Las interpretaciones distinguen observado, inferido, confirmado y sin resolver. Las aclaraciones del dueño se guardan una vez y se aplican a las investigaciones dependientes; una respuesta o archivo nuevo puede invalidar resultados anteriores. Los agentes reciben el contexto necesario mediante referencias y herramientas, sin depender únicamente de su conversación entre sí.

**Control y finalización:** el controlador de la aplicación conserva el estado autorizado, limita acceso por negocio y revisión, aplica presupuestos de tiempo, coste, llamadas y correcciones, y gestiona pausas, reintentos y operaciones repetidas. Los agentes proponen cambios; el controlador exige las comprobaciones antes de publicar. El acuerdo entre agentes no demuestra exactitud numérica ni autoriza saltarse una validación. El trabajo termina cuando las preguntas prioritarias abordables están resueltas, no queda una ampliación justificada dentro del presupuesto o se alcanza un límite. Si falta una aclaración esencial, se guarda y pausa la investigación afectada mientras las independientes pueden continuar; una respuesta permite reanudarla sin repetir lo ya resuelto. Se conserva y presenta únicamente lo respaldado, con lo pendiente identificado.

**Informe y dashboard:** negocio propone la selección de hallazgos, explicaciones, indicadores y visualizaciones; analítica aporta los datos calculados y trazables; el revisor examina el contenido final. La aplicación construye la presentación con componentes y estilo consistentes. Las interacciones del dashboard que requieran nuevos cálculos pasan por el mismo proceso de comprobación. Esta organización no requiere inicialmente otro agente dedicado a generar interfaces.

**Transición desde el MVP:** mantener separables las responsabilidades de negocio y analítica dentro del agente principal previsto para el MVP, con un plan y resultados estructurados. Posteriormente, implementar los roles separados y compararlos con la arquitectura del MVP sobre los mismos casos: utilidad, exactitud, preguntas al cliente, recuperación, tiempo y coste. Esa comparación determinará cómo desplegar la evolución; especialistas adicionales solo se incorporarán ante una necesidad y mejora comprobables. El reparto objetivo queda acordado; modelos, contratos técnicos detallados, límites numéricos y rendimiento quedan por implementar y evaluar.

## 19. Criterios de aceptación de la experiencia

| Comprobación | Resultado esperado |
|---|---|
| El dueño no sabe qué preguntar | Obtiene un análisis sin formular una consulta |
| Describe su negocio | Ese contexto orienta interpretación y preguntas |
| Una columna es ambigua | Puede aclararla antes de que afecte al resultado |
| No sabe una respuesta | Continúa con la parte fiable y entiende el límite |
| Abre el informe | Ve primero hallazgos y explicación |
| Quiere profundizar | Encuentra secciones, cifras y gráficos pertinentes |
| Comprueba una afirmación | Accede a cálculo, origen y supuestos |
| Descarga el PDF | Obtiene el mismo análisis y periodo |
| Pregunta por un hallazgo | El chat conserva contexto y muestra su sustento |
| Explora una decisión | Se distinguen hechos, hipótesis y datos faltantes |
| Guarda un asunto para revisar | Se conserva su revisión de origen y la nota declarada |
| Actualiza un asunto guardado | Se compara lo compatible sin atribuir causalidad automáticamente |
| Pide una capacidad posterior | Se distingue función no disponible de información faltante |
| Aporta solo datos agregados | Recibe un plan e informe adecuados a ese nivel, sin requisitos de detalle ajenos a lo calculable |
| No aporta un archivo opcional | El sistema adapta el plan y continúa sin insistencia injustificada |
| Hay información más rica | Profundiza o propone análisis adicionales pertinentes y verificables |
| Un resultado no supera comprobaciones | No se publica como hallazgo confirmado |
| Vuelve sin archivos nuevos | Puede conversar sobre la revisión disponible |
| Actualiza datos | Reutiliza contexto y aclara solo lo necesario |
| Repite o solapa archivos | No se duplica silenciosamente la actividad |
| Hay datos nuevos sin informe nuevo | La interfaz distingue ambos estados |
| Cambia el contexto actual | Los informes anteriores conservan sus supuestos |
| Da un dato claro y útil al chat en 2.5 | Se guarda con procedencia/ámbito, se muestra el cambio y otro chat puede usarlo |
| Plantea una hipótesis o una definición contradictoria | No se transforma automáticamente en un hecho confirmado |
| Corrige o retira memoria desde «Mi negocio» | El cambio afecta a las próximas respuestas y se revisan los resultados dependientes |
| Reabre un chat antiguo | Conserva el historial y los turnos nuevos consultan la memoria vigente aplicable |
| Falla el proceso o falta toda base útil | Hay explicación y siguiente paso sin perder el trabajo aceptado |

Son criterios de producto, no una prescripción de arquitectura o infraestructura de pruebas.

## 20. Validación y decisiones pendientes

### 20.1. Qué observar con usuarios

Se propone probar con 3–5 comercios independientes de sectores cercanos y repetir más de una revisión, usando sus archivos reales. Comparar tareas con su proceso actual e incluir el tiempo de exportación y aclaraciones: un informe agradable no demuestra ahorro ni ventaja.

- ¿Entienden cómo empezar y consiguen aportar los archivos?
- ¿La descripción inicial resulta fácil y mejora las preguntas?
- ¿Comprenden por qué se pide cada aclaración?
- ¿Pueden explicar un hallazgo con sus propias palabras?
- ¿Encuentran la evidencia cuando quieren comprobarlo?
- ¿Saben qué preguntar al chat y entienden sus límites?
- ¿Les sirve el PDF?
- ¿Vuelven para conversar, actualizar o ambas cosas?
- ¿La segunda revisión requiere menos esfuerzo?
- ¿El análisis les lleva a comprobar o hacer algo concreto?
- ¿Querrían repetir esa utilidad y posteriormente pagar por ella?

Si cada archivo exige ayuda manual continua, habrá que reducir el formato admitido o adelantar alguna ayuda de obtención de datos. No añadir funciones automáticamente para compensar.

### 20.2. Decisiones de UX todavía abiertas

- Registro e inicio de sesión.
- Detalle visual de Inicio, informes, «Mi negocio», prompt y chats; su estructura de navegación ya está acordada para 2.5.
- Cantidad de preguntas por tanda y presentación del progreso.
- Detalles de presentación del historial de conversaciones, revisiones y cambios de memoria, previstos en 2.5.
- Reglas comprensibles de sustitución o incorporación de archivos.
- Diseño y detalle estático de evidencia en el PDF.
- Política de conservación y borrado.

### 20.3. Para la siguiente conversación técnica

- Escenarios con distintos niveles de datos y resultados admisibles, incluyendo negativas a aportar más información.
- Evaluación de información, guía base, planificación autónoma y reformulación.
- Implementación y evaluación de la coordinación acordada: agente principal y revisor en el MVP; negocio, analítica y revisor como evolución del producto final (sección 18.6). Concretar presupuestos, verificación y parada.
- Lectura de Excel/CSV, operaciones componibles, consultas y análisis adicionales comprobables.
- Definiciones y requisitos por análisis, con reglas y cálculos de referencia para comprobar resultados.
- Persistencia del contexto, disponibilidad, planes, ejecuciones, evidencia y resultados.
- Interfaz del informe, evaluación del recorrido y despliegue.
- Implementación y evaluación de la previsión candidata en una fase posterior.

El orden operativo de estas decisiones está en la sección 8 del MVP. Se empieza por comportamiento y escenarios; el contrato universal de columnas y la lista fija de cálculos dejan de ser el punto de partida. Precio, calendario y modelo comercial no quedan fijados aquí.

## 21. Historial de decisiones

### 21.1. Actualización del 15 de septiembre respecto al día 14

- Se centra la visión en eliminar fricción para pequeños negocios sin conocimientos de IA.
- La descripción del negocio pasa a ser el primer paso.
- La intención inicial es recibir ayuda general, sin formular preguntas.
- El informe pasa a resumen y secciones, con hallazgos antes que cifras.
- Se define el dashboard como presentación interactiva del mismo análisis.
- El PDF pasa de opcional a parte del recorrido acordado.
- El chat pasa a ser una pieza del producto, capaz de explicar y explorar decisiones.
- Se reconocen dos motivos de regreso: conversar y actualizar datos.
- Se incorpora explícitamente la interpretación guardada y acotada de los datos.
- Se aplaza la actualización persistente del contexto desde el chat.
- El MVP se centra en usuarios con Excel o CSV existentes.
- Plantillas y ayuda para conseguir o registrar datos pasan a mejoras posteriores.
- Deja de exigirse inicialmente un Excel maestro generado por la aplicación.
- Se registran automatización, informes periódicos y predicciones como líneas futuras.
- En esa revisión, el catálogo concreto de análisis y las decisiones técnicas se reservaron para después.

### 21.2. Especialización y definición funcional del 17 de septiembre

- El foco pasa a comercios de productos no perecederos con ventas por artículo.
- Se sustituyen ejemplos de servicios por papelería, bazar y tienda de regalos.
- Se concreta el núcleo de ventas, prioridades y consultas comprobables; margen/inventario y previsiones son ampliaciones.
- Se propone guardar asuntos para revisar con seguimiento manual mínimo.
- Se diferencia una función no implementada de los datos que faltan para una función disponible.
- Se exige comparar utilidad y esfuerzo con el proceso real del comercio; las capacidades no se presentan como exclusivas.
- Se mantienen PDF, chat, revisión manual y contexto del onboarding. La memoria automática desde el chat y los conectores siguen siendo posteriores.

### 21.3. Revisión hacia investigación autónoma y adaptable

- Se retira el detalle por producto/ticket como requisito general de entrada.
- La guía de análisis sustituye al catálogo cerrado; el sistema elige y revisa su plan.
- Se piden datos opcionales explicando su utilidad y se continúa si no se aportan.
- Los análisis adicionales necesitan evidencia y cálculos comprobables; hay límites de tiempo, coste e iteraciones.
- Se evalúa con distintos niveles de detalle y planes admisibles, no con un informe único.
- La planificación técnica empieza por comportamiento y escenarios, seguida de evaluación de datos, coordinación, herramientas y persistencia.
- El MVP sigue terminando en una página sencilla; chat posterior, PDF y seguimiento quedan para entregas siguientes.

### 21.4. Organización multiagente objetivo del 21 de septiembre de 2026

- Se acuerda separar negocio, analítica y revisión en la evolución del producto completo.
- Negocio orienta la investigación y puede pedir nuevas comprobaciones a analítica; analítica devuelve evidencia, limitaciones y propuestas de profundización.
- El revisor examina cálculos y contenido; el controlador conserva los permisos, presupuestos y condiciones de publicación.
- Informe y dashboard utilizan contenido estructurado y componentes de presentación de la aplicación.
- El MVP mantiene su agente principal con revisor. La separación futura se implementará y comparará con esa referencia antes de consolidar su despliegue.

### 21.5. Memoria compartida y experiencia cotidiana del 23 de septiembre de 2026

- Se distingue onboarding de uso habitual: el negocio persiste y no se vuelve a explicar en cada análisis.
- Inicio se convierte en la página de regreso con hallazgos y gráficos respaldados, prompt y preguntas sugeridas; Informes conserva las revisiones individuales.
- La barra lateral incorpora «Mi negocio» y conversaciones recientes.
- Se adelanta la actualización de contexto desde chat: hechos versionados con procedencia, ámbito y vigencia, correcciones visibles y contradicciones resueltas antes de usarlas.
- Se comparte memoria entre conversaciones y se selecciona el contexto necesario para cada ejecución; una corrección puede afectar a resultados de varios chats.
- Se mantiene PostgreSQL y almacenamiento privado. Se añade la entrega 2.5 antes de las entregas 3–5, sin afirmar que estas capacidades estén construidas.

## 22. Experiencia objetivo

Al terminar la primera visita, el usuario debería poder decir:

> He explicado mi negocio, he subido lo que tenía y he respondido preguntas que entendía. Ahora sé qué muestran mis datos, qué merece atención y qué todavía no podemos saber. Puedo explorar el informe, descargarlo y preguntar sin empezar de cero.

Al volver:

> Mi tienda y mi último análisis siguen aquí. Puedo resolver una duda, aportar datos nuevos y revisar los asuntos que guardé. Solo tengo que aclarar lo que ha cambiado.

Ese es el centro de Decision Room: una revisión comprensible y verificable del negocio, una conversación contextual y una continuidad sencilla, antes de ampliar el producto con automatización o predicciones.
