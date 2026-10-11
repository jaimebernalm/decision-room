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

## 2. Navegador contenido (completado)

`engine/report_browser/` contiene solamente fuentes del Dockerfile y del worker.
`scripts/dev/report_browser.py --context CONTEXTO` construye un contexto temporal
con esas fuentes y `decision_room/reports/inventory.py`; guarda un manifiesto
local ignorado. El controlador exige imagen por SHA y los hashes exactos de las
fuentes. La identidad del renderizador incluye el SHA de la imagen: otra imagen
requiere otro derivado y reiniciar el worker. Una instalación sin imagen conserva
la cola pendiente; nunca usa Chrome del host. La base Python está fijada; Chromium
y fuentes se resuelven al construir y quedan congelados por el SHA de la imagen.

Límites del contenedor: usuario 10001, raíz read-only, red `none`, capacidades
retiradas, no-new-privileges, cero montajes del negocio/host, 1 CPU, 1 GiB de RAM y
swap total, 256 PID, tmpfs de 512 MiB. CLI con configuración privada vacía, sin
variables de credenciales de proveedor/BD. El sandbox interno de Chromium se
desactiva por compatibilidad con el contenedor sin capacidades; la frontera es
el contenedor, no se presenta como aislamiento por el sandbox de Chrome.

El HTML llega por stdin, máximo 256 KiB, y solo se ejecuta dentro del contenedor.
CDP inspecciona en un mundo aislado para que redefinir prototipos del documento
no sustituya el inspector. URLs bloqueadas y red offline también dentro de
Chrome. Texto estable durante un segundo, límite de diez segundos para esa
estabilidad, 100.000 nodos y un millón de caracteres. Ningún texto visible o un
DOM inestable falla. El controlador limita toda la ejecución a 45 segundos y la
salida a 36 MiB; limpia por ID exacto incluso al fallar o recuperar un huérfano.

La instantánea contiene únicamente HTML fijo propio y PNG data:, sin markup,
CSS ni URLs del agente. Tras estabilizar, se desactiva JS/animaciones de la página;
se comprueban dos capturas iguales y el mismo inventario antes/después. Imágenes
de 1280 px en tiles de hasta 2000 px; máximo 24.000 px de alto y 20 MiB de HTML.
Un ancho excesivo, overflow o captura incompleta falla en lugar de recortar.
Se pierde la interacción y selección dentro de las imágenes; la vista ofrece
el texto canónico por separado. No se declara veracidad numérica ni se reparan
gráficos equivocados del agente.

Pruebas: 38/38 (`test_report_browser`, `test_report_derivatives`, `test_engine_html`,
`test_activity`, `test_business_migration`), incluidas seis pruebas nativas de
Chrome dentro de Docker. JS con SVG y negativo, texto Unicode, prototipos
redefinidos, fetch externo/file, informe largo sin recorte, navegación, UTF-8,
DOM inestable, script infinito con límites inspeccionados y contenedor retirado.
Se actualizan a 36 las cuatro aserciones de versión de esquema; no cambia el
criterio de preservación de datos. Dos fallos del borrador se corrigieron:
imports bajo Python `-I` y pausar tiempo virtual impedía la segunda captura de
una página larga; se detienen scripts/animaciones sin pausar el compositor.

## 3. Servicio y recuperación (completado)

`decision_room/reports/derive.py` expone las firmas acordadas `derive` y `derived`.
`derived` solo hace un SELECT por negocio/documento/revisión/política/imagen y
devuelve los hashes exactos; nunca hashea CSV ni arranca un navegador. El worker
se ejecuta en un hilo independiente del motor/modelo. Un único slot PostgreSQL
global limita a un navegador, además del claim por tarea. No mantiene los locks
de memoria/documento ni una transacción durante Chrome.

Antes de renderizar registra la decisión de recepción con el módulo puro de
presentación y hace la inspección profunda de dependencias como evento de
contenido; una retirada no cambia el run ni lo vuelve a ejecutar. Un HTML bloqueado
con UTF-8 válido puede generar texto canónico dentro del contenedor: permanece
bloqueado en la vista. UTF-8 inválido y vacío fallan antes de Chrome. La publicación
vuelve a verificar identidad y borrado bajo memoria → documento, y descarta un
resultado si se borró mientras se calculaba. No concede vigencia ni verificación.

