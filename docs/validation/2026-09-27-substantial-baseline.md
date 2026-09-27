# Paso 3.1 — referencia inicial con varias tablas

**Estado: paso 3.1 completado como medición inicial, 27 de septiembre de 2026.**
Cuatro recorridos aceptados de seis; los dos fallos se conservan. La comprobación
adicional de recuperación también terminó y queda separada de la matriz inicial.
Esto no declara resueltos los fallos ni aprobada la ampliación a datos de clientes.

## Qué se midió

Aplicar el recorrido actual a un caso sustancial antes de construir la memoria de
datos del paso 3.2. Se fijó un [protocolo](../technical/substantial-baseline-plan.md)
antes de ejecutar: tres objetivos, dos repeticiones independientes, definiciones
de negocio explícitas y referencias ocultas al modelo. La aprobación del revisor
del producto y la aceptación independiente se registran por separado.

No se modifican los prompts, los agentes ni los presupuestos del producto durante
la medición. El ejecutor y el oráculo son herramientas de evaluación.

## Datos y condiciones

Se usan los CSV completos de [Wide World Importers](../../data/wide-world-importers/README.md),
negocio ficticio de Microsoft:

| Tabla | Filas |
|---|---:|
| Sales.Invoices | 70.510 |
| Sales.InvoiceLines | 228.265 |
| Sales.Customers | 663 |
| Sales.CustomerCategories | 8 |
| Warehouse.StockItems | 227 |
| Total | 299.673 |

Los cinco archivos ocupan 77.867.407 bytes. El análisis compara fechas de factura
de 2014 y 2015, con 137.839 líneas en ese intervalo. Se conservan todas las fechas
en las entradas para que el agente tenga que seleccionar el periodo.

- Código de producto congelado en `f0c26279ad6829cf3570bf5d4205cd4fd5b92b20`,
  más `substantial.py` y `substantial_data.py` de esta entrega. Se excluyen cambios
  concurrentes sin guardar. Se conservan hashes del código, esquema SQL y entradas.
- GPT-6 Luna, protocolo OpenAI, razonamiento `low`, 16.384 tokens máximos de salida
  y 300 segundos de plazo por llamada, conforme a la configuración local.
- PostgreSQL separado y almacenamiento privado; Python del modelo en el runtime
  Docker existente, cuya imagen y configuración quedan registradas.
- Dos investigaciones y 30 segundos de Python por ejecución, cuatro rondas de
  revisión. Fases ejecutadas en procesos separados.
- La elección de objetivo se introduce en el contexto del propietario. No se
  evalúa una interfaz de onboarding que aún no existe, ni la edición del dashboard.

## Referencia independiente

El controlador calcula con CSV y Decimal, antes de la primera llamada al modelo,
claves y correspondencias, agregados anuales/mensuales y desgloses por producto,
cliente y categoría actual. El modelo solo recibe datos y definiciones, nunca los
resultados esperados, la rúbrica ni la base de referencia.

Una segunda comprobación con SQL de DuckDB sobre los CSV originales coincidió
exactamente en **10.626 valores agregados** de cinco dimensiones y seis medidas.

| Métrica | 2014 | 2015 |
|---|---:|---:|
| Ventas sin impuestos | 49.929.487,20 | 53.991.490,45 |
| Margen bruto en importe | 24.828.462,45 | 26.957.600,65 |
| Margen bruto / ventas sin impuestos | 49,7271 % | 49,9294 % |
| Facturas | 20.303 | 22.250 |
| Importe medio sin impuestos por factura | 2.459,22 | 2.426,58 |

Importes en unidades monetarias de la fuente; no se atribuye una moneda que el
contexto no especifica. El margen bruto no incluye gastos generales.

Las ventas crecen 8,1355 %, el margen bruto 8,5754 %, y la tasa de margen aumenta
0,2023 puntos porcentuales. El importe medio por factura baja 1,3270 % mientras
crece el número de facturas. Son referencias del evaluador, no afirmaciones de
que todos los informes hayan descubierto esas relaciones.

