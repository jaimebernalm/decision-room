# Decision Room: investigación de segmentos y datos

**Fecha:** 17 de septiembre de 2026.  
**Estado:** investigación que fundamentó la selección del primer segmento. El usuario ha elegido comercio de productos no perecederos; la propuesta funcional posterior está en [Servicios y diferenciación](<../product/Decision Room - Servicios y diferenciacion.md>).  
**Pregunta:** ¿qué pequeños negocios permiten construir y probar un análisis útil con Excel/CSV, antes de disponer de clientes?

**Actualización de producto posterior a la investigación:** se mantiene el foco en comercio de productos no perecederos, pero se acepta información básica o detallada. El [MVP vigente](<../product/Decision Room - MVP.md>) adapta autónomamente el plan, solicita datos adicionales de forma opcional y exige resultados comprobables. Las constataciones sobre datasets y proveedores de este documento se conservan; el detalle por artículo se considera una oportunidad para profundizar, no una condición universal de entrada.

## 1. Conclusión

Recomiendo empezar por **pequeños comercios que revenden productos no perecederos y disponen de Excel/CSV aprovechables**. La profundidad dependerá de lo que permitan los datos: evolución agregada, productos, composición de compras o devoluciones. El sistema puede investigar más con información enriquecida si tiene herramientas para ejecutar y comprobar esos análisis.

Es una recomendación para tu situación: desarrollas un primer producto, no tienes acceso directo a negocios y quieres probarlo antes de ofrecerlo. **No demuestra que comercio sea el mercado con mayor disposición a pagar.** Esa pregunta requiere conversaciones y pilotos.

El alcance puede incluir varios sectores: regalos, papelería, artículos del hogar, bazares o accesorios. La operativa y la información determinan qué preguntas se pueden resolver. Un bazar con totales diarios puede recibir un análisis agregado útil; una tienda con tickets permite investigaciones más detalladas. La utilidad de ambos casos necesita validación.

Como segunda opción exploraría centros de actividades con cuotas —por ejemplo, estudios de fitness o yoga— si conseguimos históricos de socios, cobros y asistencias. Los negocios de citas también siguen siendo candidatos, pero no he localizado en las fuentes revisadas un conjunto público de peluquería equivalente a un historial comercial completo.

**Podemos compartir el motor entre sectores cercanos. No podemos asumir que todas sus decisiones, preguntas y métricas son iguales.**

## 2. Qué se ha investigado y qué queda abierto

La investigación combina documentación original de datasets, archivos descargados y documentación oficial de programas de gestión. Estos programas permiten observar qué entidades y flujos de trabajo existen y qué exportaciones ofrecen. Su documentación no prueba cuánto los usan los pequeños negocios de un país ni que sus usuarios necesiten otro producto.

Se han inspeccionado tres fuentes originales:

- **Online Retail II:** dimensiones, cabeceras y primeras 500 filas de cada hoja del Excel; no se ha auditado el millón de filas completo.
- **Sport Services:** lectura estructural de todo el CSV, número de registros, columnas y campos vacíos.
- **Hotel Booking Demand:** lectura estructural de los dos CSV originales, número de registros y columnas.

No se han entrenado modelos, ejecutado un prototipo de Decision Room ni entrevistado propietarios. Las valoraciones de encaje son razonamientos de producto basados en las evidencias, no resultados comerciales medidos.

El país de lanzamiento sigue sin definirse. Se utilizan ejemplos internacionales y alguna herramienta con documentación en español. No se presupone que una plataforma concreta domine el mercado objetivo.

### Cuatro cosas distintas que suelen confundirse

| Recurso | Qué permite comprobar | Qué no demuestra |
|---|---|---|
| Datos públicos reales | Cálculos, estructura, algunos patrones y calidad del análisis histórico | Que un comercio actual tenga esos mismos problemas o formatos |
| Datos sintéticos | Casos límite, archivos mal formados, preguntas de onboarding, respuestas esperadas | Patrones reales, utilidad comercial o precisión predictiva real |
| Cuenta de demostración de un software | Flujo de exportación o integración, cuando el proveedor lo permita | Comportamiento real de compradores y propietarios |
| Datos de un negocio piloto autorizado | Utilidad en su contexto, fricción de carga y comparación con su proceso actual | Generalización a todo un sector a partir de un solo negocio |

**Se pueden comprobar muchas cosas antes de vender. Para validar utilidad real también hacen falta personas y datos de negocios reales, aunque participen en un piloto gratuito.**

