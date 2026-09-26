# Orden de chats y ficha compacta — 25 de septiembre de 2026

## Comportamiento

- El listado de conversaciones usa la fecha del último mensaje enviado por el propietario. Consultar una conversación no cambia su posición. La barra lateral se actualiza al enviar un mensaje sin tener que salir y volver al chat.
- «Mi negocio > Información» mantiene una presentación breve y agrupa los recuerdos activos en «Por revisar», «Sobre el negocio», «Preferencias y objetivos» y «Datos y definiciones». Cada grupo muestra el número de datos y puede plegarse.
- La búsqueda filtra por el texto de los datos, sin exigir tildes. La edición aparece al pasar el cursor o recibir foco; en pantallas táctiles permanece visible. Los detalles, el origen y las acciones secundarias se abren a petición.

## Comprobaciones

- Prueba de integración de conversaciones: crear dos chats, abrir uno sin moverlo, enviar en cada uno y verificar el orden tras cada envío.
- `node --test tests/test_dashboard_ui.cjs` y comprobación de sintaxis de `app.js` y `dossier.js`.
- `python -m unittest discover -s tests -p 'test_*.py'`: 275 pruebas correctas con la base PostgreSQL local de pruebas.
- Navegador local: grupos y filas compactas, búsqueda con y sin coincidencias y apertura de «Detalles y origen».
- `git diff --check`.

La clasificación por grupos usa los tipos, el alcance y el tema estructurado de cada recuerdo. Si esos campos son ambiguos, el dato aparece en «Sobre el negocio» y sigue disponible mediante búsqueda; ninguna ficha ni historial se elimina.
