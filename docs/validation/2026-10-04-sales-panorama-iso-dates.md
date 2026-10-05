# P1a — Fechas ISO con hora y diagnóstico de filas

Corrección separada sobre `c8a42c5`. Calculador `sales-panorama-v2`; misma opción
`sales_panorama`. Sin cambios en P3c, investigación, selección de ventanas ni
prompt del panorama. No se consultaron datos de los ensayos ni se llamó a modelos
reales.

## Causa y cambio

El importador CSV conserva las columnas como texto. La regla anterior admitía
solo `YYYY-MM-DD`, así que rechazaba marcas de tiempo válidas incluso a medianoche.
Ahora valida la cadena completa: fecha ISO, hora opcional separada por espacio o
`T`, fracción de segundo y zona `Z`, `±HH`, `±HHMM` o `±HH:MM`. Comprueba el
calendario, la hora (00–23:00–59:00–59) y el rango de fechas admitido. No basta un
prefijo de fecha válido seguido de texto o una hora incorrecta.

Todas las horas válidas se agrupan por día. Para texto con zona se conserva el día
escrito, sin desplazarlo a UTC. Las columnas parquet `DATE` y `TIMESTAMP` se leen
por la misma ruta normalizada; `TIMESTAMPTZ` usa explícitamente UTC porque ya no
conserva la zona original. `date_rule` documenta la decisión en el panorama. Las
cantidades y dimensiones ya tipadas también se normalizan como texto antes de
aplicar las reglas existentes.

El diagnóstico incluye `row_count`, `invalid_rows`, `invalid_rows_by_rule` y
`validation_rules`. Distingue fecha ausente, formato/hora/zona inválidos, día
inexistente, fecha fuera de rango, cantidad inválida y dimensiones vacías o largas.
`invalid_rows` cuenta filas distintas; los recuentos por regla pueden solaparse.
Si hay filas inválidas, no se omiten para entregar un total parcial.

La versión y el hash del calculador forman parte de la clave de caché: una nueva
revisión calcula de nuevo aunque haya un panorama antiguo `unavailable`. Las
revisiones ya congeladas mantienen su evidencia: para la medición se necesita una
revisión nueva, no reanudar la anterior. No hace falta reimportar las fuentes.

## Pruebas

21 pruebas pasan con PostgreSQL, almacenamiento y Docker propios:

```sh
PYTHONPATH=tests .venv/bin/python -m unittest \
  test_sales_panorama_dates test_sales_panorama test_model_strict_schemas -q
PYTHONPATH=tests .venv/bin/python -m unittest \
  test_sales_panorama_integration.PanoramaPersistenceTests -q
```

- Importación real mediante `service.import_batch` del pequeño CSV sintético
  `tests/fixtures/sales_panorama_timestamps.csv`, con cabecera
  `fecha,canal_id,producto_id,unidades,venta_neta_eur` y valores entrecomillados
  como `"2021-09-01 00:00:00"`. Incluye horas no nulas. El panorama se genera al
  importar: 5 filas válidas, 28 unidades, periodos de 10 y 18, diferencia 8;
  evidencia congelada y resoluble con el mecanismo normal.
- Variantes ISO, agrupación de varias horas del mismo día, zona que cruzaría de
  día al convertir a UTC e invariancia al orden de las filas.
- Igualdad de totales, comparaciones y huecos entre fechas simples y las mismas
  filas con marcas de tiempo.
- Parquet tipado como `DATE`, `TIMESTAMP`, `TIMESTAMP_MS`, `TIMESTAMP_NS` y
  `TIMESTAMPTZ`, con cantidades enteras.
- Fechas imposibles, horas y zonas incorrectas, campos vacíos, límites del rango,
  año bisiesto, archivo sin filas y errores simultáneos con recuento verificable.
- Contratos de evidencia y esquemas estrictos, caché, separación de roles,
  reanudación, opción apagada y exportación combinada con P3.

Compilación Python y `git diff --check` correctos. La comprobación con los datos
reales y la comparación por parejas quedan a cargo del lanzador de medición.
