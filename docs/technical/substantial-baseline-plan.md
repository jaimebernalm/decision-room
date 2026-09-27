# Paso 3.1: protocolo de evaluación con varias tablas

Estado inicial del protocolo: fijado antes de ejecutar los seis recorridos.
Los resultados se documentan por separado; conservar todos los intentos.

**Ejecución cerrada:** [resultados de 3.1](../validation/2026-09-27-substantial-baseline.md).
Se conservan cuatro aceptados y dos fallos iniciales. Tras la matriz se hizo una
recuperación explícita adicional del caso con HTTP 503; se documenta aparte y no
modifica los resultados ni los criterios iniciales.

## Datos y alcance

Wide World Importers, negocio ficticio de Microsoft. Usar completos los cinco CSV
Invoices, InvoiceLines, Customers, CustomerCategories y StockItems de la conversión
local documentada en `data/wide-world-importers/README.md`. No reducir las filas.
Comparar 2014 y 2015; disponer de todas las fechas permite evaluar la selección.
No entregar al modelo el esquema original, claves verificadas ni resultados de
referencia. Sí proporcionar definiciones de negocio explícitas, iguales en los
seis recorridos, para aislar la comprensión y el análisis de varias tablas.

Tres objetivos, dos repeticiones independientes cada uno: organizar indicadores,
descubrir oportunidades y responder qué productos y categorías contribuyen al
cambio de ventas y margen. La selección de objetivos aún no tiene interfaz;
se introduce como contexto del propietario en el recorrido actual. Se evalúa la
salida del informe que podría alimentar un dashboard, no el editor del dashboard.

## Condiciones constantes

- Copia fija del código guardado en Git, más el ejecutor de evaluación. Excluir
  cambios concurrentes sin guardar; registrar hashes de código y archivos.
- Modelo configurado del producto, con identidad y parámetros en el manifiesto.
- Importación real, PostgreSQL separado y Python generado ejecutado en Docker.
- Presupuestos actuales del producto: dos investigaciones, 30 segundos de Python
  y cuatro rondas de revisión. No ajustar prompts ni límites para lograr éxitos.
- Procesos separados por fase y recuperación de un informe aprobado sin nuevas
  llamadas ni ejecuciones. No equivale a probar caída en mitad de una llamada.
- Respuestas automáticas restringidas al contexto del propietario predeclarado;
  otras preguntas reciben «desconocido». Registrar preguntas redundantes y límites
  de esta simulación. Nunca proporcionar resultados esperados en una respuesta.
- Plazo de 20 minutos por fase. Fallos y llamadas inciertas quedan registrados y
  no se reintentan automáticamente. STOP permite parar entre fases.

## Referencia y aceptación fijadas de antemano

El controlador calcula referencias con CSV y Decimal antes de llamar al modelo.
Valida unicidad y correspondencias, y agrega ventas sin impuestos, margen bruto,
cantidades, facturas y líneas por año, mes, producto, cliente y categoría. Calcula
las contribuciones a la variación por diferencia de importes. Esas referencias
permanecen fuera del contexto y de los archivos montados en el sandbox del agente.

Para aceptar un recorrido, debe terminar con informe publicable, fuente estable,
recuperación correcta y revisión independiente satisfactoria:

1. Todas las cifras mostradas contrastadas; tolerancia de redondeo a la precisión
   presentada, como máximo 0,01 para importes mostrados con dos decimales. Conteos
   exactos. Distinguir porcentajes de puntos porcentuales.
2. Uniones sin multiplicación ni pérdida de filas; periodo, impuestos y base de
   margen correctos; moneda no inventada; categorías actuales como limitación.
3. Organización: totales anuales, importe medio por factura, evolución mensual y
   desglose por categoría útiles para el objetivo, o ausencias explicitadas que
   se cuentan como cobertura incompleta.
4. Pregunta concreta: cambio de ventas y margen, importe y tasa de margen, y
   contribuciones de productos y categorías. Comprobar también lo omitido.
5. Descubrimiento: al menos dos observaciones pertinentes y distintas respaldadas
   por desgloses, con magnitud y comparación. Contrastar las mayores contribuciones
   y diferencias de margen de la referencia para identificar oportunidades omitidas;
   no exigir una historia sorpresa ni atribuir causas sin evidencia.
6. Preguntas pertinentes, limitaciones honestas, ausencia de contradicciones y
   presentación que responda al objetivo. Una aprobación del revisor del producto
   no sustituye este juicio ni la comprobación numérica independiente.

Registrar por separado finalización, aprobación del producto, exactitud, cobertura,
utilidad, preguntas, revisiones, fallos de ejecución, tiempo y tokens. Dejar coste
monetario desconocido si no se dispone de precios verificados.

## Cierre del paso

El paso 3.1 es una medición inicial: puede cerrarse con informes fallidos si la
matriz está ejecutada, las referencias verificadas, los fallos conservados y las
causas y prioridades de 3.2 documentadas. No implica que el producto esté aprobado
para datos de clientes reales. La base completa de 48 tablas, nuevos esquemas,
contexto ambiguo y más repeticiones corresponden a evaluaciones posteriores.

## Ejecución

En una copia fija con el entorno local y el sandbox configurados:

```sh
.venv/bin/python -m decision_room.evaluation.substantial run \
  .local/evaluation/substantial-baseline \
  --csv data/wide-world-importers/exports/csv --repeats 2
```

La base de evaluación y sus evidencias se conservan para revisión. Volver a lanzar
el mismo lote omite fases terminadas y casos fallidos; rechaza cambios en código,
datos o configuración. Las credenciales se toman del entorno; nunca se guardan en
el manifiesto. Los artefactos permanecen en `.local/`, fuera de Git.
