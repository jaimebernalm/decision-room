# Selección de conversaciones y esquinas de informes

Ampliación del paso 2.5.16, 27 de septiembre de 2026.

## Comprobaciones automatizadas

- 317 pruebas Python de regresión correctas. La última ampliación de seguimiento
  se volvió a validar con las cuatro pruebas PostgreSQL específicas de selección.
- 65 pruebas frontend correctas, incluidas selección desde Conversaciones,
  navegación conservando adjuntos, envío de referencias sin contenido del cliente
  y apertura inmediata del panel en las cuatro secciones.
- Compilación TypeScript/Vite correcta. Lint sin errores; permanecen avisos de
  Fast Refresh y componentes existentes, y el aviso de tamaño de bundles.
- Un chat sintético de 601 intercambios permite recuperar texto intermedio y
  paginar un mensaje de más de 10.000 caracteres, incluido su final. Páginas
  limitadas por bytes, también con caracteres multibyte.
- Comprobados ambos autores, mensajes posteriores excluidos de la captura,
  versiones duplicadas, cambios del contenido anterior, eliminación, otro negocio,
  identificadores inventados y acceso sin selección. La revisión rechaza una
  respuesta basada solo en la vista previa y permite la lectura original citada.
- Comprobado seguimiento sin volver a adjuntar y retirada del adjunto si se
  elimina la conversación original.

## Navegador y modelo real

Recorrido realizado sobre una base de demostración separada de los datos de uso:

1. Abrir un chat vacío en el panel desde Conversaciones, activar Seleccionar y
   adjuntar «Prueba de contexto largo · DEMO» sin abrir su página.
2. Ir a Informes conservando el adjunto. Filtrar una fila seleccionable y marcarla
   como última fila: captura visual y medidas DOM confirman borde interior de
   un píxel y radio inferior de 13 px, sin esquinas recortadas.
3. Quitar el informe y enviar una pregunta sobre la propuesta del chat adjunto.
   El modelo encontró «NUBE-47» en el intercambio 39 de 80 y respondió que no
   estaba aprobada. El dato no aparecía en la vista previa del inicio/final.
4. Ampliar a conversación completa, recargar y abrir el adjunto. El título, tipo,
   vista previa y enlace «Ver conversación original» se conservan; el enlace abre
   el chat correcto.

## Límites explícitos

La vista previa es un extracto, no un resumen automático completo. La búsqueda
actual es literal y el agente puede reformularla; no hay búsqueda semántica
específica dentro del adjunto. Se mantiene un presupuesto finito de consultas,
por lo que las respuestas deben reconocer lecturas parciales. Los chats vacíos
no se ofrecen como contexto y los chats eliminados no se pueden recuperar.
