# Investigación adaptativa por rondas — paso 3.3

## Plan de trabajo y aceptación

1. Sustituir el conjunto fijo de investigaciones por una agenda reconstruible
   desde acciones persistidas. Un candidato puede abrir verificaciones o desgloses
   que citen sus métricas. Mantener claves, estado, prioridad y motivo de cierre.
2. Limitar rondas, investigaciones iniciadas, ejecuciones, decisiones, llamadas
   (incluidas consultas y correcciones) y tiempo. Terminar normalmente al agotarlos
   y conservar resultados parciales para la revisión independiente.
3. Recuperar acciones y ejecuciones con sus claves originales. Mantener preguntas
   y dependencias bloqueadas sin impedir trabajo independiente. Transmitir agenda
   y cobertura al informe revisado.
4. Validar control con PostgreSQL/Docker reales y modelos simulados explícitos;
   validar profundización real con un modelo sobre cinco tablas públicas de Wide
   World Importers (299.673 filas) y referencias CSV/Decimal independientes.

Criterios fijados antes de la evaluación real: al menos una profundización útil
vinculada a un resultado, cifras reproducibles sin errores materiales, límites y
paradas observables, recuperación sin duplicaciones, aislamiento entre negocios y
posibilidad de revisar un resultado parcial sin dar el resto por completado.
La comparación completa entre objetivos y contra 3.1 sigue correspondiendo a 3.6.

## Contrato

- Cada investigación conserva los campos del plan y una prioridad estimada de
  relevancia, magnitud, fiabilidad y coste (1–5) con justificación. La agenda se
  ordena por `relevancia × magnitud × fiabilidad / coste`. Son estimaciones del
  analista, no hechos medidos ni una puntuación de confianza de las conclusiones.
- `record_candidate.followups` propone hasta tres investigaciones nuevas con
  `stage=verify|breakdown`, claves únicas, tablas autorizadas e inspeccionadas y
  `basis_metric_keys` existentes en ese candidato. Heredan `parent_key` y una
  ronda más que su padre. El historial vincula además el candidato a la ejecución.
- Una propuesta bloqueada conserva la aclaración necesaria; no crea ni responde
  automáticamente preguntas del onboarding. Esa conversación se amplía en 3.4.
- `discard` conserva la razón de no continuar; no convierte trabajo en completado.
  `finish` permite detenerse por poco valor adicional. La agenda no fuerza hallazgos.
- Agenda y presupuesto se guardan en las estructuras JSON existentes; no hace
  falta otra migración. El grafo nuevo usa `research-v4`. Investigaciones antiguas
  siguen siendo consultables; para continuar una de la versión anterior, iniciar
  otra investigación con otra clave sobre el plan vigente.

## Límites y recuperación

Valores por defecto: 3 rondas, 6 investigaciones iniciadas, 12 ejecuciones Python,
3 intentos por investigación, 32 decisiones, 32 llamadas lógicas al modelo,
900 segundos desde creación y 24 elementos de agenda. Python mantiene su timeout
por ejecución de 30 segundos. El CLI expone límites configurables dentro de topes.
La aplicación web usa estos mismos valores.

El tiempo es un límite de admisión: no se inicia otra llamada o ejecución una vez
vencido. Una petición que ya estaba en curso conserva su timeout del proveedor y
sus reintentos HTTP acotados; no se garantiza interrupción exactamente a los 900 s.
El tiempo incluye una interrupción y no se reinicia al reanudar. Las llamadas son
solicitudes lógicas persistidas: los reintentos de transporte se registran en uso,
pero no constituyen llamadas lógicas nuevas. No se promete un tope monetario.

Las decisiones se escriben antes de ejecutar. Reanudar reutiliza la acción y la
clave de ejecución, incluso al recuperar un cálculo completado antes de caer.
Las consultas de memoria y correcciones consumen el mismo presupuesto de llamadas.
Llegar al límite devuelve `partial`, sin borrar candidatos ni errores anteriores.
Solo una revisión independiente puede aprobar su publicación.

El contexto conserva las últimas observaciones por investigación. Omite código y
logs de candidatos ya registrados, mantiene métricas/evidencia y conserva el código
completo en almacenamiento para el revisor. No resume automáticamente evidencias
que excedan el límite; registra la parada por contexto y el trabajo pendiente.

## Cobertura en la entrega

El revisor recibe la agenda ampliada y el motivo de parada. Al presentar un informe,
el controlador añade una nota de cobertura basada en las respuestas que realmente
incluye el informe (`question_coverage`), no en el número de cálculos terminados.
Enumera las preguntas sin completar en la entrega y añade el motivo de parada de
la investigación cuando fue parcial. Esa nota forma parte del contenido revisado
y del hash de aprobación. Se sustituye al revisar la entrega, conservando las
limitaciones sustantivas: un resultado calculado puede no estar incluido en ella. Aparece en la sección
existente de limitaciones de la interfaz y en la exportación. Los candidatos siguen
siendo provisionales aunque el programa se haya ejecutado sin errores.


Las referencias a series ofrecidas al redactor se emparejan con unidad y tipo de
gráfico: barras/tablas de hasta 36 puntos; líneas temporales diarias de hasta 366.
Los resultados mayores siguen en la evidencia; exponerlos exige seleccionar o
agrupar en Python con un criterio documentado. La deduplicación del contexto usa
una referencia explícita al informe completo, sin convertir su presencia en null.


El contexto del redactor y revisor declara las capacidades reales del canal:
`execution_artifact_downloads=false`. Un CSV del sandbox es evidencia interna;
no se anuncia como adjunto ni como entrega accesible al cliente. Si su detalle no
se incluye en métricas o gráficos visibles, la entrega conserva esa limitación.
