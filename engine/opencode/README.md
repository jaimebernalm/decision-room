# OpenCode fijado para el motor

Imagen Linux ARM64 con OpenCode 1.18.34 y ripgrep 15.1.0. El producto suministra
una imagen base de su sandbox mediante un ID inmutable; no se descarga una base
nueva durante este build. La primera versión de esta imagen no cubre AMD64.

1. Ejecutar `python engine/opencode/vendor.py fetch`: descarga de npm/GitHub y
   verifica SHA-512/SHA-256 fijados en el script. `verify` vuelve a comprobar los
   archivos; `vendor/` está excluido de Git.
2. Construir con Docker, `--network=none`, `--build-arg BASE_IMAGE=sha256:…`,
   `-f engine/opencode/Dockerfile engine/opencode`, y guardar el ID de la imagen.
   El Dockerfile vuelve a verificar los archivos antes de instalar los dos
   miembros regulares seleccionados de los tarballs.
3. Pasar ese ID como `DECISION_ROOM_ENGINE_IMAGE_ID` a
   `python -m unittest tests.test_engine_image` desde el entorno de pruebas del
   repositorio. No se envía ningún prompt ni se necesita clave de proveedor.

El smoke arranca `serve` con contraseña aleatoria, usuario 10001, raíz de solo
lectura, capacidades eliminadas, recursos acotados, tmpfs privados y una red
interna con DNS externo deshabilitado. Comprueba rechazo sin contraseña, versión,
creación de sesión con título explícito, lectura de mensajes/hijos y aborto,
además de ausencia de clave de proveedor, rutas del host y resolución DNS externa.
No pretende probar todavía toda la red de producto, proxy y pasarela. El cliente
Python usa HTTP local dentro del contenedor mediante `DockerHTTPTransport`: Docker
no publica su puerto en esta red interna. El transporte emplea el ID inmutable,
`docker exec` sin shell y Python aislado; no monta el socket Docker en el agente.
Solo admite HTTP finito a loopback. Este controlador local reconcilia mensajes
por polling; SSE queda disponible en el cliente HTTP ordinario.

El cliente `decision_room.engine.client` corresponde al OpenAPI de la etiqueta
1.18.34: crea sesiones con título, envía `prompt_async` con messageID persistido
en el outbox duradero, consulta mensajes/hijos/estado y aborta. No reintenta
mutaciones y trata un timeout de envío como recepción incierta. SSE terminado
obliga a reconciliar la sesión. Sus pruebas de transporte usan también un servidor
simulado; el smoke ejercita el mismo cliente contra los endpoints reales.

