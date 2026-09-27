# Selección de contexto y conversación lateral

27 de septiembre de 2026. Estado: implementado y validado; paso 2.5.16.
Véanse [pruebas, correcciones y límites](../validation/2026-09-27-contextual-chat-check.md).

Ampliación de los pasos 2.5.6 (navegación y contexto), 2.5.10 (continuidad del
chat) y 2.5.14 (dashboard) del [plan de implementación](../product/Decision%20Room%20-%20Plan%20de%20implementacion.md).
Ejecutado después del paso 2.5.15, conservando los trabajos de onboarding.

## Experiencia acordada

«Nuevo chat» abre directamente el panel derecho sin crear una conversación hasta
el primer envío. Desde Inicio, Mi negocio e Informes mantiene la página; desde
Conversaciones o un chat ampliado vuelve a Inicio. La ruta antigua `#ask`
redirige al mismo resultado. Los chats recientes permanecen en la navegación,
sin un selector duplicado dentro del panel.

La barra del chat incorpora una herramienta visible «Seleccionar», con icono.
No se añaden botones «Preguntar sobre esto» en cada tarjeta del dashboard o
sección del informe. Al activar la herramienta, los bloques seleccionables se
resaltan al pasar el cursor o recibir foco. Clicar añade o quita un bloque;
se pueden adjuntar varios. «Listo» o Escape sale del modo sin borrar lo elegido.
Se mantiene el desplazamiento de la página. Las acciones normales de las tarjetas
no se ejecutan mientras el usuario está seleccionando.

Los adjuntos aparecen encima del texto: miniatura y título para gráficos, valor
y etiqueta para indicadores, extracto para hallazgos y secciones, vista compacta
para tablas. Se pueden quitar individualmente y ampliar antes de enviar.

Al enviar desde Inicio/dashboard, Mi negocio, Informes o un informe, la barra se transforma en un chat
a la derecha, conservando el contenido de origen visible. Se abre inmediatamente
con estado real de envío, sin esperar la respuesta del modelo. Un error conserva
texto, selecciones e identidad de reintento. El panel permite seguir preguntando
y adjuntar nuevas selecciones. El ancho es ajustable y se puede plegar.

La cabecera incluye «Abrir conversación completa»: navega a `#chat/:id` con el
mismo identificador, historial, borrador, adjuntos y trabajo en curso. Solo se
habilita cuando existe la conversación. No vuelve a enviar el primer mensaje.
La página completa muestra los adjuntos del usuario aunque el asistente no
repita el gráfico en su respuesta. Al abrir uno, muestra el gráfico, tabla o
fragmento a tamaño legible, con título, periodo, procedencia y enlace al origen.
Volver al informe restaura el bloque y posición de lectura cuando siga disponible;
permite continuar la misma conversación acoplada a la derecha.

En pantallas estrechas se utiliza un panel de ancho completo con regreso al
contenido, conservando la selección y el desplazamiento; no se comprimen dos
columnas hasta volverlas ilegibles. Las animaciones respetan movimiento reducido.

## Base comprobada y componentes oficiales

| Pieza | Situación y decisión |
| --- | --- |
| Compositor | `frontend/src/components/workspace/composer.tsx` usa AI Elements. Reutilizar `PromptInputTools`, `PromptInputButton` y la zona superior del compositor. |
| Adjuntos | Incorporar el componente oficial `Attachments`, ausente del árbol actual. Componer su presentación con vistas propias de gráfico, métrica y texto. |
| Menú de herramientas | `PromptInputActionMenu` ya está en el código del proveedor. Dejar Seleccionar visible inicialmente; ampliar el menú cuando existan otras herramientas. |
| Conversación | Extraer de `chat.tsx` un controlador y una vista compartidos para panel y página, manteniendo `Conversation` y `Message`. |
| Gráficos | Reutilizar `EvidenceChart` y `ChartData`; mantener cifras, unidades y series verificadas. La miniatura será una representación React/SVG de esos datos, sin exigir capturas de pantalla. |
| Movimiento | Reutilizar Motion y la identidad visual del compositor; preservar scroll y foco durante el cambio de distribución. |
| Referencias | Existe `finding_reference` singular. Se necesita una colección de referencias tipadas y persistentes por mensaje. |

