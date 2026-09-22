# Errores conocidos del agente

## DR-001: supuesto monetario atribuido al propietario

**Estado: abierto; conservar al evaluar los pasos 1.5 y 1.6.**

Caso: `data/reference-cases/03-ambiguous-amount/input/`. Una fila con cantidad 4
e importe 25 puede representar 100 si el importe es precio unitario o 25 si es
total de fila. El propietario define unidades, impuestos y descuentos, pero no
esa base monetaria.

`qwen3.8-27b-splash`, con el prompt de planificación v2, asumió total de fila,
lo marcó como confirmado por el propietario y propuso sumar `amount` sin preguntar.
El fallo se observó con razonamiento desactivado y activado. No hubo un cálculo
ejecutado en aquella prueba. Ver [evidencia registrada](2026-09-21-agent-check.md).

La autorización del usuario para continuar permite construir y evaluar Python y
el revisor sin cerrar este fallo. No significa que la interpretación sea aceptable.

Comportamiento esperado del sistema completo:

- Reconocer la ambigüedad y pedir la definición antes de aceptar el total afectado.
- Si el principal omite la pregunta, el revisor debe detectar que la supuesta
  confirmación no está en el contexto original y devolver el trabajo.
- Ante precio unitario, calcular cantidad por precio; ante total de fila, sumar
  una vez; ante respuesta desconocida, mantener pendiente ese total y continuar
  con las unidades cuando sea posible.
- No considerar aprobado un resultado porque Python terminó sin errores o porque
  dos modelos están de acuerdo. Conservar las fuentes y las respuestas originales.

El cálculo independiente de referencia y las respuestas de evaluación permanecen
fuera del contexto del agente. Variar nombres de columnas y las respuestas para
evitar resolver únicamente este archivo concreto.

## Evidencia del revisor en el paso 1.6

En una prueba adversarial se inyectó DR-001 en el plan, candidato y primer borrador.
Qwen como revisor detectó la confirmación inexistente y devolvió el trabajo dos
veces. El analista pidió la definición, se pausó y retomó desde otro proceso. Con
la respuesta de referencia «precio unitario», recalculó 1.220,00 y 59 unidades; el
revisor aprobó el informe basado en esa evidencia nueva. El resultado anterior
quedó obsoleto.

Esto es una mitigación observada, no el cierre de DR-001: el inicio fue un fixture
con fallo deliberado y no una demostración de que el principal ya lo evita. Se
conservan también los intentos donde Qwen detectó la ambigüedad pero incumplió el
contrato de acciones. Ver [método, resultados y límites](2026-09-21-review-check.md).

## DR-002: el revisor aprueba cifras no calculadas y contradice el contexto

**Estado: abierto; informe de prueba bloqueado por comprobación independiente.**

En el caso de ventas diarias, el analista escribió +16,13 % para el cambio del
promedio diario sin guardar ese porcentaje como métrica. El revisor lo aprobó.
La operación `(3303,85 / 2844,82 - 1) * 100` da aproximadamente 16,135643 %, que
redondea a 16,14 %. El informe también afirmó que faltaba información sobre
impuestos/descuentos, aunque el contexto original define ventas sin impuestos
y con descuentos ya reflejados.

Los controles de referencias y contadores pasaban; no validaban esas frases.
Añadir un revisor con el mismo modelo no resolvió este fallo. El informe mantiene
la aprobación histórica del modelo, pero `review-hold` lo deja no publicable.

Antes de aceptar el recorrido: ampliar la evaluación y las comprobaciones de
cifras derivadas en el texto, exigir trazabilidad de sus cálculos y evaluar otro
modelo/revisor. No basta con añadir otra instrucción al prompt ni con que ambos
roles coincidan. Ver [prueba completa](2026-09-21-review-check.md).

## DR-003: mediana incorrecta con un número par de observaciones

**Estado: abierto; observado en métricas auxiliares de la prueba del informe del cliente.**

Qwen generó `sorted(vals)[len(vals)//2]` como mediana de doce ventas diarias.
Ese cálculo toma el elemento central superior; la mediana convencional es el
promedio de los dos centrales. Guardó 2.536,00 y 3.207,65 en vez de 2.491,30 y
3.185,13 redondeados. La discrepancia se detectó comparando con el CSV mediante
Decimal y `statistics.median`, fuera del contexto del modelo.

