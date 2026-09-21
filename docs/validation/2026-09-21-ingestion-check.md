# Prueba de importación de Wide World Importers

Fecha: 21 de septiembre de 2026.

La primera importación persistente del MVP está implementada y comprobada con
los **48 CSV como una única entrega de la misma empresa ficticia**. Se conservan
las tablas por separado; no se han combinado sus filas ni producido un informe
comercial. Los archivos actuales y sus históricos no se suman entre sí.

## Resultado del lote

| Grupo | Tablas | Filas |
|---|---:|---:|
| Application | 15 | 40.455 |
| Purchasing | 7 | 12.915 |
| Sales | 12 | 701.656 |
| Warehouse | 14 | 3.958.807 |
| **Total** | **48** | **4.713.833** |

Se conservaron también las dos tablas vacías, con sus columnas.

- Negocio: `3fdd7db1-26d5-453d-829e-70b34acb6452`.
- Análisis: `d708470f-35dc-4f9b-a79c-c1a279ba803b`.
- Estado: `ready`, que aquí significa **archivos preparados**.
- Originales conservados: 604.131.203 bytes.
- Parquet preparados: 32.948.923 bytes, con compresión Zstandard.
- PostgreSQL: 1 negocio, 1 análisis, 48 fuentes y 48 tablas preparadas en el catálogo.
  Los millones de registros permanecen en archivos, no en tablas de la aplicación.

## Comprobaciones realizadas

1. **Comparación completa:** 35.662.866 valores de origen contrastados con los
   Parquet, registro a registro. Coinciden textos, decimales conservados como texto,
   fechas precisas, nulos, cadenas vacías y orden de filas.
2. **Integridad:** huellas SHA-256 de todos los originales y Parquet, columnas,
   recuentos de filas, valores ausentes, textos vacíos y longitudes máximas.
3. **Consulta sobre lo importado:** una unión conocida entre facturas y sus
   228.265 líneas no pierde ni multiplica registros y no tiene líneas huérfanas.
   Totales de cantidades, impuestos, importes y beneficio de línea coinciden con
   las referencias verificadas previamente. Es una comprobación escrita para WWI,
   no una relación descubierta automáticamente por el producto.
4. **Reenvío del lote completo:** devuelve el mismo análisis; continúan 48 fuentes
   y 48 tablas preparadas, sin duplicar la actividad.
5. **Reinicio real de PostgreSQL:** un proceso nuevo recupera exactamente los
   mismos identificadores, metadatos y referencias.
6. **11 pruebas de integración:** fidelidad de valores, tablas vacías, duplicados,
   archivos defectuosos, interrupción y reanudación, reconstrucción de Parquet,
   original alterado, separación por negocio, versiones de contenido, delimitadores,
   límites y los tres casos de referencia con sus variantes. Todas superadas.
7. **Entorno:** dependencias de Python comprobadas con `pip check`.

Durante la primera carga, el histórico de temperaturas alcanzó el límite de
memoria de 512 MB del lector. El lote quedó correctamente marcado como parcial,
con 47 tablas conservadas. Se fijó un búfer CSV de 64 MiB y se reanudó el mismo
análisis: se preparó la tabla restante y se reutilizaron las demás. No se elevó
el límite de memoria para ocultar el problema ni se omitieron filas.

## Cómo consultarlo

Desde la raíz del repositorio:

```sh
.venv/bin/python scripts/dev/local_postgres.py start
.venv/bin/python -m decision_room show --business 3fdd7db1-26d5-453d-829e-70b34acb6452 --analysis d708470f-35dc-4f9b-a79c-c1a279ba803b
```

Añadir `--details` muestra columnas, muestras acotadas e información de preparación.
Las rutas que devuelve el catálogo son relativas a `.local/storage/`.
La [guía de ingesta](../technical/ingestion.md) explica el resto de comandos y los límites.

La evidencia técnica de esta ejecución está en `.local/wwi-verification.json`,
`.local/wwi-persistence-check.json`, `.local/wwi-repeat.json` y
`.local/wwi-after-restart.json`. Son archivos locales de ejecución, fuera de Git.

## Qué queda pendiente

El resultado valida la ingesta CSV local. Todavía no implementa la lectura de
Excel de clientes, interpretación autónoma, descubrimiento de relaciones,
preguntas, ejecución aislada de Python generado, revisión ni informe comercial.
El soporte Excel sigue en el alcance acordado del MVP.

El siguiente paso del plan es **1.3: ejecutar un cálculo conocido en un entorno
aislado y conservar código, fuente y resultado como evidencia**.
