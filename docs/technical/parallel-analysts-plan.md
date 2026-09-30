# 3.5 — Investigación dirigida con analistas en paralelo

## Objetivo y referencia

Conservar el informe aprobado de Bruma de 3.4.1 como referencia. Mejorar la
profundidad y la utilidad: descomponer un cambio material, comparar exposición,
priorizar hallazgos y proponer comprobaciones concretas sin inventar causas.
No cambiar la definición monetaria desconocida para facilitar la prueba.

## Diseño

1. El analista principal decide qué preguntas de la agenda merecen delegarse y
   explica el encargo. Hasta tres ramas independientes, sin delegación recursiva.
   Las dependencias del propietario siguen bloqueadas; los seguimientos parten
   de evidencia registrada. También puede investigar por sí mismo.
2. Cada rama recibe la misma versión de fuentes/definiciones, el contexto de
   evidencia del coordinador y un único encargo. Usa el ciclo existente de
   Python aislado, inspección y candidato. Puede proponer seguimientos; el
   coordinador decide cuándo ejecutarlos en una ronda posterior.
3. Persistir la asignación y reservar cuotas globales antes de lanzar tareas.
   Llamadas (incluidas correcciones/recuperación), ejecuciones y decisiones se
   reparten dentro del presupuesto existente; todas las ramas comparten plazo.
   El límite de llamadas y tokens por respuesta acota coste, sin prometer un
   límite monetario exacto. Registrar uso real para 3.6.
4. Unir entregas en orden determinista, conservando ejecuciones y procedencia.
   Una interrupción no pierde ramas completadas. Reanudar reutiliza llamadas,
   acciones y ejecuciones guardadas. Los errores de una rama no cancelan las
   demás. No publicar candidatos sin revisión independiente.
5. Síntesis explícita del principal: priorización, descartes, discrepancias y
   siguientes comprobaciones. El revisor conserva la última palabra; un
   desacuerdo no resuelto no se convierte en conclusión aprobada.
6. Mostrar hallazgos antes de sus gráficos asociados. Mantener modo secuencial
   con idénticos encargos y cuotas para comparar, sin afirmar de antemano que
   el paralelismo reduce tiempo o mejora calidad.

## Criterios de aceptación

- Reparto por el agente, límites de concurrencia y presupuesto, aislamiento entre
  negocios, dependencias, recuperación, no duplicación y contradicciones probados.
- Bruma: profundizar en cambios por canal/producto con contribuciones numéricas;
  comprobar días observados; acciones concretas y ordenadas, límites visibles.
- Cifras contrastadas independientemente contra los CSV; revisión completa y
  presentación comprobadas. Registrar fallos, llamadas, tokens y tiempos.
- La evaluación repetida entre varios objetivos/datasets sigue en 3.6.

## Contrato implementado

- `delegate` selecciona entre una y tres preguntas listas de la agenda y conserva
  la instrucción de cada una. El coordinador puede hacer una exploración inicial;
  después encarga los cálculos independientes a los subanalistas.
- `expand` permite al principal crear seguimientos desde un candidato registrado,
  sin sustituirlo ni duplicarlo. Las dependencias pueden ser aclaraciones del
  propietario o candidatos anteriores; un candidato nunca contesta por sí mismo
  una aclaración del propietario. La profundidad contempla ambas dependencias
  de investigación, además del padre de la evidencia.
- Cada hijo reutiliza el grafo de investigación con un solo encargo y sin
  delegación. Puede proponer seguimientos; la siguiente ronda vuelve al principal.
  Comparte una instantánea de la evidencia ya guardada, no mensajes privados ni
  escrituras concurrentes en el catálogo o la memoria semántica.
- `agent_research_branches` vincula tareas, cuotas, inicio/fin y ejecuciones hijas.
  La importación al padre es transaccional y tiene orden estable. Los checkpoints
  y las claves de petición existentes conservan la idempotencia.
- Una rama fallida deja terminar a sus hermanas y el padre queda recuperable;
  una rama bloqueada o limitada permite entregar resultados parciales. Los errores
  inciertos del proveedor conservan la exigencia de reintento explícito existente.
- La síntesis considera cada candidato una vez: prioridad o exclusión, motivo,
  siguiente comprobación y discrepancias. La cobertura impide publicar como
  respondidas preguntas con discrepancias declaradas no resueltas. El revisor
  comprueba también su significado; la estructura no demuestra verdad semántica.
- El ejecutor permite tres contenedores por base de datos de aplicación. La
  admisión cuenta también ejecuciones abandonadas, que requieren recuperación.
  Se conservan el bloqueo por petición y la exclusión entre ejecución y recuperación.
- `--max-parallel 1` conserva encargos y cuotas y cambia la concurrencia.
  `--no-delegation` conserva el recorrido de un solo analista. Los presupuestos
  por defecto de investigación siguen siendo 32 llamadas, 32 decisiones,
  12 ejecuciones, 6 investigaciones y 900 segundos para programar trabajo.
  Una llamada ya en curso conserva su timeout de transporte; no se promete una
  cancelación instantánea al cumplirse el plazo.
- No hay una reserva monetaria exacta: llamadas y tamaño de respuesta acotan el
  trabajo; uso y reintentos del proveedor quedan registrados para medir coste.
  Los costes de revisión se registran aparte con sus límites anteriores.
- Las gráficas web y HTML siguen al hallazgo al que pertenecen. Los bloques de
  selección de hallazgo y gráfica siguen siendo independientes.


## Estado

**Completado**. Véase la [validación y los límites](../validation/2026-09-27-parallel-analysts.md).
Las cifras de Bruma se contrastaron independientemente y el informe está aprobado.
La evaluación amplia y comparativa continúa en 3.6.
