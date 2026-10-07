# Admisión del motor: primer tramo de P2

El servicio interno admite llamadas únicamente con una credencial ligada a un
trabajo, su negocio, análisis y snapshot de tablas. Las migraciones 32–35 y el paquete
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
restauración de sesión completa ni política global de ritmo por host. La primitiva
de backup consistente de SQLite está disponible, pendiente de conectarse al controlador.

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

Por ahora hay cinco herramientas:

- `panorama` reutiliza el cálculo determinista existente para una tabla autorizada,
  sin activar contratos legacy. Congela resumen, código y observaciones por trabajo;
  pagina el resumen y expone referencias que `resultado` puede resolver. Un catálogo
  no compatible queda como no disponible, sin cifras cero fabricadas.
- `verify_numbers` resuelve métricas del trabajo y recalcula desde Parquet las del
  panorama, sin usar su caché de resultados. Conserva el antes, después, operación,
  mapeo, periodos y hashes. Un cambio de alcance impide corregir automáticamente;
  el cálculo Python del agente continúa no verificado, aunque sea trazable.
- `consulta` ejecuta Python en el sandbox Docker existente, exclusivamente sobre
  las tablas permitidas. La clave de ejecución incluye el trabajo; repetir clave
  y contenido devuelve la ejecución anterior, y cambiar contenido la rechaza.
- `entregar_informe` conserva bytes y hash en una revisión antes de parsear el
  texto. Su recibo significa recepción pendiente, no aprobación ni fin del trabajo.
- `resultado` pagina únicamente ejecuciones u observaciones del panorama vinculadas al trabajo. Los valores
  son candidatos pendientes de verificación, nunca cifras aprobadas.

Las páginas contienen como máximo 100 filas y tres columnas (puntero JSON,
número de fragmento, valor). Dividen cadenas en fragmentos de hasta 512 caracteres,
con cursor, total de filas, marca de truncado y hash del resultado completo. Cada
respuesta MCP queda bajo 64 KiB, incluyendo escapes. El resultado privado completo
continúa en el almacén de ejecuciones o en el snapshot del panorama. Las referencias
del panorama son observaciones deterministas congeladas, no filas ficticias de
`executions`; su origen se devuelve explícitamente. Las rutas de campo mayores de 512 caracteres
se rechazan; la presentación final de tablas y artefactos sigue pendiente.

La primera versión de `verify_numbers` admite referencias escalares de métrica;
las series y las recetas independientes para Python arbitrario siguen pendientes.
`verified_in_scope` significa que valor y operación del panorama se recalcularon
con la misma tabla y mapeo. Se vuelve a ejecutar la receta del producto: no es
una auditoría con un algoritmo independiente del calculador. No certifica cómo se atribuye la cifra en la prosa ni
las unidades confirmadas por el propietario. `corrected_in_scope` conserva ambos
valores y solo procede si la operación coincide. Una referencia ajena o ausente no
revela valores. Los resultados, límites e incidencias se guardan en un registro
idempotente con hash y se devuelven paginados; el verificador final de documentos
aún debe consumirlos y marcar visiblemente los bloques sin comprobación.

Ocho pruebas usan fixtures públicos pequeños, PostgreSQL y el sandbox Docker:
comprueban sumas y periodos conocidos, paginación, aislamiento, copia corrupta,
finalización tardía durante pausa, recálculo real sin caché, corrección inequívoca,
rechazo de un alcance distinto y un cálculo inventado que nunca se certifica.

## Entrega duradera antes de validar

`engine.store.receive_document` persiste hasta 256 KiB de UTF-8 en tablas propias
`engine_documents` y `engine_document_revisions`. Un bloqueo por trabajo serializa
las versiones. Reintentar una clave con los mismos bytes devuelve la misma
revisión; una representación distinta, aunque sea JSON equivalente, exige otra
clave. Las revisiones anteriores se conservan. JSON malformado, texto vacío y
bytes no interpretables siguen siendo exportables. Vacío nunca equivale a un
informe entregado.

La pasarela devuelve el recibo sin devolver al modelo el texto recibido. Su límite
de entrada HTTP es 2 MiB para admitir el sobre JSON y los escapes de una entrega
de 256 KiB; el límite de contenido se comprueba después sobre los bytes reales.
Los límites de código y resultados de consulta continúan vigentes.

