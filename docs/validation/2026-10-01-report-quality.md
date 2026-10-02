# 3.9 — Reanudación de la evaluación tras restablecer saldo

La recarga permite volver a ejecutar el proveedor. El bloqueo anterior afectó a
la validación real y al cierre de 3.9.7, no a la implementación de 3.9.1–3.9.6.
Se conservan los [resultados anteriores](2026-09-30-report-quality.md), incluidos
los seis intentos que fallaron por saldo. Ningún informe favorable los sustituye.

## Correcciones y comprobaciones

- `3f02371`: el revisor conoce que `temporal_grain=null` en un gráfico que cita
  una serie completa hereda el grano de esa evidencia. No debe exigir un override
  que el esquema prohíbe. Pasan 38 pruebas dirigidas.
- `1db869e`: los roles deben inspeccionar columnas reales antes de declarar un
  dato ausente y calcular los contrastes materiales que permitan discriminar
  reacciones. Facturas, compradores, cantidades, precios y composición pueden
  estar disponibles; stock o tráfico operativos pueden faltar. Una omisión por
  presupuesto debe conservarse como parcial, no describirse como imposible.
  Pasan 80 pruebas dirigidas.
- `9421aa1`: el esquema ofrece identificadores nuevos de seguimiento en el
  espacio de la rama y dentro del presupuesto de agenda. Conserva la validación
  de unicidad y el origen explícito; no elige preguntas ni métodos de negocio.
  Pasan 46 pruebas dirigidas, incluidas agenda llena y claves largas.
- Regresión completa posterior: **533 pruebas Python pasan**. Los cambios de esta
  reanudación no modifican la interfaz; las 117 pruebas web y build/lint de la
  entrega previa siguen siendo su última comprobación.

## Lote reanudado con `4499f15`

Seis ejecuciones nuevas con las mismas fuentes, objetivos, contexto desconocido,
modelo y presupuestos; se reutilizan las seis bases históricas, sin contabilizarlas
como nuevos intentos. Rúbrica 2 y comprobación CSV/Decimal independientes sobre el
borrador final. La revisión semántica es de desarrollo, no ciega ni aceptación del
propietario. Esta copia precede a las tres correcciones anteriores.

| Caso | Rep. | Publicable | Aceptación independiente | Referencias cotejadas | Segundos |
|---|---:|---|---|---:|---:|
| Bruma descubrir | 1 | Sí | Sí | 25 | 291,529 |
| Bruma descubrir | 2 | No | No | 33 del borrador | 567,323 |
| WWI descubrir | 1 | Sí | No | 42 | 416,010 |
| WWI descubrir | 2 | No | No, sin informe | — | 188,433 |
| WWI organizar | 1 | Sí | Sí | 110 | 256,902 |
| WWI organizar | 2 | No | No | 110 del borrador | 471,506 |

Resultado: **3/6 publicables y 2/6 aceptados** frente a las bases históricas
5/6 publicables y 1/6 aceptadas. Las 320 referencias entregadas o conservadas en
borradores se corresponden con las fuentes; esto no convierte un borrador sin
aprobación en entrega válida. Muestra pequeña y continuación no alternada: no
prueba causal ni mejora consistente.

- Bruma 1 profundiza en contribuciones producto/canal y en los seis productos de
  Tienda física. Reconcilia el descenso de −71 unidades de junio a agosto y
  localiza −24 en Café de la casa. Distingue volumen, contribución y sensibilidad
  por día calendario; no infiere días de apertura. Propone corregir captura si
  hay discrepancia, revisar disponibilidad si hay una restricción documentada y
  contrastar tráfico/conversión si concilia sin ella. Sus condiciones siguen
  siendo hipótesis; no usa importes cuya base se desconoce.
- Bruma 2 tiene profundidad y reacciones útiles, pero agota las ocho rondas de
  revisión por la exigencia errónea sobre el grano heredado. Se conserva limitado.
- WWI descubrir 1 mantiene importes y citas correctos, pero deja para después
  conteos de facturas/compradores y contrastes de precio/composición que permiten
  los archivos. Falla profundidad, siguiente comprobación y respaldo de la
  decisión, aunque el revisor del producto lo aprueba.
- WWI descubrir 2 falla al proponer una nueva verificación con una clave de
  seguimiento ya existente, después de dos validaciones. Su investigación previa
  permanece disponible; no hay entrega cuya utilidad pueda juzgarse.
- WWI organizar 1 entrega las tres medidas en anual, 24 meses y cinco categorías
  para ambos años. Las medias se calculan por factura tras sumar sus líneas.
  Tres líneas temporales y una comparación categórica, con margen/media por
  categoría también citados en prosa, satisfacen el encargo de organización.
