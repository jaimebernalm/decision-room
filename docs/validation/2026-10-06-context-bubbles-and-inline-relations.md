# Contexto en burbujas y Relaciones visibles

Comprobación del paso 2.5.28, 6 de octubre de 2026, en `feature/smoother-UI`.

## Comportamiento

- El contexto del conjunto aparece en una burbuja de ancho ajustado al texto,
  sobre el campo y con una pequeña cola. La isla exterior es transparente;
  el campo y cada adjunto tienen su propia superficie. Se conserva la vista
  previa de los fragmentos y su retirada individual.
- Quitar el conjunto conserva los otros elementos seleccionados y el borrador.
- «Preguntar sobre estas tablas» abre un nuevo borrador en el panel derecho,
  manteniendo Mi negocio → Datos y el identificador exacto del conjunto.
  No crea ni envía un chat hasta que el propietario envía una pregunta.
- Relaciones muestra directamente el modelo preparado, sus tablas, conexiones,
  historial y controles. Un conjunto con una sola tabla muestra su estructura
  y explica por qué no contiene conexiones entre tablas.
- El botón de preparación sigue disponible como recuperación si una importación
  antigua carece de modelo. El flujo de importación ya prepara el modelo.

## Ejemplo local

Se ha añadido a Papelería Horizonte el conjunto independiente «Ejemplo: ventas,
productos y proveedores», con datos totalmente sintéticos de
`data/demo/papeleria/`. Contiene 12 ventas, 5 productos y 3 proveedores ficticios.
Las conexiones ventas → productos y productos → proveedores son muchos a uno;
las comprobaciones de todos los registros encuentran cero referencias ausentes
y cero filas adicionales. El conjunto original permanece disponible.

`scripts/dev/add_demo_tables.py --business-id UUID` reproduce el ejemplo usando
el flujo normal de carpetas: originales descargables, tablas preparadas y
revisiones del modelo. Repetirlo reutiliza el conjunto y conserva cambios
posteriores, incluida una relación rechazada. Solo declara las dos conexiones
conocidas de este ejemplo sintético.

## Validación

- `npm --prefix frontend test`: 236 pruebas, 31 archivos, pasan.
- `npm --prefix frontend run build`: TypeScript y Vite pasan; aviso preexistente
  de tamaño de algunos bundles.
- `npm --prefix frontend run lint`: sin errores, 27 avisos preexistentes.
- `.venv/bin/python -m unittest discover -s tests -p 'test_data_knowledge.py'`:
  15 pruebas pasan con PostgreSQL y comprobaciones completas de las tablas.
  Incluye originales, reutilización, aislamiento del negocio, cardinalidades,
  cobertura y conservación de correcciones al repetir el ejemplo.
- Navegador local: Datos permanece seleccionado y la URL sigue en Mi negocio al
  abrir el panel de 420 px. El diagrama de tres tablas y dos conexiones aparece
  al entrar en Datos, sin pulsar «Ver relaciones».
- Escritorio de 1280 × 900: burbuja de aproximadamente 309 px junto al campo
  flotante de 656 px, separados por 14 px y sobre fondo exterior transparente.
- Móvil de 390 × 844: ancho del documento 390 px, sin desbordamiento horizontal;
  el diagrama conserva su desplazamiento dentro de su propio contenedor.
- Capturas privadas en `.local/checks/2026-10-06-context-bubble.jpg` y
  `.local/checks/2026-10-06-data-side-chat.jpg`, excluidas de Git.

No se consultó un modelo externo ni se enviaron mensajes durante la comprobación
en navegador. Las relaciones de otros conjuntos conservan su estado de revisión;
no se infieren conexiones por coincidencias de nombres.
