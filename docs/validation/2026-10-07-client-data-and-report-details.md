# Datos e informes para el cliente — 2.5.32

## Comportamiento

- Archivos muestra originales descargables, sin encabezados de lotes, periodos
  vacíos ni versiones. Tablas muestra nombres de tablas sin extensiones: un CSV
  conserva su nombre base y cada hoja de Excel usa su nombre de hoja. No cambian
  nombres almacenados, identificadores ni descargas.
- Preguntar abre el panel junto a Datos con el conjunto exacto; la cápsula usa
  los nombres de sus tablas. Los datos corregidos siguen identificados y no se
  pueden seleccionar para preguntar. No se fusionan conjuntos independientes.
- Relaciones conserva el lienzo, arrastre, zoom y explicaciones. Se elimina el
  contenedor duplicado, el historial visible y el pie de instrucciones. Solo los
  catálogos de más de doce tablas necesitan búsqueda y selección adicional.
- Conexiones y comprobaciones es un botón compacto con hover que abre un diálogo.
  La lista muestra los nombres conectados; confirmaciones normales no añaden
  otra línea. Los estados pendientes/descartados y problemas de verificación
  siguen visibles. Comprobaciones y ajustes se consultan bajo petición y las
  escrituras mantienen la revisión exacta y el permiso de edición del servidor.
- En Informes, pulsar fuera del título y de las acciones abre sus detalles; el
  botón de información permite hacer lo mismo con teclado. El título y Abrir
  conservan su destino, incluidos informes retirados y trabajos pendientes.
  En móvil las filas se adaptan sin desplazamiento horizontal.
- Los detalles muestran fecha, catálogo original y tablas actuales añadidas
  después. GET `/api/jobs/<id>/sources` lee el snapshot persistido de la sesión;
  no entrega muestras, datos de celdas ni rutas locales. Está autenticado y
  limitado al negocio activo. Mantiene el catálogo histórico tras nuevas cargas.
  Las versiones sustituidas/corregidas y cargas pendientes no cuentan como
  tablas nuevas actuales; actualizar una tabla en la misma familia no multiplica
  el contador. Antes de existir una sesión, no se inventa un catálogo.

## Validación

- 253 pruebas frontend pasan en 34 archivos. Incluyen nombres CSV/hojas Excel,
  descargas, selección exacta y borradores, datos corregidos, mapa acotado,
  aclaraciones con revisión guardada, lectura sin edición, diálogo sin textos
  redundantes, detalles de informes, selección de contexto, papelera y apertura.
- 12 pruebas PostgreSQL/HTTP dirigidas pasan: procedencia histórica, nuevas
  tablas y actualización, sesión pendiente, autenticación, aislamiento entre
  negocios, papelera/retirada y los nueve casos de dossier.
- Build y lint sin errores; permanecen avisos existentes sobre tamaño de chunks
  y componentes/exportaciones compartidas. `git diff --check` pasa.
- Localhost: listado real de archivos, tablas sin `.csv`, tres tablas conectadas
  con Mermaid real, diálogo de conexiones y apertura del informe verificados.
  El informe original muestra una tabla al crearse y tres añadidas después.
- Escritorio 1280×900 y móvil 390×844: diálogos accesibles, apertura/cierre,
  informes legibles y página sin desbordamiento horizontal. Capturas locales
  en `.local/checks/`; las dimensiones temporales del navegador se restauran.

## Alcance

El catálogo del snapshot indica las tablas disponibles para preparar el informe;
no prueba que cada tabla participara en todos los cálculos. El contador compara
la incorporación de tablas actuales con el inicio de aquella sesión. No calcula
cobertura analítica ni modifica, recalcula o publica informes históricos.
Los originales de conjuntos independientes permanecen separados aunque compartan
nombre de archivo. El historial del modelo permanece almacenado y accesible por
API, pero se retira de la interfaz cotidiana por petición del propietario.