El primer borrador que intentaba utilizar estas cifras era JSON mal formado y
no obtuvo aprobación. No se atribuye al revisor la detección estadística: ese
intento se detuvo antes de completar la revisión. Incluir este caso en la evaluación
1.7. Ver [validación del informe del cliente](2026-09-21-client-report-check.md).

## Observaciones de la calibración del paso 1.7

Los nuevos controles exigen que cada porcentaje literal en el informe coincida
con un `percent_change` o `ratio_percent` recalculado con Decimal. Esto bloquea
el 16,13 % de DR-002 aunque el modelo lo apruebe; no verifica por sí solo que el
porcentaje corresponda al concepto de negocio correcto. La calibración estructurada
calculó y citó 16,14 % correctamente. Las medianas auxiliares también fueron
correctas dentro de 0,01, tras usar una biblioteca estadística. Son mitigaciones
observadas, no una garantía general ni el cierre automático de los tres errores.

### DR-004: representación o etiquetas que no corresponden a la evidencia

En `calibration-02/daily-1`, Qwen aprobó una gráfica que combinaba sumas de periodo
y medias diarias en el mismo eje. Las etiquetas identificaban ambas, pero no
cumplía la comparabilidad exigida para ese gráfico. La revisión independiente
retuvo el informe mediante `review.hold`; se conserva la aprobación histórica.
Las cifras de totales, medias, medianas, extremos, 24 valores diarios y oscilaciones
fueron contrastadas directamente con el CSV. Una comprobación numérica correcta
no sustituye la evaluación de la presentación. Mantener este caso en la rúbrica.

### Transporte y coste de contexto

El adaptador genérico `chat_completions` no enviaba control de razonamiento. En la
prueba local, el servidor empleaba razonamiento aunque la configuración interna
indicase `off`. El protocolo específico `lmstudio_structured` envía
`reasoning_effort: none` y JSON Schema; las respuestas observadas registran cero
tokens de razonamiento. Las opciones nativas y genéricas siguen separadas.

La revisión recibía código y borrador duplicados en observaciones y conversación.
Se han sustituido solamente copias idénticas por referencias explícitas dentro del
mismo contexto. No es compactación semántica: se conservan programas distintos,
borradores anteriores, respuestas y objeciones. El límite de contexto sigue
existiendo y se mantiene el bloqueo seguro cuando se supera.

La calibración `calibration-02/unit-price-1` reprodujo además DR-001 en el recorrido
completamente autónomo: no hubo pregunta, el analista publicó 257,50 como ventas
y el revisor lo aprobó. La comprobación independiente retuvo el informe. La
planificación v4, investigación v4 y revisión v6 añaden ejemplos explícitos de
una base monetaria sin definir frente a agregados diarios definidos. La matriz
posterior debe medir esta mitigación; no se considera resuelto por cambiar el prompt.

Comprobación posterior de DR-004: `focused-06/daily-3` vuelve a recibir una
aprobación explícita para barras que mezclan totales de periodo y medias diarias.
Las cifras, fechas de extremos y desviaciones estándar son correctas; la evaluación
independiente retiene la aprobación y bloquea su exportación. El problema de
significado y presentación sigue abierto tras las restricciones de referencias.

### DR-005: inspección imposible repetida

La primera serie con los ejemplos de definiciones pidió repetidamente inspeccionar
perfiles ya suministrados y agotó las dos validaciones. En las cargas de hasta tres
tablas, la aplicación proporciona esos perfiles desde el inicio. El esquema de
salida ahora ofrece únicamente `propose` cuando no quedan tablas por inspeccionar;
si quedan, conserva ambas acciones. Esta restricción usa el estado real del grafo,
no respuestas esperadas, y tiene una prueba de regresión. La serie fallida se
conserva y la siguiente usa una identidad de lote nueva.

DR-004 apareció también en `matrix-04/products-renamed-3`: tras una devolución
real del revisor, el analista calculó y guardó 16,14 % y 8,44 % y corrigió el
borrador. El revisor lo aprobó, pero una tabla etiquetaba 67.754,90 como productos
«restantes» aunque era el total de los cinco líderes e incluía al primero.
Los demás miembros de esos cinco suman 35.009,90. La evaluación independiente
retuvo el informe. La corrección numérica del diálogo funcionó; no resolvió esta
incoherencia de etiquetas ni algunas expresiones de cobertura excesiva.

