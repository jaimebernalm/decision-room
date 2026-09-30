# 3.8.12 · Lectura breve y descarga completa

## Comportamiento final

- Cabecera breve con primera frase completa del resumen revisado, periodo,
  condición de entrega y métricas visibles. No se inventa una nueva conclusión.
- «Contexto y alcance» y cada hallazgo se despliegan independientemente. Botón
  completo con «Ver detalle», chevron, hover, foco y teclado. Al abrir aparecen
  texto completo, interpretación y siguiente comprobación; métodos y fuentes
  mantienen sus controles existentes. Los gráficos permanecen visibles.
- Se conservan las referencias de selección contextual y el contenido aprobado.
- Botón de descarga con icono, sin etiqueta visible. Tooltip y nombre accesible
  «Descargar informe», estado ocupado, prevención de clic repetido y error visible.
- PDF generado en memoria desde la misma presentación validada de jobs/chats.
  Se reutilizan los límites vigentes de negocio, publicación y versión. La
  respuesta es un adjunto sin caché; las rutas HTML anteriores se conservan.
- PDF estático completo: resumen, cifras, alcance, preguntas, hallazgos, gráficos
  vectoriales, valores exactos, métodos, fuentes, cobertura y limitaciones. Paleta
  compartida de azules/grises, páginas numeradas y cabeceras de tabla repetidas.
  Ningún texto depende de abrir un desplegable en el PDF.

## Comprobaciones

1. **111 pruebas frontend, 16 archivos:** apertura con teclado, independencia,
   primera frase sin cortar decimales, detalles, escape de HTML, descarga Blob,
   nombre accesible y error de publicación sin descargar JSON como PDF.
2. **18 pruebas backend:** PDF completo y estático, tablas largas, filas finales,
   contenido extenso paginado, rechazo de datos no aprobados/caducados y regresión
   de materialización/gráficos.
3. **Una prueba HTTP con PostgreSQL y sandbox reales:** informe aprobado,
   autenticación 401, PDF 200 con attachment/no-store, rechazo 409 del gate. La
   ruta de chat comprueba delegación estructurada mediante mock de publicación;
   no representa una nueva ejecución real del analista de chat.
4. **TypeScript/Vite y lint:** completados sin errores. Se conservan avisos previos
   de Fast Refresh y tamaño del bundle.
5. **Bruma Café guardado:** comprobación web en escritorio y móvil de 390 × 844,
   teclado, apertura/cierre y ausencia de desbordamiento horizontal. Icono sin
   texto visible y tooltip correcto. Clic en navegador sin error visible; el
   navegador integrado no notificó el evento de descarga a la automatización.
   Se verifica por separado el flujo Blob/anchor en frontend y la respuesta PDF
   real HTTP de la vista local (200, application/pdf, unos 31 KB).
6. **PDF de Bruma:** 14 páginas rasterizadas e inspeccionadas, sin recortes ni
   solapamientos; títulos con su primer gráfico, leyendas y tablas legibles.
   Extracción independiente confirmó 119 fragmentos del reporte original,
   incluyendo declaraciones completas, interpretación, acciones, métodos,
   etiquetas de valores, alcance y limitaciones.

No hubo nuevas llamadas al modelo ni regeneración del análisis. Los resultados
pertenecen al escenario sintético guardado. La aceptación de calidad analítica
sigue siendo un trabajo separado. Archivos generados, claves y estado local
quedan fuera de Git; no se ha realizado push.
