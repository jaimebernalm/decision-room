# F3: espera y preguntas al dueño

Base: F2 `37f1c45`. Solo F3; legacy sigue por defecto. No llamadas a modelos.

## Perfil y guardas (primer paso completado)

- `html-v1` conserva preguntas desactivadas. El opt-in interno `engine_questions: true`
  fija `html-v1-questions-1` al crear el trabajo; no es una opción de UI ni cambia runs previos.
- Encargo opt-in `v1-brief-1q`, con texto y hash propios. La pregunta MCP `preguntar_dueno`
  permite una pregunta por run; repetir la misma clave y contenido recupera su recibo.
  La herramienta nativa `question` continúa desactivada.
- La respuesta se guarda solo en el run y su outbox; nunca se convierte automáticamente en
  memoria del negocio, ni sustituye las dependencias o el encargo congelados.
- Vencimiento de siete días: conserva entregas, respuesta y checkpoint, pero no reactiva.
  La restauración y la activación comprueban la vigencia de datos, definiciones y memoria
  bajo el lock de memoria antes del lock del run.
- Una respuesta desconocida o rechazada sigue siendo una declaración y una limitación;
  no se inventa una respuesta a partir del silencio.

Pruebas de este paso: 68 PostgreSQL (questions, brief, jobs, admission), todas pasan.
Incluyen reintento MCP al pausar, opt-in inmutable, límite real de preguntas, vencimiento,
cambio de definiciones antes de restaurar, identidad y límites acumulados.

Los pasos de respuesta, controlador y UI se documentan a continuación; el cierre
depende de la regresión completa y la revisión cruzada.

## Respuesta web y acuse (segundo paso completado)

`web/engine_wait.py` adapta el detalle y `reply` con negocio, trabajo, run y pregunta
exactos. `web_replies` y `engine_owner_answers` se guardan en la misma transacción;
una caída antes de terminar no deja solo uno de los recibos. Se reutiliza el JSON existente,
sin modificar ni migrar recibos legacy. La cola web conserva `pending_answer` hasta el
acuse del mensaje exacto del outbox o su reconciliación; guardar la respuesta no basta.

Orden de locks de respuesta: selección del negocio, memoria, run y trabajo. Confirmar un
prompt toma run y trabajo en el mismo orden. Dos respuestas no sobrescriben el primer
recibo. El detalle usa comparación barata de vigencia y presencia; no hashea archivos.

Pruebas: 38 (web_wait, questions, control, jobs), sin fallos y un smoke Docker omitido.
El selector de una prueba legacy inexistente se corrigió antes de esta pasada; no fue un
fallo de implementación. Se probó interrupción entre los dos recibos, antes del envío,
reintento tras completar, dos respuestas y pregunta/run ajenos. El encargo y la memoria
conservan sus versiones después de responder.

## Controlador y recuperación (tercer paso completado)

El controlador comprueba la espera antes de restaurar y otra vez al activar. Un
turno de respuesta en cola comprueba también la vigencia antes de enviarse. Si la
pregunta vence o cambia su contexto tras guardar la respuesta, el run se aborta,
el trabajo queda bloqueado y los recibos y `pending_answer` se conservan.

La identidad de restauración se guarda antes de copiar. Si la copia termina y el
proceso cae antes de activar, se reutilizan generación y token. Una restauración
parcial se detiene como `failed`, conservando checkpoint y respuesta; no se crea
una nueva generación automáticamente. Recuperar `pausing` detiene y captura sin
arrancar el agente. Si el prompt previo quedó sin reconciliar, no se declara una
espera íntegra: queda `failed` y conserva lo recibido, sin repetir el envío.

Una respuesta HTTP perdida después de aceptar el prompt se reconcilia por su ID
persistido. El marcador de envío impide reenviarlo. No se reinician presupuestos,
encargo, contexto o sesión. Uso de modelo incierto conserva la política de aborto
sin reintento de F0; un fallo transitorio del controlador exige análisis nuevo.

Las comprobaciones profundas de pregunta/reanudación y envío de respuesta hashean
los CSV bajo el lock de memoria; son eventos raros, no lecturas de página. La
prueba concurrente verifica que un writer de memoria espera y continúa cuando se
libera el lock. La excepción de credencial de `retry_question` existe solo para
recuperar un recibo idéntico durante `pausing`; `questions.request` vuelve a exigir
perfil, identidad, estado y límite de una pregunta para una solicitud nueva.

