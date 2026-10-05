# P3 — Propiedad de las notas del controlador

Base `5d0aae0`. Corrección separada de la limpieza P3c; misma opción
`owner_presentation`, sin llamadas reales al modelo.

El controlador insertaba tras cada `submit` el contador «Cobertura del encargo…»
en `limitations`, mientras el prompt editorial pedía retirarlo. P3 deja de
reinsertar ese texto en el borrador. Conserva `owner_coverage`, cobertura de
investigación, estados parciales y explicaciones concretas de las preguntas
pendientes. El contador se calcula aparte en `controller_annotations`, junto a
las notas de selección, para el contexto de revisión y la auditoría exportada.

El prompt `owner-presentation-v2-controller-notes` indica que la redacción de esas
notas exactas no es responsabilidad del redactor, también en borradores antiguos.
El feedback editorial excluye solamente coincidencias exactas. La excepción no
permite aprobar falsas coberturas, números erróneos ni respuestas incompletas
presentadas como completas; validadores y estándares de evidencia no cambian.
El control con P3 apagada conserva su comportamiento.

15 pruebas pasan: una conversación simulada reproduce el bucle y agotamiento en
el control; P3 completa la misma revisión en dos llamadas simuladas, con parcialidad
honesta y contador auditable. Se comprueba también que otra cautela añadida al texto
no obtiene la excepción por prefijo, además de persistencia y presentación P3.
PostgreSQL y Docker propios; ninguna llamada real al modelo. La conducta editorial
real sigue pendiente de medición. `git diff --check` correcto.
