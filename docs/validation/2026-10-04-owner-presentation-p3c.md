# P3c — Limpieza de la lectura del dueño

Base `f740c0b` (corrección del bucle de cobertura sobre `5d0aae0`). Cambio separado,
con la misma opción `owner_presentation`, apagada por defecto. No cambia P1a,
la investigación ni los criterios de exactitud. Sin llamadas reales al modelo.

## Comportamiento

- El controlador deja de reinsertar los contadores «Selección entregada…» en los
  límites de P3. Conserva las selecciones estructuradas, su validación, manifiesto
  y notas en `controller_annotations`. Los borradores anteriores se limpian por
  coincidencia exacta con la nota calculada, sin borrar advertencias por prefijo.
- La proyección de lectura retira frases independientes reconocibles sobre abrir
  o verificar el informe en navegador. Conserva las frases contiguas de negocio y
  guarda las notas de software en la información técnica. No modifica el informe
  aprobado, sus referencias, cifras ni evidencia.
- Retira el enlace y rótulo «Anexo técnico» del HTML del dueño. Siguen exportándose
  `internal.html` y `review.json`; el PDF mantiene su apéndice técnico separado.
- Las cautelas generales reconocibles de causalidad y datos sintéticos se reúnen
  una vez en límites. Las condiciones específicas de una decisión se conservan.
  La proyección es idempotente y se aplica una sola vez al ensamblar la lectura.
- El prompt y feedback `owner-presentation-v3` piden reformular la jerga indicada,
  explicar con una frase la elección de ventanas no evidentes, y retirar repeticiones
  semánticas. Distinguen días con registros de días naturales, falta de filas de
  ventas cero, y prohíben inventar razones estacionales o procedencia sintética.
- HTML y PDF no muestran un bloque de alcance vacío si solo contenía una nota de
  software. Con la opción apagada se conserva la lectura anterior.

## Validación

51 pruebas pasan con PostgreSQL y Docker propios y modelos simulados:

```sh
PYTHONPATH=tests .venv/bin/python -m unittest \
  test_owner_presentation_p3c test_presentation_controller_ownership \
  test_owner_presentation test_owner_presentation_p3b \
  test_owner_presentation_values test_owner_coverage_reading \
  test_client_report test_report_pdf test_delivery_scope \
  test_model_strict_schemas \
  test_sales_panorama_integration.PanoramaPersistenceTests -q
```

Incluyen el bucle controlador/revisor, preservación de advertencias concretas,
auditoría y cifras originales, HTML/PDF, opción apagada, repetición de cautelas,
exportación con evidencia textual, contratos de selección, esquemas estrictos y
persistencia del panorama. Compilación Python y `git diff --check` correctos.

## Límite de esta entrega

La limpieza determinista reconoce frases acotadas; no pretende interpretar toda
paráfrasis ni sustituir palabras técnicas a ciegas. La reformulación semántica y la
justificación de ventanas se exigen al redactor y al revisor, sin un rechazo
mecánico basado en palabras. Queda pendiente volver a redactar y evaluar por
parejas sobre investigaciones congeladas: estas pruebas no demuestran que mejore
la comprensión real. P2 no se implementa aquí.
