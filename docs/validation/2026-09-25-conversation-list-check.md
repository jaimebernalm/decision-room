# Listado de conversaciones — 25 de septiembre de 2026

La vista «Conversaciones» usa filas compactas con 12 px de separación. Cada fila muestra título y fecha del último mensaje enviado, sin el enlace redundante «Abrir conversación». El enlace ocupa toda la tarjeta y la X sigue siendo una acción independiente. La tarjeta completa cambia de fondo al pasar el cursor o recibir foco.

## Comprobaciones

- Navegador local: 12 px entre tarjetas; el enlace y la tarjeta miden ambos 658 px en la ventana comprobada. El texto «Abrir conversación» ya no aparece. Al enfocar la X se resalta toda la tarjeta sin activar la eliminación.
- `node --test tests/test_dashboard_ui.cjs`, `node --check decision_room/web/static/app.js` y `git diff --check`.
