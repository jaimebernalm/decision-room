# F1: registro y lectura de informes HTML

F1 incorpora metadatos y acceso por negocio, documento y revisión. No autoriza
servir HTML del agente, texto canónico, citas o PDF; esas superficies esperan F4.
Legacy conserva sus tablas, identificadores, historial y permisos.

## Registro aditivo

La migración 33 registra solo `engine_html`, adopta los UUID de los recibos del
motor y conserva todas sus revisiones sin interpretar los bytes. Los runs nuevos
congelan sus dependencias al crearse. Los anteriores sin ese registro conservan
sus recibos pero no se consideran vigentes. La adopción es idempotente y enlaza
`web_jobs.report_document_id` sin inventar una revisión legacy.

Las revisiones y dependencias son inmutables en PostgreSQL. Solo una ejecución
`delivered` con recibo no vacío puede tener cabeza actual; una entrega parcial,
fallida o abortada sigue siendo histórica e incompleta. Esta integridad no afirma
que el HTML sea seguro ni que sus cifras estén verificadas.

Validación inicial: 62 pruebas PostgreSQL de registro, motor, control, migración
y actividad: sin fallos; una prueba Docker omitida con la imagen desactivada.
Incluye adopciones concurrentes, bytes malformados, hashes e identidad exactos,
rechazo de mutaciones y migración sobre master aplicada dos veces.
La vigencia y las superficies se completan en los commits siguientes.