Entre los contrastes para evaluar descubrimiento: Novelty Shop aporta
2.056.069,55 al crecimiento de ventas sin impuestos y 1.114.657,95 al de margen;
el producto «20 mm Double sided bubble wrap 50m» aporta 370.440,00 y 315.560,00,
respectivamente. «10 mm Anti static bubble wrap (Blue) 10m» pierde 27.180,00 de
margen bruto. Comprobar tanto hallazgos encontrados como oportunidades omitidas.

## Resultados por recorrido

| Recorrido | Resultado inicial | Segundos de fases | Llamadas | Ejecuciones Python | Ejecuciones fallidas | Peticiones de revisión |
|---|---|---:|---:|---:|---:|---:|
| Organizar 1 | Aceptado | 127,886 | 12 | 4 | 1 | 1 |
| Organizar 2 | Aceptado | 141,674 | 14 | 4 | 1 | 2 |
| Descubrir 1 | Aceptado, con límites de utilidad | 192,269 | 16 | 6 | 2 | 2 |
| Descubrir 2 | Fallo de consulta de contexto | 179,868 | 17 | 6 | 2 | 3 |
| Pregunta concreta 1 | Aceptado | 174,111 | 16 | 4 | 0 | 3 |
| Pregunta concreta 2 | Fallo del proveedor, HTTP 503 | 113,512 | 11 | 4 | 1 | 1 |

- **Finalización y aceptación independiente: 4/6.** Los cuatro informes publicados
  coinciden con la referencia en las 198 comprobaciones numéricas y tres de nombres
  realizadas sobre métricas citadas y todos los puntos de sus gráficos. También se
  revisaron narrativa, redondeos, rankings, unidades, alcance y correspondencia con
  el objetivo. Los borradores de los dos fallos no se cuentan como entregas.
- **Recuperación: 4/4 informes aprobados** reabiertos y reanudados desde otro
  proceso sin llamadas ni ejecuciones adicionales. Código estable en los seis casos.
- **Preguntas al propietario: cero** en los seis recorridos. El contexto inicial
  ya proporcionaba las definiciones; este resultado no prueba que un onboarding
  con respuestas incompletas funcione igual.
- **Recursos iniciales:** 86 llamadas, 28 ejecuciones de Python y siete ejecuciones
  fallidas, conservadas. Suma de tiempos de fases: 929,320 segundos, aproximadamente
  15 minutos y 29 segundos; excluye el cálculo de referencia y la revisión independiente.
- **Tokens conocidos:** 2.475.960 de entrada y 128.401 de salida. Una llamada fallida
  no informó uso: los totales exactos quedan desconocidos. La entrada incluye
  tokens en caché y no equivale directamente a coste facturado. Prompts:
  `planning-v9`, `research-v10` y `review-v13`.

### Utilidad y cobertura

**Organización:** ambas repeticiones entregaron totales anuales, importe medio por
factura y las series de ventas y margen por mes y categoría. En ambos casos el
revisor pidió completar visualizaciones de margen; en el segundo exigió comprobar
si había facturas sin líneas antes de aceptar el denominador del promedio.

**Descubrimiento 1:** encontró el producto con mayor aumento de importe con impuestos,
el de mayor caída de margen y la concentración del crecimiento en Novelty Shop.
Los importes y extremos son correctos y están acotados a los productos comparables.
Dos etiquetas quedaron como «Product 180/184»: el código construyó series con
nombres, pero no las incluyó al guardar el resultado. La entrega es útil para una
primera revisión, con explicaciones poco profundas y recomendaciones generales.
No cuantifica cuotas del crecimiento ni explora precio, coste o mezcla; omite el
segundo mayor contribuyente de ventas al seleccionar una unión de extremos.

