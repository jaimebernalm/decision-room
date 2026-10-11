# F4: vista y derivados contenidos

Base: `9bd7469` (F0–F3). F4 autorizada; legacy sigue por defecto. Sin llamadas
de API, push ni cambios en master. PDF de HTML queda aplazado; F5 no está autorizado.

## 1. Registro y cola (completado)

Migración 36 aditiva. Recibos originales, identidad de revisión y estado de
verificación siguen inmutables. Las evaluaciones de presentación y los resultados
del renderizador son registros inmutables por negocio, documento, revisión, hash
bruto y versiones de política/renderizador. Las columnas de revisión son una
proyección: el trigger exige el registro de origen correspondiente antes de
permitir cambios. Una nueva política exige una clave nueva, no reescribir resultados.

`decision_room/reports/derivative_store.py` es el único escritor de estas
proyecciones. `set_presentation` guarda una evaluación versionada y rechaza una
decisión distinta bajo la misma identidad. `publish` guarda el resultado terminal,
proyecta la revisión y termina la tarea en una sola transacción, con una guarda del
claim actual. Fallar no publica texto parcial ni cambia la ejecución del motor.

`adopt` encola durablemente las revisiones dentro de su transacción, incluidas
entregas parciales; el registro no las convierte en informe vigente. No arranca
Chrome ni en adopción ni en lectura. La reclamación mantiene un advisory lock de
sesión durante el trabajo; morir libera el lock y permite recuperar la misma
identidad con un nuevo claim. No basta con vencer una lease para duplicar un
worker vivo. El contenedor deberá limpiarse por esa misma identidad al recuperar.

Pruebas PostgreSQL: 13/13 (`test_report_derivatives`, `test_report_registry`,
`test_engine_report_surfaces`). Migración repetida, preservación de bytes/IDs/run,
guarda entre negocios/documentos/revisiones, evaluación idempotente, dos workers,
recuperación y fencing, rollback antes de commit, fallo sin contenido parcial.

## Pasos pendientes

Navegador contenido y capturas estáticas; servicio de derivación y recuperación;
integración con la vista/chat de Claude; suite hostil y regresión completas. Este
documento no declara F4 terminada todavía.