En `matrix-05/daily-1`, el diálogo corrigió la mezcla de totales y medias y
retiró una comprobación aritmética incorrecta. El revisor aprobó después un texto
que asignaba los mínimos 28,80 y 100,00 al 1 y al 15 de abril. El CSV los sitúa
el 12 y el 23 de abril; las fechas de mínimos no se habían guardado como métricas.
Los importes, porcentajes, extremos y gráficos finales son correctos, pero esa
asociación inventada hace inadmisible el informe. La evaluación independiente lo
retuvo. **Estado: abierto.** Verificar valores sueltos no verifica sus etiquetas,
fechas ni correspondencia con una entidad.

En `matrix-05/products-renamed-3` se repitió DR-004: el revisor aprobó el
gráfico «Top 5 restantes» con el total que incluye al líder. La devolución previa
corrigió porcentajes y el analista arregló el título monetario, pero no ese
conjunto. La evaluación independiente retuvo el informe. También se detectó
un error auxiliar de granularidad: `duplicate_sku_day_pairs=8` agrupaba por
(nombre, SKU), no por (SKU, fecha); la referencia de duplicados por fecha es
cero. Esa métrica no se utilizó en el informe final. El promedio por fila sí
aumenta en estos datos, pero comparar crecimiento de importe y unidades no
fundamenta ese promedio: el denominador pertinente son las filas.

### DR-006: interpretar huecos de una selección como ausencia de actividad

En `matrix-05/line-total-1`, el analista y el revisor conservaron la frase
«La distribución en 7 días sugiere actividad intermitente, no diaria continua».
El contexto dice expresamente que las 12 filas son una selección, no una
exportación completa. Los registros ausentes no acreditan días sin actividad.
Las advertencias de cobertura y el gráfico sin ceros no justifican esa frase.

Los 257,50 de ventas, 59 unidades, promedios, conteos y las dos series diarias
son correctos. El revisor había corregido un gráfico con el total duplicado y
un conteo afirmado sin evidencia, pero aprobó la interpretación temporal sin
sustento. La evaluación independiente retuvo el informe conservando la
aprobación histórica. **Estado: abierto.** Un cálculo correcto y una advertencia
general de cobertura no bastan para aprobar todas las conclusiones.

La serie posterior `focused-06/unknown-2` volvió a aprobar «La actividad no es
diaria» tras corregir el gráfico. Las referencias eran válidas, los siete valores
y el promedio correctos, y el importe permanecía bloqueado ante la respuesta
desconocida. La evaluación independiente retuvo la conclusión temporal.

### DR-007: negar un cálculo posible al confundir precio neto y precio fijo

En `matrix-05/line-total-2`, el resumen afirma que no se puede determinar el
precio unitario implícito porque el importe es un total de fila con descuentos.
Con una cantidad positiva y el total neto de fila confirmado, `value / units`
sí obtiene el precio neto medio por unidad de esa fila: en la primera, 25 / 4
= 6,25. Eso no demuestra un precio de lista ni un precio fijo común a todas
las filas. Tampoco permite atribuir la variación a descuentos específicos.

El revisor aprobó el informe con esta limitación falsa; los totales de ventas,
unidades y el gráfico diario eran correctos. La evaluación independiente lo
retuvo. **Estado: abierto.** La adaptación se evalúa también por abstenciones
injustificadas y explicaciones falsas, no solo por cifras inventadas.

En `correction-05-2` se reprodujo DR-007 tras corregir la definición a total de
fila: el informe niega poder sumar importes por producto o fecha sin confirmar
un precio unitario. Esa suma tampoco requiere dividir por cantidades. El revisor
no lo detectó y, además, pidió presentar el rango de la muestra (2–7 de abril)
como rango completo de las 12 filas, que llegan al 15 de abril (DR-004). El
analista siguió esa instrucción y el revisor aprobó. Se retuvo el informe. Los
totales 257,50/59, la invalidación de la aprobación anterior y la persistencia
funcionaron: el fallo es semántico, no del mecanismo de corrección.

### DR-008: identificadores de herramientas y evidencias inexistentes

`matrix-05/unknown-1` conservó la respuesta «no lo sé» y dejó el importe
bloqueado, pero intentó ejecutar usando el alias `t1` como identificador de
tabla y, después, un UUID incorrecto. Ambas llamadas fueron rechazadas antes
de ejecutar Python. No llegó al análisis de cantidades que sí era posible.