La comprobación de título en `session/prompt.ts:193–200` de OpenCode omite la
llamada de título si la sesión ya tiene uno explícito. Esto es evidencia de código;
el presupuesto de llamadas ocultas aún debe verificarse con un turno real.
Fuente: [OpenCode 1.18.34](https://github.com/anomalyco/opencode/tree/v1.18.34).

`decision_room.engine.checkpoint` usa la API backup de SQLite, que incorpora WAL
confirmado sin copiar una base a medio escribir. Comprueba integridad, hash y
publicación exclusiva. La restauración exige un destino nuevo y un servidor
parado. Las pruebas cubren WAL, transacciones no confirmadas, revisiones de copia,
corruptelas y enlaces simbólicos. `engine.container` incorpora además los archivos
de trabajo, entradas y estado; el controlador registra la copia y restaura la
sesión con sus hijos en otro contenedor. La pregunta en PostgreSQL referencia el
checkpoint confirmado antes de activar una respuesta.

La configuración por trabajo, el supervisor y la API de ejecución/espera/reanudación
están disponibles en `engine.container` y `engine.api`, junto con el outbox de
`engine.control`. Estos componentes no habilitan el motor en la interfaz. La
[matriz de P2](../../docs/technical/engine-p2-recovery.md) relaciona aislamiento,
recuperación abrupta, cuotas y el lote real con sus pruebas y límites.

Para el sentido agente → servicio, `decision_room.engine.tunnel.JobTunnel` lanza
`relay.py` con Python aislado mediante Docker exec. El script se lee del árbol de
fuentes del producto, no del directorio escribible del agente. Expone únicamente
las rutas HTTP de ese trabajo en `127.0.0.1:8080` del contenedor y transporta JSON y
SSE por pipes hacia el servicio loopback del host. El host valida los frames otra
vez; el socket Docker y la clave del proveedor nunca cruzan el pipe. La prueba
`tests.test_engine_tunnel` usa un servicio simulado sin modelo. El controlador gestiona arranque, corte y recuperación de este recorrido.

## Runtime de trabajo

`engine.container.Runtime` crea una generación identificada por UUID, con tres
volúmenes exclusivos (`state`, `work` e `inputs`) y red `none`. `inputs` está
montado en solo lectura para el agente; un cargador sin red lo prepara antes del
primer arranque. El controlador debe guardar
esa identidad antes de crearla. Reconcilia un contenedor existente por nombre,
labels e imagen inmutable; no adopta recursos ajenos. La configuración MCP y
Responses apunta al relay loopback del trabajo y solo contiene su credencial,
nunca la del proveedor.

El checkpoint detiene todo el contenedor, copia los tres volúmenes mediante tar
acotado, rechaza enlaces/dispositivos/traversal y hace backup SQLite desde la copia
con WAL. Publica hashes de cada archivo, del modelo de imagen y del trabajo. La
restauración valida todo antes de crear una generación y volúmenes nuevos. No
sobrescribe un servidor activo ni una restauración parcial. Conserva el SQLite
completo (incluidas las sesiones hijas que existan) y los archivos de trabajo;
la exportación legible de esas sesiones corresponde al supervisor.

Prueba real sin modelo: sesión y sesión hija creadas con título explícito y archivos CSV/texto,
parada, checkpoint, restauración en otro contenedor, lectura de la misma sesión
y archivos; rechaza corrupción y restauración sobre una instancia existente.
Las pruebas de archivo rechazan enlaces simbólicos/duros, dispositivos, duplicados
y rutas externas. No son todavía el recorrido integrado de `run_report` ni la
prueba de todas las ventanas de caída del supervisor. Un checkpoint que falla
conserva los volúmenes originales; su retirada es una operación separada.


La API requiere `DECISION_ROOM_ENGINE_IMAGE_ID` con el ID SHA-256 de la imagen
local fijada; usa el backend Docker configurado por el producto. El servicio de
pasarela es compartido por configuración dentro de cada proceso del host. El
modelo se fija desde configuración confiable (`DECISION_ROOM_ENGINE_MODEL`, por
defecto `gpt-6-luna`). Solo el servicio del host recibe `OPENAI_API_KEY`.

El runtime inicial entrega los CSV originales en `/inputs`, tras comprobar sus
hashes, junto con un manifiesto de tablas. Esta primera API no acepta aún fuentes
Excel. La pausa detiene todo el contenedor y captura estado/work/inputs; la respuesta
restaura en otra generación, conserva la sesión y encola un único mensaje con
credencial rotada. Una caída con petición al proveedor pendiente aborta conservando
la reserva, sin reenvío. Una restauración incompleta conserva sus archivos y exige
recuperación; no se sobreescribe. Los volúmenes detenidos se conservan para diagnóstico;
no hay todavía política automática de caducidad ni cuota de disco por volumen.

El controlador observa hasta 64 sesiones y 64 páginas por sesión. Sobrepasar esos
límites no afirma una exportación completa; registra un fallo y conserva los datos
ya persistidos. Los límites de checkpoint son independientes de los del modelo.


La prueba integrada `tests.test_engine_api.RealApiTests` usa OpenCode, MCP,
PostgreSQL y Docker reales con un transporte Responses simulado sin red externa.
Cubre entrega, pregunta, parada/restauración en la misma sesión y entrega posterior,
así como proveedor deshabilitado. El controlador confirma MCP antes del prompt y
no interpreta un paso `tool-calls`/`unknown` como fin del turno. Otras pruebas cubren
reservas inciertas tras caída, idempotencia de respuesta, aislamiento por negocio y
fallo del render con raw recuperable. Esto no sustituye los ensayos con modelo de P2
ni certifica calidad analítica de P3.


El acceso de OpenCode a directorios externos permanece denegado salvo `/inputs/*`,
para que sus herramientas nativas puedan descubrir el manifiesto y leer los CSV.
Docker monta ese volumen en solo lectura. La prueba real de descubrimiento lee
manifiesto y CSV, extrae un UUID de tabla, lo usa en MCP y comprueba que
`/etc/hostname` siga denegado; el test de restauración comprueba además que escribir
en inputs falla. Esta excepción corrige el primer canario real, que conservó su
salida parcial pero no pudo descubrir tablas por la denegación global anterior.


`consulta` describe su API Python completa en el propio catálogo MCP: el argumento
`tables` solo asigna alias a UUID; no existe una variable Python implícita con ese
nombre. `dr_runtime.connect()` crea vistas DuckDB por alias, `table_path(alias)`
da el Parquet, y `write_result(metrics, evidence=...)` persiste el resultado.
La prueba integrada ejecuta literalmente el ejemplo publicado por la herramienta
sobre una tabla descubierta en el manifiesto y exige estado `completed`. Esto
corrige los errores `NameError` observados en el segundo canario, sin cambiar el
contrato ni el aislamiento del sandbox de cálculo.

La descripción detalla también métricas escalares, límites de texto y series para
resultados por grupos. `consulta` y `resultado` devuelven `diagnostic` en ejecuciones
fallidas o con salida inválida: código estable, explicación y regla de reintento.
Los errores conocidos del contrato y clases admitidas de excepción Python reciben
orientación concreta; no se devuelven excepciones, rutas ni logs crudos. Repetir
una clave recupera el mismo fallo; corregir el programa exige una clave nueva.
Una prueba Docker real provoca falta de result.json, métricas anidadas y texto
excesivo, recupera el diagnóstico y termina con una consulta corregida. Las
columnas CSV pueden ser texto: hay que validar y convertir antes de sumar.
