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

## Guardas y vigencia

El adaptador común conserva el bloqueo padre de legacy y añade resolución exacta
por negocio, documento y revisión. Para HTML, el orden es cabeza de memoria,
documento y filas mutables. El token del motor no es una autoridad de lectura.
Borrar/restaurar cambia la visibilidad de trabajo y documento en una transacción;
restaurar no elimina una retirada previa.

La vigencia compara las dependencias congeladas, los hashes de los archivos y el
estado de los datos. Cambios aplicables de memoria o definiciones, correcciones,
sustituciones y archivos ausentes retiran el informe. Se conservan la instantánea
y el histórico, sin recalcularlo ni modificar runs activos o en espera.

La cabeza sigue el último ordinal recibido de forma durable, incluso si un
archivo recogido al terminar difiere de una entrega MCP previa. El historial
identifica ambas vías y sus hashes; no inferimos la intención temporal del agente.
F5 debe conservar esta diferencia y F2 puede reducirla pidiendo solo el archivo.

F4 necesitará una migración explícita para introducir derivados y estados de
presentación: F1 restringe texto canónico a NULL y versión de derivados a cero.
No hay borrado duro del histórico ni de negocios; las restricciones inmutables
impedirían añadirlo sin una política de conservación propia.

Validación de guardas: 75 pruebas PostgreSQL sin fallos ni omitidos, con modelos
falsos y sandbox local. Incluyen rechazo cruzado entre negocio/documento/revisión,
archivos ausentes y restaurados, retirada de memoria aplicable sin modificar runs
activos, revisión histórica exacta, lectura concurrente con adopción y borrado/
restauración sin recuperar vigencia. También pasan dossier y contexto legacy.