`matrix-05/unknown-2` calculó las cantidades, pero sus dos borradores citaron
métricas por fecha no guardadas; el segundo incluso inventó una ejecución.
El contrato los rechazó antes de pasar al revisor. **Estado: abierto en esta
serie.** Los controles evitan publicar evidencia inexistente, pero ese bloqueo
no satisface el recorrido requerido. La versión posterior limita las opciones
a identificadores y parejas ejecución/métrica disponibles, conserva la
validación posterior y no introduce respuestas del evaluador. Sus pruebas de
regresión y la serie real separada se detallan en el informe del paso 1.7.
Una referencia válida todavía puede asociarse a una etiqueta o interpretación
incorrecta; no se da por resuelto DR-004 con este cambio.

### DR-009: precisión de porcentajes y lectura incorrecta de una comprobación

En `matrix-05/daily-3`, el primer borrador usaba un total monetario como resultado
de un check de porcentaje. El revisor detectó ese error y el analista guardó
16,14. Su diferencia con 16,135755… es inferior a la tolerancia 0,01; ese check
aritmético pasaba. Sin embargo, nuestro control del texto exigía dos decimales y
rechazaba el redondeo válido «16,1 %». Era una restricción innecesaria del controlador.

El revisor confundió el fallo de texto con el check aritmético y pidió almacenar
16,1. Esa modificación sí supera la tolerancia 0,01 y provocó otra devolución.
La revisión alcanzó el límite de 20 minutos sin aprobación. Se conserva la
conversación y una comparación retrospectiva del validador propuesto: el borrador
intermedio pasa sus controles al respetar la precisión mostrada. Esto no es una
aprobación real del modelo ni convierte el intento interrumpido en éxito.

La corrección implementada redondea una sola vez desde el porcentaje recalculado a
la precisión del texto. Las pruebas mantienen el rechazo de valores incorrectos,
precisión falsa y errores de doble redondeo. Su comprobación real se registra por separado en el informe de evaluación;
el código de la matriz original permaneció fijo hasta terminar sus ejecuciones.

En `focused-06/daily-1`, el texto 16,1 % pasó con una métrica de precisión
completa: comprobación real de la corrección del controlador. En `daily-2`, el
revisor volvió a pedir inicialmente almacenar 16,1 con tolerancia 0,01; ese check
aritmético falla correctamente. En su siguiente devolución identificó la pérdida
de precisión y pidió guardar el porcentaje sin redondear. El cambio del controlador
no elimina por sí solo los errores del modelo al construir una comprobación.

En `matrix-05/products-1` apareció otro límite: el control compara porcentajes
literales, sin interpretar desigualdades como «menos del 5 %». El máximo de las
participaciones pertinentes era 4,92 %, pero el literal 5 seguía sin un check
coincidente. El revisor volvió a atribuir el fallo al check aritmético que pasaba.
El analista terminó expresando las participaciones concretas con sus checks;
el último borrador era correcto, pero la fase agotó su tiempo antes de la
aprobación. Validar porcentajes literales no equivale a comprender todas las
afirmaciones numéricas del lenguaje natural.

### DR-010: atribuir un error del programa a datos válidos

En `matrix-05/daily-renamed-1`, el modelo reconoció `day` y `sales_value`, pero
generó consultas con `db.execute` después de salir de `with connect()`. La
conexión ya estaba cerrada. Un `except Exception` ocultó el error original y
clasificó las 24 fechas ISO válidas como no convertibles. Los tres intentos
conservaron ese defecto; el último repitió el segundo programa.

La investigación quedó bloqueada y pidió injustificadamente al propietario
explicar el formato o corregir el archivo. No hubo candidato válido ni informe:
el servicio rechazó iniciar la revisión sin candidato. **Estado: abierto.** Es
un fallo del programa y su diagnóstico por el agente, no de las fechas ni de la
variante CSV. No se corrigió manualmente el Python para rescatar esta repetición.

### DR-011: confundir repeticiones esperadas con conflictos de nombres

En `matrix-05/products-2`, el programa incrementa `name_conflicts` cada vez que
reaparece la misma pareja `(product_id, product_name)`. Son 108 repeticiones de
ocho productos a lo largo de 116 filas de producto por fecha; no nombres distintos
para el mismo identificador. La comprobación independiente encontró un único
nombre por identificador y cero conflictos.

El borrador conserva la falsa alerta en método, limitaciones y siguiente paso.
El revisor devuelve errores de porcentajes, pero describe el resto como correcto
sin detectar este diagnóstico. La fase se interrumpe por tiempo antes de una
aprobación; no se afirma que el informe haya sido aprobado o entregado. Los
totales, cantidades y ranking son correctos. **Estado: abierto.** La coherencia
del significado de una métrica debe comprobarse contra su operación y el nivel
de detalle de las filas, no inferirse de su nombre o de su descripción.