Si cambia la imagen/política, `refresh` encola la nueva clave en el worker, nunca
al leer; los derivados anteriores se conservan. La proyección se vuelve pending
para la nueva clave y solo cambia al publicarla. Resultados terminales de una
clave no se recalculan al leer ni se reintentan automáticamente.

Pruebas PostgreSQL: 16/16 (`test_report_derive`, `test_report_derivatives`,
`test_report_registry`), sin omitidas. Idempotencia de servicio, lectura sin Chrome, hashes exactos,
fallo privado sin texto parcial, bloqueado con texto, UTF-8 sin llamada al render,
nueva imagen y política, borrado concurrente y ausencia de locks durante render.
SIGKILL real del controlador después de entrar al render: se liberan slot/claim,
se recupera el mismo job con un nuevo claim y se publica una vez. Los tests de
registro también cubren muerte lógica antes del commit y fencing de un worker
anterior. Prueba nativa del servicio verifica texto, píxeles y proyección juntos.

## 4. Puerta del marco y recuperación adicional

El candidato que servía el bruto en un `iframe sandbox=""` se descarta. En Chrome
real, con HTML sintético y la CSP del producto, un enlace SVG con animación SMIL
cambia su destino a una ruta del mismo origen. Al pulsarlo se registra la petición
en el sumidero; el padre conserva su título. Desactivar scripts no impide esa
navegación. La comprobación de meta refresh no produjo navegación.

La política acordada es `v1-snapshot-only-1`: solo HTML propio con PNG del navegador
aislado, acompañado de texto canónico. Nunca se introduce marcado del agente en
el marco. `tests/synthetic_browser.py` es exclusivamente un arnés de prueba del
origen con fixtures escritos a mano; no carga archivos ni informes, y no es una
dependencia del producto. Toda ejecución de HTML del agente sigue dentro de Docker.

Las dos pruebas de `test_report_frame_native` pasaron primero contra la política
de vista `a4c7e09` y después contra la rama integrada. Reproducen el
fallo del candidato y prueban que instantánea/recepción dejan el padre intacto y
no generan peticiones al sumidero para SMIL y diez fixtures de scripts, fetch,
URL construida, base, refresh, JavaScript URL, URL relativa, formulario y tamaño.
El marco del producto nunca recibe el HTML sintético del candidato rechazado.

Ocho pruebas adicionales de servicio y recuperación pasan: recuperación del
contenedor huérfano por ID exacto y rechazo del contenedor con otra etiqueta,
además del servicio. Sin imagen configurada, la lectura distingue `unavailable`
de `pending`, respeta negocio/documento/revisión y conserva la cola; no inspecciona
el bruto ni intenta Chrome. El borrador del test de etiqueta tenía un índice de
argumento erróneo; se corrigió antes de comprobarlo y guardar este commit.

## 5. Integración de vista y chat

Fusión local autorizada de `claude/v1-view` (`ac7e870`) en
`codex/v1-engine-path`: commit `1f96719`. No se modifica master. Las versiones
de política tienen una sola constante, en `decision_room/reports/presentation.py`.
La vista no tiene fallback a marcado bruto. Raw es un adjunto octet-stream con
Content-Disposition y CSP sandbox; PDF responde 409. La vista no concede una
aprobación ni muestra «Revisado» para informes v1.

El chat solo descubre documentos vigentes con texto canónico listo. Cada lectura
toma memoria → documento compartido; su dependencia contiene ID de revisión,
hash bruto, hash canónico, política y renderizador. La búsqueda revalida tras el
ranking; una retirada o cambio de derivado invalida los resultados usados al
reanudar o reutilizar una conversación. No inventa evidence_ids ni claims y no
adjunta evidencia revisada a los textos v1. El texto está limitado a 40.000
caracteres con indicador de recorte. Corpus mayor de 1.000 se rechaza explícitamente.

