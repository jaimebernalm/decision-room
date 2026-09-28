# Validación de 3.5 — Investigación dirigida en paralelo

## Alcance

Mismo Bruma Café sintético, archivos originales de 3.4.1 y definición monetaria
sin confirmar. La referencia aprobada de 3.4.1 queda conservada en almacenamiento
local. No se han introducido resultados esperados en las instrucciones del agente.

Las repeticiones de desarrollo siguientes no son una prueba estadística de mejora
ni permiten atribuir una reducción de tiempo al paralelismo. La comparación amplia,
con varios objetivos, datasets y repeticiones, corresponde a 3.6.

## Problemas encontrados y corregidos durante el desarrollo

1. El ejecutor tenía un bloqueo global de una sola ejecución. Se sustituyó por
   admisión de hasta tres contenedores, conservando aislamiento y recuperación.
2. Un intento volvió a pedir confirmar cantidades ya incluidas en el alcance
   aceptado y no profundizó. Ahora se distingue la comparación descriptiva
   autorizada de una definición monetaria realmente ambigua.
3. Otro encadenó desgloses independientes y consumió profundidad innecesaria.
   Las ramas independientes pueden ser hermanas dentro de la misma ronda.
4. El contrato solo reconocía dependencias de preguntas al propietario; rechazó
   seguimientos que dependían legítimamente de un candidato anterior. Se amplió
   el contrato sin convertir evidencia calculada en confirmación del propietario.
5. Los trabajadores podían proponer seguimientos, pero el principal no podía
   abrirlos después de leer sus entregas. `expand` cubre ese punto de decisión.
6. Al retirar `execute` del coordinador, un intento interpretó erróneamente que
   Python no estaba disponible. Se hizo explícito que su herramienta es
   `delegate`; una tarea lista debe resolverse o descartarse explícitamente.
7. Una revisión detectó un nombre de producto mal asociado a un ID y agotó sus
   rondas tras reparos adicionales. Las instrucciones exigen guardar nombres
   junto a los valores mediante uniones comprobadas y revisar procedencia desde
   la primera ronda. Los datos sintéticos permiten priorización dentro del
   escenario, con límites visibles; no acreditan actividad comercial real.
8. Una actualización local de las columnas de telemetría durante una espera
   produjo un error de esquema en el sexto intento. Se aplicó la migración y
   se reanudó la misma tarea, conservando su llamada y asignación ya guardadas.

Todos los intentos se conservan localmente, incluidos informes limitados,
resultados sin la profundidad deseada y revisiones no aprobadas.

## Verificación automatizada

Pruebas con PostgreSQL y Docker reales y modelos guionizados para los controles:
concurrencia, modo secuencial, cuotas globales, límites de contenedores, aislamiento
por negocio, dependencias, propuesta de seguimientos, expansión del principal,
fallo de una rama, recuperación antes del checkpoint y después de la unión,
no duplicación, síntesis y rechazo de contradicciones pendientes.

- Batería de regresión: **111 pruebas backend correctas** (investigación,
  controles paralelos, revisión, fuentes/series, exportación y servicio web).
- Tras el último ajuste de selección de series: **38 pruebas específicas** de
  referencias, revisión, contexto, series y entrega correctas. Los grupos se
  solapan; no se suman como si fueran casos distintos.
- Controles finales del coordinador, recuperación y presupuestos: **31 pruebas
  correctas**, incluidas decisiones `finish` de trabajadores y recuperación tras
  unión o respuesta del modelo guardada antes del checkpoint.
- Frontend: **78 pruebas correctas**; build correcto; lint sin errores, con los
  avisos existentes de Fast Refresh. `git diff --check` correcto.
- Comprobación visual en la aplicación: hallazgo prioritario primero, gráfico
  correcto de contribuciones y tablas asociadas, valores visibles y estado revisado.

## Resultado de Bruma