**Pregunta concreta 1:** respondió los cambios de ventas y margen en importe,
el cambio de 0,20 puntos porcentuales y los mayores contribuyentes por producto y
categoría. Los cuatro gráficos mostraron cinco mayores aumentos por producto y
todas las categorías. Necesitó tres solicitudes de revisión, dos relacionadas con
expresar explícitamente el cambio de tasa. No investiga causas comerciales ni
muestra contribuciones negativas en la entrega final.

**Descubrimiento 2 y pregunta concreta 2:** conservaron cálculos y borradores, pero
no completaron la entrega. Sus causas son distintas; no atribuir el HTTP 503 a un
error aritmético ni tratar los borradores como informes aprobados.

### Recuperación adicional del HTTP 503

Tras cerrar la matriz inicial, se inició una única recuperación explícita en el
mismo checkpoint, conservando intactos sus archivos y resultado fallido. El estado
de la llamada era `failed/ModelAPIError`, con respuesta HTTP 503, no una llamada de
resultado incierto. El seguimiento se guarda aparte en `recovery-503`; su resultado
no reemplaza el 4/6 inicial.

La recuperación duró 27,762 segundos, hizo tres llamadas adicionales y no repitió
ninguna ejecución de Python. Superó la llamada HTTP fallida y avanzó en el borrador,
pero terminó sin aprobación: el analista pidió `open_report` con identificador
vacío y se produjo `badly formed hexadecimal UUID string`. La respuesta y el
estado de fallo se conservan aparte; no se hicieron más reintentos.

Por tanto, se comprobó la recuperación del checkpoint y la conservación de los
cálculos, pero **no** la entrega final tras el error del proveedor. El segundo
fallo confirma que las peticiones de herramientas inválidas necesitan validación
y corrección acotada. Es un defecto del producto distinto del HTTP 503 inicial.

## Fallos y límites identificados

### Petición de contexto inválida que termina una revisión

En `discover-2`, el modelo produjo `action="retrieve"` con `retrieval=null`.
El esquema permite esa combinación, pero `memory.retrieval.Request` requiere un
objeto. `agent.persistence.model_call` llama a `retrieval.save` antes de entrar
en el bucle de corrección de acciones de `review_graph.decide`: la validación
lanza una excepción y la revisión termina como fallida. No se publica el borrador.
Se conserva la respuesta original en `failure-output.json` del recorrido.

Corrección prioritaria antes de ampliar la consulta de memoria en 3.2: validar la
petición antes de despacharla, devolver al modelo un error corregible con un
presupuesto acotado, y probar petición nula, identificador vacío o mal formado y
recuperación. Diferenciar requisitos de búsqueda y apertura: `open_report`
necesita un identificador válido y autorizado; no sirve para abrir el borrador
actual que el agente ya recibe en su contexto. No volver
a ejecutar automáticamente una llamada cuyo resultado sea incierto. Este fallo
queda medido, no corregido ni ocultado con un reintento en la matriz inicial.

### Qué debe cambiar en los siguientes pasos

1. **3.2 — Relaciones y columnas persistentes.** En distintas ejecuciones se
   intentó leer CustomerCategoryName desde Customers, aunque pertenece a
   CustomerCategories. Un catálogo consultable debe conservar entidad, columna,
   claves y recorrido de unión, con nombres visibles de productos y categorías.
   Las comprobaciones de cardinalidad deben ser reutilizables y revalidarse con
   nuevas versiones de datos. En esta base limpia los resultados coincidieron;
   eso no demuestra que todas las ejecuciones comprueben todas las relaciones.
2. **3.2 — Definiciones explícitas de métricas.** El objetivo de descubrimiento
   eligió ExtendedPrice con impuestos, mientras organización y pregunta concreta
   emplearon ventas sin impuestos. La primera elección puede ser válida si se
   etiqueta claramente, pero revela que «ventas» no tiene una definición estable
   compartida. Guardar base, unidad y fórmula evita comparaciones incompatibles.