Documentación oficial consultada:
[Prompt Input](https://elements.ai-sdk.dev/components/prompt-input) y
[Attachments](https://elements.ai-sdk.dev/components/attachments).
Los componentes aportan herramientas y presentación de adjuntos; la selección
de bloques y el acoplamiento al dashboard pertenecen a nuestra aplicación.

Incorporar Attachments desde el registro oficial con el procedimiento de
`frontend/README.md`, revisando dependencias, licencia y diferencias. No reemplazar
automáticamente el compositor actual ni sus adaptaciones de borradores y errores.
Un adjunto de contexto se conserva como referencia de negocio; no se convierte
en un archivo subido para aprovechar la interfaz del proveedor.

## Contrato y persistencia

Añadir `context_references` a borradores, envío y lectura de turnos. Cada selección
contiene `report_id`, `report_version`, `kind` y `element_key`. Tipos iniciales:
gráfico, indicador, tabla, hallazgo y sección completa de informe. El servidor
resuelve sus hallazgos asociados, datos, título, periodo y procedencia. No acepta
cifras o títulos enviados por el navegador como evidencia autorizada.

Los gráficos ya tienen clave. Normalizar claves para indicadores y secciones
en las proyecciones de Inicio e informe; no utilizar posición DOM o título como
identidad. La identidad de selección incluye informe, revisión, tipo y clave:
dos tarjetas que señalen el mismo elemento se deduplican. Límite inicial propuesto:
ocho referencias por mensaje, validado en cliente y servidor.

Conservar compatibilidad con mensajes antiguos que usan `finding_reference`.
Normalizar a una lista al leerlos. Rechazar envíos ambiguos con ambos formatos.
Implementación final: guardar las referencias normalizadas en el JSON del turno
y resolver su proyección desde el servidor en cada lectura, sin duplicar series
en el mensaje persistido. No guardar imágenes base64 ni datos de pantalla en localStorage.
La vista ampliada obtiene las series completas del informe versionado mediante
una lectura autorizada; la miniatura puede simplificar la presentación sin
modificar las cifras de la vista completa. Establecer límites de tamaño al
serializar proyecciones, reutilizando los límites de los informes.

Cada lectura verifica negocio, acceso y estado de la evidencia antes de entregar
contenido visible. Una versión histórica permitida se etiqueta como tal y no
se sustituye por la reciente. Una referencia retirada conserva su identidad y
motivo de indisponibilidad, pero no sus cifras o miniatura como contenido vigente;
las cachés visibles también deben invalidarse. La retirada no rompe todo el chat.

El contrato debe permitir seleccionar bloques de varios informes del mismo negocio.
Actualmente `Conversations.send` fija `analysis_id` a partir del primer
hallazgo y rechaza otro conjunto. Separar las referencias consultadas del conjunto
elegido para una investigación: adjuntar varios gráficos no elige ni fusiona
automáticamente sus datos. Si una investigación necesita varios conjuntos, usa
la recuperación existente y pide aclaración cuando no pueda resolver la relación.
Una incompatibilidad con un conjunto explícito debe explicarse sin descartar
silenciosamente adjuntos ni cambiar la selección de datos.

Propagar todas las referencias al contexto del agente, recuperación, manifiesto
de evidencia, dependencias de investigaciones e invalidación. Revisar los usos
singulares en `decision_room/conversations.py` y `decision_room/chat_agent.py`;
cambiar únicamente la API de entrada no cubre el recorrido completo.

La firma idempotente incluye texto, aclaración y lista ordenada normalizada de
referencias. Un reintento exacto recupera el mensaje ya guardado; modificar sus
adjuntos con la misma clave se rechaza. Validar todos los adjuntos en la misma
transacción antes de persistir el mensaje, conservando los bloqueos de revisión
y memoria existentes. Si uno caduca antes del primer envío, informar cuál y
mantener el borrador para que el usuario pueda quitarlo.

## Estado de interfaz y navegación

Crear un proveedor del asistente por negocio, por encima de las rutas que
comparten barra y panel. La barra actual se remonta por ruta; el estado de la
conversación no puede depender de ese componente. Mantener separados:

- Presentación: barra, panel o página completa.
- Selección: activa/inactiva y referencias en el borrador.
- Conversación: identificador, mensajes, envío, cola y aclaraciones.
- Origen: ruta, bloque y posición de lectura; no altera la evidencia del mensaje.

Al plegar se conserva conversación y borrador. Cambiar entre Inicio, Mi negocio e Informes
mantiene el chat acoplado; un nuevo bloque se añade al siguiente mensaje. «Nueva
conversación» crea otro chat solo al enviar. Desde la página completa, abrir un
origen puede volver a acoplar el chat existente. En las demás pantallas se conserva
el comportamiento de navegación actual y no se ofrece selección sin bloques.

Compartir las claves durables de `launchChat` y `messageKey`, el estado de envío
y un único lector activo del chat. Persistir referencias del borrador e identidad
del chat activo para recuperar recargas; las respuestas tardías no cambian de
ruta ni de negocio. Un cambio de negocio reinicia el proveedor y cancela lecturas.
No montar dos compositores o lectores compitiendo al ampliar el panel.

## Secuencia de implementación

### 1. Referencias múltiples y recuperación verificable

Ampliar tipos, proyecciones, envío, lectura, recuperación del agente y dependencias.
Añadir resolución de un adjunto para su vista ampliada y compatibilidad histórica.
Zonas principales: `decision_room/conversations.py`, `decision_room/chat_agent.py`,
`decision_room/web/dashboard.py`, `decision_room/web/home.py`, rutas web y
`frontend/src/lib/types.ts`/`api.ts`.

Comprobar persistencia tras reinicio, varios informes del mismo negocio, rechazo
de otro negocio o elemento falsificado, conflicto de versión, retirada, límites
e idempotencia. Contrastar las cifras de la proyección con la evidencia guardada.
Guardar un commit local cuando este incremento pase sus comprobaciones.

### 2. Motor de conversación compartido

Extraer el controlador de `ChatPage` y coordinarlo con `FloatingAssistant`,
`App.tsx` y `Layout`. Conservar la página actual mientras se habilita presentación
en panel. Mantener cola, aclaraciones, errores, reintentos y borradores.

Comprobar que abrir, plegar, cambiar ruta, ampliar y recargar no duplica chats ni
mensajes, y que cambiar de negocio no deja datos del anterior. Revisar y commit.

### 3. Herramienta de selección y adjuntos visuales

Incorporar Attachments oficial y un registro de bloques seleccionables en Inicio
y Report. Añadir selección múltiple, estado visual, miniaturas, eliminación y
vista previa. Ocultar o retirar acciones anteriores de preguntar por bloque donde
estén activas. Reutilizar el mismo adjunto visual en borrador y mensaje enviado.

Comprobar selección/deselección, deduplicación, límite, borrador tras fallo,
referencias de varios informes y controles normales fuera del modo selección.
Validar teclado, foco, Escape y toque sin depender del hover. Revisar y commit.

### 4. Panel fluido y conversación completa con contenido consultable

Abrir el panel al enviar desde dashboard/informe, con ancho ajustable, minimizar
y «Abrir conversación completa». Mantener el origen visible sin superponer el
panel al gráfico. La página completa presenta todos los adjuntos persistidos y
permite abrirlos a tamaño legible, incluso al entrar desde el historial o recargar.
Implementar regreso al origen y presentación móvil con los mismos mensajes.

Comprobar el recorrido completo: seleccionar dos gráficos → preguntar → respuesta
lateral → ampliar → abrir ambos gráficos → recargar → regresar al origen. Verificar
identidad del chat, cifras, scroll, borrador y continuidad durante una respuesta
pendiente. Revisar temas claro/oscuro y movimiento reducido. Revisar y commit.

### 5. Validación integrada

Ejecutar pruebas de frontend, compilación, lint y regresión Python/HTTP pertinentes.
Usar datos públicos de referencia para un recorrido con el modelo y comprobar
que su respuesta consulta los elementos exactos sin inventar relaciones entre
periodos o conjuntos. Revisar visualmente escritorio y móvil. Registrar pruebas,
límites, fallos y hashes de los commits antes de dar la ampliación por terminada.

No cerrar este paso con solo una demo visual: los adjuntos deben recuperarse
desde servidor y seguir visibles al abrir una conversación por su ruta directa.

## Límites de la primera versión

Selección por bloques completos de dashboard e informe, resúmenes del listado
de Informes y presentación/hechos activos de Mi negocio. El lazo de píxeles,
selección arbitraria de texto, archivos e historial retirado quedan fuera
de esta implementación. Se conservan las referencias y la vista de los
gráficos originales; no se incorpora edición de informes ni recálculo al seleccionar.

## Verificación de esta planificación

Contrastes realizados: navegación y envío actuales, borradores y reintentos,
restricción de una referencia por turno, asociación a un conjunto, proyecciones
del dashboard, claves de gráficos, presentación de mensajes y componentes de
Vercel disponibles. Revisar enlaces locales y diferencias antes de guardar este
documento. Las pruebas de ejecución se completaron y constan en la
[validación integrada](../validation/2026-09-27-contextual-chat-check.md).
El paso 1 se guardó en `3cfaaa8`; los pasos 2–4, desarrollados y comprobados
conjuntamente, en `a785c61`. El cierre del paso 5 registra los resultados y límites.
Se reutiliza `ChatPage` tanto en panel como en página y la lectura existente del
chat entrega los adjuntos; no fue necesario añadir un endpoint de resolución.
La transición usa CSS con respeto a movimiento reducido, y las tablas conservan
el tipo de gráfico tabular del contrato de presentación existente.


## Ampliación a Mi negocio e Informes

El panel permanece montado al navegar por Inicio, Mi negocio e Informes, con el
mismo identificador, borrador y adjuntos. El editor de presentación y la ruta de
datos también conservan el panel; el editor no ofrece selección de campos.
La navegación principal pasa a Inicio, Mi negocio, Informes y Conversaciones;
el listado usa dos bocadillos para distinguirse del icono de los chats individuales.

Las referencias de perfil y memoria usan `source_id`, `source_version`, `kind`
(`business` o `memory`) y `element_key`. El servidor resuelve la presentación
vigente o la última revisión activa del hecho dentro del negocio seleccionado.
No acepta contenido aportado por el cliente. Conserva autoridad, estado, ámbito
y alternativas para distinguir contexto del propietario de resultados revisados.
La captura de correcciones recibe contexto de la selección, con su estado y ámbito,
sujeto al límite de 6.000 caracteres de la pregunta auxiliar existente.

Un envío con versión antigua se rechaza. Si cambia después de enviarse —incluida
una corrección solicitada por el propio mensaje— el adjunto se marca no disponible;
la respuesta dispone del perfil y memoria vigentes sin recuperar el texto retirado
como evidencia actual. Las selecciones de informes siguen obligando al agente a
abrir y citar la revisión exacta. El listado solo ofrece referencias de informes
publicables; seleccionar un resumen no lanza un nuevo cálculo.


## Corrección del listado y procedencia de adjuntos

Desde la conversación completa queda una sola acción «Abrir en panel», que abre
Inicio con la misma identidad y borrador. Abrir un adjunto conserva su acceso al
origen concreto. El control duplicado de regreso se retira.

Seleccionar una fila de Informes usa `kind=report`, `element_key=report`, el
identificador de revisión y su versión. `selection_scope=whole_report` diferencia
el informe completo de un fragmento; su resumen sirve de miniatura, pero el agente
debe abrir la revisión íntegra. Las referencias antiguas `section/summary` siguen
siendo fragmentos válidos. La memoria incorpora fuente, tipo, texto original y
pregunta de procedencia para contrastar de dónde procede un dato, sin inferirlo
solo a partir del resumen del informe.

Esquema 18 añade `web_jobs.deleted_at`: el listado y recientes excluyen eliminados;
`GET /api/reports/deleted` ofrece la papelera del negocio activo. Los POST
`/api/jobs/:id/delete` y `/restore` validan negocio y trabajo con bloqueo, son
idempotentes y no purgan datos ni revisiones. No se elimina un trabajo en curso.
La interfaz permite confirmar, cancelar y restaurar; las referencias históricas
siguen apuntando a los originales. Véase la
[validación](../validation/2026-09-27-report-context-fixes.md).