Cuatro encargos en tres rondas: exploración, producto/canal en paralelo y después
productos dentro de Tienda física. Las dos ramas independientes se solaparon
**13,21 segundos**. No se fuerza un número de agentes: se eligen desde la agenda.
La investigación utilizó **14 llamadas y 5 ejecuciones Python**; una ejecución
produjo demasiadas series y fue corregida dentro de su cuota. Se conservó ese fallo.

El informe final prioriza Tienda física: pasa de **599 a 528 unidades** entre
junio y agosto (**−71**). Desglosa las contribuciones por producto: Café de la casa
**−24**, Café de origen **−15**, Filtros **−15**, Kit **−10**, Descafeinado **−9**,
Molino **+2**. Incluye evolución mensual de los tres productos con mayores cambios
absolutos y el contraste de canales. No atribuye causas ni inventa márgenes.

Un cálculo independiente con `csv`, `Decimal` y acumuladores, leyendo las fuentes
originales y sin ejecutar el código del agente, verifica **50 métricas y 60 valores
de series**. Los datos contienen **1.656 filas y 5.975 unidades**. Coinciden los
**36 valores visualizados** y las **34 referencias de los cuatro hallazgos**;
los **12 controles mecánicos** pasan y las proyecciones web, HTML y chat resuelven
la evidencia actual.

La comprobación independiente cuenta **30, 31 y 31 fechas observadas**. Tienda
física pasa de 19,9667 unidades por fecha observada en junio a 17,0323 en agosto:
la dirección de la caída se mantiene al considerar esa exposición. **El informe
entrega totales, no estas tasas**; tampoco certifica días de apertura ni cobertura
completa. Automatizar y evaluar de forma consistente la selección de estas
comparaciones sigue siendo un criterio de 3.6.

## Revisión, tiempos y consumo

La investigación final duró **126,92 s** entre la primera llamada y la última,
incluyendo la interrupción local de esquema y su recuperación. No usar `updated_at`
como duración: consultar de nuevo una investigación terminada puede actualizarlo.

Sobre sus mismos cálculos hubo una revisión aprobada inicial (6 llamadas, 85,67 s),
una nueva entrega priorizada que agotó sus rondas (10 llamadas, 177,86 s) y un
reintento aprobado (2 llamadas, 39,97 s). La nueva entrega añadió un cálculo mensual
por producto en revisión, retenido en el reintento final. No se ocultan esos costes.

El agotamiento mostró un defecto de selección: al generar la unidad antes de la
serie, la salida estructurada podía quedar limitada a la serie anterior aunque el
mensaje afirmase corregirla. Se corrigió el orden del esquema para elegir evidencia
antes que unidad, manteniendo sus parejas válidas. Tras ese cambio el mismo trabajo
se recuperó y aprobó en **una ronda**, sin nuevos cálculos. La síntesis ordena los
hallazgos por los enlaces explícitos a las preguntas priorizadas, antes de aprobación.

Investigación y **todas esas revisiones** suman **32 llamadas**, **1.139.728 tokens
de entrada** y **59.245 de salida** (1.198.973 en total, incluidas entradas repetidas;
no equivalen a tokens facturados sin caché). Los cinco recorridos anteriores de
desarrollo se conservan aparte y no están incluidos en esta cifra. No se afirma
que 3.5 sea ya más rápido o más barato.

## Cierre y límites

3.5 queda completado como capacidad integrada y comprobada. Las prioridades y la
profundización son decisiones del agente; el código limita concurrencia, valida
referencias y conserva evidencia. No hay especialistas con temas de negocio
hardcodeados ni conversación recursiva entre trabajadores.

El resultado supera la referencia en profundidad del canal que cae y en orden de
presentación. Sigue habiendo variación entre intentos y coste elevado de contexto y
revisión. La densidad de algunas tablas y la repetición parcial entre hallazgos
requieren evaluación de utilidad en 3.6; esta prueba no demuestra calidad general
ni sustituye esa evaluación. La referencia de 3.4.1 permanece intacta.
