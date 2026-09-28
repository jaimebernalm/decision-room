# Actividad del cliente y monitor interno — 3.8

Implementado el 28 de septiembre de 2026. Véanse el [plan](live-investigation-plan.md)
y las [pruebas y límites](../validation/2026-09-28-live-investigation.md).

## Abrir las vistas

Con PostgreSQL, proveedor y sandbox ya configurados, desde la raíz del checkout:

```sh
.venv/bin/python scripts/dev/start_web.py --internal-monitor
```

El launcher construye la interfaz y arranca el servidor. Para usar una interfaz ya
construida y un PostgreSQL ya disponible:

```sh
npm --prefix frontend run build
.venv/bin/python -m decision_room.web --port 8787 --internal-monitor
```

El servidor reclama el puerto antes de migrar al esquema 25. Elegir otro puerto
si está ocupado; no migrar debajo de un worker antiguo sobre la misma base.

- Cliente: `http://127.0.0.1:8787/`. El chat, onboarding y análisis muestran una
  línea desplegable; el informe terminado conserva «Ver proceso» y datos relacionados.
- Operador: `http://127.0.0.1:8787/#internal/investigations`. Introducir la clave
  interna desde el archivo `.internal-access-key` del almacenamiento configurado.
  Es independiente de `.web-access-key`; ambos archivos tienen permisos `0600`.
- El flag solo habilita las consultas internas. La captura y el historial del
  cliente siguen funcionando sin él. Monitor desactivado: API interna devuelve 404.
- La cookie interna es `HttpOnly`, `SameSite=Strict`, path `/api/internal`, duración
  de navegador de ocho horas. No se guarda la clave en URL ni almacenamiento JS.
  El servidor actual sirve exclusivamente HTTP en loopback; no es un despliegue HTTPS.

## Qué se guarda y dónde

| Archivo | Responsabilidad |
|---|---|
| `decision_room/schema.sql` | Migración 25: raíces, vínculos, tareas y eventos. |
| `observability/store.py` | Secuencia bajo bloqueo de la raíz, UUID estables, deduplicación y savepoints. |
| `observability/runtime.py` | Contexto de proceso, sampler del worker, heartbeat, reutilizaciones, intentos HTTP y mantenimiento. |
| `observability/collector.py` | Proyección de registros analíticos reales a tareas y transiciones; sin llamadas al modelo. |
| `observability/projection.py` | Snapshots consistentes de solo lectura, estados y páginas públicas/internas. |
| `web/activity.py` | Alcance del negocio seleccionado y del job/turno. |
| `web/internal_monitor.py` | Listado del espacio configurado, recursos y detalles acotados bajo demanda. |
| `web/server.py` | Autorización interna independiente y controles de origen/host. |
| `frontend/src/lib/activity.ts` | Una suscripción por audiencia/proceso, polling incremental y recuperación. |
| `workspace/analysis-activity.tsx` | Línea, historial de tareas, enlaces a preguntas y datos. |
| `workspace/internal-monitor.tsx` | Lista, filtros, mapa de participantes, cronología y detalles. |

Las rutas de la tabla son relativas a `decision_room/` o `frontend/src/components/`
según el prefijo. No se incorpora un servicio externo de telemetría.

La identidad sigue turno → job → sesiones sucesoras → investigaciones → ramas →
revisión. Los subanalistas conservan sus identidades reales y el contexto se copia
al hilo de cada rama. Un cálculo importado al padre mantiene su ID único.

El contador de secuencia se incrementa en la misma transacción que el evento y la
proyección de tarea. Un productor concurrente espera al commit del anterior: un
cursor no adelanta a un evento que todavía no se ha confirmado. El fallo del
escritor revierte su savepoint y señala `history_complete=false`; el trabajo
analítico permanece válido. Un fallo externo del sampler/intentos también intenta
marcar esa señal. Una caída completa de PostgreSQL puede impedir registrar la señal.

