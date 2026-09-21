# Decision Room: servicios, diferenciación y definición del producto

**Actualizado:** 17 de septiembre de 2026.  
**Segmento acordado:** pequeños comercios que revenden productos no perecederos y tienen Excel/CSV aprovechables, desde totales agregados hasta registros detallados.  
**Estado:** propuesta funcional fundamentada; la demanda, la disposición a pagar y la superioridad frente a alternativas aún requieren pilotos.  
**Relación con otros documentos:** este documento define qué resolver y con qué límites. La [definición del producto](<Decision Room - Definicion del producto.md>) define la experiencia de uso; la [investigación de segmentos y datos](<../research/Decision Room - Investigacion de segmentos y datos.md>) conserva la selección del segmento. El [MVP](<Decision Room - MVP.md>) y su plan recogen las decisiones posteriores de arquitectura e implementación.

**Actualización de alcance de la primera entrega:** se ha acordado un [MVP más pequeño](<Decision Room - MVP.md>): archivo compatible → aclaraciones → análisis histórico → informe en una página sencilla. Ese documento prevalece para la implementación inmediata. Las referencias de este documento al núcleo o MVP con chat, PDF y seguimiento describen el producto posterior; esas funciones se conservan en la visión, pero se aplazan respecto a la primera entrega.

**Enfoque transversal acordado:** autonomía para decidir qué investigar, con resultados comprobables. La guía de análisis orienta un plan revisable; el detalle por producto/ticket no es un requisito de entrada y los servicios descritos son oportunidades condicionadas a los datos y herramientas, no una lista de conclusiones obligatorias.

## 1. El producto que queremos crear

**Decision Room convierte los archivos de una pequeña tienda en una revisión comprensible de sus ventas, unas pocas prioridades respaldadas por datos y una conversación que permite comprobarlas y profundizar. En sucesivas revisiones ayuda a ver qué cambió y qué merece seguir investigando.**

Promesa inicial propuesta:

> Entiende qué muestran los datos que tienes de tu tienda y qué conviene revisar. El análisis se adapta a la información disponible y puedes comprobar las cifras. Con más detalle, podemos investigar más.

La evolución del producto desarrolla capacidades de margen, inventario y previsión. El sistema puede realizar exploraciones históricas adicionales con costes o existencias si dispone de datos y herramientas verificables, sin convertir esos módulos completos en requisitos del MVP. Las predicciones siguen en una fase posterior. No se promete desde el primer día optimizar compras, aumentar beneficios ni anticipar cualquier problema.

Los informes, el dashboard, las predicciones y el agente son capacidades útiles. **Su combinación, por sí sola, no demuestra diferenciación:** hay competidores que ya ofrecen partes sustanciales de ella. Nuestra oportunidad por comprobar es resolver esas tareas para un propietario cuyos archivos y proceso actual no le permiten hacerlo satisfactoriamente, sin exigirle cambiar su sistema de caja.

## 2. Para quién y en qué situación

### Cliente inicial

- Dueño o encargado de una tienda de regalos, bazar, papelería, hogar o accesorios; otros sectores pueden entrar si comparten la operativa admitida.
- Una ubicación, moneda y canal sencillos en la primera versión.
- Tiene Excel/CSV que permiten alguna lectura útil: totales por periodo, ventas por producto, tickets u otros datos pertinentes. Cada análisis exige sus propios requisitos; no se imponen los de tickets a toda la entrada.
- Tiene una pregunta repetida sobre su actividad y su proceso actual exige demasiado trabajo o no le da una explicación satisfactoria.
- Puede volver a aportar datos para una segunda revisión.

No basta con «no saber de IA». Ese rasgo no demuestra una necesidad ni voluntad de pagar. Hay que encontrar una dificultad concreta que el producto resuelva.

### Necesidades candidatas: todavía hipótesis