## 3. Comparación de las cinco familias

Valoraciones cualitativas para el MVP definido: archivos existentes, onboarding, informe explicado, visualización y chat con evidencias. No son puntuaciones de mercado.

| Familia | Datos públicos encontrados | Ayuda potencial | Principal dificultad | Encaje para empezar sin contactos |
|---|---|---|---|---|
| Venta de productos | Históricos transaccionales reales; faltan costes y existencias en la fuente principal | Explicar cambios de ventas, cesta y devoluciones; después margen y stock | Diferenciarse de los informes existentes y no confundir ventas con beneficio | **El más favorable para desarrollar y probar el núcleo** |
| Cuotas e inscripciones | Un conjunto deportivo real, agregado por usuario | Renovaciones, uso, cobros y capacidad de clases | Necesitamos historias temporales y varias tablas para muchos análisis | **Alternativa condicionada a datos piloto** |
| Citas | Datos médicos públicos; escasa equivalencia comercial con belleza en lo revisado | Agenda, recurrencia, ausencias y rendimiento por tiempo | Conseguir citas, disponibilidad y cobros coherentes | **Viable si se desbloquea acceso a un negocio** |
| Reservas de recursos | Buenos históricos hoteleros; no equivalen a todos los alquileres | Cancelaciones, canales, utilización y rendimiento de recursos | Capacidad disponible, tarifas y costes; diferencias entre recursos | **Bueno para una demo hotelera, más exigente como familia amplia** |
| Trabajos por encargo | Reparaciones comunitarias; no un historial completo de rentabilidad comercial | Presupuestos, desviaciones, horas, materiales y cobros | Unir todo por trabajo y conseguir datos representativos | **El más difícil de validar de forma autónoma con lo encontrado** |

Las familias se solapan. Un gimnasio puede cobrar cuotas y reservar clases; una peluquería puede vender productos; un taller agenda visitas y ejecuta trabajos. Elegir familia significa elegir **la decisión principal que resolverá el primer producto**.

## 4. Negocios que trabajan con cita

### Qué negocios incluye

Peluquerías, barberías, uñas, estética, tatuajes, peluquería canina y sesiones individuales de entrenamiento. Consultas sanitarias comparten la agenda, pero añaden procesos y datos que aconsejan tratarlas como un producto separado.

### Cómo trabajan y qué tendríamos que entender

Flujo básico: **reserva → asignación de profesional y tiempo → servicio, ausencia o cancelación → cobro → posible nueva visita**.

Datos: identificador de cita, fecha, servicio, duración prevista o real, profesional, estado, importe y cliente seudonimizado. Para medir ocupación necesitamos además las horas realmente disponibles, bloqueos y descansos.

Una pregunta importante de onboarding sería: «¿Hay servicios que ocupan una silla durante un tiempo, pero permiten al profesional atender otra cosa?». Dos citas de una hora no siempre consumen la misma capacidad.

### Ayuda que propondríamos

- Identificar franjas con huecos recurrentes y comprobar si coincide con la disponibilidad real.
- Comparar ingreso por tiempo de servicio, distinguiéndolo del margen.
- Observar intervalos entre visitas y cambios en repetición de clientes.
- Separar cancelaciones anticipadas, ausencias y huecos que finalmente se rellenaron.

Son candidatos a análisis, no promesas de que una promoción o recordatorio vaya a aumentar las ventas. Para medir esos efectos hacen falta intervenciones y seguimiento.

### Datos disponibles y exportaciones

