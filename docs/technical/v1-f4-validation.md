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

## Pasos pendientes

integración con la vista/chat de Claude; suite hostil y regresión completas. Este
documento no declara F4 terminada todavía.

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

Las dos pruebas de `test_report_frame_native` pasan contra la política del commit
de vista `a4c7e09`, cargada en el runner hasta integrar las ramas. Reproducen el
fallo del candidato y prueban que instantánea/recepción dejan el padre intacto y
no generan peticiones al sumidero para SMIL y diez fixtures de scripts, fetch,
URL construida, base, refresh, JavaScript URL, URL relativa, formulario y tamaño.
La misma suite se repetirá sobre la rama integrada.

Ocho pruebas adicionales de servicio y recuperación pasan: recuperación del
contenedor huérfano por ID exacto y rechazo del contenedor con otra etiqueta,
además del servicio. Sin imagen configurada, la lectura distingue `unavailable`
de `pending`, respeta negocio/documento/revisión y conserva la cola; no inspecciona
el bruto ni intenta Chrome. El borrador del test de etiqueta tenía un índice de
argumento erróneo; se corrigió antes de comprobarlo y guardar este commit.