Pruebas: 59 PostgreSQL, sin fallos, con un smoke Docker omitido hasta la regresión
nativa. Incluyen SIGKILL real en procesos nuevos antes/después de la transacción de
respuesta, después de pregunta, checkpoint y espera, durante restauración,
antes/después de activación, envío y reconocimiento. Dos workers reanudan una sola
vez; sesión, archivos y encargo permanecen iguales. Se prueban vencimiento y
revocación entre recibo y worker, revocación tras activación, restauración fallida,
espera sin modelo y acuse de transporte perdido. Los primeros fallos de fixtures
(claves reutilizadas y patch de método) se corrigieron antes de esta pasada.


## UI y chat

La aclaración muestra pregunta, motivo, opciones y espera detenida. Permite una
respuesta explícita, no disponer del dato o preferir no responder. Avisa de que
la respuesta es una declaración y de los siete días de vencimiento. La respuesta
guardada permanece visible con su pregunta y disposición, aunque el run se
bloquee. Nunca se ofrece el reintento legacy para recuperar un run del motor.

En el chat, la identidad del run se captura de la pregunta validada por el
servidor y se guarda en el payload del turno. La respuesta usa el mismo recibo
web/run y no crea memoria. Esperas vencidas o ya respondidas dejan de mostrar la
aclaración. Con contexto seleccionado, la transacción ya tiene el lock de memoria:
se consulta solo metadato de espera, sin abrir otra conexión con el lock de lectura
del informe parcial. La prueba usa entrega parcial y perfil seleccionado, con
statement_timeout, y completa sin quedarse esperando su propio lock.

`DeliveryUncertain` usa el mismo `uncertain_since` y tope de 30 segundos que los
otros envíos no reconciliados; el marcador impide un segundo envío y una segunda
reserva. El controlador aborta si no se acredita el mensaje dentro de ese plazo.

La primera regresión completa se interrumpió para incorporar la comprobación de
chat con contexto seleccionado y corregir la limpieza del fixture: los turnos de
chat referenciaban los trabajos que el siguiente setUp intentaba borrar. No se
presenta esa pasada como exitosa. La validación de cierre usa el estado final.

## Límites y siguientes fases

F3 mantiene `html-v1` sin preguntas y legacy como motor por defecto. El perfil con
preguntas es un opt-in interno distinto que requiere su propia evaluación antes
de adoptarse. No se autoriza servir HTML ni afirmar verificación de las cifras.
F4 conserva la responsabilidad de vista aislada y derivados, y F5 la comparación
por la ruta real del producto y el límite monetario antes de cambiar el motor por defecto.
Ninguna respuesta amplía límites ni inicia automáticamente un análisis nuevo.

## Validación de cierre

- PostgreSQL focalizado de espera y chat: 74 pruebas, cero fallos, errores y
  omitidos. Incluye declaración `unknown` desde chat con perfil seleccionado y
  una entrega parcial, sin insertar memoria ni cambiar el run.
- Regresión Python final: 759 pruebas en 577,819 segundos, cero fallos, errores y
  omitidos. PostgreSQL desechable, sandbox construido e imagen OpenCode fijada;
  incluye los smokes Docker nativos, migraciones, rutas legacy y UI web/chat.
  Los logs de excepciones pertenecen a los casos de inyección de fallos; el
  resultado final de unittest es `OK`.
- UI: 311 pruebas en 40 archivos, todas pasan. TypeScript, Vite y oxlint pasan;
  se conservan advertencias existentes de Fast Refresh y tamaño de bundle.
  Las seis nuevas pruebas cubren los tres tipos de respuesta, conservación en
  bloqueo/fallo sin retry legacy e historial de la declaración rechazada.
- Clave del proveedor vacía; todos los modelos son falsos. Sin gasto de API.
- `git diff --check` y revisión de archivos preparados para el repositorio público:
  sin credenciales, rutas personales, datos privados ni archivos generados grandes.

Commits locales previos: `fd1e5c7` (perfil y guardas), `0f1f643` (recibo web y acuse),
`19dda7d` (recuperación sin replay). Este documento acompaña el commit de cierre
con UI, chat y las comprobaciones finales. Claude revisó los tres anteriores y el
borrador final sin cambios bloqueantes; la revisión del commit final queda en el
registro de colaboración. F3 está implementada dentro del alcance descrito.
