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
gráficos ni comprobaciones mecánicas, permiten entrega limitada. Toda objeción de integridad o sin clasificar impide esa entrega; las
notas editoriales nuevas se conservan también, sin perder el informe por ellas. No se inventa un evento approve:
la resolución del controlador queda firmada junto al borrador, con objeciones abiertas,
verificación `controller_qualified_delivery` y límites visibles cuando afectan al dueño.

El esquema declara un único foco por hallazgo; el revisor comprueba si la prosa
oculta otros focos. Este contrato no permite demostrar automáticamente la veracidad
de la clasificación semántica hecha por el modelo. No es aprobación independiente.

Validación: 29 tests (`test_review_loop_guard`, `test_review`,
`test_model_strict_schemas`, `test_presentation_controller_ownership`), PostgreSQL
propio y modelos simulados. Incluyen tres bucles, controles apagado/integridad,
progreso real, objeciones nuevas, auditoría, exportación y reanudación. Sin API real.

Refuerzo de seguridad: una objeción de integridad abierta sobre el mismo borrador
no se puede desbloquear renombrándola como editorial. 19 pruebas de guardián y
endurecimiento pasan. Se actualizaron dos simuladores HTTP antiguos al transporte
asíncrono existente, con verificación de espera/estimación; no cambia el transporte.

## Paso 2: panorama y decisiones verificables

Misma opción `sales_panorama`, sin activar P1b. Contrato/prompt de presentación v3;
la marca interna histórica de la opción sigue siendo compatible con v2.

- Materialidad explícita, relativa al último día del archivo: abierto al cierre,
  o terminado en los 365 días anteriores y de canal entero, con al menos siete
  días esperados ausentes o al menos un mes habitual ausente. No usa la fecha
  de la máquina, nombres de negocios ni resultados de los ensayos.
- Todas las señales materiales del panorama congelado necesitan disposición.
  La apertura muestra cinco como máximo, ordenadas por días esperados ausentes
  (meses ausentes como segundo criterio), y resume los restantes tramos guardados.
  Se conserva la selección original del calculador: hasta diez tramos por dimensión;
  esta corrección no recalcula ni amplía las investigaciones congeladas.
- Un descarte exige un hecho concreto y una cita exacta de una fuente del dueño
  o referencias vigentes de un cálculo separado. La ausencia del panorama no se
  puede citar como prueba para descartarse a sí misma. Esas referencias se resuelven
  en los checks y quedan vinculadas al hash de aprobación.
- Si hay un hallazgo con esa combinación focal, debe enlazarse a él como prioridad.
  Un enlace a otro hallazgo debe al menos cubrir su tabla y combinación. Un foco
  tiene una sola combinación y sus valores se restringen a las dimensiones
  registradas cuando están disponibles. El revisor comprueba la prosa frente al foco.
- `panorama_priority` es obligatorio con panorama activado aunque falte el número
  interno de contrato; alternativa, razón y evidencia no pueden estar vacías.
  El panorama disponible sin evidencia vigente produce error antes de pedir una
  redacción, en vez de desactivar silenciosamente la obligación.
- Una comparación alternativa declara periodos y una frase de motivo, visible
  en web, HTML y PDF. Se distinguen cambios por canal y por producto/canal; las
  cantidades se presentan como «unidades registradas».

### Límites de las garantías

Los esquemas imponen forma, obligatoriedad y dominios de valores; las relaciones
entre campos del mismo borrador (p. ej. un `claim_key` recién creado) se verifican
al validar la entrega y generan corrección explícita. JSON Schema estricto no
expresa esas relaciones dinámicas. La veracidad/relevancia de un hecho, o si la
prosa esconde dos focos o una comparación distinta, sigue siendo juicio del revisor:
una cita existente por sí sola no demuestra una justificación válida. El prompt
exige rechazar como integridad los descartes basados solo en «no demuestra causa»
o fuentes irrelevantes. No se afirma que estas pruebas garanticen calidad semántica.

Se encontró una vía de omisión por marca de versión ausente. Sin inspeccionar la
petición efectiva del informe señalado no se atribuye a ella aquel caso concreto.

### Validación final

Batería de 97 pruebas sin proveedor real: contratos de panorama y esquemas estrictos,
1.200 métricas con enums acotados, materialidad y límite visible, descartes y enlaces,
justificaciones vacías, CSV real de importación con fechas entrecomilladas y hueco,
HTML/PDF, auditoría y hashes, bucles, caída entre persistencia y cierre, transporte
simulado y controles de integridad. PostgreSQL y almacenamiento propios.
`compileall` y `git diff --check` también pasan.

La cita exacta del dueño se trata como procedencia, no como porcentaje calculado
por el redactor; las afirmaciones porcentuales del informe mantienen su comprobación
aritmética. La decisión del revisor sobre reacciones sin soporte sigue bloqueando
la entrega, aunque se clasifique mal una objeción editorial.

Para medir: `DECISION_ROOM_REVIEW_LOOP_GUARD=true` activa solo el guardián;
`DECISION_ROOM_SALES_PANORAMA=true` activa estas correcciones del panorama.
Ambas opciones pueden compararse separadas. Generar nuevos borradores sobre las
investigaciones guardadas; no asumir que una disposición antigua sin prueba cumple
el contrato actual. Sin push, fusión ni incorporación de P1b.