`read_document` y `export_raw` son entradas del producto con ámbito de negocio,
no rutas autorizadas mediante la credencial del agente. Permiten recuperar un
borrador tras aborto, caducidad o revocación. Comprueban el hash y escriben
`draft.raw` y su recibo mediante reemplazo atómico de archivos privados. Una
entrega tardía en pausing/waiting/aborted sigue denegada. El controlador todavía
no persiste los mensajes intermedios ni genera una proyección verificada.

## Outbox y conservación de mensajes

`engine.control` vincula un trabajo a una sesión una sola vez. Cada prompt lleva
una clave y un ID de mensaje duraderos; cambiar el texto bajo la misma clave se
rechaza. Se permite un solo prompt pendiente. Antes de llamar a OpenCode se
confirman en PostgreSQL el texto y el estado `dispatching`, tras comprobar ámbito,
estado, caducidad, tiempo activo y snapshot. Un bloqueo cooperativo por trabajo
impide que dos controladores conduzcan simultáneamente la sesión.

Un 204 de `prompt_async` no confirma persistencia. Se consulta el ID y se contrasta
sesión, rol, partes y texto exacto antes de marcar `confirmed`. Tras timeout,
respuesta rota o caída del controlador, repetir la operación solo reconcilia: un
404 no autoriza otro envío. Si la caída fue entre el marcador y la petición, queda
pendiente; todavía falta la prueba de quiescencia/restauración que permitiría
recuperar ese caso con seguridad. No se declara reanudación completa.

Cada versión distinta observada de los mensajes se conserva con hash, incluidas
las parciales. Una observación más corta o un aborto no borra versiones anteriores.
Estas son operaciones internas con ámbito de negocio, no herramientas del agente.
Los hijos de la sesión y los archivos de trabajo aún requieren integración.

Las nueve pruebas del control usan PostgreSQL real e incluyen proceso terminado
tras el marcador, concurrencia, texto/identidades incorrectas, caducidad y lectura
después del aborto. Una de ellas usa además OpenCode real con un proveedor
inexistente en loopback: confirma un único mensaje duradero mediante el mismo
cliente y conserva su sesión, sin conexión a un proveedor ni gasto. Esto comprueba
recepción y recuperación de mensajes; no generación satisfactoria de informes.

## Comprobaciones y alcance restante

Se ejecutaron 47 pruebas: 29 del motor y 18 de actividad/migración, con PostgreSQL,
HTTP y Docker reales; proveedor simulado. Incluyen credenciales de otros trabajos
y negocios, revocación, caducidad, waiting, cambio de metadatos/bytes del snapshot,
reservas concurrentes, cuotas de entrada/salida/llamadas, vencimiento activo,
reconciliación, uso desconocido leído desde otro proceso, SSE incompleto,
idempotencia de la consulta real y paginación Unicode. Las nueve pruebas de
entrega cubren JSON roto, revisiones concurrentes, proceso terminado justo
después del commit, exportación tras aborto, claves conflictivas, permisos entre
trabajos/negocios, límites de bytes y detección de corrupción. Las 11 pruebas del ejecutor
existente también pasan. No se hicieron llamadas facturables.

La imagen ARM64 fijada y el cliente HTTP de OpenCode están disponibles; véase
[su construcción y alcance](../../engine/opencode/README.md). Nueve pruebas
comprueban el cliente sin reintentos implícitos y el backup/restauración SQLite
con WAL, corrupción y publicación exclusiva. Un smoke adicional usa OpenCode
1.18.34 real sin enviar prompts: autenticación, versión, sesión con título,
mensajes, hijos y aborto en un contenedor sin salida externa. No se hicieron
llamadas facturables. El cliente también se comprueba contra el servidor real usando HTTP loopback
a través de Docker exec, sin publicar puertos ni dar salida de red al agente.

Esta evidencia valida componentes de P2, no todo el paso. Faltan la red completa
de producto y agente, supervisor y conexión de `preguntar_propietario` al runtime,
verificación final de documentos, proyección y exportación completas,
captura de todos los hijos/archivos y recuperación completa del ciclo de vida,
y las seis ejecuciones reales. La prueba de terminación cubre el receptor de
borradores y el marcador del outbox; todavía no cubre la restauración completa
del controlador ni la caída durante la
verificación o el render.
P2 permanece abierto y P3 no ha empezado.

Última regresión del tramo: 74/74 pruebas de motor, actividad y migraciones,
incluidos los dos recorridos con OpenCode real aislado; sin gasto de modelo.

## Transporte local del servicio interno

