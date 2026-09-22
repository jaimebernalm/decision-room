# Agente principal: paso 1.4

Este agente interpreta los archivos de un análisis, selecciona perfiles, propone
investigaciones y pregunta por definiciones materiales. LangGraph conserva la
pausa y permite continuar desde otro proceso. El resultado es provisional: no
genera Python ni calcula métricas dentro de esta fase. La fase posterior del
[paso 1.5](research.md) ya conecta esta sesión al sandbox y registra candidatos.
El [paso 1.6](review.md) añade borradores estructurados, conversación con el revisor
e informes HTML; la aprobación se guarda separada de esta planificación.

## Ubicación y responsabilidades

| Archivo | Responsabilidad |
|---|---|
| `decision_room/agent/contracts.py` | Contratos Pydantic, procedencia y referencias válidas; dependencias pendientes bloquean investigaciones. |
| `decision_room/agent/context.py` | Catálogo y perfiles del lote autorizado, muestras acotadas y huella de la entrada. Excluye rutas internas y respuestas de evaluación. |
| `decision_room/agent/prompts.py` | Instrucciones versionadas de interpretación, preguntas y límites analíticos. |
| `decision_room/agent/model.py` | Conexión configurable a LM Studio o Chat Completions compatible, límites de salida y registro de consumo. |
| `decision_room/agent/graph.py` | Grafo `reason → inspect → reason → record → ask → reason`; pausa persistente con `interrupt`. |
| `decision_room/agent/persistence.py` | Checkpoints, revisiones, preguntas y llamadas; bloqueos e idempotencia. |
| `decision_room/agent/service.py` | Crear, consultar, responder y reanudar sesiones dentro de su empresa; rechaza cambios de entrada silenciosos. |
| `decision_room/agent/__init__.py` | Marca el paquete del agente. |
| `decision_room/__main__.py` | Nuevos comandos de terminal `agent-*`. |
| `decision_room/schema.sql` | Migración 3: sesiones, revisiones, preguntas, respuestas y llamadas. |
| `tests/test_agent.py` | Pruebas de integración PostgreSQL/LangGraph con modelo simulado explícito. |
| `scripts/checks/check_agent.py` | Pruebas separadas con el modelo real, CSV públicos y nuevos procesos para responder. |
| `requirements.txt`, `requirements.lock` | Dependencias directas y versiones completas del entorno anfitrión. |
| `.env.example` | Variables de ejemplo sin credenciales. No se carga automáticamente. |

## Arranque local

Ejecutar desde la raíz del repositorio, con Python 3.12:

```sh
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python scripts/dev/local_postgres.py start
.venv/bin/python -m decision_room init
lms server start --bind 127.0.0.1 --port 1234
lms ps
export DECISION_ROOM_AGENT_MODEL=qwen3.8-27b-splash
```

El modelo del ejemplo debe estar instalado y cargado en LM Studio. El protocolo
predeterminado `lmstudio_structured` usa `/v1/chat/completions`, JSON Schema y
`reasoning_effort: none` cuando se configura `DECISION_ROOM_AGENT_REASONING=off`.
La prueba local del paso 1.7 confirmó respuestas estructuradas con cero tokens de
razonamiento. El formato no garantiza exactitud semántica. El protocolo nativo
`lmstudio` sigue disponible con `/api/v1` y su control `reasoning`, pero únicamente
valida el JSON recibido; no promete gramática restringida. Las sesiones existentes
conservan su transporte y configuración originales.

El [evaluador del paso 1.7](evaluation-plan.md) añade escenarios repetidos,
referencias independientes y controles de acciones, identificadores y evidencia
según el estado real de la sesión. Sus resúmenes separan aprobación del modelo
y aceptación independiente.

Esta configuración permite reproducir las pruebas locales; no es una recomendación
de calidad. Consultar el [fallo semántico observado](../validation/2026-09-21-agent-check.md)
antes de usar sus propuestas. `DECISION_ROOM_AGENT_TIMEOUT` permite ajustar el
timeout entre 1 y 300 segundos; `DECISION_ROOM_AGENT_MAX_OUTPUT_TOKENS`, entre 256
y 16.384 tokens. Los valores se conservan por sesión. La evaluación local del
paso 1.7 usa `DECISION_ROOM_AGENT_TIMEOUT=300`; el valor predeterminado sin
configuración sigue siendo 180 s. Exportar explícitamente 300 para reproducir
esa configuración con la CLI.

Para un endpoint que implemente Chat Completions y JSON Schema:

```sh
export DECISION_ROOM_AGENT_PROTOCOL=chat_completions
export DECISION_ROOM_AGENT_BASE_URL=https://servidor-del-proveedor.example/v1
export DECISION_ROOM_AGENT_MODEL=identificador-del-modelo
```

La credencial opcional se lee de `DECISION_ROOM_AGENT_API_KEY`. Configurar su valor
fuera de Git. No se guarda en sesiones, checkpoints ni prompts. No se ha validado
un proveedor externo con este proyecto: algunos requieren adaptar parámetros,
autenticación o formato. Cambiar de modelo exige una nueva sesión y evaluación.
`DECISION_ROOM_AGENT_REASONING` se aplica a `lmstudio` y `lmstudio_structured`.
El protocolo genérico `chat_completions` no envía un parámetro de razonamiento
específico del proveedor.

El cliente del modelo vive en la aplicación, fuera del sandbox de Python sin red.
Un servicio comercial puede usar un proveedor externo o alojar el modelo en un
servidor propio: el cliente final no necesita instalar LM Studio. Este código es
una CLI de desarrollo; los UUID de empresa no son un sistema de autenticación.

## Crear, responder y recuperar