Fresha permite exportar la mayoría de sus informes individualmente a CSV/XLSX/PDF, con permisos y selección de campos. Por tanto, empezar con archivos es plausible; habría que revisar los informes concretos de un piloto. [Documentación de Fresha](https://www.fresha.com/help-center/knowledge-base/reports/191-export-reports).

El conjunto público Medical Appointment No Shows corresponde a citas médicas y declara licencia **CC BY-NC-SA 4.0**. No lo tomaría como base de una demo comercial sin resolver las condiciones de uso; tampoco valida la economía de una peluquería. No he encontrado en esta revisión un historial público comparable de agenda, disponibilidad, servicios y cobros de un salón. [Fuente del dataset](https://www.kaggle.com/joniarroba/noshowappointments/activity).

**Juicio:** el problema es comprensible y permite un informe accesible, pero su facilidad de desarrollo está condicionada por los datos. Una familia inicial de belleza y cuidado personal tendría más sentido que «todos los negocios con cita».

## 5. Negocios que realizan trabajos por encargo

### Qué negocios incluye

Fontaneros, electricistas, climatización, reparaciones, carpintería, pintura, reformas y algunos servicios de jardinería. Talleres de coches, motos y bicicletas comparten partes del modelo, pero requieren distinguir mano de obra, piezas, diagnóstico y garantías. Agencias y estudios profesionales comparten proyectos, pero su estructura de costes es distinta.

### Cómo trabajan y qué tendríamos que entender

Flujo: **solicitud → visita o diagnóstico → presupuesto → aceptación → ejecución → materiales y horas → factura → cobro**.

Necesitamos relacionar los registros mediante un identificador de trabajo. Un archivo de facturas no explica por sí solo cuántas horas se invirtieron ni cuáles fueron los materiales consumidos.

Preguntas de onboarding: «¿Anotáis horas reales por trabajo?», «¿Los desplazamientos están incluidos?» y «¿Las compras de materiales están asignadas a cada encargo?».

### Ayuda que propondríamos

- Detectar tipos de encargo que generan desviaciones respecto al presupuesto.
- Comparar horas estimadas y reales, incluyendo desplazamientos si se registran.
- Examinar presupuestos pendientes y tasas de aceptación por tipo de trabajo.
- Mostrar facturas vencidas separando lo facturado de lo cobrado.

Para rentabilidad, definiríamos exactamente los costes incluidos. «Ingresos menos materiales» no equivale a beneficio del trabajo.

### Datos disponibles y exportaciones

Jobber documenta informes exportables y un cálculo de costes que combina horas, costes de mano de obra, materiales y gastos. Esto confirma la necesidad de unir esas piezas; también muestra que la rentabilidad por trabajo ya existe en herramientas del sector. [Informes de Jobber](https://help.getjobber.com/en/articles/reports-basics/), [costes por trabajo](https://help.getjobber.com/en/articles/job-costing/).

Open Repair Alliance publica reparaciones comunitarias bajo **CC BY-SA 4.0**. Es útil para estudiar objetos, averías y resultados; su finalidad y estructura no equivalen a presupuestos, horas, materiales, facturas y cobros de un taller comercial. [Datos originales](https://openrepair.org/open-data/downloads/), [estándar de campos](https://standard.openrepair.org/standard.html).

No he localizado en las fuentes revisadas un conjunto público completo que reproduzca ese flujo financiero y operativo de una pequeña empresa de servicios.

**Juicio:** tiene preguntas con posible impacto económico importante, pero es una mala primera elección si queremos depender de datos públicos. Ganaría atractivo con un negocio colaborador que ya registrara costes y horas.

## 6. Negocios que venden productos

### Qué negocios incluye

Bazares, regalos, papelerías, artículos del hogar, jugueterías, accesorios de mascotas, tiendas de ropa, ferreterías y tiendas online. Son candidatos a compartir análisis; no todos deberían entrar en la primera versión.

Flujo: **compra de mercancía → inventario → venta con uno o varios artículos → descuento o devolución → reposición**.

Para empezar basta con entender ventas y devoluciones por producto. Añadir inventario cambia el problema: ahora hay que registrar entradas, salidas, ajustes y disponibilidad.

### Ayuda que propondríamos

- Descomponer una caída de ventas en número de tickets, unidades por ticket y precio medio, cuando los campos lo permitan.
- Detectar qué productos o categorías explican los cambios.
- Analizar devoluciones y descuentos, y combinaciones frecuentes de compra.
- Comparar periodos equivalentes y señalar cierres o datos incompletos.
- Con costes fiables, analizar margen bruto; con stock y movimientos, estudiar rotación y posibles problemas de reposición.

Preguntas de onboarding: «¿Los importes incluyen impuestos?», «¿Cómo aparecen las devoluciones?» y «¿Cada producto tiene un código estable?». Serían preguntas adaptadas a lo detectado en los archivos.

**Ejemplo de límite:** que un artículo deje de venderse puede deberse a falta de existencias, descatalogación o demanda menor. Sin información adicional solo podemos señalar la caída, no afirmar su causa.

### Datos públicos comprobados

Online Retail II ofrece un Excel real con aproximadamente **1,07 millones de líneas**, correspondientes a un vendedor online británico de regalos en 2009–2011, con muchos compradores mayoristas. Su licencia es **CC BY 4.0**. El archivo contiene identificadores de factura y artículo, cantidad, fecha, precio, cliente y país. Permite probar análisis transaccionales; no incluye costes de compra ni histórico de existencias. [UCI, fuente original](https://archive.ics.uci.edu/dataset/502/online+retail+ii).

Es suficiente para empezar a comprobar cálculos y trazabilidad. Sus dos hojas anuales siguen siendo **un solo negocio**, y no prueban que el producto funcione en tiendas físicas actuales.

M5 añade una posible fuente para una fase futura de predicción de ventas minoristas. Su acceso y uso están sujetos a las reglas de la competición; no he validado aquí condiciones para incorporarlo a un producto comercial. [Competición y datos M5](https://www.kaggle.com/c/m5-forecasting-accuracy/data).

### De dónde saldrían los archivos de un cliente

Loyverse permite exportar tickets y tickets por artículo en CSV. Esta segunda opción incluye detalle de precio, descuentos e impuestos: es mucho más próxima a nuestro análisis propuesto que un total mensual. [Exportaciones de Loyverse](https://help.loyverse.com/help/exporting-data-from-loyverse-account).

**Matiz comprobado en la revisión funcional posterior del mismo día:** la documentación de informes de ventas indica límites de histórico y ausencia de exportación de informes en la versión gratuita. Debemos comprobar el plan, el tipo de exportación y los permisos de cada piloto; no asumir que todos los usuarios de un programa pueden obtener gratis cualquier archivo. [Condiciones en el informe por artículo](https://help.loyverse.com/help/sales-item-report-back-office).

Shopify permite exportar pedidos, pero una compra con varios artículos ocupa varias filas y algunos campos de pedido quedan vacíos en las siguientes. Nuestro importador tendría que interpretar esa estructura y evitar duplicar totales. [CSV de pedidos de Shopify](https://help.shopify.com/en/manual/fulfillment/managing-orders/exporting-orders).

### Competencia y valoración

Shopify Sidekick ya puede generar consultas analíticas, gráficos e informes a partir de peticiones en lenguaje natural. El chat no sería por sí solo una diferenciación. [Documentación de Sidekick](https://help.shopify.com/en/manual/ai-powered-tools/sidekick/help-and-guidance).

Nuestra hipótesis de valor sería ayudar al propietario a **entender qué cambió, comprobar la evidencia y priorizar qué revisar**, usando sus archivos y su contexto. Tiene que superar su forma actual de hacerlo. Juntar dos archivos o explicar una cifra de forma agradable solo tiene valor si resuelve una dificultad real.

**Juicio:** mejor base para un prototipo verificable sin contactos. La oportunidad comercial sigue pendiente de validar, especialmente frente al software que ya utilice cada tienda.

## 7. Negocios que cobran cuotas o inscripciones

### Qué negocios incluye

Gimnasios, estudios de yoga y pilates, escuelas de danza, artes marciales, academias y clubes. «Inscripción» a un curso puntual no es lo mismo que una cuota mensual renovable: no asumiríamos que ambos tienen ingreso recurrente idéntico.

Flujo: **alta → plan o curso → cobro → asistencia → renovación, pausa o baja**.

Datos: socios, contratos o matrículas, vigencias, estados, cobros y devoluciones, asistencias y calendario de clases. Para capacidad, aforo e instructor; para resultado económico, sus costes.

### Ayuda que propondríamos

- Señalar miembros con una caída observada de asistencia, con contexto de pausas o vacaciones.
- Mostrar renovaciones y vencimientos, distinguiendo activos, pagadores y usuarios en prueba.
- Comparar ocupación de clases y horarios con su capacidad.
- Examinar retención de grupos que se incorporaron en el mismo periodo.

No etiquetaríamos automáticamente a una persona como «se va a dar de baja» porque lleve dos semanas sin asistir. Al principio ofreceríamos señales descriptivas explicables.

### Datos públicos comprobados y límites

Sport Services contiene datos reales de un centro deportivo de Lisboa, con licencia **CC BY 4.0**. He comprobado **14.942 filas y 47 columnas**. El periodo documentado es 2014–2019. [Repositorio original](https://data.mendeley.com/datasets/yprk4jdgnv/1).

Cada fila resume un usuario; contiene asistencia agregada, periodos de inscripción, valor acumulado y baja. No es un registro de cada visita y cada recibo. Algunas variables describen el final de la relación: usarlas para pronosticar desde una fecha anterior introduciría información del futuro. Para un seguimiento semanal necesitaríamos históricos o reconstrucciones temporales válidas. [Descripción de los autores](https://pmc.ncbi.nlm.nih.gov/articles/PMC8100056/).

TeamUp documenta exportaciones de informes. Un detalle relevante: su informe de asistencias omite a quienes tienen cero asistencias en el periodo. Para detectar a quienes dejaron de ir hay que cruzarlo con el listado de clientes correspondiente. [Informes](https://support.goteamup.com/en/articles/9327463-an-overview-of-reporting), [limitación del informe de asistencias](https://support.goteamup.com/en/articles/9327465-reports-class-attendances-all-attendances).

**Juicio:** alternativa atractiva por la repetición de decisiones y el seguimiento de socios. El dataset público ayuda, pero no elimina la necesidad de un piloto. Empezaría por centros de actividades con una operativa similar, no por cualquier negocio que cobre periódicamente.

## 8. Negocios que reservan o alquilan recursos

### Qué negocios incluye

Pequeños alojamientos, pistas deportivas, salas, estudios, alquiler de bicicletas, vehículos, herramientas o material para eventos. Una habitación se comercializa por noches; una pista, por franjas; una herramienta puede implicar transporte, mantenimiento y devolución física.

Flujo: **disponibilidad → reserva → anticipo → uso → salida o devolución → liquidación**. Se cruzan bloqueos, cancelaciones, mantenimiento y gastos.

Datos: recurso o categoría, fecha de reserva, inicio y fin de uso, estado, tarifa, importe, canal y capacidad disponible. Los costes y comisiones hacen falta para hablar de rentabilidad.

### Ayuda que propondríamos

- Analizar cancelaciones y anticipación de reserva.
- Comparar canales y tipos de recurso, descontando comisiones si se conocen.
- Detectar periodos de utilización baja respecto a la disponibilidad efectiva.
- Estudiar rendimiento de recursos, sin confundir ingresos con retorno neto de la inversión.

### Datos públicos comprobados y límites

Hotel Booking Demand contiene **119.390 reservas de dos hoteles portugueses**, llegadas previstas entre 2015 y 2017. He comprobado sus CSV originales: 40.060 y 79.330 filas, con 31 columnas cada uno. Incluyen cancelaciones, estancias, canales y tarifa media. El artículo se publica bajo **CC BY 4.0** y enlaza los datos suplementarios. [Artículo original](https://doi.org/10.1016/j.dib.2018.11.126).

Es una base útil para análisis hotelero, pero los archivos no contienen un calendario completo de capacidad vendible y costes. Tampoco deben usarse estados finales para simular predicciones que se habrían hecho al reservar. No extrapolaría sus patrones a alquileres de herramientas.

Inside Airbnb ilustra otra trampa: una fecha no disponible puede estar reservada o bloqueada por el propietario. No permite deducir directamente ingresos u ocupación real. [Limitaciones declaradas por Inside Airbnb](https://insideairbnb.com/data-assumptions/).

Booqable documenta informes y exportaciones para alquileres. Cloudbeds dispone de informes hoteleros y de exploración mediante lenguaje natural. El competidor de nuestro informe puede estar dentro del programa de gestión del cliente. [Booqable](https://help.booqable.com/en/articles/1354239-getting-started-with-reports-and-exports), [Cloudbeds](https://myfrontdesk.cloudbeds.com/hc/en-us/articles/41695559811611-Cloudbeds-Reports-Hotel-Reporting-for-Operational-Financial-Revenue-Occupancy-Analysis).

**Juicio:** una de las mejores fuentes para una demostración con datos reales; convendría elegir un subtipo de recurso. No es el camino más sencillo hacia un producto común para todos los pequeños negocios de reservas.

## 9. Catálogo de datos y estado de comprobación

Las licencias indicadas son las declaradas por las fuentes consultadas. No se ha usado la licencia de una copia de terceros para sustituir la de la fuente original.

| Fuente | Estado en esta investigación | Uso razonable para Decision Room | Límite principal |
|---|---|---|---|
| Online Retail II — UCI | Descargado; estructura y muestra de cada hoja inspeccionadas | Cálculos de ventas, archivos por periodos, trazabilidad a líneas | Un único negocio histórico; sin costes ni stock |
| Sport Services — Mendeley | CSV completo leído para comprobar estructura | Análisis descriptivo por socio, lectura de campos y contexto | Resumen por persona, no historial de eventos completo |
| Hotel Booking Demand — autores | Dos CSV originales leídos para comprobar estructura | Análisis histórico de reservas y cancelaciones | Dos hoteles; sin calendario completo de capacidad |
| Open Repair Alliance | Documentación y esquema revisados; archivo no inspeccionado | Resultados de reparación, categorías, interpretación de campos | Reparación comunitaria, no rentabilidad comercial |
| Medical Appointment No Shows — autor | Ficha y licencia revisadas; archivo no inspeccionado | Referencia académica sobre citas | Ámbito médico y licencia no comercial |
| M5 — competición original | Ficha revisada; sin descarga ni revisión completa de reglas | Investigación futura de predicción de ventas | Condiciones específicas y contexto distinto a una pequeña tienda |

**No todos estos conjuntos son adecuados para una demo comercial.** Los tres archivos inspeccionados permiten comenzar experimentos concretos; cada experimento debe limitarse a lo que sus campos realmente representan.

## 10. Hasta dónde especializarnos

Propondría tres capas:

1. **Motor común:** carga, calidad de datos, cálculos, gráficos, trazabilidad y preguntas.
2. **Modelo operativo:** ventas por producto, citas, trabajos, cuotas o reservas; fija entidades y métricas.
3. **Contexto del negocio:** sector, horarios, estacionalidad, promociones, objetivos y excepciones recogidos en onboarding.

Esto permite servir a más de un sector sin pedirle a la IA que invente las reglas de cada negocio. Conocer qué significa una columna no garantiza que contenga toda la información necesaria.

### Familia inicial propuesta: comercio de productos no perecederos

**Incluir al principio:** reventa de productos no perecederos y una única ubicación o canal sencillo, con registros básicos o detallados. Sectores candidatos: regalos, bazar, hogar, papelería y accesorios. Los identificadores y unidades estables permiten profundizar por artículo; no son necesarios para toda lectura agregada. Ferretería o moda pueden entrar si los análisis elegidos pueden interpretar correctamente sus unidades y variantes.

**Posponer:** elaboración de productos, restauración, venta a peso, perecederos, lotes y caducidades, consignación y operaciones complejas de múltiples almacenes. No se trata de que sean imposibles: añaden decisiones y campos que no necesitamos para comprobar la primera hipótesis.

Un bar o restaurante no debe entrar automáticamente porque «vende productos»: los costes pueden depender de recetas, porciones, desperdicio y compras de ingredientes. Compartir el cálculo de ventas no equivale a resolver su gestión.

### Requisitos según la pregunta que se quiera responder

No se exige un conjunto universal de columnas. Cada investigación necesita información suficiente y de significado comprensible:

- Evolución: periodos, importes y cobertura interpretable.
- Análisis por producto: identificación consistente de artículos y ventas asociadas.
- Cesta e importe por compra: detalle agrupable por ticket o una tabla de compras equivalente.
- Devoluciones, descuentos e impuestos: tratamiento definido para evitar duplicar ajustes.
- Repetición de compradores: identificadores apropiados y cobertura conocida.
- Costes o existencias: vigencia, relaciones y medidas suficientes para el análisis adicional concreto.

El sistema pide información adicional si mejora una investigación disponible. Si el dueño no la aporta, adapta el plan; no fabrica campos o conclusiones para completar una plantilla. No se confunde falta de datos con una capacidad aún inexistente.

Unos pocos meses pueden bastar para una primera lectura descriptiva si hay suficiente actividad. Comparar estacionalidad anual requiere cubrir periodos equivalentes; ni siquiera un año garantiza una predicción útil. El sistema debe mostrar qué cobertura tiene cada conclusión.

## 11. Cómo comprobar la utilidad antes de ofrecer el servicio

### Fase A. Pruebas internas con datos públicos

1. Definir una guía de preguntas y varios escenarios: totales agregados, productos sin tickets, tickets completos y datos enriquecidos. Especificar qué puede concluirse en cada caso y qué no.
2. Construir resultados de referencia mediante cálculos reproducibles, separados del texto que redacte la IA.
3. Exigir que cada cifra del informe y del chat pueda rastrearse al archivo, periodo y cálculo correspondientes.
4. Introducir copias alteradas deliberadamente: columnas renombradas, duplicados, fechas ambiguas, devoluciones, importes con impuestos y periodos incompletos. Etiquetarlas como pruebas artificiales.
5. Comprobar preguntas sin datos suficientes: beneficio sin costes, roturas de stock sin existencias o causalidad sin evidencia. La respuesta correcta debe reconocer qué falta.
6. Separar periodos de prueba y formatos desconocidos. Dividir un negocio en varias muestras comprueba robustez, pero no valida varios sectores.
7. Probar que el plan cambia con información nueva, que continúa cuando se rechazan datos opcionales y que verifica las investigaciones adicionales. Evaluar también coste, tiempo y criterios de parada.

El primer criterio de salida sería consistencia numérica y trazabilidad, incluyendo casos vacíos o ambiguos; después evaluaríamos claridad y priorización. Un informe convincente con cifras erróneas no pasa.

### Fase B. Pilotos de diseño, antes de vender

Propuesta práctica, no umbral estadístico: conseguir **3–5 comercios independientes de 2–3 sectores cercanos**, y realizar al menos dos ciclos de carga y análisis.

Comprobaríamos:

- Qué archivo consiguen exportar realmente y cuánto acompañamiento requieren.
- Qué parte de la interpretación es común y qué exige reglas específicas de cada negocio.
- Si entienden las conclusiones y pueden verificar las cifras.
- Si el informe responde una pregunta que les importa y que su herramienta actual no resuelve satisfactoriamente.
- Si una segunda carga produce valor nuevo y mantiene el contexto.
- Si quieren continuar y bajo qué condiciones; no confundir interés cortés con disposición a pagar.

Al no tener contactos, el reclutamiento es una incertidumbre real. Se puede intentar por comercios locales, asociaciones o profesionales que lleven su gestión; aquí no se ha contactado a nadie ni comprobado tasas de respuesta. Probar el acceso a propietarios debe ocurrir antes de invertir mucho en conectores o predicción.

### Señales para mantener o cambiar la elección

- **Mantener comercio:** distintos establecimientos exportan datos utilizables y reconocen decisiones concretas en los análisis.
- **Acotar más:** el núcleo funciona, pero las preguntas útiles se concentran en un subtipo o un software.
- **Cambiar de familia:** los datos accesibles no sostienen la promesa, los informes existentes ya bastan, o otra familia ofrece mejores colaboradores y problemas repetidos.

## 12. Consecuencias para el UX ya definido

El flujo del producto ampliado sigue encajando: explicar el negocio → subir archivos → evaluar y adaptar el plan → aclarar o aportar datos opcionales → recibir resultados verificados → explorar con chat y descargar PDF. La primera entrega se detiene en el informe de una página, según el MVP vigente.

La investigación sugiere concretar tres elementos:

1. **Empezar con lo que hay y pedir lo que aporta valor.** Aceptar datos agregados o detallados; solicitar información adicional para una investigación pertinente y disponible, y continuar si no se aporta.
2. **Mostrar cobertura de forma comprensible.** Por ejemplo: «Podemos analizar ventas y devoluciones. Para conocer el margen falta el coste de compra».
3. **Separar hallazgo, interpretación y siguiente comprobación.** Una bajada medida, una explicación posible y una acción propuesta deben aparecer como cosas distintas.

Esto mantiene el alcance de Excel/CSV y experiencia de usuario. Conectores, automatización periódica y modelos predictivos continúan en fases posteriores. Una guía corta para exportar desde uno o dos programas podría ser un experimento posterior de reducción de fricción.

## 13. Decisión recomendada

**Construir y probar primero el núcleo de Decision Room para comercios de productos no perecederos, adaptando el análisis a datos básicos o detallados. Validar con una pequeña diversidad de pilotos qué profundidad aporta valor, cuánto contexto necesita cada sector y si las investigaciones autónomas siguen siendo comprobables.**

La pregunta comercial pendiente no es si podemos producir gráficos: es si un propietario obtiene una explicación fiable y una decisión útil con menos esfuerzo que con su proceso actual.

### Evidencia local reproducible

- Script de inspección: `scripts/datasets/inspect_public_data.py`.
- Comercio: `docs/research/2026-09-17/public_data_inspection.json`.
- Centro deportivo: `docs/research/2026-09-17/sport_data_inspection.json`.
- Hoteles: `docs/research/2026-09-17/hotel_data_inspection.json`.
- Descargas originales y atribución: `docs/research/2026-09-17/README.md`.
