# Recuperación tras rechazos de validación — intervención separada

Base: `af64f48` (reparación de contratos de continuidad). Rama:
`codex/feature/research-validation-recovery`. Extensión aislada de la fase 2;
no modifica presentación, prioridades analíticas ni criterios de aprobación.

## Activar y medir

- Control: `DECISION_ROOM_RESEARCH_VALIDATION_RECOVERY=false` (predeterminado).
- Candidato: `DECISION_ROOM_RESEARCH_VALIDATION_RECOVERY=true`.
- API: `research.start(..., research_validation_recovery=True)`.
- Independiente de `DECISION_ROOM_RESEARCH_CONTINUITY`.

Cargar la configuración después de definir la variable. Se congela en las opciones
de la investigación, se hereda en las ramas delegadas y entra en su huella de
idempotencia. Reanudar conserva la opción inicial. No hace falta cambiar la opción
de continuidad ni activar presentación. Comparar la misma revisión con esta
opción apagada/encendida permite atribuir su efecto.

## Política

1. Se conserva el intento de corrección existente. Solo **dos rechazos de validación**
   del investigador o del planificador activan la recuperación. No se interceptan
   indiscriminadamente errores de transporte, 429, solicitudes inciertas ni cambios
   de fuentes/conocimiento.
2. Se cierra la investigación como **parcial**. Los candidatos ya registrados se
   conservan. De tareas intentadas todavía abiertas se pueden registrar referencias
   a cálculos correctos y visibles, después de pasar el validador de dominio.
3. Estas altas las produce el sistema, con `system_recovery.source=system` y
   `interpretation=pending_independent_review`. La descripción dice que los cálculos
   necesitan interpretación; no reutiliza ninguna afirmación ni código rechazado.
   El cierre de continuidad explica que no se pudo inferir con seguridad una decisión
   ni un cálculo pendiente. No inventa una causa ni una recomendación.
4. En continuidad se conservan métricas y series de éxitos anteriores incluso tras
   un cálculo fallido, hasta el límite existente de referencias del contrato.
   Sin continuidad solo se registra el último resultado escalar correcto. Si no
   hay material utilizable se bloquea la tarea cuando su contrato lo permite;
   no se fabrica un candidato para forzar un informe. Resultados omitidos, fallidos
   u obsoletos no se promocionan. Todos los originales siguen guardados.
5. No hay una tercera llamada al modelo, nuevo Python, nuevas tareas ni aprobación
   automática. Las altas de recuperación son administrativas y pueden cerrar las
   tareas intentadas aunque se haya consumido el presupuesto de decisiones del modelo.
   El revisor recibe la parcialidad, referencias y procedencia de estas altas.
   Todavía debe interpretar, verificar y decidir si hay entrega publicable.
6. Las respuestas rechazadas quedan en `agent_calls`. Altas y referencias se escriben
   atómicamente antes del checkpoint. Reanudar tras una interrupción no vuelve a
   calcular, llamar al modelo ni duplicar candidatos. El coordinador también recibe
   la marca cuando la recuperación ocurrió en un trabajador.

## Validación

117 pruebas pasadas, incluidas 14 nuevas de recuperación y las regresiones de
continuidad, esquemas estrictos, contratos de fase 1, rondas, delegación y planificador.
Pruebas sintéticas de contrato e integración con PostgreSQL y Docker propios:
activado/desactivado; recuperación independiente de continuidad; corrección válida
en el segundo intento; evidencia previa a un error; evidencia ausente, obsoleta u
omitida; dependencias; rechazo del planificador; delegación; entrega al revisor;
interrupción después de escribir y reanudación; opciones congeladas; errores de
transporte que deben seguir propagándose. Sin llamadas reales al modelo ni lectura
de los datos de ensayo u oráculos.

La recuperación puede mejorar la tasa de entregas revisables; **no demuestra** que
mejore profundidad o utilidad. Medir por separado tasa de recuperación, publicación,
calidad y utilidad, conservando en el denominador los fallos y los cierres sin informe.