3. **3.3 — Profundización y comprobaciones.** La selección de extremos encuentra
   algunos cambios relevantes, pero deja fuera contribuyentes importantes y no
   investiga necesariamente precio, coste, mezcla o composición de segmentos.
   Evaluar qué aporta una ronda adicional, con presupuesto y evidencia.
4. **3.5 — Presentación y revisión.** Se repitieron correcciones por gráficos
   incompletos. El límite de cuatro gráficos provocó alternancia entre desgloses
   por producto y categoría. Preparar comparaciones compactas y evidencia adecuada
   para los hallazgos, sin obligar al revisor a resolver el diseño por ensayo.
   En un caso se retiró una afirmación correcta sobre la categoría líder porque
   la evidencia citada era solo el número de categorías; mejorar la vinculación
   de comparaciones y series con afirmaciones, manteniendo la verificación.

También hubo errores de sintaxis SQL y Python que el propio agente corrigió.
La memoria de relaciones puede ayudar con columnas y uniones, pero no elimina
por sí sola esos errores de código. Conservar casos de regresión y medir los
intentos necesarios antes de atribuir una mejora a la nueva arquitectura.

## Evidencias y reproducción

Ejecutor: [substantial.py](../../decision_room/evaluation/substantial.py).
Referencia independiente: [substantial_data.py](../../decision_room/evaluation/substantial_data.py).
Pruebas: [test_substantial_evaluation.py](../../tests/test_substantial_evaluation.py).

Artefactos privados en `.local/evaluation/substantial-31/batch/`: manifiesto,
procedencia, hashes, referencia, contraste SQL, estados, preguntas, planes,
investigaciones, código generado, resultados, revisiones, exportaciones, tiempos,
tokens y evaluaciones independientes. La copia fija de ejecución se conserva en
la carpeta `source` del mismo experimento. La base de evaluación permanece
separada de la aplicación para poder inspeccionar y recuperar sus evidencias.

Los archivos descargados y las salidas extensas no se incorporan a Git. El coste
monetario queda desconocido: se conserva el uso de tokens, sin inventar precios.

## Comprobaciones y cierre

- 20 pruebas pasan con `python -m unittest tests.test_substantial_evaluation
  tests.test_evaluation tests.test_evaluation_resources`. Las cuatro nuevas prueban
  granularidad por factura, impuestos, signos negativos, periodos, contribuciones,
  claves duplicadas y referencias inexistentes incluso fuera del periodo objetivo.
- Los dos módulos nuevos compilan; coinciden byte a byte con la copia ejecutada.
- Seis estados terminales, seis evaluaciones independientes y fuentes estables;
  los cuatro aceptados conservan todas sus comprobaciones y recuperación correcta.
- Enlaces locales y diff comprobados; revisión de archivos para no incluir
  credenciales, rutas personales, datos descargados ni salidas privadas.

**Cierre de 3.1:** hay una referencia reproducible, resultados medidos, fallos
identificados y prioridades concretas para 3.2. El producto aún necesita corregir
la validación de herramientas y mejorar consistencia, eficiencia y profundidad.
Las próximas mejoras se contrastarán con esta matriz original, sin sustituirla.

## Límites de esta evaluación

- Dos repeticiones por objetivo y un único negocio ficticio con estructura limpia;
  no demuestran generalización a datos de clientes reales.
- Definiciones explícitas; no se simula una conversación humana completa ni se
  evalúa aquí la capacidad de obtenerlas durante el onboarding.
- Cinco tablas, no las 48 del conjunto completo. Selección entre muchas tablas y
  resistencia a cambios de esquema siguen pendientes.
- Recuperación de trabajo aprobado entre procesos; no se simula una caída en
  mitad de una llamada al proveedor ni se reintenta una llamada incierta.
- La evaluación independiente revisa cálculos, evidencia y contenido del informe;
  no incluye un estudio con usuarios ni nuevas pruebas visuales de la interfaz.