- WWI organizar 2 tiene un borrador con esas medidas y tres categorías del catálogo
  sin registros, sin imputarlas como ceros. La revisión repite el mismo error de
  grano heredado y termina por HTTP 429. La causa específica de este rechazo no
  está diagnosticada; no se identifica automáticamente como saldo agotado.

## Recuperación aislada del protocolo

Una revisión nueva de Bruma 2 con `3f02371` aprueba en 36,326 segundos el informe
sobre la investigación ya guardada. Las 33 referencias siguen correctas, el estado
limitado original se conserva y reanudar la nueva revisión es idempotente. Los
recursos incrementales se separan de los originales.

Esta prueba verifica la corrección del protocolo de revisión; **no constituye
un séptimo recorrido completo**, no reemplaza el fallo de Bruma 2 y no demuestra
por sí sola una mejora de calidad de investigación.

## Intento posterior con las tres correcciones: `9421aa1`

Se ejecuta Bruma descubrir, repetición 1, con la copia congelada y las mismas
fuentes/objetivo. Termina **limitado, sin aprobación**, en 1.019,520 segundos tras
ocho rondas de revisión. No se lanza ninguna de las otras cinco reservas: no son
intentos fallidos ni se incluyen en el recuento de intentos realizados. El resumen
del ejecutor conserva sus estados `not_run`; sus seis plazas no representan seis
recorridos ejecutados.

Las **73 referencias entregadas** del borrador final coinciden con CSV/Decimal.
Se verifican además etiquetas mensuales frente a los periodos de las métricas.
El error previo que usaba agosto para julio se repara en ese borrador final, y la
atribución de +188 ya cita tanto magnitud como identidad. Sin embargo, el texto y
la cobertura afirman mostrar 18 combinaciones en tres vistas, mientras la entrega
contiene solo 12 en dos tablas. No se acepta coherencia de entrega ni claridad.
La línea mensual y las tablas son representaciones legítimas; no se exige una
línea para aceptar una comparación de categorías.

El problema observado amplía el objetivo original —priorizar productos/canales y
profundizar señales— hacia un inventario completo de combinaciones. Las rondas
recalculan datos ya guardados y alternan omisiones al intentar encajar las vistas
en el presupuesto de entrega. Las correcciones de grano, comprobaciones con datos
y claves nuevas no bastan para impedir ese comportamiento. **No se declara
validación consistente de la versión final** ni se reemplaza el fallo por la
recuperación aislada favorable.

## Recursos y conservación

Se conservan **25 intentos únicos**: los 18 anteriores, seis tras restablecer saldo
y este intento posterior. Las seis bases históricas copiadas no se cuentan otra
vez; la recuperación aislada y el diagnóstico previo de proveedor quedan fuera.

| Ejecuciones adicionales | Llamadas lógicas | Ejecuciones fallidas | Entrada conocida | Salida conocida | Uso completo |
|---|---:|---:|---:|---:|---|
| Seis con `4499f15` tras recarga | 162 | 9 | 5.961.273 | 272.296 | No, dos intentos incompletos |
| Un intento con `9421aa1` | 45 | 1 | 2.662.609 | 147.788 | No |
| Recuperación aislada `3f02371` | 2 | 0 | 108.798 | 4.903 | Sí, solo recursos incrementales |

Los 25 intentos acumulan 532 llamadas lógicas y 24 ejecuciones fallidas; entrada
conocida 21.065.735 y salida conocida 905.206. Trece intentos tienen uso incompleto;
los rechazos y recursos desconocidos no se sustituyen por cero. Estos totales
incluyen reintentos lógicos y caché según lo registrado, y no incluyen los dos
registros de recuperación ni el diagnóstico externo a la matriz. No se estima
un coste en dinero sin tarifas declaradas y uso completo.

## Aceptación pendiente

El informe aprobado de Bruma 1 está disponible en una vista local de revisión
identificada, separada del informe histórico. La prueba del propietario sobre
prioridad, siguiente comprobación y reacción continúa abierta. La consulta web
3.95 sigue fuera del alcance. El paso 3.9.7 permanece sin marcar completo.
La siguiente corrección debe impedir
que el brief/revisor conviertan métodos internos en obligaciones del cliente y
reconciliar la cobertura declarada con el manifiesto final, antes de repetir
comparaciones pagadas.

Los artefactos, bases independientes, fuentes y programas de auditoría permanecen
en almacenamiento local ignorado. No se publican datos privados, credenciales,
rutas personales ni volcados del proveedor en Git.