`engine.tunnel.JobTunnel` conecta el HTTP loopback del agente con el servicio del
producto en el host mediante los pipes de `docker exec`. La clave del proveedor,
PostgreSQL, storage y el socket Docker permanecen en el host. El agente no recibe
otra red ni un puerto publicado del host. Esto resuelve el transporte local en
entornos donde Docker no publica puertos de una red `--internal`; no sustituye
la autenticación, las reservas ni las comprobaciones del servidor de producto.

El relay del contenedor solo acepta las dos rutas POST de su trabajo (MCP y
Responses). El host vuelve a validar ruta, ID, cabeceras y tamaños antes de
contactar exclusivamente un origen loopback configurado por el controlador.
Transporta bytes JSON y SSE con un máximo de ocho solicitudes simultáneas y
buffers acotados. No interpreta cuerpos como código ni reintenta mutaciones.
Un corte queda observable para que el futuro supervisor aborte y reconcilie;
el transporte por sí solo no cambia el estado PostgreSQL del trabajo.

Tres pruebas validan un contenedor real aislado con servidor de producto
simulado: JSON, UTF-8 y SSE concurrentes, rechazo de token en el destino, rutas de
otro trabajo, corte del proceso y validación del lado host frente a frames
manipulados. No son todavía pruebas del controlador completo ni del proxy real
con OpenCode generando un informe. El despliegue compartido del servicio por host,
supervisión, recuperación y generación completa siguen pendientes.

## Preguntas y respuestas duraderas (schema 36)

`preguntar_propietario` guarda la pregunta y cambia el trabajo a `pausing` en una
transacción. Devuelve un recibo breve; no mantiene HTTP abierto. El mismo contenido
con la misma clave recupera el recibo durante la pausa. El resto de herramientas,
nuevas llamadas y entregas tardías siguen bloqueadas. Una credencial revocada no
puede recuperar siquiera ese recibo.

El plano de control `engine.questions` separa tres operaciones:

1. `confirm_waiting`: después de que el supervisor detenga el runtime, verifica y
   fija la copia SQLite de ese trabajo. Exige prompts reconciliados y ninguna
   llamada con uso pendiente o incierto. Congela el tiempo activo y fija siete
   días de espera; repetir no cambia ni la copia ni el vencimiento.
2. `answer`: guarda una respuesta explícita e idempotente (`answered`, `unknown`
   o `declined`), también si la espera ya venció. No ejecuta nada automáticamente.
3. `activate_answer`: después de restaurar el runtime, comprueba la copia y el
   snapshot, rota la credencial y encola una sola respuesta en la misma
   transacción. Conserva consumo, reservas y segundos activos. El outbox existente
   confirma después el mensaje exacto en OpenCode; no reenvía una entrega incierta.

El supervisor debe persistir la nueva credencial privada antes de activar y
reutilizarla si no conoce el resultado de la transacción. La credencial anterior
no sirve en el turno reanudado. Los hashes guardados no permiten recuperarla.

**Límite de este tramo:** estas son transiciones del plano de control, no la API
`resume_report` ni una prueba de restauración completa del contenedor. El llamador
confiable todavía debe garantizar parada, preservación de los archivos de trabajo
y restauración antes de las transiciones correspondientes. La copia SQLite por sí
sola no demuestra esas condiciones. Falta conectar el supervisor, la captura de
archivos/hijos, las API públicas y el exportador. P2 permanece abierto.

Validación sin modelo: 75 pruebas de regresión del motor (incluidas imagen,
transporte y outbox con OpenCode real aislado), y posteriormente 30 de preguntas,
actividad y migraciones. Dos comprobaciones posteriores añaden el recorrido
HTTP y corrupción de la respuesta (14/14 de preguntas). Esas pruebas usan PostgreSQL y SQLite
reales; verifican concurrencia, aislamiento, repetición, corrupción, caducidad,
reservas inciertas y presupuestos conservados. No se facturó ninguna llamada.


## Tier de procesamiento

El proxy fija `service_tier="default"` como política Standard del servicio y lo
incluye en la petición efectiva cuyo hash se registra. Rechaza `auto`, Fast,
Priority, Flex, null y tipos inválidos antes de reservar o llamar al proveedor.
Omitirlo tampoco permite heredar el tier configurado en el proyecto. El conteo de
entrada recibe solo los campos admitidos por su endpoint. Las 21 pruebas de
admisión pasan, incluido el transporte simulado al proveedor que comprueba el
valor efectivo enviado y cero llamadas ante un intento de cambiarlo. Esto no
implementa todavía el catálogo ni demuestra el tier facturado por el proveedor.