| Situación del propietario | Resultado que querríamos entregarle | Cómo comprobar que importa |
|---|---|---|
| «Vendo menos y no sé por dónde empezar» | Desglose de la variación y pocos puntos a revisar | Reconoce una pregunta real, entiende la explicación y puede contrastarla |
| «Tengo muchas referencias y no puedo mirarlas todas» | Selección de cambios relevantes en productos y categorías | Le ahorra revisión y encuentra algo que merece atención |
| «Las devoluciones o descuentos me preocupan» | Evolución, concentración y magnitud observada | La información le permite investigar una incidencia concreta |
| «No sé si vender más me está dejando más margen» | Margen bruto si hay costes compatibles y herramientas verificables; ampliación especializada cuando sea necesaria | Aporta costes y usa la comparación para una decisión real |
| «No sé cuánto reponer» | En una ampliación: cobertura y previsión con sus límites | Tiene stock/plazos y la propuesta mejora su método de compra |
| «Quiero preguntar algo sin rehacer el Excel» | Respuesta con periodo, cálculo y evidencia | Resuelve consultas reales más fácilmente que su alternativa |
| «Hicimos un cambio; ¿qué pasó después?» | Comparación y contexto de la decisión | Vuelve con datos y utiliza el seguimiento sin atribuir causalidad automáticamente |

No se han entrevistado propietarios para confirmar estas prioridades. Son candidatas derivadas de los procesos y datos investigados.

### Clientes con poco encaje inicial

Operaciones complejas de fabricación, perecederos o venta a peso; quien necesita un TPV completo; o quien ya resuelve estas tareas con su plataforma y está satisfecho. La ausencia de detalle por producto reduce posibilidades, pero no excluye por sí sola al comercio. Sin ninguna base interpretable se explica qué información permitiría empezar.

## 3. Qué existe ya: contraste competitivo

Revisión de documentación oficial a 17 de septiembre de 2026. Se verifican capacidades publicadas, no su calidad mediante pruebas de uso. Disponibilidad, permisos, país y plan pueden variar.

