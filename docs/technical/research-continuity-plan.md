# Fase 2: continuidad de una investigación

Base de comparación: `baa0bbb`. Opción desactivada por defecto. Sin ensayos de
modelo ni reglas de negocio específicas; la medición corresponde al lanzador.

1. Añadir contrato opcional de continuidad: referencias explícitas a ejecución,
   métricas o series; cálculo siguiente y qué decisión puede cambiar. Permitir
   varios cálculos en la misma tarea, sin cierre intermedio ni nueva delegación.
2. Conservar ejecuciones inmutables y su evidencia en contexto, registro de
   candidato, cierre, importación de trabajadores y revisión. Una ejecución
   posterior fallida no elimina evidencia anterior. Mantener cuotas y vigencia.
3. Permitir ampliaciones basadas en series registradas, además de métricas.
   Referencias inexistentes, de otra tarea, omitidas o no registradas se rechazan;
   no reparar silenciosamente una referencia inventada por el planificador.
4. Probar contrato, esquema efectivo, contexto, presupuestos, recuperación y
   recorrido delegado con modelos simulados y datos mínimos genéricos.
5. Documentar activación y límites, revisar cambios y crear commit local.

Quedan fuera: exploración provisional, panorama automático, cambios de rúbrica,
reescritura general de roles, presupuesto ampliado y tratamiento general de errores
repetidos del planificador. El cierre explicita un cálculo pendiente y su efecto
potencial, o explica por qué no queda uno material. Si se agota el presupuesto sin
poder obtener esa nota, el controlador lo marca como cierre incompleto sin inventarla.

Los pasos 1–5 quedan implementados y verificados localmente en un único cambio
experimental. [Registro de activación, pruebas y límites](../validation/2026-10-03-research-continuity.md).
La medición comparativa queda abierta y la opción permanece desactivada por defecto.

6. Corrección del rechazo HTTP 400 detectado en el ensayo: exigir ambas listas de
   `EvidenceRef` en el esquema efectivo y verificar recursivamente las reglas de
   objetos estrictos de todos los productores mediante transporte simulado.
   Completado; resultados y reproducción previa al arreglo en el registro enlazado.

La propuesta de adelantar presentación (P3) se mantiene separada de esta corrección
y de la medición de continuidad; no se implementa ninguna intervención de
presentación en este cambio.
