# Entregas de carpetas CSV y Excel

La persona puede seleccionar varios archivos o una carpeta desde «Mi negocio»,
«Crear informe» y el primer informe. Una selección se registra como **un conjunto
del negocio**: conserva rutas relativas, originales y tablas preparadas por archivo
u hoja. El límite inicial es **2.000.000.000 bytes (2 GB decimales) sumados por
entrega**. No se ofrece una cuota de «accesos» ni un límite de diez archivos.

## Recorrido

1. El navegador muestra los CSV y `.xlsx` seleccionados y el peso total. Omite
   otros formatos de una carpeta y muestra cuántos omitió. El selector de carpeta
   usa la ruta relativa proporcionada por el navegador; seleccionar la carpeta
   no concede acceso continuo a los archivos del equipo.
2. `POST /api/datasets/bundles` registra un manifiesto privado e idempotente.
   Los archivos viajan en fragmentos de hasta 8 MiB a
   `/api/datasets/bundles/{id}/files/{index}`. El servidor registra el avance en
   disco, verifica fragmentos repetidos y permite reanudar después de un corte o
   volver a seleccionar la misma carpeta tras recargar la página.
3. `POST /api/datasets/bundles/{id}/finish` comprueba tamaños, conserva los
   originales en el almacenamiento privado, convierte cada hoja Excel con datos
   en un CSV preparado y entrega todos los CSV al importador por lotes existente.
   Cada tabla preparada queda vinculada al negocio y al análisis. Los libros
   originales se pueden volver a descargar desde «Mi negocio».
4. Si se pidió un informe, `/api/jobs/from-dataset` inicia el trabajador sobre
   ese conjunto preparado. La misma clave de envío evita duplicar el informe al
   reintentar una respuesta perdida. Las conversaciones pueden reutilizar el
   conjunto desde la ficha. Ninguna hoja se une ni se suma automáticamente con
   otra.

Un CSV legible queda disponible aunque otro archivo de la entrega falle. Los
libros ilegibles quedan marcados como fuente fallida, y el conjunto aparece como
parcial. Una actualización o corrección parcial no sustituye la versión anterior;
los originales y tablas aprovechables siguen visibles.

## Límites de preparación

- 2 GB de archivos seleccionados y 2 GB de CSV preparados por entrega. El
  importador mantiene límites técnicos por tabla de 256 columnas y 10 millones
  de filas, además de un límite de 10.000 entradas para acotar el manifiesto.
- Un Excel se lee por hojas, usando los valores guardados en el libro. Una fórmula
  sin resultado guardado puede aparecer vacía; debe revisarse antes de atribuirle
  un cero o publicar un resultado que dependa de ella. Una hoja vacía se omite.
  Se limita a 4 GB el tamaño descomprimido declarado del libro.
- La carga por fragmentos evita mantener el archivo entero en memoria. Durante la
  preparación se necesitan copias temporales y espacio para Parquet; por tanto,
  aceptar 2 GB de entrada no equivale a necesitar solo 2 GB libres en disco.
- El catálogo analítico puede contener todas las tablas importadas. El agente
  selecciona las relevantes para cada investigación; la planificación actual
  inspecciona hasta ocho perfiles por sesión y mantiene un contexto de 200 KB.
  La carga completa de Wide World Importers prueba la disponibilidad de las 48
  tablas, pero no certifica que una sola investigación abierta use las 48.

El lote Microsoft Wide World Importers ocupa 604.131.203 bytes en sus 48 CSV;
entra dentro del límite. Sus cuatro Excel, como representación alternativa,
ocupan 196.723.641 bytes. No se deben entregar ambas representaciones juntas
como si fueran ventas distintas.

## Comprobación

`tests/test_bundles.py` cubre una carpeta con subcarpetas, CSV, un Excel de dos
hojas, repetición y reanudación de fragmentos, descarga del original, análisis
sobre el lote, límites y un archivo ilegible junto a datos útiles. El 27 de
septiembre se ejecutó además la ruta nueva de carpeta, de principio a fin, en
una base temporal aislada, con los **48 CSV originales** de Wide World Importers:
604.131.203 bytes, 48 tablas y 4.713.833 filas preparados, estado `ready` en
9,1 segundos. La base y los archivos de esa prueba se eliminaron al terminar.
El lote original y sus 4.713.833 filas ya se habían contrastado en
[`2026-09-21-ingestion-check.md`](../validation/2026-09-21-ingestion-check.md).
