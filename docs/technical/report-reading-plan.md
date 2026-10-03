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

## 3.8.12.1. Lectura progresiva del informe y de Inicio

Incremento de presentación sobre la integración UI1/UI2; no modifica la revisión,
los cálculos ni el contrato analítico de la rama de calidad del informe.

1. Revisar el estado actual y, en lectura, los cambios de calidad. Agrupar título,
   conclusión revisada y gráficos de un hallazgo en una tarjeta. Abrir evidencia
   después del gráfico; conservar selección independiente de hallazgo y gráfico.
2. Mover el contexto general a «Sobre este informe» en la cabecera. Mostrar tres
   indicadores inicialmente y conservar el resto en un desplegable. Mantener
   periodo, revisión, informe parcial y límites de interpretación visibles.
3. Relacionar gráficos de Inicio con hallazgos del mismo informe y versión. Enlazar
   al hallazgo exacto y comprobar identidad/versión al abrirlo. Conservar selección,
   personalización, propuesta y fijados; reducir controles secundarios.
4. Probar comportamiento, compilación y lint; revisar informe abierto/cerrado,
   Inicio, móvil, teclado, selección y PDF. Documentar límites y guardar un commit
   local enfocado después de revisar privacidad y archivos preparados.

Los textos existentes pueden mezclar explicación y advertencias. No extraer la
primera frase ni truncar automáticamente conclusiones, captions o límites. Un
resumen breve nuevo requeriría contrato y revisión analítica en la rama de calidad;
este incremento conserva el texto revisado completo donde pueda condicionar la
lectura. Los periodos de Inicio pertenecen a cada tarjeta, sin un filtro global
que simule recalcular evidencia revisada.


## 3.9.8. Primera lectura y síntesis sobre la interfaz integrada

Incremento autorizado al continuar la calidad del reporte y su presentación.
El propietario pide presentación y síntesis de agentes juntas. No sustituye la
aceptación analítica pendiente de 3.9.7.

1. Mostrar el resumen revisado completo al inicio, una sola vez. Facilitar la
   navegación local entre hallazgos con sus títulos, conservando versión,
   selección contextual y detalle plegado. No sintetizar texto en el navegador.
2. Presentar orientación en bloques legibles: próxima comprobación y utilidad,
   condiciones y reacciones, con prioridad y límites completos. Conservar todas
   las alternativas y la compatibilidad histórica.
3. Formatear periodos temporales según el idioma sin cambiar coordenadas ni
   claves. Ajustar tooltips al gráfico agrupado y conservar cifras exactas,
   controles accesibles y periodos largos legibles también en móvil.
4. Coordinar planificador, analista y revisor para una síntesis breve, con funciones
   distintas para resumen, conclusión, interpretación y orientación. Añadir
   feedback editorial de longitud y repeticiones exactas, sin modificar datos,
   huellas de aprobación ni convertir preferencias en bloqueos.
5. Comprobar contexto, contenido, teclado, navegación sin llamadas, idioma,
   huecos y precisión; ejecutar regresiones, compilación y lint. Revisar Bruma y
   WWI en escritorio/móvil y probar redacción sobre evidencia congelada, guardando
   fallos y separando la prueba editorial de un recorrido completo de investigación.
6. Documentar resultados y límites, revisar archivos públicos y guardar commit
   local. Los informes históricos y sus evaluaciones permanecen congelados.

Estado: implementado y comprobado. Véanse [resultados y límites](../validation/2026-10-02-report-reading-and-synthesis.md).
No se amplía el esquema del informe ni se cambian los
cálculos, presupuestos del producto o requisitos de aceptación numérica y negocio.

## 3.9.8.1. Bruma Café en la web habitual

Incremento solicitado para ver la presentación y síntesis integrada con los
negocios habituales, en una rama separada de los cambios de UI simultáneos.

1. Crear una rama de integración e incorporar los commits terminados de UI y
   búsqueda, sin modificar el checkout donde se realizan esos cambios.
2. Trasladar únicamente el caso sintético de Bruma y sus fuentes, ejecuciones y
   revisiones a la base habitual. Validar primero la inserción en una transacción
   que se revierte; conservar identidades, archivos y aprobación del original.
3. Someter la nueva redacción a revisión real con la evidencia congelada. Guardar
   fallos y correcciones; publicar únicamente una versión cuya aprobación vigente
   valide el contrato. Presentar la entrega parcial y la comprobación pendiente.
4. Incorporar original y revisión a la biblioteca de Bruma, enlazar la actividad
   existente y comprobar informe, gráficos, PDF y aislamiento entre negocios.
5. Resolver compatibilidad de políticas históricas ausentes o nulas sin cambiar
   huellas de aprobación. Hacer concretos los errores de referencias de la
   evaluación sin relajar requisitos. Ejecutar regresiones e inspeccionar la web.
6. Documentar resultados, revisar privacidad y guardar commits locales. Mantener
   datos, scripts privados, capturas y respuestas de proveedores fuera de Git.

Estado: completado para lectura en la aplicación local habitual. Véanse
[resultados y límites](../validation/2026-10-02-bruma-web-integration.md).
No cierra la aceptación analítica de 3.9.7 ni constituye una nueva investigación.

## 3.9.8.2. Jerarquía de hallazgos y control de series

1. Aumentar títulos y numeración de hallazgos para distinguirlos de la prosa y
   de los títulos de gráficos. Conservar conclusiones completas.
2. Retirar el selector de puntos de gráficos sin desglose adicional guardado.
   Mantener tooltip, tablas exactas y navegación; si existe desglose, ofrecer
   acceso por teclado en un detalle plegado con título explícito.
3. Mostrar series visibles con fondo oscuro y ocultas con texto tachado y ojo
   cerrado. Explicar el clic, permitir restaurar y mantener una serie visible;
   conservar todos los valores originales aunque una línea se oculte.
4. Comprobar teclado, idioma, datos exactos y estados, compilar y revisar Bruma
   en la web habitual. Guardar evidencia local y commit tras revisión pública.

Estado: completado y comprobado. Véase [validación](../validation/2026-10-02-report-hierarchy-and-legend.md).

## 3.9.8.3. Lectura continua y leyenda discreta

Revisión solicitada después de probar el fondo oscuro y los controles de detalle.

1. Devolver la leyenda a fondo transparente con gris al pasar el puntero; mostrar
   un ojo cerrado únicamente para series ocultas y conservar teclado y estados.
2. Vincular el énfasis entre leyenda y curva/puntos: oscurecer y engrosar la serie
   señalada, atenuar las otras y restaurar la vista al salir. No cambiar escalas
   ni valores, y no enfatizar una serie oculta.
3. Presentar los hallazgos como secciones continuas con separadores finos. Cambiar
   el pie completo de detalle por un enlace discreto «Datos y fuentes». Reunir
   método, fuentes y tablas en una sola apertura, omitiendo controles vacíos.
4. Verificar estados, precisión, idioma, teclado y lectura histórica; ejecutar
   frontend, compilación y lint. Revisar Bruma en la aplicación habitual, guardar
   evidencia local y hacer un commit tras revisar archivos públicos.

Estado: completado. Véase [validación](../validation/2026-10-02-report-continuous-reading.md).