| Alternativa | Capacidad documentada | Consecuencia para Decision Room |
|---|---|---|
| Loyverse | Informes por artículo con ventas, devoluciones, descuentos, costes y margen; gráficos y exportación. La página consultada limita los informes de la versión gratuita a 31 días y exige acceso adicional para exportarlos | Mostrar ventas o productos destacados no basta; también hay fricción de acceso que comprobar antes de reclutar usuarios. [Fuente](https://help.loyverse.com/help/sales-item-report-back-office) |
| Shopify Sidekick y Pulse | Conversación contextual y recomendaciones proactivas; Pulse figura en acceso anticipado para ciertos comercios | No podemos afirmar que descubrir prioridades sin preguntar sea exclusivo. [Sidekick](https://help.shopify.com/en/manual/ai-powered-tools/sidekick), [Pulse](https://help.shopify.com/en/manual/ai-powered-tools/sidekick/pulse) |
| Shopify, inventario | El proveedor describe recomendaciones de reposición basadas en ventas, stock y previsión, junto con preparación de pedidos | «Agente que te dice qué comprar» tampoco es una diferenciación suficiente. Es una capacidad publicada por el proveedor, no una eficacia medida aquí. [Fuente](https://www.shopify.com/blog/enhanced-inventory-management) |
| Lightspeed Retail X-Series | Previsión de demanda y cantidades sugeridas de reposición, con disponibilidad según plan y módulos | Predecir unidades no es novedoso. Debemos comparar utilidad y error con alternativas sencillas y con la herramienta del cliente. [Fuente](https://x-series-support.lightspeedhq.com/hc/en-us/articles/25533686759451-Getting-started-with-demand-forecasting) |
| Square Managerbot | Resúmenes, señales, preguntas sobre datos y sugerencias de siguientes pasos; también tareas con aprobación | La combinación informe, ideas y conversación ya tiene competencia directa. La documentación revisada corresponde a Estados Unidos. [Fuente](https://squareup.com/help/us/en/article/8617-use-managerbot-to-manage-business-tasks-and-insights) |
| Holded | Informes de productos, costes y existencias construidos desde documentos y movimientos de stock | Reunir ventas e inventario tampoco constituye una novedad por sí mismo. [Fuente](https://help.holded.com/es/articles/6933228-consultar-los-informes-de-inventario) |

**Conclusión validada documentalmente:** esas funciones existen. **Conclusión que no está validada:** que los pequeños comercios objetivo estén bien atendidos o que prefieran Decision Room. Ambas requieren observar su trabajo.

## 4. Diferenciación que proponemos comprobar

### 4.1. Una revisión preparada para decidir

El dueño abre un resumen con pocas prioridades, la evidencia y una siguiente comprobación concreta. No tiene que elegir primero métricas o formular una pregunta. El objetivo es reducir el trabajo de interpretación.

Esto es una hipótesis de mejor ejecución para nuestro público; competidores como Pulse también priorizan. La prueba es que el usuario complete una tarea real mejor que con su alternativa, no que prefiera el aspecto del informe.

### 4.2. Trabajar con archivos compatibles de su operativa actual

El sistema interpreta archivos Excel/CSV con distintos niveles de detalle, sin exigir que todos encajen en un esquema de tickets. Define qué puede analizar ahora y pregunta por datos adicionales si habilitan una investigación pertinente y disponible. Si el dueño no los tiene o no quiere aportarlos, continúa con el plan ajustado. Los límites físicos de ingesta y las herramientas se concretarán técnicamente; no se promete importación universal.

Esta independencia puede ayudar cuando la información está fuera de un solo programa. También tiene un coste: exportar y actualizar archivos puede ser peor que un asistente integrado. El piloto debe medir ambos lados.

### 4.3. Cifras comprobables y contexto conservado

El propietario puede ver qué periodo, archivos, filtros y definiciones sostienen una afirmación. Informe, PDF y chat utilizan la misma revisión. Las aclaraciones sobre impuestos, devoluciones o códigos se reutilizan donde sigan aplicando.

La fiabilidad es un requisito del producto, no una superioridad demostrada frente a otros sistemas. Puede convertirse en preferencia si el cliente comprueba que resuelve sus dudas con menos errores o esfuerzo.

### 4.4. Continuidad entre una revisión y la siguiente

Propuesta nueva y acotada: guardar un hallazgo para revisarlo después, con una nota opcional y, si el dueño actuó, la fecha declarada. Al cargar datos nuevos se muestra qué ocurrió con la métrica relacionada.

En el producto ampliado sería una selección explícita y sencilla desde el informe; queda fuera de la primera entrega y no requiere memoria automática desde el chat, recordatorios, un gestor de tareas ni ejecución externa. Una mejora posterior al cambio no se presenta automáticamente como efecto causado por él.

### 4.5. Profundidad adaptada a la información real

Una tienda con totales diarios puede recibir una lectura útil de su evolución; otra con detalle puede obtener desgloses por producto y tickets. El sistema no se detiene en un checklist si encuentra una pregunta adicional pertinente que puede resolver y verificar.

La diferenciación por comprobar es esa adaptación con resultados fiables y pocas preguntas innecesarias. Se evaluará con entradas de distinta riqueza, incluyendo respuestas «no lo tengo». No se afirma que los competidores carezcan de adaptación ni que autonomía equivalga a ventaja por sí misma.

### Qué no usaríamos como argumento de venta

«Tenemos varios agentes», «usamos machine learning», «tenemos un dashboard», «somos los únicos que recomendamos acciones» o «somos más precisos». Los dos primeros describen medios; los demás necesitan evidencia que todavía no tenemos.

## 5. Servicios y resultados concretos

Son una guía base para elegir investigaciones. El plan puede omitir, profundizar o añadir análisis pertinentes dentro del alcance histórico y de las herramientas disponibles. Cada conclusión debe satisfacer sus requisitos de datos y comprobación; no se exige producir todas las secciones.

### 5.1. Comprender qué cambió — núcleo inicial

Comparar ventas entre periodos compatibles; identificar contribuciones de productos y categorías; examinar tickets, unidades, devoluciones y descuentos cuando existan los campos correspondientes.

**Entrega:** resumen explicado, desglose verificable y opciones de profundización. Las definiciones de ventas netas y ticket deben fijar impuestos, devoluciones y anulaciones; no se resta dos veces un descuento ya aplicado.

**Límite:** menos tickets no demuestra menos personas ni menor conversión. Para contar compradores necesitamos identificadores apropiados; para conversión, datos de visitas o tráfico.

### 5.2. Detectar qué merece atención — núcleo inicial

Seleccionar variaciones relevantes, incidencias de datos y concentraciones de devoluciones o descuentos. Ordenarlas considerando magnitud observada, cobertura y posibilidad de comprobar o actuar. Evitar repetir el mismo cambio en varias tarjetas.

**Entrega:** idealmente hasta tres asuntos prioritarios como propuesta de diseño, sin obligación de rellenar ese número. Cada uno incluye qué ocurrió, por qué se destaca y qué comprobar.

**Límite:** una caída grande en porcentaje sobre dos ventas puede no merecer atención. La selección considerará volumen, euros, comparabilidad y contexto; no un umbral universal. Un fallo de archivo puede ser más urgente que un supuesto problema comercial.

### 5.3. Resolver preguntas con evidencia — núcleo inicial

El agente explica resultados y elige o compone operaciones verificables para responder a las preguntas. Filtros, agregaciones, comparaciones y desgloses constituyen una base, no un catálogo cerrado de preguntas. Puede proponer investigaciones adicionales, ajustar el plan y señalar qué falta. El chat posterior permanece fuera de la primera entrega; este mismo principio se aplica al análisis autónomo que prepara su informe.

Ejemplos: «¿Qué artículos explican esta caída?», «¿Ocurre también sin devoluciones?», «¿Estamos comparando los mismos días?» y «¿De dónde sale esa cifra?».

**Entrega:** respuesta directa, evidencia accesible y límites concretos. Un vínculo a un archivo no basta si no permite localizar los registros o el cálculo que sostienen la respuesta.

**Límite:** ni acceso a todos los datos garantiza respuesta a cualquier pregunta ni una recomendación general equivale a un hallazgo del negocio.

### 5.4. Revisar decisiones — núcleo inicial acotado

Guardar manualmente un asunto para la próxima revisión, recuperar su explicación y comparar el periodo nuevo cuando sea válido. La anotación del dueño se distingue de los datos calculados.

**Entrega:** «Esto seguía pendiente; esto cambió; esto todavía no sabemos». No se generan seguimientos ficticios si no hay datos nuevos o suficientes.

### 5.5. Comprender margen y existencias — exploración condicional y ampliación especializada

Cruzar ventas con costes compatibles e inventario mediante códigos confirmados. Priorizar productos que aportan margen, existencias con baja salida y comprobaciones antes de reponer.

**Entrega:** margen bruto y cobertura o valor de existencias, según lo que pueda calcularse. El margen bruto no es beneficio neto. El stock valorado a coste no es dinero recuperable garantizado.

**Datos adicionales:** coste aplicable a cada venta o periodo; existencias con fecha; movimientos o disponibilidad histórica cuando el análisis los necesite. El coste de hoy no se aplica como coste real a todas las ventas antiguas. Una aproximación, si se admite, debe identificarse y no mezclarse con margen observado.

Las exploraciones descriptivas que el sistema ya pueda ejecutar y comprobar no quedan prohibidas por no figurar en la guía base. El módulo especializado de margen/inventario sigue siendo una ampliación, prioritaria si los pilotos muestran valor. No se promete que cualquier archivo con costes habilite automáticamente margen ni se bloquea el MVP por carecer de esa capacidad. El análisis histórico puede resultar insuficiente como producto de pago; hay que comprobarlo.

### 5.6. Anticipar ventas y apoyar reposición — ampliación validada

Primera candidata: ventas o unidades de las próximas semanas, al nivel de tienda, categoría o producto que el histórico permita. Probaríamos horizontes de una a cuatro semanas según la decisión; no es una garantía aplicable a todas las tiendas.

**Entrega:** previsión, rango de incertidumbre, periodo, datos utilizados y error histórico comprensible. Para convertirla en propuesta de compra hacen falta además stock utilizable, pedidos entrantes, plazos del proveedor, mínimos de compra y restricciones relevantes.

Una previsión de ventas observadas no equivale automáticamente a demanda: si hubo roturas de stock, las ventas pueden estar limitadas por disponibilidad. Con la información insuficiente, se explicita el problema y se reduce el alcance o no se publica la previsión.

No prometeríamos cantidades óptimas, precios óptimos, demanda de productos nuevos sin evidencia, ni ingresos adicionales causados por promociones.

### 5.7. Descubrir asociaciones y explorar escenarios — después

Las compras conjuntas podrían sugerir artículos para estudiar juntos. No prueban que un paquete promocional aumente ventas. Una simulación de descuento puede calcular qué volumen compensaría un margen menor bajo supuestos explícitos; no predice que se vaya a conseguir ese volumen.

Estas capacidades se añadirán solo si responden a una necesidad repetida. No constituyen requisitos del primer producto.

## 6. Condiciones de datos y alcance

| Resultado | Datos mínimos relevantes | Si faltan datos o la capacidad no está implementada |
|---|---|---|
| Evolución agregada | Periodos e importes de significado y cobertura interpretables | No exigir productos ni tickets; limitarse al nivel disponible |
| Evolución de ventas y productos | Fechas, producto, importes y tratamiento de descuentos/devoluciones | Analizar la parte interpretable; excluir lo ambiguo de forma visible |
| Ticket medio y cesta | Identificador de ticket y líneas coherentes | No contar filas como compras |
| Devoluciones y descuentos | Importes o estados que permitan identificarlos sin duplicación | No inferirlos de cualquier número negativo |
| Repetición de compradores | Identificador estable de cliente y cobertura conocida | Fuera del núcleo inicial; no confundir tickets con clientes |
| Margen bruto | Ventas y costes pertinentes, enlazados y con vigencia | Explorar si la operación se puede ejecutar y verificar; si no, explicar el límite sin impedir otros análisis |
| Baja salida y cobertura de stock | Stock fechado, ventas y disponibilidad/catálogo según el análisis | No convertir cero ventas en exceso de existencias |
| Previsión | Histórico suficiente para el horizonte y evaluación temporal | No mostrarla si no supera criterios de utilidad |
| Cantidad de reposición | Previsión utilizable, stock, entradas, plazos y restricciones | Puede haber análisis de ventas sin recomendación de compra |

La interfaz diferencia **dato ausente**, **dato dudoso**, **dato no aportado por decisión del usuario** y **función todavía no disponible**. Solicita información que mejoraría un análisis disponible, explica su utilidad y continúa si el usuario no la aporta. No pide archivos para una capacidad inexistente ni confunde esas peticiones opcionales con aclaraciones indispensables para un cálculo concreto.

## 7. Ejemplo de la experiencia que buscamos

**Ejemplo ficticio, solo para definir el producto.** Dos periodos comparables, misma cobertura, sin devoluciones ni descuentos en este ejemplo:

- Ventas: 20.000 € → 18.000 €.
- Tickets: 1.000 → 900.
- Ticket medio: 20 € en ambos periodos.
- Una categoría pasa de 6.000 € a 4.400 €: aporta 1.600 € de los 2.000 € de caída.

Tarjeta propuesta:

> **Revisa qué ha cambiado en esta categoría.** Las ventas registradas bajan un 10 %. El ticket medio se mantiene y hay 100 compras menos. Esta categoría concentra el 80 % de la caída neta total.

Detalle: periodos, fórmula, productos que contribuyen, origen y cualquier exclusión. Si otras categorías compensan una caída, se mostrarían por separado para que la contribución no resulte engañosa.

Ante «¿Ha bajado la demanda?», el agente explica que faltan disponibilidad y otros elementos para concluirlo. Propone comprobar si hubo artículos agotados o cambios de surtido. El dueño puede guardar el asunto para revisar.

El producto debe funcionar igual de bien cuando el resultado correcto sea «no hay una variación relevante» o «no podemos comparar estos archivos».

## 8. Qué significa que el agente sea fiable

Son requisitos verificables, no una promesa de infalibilidad:

1. **Cifras calculadas:** los números proceden de operaciones reproducibles sobre los datos admitidos. No los inventa la redacción del modelo.
2. **Fuentes que respaldan la afirmación:** periodo, archivo/hoja, registros o resultado de cálculo localizables; citar no equivale a demostrar.
3. **Definiciones compartidas:** informe, PDF y chat usan las mismas reglas. Un filtro nuevo se declara como análisis adicional.
4. **Separación visible:** observado, contexto declarado, hipótesis, previsión y escenario son categorías distintas.
5. **Preguntar o abstenerse:** si hay impuestos, unidades o uniones ambiguas, se aclara antes de publicar el resultado afectado.
6. **Vigencia y acceso acotados:** utiliza la revisión y el negocio correspondientes. Un texto dentro de un archivo es un dato, no una instrucción para cambiar las reglas del agente.
7. **Errores recuperables:** puede señalar una discrepancia, mostrar qué falta y corregir el análisis sin ocultar el cambio de versión.

La autonomía abarca seleccionar preguntas, componer análisis, pedir aclaraciones, replanificar y detener líneas poco útiles. Las operaciones deben dejar resultados reproducibles, evidencia y comprobaciones. El acuerdo entre agentes no sustituye una comprobación numérica o de cobertura. Los límites de tiempo, coste e iteraciones y la abstención evitan exploración indefinida y resultados inventados. La arquitectura para ejecutar análisis adicionales sigue pendiente. La conversación puede acompañar una decisión sin asumir autoridad para ejecutar compras o cambiar precios.

## 9. Predicciones: utilidad antes que complejidad del modelo

Machine learning es una posible técnica; no una necesidad para cada hallazgo ni una garantía de mejor resultado. Una regla o un modelo estadístico sencillo pueden ser la solución correcta.

Para habilitar una previsión:

- Compararla con métodos simples, como repetir el periodo equivalente anterior o una media reciente. [Referencias de comparación](https://otexts.com/fpp3/simple-methods.html).
- Evaluarla avanzando por fechas: en cada prueba solo se utiliza información que ya habría existido. El horizonte de evaluación debe coincidir con el de la decisión. [Validación temporal](https://otexts.com/fpp3/tscv.html).
- Medir errores en unidades o euros y evitar una «accuracy» universal. Los errores porcentuales pueden ser inadecuados con ventas cero. [Evaluación de precisión](https://otexts.com/fpp3/accuracy.html).
- Comprobar la cobertura y amplitud de los rangos de incertidumbre, además del error medio. [Intervalos de predicción](https://otexts.com/fpp3/prediction-intervals.html).

No habrá una regla universal de «con tres meses ya podemos predecir». Depende de frecuencia, volumen, estacionalidad, cambios y horizonte. Un modelo que falla en artículos de poca salida no debe quedar oculto tras un buen promedio global.

**Criterio propuesto:** usar el método que supere la evaluación y sea útil para la decisión. Si no hay una mejora práctica frente al método sencillo, no justificar complejidad extra. Si ninguna previsión tiene utilidad, mantener el análisis histórico y explicar el límite.

Los datos públicos de comercio de la investigación anterior permiten investigar ventas; no validan por sí solos una política de inventario, al faltar costes, disponibilidad y plazos. No se ha entrenado ni evaluado ningún predictor durante esta definición del producto.

## 10. Qué verá el cliente

El dashboard sigue siendo la presentación interactiva del informe, no un segundo producto separado:

- **Resumen:** pocas prioridades, breve explicación y cifras de apoyo.
- **Ventas y productos:** comparaciones, contribuciones y detalle pertinente.
- **Devoluciones y descuentos:** cuando los datos lo permiten.
- **Para revisar:** asuntos guardados explícitamente y su evolución cuando haya nueva información.
- **Exploraciones adicionales:** se muestran si el sistema pudo ejecutarlas y verificarlas, también con costes o existencias pertinentes. Las previsiones se incorporan en una fase posterior.
- **Chat contextual y PDF:** otras formas de explorar o leer la misma revisión.

El producto prepara prioridades al generar una revisión, sin obligar a preguntar. En el MVP esto sucede tras una carga manual; no significa vigilancia permanente, sincronización en tiempo real ni informes semanales automáticos.

## 11. Alcance y orden de entrega

La primera entrega implementable se ha acotado posteriormente en [MVP y primera entrega](<Decision Room - MVP.md>). La tabla siguiente conserva la evolución del producto más amplio, no los requisitos para dar por terminado ese MVP.

| Etapa | Qué entregamos | Qué debe justificar avanzar |
|---|---|---|
| Núcleo inicial | Plan adaptado a datos agregados o detallados; preguntas opcionales; análisis histórico verificable con guía base y exploraciones adicionales pertinentes. En el producto ampliado: PDF, chat y seguimiento | Adaptación, cálculos sólidos y utilidad repetida en pilotos |
| Primera ampliación especializada | Herramientas más completas de costes e inventario; margen bruto, baja salida y cobertura donde sea posible | Archivos reales accesibles y decisiones que requieran esa información |
| Previsión | Un caso acotado de ventas/unidades; después apoyo a reposición con datos suficientes | Evaluación temporal y utilidad superior o suficiente frente al método actual |
| Continuidad automatizada | Conectores elegidos por uso real, actualizaciones e informes periódicos | Uso recurrente demostrado y carga manual como obstáculo observado |

El PDF y el chat permanecen en el núcleo acordado. La ampliación pequeña de seguimiento se registra como propuesta nueva. La memoria persistente automática desde conversaciones sigue siendo posterior.

No entran inicialmente: cambios de precios o compras autónomas, optimización integral de la tienda, contabilidad completa, medición causal automática, benchmarking competitivo sin fuentes comparables, todas las integraciones ni todas las clases de archivos.

## 12. Cómo validar las conclusiones

### Comprobado en esta revisión

- Las capacidades competitivas de la sección 3 están documentadas por sus proveedores. Se consultaron condiciones de acceso donde eran relevantes.
- La promesa se ha contrastado con los campos disponibles: ventas no implica margen, stock ni demanda no atendida.
- Los criterios de previsión se contrastaron con referencias de evaluación de series temporales.
- Se revisaron casos que invalidarían conclusiones: faltan días, el producto estuvo agotado, hay descuentos ya incluidos, cambia el coste y se cuenta cada línea como un ticket. Son comprobaciones conceptuales, no pruebas de un sistema ya implementado.

### Pendiente antes de afirmar que tenemos una ventaja

**A. Evaluación del sistema, cuando exista.** Preparar un conjunto de consultas y archivos con respuestas comprobadas independientemente, incluyendo preguntas imposibles de responder. Verificar cifras, filtros, referencias, revisiones, duplicados y consistencia entre informe/PDF/chat. Exigir que todos los casos críticos del conjunto de aceptación pasen; eso no garantiza cero errores futuros.

Evaluar también planes diferentes con datos agregados, detalle sin tickets, registros completos y datos enriquecidos. Comprobar que se adapta cuando el dueño rechaza aportar más información y que los análisis adicionales tienen sustento. Las expectativas se fijan sobre resultados admisibles, límites y exactitud, no sobre un texto único o una secuencia de agentes obligatoria. Esta batería está propuesta; aún no se ha ejecutado.

**B. Comparación con el proceso real.** Propuesta: 3–5 tiendas independientes, al menos dos ciclos de datos. Pedir que cada dueño resuelva una tarea habitual con su proceso actual y con el prototipo. Medir ayuda necesaria, tiempo total —incluida exportación—, comprensión y errores. Variar el orden de prueba cuando sea posible. Comparar con herramientas que realmente tienen disponibles, no con una versión artificialmente pobre.

**C. Demanda y continuidad.** Observar si guardan una comprobación útil, aportan la segunda actualización y quieren continuar. Una novedad interesante, elogios o aceptar una prueba gratuita no equivalen a disposición a pagar. La oferta comercial debe probarse con una decisión real de contratación cuando el servicio esté preparado.

### Criterios para decidir

| Hipótesis | Evidencia que buscar | Resultado que obligaría a cambiar |
|---|---|---|
| La revisión ahorra esfuerzo | Menor tiempo total para una tarea resuelta correctamente | La exportación y aclaraciones consumen más de lo que ahorran |
| Las prioridades aportan valor | El propietario entiende y usa una comprobación que le importa | Solo recibe cifras que ya conoce o consejos genéricos |
| El chat es útil y comprobable | Responde consultas reales, y el dueño localiza la evidencia | Inventar cifras, citar sin respaldo o limitarse a repetir el resumen |
| Hay motivo para volver | Segunda actualización y seguimiento de asuntos reales | Solo interés por la primera demo |
| El segmento puede abarcar varios sectores | Reglas comunes y pocos ajustes entre negocios | Cada tienda requiere trabajo manual distinto y permanente |
| La autonomía se adapta a la riqueza de datos | Informes útiles con totales y mayor profundidad justificada con detalle; continuidad si no se aportan datos extra | Rechaza datos básicos aprovechables, se limita siempre a la misma lista o publica análisis sin comprobar |
| La previsión mejora decisiones | Error y utilidad evaluados frente a alternativas | No supera la referencia o no cambia ninguna decisión útil |

Con pocos pilotos no se estimará el mercado ni se generalizarán porcentajes de éxito. Si no aparece valor repetido, acotaríamos problema/segmento o adelantaríamos la ampliación concreta que lo resuelva; no añadiríamos funciones indiscriminadamente.

## 13. Decisión de producto

Mantener las tres ideas del usuario —informe interactivo, descubrimiento/predicción y agente con datos—, organizadas alrededor de resultados concretos. Incorporar una continuidad pequeña para revisar lo que el dueño decidió investigar.

**Diferenciación propuesta:** una revisión comercial que adapta autónomamente la investigación a los archivos y contexto de la tienda, con resultados verificables y menor trabajo para entender qué merece atención. Es un posicionamiento por validar, no una característica exclusiva ni una ventaja comercial ya probada.

La primera prueba decisiva será que varios propietarios resuelvan mejor una pregunta real y quieran repetir la experiencia. A partir de ahí se justifica invertir en margen, inventario, previsiones o automatización.
