# Reintento web y disponibilidad del modelo local

## Incidencia observada

El reintento pasaba el trabajo a la cola, pero LM Studio intentaba cargar un
modelo de unos 17,4 GB y lo rechazaba por memoria insuficiente. El motor exigía
además unos 5,2 GB de reserva para macOS; en el último fallo había unos 14,2 GB
disponibles. La petición tardaba unos 30 segundos y devolvía HTTP 400. El trabajo
regresaba a la pantalla de interrupción conservando su revisión y respuestas.

## Cambio

Para LM Studio local, el reintento consulta primero `/api/v1/models`. Si el
modelo del trabajo no está cargado, el servidor no responde o la respuesta no
es válida, devuelve una explicación sin encolar el trabajo ni generar texto.
El botón indica que está comprobando el modelo y permite intentarlo después.
Los proveedores distintos de LM Studio conservan su flujo anterior.

La lista de modelos cargados no garantiza que el motor pueda completar una
inferencia. La gestión de fallos durante la ejecución sigue siendo necesaria.

## Comprobaciones

- Suite completa: 122 pruebas correctas. Incluye disponibilidad del modelo,
  respuesta inválida, servidor inaccesible, identificador de instancia,
  aislamiento entre proveedores y reanudación desde la revisión guardada.
- La prueba HTTP verifica que un reintento sin modelo devuelve 409 y mantiene
  el trabajo interrumpido; al recuperarlo conserva las identidades y respuestas.
- JavaScript: comprobación de sintaxis y formato Prettier; diff sin errores.
- Computer Use: con el modelo descargado, el botón muestra el aviso sin pasar
  a progreso. La base de datos confirma que no se crea otra llamada al modelo.
- Con autorización del propietario, se cerró Chrome de forma normal para
  liberar memoria. El mismo modelo cargó correctamente en unos 11 segundos.
  Para la revisión se cargó con contexto de 65.536 tokens, dejando margen para
  su historial y salida; no se cambió el proveedor ni el modelo del análisis.
- Reanudación real desde la web: el analista completó la nueva versión en unos
  133 segundos y el revisor respondió en unos 96 segundos. El trabajo terminó
  con informe disponible, conservando las dos respuestas del propietario.
  Computer Use verificó el informe, los gráficos y el estado final en pantalla.
  Esta prueba acredita la recuperación técnica; no sustituye la evaluación
  semántica pendiente de la entrega 1.
