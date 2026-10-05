# P1a — Panorama determinista para redactar y revisar

Base `929d142` (P3b), rama `codex/feature/sales-panorama-p1a`.
Implementación experimental; utilidad pendiente de la comparación por parejas.
[Plan](../technical/sales-panorama-plan.md). Sin llamadas reales al modelo.

## Activación y medición

1. Aplicar la migración normal (`python -m decision_room init`); añade la caché
   privada `sales_panoramas` (versión de esquema 31).
2. `DECISION_ROOM_SALES_PANORAMA=true` activa el cálculo al importar o reanudar una
   importación. Apagada por defecto. No añade panorama al planificador, investigador,
   perfiles de tablas ni modelo de datos compartido.
3. Para las investigaciones existentes, usar `review.start(..., sales_panorama=True,
   request_key=<clave nueva>)`. Calcula o reutiliza el mismo panorama de sus tablas
   ya importadas; no vuelve a investigar ni altera candidatos o ejecuciones.
4. Control: `sales_panorama=False` explícito prevalece sobre la configuración.
   CLI: `review-start --sales-panorama` / `--no-sales-panorama`. Mantener los demás
   argumentos del lanzador, incluidos P3b, modelo y presupuestos.
5. Repetir sobre las nueve investigaciones congeladas, con claves distintas para
   cada brazo. Comparar en pareja, contabilizando también fallos. P1a no garantiza
   mejores prioridades por superar los tests de cálculo.

La opción y el panorama se congelan en la revisión; reanudar/reiniciar conserva
ambos aunque cambie la variable de entorno. La huella de petición incluye opción,
entradas, código, versión, mapeo y resultados. El prompt efectivo añade
`sales-panorama-v1` a su versión (también junto a `owner-presentation-v2`).

## Datos y medida

Cada archivo se calcula por separado: no se unen catálogos ni se suman tablas que
pueden solaparse. Encabezados comunes en español/inglés identifican fecha, producto,
canal y cantidad solo si hay una coincidencia por rol. No se adivinan roles ambiguos.

Para columnas diferentes, API de revisión:

```python
review.start(config, business_id, research_id,
    request_key="p1a-explicit-mapping", sales_panorama=True,
    panorama_mappings={str(table_id): {
        "date": "fecha_operacion", "product": "articulo",
        "channel": "punto_venta", "quantity": "piezas"
    }})
```

El mapeo es configuración explícita, no una respuesta inventada del dueño. Puede
prepararse por separado con `sales_panorama_store.prepare(config, business_id,
analysis_id, mappings=...)`; para utilizar ese mapeo en una revisión hay que pasarlo
allí también. No se hereda silenciosamente una interpretación de otra revisión.

P1a suma la columna de **cantidades registradas**. No calcula euros a partir de un
importe de base desconocida, ni tickets, margen o beneficio. El redactor debe
contrastar la interpretación con el contexto real del dueño. Se conservan filas
repetidas, cantidades negativas y ceros explícitos. Fechas ISO y decimales con punto
(hasta ocho decimales); entradas ambiguas/inválidas dejan el panorama no disponible,
sin descartar filas para fabricar un total. Los catálogos que no son tablas de
ventas no se presentan como un fallo de cobertura del negocio.

## Cálculos y reglas

- Totales completos por canal y producto, más total y número de filas del archivo.
- Comparación: primero año hasta el último mes completo frente a los mismos meses
  del año anterior, si cabe dentro del intervalo; si no, últimos tres meses frente
  a los tres anteriores; con menos historia, último mes frente al anterior.
  Meses de borde parciales quedan fuera de la comparación, no de los totales.
  Se guardan fechas, regla, totales, diferencia y días de cada ventana. El intervalo
  no certifica cobertura: meses enteros sin filas invalidan la comparación elegida.
  Se explican la estacionalidad no ajustada y posibles diferencias de días.
- Mayores aumentos y descensos de cantidad por canal y producto × canal: hasta
  cinco por signo, con valores anterior/actual/diferencia y filtros trazables.
  Ordenar por cambio absoluto no determina la prioridad comercial. Si un grupo no
  tiene filas en una ventana, se registra como no comparable, sin imputar cero.
