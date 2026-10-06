# Admisión del motor: primer tramo de P2

El servicio interno admite llamadas únicamente con una credencial ligada a un
trabajo, su negocio, análisis y snapshot de tablas. La migración 32 y el paquete
`decision_room.engine` son optativos: todavía no existe el controlador OpenCode
ni la API pública `run_report` / `resume_report` / `export_run`.

## Estado persistido y cuotas

`admission.create_run` es una entrada del producto, no una herramienta expuesta al
agente. Fija modelo, contexto, límites y hashes del snapshot. Devuelve el token
una vez; almacena únicamente su hash. La misma clave y contenido recuperan el ID
sin emitir otro token; cambiar contenido bajo esa clave produce un conflicto.
El futuro controlador tendrá que custodiar y rotar la credencial de forma privada.

Cada operación comprueba credencial, vencimiento, revocación, estado y snapshot.
Solo `running` admite trabajo. El snapshot se contrasta con metadatos y bytes de
Parquet; el agente no puede elegir otro negocio o análisis en sus argumentos.

Las llamadas se registran antes del conteo. Una transacción con bloqueo del trabajo
reserva entrada y salida antes de contactar al modelo, contando otras reservas
pendientes. La salida por solicitud se acota al límite del trabajo. Al recibir
`usage` válido se reconcilia la reserva; caché forma parte de la entrada total.
Sin uso confirmado se conserva la reserva completa y se aborta. El uso que supere
la reserva se registra íntegro y detiene el trabajo, sin ocultar el exceso.

Los límites iniciales son hipótesis: 3 M de entrada, 64 k de salida acumulada,
8 k de salida por solicitud, 60 intentos de llamada y 20 min activos. El reloj se
comprueba al admitir y durante la recepción de contenido. El corte estricto de
pared durante una lectura bloqueada requiere todavía el supervisor del
controlador; el timeout de red no sustituye ese supervisor. No hay aún pausa,
restauración de sesión, copia SQLite ni política global de ritmo por host.

## Proxy de Responses

`proxy.forward` usa exclusivamente el endpoint de OpenAI configurado en código,
sin redirecciones, proxies del entorno ni reintentos. Solo admite el modelo
fijado para el trabajo y contexto explícito de texto con herramientas locales.
Rechaza referencias a conversaciones/respuestas remotas, medios y herramientas
alojadas. Impone `store=false` y cuenta exactamente la misma representación de
entrada, instrucciones y esquemas de herramientas que enviará a generación.

El conteo remoto previo usa `/responses/input_tokens`; un fallo impide generar y
queda como aborto duradero. Su latencia se guarda separadamente como
`count_seconds`. No se presupone que los bytes del JSON acoten todos los tokens
del proveedor. Véanse el [conteo oficial de tokens](https://developers.openai.com/api/docs/guides/token-counting)
y el [control de gasto por ejecución](https://developers.openai.com/cookbook/articles/per_run_spending_controller_responses_api).

El parser SSE tolera fragmentación y CRLF, distingue terminación completa,
incompleta y ausencia de uso. La clave del proveedor pertenece al servicio;
nunca se acepta del agente ni se guarda en el registro de llamadas. No se
registran cuerpos privados ni cabeceras de autorización. Todavía falta comprobar
esta lista de campos con el tráfico real de OpenCode 1.18.34 y registrar precios,
modelo efectivo y metadatos necesarios para el coste de catálogo.

## MCP y resultados

`server.Server` se inicia explícitamente en una dirección interna (por defecto,
loopback). Solo sirve POST a `/jobs/<id>/mcp` y `/jobs/<id>/v1/responses`, con
bearer por trabajo. Valida Origin, tamaño, Content-Length y tipo de contenido.
MCP implementa initialize, ping, tools/list y tools/call con respuestas JSON y
notificación de inicialización 202; sigue el [transporte MCP](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports).
No está montado en la aplicación web ni constituye un despliegue listo para uso.

Por ahora hay dos herramientas:

- `consulta` ejecuta Python en el sandbox Docker existente, exclusivamente sobre
  las tablas permitidas. La clave de ejecución incluye el trabajo; repetir clave
  y contenido devuelve la ejecución anterior, y cambiar contenido la rechaza.
- `resultado` pagina únicamente ejecuciones vinculadas al trabajo. Los valores
  son candidatos pendientes de verificación, nunca cifras aprobadas.

Las páginas contienen como máximo 100 filas y tres columnas (puntero JSON,
número de fragmento, valor). Dividen cadenas en fragmentos de hasta 512 caracteres,
con cursor, total de filas, marca de truncado y hash del resultado completo. Cada
respuesta MCP queda bajo 64 KiB, incluyendo escapes. El resultado privado completo
continúa en el almacén de ejecuciones. Las rutas de campo mayores de 512 caracteres
se rechazan; la presentación final de tablas y artefactos sigue pendiente.

## Comprobaciones y alcance restante

Se ejecutaron 38 pruebas: 20 del motor y 18 de actividad/migración, con PostgreSQL,
HTTP y Docker reales; proveedor simulado. Incluyen credenciales de otros trabajos
y negocios, revocación, caducidad, waiting, cambio de metadatos/bytes del snapshot,
reservas concurrentes, cuotas de entrada/salida/llamadas, vencimiento activo,
reconciliación, uso desconocido leído desde otro proceso, SSE incompleto,
idempotencia de la consulta real y paginación Unicode. Las 11 pruebas del ejecutor
existente también pasan. No se hicieron llamadas facturables.

Esta evidencia valida los fundamentos de admisión, no todo P2. Faltan imagen y
red aislada del agente, supervisor y cliente OpenCode, `panorama`, `verify_numbers`,
`entregar_informe`, `preguntar_propietario`, persistencia del borrador antes de
validar, exportación, recuperación con procesos terminados y las seis ejecuciones
reales. Tampoco se ha probado conservación de informes: aún no existe su almacén.
P2 permanece abierto y P3 no ha empezado.
