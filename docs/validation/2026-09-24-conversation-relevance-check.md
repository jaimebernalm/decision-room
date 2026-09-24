# Corrección de pertinencia de respuestas del chat

Corrección de los pasos 2.5.4 y 2.5.6, 24 de septiembre de 2026.

## Causas comprobadas

- El contrato de conversación solo permitía recuperar memoria o evidencia,
  investigar, aclarar o declarar información insuficiente. No ofrecía respuestas
  de fecha, hora o capacidades, ni proporcionaba un reloj al modelo.
- Una consulta de fecha eligió `remember`; la aplicación volcó la memoria.
- Una consulta vaga sobre lo último ocurrido eligió `investigate` y abrió un
  análisis, aunque el usuario no había pedido calcular nada.
- Una explicación de hallazgo sí seleccionó su referencia, pero la interfaz
  presentó cifras, gráficos y secciones de informe antes de una respuesta breve.

## Cambios

- El contexto guarda fecha, hora, zona del servidor y capacidades disponibles.
  Las preguntas simples de reloj se resuelven directamente, sin extraer memoria;
  las variantes lingüísticas también pueden seleccionar `respond`. Las respuestas
  de reloj persisten como respuestas históricas, sin cambiar al recargar.
- `conversation-v3` distingue contexto guardado, capacidades, recencia,
  explicación de un cálculo y petición de análisis nuevo. Las preguntas vagas
  de recencia buscan informes primero. Si faltan informes, presentan los datos
  disponibles y explican que aún no se ha verificado su periodo completo.
- Los identificadores de tabla y análisis se distinguen explícitamente en las
  instrucciones de recuperación. Un campo `question` redundante en una búsqueda
  se ignora; nunca se muestra ni ejecuta como respuesta.
- Las respuestas con evidencia muestran primero fragmentos revisados pertinentes:
  resultado/interpretación, método, o periodo y límites según la pregunta. Las
  cifras y gráficos quedan en «Ver datos y evidencia». El modo se conserva al
  recargar y sigue sujeto a la versión aprobada del informe.
- Una referencia explícita a un hallazgo limita la explicación a ese informe y
  hallazgo, aunque el modelo deje vacía su selección de afirmaciones.

## Validación

- Regresión completa: **254 pruebas Python** correctas. Tras ajustar la tolerancia
  al campo redundante de búsqueda, se repitieron las **25 de conversación**.
- **14 pruebas JavaScript** correctas, incluida respuesta visible antes de la
  evidencia plegada y escape del texto recibido.
- Siete escenarios con GPT-6 Luna: variante de fecha, recencia con informe,
  explicación del método, hallazgo seleccionado, petición externa, ausencia de
  datos y datos sin revisión. Los dos últimos usaron respuestas de recuperación
  controladas; el resto consultó referencias existentes de la instancia local.
  Se comprobó además la ruta directa de fecha sin llamada al modelo.
- En el navegador: envío por Enter, fecha real del servidor, consulta de recencia
  resuelta sin iniciar un trabajo analítico, respuesta breve y evidencia plegada.
  Esta comprobación detectó y permitió corregir el rechazo del campo redundante.

## Límites

La hora corresponde al servidor y se etiqueta como tal. No se añade navegación
web ni acceso a actividad empresarial en tiempo real. La redacción analítica
continúa usando contenido revisado; no se permiten cifras ni conclusiones nuevas
generadas libremente. La selección de intención de preguntas abiertas sigue
dependiendo del modelo: estos escenarios son regresiones concretas, no una
garantía de pertinencia para cualquier formulación. Los mensajes históricos
incorrectos no se reescriben; las preguntas nuevas usan el contrato actualizado.

Los registros de pruebas con contexto local permanecen fuera de Git.