- Huecos diarios por canal y producto × canal: frecuencia de cada día de semana
  en las ocho semanas previas al hueco. Un día habitual aparece en seis de esas
  ocho semanas; el tramo debe perder al menos tres días esperados. No se confunden
  fines de semana habituales sin actividad con huecos. La referencia se congela
  antes del tramo: no utiliza datos futuros para establecer habitualidad.
- Huecos mensuales: grupos presentes en al menos cuatro de los seis meses previos
  y ausentes al menos un mes completo. Solo tras su primera aparición; se evitan
  duplicados solapados con huecos diarios. Se detectan también desapariciones al
  final del archivo, usando el fin observado de la tabla, no el reloj actual.
- Se conservan referencias para duración, frecuencia previa y filas del hueco.
  Se muestran hasta diez tramos por dimensión ordenados por duración y un recuento
  de todos los detectados. No se infiere causa, ventas perdidas ni cierre.

## Evidencia, lectura y aislamiento

La caché contiene fórmula/código y huellas de fuente, motor y resultados. La revisión
los adapta a observaciones con origen `sales-panorama-v1`, IDs deterministas y
referencias ordinarias `execution_id`/`metric`. No son ejecuciones de Python pedidas
por un agente ni incrementan sus presupuestos. Se validan con el contrato normal
de resultados y se resuelven con el mismo mecanismo de evidencia, aprobación,
HTML/PDF y auditoría. Las métricas se reparten en observaciones de hasta 40 cifras y 48 KB por resultado;
el programa se incluye una sola vez por tabla, con referencias en las restantes.

`review.json` conserva panorama y evidencia. Los datos originales se comprueban por
huella y ámbito de negocio al reconstruirlo. Una respuesta nueva del dueño deja
obsoletas las observaciones anteriores según la regla habitual: el código no
promueve automáticamente un significado contradicho a evidencia actual.

Solo redactor y revisor reciben el panorama. Las instrucciones piden abrir el
informe con él y justificar cada prioridad respecto al objetivo y al panorama.
El controlador conserva ese orden editorial cuando P1a está activo; con la opción
apagada mantiene la ordenación previa por síntesis de investigación. No se añade
un requisito mecánico de prioridad, ni un bucle de rechazo P2. P1b sigue pendiente.

## Pruebas y límites

- 78 pruebas de regresión: diez de cálculo/protocolo P1a, dos integradas con
  PostgreSQL y Docker propios, además de presentación, revisión, continuidad,
  esquemas estrictos, PDF y capas.
- Otras 19 pruebas de importación y acciones del modelo pasan. Se repiten las doce
  de P1a tras la revisión final de código. Modelos simulados, transporte HTTP
  simulado en las pruebas de esquema; ninguna petición real a la API.
- Verificado: conservación de investigación y llamadas previas, importación
  idempotente, control apagado, caché e instantánea íntegras, aislamiento por negocio,
  referencias citables, reanudación, exportación, P1a junto a P3b y orden editorial.
- Datos sintéticos: hueco de dos semanas, calendario laboral sin fines de semana,
  desaparición final, actividad mensual, meses ausentes, ceros explícitos, cantidades
  negativas/decimales/duplicados, inversión del orden de filas y año bisiesto.
- Más de 1.000 métricas: esquemas estrictos de ambos roles dentro del límite de
  enums; resultados separados por observación para evitar omitirlos por tamaño.
- Compilación Python, ayuda CLI y `git diff --check` correctos. No hay cambios en
  frontend ni dependencias. No se han abierto datos, informes u oráculos de ensayo.

El cálculo tiene límites declarados: hasta un millón de grupos diarios, 500 grupos
por dimensión y 512 MB para DuckDB. Una sección que supera su límite se declara
no disponible; no se muestrea para sustituir sus totales. Las dimensiones tienen
hasta 500 caracteres. La memoria/contexto de revisión conserva sus presupuestos
anteriores: muchos grupos, archivos o evidencias pueden superar ese límite; P1a
no lo amplía ni borra contexto para conseguir aprobar. El test de 1.000 métricas
verifica el esquema, no promete que todo ese panorama y una investigación extensa
quepan juntos en el presupuesto de contexto.

La detección de huecos es una señal descriptiva con umbrales explícitos. No detecta
toda cadencia irregular ni prueba defectos de extracción. Tampoco demuestra que el
redactor interprete mejor el negocio: esa es la siguiente medición por parejas.
