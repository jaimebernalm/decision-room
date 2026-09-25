# Centrado y confirmación de eliminación de chats

**Fecha:** 25 de septiembre de 2026.

La lista de conversaciones y la sección de chats eliminados quedan centradas en el área principal, con un ancho máximo común. Al pulsar la X de un chat aparece un diálogo propio de la aplicación, centrado, que identifica el chat y explica que puede recuperarse desde «Chats eliminados». «Cancelar» recibe el foco inicial y cierra el diálogo sin enviar ninguna petición de eliminación. «Eliminar chat» ejecuta la petición solo después de la confirmación.

## Comprobaciones

- `node --test tests/test_dashboard_ui.cjs`: 19 pruebas correctas, incluido cancelar sin petición y confirmar con una única petición.
- `node --check decision_room/web/static/app.js` y `git diff --check`: correctos.
- Navegador local: el diálogo se mostró centrado sobre la página de conversaciones; al pulsar «Cancelar» se cerró y el chat siguió visible.

No se confirmó el borrado de ningún chat del espacio local durante la comprobación visual.
