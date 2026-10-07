# Biblioteca actual y tablas consultables — 2.5.33

## Comportamiento

- Datos omite entradas archivadas, corregidas o sustituidas. Los originales y
  tablas del primer informe del ejemplo local se han archivado de esta vista,
  por petición del propietario. Permanecen en almacenamiento y en la procedencia
  del informe; no se eliminan ni se alteran sus resultados. La vista ahora tiene
  tres originales, tres tablas y un solo botón de consulta del conjunto actual.
- La migración 30 añade `analyses.library_hidden` como preferencia de presentación.
  Archivar un conjunto es explícito: crear un informe con tablas actuales no las
  oculta automáticamente. La biblioteca no fusiona tablas de lotes independientes.
  Volver a subir expresamente esos datos los devuelve a la biblioteca.
- POST `/api/datasets/<analysis_id>/library` acepta el negocio activo y un booleano
  `hidden`, de forma reversible e idempotente. Comprueba negocio y propiedad;
  no cambia revisión, disponibilidad analítica, evidencias ni publicación.
- Cada fila de tabla es un botón con hover y foco, independiente de su descarga.
  Abre un diálogo con nombre, número de filas/columnas y datos reales. No muestra
  otro desplegable, selector de lote ni instrucciones de preguntas.
- GET `/api/datasets/table/<source_id>` resuelve la fuente pulsada a su tabla
  preparada dentro del negocio activo. Reutiliza los límites, orden, lectura de
  valores originales e integridad del visor existente. Un parámetro `table`
  ajeno no puede redirigir la consulta de la fuente seleccionada.
- El visor permite recorrer filas y columnas cuando superan una página; las
  tablas fallidas no se pueden abrir. Conserva error/reintento, valores vacíos,
  texto escapado y desplazamiento contenido. Cerrar restaura el foco en la tabla
  de origen y no cambia el contexto o borrador del asistente.

## Comprobaciones

- 259 pruebas frontend pasan en 34 archivos: biblioteca actual, descargas,
  archivos CSV/hojas Excel, apertura de la tabla exacta, contenido, paginación,
  error/reintento, fuentes fallidas y regreso del foco, junto a los recorridos
  existentes de preguntas, selección, mapas e informes.
- 14 comprobaciones PostgreSQL/HTTP pasan: once del dossier (incluidas archivo
  reversible, reenvío explícito sin alterar el informe, tabla exacta, paginación,
  autenticación y aislamiento), y tres de visor/procedencia histórica.
- Build y lint sin errores; siguen los avisos existentes sobre chunks grandes
  y componentes/exportaciones compartidas. Revisión de diferencias sin errores.
- Localhost: tres originales y tres tablas actuales; Productos abre cinco filas
  y cinco columnas, Ventas abre doce filas y cinco columnas del conjunto actual.
- Móvil 390×844: diálogo de 358 px, página de 390 px, desplazamiento de la tabla
  dentro del diálogo y foco restaurado al cerrar. Dimensiones temporales del
  navegador restauradas; captura local en `.local/checks/table-dialog-final.jpg`.

## Límites

La vista presenta páginas de hasta 50 filas y 12 columnas; las celdas de más de
500 caracteres se acortan con puntos suspensivos como en el visor existente.
La descarga conserva los datos completos. Archivar cambia la biblioteca cotidiana,
no el acceso histórico ni las dependencias de informes. La gestión visual general
para archivar/restaurar otros conjuntos no forma parte de esta petición; se
conserva el contrato reversible y la recuperación al subirlos expresamente.
