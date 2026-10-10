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
hashear CSV/Parquet ni persistir retirada bajo un lock compartido. Los eventos
de memoria o definiciones aplicables, correcciones y sustituciones retiran el
informe. La ausencia de archivos impide vigencia al leer; la auditoría explícita
registra su retirada permanente. Se conservan la instantánea
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


## Cierre de F1

La migración 34 completa las claves de procedencia: negocio, análisis, ejecución
y documento deben coincidir en PostgreSQL y en el adaptador. No permite cambiar
el análisis del trabajo ni dejarlo nulo después de enlazar una entrega. Ambas
migraciones son aditivas y se pueden aplicar dos veces sobre datos existentes.

La prueba de actualización desde F0 (`60360df`) conserva los UUID y bytes brutos
de un recibo anterior, incluso con UTF-8 malformado. Después de migrar y adoptar,
el recibo carece de cabeza vigente porque no tenía contexto congelado; no se
reconstruye retrospectivamente. Las fixtures de master/F0 preparan los datos
anteriores con los hooks nuevos de invalidación y captura desactivados solo
durante ese montaje, para reproducir el writer antiguo. La migración y sus
aserciones se ejecutan sin esos parches. Esas pruebas requieren un checkout Git
con los commits de referencia disponibles.

El test concurrente de lectura, borrado y restauración comprueba que la
visibilidad de trabajo y documento coincide bajo las guardas. Las pruebas
legacy de historial, presentaciones, fijados, chat, papelera, edición y PDF
forman parte de la regresión completa; no se reescriben sus IDs ni hashes.
La lectura histórica legacy de la papelera se conserva como antes.

Los detalles de UUID, hash, bytes y vía de entrega quedan plegados en la vista.
La vía se expresa como «archivo final» o «entrega directa». Inicio y el trabajo
explican que el contenido podrá abrirse cuando la vista esté lista.

Commits locales de F1: `a91db52` (registro), `f8ab5b5` (guardas y vigencia),
`ed2d43b` (superficies y corrección de lectura), más el commit de cierre que
contiene esta validación y la integridad adicional. Se conserva `legacy` por
defecto, sin relanzar trabajos ni consumir API. No se ha hecho push.

F2 sigue pendiente para el encargo y panorama, F3 para espera/preguntas y F4
para la vista aislada, derivados y texto canónico. F1 muestra solo metadatos;
no publica ni afirma verificar el HTML. Volver a `legacy` solo cambia trabajos
nuevos y conserva los runs y entregas existentes. No se ha empezado F2–F5.


Validación final: `unittest discover -s tests`, 718 pruebas en 502,336 s,
cero fallos y cero omitidas, con PostgreSQL real, la imagen fijada del motor y
el sandbox local construido. Incluye los seis smokes nativos de F0 y el conjunto
legacy de master. `OPENAI_API_KEY` vacío; no hay gasto de API. Los mensajes de
error de las fixtures de interrupción/validación son deliberados y la suite
termina en `OK`. La prueba de un millón de filas también pasa.

Frontend: 40 archivos y 305 pruebas Vitest, todas en verde tras los ajustes de
UX; `tsc -b`, Vite y oxlint pasan. Persisten solo los avisos previos de Fast
Refresh y tamaño del bundle. Se revisó el diff y los archivos preparados antes
del commit: sin credenciales, rutas personales, datos privados ni archivos
generados grandes.