Una búsqueda mixta respeta un límite total. Sin consulta ordena legacy y v1 por
fecha de aprobación/entrega; con consulta reserva los huecos restantes tras los
resultados legacy para v1, que se ordena por separado. Ese orden está declarado
en la respuesta (`engine_order=ranked_separately_after_reviewed`); no representa
un ranking semántico global de ambas fuentes. Un fixture mixto comprueba los
límites 1 y 2 y las dependencias correspondientes.

Sobre la rama integrada: 27/27 focalizadas de chat, vista, servicio y marco nativo.
Un smoke nativo adicional une render real en Docker → publicación en PostgreSQL
→ lectura del chat y vista, sin doble de derived: texto, revisión y hashes iguales,
rechazo del negocio ajeno, y solo instantánea en el marco. UI 313/313, TypeScript,
Vite y oxlint pasan. Se mantienen advertencias existentes de Fast Refresh y bundle.

La primera regresión completa preintegración terminó con 779 pruebas y un fallo:
se cambió la política durante la pasada, de modo que el proceso hijo del test
SIGKILL cargó otra política y encoló un ID diferente del esperado por el padre.
No se acredita esa pasada; la limpieza del test recoge también el proceso si falla.
La pasada integrada de `1f96719` terminó con 801 pruebas y un error en el fixture
antiguo de `test_report_metadata`: el doble de BD no devolvía una lista vacía de
documentos del motor. Se corrige el fixture manteniendo el criterio de fechas y
la prueba mixta con documento real.

La revisión cruzada encontró un fallo del turno completo del chat: tras recuperar
un informe v1, `conversations.run` intentaba decorarlo con la presentación legacy,
que exige un informe revisado. El commit `37a6fb4` excluye `engine_html` de esa
decoración. Una prueba de búsqueda → apertura → respuesta con modelos falsos
reproduce el fallo antes del arreglo y pasa después: usa el texto canónico, no
adjunta `evidence` ni `report_id` y etiqueta la fuente como «Informe», sin «revisado».

Ese commit fija también la versión del renderizador en los tests offline,
incluido el proceso hijo del SIGKILL; el smoke nativo conserva la configuración
real. Las 27 focalizadas pasan con imagen configurada. Desde una exportación
limpia de Git, sin manifiesto local ni imagen configurada, pasan 26 y se omite
solo el smoke nativo. Claude reproduce esos resultados en su checkout limpio.

Commits enfocados de F4:

- `df9602f`: migración 36, registro inmutable y cola en adopción.
- `2c22747`: navegador contenido, inventario y captura PNG.
- `d2260ab`: servicio de derivados, worker independiente y recuperación.
- `2d1c910`: cierre del bruto en el marco, unavailable y prueba de navegación SMIL.
- `78d792d`, `a4c7e09`, `8b3fc4b`, `ac7e870` (Claude): recepción, vista,
  instantánea obligatoria y chat con referencias por revisión.
- `1f96719`: integración local, límite mixto de búsqueda y smoke conjunto.
- `37a6fb4`: turno completo del chat y pruebas independientes de la imagen local.

## Validación final y alcance

Regresión completa congelada de `37a6fb4`: **802/802 Python**, cero fallos,
errores u omitidas, 591,539 segundos. PostgreSQL y almacenamiento desechables,
modelos falsos y clave de proveedor vacía; imágenes nativas fijadas del motor,
sandbox y renderizador. Incluye la migración repetida y preservación legacy,
recuperación/locks, navegador real contenido y suite sintética del marco.
UI **313/313**; TypeScript, Vite y oxlint pasan. Las correcciones posteriores a
esa pasada de UI afectan únicamente a Python y sus pruebas.

Claude revisó los commits de núcleo y vista, y comprobó `37a6fb4` en un checkout
limpio sin configuración de imagen. El resultado integrado se registra en el
Bridge para la revisión de su versión exacta. Las dos pasadas completas anteriores
con fallo están declaradas arriba; solo la pasada congelada final se acredita.

F5 requiere su propio preregistro y autorización de gasto; legacy sigue por
defecto. PDF permanece aplazado. F4 no certifica la exactitud de los informes,
no modifica los datos/encargos del run ni vuelve a ejecutarlo. No se gastó API,
no se enviaron cambios a GitHub y no se modificó master.
