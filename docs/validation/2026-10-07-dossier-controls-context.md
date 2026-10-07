# Mi negocio: acciones discretas y contexto de relaciones

Incremento de la ficha de negocio, asociado al refinamiento de 2.5.5 del
[plan de interfaz](../technical/business-dossier-ui-plan.md).

## Comportamiento

- Personalizar grupos aparece debajo de la navegación de Información, con una
  acción discreta. Sigue disponible cuando no quedan grupos ni recuerdos y
  conserva la apertura del editor y el retorno del foco.
- Ver presentación original es un enlace desplegable compacto. Conserva el
  texto completo, su selección contextual y el acceso a Editar presentación.
- Seleccionar permite adjuntar una conexión del diagrama, una relación mediante
  su botón con nombre o Todo el mapa. El resaltado y el contador permiten quitar
  cualquiera de ellos. Fuera de selección, pulsar conexiones sigue abriendo sus
  detalles y comprobaciones; zoom, desplazamiento y columnas se conservan.
- Las vistas previas incluyen las claves y el estado semántico. Volver al origen
  desde el adjunto abre Datos → Relaciones, también tras recargar la ficha.

## Contrato del contexto

El nuevo tipo `data_model` conserva los cuatro campos del contrato de fuentes:
`source_id` identifica el conjunto, `source_version` la revisión guardada y
`element_key` es `model` o `relation:<id>`. El cliente envía referencias, nunca
contenido arbitrario como evidencia.

El servidor exige pertenencia al negocio, revisión actual y archivos vigentes
mediante el contrato existente del modelo. Una relación incluye únicamente sus
dos tablas; el mapa incluye todos los esquemas y relaciones guardados. Conserva
claves, cardinalidad, estado semántico, comprobaciones, alcance y límites de
descubrimiento. Se identifica como metadatos del modelo, sin convertir propuestas
o comprobaciones técnicas en resultados analíticos revisados.

Si cambia la revisión o el conjunto deja de estar disponible, se rechaza un
nuevo envío con la referencia antigua y el adjunto histórico aparece retirado.
La selección conserva el límite existente de ocho elementos y el límite de
contenido del servidor. El mapa completo incluye el modelo guardado entero,
también si la vista está filtrada o muestra solo algunas tablas.

## Comprobaciones

- Frontend: `npm test -- --reporter=json`, 271 pruebas correctas. Incluyen ratón,
  teclado, selección/deselección, mapa completo, vistas previas, recarga,
  retorno al contexto, modelo obsoleto y personalización sin grupos ni recuerdos.
- PostgreSQL y procesamiento reales, con datos sintéticos: 16 pruebas de
  `test_data_knowledge`, 58 de `test_conversations` y 2 de
  `test_context_references`, todas correctas. La prueba de envío verifica el
  contenido exacto entregado al chat, recarga, revisión posterior y retirada.
  Se comprueban aislamiento, claves inventadas, revisión incorrecta y contenido
  inyectado. Los modelos de las pruebas de chat son programados, no una evaluación
  de calidad de respuestas de un modelo real.
- `npm run build`, `npm run lint` y `git diff --check`: correctos. Se conservan
  avisos anteriores de chunks grandes y lint; sin avisos nuevos en los componentes
  añadidos o en el comportamiento modificado.
- Navegador local: selección mediante etiqueta de conexión, Tab y Enter dentro
  del diagrama, selección por botón con nombre y de todo el mapa; apertura normal
  de comprobaciones, vistas previas y vuelta desde Información a Datos/Relaciones.
  Se verifican Personalizar grupos y el despliegue de la presentación y su enlace
  de edición, sin guardar cambios en los datos de ejemplo.
- Escritorio de 1440 px y móvil de 390/320 px. A 320 px, el explorador ocupa
  280 px sin desbordamiento horizontal; los botones de relaciones siguen
  permitiendo selección. Se restableció el tamaño normal del navegador y se
  retiraron únicamente los adjuntos creados durante la comprobación.

Capturas y resultados completos permanecen en `.local`, fuera de Git. No se
modifican el procesamiento, las relaciones guardadas ni los formularios existentes.
