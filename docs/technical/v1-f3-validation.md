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

Pendiente en los siguientes commits: integración de respuesta web y acuse, recuperación del
controlador, UI y regresión de cierre. No se declara F3 terminada aún.

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
