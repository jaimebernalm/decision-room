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

La vigencia compara las dependencias congeladas y el estado de los datos.
Al adoptar una revisión nueva y en `audit()` se comprueban también los hashes de
los archivos. Las lecturas de metadatos solo consultan versiones y presencia, sin
hashear CSV/Parquet ni persistir retirada bajo un lock compartido. Cambios aplicables de memoria o definiciones, correcciones,
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


## Superficies de metadatos

Listado, búsqueda por metadatos del dueño, detalle, fuentes e Inicio resuelven el
registro HTML sin usar IDs del revisor legacy. Inicio ofrece solo enlace y estado;
sus candidatos y fijados legacy permanecen separados. Las revisiones históricas
se resuelven por UUID exacto y el detalle conserva hashes y vías de entrega.
El chat registra una respuesta de estado con el documento y revisión, sin claims,
evidencia ni contenido canónico del agente; las referencias legacy conservan sus
IDs y hashes. Una respuesta de estado se retira cuando el documento deja de ser
actual.

La UI muestra entrega guardada, incompleta o retirada, sin «Revisado». El HTML
bruto y PDF están bloqueados por la misma guarda; la vista solo recibe metadatos.
El texto del dueño se escapa por React y no hay iframe ni montaje del HTML. La
edición de presentaciones HTML espera F4 y los PDF v1 la fase posterior acordada.
Una ausencia de archivos detectada en una lectura impide vigencia sin escribir;
solo un evento del producto o la auditoría explícita registra una retirada
permanente. F4 deberá hacer la comprobación profunda antes del uso de contenido.
El writer de definiciones ya invoca `context.invalidate` desde `persist`; ese
hook incluye ahora la retirada de los informes HTML en la misma transacción.

Validación de superficies: 22 pruebas de metadatos/Inicio/motor sin fallos; tras
ampliar a 130 pruebas de chat y web se detectó un cambio no deseado en la lectura
legacy de la papelera. Se restauró ese comportamiento y pasan las 17 pruebas de
motor/guardas/superficies más el caso de papelera. Se comprobaron también las
rutas HTML/PDF bloqueadas, UUID de revisión exacto, fuentes, búsqueda, negocio
ajeno, chat de estado y retirada por definición escrita. La regresión completa
se ejecuta en el cierre. UI: 305 pruebas sin fallos; TypeScript, Vite y oxlint
pasan (avisos preexistentes de Fast Refresh y tamaño de bundle).
