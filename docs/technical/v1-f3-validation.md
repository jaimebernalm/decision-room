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
