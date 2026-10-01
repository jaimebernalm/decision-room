# Edición compartida de la presentación · 2.5.18

## Alcance acordado

Inicio, informe y chat comparten los nombres y las ediciones del mismo elemento.
El catálogo aporta etiquetas cuando la clave es única y la relación está comprobada.
El propietario puede editar títulos, nombres y formato de cifras directamente o
pedírselo al chat. Las cifras, referencias, cálculos y aprobación analítica original
se conservan. Una unidad de significado distinto exige una corrección analítica.

## Pasos

1. **2.5.18.1 — Catálogo y presentación común.** Resolver nombres desde las tablas
   preparadas del mismo negocio/conjunto, verificar integridad y unicidad y excluir
   correspondencias ambiguas o rechazadas. Compartir la proyección entre Inicio,
   informe y PDF; conservar claves estables y los códigos originales en procedencia.
   Comprobar aislamiento, ambigüedad, valores y publicación retirada.
2. **2.5.18.2 — Edición directa y versiones.** Un editor contextual para informe,
   indicador, gráfico y hallazgo, con títulos, nombres y formato. Persistir revisiones
   de presentación vinculadas al hash analítico, con control de concurrencia,
   historial, consulta de versiones y deshacer. Sincronizar Inicio/informe/PDF.
   Conservar la presentación original; rechazar cambios de cifras y unidades
   incompatibles. Comprobar persistencia, ediciones concurrentes y fronteras HTTP.
3. **2.5.18.3 — Acciones del chat y aceptación.** El modelo utiliza un contrato
   estructurado de edición contra elementos autorizados y el mismo servicio del
   editor. Solo comunicar cambios realizados con recibo del servidor; reenvíos
   idempotentes. Comprobar las tres vías con pruebas controladas, modelo real y
   navegador en escritorio/móvil sobre Bruma, conservando su evidencia histórica.
4. **2.5.18.4 — Aclaración de unidades y acciones compactas.** Cuando el análisis
   no especifica la unidad de un recuento, permitir al propietario escribir su
   etiqueta visible desde el editor o solicitarla al chat. Guardar la unidad
   original y la procedencia de la aclaración, sin convertir cantidades ni cambiar
   unidades conocidas incompatibles. Agrupar Editar, Fijar/Desfijar y Ocultar en
   un menú de tres puntos por tarjeta. Comprobar guardado, restauración, exportación,
   chat, navegación por teclado y disposición móvil. Completado.

## Decisiones de implementación

- La edición crea una **revisión de presentación**, separada de la revisión
  analítica aprobada. No se modifica un informe aprobado bajo su hash original.
- Los nombres de catálogo describen la correspondencia en los archivos; no
  certifican procedencia real, causalidad ni semántica monetaria.
- Una edición de nombre se aplica a ese código dentro de la presentación del
  informe, en todas sus apariciones. Otro conjunto o informe no hereda cambios
  silenciosamente. Los títulos se aplican al elemento seleccionado.
- El cliente ve dónde se aplicará el cambio y puede restaurar una versión anterior.
- Una unidad de recuento sin especificar se puede aclarar mediante una etiqueta
  solicitada por el propietario. Las opciones sugeridas no son una lista cerrada
  de datos del catálogo. La aclaración se registra como presentación del propietario
  y conserva la unidad original del análisis; no realiza conversiones.
- El historial guarda la configuración y el resultado de cada revisión; las
  fuentes retiradas dejan de poder publicarse también con etiquetas personalizadas.

## Estado

**2.5.18.1 completado:** 12 pruebas de catálogo/proyección/Inicio correctas,
comprobación local de las nueve etiquetas de Bruma y sus cifras originales.
**2.5.18.2 completado:** 60 pruebas backend (edición, Inicio y frontera web),
114 pruebas frontend, build y lint correctos. Edición real desde Inicio de Bruma
comprobada en el informe. Se conserva el hash analítico; historial y restauración
crean revisiones nuevas.

**2.5.18.3 completado:** edición estructurada desde el chat, recibo transaccional
del servidor y deshacer; contexto y adjuntos utilizan la presentación vigente.
Las preferencias de presentación no se convierten en hechos del negocio.
Exportación HTML sincronizada y lectores concurrentes compatibles con el bloqueo
exclusivo del análisis. Regresión backend: 122 pruebas; contratos/contexto/memoria:
57; catálogo/Inicio y comprobaciones finales: 19. Estas suites comparten algunos
casos. Frontend: 117 pruebas, build y lint correctos. Aceptación con GPT-6 Luna,
navegador en escritorio/móvil y PDF real de Bruma. Véase la
[validación completa](../validation/2026-09-30-presentation-editing.md).

**2.5.18.4 completado:** unidad visible libre para recuentos sin especificar,
con unidad original y procedencia del propietario conservadas. Las unidades
conocidas incompatibles siguen rechazándose. Menú de tres puntos en todas las
tarjetas de Inicio; editor, fijación y ocultación conservan su comportamiento.
44 pruebas backend, 120 frontend, build y lint correctos. GPT-6 Luna guardó la
etiqueta solicitada en Bruma, comprobada en Inicio, informe, HTML y PDF. Navegador
en escritorio y móvil, sin guardar previsualizaciones de prueba.
