# P1a — Panorama determinista para redacción

Base `929d142`. Opción propia, apagada por defecto; no modifica planificación ni
investigación. Sin llamadas reales al modelo y sin reglas por negocio.

1. Calcular al importar una vista determinista por tabla de fecha × producto ×
   canal. Usar cantidades reconocibles, nunca asumir que un importe es total de
   fila. Permitir un mapeo explícito para encabezados distintos. No unir archivos
   sin contrato de unión ni confundir filas con tickets.
2. Guardar totales, comparación de periodos explicada, cambios principales y
   huecos de registros con fórmula, filtros y huella de entrada. Mantener una
   caché separada del contexto de investigación; preparar importaciones antiguas
   con el mismo cálculo para los ensayos por parejas.
3. Entregar el panorama y referencias de evidencia solo a redactor/revisor cuando
   la opción esté activa. Congelar opción y evidencia en la revisión, con auditoría
   de prompt y reanudación; comenzar por el panorama y justificar prioridades,
   sin imponer un orden por magnitud ni un nuevo bucle de aprobación.
4. Verificar con datos sintéticos cifras, huecos, periodos, orden de filas,
   ambigüedades, aislamiento por negocio, control apagado y exportaciones. Commit
   local; utilidad pendiente de las nueve comparaciones por parejas.

Pasos 1–4 implementados y comprobados.
[Activación, evidencia, pruebas y límites](../validation/2026-10-04-sales-panorama-p1a.md).
La medición de utilidad queda pendiente; P1b y P2 no se implementan en este cambio.
