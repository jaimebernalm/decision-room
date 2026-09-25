# Selección, cola y burbujas del chat — 25 de septiembre de 2026

## Comportamiento

- El chat abierto tiene fondo y texto destacados en el panel lateral, además de `aria-current="page"`. Si no está entre los seis más recientes, aparece debajo de ellos como «Chat actual» sin alterar su orden.
- El estado al pasar el cursor y el estado activo pintan la fila completa, incluida la zona de la X. La X conserva su área clicable y no dibuja un fondo rojo independiente.
- El primer mensaje pendiente no muestra «En cola». El indicador aparece únicamente cuando otro turno anterior está en cola, enrutamiento o procesamiento. Una respuesta histórica caducada, fallida o bloqueada no crea una cola visual ficticia.
- Las respuestas breves del agente ocupan el ancho de su contenido y se alinean a la izquierda, como las burbujas del propietario se ajustan y alinean a la derecha. Las respuestas con métricas o gráficos mantienen el ancho disponible para no comprimir la evidencia.

## Comprobaciones

- `node --test tests/test_dashboard_ui.cjs`: 18 pruebas correctas. Los casos nuevos cubren selección de un chat antiguo sin reordenarlo y el indicador de cola ante turnos completados, caducados, fallidos, bloqueados y activos.
- `node --check decision_room/web/static/app.js` y `git diff --check`.
- Navegador local: el chat actual queda resaltado; una respuesta breve mide 253 px dentro de una conversación de 621 px de ancho, y las tarjetas con contenido extenso conservan espacio para su lectura.
- Revisión visual posterior: la fila activa y el fondo bajo el cursor usan el mismo contenedor de 175 px; el botón de la X ocupa 28 px dentro de él, con fondo transparente y sin borde.

No se enviaron mensajes a los chats existentes durante esta comprobación; la lógica de cola se verificó con estados controlados en la prueba de interfaz.
