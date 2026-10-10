# Contexto compacto y relaciones con Mermaid — 6 de octubre de 2026

## Alcance

Petición del propietario: burbuja más pequeña, circular y próxima al campo;
presentación más clara de tablas y relaciones, sugiriendo Mermaid.

El contexto pendiente usa cápsulas con borde completamente redondo y unión
pequeña. El conjunto seleccionado mide 30 px de alto y queda a 3 px del campo.
Los adjuntos pendientes también se compactan, conservando retirada individual
y el diálogo con su vista previa completa.

El diagrama ER anterior se sustituye por Mermaid 12, cargado bajo demanda.
Muestra hasta ocho columnas por tabla, priorizando las utilizadas por conexiones;
los detalles existentes conservan todas. Las claves primarias se indican solo
cuando están declaradas y son válidas. El marcador de tipo genérico «dato» no
declara una interpretación nueva de las columnas. Se conserva la cardinalidad
registrada, con mínimos opcionales porque el modelo no declara obligatoriedad.

La disposición pasa de horizontal a vertical al reducirse el contenedor.
Incluye zoom, ajuste, selección de tablas y conexiones, foco y activación con
Enter/espacio. Búsqueda e historial se pliegan inicialmente. Las comprobaciones
y correcciones siguen asociadas a la revisión exacta.

## Comprobaciones

- `npm --prefix frontend test`: 242 pruebas correctas en 33 archivos.
- `npm --prefix frontend run build`: correcto, incluido TypeScript.
- `npm --prefix frontend run lint`: sin errores; conserva los avisos existentes.
- Pruebas del generador con el parser real: sintaxis ER, cardinalidad, claves
  compuestas, columnas prioritarias y nombres con HTML/directivas/comillas.
- Pruebas del componente: selección con área ampliada y teclado, conservación
  de selección sin recalcular disposición, descarte de render antiguo y fallo
  del renderizador con mensaje de alternativa.
- Navegador local: ejemplo existente de ventas, productos y proveedores con
  dos conexiones; selección de tabla y relación, detalles, Tab/Enter entre
  conexiones, zoom y ajuste.
- Vista de 390 × 844: ancho del documento 390 px, diagrama vertical de unos
  220 px dentro de su área desplazable, cápsula de 30 px; sin desbordamiento
  horizontal de la página. Restaurado el tamaño normal al terminar.

Capturas y registros se conservan en `.local/checks/`, fuera de Git.

## Límites y revisión

No modifica datos, inferencia ni validación de relaciones. Usa el conjunto
sintético cargado en el paso anterior; no crea otra copia. No se declara aquí
una evaluación nueva de calidad analítica ni del alcance de la entrega 3.

Mermaid usa `securityLevel: strict`, etiquetas sin HTML e identificadores
generados; los nombres subidos se codifican como literales. La selección se
vincula desde React al SVG generado. La dependencia y su lock se incluyen en
Git; estado local, capturas y archivos compilados siguen ignorados.

La auditoría de dependencias conserva ocho avisos altos del árbol previo y
dos bajos relacionados con KaTeX/Mermaid. No se aplicaron actualizaciones
automáticas de dependencias ajenas a este cambio.
