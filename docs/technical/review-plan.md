# Paso 1.6: plan de revisión y presentación

1. Congelar la investigación de entrada y enlazar la revisión con la sesión del
   analista. Conservar contexto original, respuestas, plan, código, resultados y
   conversación visible en PostgreSQL y checkpoints LangGraph.
2. Pedir al analista un informe estructurado con afirmaciones y referencias a
   métricas realmente ejecutadas. La aplicación comprueba referencias, vigencia,
   evidencia y relaciones numéricas declaradas; no acepta texto como prueba.
3. Dar al revisor la versión exacta, el contexto del propietario, las evidencias
   y los controles. Puede pedir cambios o justificación, ejecutar comprobaciones
   en el sandbox, preguntar al propietario, rechazar o aprobar.
4. Devolver los reparos al analista con todo el contexto acotado y la conversación.
   Puede explicar, corregir el informe, recalcular, preguntar o retirar el trabajo.
   Una justificación no cierra un reparo: solo el revisor aprueba la nueva versión.
5. Pausar con `interrupt` para preguntas al propietario. Guardar la respuesta antes
   de reanudar; compartir la aclaración con la sesión e invalidar conservadoramente
   cálculos previos. Exigir evidencia nueva tras cambiar el conocimiento.
6. Limitar rondas, llamadas, Python, preguntas y contexto. Una caída no duplica una
   ejecución completada. Un límite deja trabajo sin aprobar y con diagnóstico.
7. Renderizar HTML desde datos estructurados, escapando texto y sin aceptar HTML
   del modelo. Mostrar estado, conclusiones revisadas, limitaciones y evidencia;
   conservar también el diálogo. No presentar borradores o versiones obsoletas
   como informes publicables. Una exportación estática es una instantánea fechada.
8. Probar conversación, defensa aceptada y rechazada, corrección de código,
   preguntas/respuestas con recuperación entre procesos, obsolescencia, límites,
   referencias ajenas y escape HTML. Separar modelos simulados de pruebas reales
   con Qwen, incluyendo DR-001. Contrastar cifras independientemente.

Se reutilizan LangGraph, PostgreSQL y el sandbox existentes. Analista y revisor
pueden usar el mismo modelo local con roles y llamadas separados; eso no garantiza
independencia de sus errores. No se añade compactación automática ni el dashboard.

Referencias de implementación: [interrupt](https://reference.langchain.com/python/langgraph/types/interrupt)
y [durabilidad](https://reference.langchain.com/python/langgraph/types/Durability).

Durante las pruebas reales se añadió un bloqueo independiente (`review-hold`):
el revisor aprobó un informe incorrecto en DR-002. El bloqueo conserva su decisión
histórica y evita presentar ese informe como disponible para entrega. Este control
no se atribuye al revisor; la calidad del modelo sigue pendiente de evaluación.


## Ampliación del paso 1.6: informe para el cliente

1. Separar el registro interno persistente y su HTML del documento del cliente.
2. Ampliar el contrato con contexto, cobertura, interpretación, siguiente
   comprobación y explicación del cálculo para cada hallazgo.
3. Incorporar barras, líneas diarias y tablas con referencias a métricas guardadas;
   validar valores, vigencia y fechas y cubrir esas referencias en la aprobación.
4. Hacer que el analista prepare el contenido y que el revisor examine también
   las visualizaciones y la utilidad de las conclusiones antes de publicarlo.
5. Probar publicación, bloqueo, evidencia, gráficos y escape; ejecutar un caso
   con el modelo real y contrastar sus resultados con el CSV independientemente.

Implementación y límites: [informe del cliente](client-report.md).
