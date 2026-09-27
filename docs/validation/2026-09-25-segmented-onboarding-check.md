# Onboarding por pasos cortos — 25 de septiembre de 2026

El recorrido del primer informe presenta una decisión por pantalla: nombre del negocio, descripción, tipo de informe, pregunta concreta cuando se elige esa opción, archivo y resultado. La barra de progreso superior muestra tramos separados y no aparece la barra lateral del espacio cotidiano.

## Comprobaciones

- 18 pruebas JavaScript: rutas del onboarding, barra segmentada, ausencia de barra lateral y comportamiento del dashboard.
- 34 pruebas web Python: contrato de negocio, primer informe, recuperación, reintento y límites del servidor.
- Navegador local con datos ficticios: nombre → descripción → informe → pregunta → archivo; el borrador de descripción sobrevive a recargar.
- Vista de escritorio y ancho móvil de 390 px revisados; el contenido ocupa el ancho disponible sin desbordamiento horizontal.

La prueba local se devuelve al primer paso tras la revisión. La elección de archivo debe repetirse si se recarga la página antes de enviarlo, porque el navegador no permite recuperar automáticamente archivos seleccionados.