### DR-012: bloquear cantidades por una ambigüedad monetaria independiente

En `focused-06/declined-2`, la planificación conserva correctamente el rechazo
a aclarar `value`: el total monetario queda bloqueado y la investigación de
cantidades sigue disponible, con `units` definida y sin dependencias pendientes.
La primera acción de investigación bloquea, sin embargo, las cantidades y lo
justifica por no saber si el importe es precio unitario o total de fila.

No ejecutó Python ni produjo un candidato; el servicio rechazó iniciar la revisión
sin candidato y no hubo informe. Es una acción formalmente válida con una razón
que no corresponde a esa investigación. **Estado: abierto.** La corrección de
identificadores no sustituye comprobar qué resultados dependen realmente de una
definición pendiente. Las 59 unidades eran calculables y debían continuar aunque
el propietario mantuviera su negativa sobre el importe.

El revisor no llegó a intervenir en DR-012: el inicio de la revisión exige al
menos un candidato registrado. Por tanto, este recorrido todavía no revisa
independientemente una abstención errónea que bloquea todas las investigaciones.
No se atribuye al revisor una detección o corrección que no ocurrió.

### DR-013: contador auxiliar de SKU calculado desde una lista vacía

En `focused-06/declined-3`, el programa crea `sku_values = []` y nunca añade
valores; `len(set(sku_values))` guarda `unique_skus=0`. La agrupación por SKU en
el mismo programa sí calcula `sku_1_units=59`; la referencia independiente
confirma un único SKU. El analista y el revisor no corrigieron el contador.

El informe final no cita `unique_skus` y presenta correctamente un SKU, los
importes monetarios omitidos y las cantidades diarias. La evaluación del informe
separa ese resultado del cálculo auxiliar defectuoso. **Estado: abierto.** Una
aprobación del informe no verifica todas las métricas guardadas ni permite
reutilizar automáticamente ese contador como un hecho comprobado.

### DR-014: una corrección introduce métricas constantes con procedencia falsa

En la segunda y tercera ejecuciones de `focused-06/daily-2`, el analista recalcula el porcentaje
solicitado por el revisor, pero también guarda medianas y cambios diarios medios
como cero literal. Conserva descripciones que atribuyen esos valores a operaciones
estadísticas que ese programa no ejecuta. Otros controles de duplicados, cobertura
y parejas consecutivas se copian como constantes. La primera ejecución había
calculado correctamente esas estadísticas.

**Estado: abierto.** Disponer de una referencia existente y una descripción de
procedencia no prueba que el programa haya realizado la operación descrita. Los
ceros de las medianas contradicen el CSV. En la devolución siguiente, el analista
reconoció el error y mantuvo las referencias a las medianas correctas de la primera
ejecución; las métricas incorrectas siguen guardadas. El revisor terminó aprobando
esas referencias correctas sin corregir las métricas auxiliares. La evaluación distingue las referencias
del informe final de las métricas auxiliares e intermedias: una corrección limitada
puede degradar resultados que antes eran correctos, aunque el agente diga que los
ha conservado. No se reparó manualmente el programa.

### DR-015: unidades y afirmaciones de cobertura no sustentadas en la prueba web

**Estado: abierto; observado al validar la entrega 2 el 22 de septiembre.**

El recorrido web real recibió `01-daily-sales/input/sales.csv`, preguntó por la
base monetaria, conservó la respuesta tras reiniciar el servidor y completó
investigación y revisión. Tras una devolución, el revisor aprobó un informe con
dos gráficos. Los totales 34.137,85 y 39.646,25, la diferencia 5.508,40 y el
16,135755… % coinciden con el CSV calculado independientemente con Decimal.

Sin embargo, el informe presenta los 28 días del periodo como los días del mes
de abril; utiliza euros sin que el archivo ni la respuesta confirmen moneda;
y afirma que usar medias diarias daría un porcentaje de cambio distinto. Ambos
periodos contienen 12 días, por lo que el porcentaje de cambio de la media es
idéntico al del total. El revisor no detectó esas afirmaciones.

Se aplicó `review.hold` conservando la aprobación histórica. La web retiró el
informe del detalle y del filtro de informes disponibles, y denegó el acceso
directo. No se modificaron manualmente el código generado ni el informe para
rescatar el caso. Este hallazgo mantiene abierta la aceptación analítica de la
entrega 1; la interfaz y su bloqueo se verifican por separado. Ver
[validación de entrega 2](2026-09-22-web-check.md).
