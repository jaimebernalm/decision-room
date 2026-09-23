# Validación de 2.5.6 · experiencia cotidiana

Fecha: 23 de septiembre de 2026. Negocios y archivos exclusivamente sintéticos.

## Cambios comprobados

- Inicio compacto, con compositor en el flujo de la página y acceso desde la cabecera.
  El compositor ocupa espacio propio y no cubre resultados. Se mantiene la identidad visual.
- Actividad de conversaciones antes de publicar un informe: en cola, en curso,
  aclaración pendiente, respuesta revisada sin informe, interrupción y retirada.
  Una retirada no anuncia un cálculo inexistente.
- «Preguntar sobre este hallazgo» conserva revisión, hash aprobado, clave del hallazgo,
  conjunto y fuentes verificadas por el servidor. Las referencias ajenas, modificadas,
  retiradas o incompatibles con el conjunto se rechazan. La referencia se conserva
  en el mensaje, contexto del agente y dependencias de nuevas investigaciones.
- Inicio, Nueva pregunta y Mi negocio comparten el envío durable del primer mensaje.
  El título es breve; la pregunta original se conserva íntegra. La selección de datos
  se muestra antes del envío y con su versión dentro del chat.
- El chat muestra cifras con etiquetas/formato del informe aprobado y gráficos de
  los hallazgos seleccionados antes de generar el informe. Las métricas técnicas
  permanecen en la respuesta interna, sin duplicarse en la interfaz.
- Biblioteca con búsqueda y filtros; diferencia disponibles, históricos, retirados,
  pendientes e interrumpidos. Cada informe de chat enlaza a su conversación.
- Se retira el aviso global de memoria procesada sin acciones pendientes. Se conservan
  los avisos de preparación, fallo y confirmación, con acceso a Mi negocio.
- El primer acceso abre el onboarding y su refresco no lo reemplaza. Tras guardar
  el negocio y en visitas posteriores se abre Inicio.

## Pruebas automatizadas

- `python -m unittest discover -s tests`: **243 pruebas, OK**.
- `node --test tests/test_dashboard_ui.cjs`: **12 pruebas, OK**.
- `node --check` para `app.js` y `dossier.js`; `git diff --check`: OK.

Las pruebas nuevas cubren referencias a hallazgos entre negocios y conjuntos,
revisión/hash/clave inválidos, fuentes derivadas en servidor, persistencia,
idempotencia tras retirada, apertura por el agente, dependencia en nuevas
investigaciones, retirada de respuestas, actividad anterior a la publicación,
formato del chat, títulos breves y permanencia del onboarding.
Las regresiones existentes cubren selección aislada de revisiones, cambios de
memoria, corrección de datos, publicación, pérdida de respuestas HTTP y doble envío.

## Prueba con modelo real y navegador

Se reutilizó una demostración con 14 filas, siete días y dos categorías:
la versión inicial sumaba 1.155 EUR; la corrección v2 suma 1.255 EUR; una actualización
v3 tiene 1.355 EUR. La v3 sigue sin analizarse: no se presenta como resultado revisado.

Desde el hallazgo «Distribución diaria y por categoría» de v2 se envió una pregunta
con Luna. En **dos llamadas de conversación** abrió la revisión exacta y eligió
ese hallazgo. No se creó un nuevo trabajo analítico. Se verificaron por separado
la revisión, la fuente corregida, la selección v2 pese a existir v3 y los puntos
de ambos gráficos: 120, 135, 150, 165, 180, 195, 310 por día; 870 y 385 por categoría.
El chat mostró los gráficos antes de solicitar un informe y el enlace de evidencia
llevó al hallazgo sin abandonar la conversación.

Recorrido visual y funcional:

- Inicio con informe histórico, aviso de datos nuevos y actividad desplegable.
- Biblioteca: filtro de retirados y búsqueda sin coincidencias.
- Selección de una versión desde Mi negocio antes de enviar la pregunta.
- Borrador conservado tras recarga; foco desde la cabecera al compositor.
- Onboarding en otro espacio vacío, guardado, vuelta a Inicio y persistencia tras recarga.
- Envío por Tab/Enter, error por modelo no configurado y borrador conservado.
- Escritorio de 1280 × 720 y móvil de 390 × 844, sin desbordamiento horizontal en Inicio.
  El compositor es estático y ocupa su propio espacio; ya no tapa gráficos al recorrerlos.

## Alcance

Se cierra el alcance funcional local de **2.5.6**. No equivale a la evaluación
integrada de **2.5.7**, ni a garantías generales de exactitud del modelo. La prueba
móvil usa un viewport de navegador y teclado de escritorio; el teclado virtual de
un teléfono físico, la carga elevada y la accesibilidad con lector de pantalla
no se han validado en esta ronda. Los datos y logs de la demostración quedan locales.
