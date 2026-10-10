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

## Perfil html-v1 (F0)

El perfil registra modelo `openai/gpt-6-luna`, razonamiento `low`, versión
1.18.34 e ID inmutable de la imagen. Autoupdate, share y snapshot están
desactivados. El agente calcula localmente con bash/Python. Los permisos generales
están en allow; webfetch, websearch y question están en deny. Las entradas CSV y el
contexto se montan en `/inputs` con solo lectura real: se permite únicamente ese
directorio externo. Esta excepción y el uso de `serve` + MCP, frente a `run` en
los ensayos, son diferencias que deberá medir F5.

Cada runtime tiene volúmenes exclusivos state/work/inputs, red none, recursos
acotados y credenciales privadas de trabajo. El proveedor se alcanza solo por el
proxy acotado; su clave nunca entra en el agente. `tunnel.JobTunnel` ejecuta el
relay del código confiable para las rutas de ese trabajo, sin socket Docker en
el agente. El outbox reconcilia mensajes por ID; el uso incierto no se reintenta.

El agente escribe `/work/informe.html` o llama a `entregar_informe`. La recogida
para el runtime y lee el archivo regular desde un helper sin red y con el
volumen de trabajo en solo lectura. Conserva bytes exactos, incluso HTML vacío,
malformado o interrumpido; no ejecuta ni parsea HTML. El límite de recepción es
256 KiB. Los intentos mayores registran tamaño, hash, fecha y vía sin sustituir
recibos anteriores. La ejecución, el recibo y el permiso de presentación son
estados independientes. F0 no permite presentar HTML ni afirma verificación.

Las preguntas internas y los checkpoints se conservan, pero html-v1 no expone
preguntas al agente; su activación en producto pertenece a F3. El registro neutral
y el acceso de lectura son F1, el encargo generado y el panorama F2, la vista
segura y el texto canónico F4. PDF queda para una fase posterior.