Sustituir los UUID por los devueltos por los comandos de ingesta:

```sh
.venv/bin/python -m decision_room agent-start \
  --business UUID_EMPRESA --analysis UUID_ANALISIS \
  --context-file contexto-del-propietario.md --request-key plan-1

.venv/bin/python -m decision_room agent-show \
  --business UUID_EMPRESA --session UUID_SESION

.venv/bin/python -m decision_room agent-answer \
  --business UUID_EMPRESA --session UUID_SESION --question UUID_PREGUNTA \
  --text 'El importe es el total de la fila, después de descuentos y sin impuestos.' \
  --request-key respuesta-1

.venv/bin/python -m decision_room agent-resume \
  --business UUID_EMPRESA --session UUID_SESION
```

Para una respuesta desconocida o rechazada, usar `--disposition unknown` o
`--disposition declined` sin `--text`. El grafo espera todas las preguntas del
lote actual antes de generar su siguiente propuesta. El trabajo independiente
permanece visible en el plan. Las preguntas son materiales; los datos opcionales
faltantes deben figurar como limitaciones.

`agent-show` muestra historial de revisiones, preguntas pendientes, respuestas,
consumo y estado. `ready` significa listo para investigar en el paso 1.5;
`limited` conserva investigaciones bloqueadas o imposibles; ninguno significa
cálculo aprobado. Todas las salidas llevan `verification=provisional_not_computed`.

Una clave repetida de inicio recupera la sesión si entrada y modelo coinciden.
Una respuesta repetida idéntica no se duplica. En este paso las respuestas son
inmutables: para corregir una ya enviada, iniciar otra sesión con el contexto
corregido mediante `agent-replan`. El [paso 1.5](research.md) conserva el vínculo
e invalida las investigaciones calculadas con la definición anterior.

## Persistencia, límites y fallos

PostgreSQL conserva `agent_sessions`, `agent_revisions`, `agent_questions`,
`agent_answers`, `agent_calls` y las tablas técnicas en el esquema privado
`agent_checkpoints`. Los CSV y Parquet siguen en almacenamiento privado.
Las muestras y respuestas también son datos privados, aunque se almacenen en SQL.

- Una ejecución por sesión mediante bloqueo PostgreSQL. Todas las entradas del
  servicio verifican su empresa antes de acceder al checkpoint.
- Hasta ocho perfiles por sesión, cinco filas de muestra por tabla y celdas de
  hasta 200 caracteres, tal como las produjo la ingesta. Catálogo de todo el lote.
- Contexto enviado máximo 200 KB; contexto del propietario 12.000 caracteres;
  respuesta del propietario 6.000 caracteres. Si el catálogo excede el límite,
  se necesita un lote menor; no se ocultan tablas silenciosamente.
- Hasta tres rondas de preguntas, tres preguntas por ronda, 16 turnos y 20
  peticiones al modelo contando fallos y correcciones. Una corrección estructural
  por turno. Respuesta HTTP limitada a 2 MiB y salida por defecto a 8.192 tokens.
- Timeout de red de 180 segundos por operación. Uso registrado si el servidor lo
  devuelve; no se supone tarifa ni se inventa un coste. El límite de llamadas es
  por sesión; un presupuesto global y límites por cliente son trabajo del piloto.
- Los resultados de peticiones completadas se reutilizan durante recuperación.
  Una caída entre envío y registro puede dejar incierto si el proveedor procesó
  la petición. Solo `agent-resume --retry-model` vuelve a enviarla en ese caso;
  podría generar un segundo coste. No se promete ejecución HTTP exactamente una vez.
- Las respuestas se guardan antes de continuar el grafo. Si el proceso cae en
  medio, `agent-resume` consume la respuesta ya guardada y no vuelve a preguntarla.
- Dos respuestas inválidas dejan una sesión fallida con diagnóstico. Repetirla
  reutiliza las mismas salidas; tras corregir el prompt o cambiar de modelo, crear
  una nueva sesión. Un error de conexión permite reintentar con `agent-resume`.

No hay acceso del modelo a SQL, shell, archivos arbitrarios, otras empresas ni al
ejecutor de Python en este paso. El payload se trata como datos no confiables.
LangSmith tracing se desactiva en la ejecución del grafo. El checkpointer no usa
pickle. El motor valida estructura y procedencia, pero no puede demostrar que una
frase del modelo sea cierta ni detectar todas las paráfrasis de una misma pregunta.
La revisión semántica y los casos con variaciones siguen siendo necesarios.

## Comprobaciones repetibles

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/checks/check_agent.py --model qwen3.8-27b-splash
.venv/bin/python scripts/checks/check_agent.py --model qwen3.8-27b-splash --answer unknown
.venv/bin/python scripts/checks/check_agent.py --model qwen3.8-27b-splash --variant
.venv/bin/python scripts/checks/check_agent.py --model qwen3.8-27b-splash --case 01-daily-sales
.venv/bin/python scripts/checks/check_agent.py --model qwen3.8-27b-splash --case 02-product-sales
```

El script crea datos de prueba y escribe resultados privados en `.local/agent-checks/`.
También admite `--wwi-business UUID --wwi-analysis UUID` para inspeccionar el lote
de 48 tablas existente. No lee `expected.json`; solo transmite una respuesta
explícita del propietario cuando se prueba la aclaración. Una ejecución terminada
requiere revisar el contenido; no equivale por sí sola a una evaluación aprobada.

Referencias oficiales: [LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts),
[persistencia](https://docs.langchain.com/oss/python/langgraph/persistence),
[API nativa LM Studio](https://lmstudio.ai/docs/developer/rest/chat) y
[JSON Schema compatible](https://lmstudio.ai/docs/developer/openai-compat/structured-output).
