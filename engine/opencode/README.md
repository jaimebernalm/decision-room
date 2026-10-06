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
No pretende probar todavía toda la red de producto, proxy y pasarela. Usa HTTP
local dentro del contenedor: Docker no publica su puerto en esta red interna.

El cliente `decision_room.engine.client` corresponde al OpenAPI de la etiqueta
1.18.34: crea sesiones con título, envía `prompt_async` con messageID persistido
por el futuro controlador, consulta mensajes/hijos/estado y aborta. No reintenta
mutaciones y trata un timeout de envío como recepción incierta. SSE terminado
obliga a reconciliar la sesión. Sus pruebas de transporte usan un servidor
simulado; el smoke comprueba los endpoints reales con la biblioteca estándar.

La comprobación de título en `session/prompt.ts:193–200` de OpenCode omite la
llamada de título si la sesión ya tiene uno explícito. Esto es evidencia de código;
el presupuesto de llamadas ocultas aún debe verificarse con un turno real.
Fuente: [OpenCode 1.18.34](https://github.com/anomalyco/opencode/tree/v1.18.34).

`decision_room.engine.checkpoint` usa la API backup de SQLite, que incorpora WAL
confirmado sin copiar una base a medio escribir. Comprueba integridad, hash y
publicación exclusiva. La restauración exige un destino nuevo y un servidor
parado. Las pruebas cubren WAL, transacciones no confirmadas, revisiones de copia,
corruptelas y enlaces simbólicos. No es aún un checkpoint completo de OpenCode:
falta incorporar los archivos de trabajo, registrar el puntero duradero en
PostgreSQL y probar reanudación de la sesión en otro contenedor.

Todavía faltan plantilla de configuración con MCP/proxy por trabajo, supervisor,
red completa, outbox y controlador de ejecución/espera/reanudación. Estos
componentes no habilitan el motor en la interfaz ni completan P2.
