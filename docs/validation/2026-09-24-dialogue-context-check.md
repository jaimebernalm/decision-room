# Continuidad conversacional y saludos

Corrección de 2.5.4, 24 de septiembre de 2026.

## Diagnóstico comprobado

Los turnos estaban guardados, pero la petición al modelo incluía únicamente hasta
seis mensajes anteriores del propietario; omitía las respuestas del asistente.
El detector de saludos tampoco reconocía «hola buenos dias» como combinación sin
tildes. El modelo eligió `help` para ese saludo y `thanks` para una petición de
cortesía posterior. El prompt describía `thanks` como reconocimiento genérico y
la aplicación mostraba su respuesta fija «De nada». La siguiente expresión de
confusión volvió a llegar sin las respuestas anteriores del asistente.

## Corrección

- Saludos completos combinados y sin tildes; se devuelve el saludo correspondiente.
  Un mensaje con saludo y pregunta de negocio continúa hacia el modelo.
- `recent_dialogue` añade ambos lados de hasta seis intercambios recientes con
  contexto vigente. La respuesta anterior se limita a 4.000 caracteres con marca
  de truncamiento. No incluye trazas internas de revisión.
- Los hechos retirados no reaparecen desde el diálogo. La evidencia cuyo informe
  o versión ya no es vigente se oculta también en este contexto.
- `conversation-v4` distingue saludo, petición de devolver un saludo, agradecimiento
  real y reconocimiento simple. Permite entender una corrección o un seguimiento
  breve a partir de lo que el asistente dijo antes.
- El diálogo se etiqueta como historial, no como evidencia. Las citas del
  propietario usadas por el analista conservan su mecanismo anterior.

## Comprobaciones

Pasan **27 pruebas de conversación, 24 de memoria y 4 del contrato del modelo**.
Cubren el saludo combinado sin extraer hechos, acceso a las respuestas anteriores,
reparación de un saludo omitido y exclusión de hechos retirados del diálogo.

Con GPT-6 Luna se comprobaron cinco decisiones: petición de devolver el saludo,
confusión posterior al agradecimiento incorrecto, agradecimiento explícito,
reconocimiento simple y saludo seguido de una pregunta sobre el negocio. Se usaron
los intercambios registrados para los dos primeros y variantes coherentes del
contexto para los demás. Las cinco decisiones finales coincidieron con la intención.
Los registros y el contexto local permanecen fuera de Git.

La instancia local se reinició con la corrección. Las respuestas históricas se
conservan. El contexto automático sigue acotado a seis turnos y las respuestas
sociales siguen siendo frases renderizadas por la aplicación según la intención
elegida; esto no incorpora conversación libre ni memoria ilimitada.
