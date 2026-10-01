# Mi negocio: información organizada y compacta

Este ajuste de presentación continúa la ficha de 2.5.5 y su migración a React
de 2.5.8. Conserva los contratos de memoria, revisiones, datos y selección de
contexto. No amplía ni cierra capacidades analíticas del plan del producto.

## Secuencia de ejecución

1. Reorganizar Información: cabecera con nombre y pestañas Información, Datos e
   Historial; presentación original dentro de Información y plegada. Cuando no
   haya recuerdos activos, mostrar una presentación breve como alternativa.
   Agrupar recuerdos en Sobre el negocio, Operativa, Objetivos y preferencias y
   Por revisar. Usar tipo, tema y ámbito existentes, sin generar hechos nuevos.
2. Sustituir tarjetas por filas: texto completo, avisos de revisión y ámbito o
   fechas cuando sean relevantes. Menú accesible para editar, consultar detalles,
   confirmar cuando el contrato lo permite y retirar. Conservar origen, citas,
   alternativas, revisión y conversación en el detalle; mantener formularios y
   control de concurrencia existentes.
3. Comprobar recorridos: pestañas, grupos, presentación alternativa, teclado,
   detalles, edición y retirada con revisión exacta, errores y selección como
   contexto. Ejecutar pruebas de frontend, compilación, lint y revisión visual
   en escritorio y móvil con datos ficticios. Revisar el diff y los archivos
   preparados para un repositorio público; guardar un commit local del ajuste.

## Criterios de cierre

- El texto inicial y los controles secundarios no dominan la vista habitual.
- Ningún recuerdo activo desaparece; los retirados y sustituidos siguen en el
  historial. Las dudas y contradicciones se distinguen de información confirmada.
- La edición, confirmación y retirada conservan negocio, fact_id, revisión e
  idempotencia existentes. Los errores no ocultan información ni cierran edición.
- Los menús se pueden utilizar con teclado y en pantallas táctiles; las filas
  admiten texto largo y la navegación no desborda el ancho de móvil.
- Procedencia, fechas y versiones siguen disponibles; selección de contexto y
  navegación a conversación de origen continúan funcionando.

Estado, 30 de septiembre de 2026: implementación y comprobaciones completadas
siguiendo los tres incrementos. Véanse las
[pruebas y límites](../validation/2026-09-30-dossier-ui-check.md).

## Refinamiento visual de los grupos

1. Separar cada grupo en una caja con borde, esquinas redondeadas y espacio
   entre grupos; destacar su cabecera y mantener compactas las filas interiores.
2. Usar el color de interacción de la barra lateral para el cursor sobre filas
   y cabeceras, y para el foco de teclado dentro de una fila. Conservar plegado,
   menús, selección de contexto y alineación con el nombre del negocio.
3. Comprobar la ficha y selección de contexto, compilación y lint; revisar
   escritorio, móvil y modo oscuro. Guardar un commit local tras revisar el diff.

Estado: refinamiento completado y validado el 30 de septiembre de 2026.

## Acciones directas para propuestas y conflictos

1. Ofrecer confirmar y descartar en la fila de una propuesta válida al pasar el
   cursor o enfocar sus acciones. Dejarlas visibles en móvil y dispositivos sin
   cursor. Descartar retira al historial mediante el contrato existente.
2. Mostrar Resolver conflicto junto al aviso, con comparación de versiones y
   posibilidad de elegir una como borrador o escribir una corrección. Guardar
   requiere una acción explícita y conserva revisión, ámbito e idempotencia.
3. Añadir un texto largo ficticio a la demo; comprobar lectura y acciones en
   escritorio/móvil, errores, cancelación, persistencia del borrador y selección
   de contexto. Revisar y guardar un commit local.

Estado: acciones implementadas y comprobadas el 30 de septiembre de 2026.
