# 3.4.1 — Conocimiento de datos y utilidad del primer informe

## Plan acordado

1. Sustituir la propuesta automática por nombres por descubrimiento del agente sobre catálogo, perfiles y muestras acotadas. Guardar propuestas, modelo, consumo y comprobaciones completas en revisiones del catálogo antes de capturar el contexto de chat/planificación.
2. Comprobar claves simples/compuestas, nulos, duplicados, cobertura y multiplicación mediante código determinista. Las propuestas nunca confirman significado; conservar correcciones del propietario. No ejecutar SQL generado para construir el catálogo.
3. Reconocer fechas ISO con hora. Mantener las revisiones antiguas y refrescar perfiles sin borrar definiciones en la misma versión de archivos.
4. Orientar planificación e investigación a contrastes, segmentos y contribuciones. Revisión explícita de utilidad por pregunta, con bloqueo de entregas que solo describen gráficos cuando el objetivo exige conclusiones. Gráficos comparables y límites de incertidumbre concisos.
5. Probar aislamiento, claves compuestas, uniones inseguras, recuperación y rechazo de falsa cobertura. Repetir Bruma Café con el modelo real y verificar cifras independientemente. No prescribir al agente los hallazgos esperados.

## Criterios de aceptación

- Bruma: relaciones ventas-productos, ventas-canales y marketing-canales persistidas con evidencia, sin confirmación semántica inventada.
- Fechas con hora interpretables; ningún gasto mensual multiplicado por filas de venta.
- Informe con diferencias cuantificadas y segmentos que ayuden a priorizar; excluye margen por definición desconocida. Cobertura honesta y representación comparativa.
- Mantener presupuestos y trazabilidad; no introducir analistas paralelos del 3.5 en este cambio.

## Cierre

Implementado. Véase la [validación y sus límites](../validation/2026-09-27-agent-data-and-insights.md). Se añadieron citas verificables a puntos de series porque la prueba real mostró que la restricción a métricas escalares provocaba pérdida de hallazgos o cálculos repetidos.
