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

## Elección visible, grupos personalizados y barra de herramientas

1. Sustituir los botones sin indicador de elección por opciones de versión
   seleccionables. Mostrar la elección, permitir una solución escrita y mantener
   Guardar solución visible mientras se revisan los datos. Comparar versiones
   distintas aunque el contrato repita la información actual en alternativas.
2. Guardar por negocio nombres, orden, grupos nuevos y asignaciones de recuerdos
   en una configuración de presentación versionada. Por revisar sigue reservado;
   eliminar un grupo conserva sus recuerdos mediante clasificación automática o
   Sin grupo. Comprobar aislamiento, validación y escrituras concurrentes.
3. Acercar Actualizar a las pestañas, ofrecer Personalizar grupos y mover datos
   desde cada fila. Validar recorridos reales del navegador, móvil/teclado,
   pruebas de frontend y API/persistencia, compilación y revisión pública del diff.
   Crear un commit local al cerrar el incremento.

Estado: implementado y comprobado el 30 de septiembre de 2026. Selección visible,
guardado fijo, grupos persistentes y barra compacta; véase la validación adjunta.

## Jerarquía de controles y descripción para clasificar recuerdos

1. Dar mayor tamaño a las pestañas y convertir Añadir información en un botón
   circular con etiqueta visible. Mostrar el menú de fila con cursor, foco o
   apertura; mantenerlo visible en dispositivos táctiles.
2. Añadir descripciones editables y persistentes a los grupos, exigirlas al crear
   uno nuevo y entregarlas como datos al extractor. Clasificar recuerdos nuevos
   mediante un ID limitado a los grupos del negocio; conservar movimientos
   manuales y descartar una clasificación si cambia la configuración durante
   la extracción. No convertir descripciones en declaraciones del negocio.
3. Validar contratos, clasificación y concurrencia con PostgreSQL, formularios y
   navegación con pruebas frontend, y dimensiones/interacciones en escritorio y
   móvil. Revisar el diff público y guardar un commit local del incremento.

Estado: implementado y comprobado el 30 de septiembre de 2026; véase la validación.

## Añadir información dentro del grupo

1. Trasladar el botón circular a la derecha de cada cabecera, separado del
   control de plegado, y dejar Personalizar grupos en la barra superior. Mostrar
   grupos vacíos para poder empezar desde ellos. Bajar las pestañas y compartir
   el radio de las cajas con el contenedor y la selección activa.
2. Abrir un formulario con grupo fijo y sin selector de tipo para recuerdos
   nuevos. Guardar declaración y asignación juntas, con pertenencia validada e
   idempotencia; Por revisar crea propuestas y Sin grupo conserva ese destino.
3. Comprobar creación, errores y cancelación con teclado; persistencia atómica,
   reintentos y grupos retirados con PostgreSQL; cabeceras y navegación en móvil
   y escritorio. Revisar el diff público y crear un commit local.

Estado: implementado y comprobado el 30 de septiembre de 2026; véase la validación.

## Botón de grupo más discreto

1. Reducir el círculo a 36 px y el símbolo a 20 px; usar una sombra suave solo
   durante la interacción. Conservar 44 px en dispositivos con puntero táctil.
2. Comprobar compilación, lint y tamaños/apertura en la demo; revisar el diff
   público y guardar el ajuste en un commit local.

Estado: implementado y comprobado el 30 de septiembre de 2026.

## Acción con solo icono

1. Retirar la etiqueta permanente del botón y mostrar Añadir información en un
   tooltip con cursor o foco, conservando su nombre accesible con el grupo.
2. Verificar compilación, lint y tooltip/apertura en el navegador; revisar y
   guardar el ajuste en un commit local.

Estado: implementado y comprobado el 30 de septiembre de 2026.

## Lectura compacta y cabeceras completas

1. Igualar el ancho de Información y Datos. Aplicar el fondo de interacción a
   toda la cabecera; colocar el botón + antes de la flecha, conservando acciones
   independientes y el destino fijo del formulario.
2. Mostrar cada declaración en una línea con puntos suspensivos, sin recortar
   su contenido guardado. Abrir los detalles completos al pulsar el texto o
   mediante teclado, con el resto de la página visible detrás, lectura con
   desplazamiento y cierre que devuelve el foco a la fila. Mantener estados,
   conflictos y fechas relevantes visibles.
3. Comprobar texto largo, teclado, acciones, selección contextual y regresión
   de la ficha; compilación, lint y lectura/ancho/cabeceras en escritorio y móvil.
   Revisar el diff público y crear un commit local al completar el incremento.

Estado: implementado y comprobado el 2 de octubre de 2026; véanse los resultados
y límites en la [validación de lectura](../validation/2026-10-02-dossier-reading.md).

## Decisiones en el detalle y orden con arrastre

1. Añadir confirmar, descartar y corregir en el detalle, usando las revisiones
   y contratos existentes. Resolver conflictos dentro de esa misma ventana,
   conservando errores, borradores y retorno del foco.
2. Permitir arrastrar grupos desde un asa, con desplazamiento y reordenación
   visible. Conservar las flechas y el acceso con teclado, edición independiente
   y guardado explícito del orden, descripciones y asignaciones.
3. Comprobar decisiones, fallos, orden persistido y cancelación; probar el
   arrastre real y la lectura en escritorio/móvil, ejecutar las comprobaciones
   frontend y revisar el contenido público antes de crear un commit local.

Estado: implementado y comprobado el 2 de octubre de 2026; véase la
[validación de decisiones y orden](../validation/2026-10-02-dossier-actions-order.md).

## Avisos de error compactos

1. Usar el mismo fondo rojo suave y texto rojo que los estados de conflicto,
   con esquinas más redondeadas y ancho ajustado al contenido. Permitir que
   mensajes largos se envuelvan sin desbordar la pantalla.
2. Comprobar avisos de conexión y fallos dentro de los detalles en escritorio
   y móvil, regresión frontend, compilación y lint. Revisar y guardar el
   incremento en un commit local.

Estado: implementado y comprobado el 2 de octubre de 2026; véase la
[validación de avisos](../validation/2026-10-02-error-notices.md).
