# 3.8.12 · Lectura breve y descarga del informe

## Objetivo y decisiones

El cliente debe identificar las conclusiones y cifras rápidamente y desplegar
la explicación cuando quiera profundizar. La descarga será un PDF completo,
con estética blanca, tipografía sans serif, azules de la paleta y grises de apoyo.

- Cabecera: periodo, estado, título y resumen breve obtenido de una frase completa
  del contenido revisado. Contexto y alcance plegados contienen resumen completo,
  cobertura, pregunta y limitaciones. No generar conclusiones nuevas en la UI.
- Hallazgos: cabecera pulsable con número, título, primera frase completa y métricas
  asociadas cuando existan. «Ver detalle» permanente, chevron, hover más oscuro y
  foco de teclado. Cada hallazgo se abre independientemente. Dentro: declaración
  completa, interpretación, siguiente comprobación, método y fuentes existentes.
  Los gráficos siguen visibles y se conserva selección contextual.
- No esconder la condición de entrega parcial ni truncar unidades numéricas.
  Las advertencias que estén en la primera frase revisada siguen visibles.
- Descarga: botón con icono Download sin texto visible; tooltip y nombre accesible
  «Descargar informe». Estado ocupado, fallo visible y protección contra doble clic.
- Endpoints PDF para informes web y de chat reutilizan la comprobación vigente de
  negocio, aprobación, versión y publicación de la presentación estructurada.
  Conservar HTML existente por compatibilidad. Respuesta attachment, sin caché.
- Generar PDF en memoria con ReportLab, sin navegador ni red. Contenido procede de
  la misma presentación validada. Todas las secciones y fuentes están abiertas;
  tablas completas de valores y gráficos vectoriales con la paleta compartida.
  Paginación, cabeceras repetidas y líneas largas legibles; no controles plegables.

## Implementación y comprobaciones

1. Componente de sección desplegable y lectura breve compartida en ReportView.
2. PDF paginado, dependencia fijada, límites y descargas autenticadas.
3. Botón de descarga con errores recuperables en ambos tipos de informe.
4. Pruebas de navegación por teclado, apertura independiente, selección y estados
   de descarga; PDF completo, filas exactas, texto largo y límites de acceso.
5. Bruma Café real guardado: inspección visual web en escritorio/móvil y PDF
   rasterizado, contenido completo, gráficos y paginación.
6. Actualizar validación, revisar privacidad y commit local sin push.

Estado: completado y validado. Véase [evidencia de cierre](../validation/2026-09-28-report-reading-and-pdf.md).
Este paso cambia presentación y exportación; no cierra la evaluación de calidad
analítica ni regenera el informe de Bruma.
