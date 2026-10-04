# P3b — Evidencia fuera de la lectura del dueño

Base `b91aefb`, rama `codex/feature/report-owner-presentation-v2`.
Misma opción `owner_presentation`, apagada por defecto. Sin llamadas reales al
modelo, sin cambios en investigación, presupuestos, esquemas o aceptación.
Motiva esta corrección la evaluación comunicada en la sección 13 de `703a1ae`:
el detalle plegado también forma parte de la lectura y acumulaba texto técnico.
No se consultan datos, informes ni oráculos de ensayo para construir reglas.

## Comportamiento comprobable sin modelo

- React y HTML exportado dejan de renderizar filas de evidencia, descripciones de
  operaciones y valores originales. Tampoco replican las series de un gráfico en
  tablas plegadas. Las tablas que el agente elige como visualización se mantienen,
  con etiquetas y cifras legibles; los gráficos interactivos conservan sus tooltips.
- Por hallazgo queda una nota breve en castellano con archivos de origen y periodo.
  Se limita su longitud y no incorpora descripciones técnicas de cálculos. No se
  inventa una explicación de negocio a partir de una clave interna.
- El HTML exportado enlaza `internal.html`, que conserva cálculos, código y evidencia.
  `review.json` conserva la auditoría estructurada y el PDF mantiene los valores y
  métodos originales en su anexo. La web mantiene la descarga de ese PDF. La
  proyección estructurada conserva evidencia para esas salidas; no se elimina del
  almacenamiento ni se sustituye en el informe aprobado.
- Las etiquetas generadas como `layer_key:period` usan el nombre revisado de la
  serie y su categoría/periodo, antes de aplicar el catálogo verificado existente.
  No cambian valores, coordenadas, claves de referencia ni identidades de series.
  Los identificadores originales se conservan en auditoría. No se adivinan nombres
  sin catálogo y no se fusionan etiquetas distintas si la sustitución colisiona.
- Se quitan prefijos `Si`/`If` duplicados. Reacciones textualmente equivalentes
  (normalizando espacios, mayúsculas y punto final) se muestran una sola vez con
  sus condiciones. Reacciones distintas se conservan. No se inventan decisiones.
- No aparece el pie «Versión 0» en el HTML P3. Notas independientes reconocibles
  de exportación HTML sin verificar pasan al anexo; no se borran límites sobre
  datos, costes o exportaciones comerciales. El estado original sigue auditable.
- Con P3 apagada se conserva la presentación de control.

## Redacción y revisión que habrá que medir

Prompt registrado `owner-presentation-v2`, para redactor y revisor. Pide lenguaje
llano, nombres de negocio, fuente breve, decisiones diferentes cuando estén
justificadas y cautela causal general una sola vez en límites. Pide preservar las
incertidumbres distintas y condiciones necesarias junto a cada recomendación.

El feedback señala ubicaciones de jerga, identificadores, posibles notas de
software, cautelas causales y reacciones idénticas. Son pistas para revisión,
no hechos ni una barrera nueva de aprobación. No se borran cautelas semánticas
mediante expresiones regulares: una frase específica puede limitar legítimamente
una decisión. La calidad de esa reescritura requiere medición; los tests no prueban
que el modelo vaya a cumplir siempre esas instrucciones.

## Pruebas

- 72 pruebas Python: presentación P3/P3b, valores de evidencia (incluido texto),
  cobertura, leyendas, esquemas estrictos, PDF, edición, informe cliente, contratos
  y capas. Incluyen datos fuente inmutables, control apagado, auditoría conservada,
  ausencia de SQL y volcados en todo el HTML y reacciones con condiciones intactas.
- 33 pruebas de frontend en seis archivos: lectura, calidad, tooltips, descarga,
  edición y recibo de presentación. Comprueban abrir los detalles sin revelar
  volcados, tablas legibles y reacción común mostrada una sola vez.
- Compilación TypeScript y build Vite correctos; permanece el aviso habitual de
  fragmentos mayores de 500 kB. Compilación Python y `git diff --check` correctos.
- Navegador sobre exportación sintética: lectura sin tablas/volcados plegados ni
  `TRY_CAST` en el DOM; enlace «Anexo técnico» abre el archivo separado con evidencia
  y cálculos. No se presenta el fixture como informe real ni evaluación de utilidad.

PostgreSQL, almacenamiento, temporales y VM Docker propios para tests integrados.
Modelos simulados; ninguna llamada real a la API.

## Medición siguiente

Volver a redactar/revisar las mismas investigaciones congeladas con esta revisión,
`owner_presentation=True` y claves de petición nuevas. Mantener iguales datos,
objetivo, modelo, presupuestos y opciones de continuidad/recuperación. Comparar
por parejas con el brazo anterior, puntuando también los fallos y la lectura de
los detalles. Reexportar basta para verificar los cambios deterministas, pero no
para evaluar el nuevo prompt. La aceptación de calidad sigue abierta.
