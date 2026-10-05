# Correcciones posteriores a P1a v2 — 5 de octubre de 2026

Base df6ce59. Rama de correcciones separada; b0f69de (P1b) se conserva para
medirlo después sobre estas reparaciones. Sin fusiones ni llamadas reales.

1. Guardián de bucles, opción propia: detener la segunda objeción repetida ante
   borrador sin cambios o exigencia fuera del esquema. Integridad sigue bloqueada;
   forma/completitud pueden entregarse con resolución del controlador auditada y
   límites visibles. No simular una aprobación del revisor. Exponer capacidades,
   avisar de entregas sin cambios y un único foco estructurado por hallazgo.
2. Panorama: seleccionar huecos materiales por reglas genéricas y reproducibles;
   limitar alertas visibles y resumir los demás. Descarte solo con fuente
   verificable; enlace obligatorio a hallazgo de la misma combinación. Cifras,
   títulos de cambios y regla temporal claros. Justificaciones obligatorias con
   sales_panorama, incluso cuando falte una marca interna de versión.
3. Pruebas sin proveedor real, CSV entrecomillado con fecha y hora, esquemas,
   exportación y auditoría. Commits locales separados. P1b no se incorpora aún.

La selección de materialidad es descriptiva y explícita, no una causa ni una
prioridad comercial. La integridad semántica y relevancia de los motivos sigue
necesitando revisión; las pruebas no demostrarán utilidad real para el dueño.

## Paso 1 implementado

`DECISION_ROOM_REVIEW_LOOP_GUARD=true` activa el guardián (por defecto apagado),
también disponible como `review.start(review_loop_guard=True)`. El segundo
rechazo de la misma objeción, con borrador idéntico o recuento imposible, termina
la revisión. Solo forma/completitud clasificadas, sin fallos de números, significado,
gráficos ni comprobaciones mecánicas, permiten entrega limitada. Una objeción nueva
sin resolver o sin clasificar impide esa entrega. No se inventa un evento approve:
la resolución del controlador queda firmada junto al borrador, con objeciones abiertas,
verificación `controller_qualified_delivery` y límites visibles cuando afectan al dueño.

El esquema declara un único foco por hallazgo; el revisor comprueba si la prosa
oculta otros focos. Este contrato no permite demostrar automáticamente la veracidad
de la clasificación semántica hecha por el modelo. No es aprobación independiente.

Validación: 29 tests (`test_review_loop_guard`, `test_review`,
`test_model_strict_schemas`, `test_presentation_controller_ownership`), PostgreSQL
propio y modelos simulados. Incluyen tres bucles, controles apagado/integridad,
progreso real, objeciones nuevas, auditoría, exportación y reanudación. Sin API real.
