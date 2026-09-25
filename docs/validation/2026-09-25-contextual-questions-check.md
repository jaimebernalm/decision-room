# Aclaraciones con datos a la vista · 25 de septiembre de 2026

## Resultado

- 34 pruebas web Python y 17 de interfaz JavaScript, más comprobación de
  sintaxis de ambos archivos JS y `git diff --check`.
- La API de vista previa solo sirve el archivo del negocio activo a una sesión
  autenticada. La prueba cubre CSV con `;`, las primeras 30 filas, la página
  siguiente y offsets inválidos. Los valores proceden del archivo original
  verificado por su firma.
- Las referencias de columna validadas del agente llegan a la pregunta web;
  la tabla señala esas columnas aunque el texto de la pregunta use una
  descripción más general. Sin referencia, la coincidencia exige el encabezado
  completo y evita resaltar fragmentos incidentales.
- En navegador, con un negocio y CSV ficticios aislados, se verificaron la
  pregunta y la tabla juntas a ancho de escritorio, la columna `amount`
  resaltada, y la barra lateral guiada. Al elegir «Total de fila», el campo
  libre queda vacío; al elegir «No lo sé», la opción anterior se desmarca; al
  escribir, «No lo sé» se desmarca. No se envió ninguna respuesta de esta prueba.
- A 390 px, la pregunta y la tabla permanecen legibles en vertical; el botón
  «Ver mis datos» lleva a la tabla. El tamaño del navegador se restauró tras
  comprobarlo.

## Alcance

La tabla pagina 30 filas y trunca cada celda a 200 caracteres para mantener la
respuesta acotada; el archivo completo se ofrece para descarga. La vista
muestra el CSV original, no una hoja de cálculo editable. Una pregunta de
revisión sin referencias de columna muestra la tabla sin un resaltado inventado
si no cita un encabezado literalmente. La sesión de navegador usa un modelo
controlado para verificar la interfaz y no demuestra calidad analítica.
