# 3.9.10.1 — Reparación de contratos antes de los ensayos

Base congelada: `4815b68`. Rama: `codex/fix/report-quality-contracts`.
Acuerdo de ensayos de Opus: `42a1bdd`, en `claude/report-quality-trials`.

Esta fase precede a continuidad, exploración provisional, revisión, panorama y
presentación. No cambia la política de profundidad, el orden de prioridades ni
la rúbrica. No consulta Albor ni diseña todavía el negocio reservado.

## Pasos de implementación

1. **Capas accesibles desde el productor.** Añadir a ambos esquemas efectivos
   una alternativa de gráfico con `layers`, sin puntos escalares ni `series`
   principal. Agrupar referencias vigentes por unidad y grano temporal; conservar
   la validación de derivaciones, nombres únicos y máximos combinados. Comprobar
   el esquema real con un validador JSON Schema independiente, y después la misma
   evidencia en validación, web, HTML y PDF.
2. **Entrega y errores explícitos.** Comunicar que el controlador exporta HTML y
   PDF después de una aprobación vigente. Separarlo de artefactos de ejecución,
   adjuntos y comprobación visual. Distinguir nombre inválido, tipo no admitido y
   nombre duplicado; identificar el ámbito de los límites. Mantener los límites.
3. **Identidad visible.** Mostrar el nombre completo de las categorías en barras
   simples y agrupadas, ajustar su altura y conservar sufijos diferenciadores.
   Evitar también recortes y solapamientos de etiquetas en las exportaciones.
4. **Peticiones auditables.** Persistir el cuerpo efectivo después de añadir
   instrucciones de memoria, idioma, esquema del proveedor y correcciones, antes
   del transporte. Conservarlo en éxito, error y recuperación. No reconstruir
   retrospectivamente peticiones que no se guardaron.
5. **Estabilidad frente al orden físico.** Comprobar cada cálculo completado con
   los mismos datos en orden físico inverso, dentro de otro contenedor aislado.
   Comparar métricas y series sin depender de su enumeración. Rechazar resultados
   que cambien o cuya segunda ejecución no pueda verificarse; conservar originales
   y trazas. Aplicar a cualquier negocio, nombre de columna o fórmula.
6. **Validar y congelar.** PostgreSQL, almacenamiento, worktree y Docker propios;
   transporte del modelo simulado y llamadas reales prohibidas. Pruebas de
   contratos, persistencia, migración, aislamiento, regresión y presentación.
   Commit local para que Opus ejecute Bruma 3 + Albor 3 y los controles.

La estabilidad se comprueba con **una permutación**, no con todas las posibles:
se buscan contraejemplos de dependencia del orden; no se demuestra la corrección
matemática de cualquier programa. Un programa que depende de una fila intermedia
podría superar esta prueba. La revisión de fórmulas continúa siendo necesaria.

Estado: los seis pasos están implementados y validados localmente; la ejecución
comparativa real corresponde a Opus.

Los pasos de esta fase se validan juntos porque el esquema, la ejecución y la
representación forman un contrato. No se declara cerrada la aceptación analítica
3.9.7. Véase la [validación y entrega](../validation/2026-10-03-report-quality-contracts.md).
