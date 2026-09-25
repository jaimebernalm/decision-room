# Centrado y confirmación de eliminación de chats

**Fecha:** 25 de septiembre de 2026.

La lista de conversaciones queda centrada en el área principal. Al pulsar la X de un chat aparece un diálogo propio de la aplicación, centrado, que identifica el chat y avisa de que el usuario ya no podrá acceder a él. «Cancelar» recibe el foco inicial y cierra el diálogo sin enviar ninguna petición de eliminación. «Eliminar chat» ejecuta la petición solo después de la confirmación. No se muestra una sección de chats eliminados, la API no los incluye en la lista y no ofrece una acción de restauración.

## Comprobaciones

- `node --test tests/test_dashboard_ui.cjs`: 19 pruebas correctas, incluido cancelar sin petición y confirmar con una única petición.
- Dos pruebas de conversaciones en PostgreSQL local: el chat eliminado desaparece del listado y de la búsqueda, no se puede abrir ni continuar y la ruta de restauración responde 404.
- `node --check decision_room/web/static/app.js` y `git diff --check`: correctos.
- Navegador local: no aparece una sección de chats eliminados; el diálogo muestra el nuevo aviso y, al pulsar «Cancelar», se cierra y el chat sigue visible.

No se confirmó el borrado de ningún chat del espacio local durante la comprobación visual.
