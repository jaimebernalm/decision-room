# Selección del diagrama y presentación en su sitio

Refinamiento del paso 2.5.5, comprobado el 7 de octubre de 2026.

- En modo Seleccionar, las tablas del diagrama se resaltan al pasar el cursor o
  enfocarlas. Clic, Enter y Espacio alternan su selección sin abrir detalles.
  Tablas y diagrama comparten la misma referencia de tabla preparada, con su
  revisión, y no duplican adjuntos. Se conservan conexiones y mapa completo.
- El color cubre tanto los rectángulos como las capas de filas que genera Mermaid.
  Fuera de la selección, las tablas siguen abriendo sus detalles. Los modelos
  pendientes de actualización permanecen consultables sin ofrecer contexto vigente.
- Editar presentación sustituye el texto por un campo en Información, con Guardar
  cambios y Cancelar. Usa el servicio de perfil existente, mantiene el nombre y
  envía la revisión de inicio del borrador. Un error conserva el texto pendiente;
  cancelar restaura el texto guardado y devuelve el foco a Editar presentación.
  El texto aceptado se muestra mientras se refrescan la ficha y el espacio.

## Validación

1. Suite frontend completa: 282 pruebas correctas. Incluye selección y hover de
   nodos, teclado, selección compartida con la lista, referencias versionadas,
   conexiones/mapa, modelos pendientes de actualización, cancelación sin escrituras,
   guardado de la presentación, revisión del nuevo contexto y conflicto sin perder
   el borrador ni salir de Información.
2. `npm run build`, `npm run lint` y `git diff --check`: correctos. Permanecen
   avisos anteriores del proyecto; sin avisos nuevos en los archivos modificados.
3. Navegador local a 1440 × 1100: selección directa de una tabla, hover sin selección,
   tarjeta equivalente en Tablas, conexión y mapa completo. Se verificó el color
   calculado de las capas visibles del SVG. Edición en su sitio y cancelación de
   un borrador temporal con recuperación del texto original.
4. Revisión a 390 × 900 y 320 × 900: controles de edición visibles sin desbordamiento
   horizontal; selección directa de un nodo a 390 píxeles. Se restauró el tamaño
   habitual del navegador y se retiraron únicamente los adjuntos de prueba.
   Capturas en `.local/visual-checks/`, excluidas de Git.
5. Diff revisado para publicación: código y ejemplos sintéticos; sin credenciales,
   datos del navegador, rutas personales ni archivos generados en el commit.
   Se preservan los cambios previamente preparados por el usuario en otros archivos.

El guardado y los conflictos se comprobaron mediante pruebas del frontend contra
respuestas simuladas del contrato existente. La revisión visual canceló los
borradores y no modificó el perfil guardado. No se cambiaron contratos del servidor.