Los inicios se registran antes de esperar al proveedor o al sandbox. El sampler
pertenece al worker, consulta cada segundo y confirma heartbeat. A los 15 segundos
sin heartbeat vivo se muestra una interrupción por confirmar; no se fabrica un
fallo analítico. El arranque ejecuta un mantenimiento explícito, reconstruye los
registros disponibles y etiqueta esos eventos. Ningún GET ejecuta este mantenimiento.

## API y paginación

```text
GET /api/jobs/<job_id>/activity
GET /api/chats/<chat_id>/turns/<turn_id>/activity
POST /api/internal/login                   {token: ...}
POST /api/internal/logout
GET /api/internal/session
GET /api/internal/investigations           business_id/status/offset/limit
GET /api/internal/investigations/<trace_id>
GET /api/internal/investigations/<trace_id>/events
GET /api/internal/investigations/<trace_id>/tasks/<task_id>
GET /api/internal/investigations/<trace_id>/calls/<call_id>
GET /api/internal/investigations/<trace_id>/executions/<execution_id>
```

Las páginas aceptan `after=<trace>:<sequence>` o `before=<trace>:<sequence>`, nunca
ambos; límite por defecto 100, máximo 200. La primera página devuelve los eventos
más recientes. `previous_cursor` recupera anteriores; `next_cursor` avanza por la
última secuencia inspeccionada, incluyendo eventos ocultos en la proyección pública.
`task_updates` representa el estado actual de las tareas de esa página; `active_tasks`
aporta tareas activas aunque su inicio esté fuera de ella. No confundir el estado
actual de una tarea con el estado de un evento histórico.

El detalle interno admite `event_id=<uuid>`: valida proceso y tarea y devuelve
`selected_event` aunque quede fuera de los últimos 20 eventos de la tarea. El
estado actual, evento seleccionado e historial reciente son campos distintos.

El cliente recibe un contrato explícito: estado, titular, tareas, referencias
pequeñas, fechas, cursores y salud de captura/worker. No recibe prompts, código,
mensajes internos, candidatos ni payloads diagnósticos. El operador autorizado abre
entradas seleccionadas y salidas estructuradas bajo demanda. Se eliminan credenciales,
cabeceras, cookies, DSN, URLs, rutas personales y campos de razonamiento privado.
El detalle limita profundidad, listas, cadenas y bytes, con señal de truncamiento.

La lectura del estado consulta aprobación, hold, correcciones y vigencia. También
comprueba existencia de código y tablas preparadas para una entrega completada;
la integridad completa y publicación siguen perteneciendo al endpoint de informe.
Abrir actividad no materializa un informe ni dispara DuckDB o llamadas al modelo.

El polling compartido se ejecuta cada dos segundos; espera de cliente y pestaña
oculta usan cinco segundos. Se drenan páginas nuevas, se deduplican IDs y se ignoran
respuestas abortadas. Al terminar se detiene el polling rápido; foco, apertura o
Actualización hacen una nueva lectura. Un 401/403 elimina datos diagnósticos de la UI.

## Recursos y límites de interpretación

- Llamadas lógicas: registros reales únicos; los intentos HTTP se obtienen de su
  metadata o de tareas de transporte para esa misma llamada. La ausencia de registro
  se muestra como desconocida, no como una sola petición supuesta.
- Tokens conocidos se separan de llamadas con uso desconocido. No se calcula coste
  monetario sin una tarifa configurada y atribuible.
- Tiempo del proceso: raíz hasta el final confirmado de job/turno; la reconstrucción
  posterior no alarga la ejecución. Las esperas concurrentes se unen, no se suman.
- Actores: participantes lógicos y ramas reales; las tarjetas y relaciones proceden
  de tareas. No representan cada petición HTTP como un nuevo agente.
- Sin eventos previos: mostrar historial no disponible o reconstruido. No inventar
  una secuencia exacta de acciones históricas ni reproducir razonamiento privado.

Estas vistas hacen el proceso inspeccionable; no certifican utilidad ni calidad
analítica. La aceptación de calidad pendiente de 3.7 se mantiene abierta.
