# Conversaciones funcionales · Paso 2.5.4

## Implementación

1. **Persistencia.** Esquema 12: `chat_conversations`, `chat_turns`, `chat_calls` y `chat_retrievals`. Cada turno conserva el mensaje original, la pregunta a la que responde, su orden, estado, respuesta estructurada, referencias y contexto entregado. El servidor confirma el envío después del commit; el trabajo ocurre en segundo plano. La clave de envío y el bloqueo de la conversación evitan duplicados y turnos simultáneos fuera de orden.
2. **Memoria compartida.** Los mensajes nuevos pasan por `memory.capture` y la extracción existente. Una respuesta a una aclaración analítica utiliza la captura del planificador/revisor, sin duplicarla. Las contradicciones aparecen con sus alternativas: el cliente elige explícitamente la corrección, con control de revisión. Una pregunta sobre un hecho no debe convertir ese hecho en un conflicto. No se crea una memoria independiente por chat.
3. **Selección de contexto.** El turno registra perfil, revisión de memoria, recuerdos aplicables, selección de fuentes, catálogo acotado y versiones de tablas. El modelo puede ampliar ese punto de partida usando el mismo servicio de recuperación del paso 2.5.3. Cada búsqueda guarda entrada, resultado y dependencias; se vuelven a comprobar después del proveedor y antes de publicar.
4. **Investigación.** El modelo puede seleccionar un lote existente del negocio, respetando una selección explícita del cliente. Se crea atómicamente un trabajo `web_jobs` con `origin=chat`, enlazado al turno; no exige subir otro CSV. El trabajador existente ejecuta planificación, aclaraciones, cálculo y revisión. El manifiesto del plan recibe las citas de continuación y sus dependencias; las aclaraciones de esa misma sesión no invalidan por sí solas su antecedente. Cada respuesta a una aclaración queda como nuevo turno ordenado y conserva la relación con el trabajo.
5. **Respuesta e informe.** El modelo consulta herramientas y redacta su respuesta con referencias del servidor. Un pase independiente comprueba su pertinencia y apoyo en esas fuentes antes de publicar. Las explicaciones abren los informes originales; los cálculos nuevos siguen pasando por investigación y revisión. Las plantillas previas solo se conservan para compatibilidad histórica. Véase el [diseño actualizado](autonomous-chat-plan.md). El informe completo se ofrece mediante una acción explícita. Consultar la respuesta o exportar el informe vuelve a comprobar vigencia, evidencia, aprobación y la versión exacta del informe citado.
6. **Antecedentes.** `search_chats` se incorpora al selector compartido, también disponible para los agentes analíticos. Busca con el índice híbrido existente (`kind=chat`) tras filtrar negocio y ámbito. Si aún no se ha seleccionado un conjunto, permite descubrir antecedentes del mismo negocio indicando expresamente su conjunto de origen; con un conjunto seleccionado excluye los de otros conjuntos. Devuelve el texto del propietario, la pregunta precedente, referencia al mensaje/conversación y una etiqueta de cita histórica. El agente puede citar ese fragmento en el chat; no lo convierte en un hecho declarado. Los resultados analíticos se recuperan abriendo su informe, no copiando afirmaciones de otra respuesta.
7. **Recuperación y pantalla.** Vista «Conversaciones» en la navegación existente, listado, creación, selección opcional de datos, mensajes, sugerencias, aclaraciones, conflictos, progreso, reintento e informe. El formulario conserva el borrador y la identidad de envío ante fallos de red/recarga. El refresco actualiza los mensajes sin reemplazar el campo mientras se escribe.

## Contratos y límites

- PostgreSQL es la autoridad. No se necesitan archivos Markdown para mantener chats o recuerdos; pgvector contiene solamente el índice derivado.
- Un turno guarda usuario y respuesta asociados; no hay generación parcial por streaming. Las llamadas completadas se reutilizan tras un reinicio; una llamada en vuelo/interrumpida requiere reintento explícito. Se conservan las respuestas de intentos anteriores en `response_history`, las llamadas/recuperaciones por intento y el contexto exacto de cada llamada.
- El agente empieza con memoria aplicable y un catálogo de hasta 20 tablas. Puede buscar más. Hasta 12 recuperaciones por intento; memoria inicial de 48 KB y contexto total de 200 KB. No se truncan silenciosamente dudas materiales.
- La primera versión aplica una regla conservadora a los fragmentos de chat: una revisión de memoria posterior impide recuperarlos automáticamente. El historial original permanece visible. Esto evita reintroducir declaraciones retiradas, aunque puede descartar antecedentes que no estaban afectados. Los informes mantienen la comprobación de dependencias y periodos del paso 2.5.3.
- La memoria declarada se muestra como declaración del cliente, no como evidencia calculada. Las hipótesis/citas mantienen su condición histórica. Una conversación sin datos puede consultar o aportar memoria y recibir una explicación de lo que falta.
- Se analizan conjuntos existentes de uno en uno; no se autoriza una combinación nueva de archivos mediante similitud. La gestión completa de archivos y recuerdos queda en 2.5.5 y el dashboard definitivo en 2.5.6.
- El adaptador de conversación usa contratos estructurados y texto escapado. Ninguna respuesta del modelo se interpreta como HTML ejecutable.

## HTTP

Se mantienen autenticación local, protección de origen y aislamiento por negocio activo.

| Operación | Ruta |
|---|---|
| Listar/crear | `GET/POST /api/chats` |
| Abrir | `GET /api/chats/{chat}` |
| Enviar mensaje/aclaración | `POST /api/chats/{chat}/messages` |
| Reintentar turno | `POST /api/chats/{chat}/retry` |
| Confirmar alternativa de memoria | `POST /api/chats/{chat}/resolve` |
| Solicitar informe vinculado | `POST /api/chats/{chat}/report` |
| Abrir informe vigente | `GET /api/chats/{chat}/report/{turno}` |

Las escrituras incluyen el negocio visto por el cliente; los mensajes y conversaciones incluyen una clave UUID de envío. Los errores de búsqueda por referencia inexistente/fuera de ámbito vuelven al agente como resultado acotado, sin exponer datos ajenos; una llamada incierta al proveedor no se repite automáticamente.

## Validación

```sh
.venv/bin/python -m unittest discover -s tests -v
node --check decision_room/web/static/app.js
.venv/bin/python scripts/evaluate_conversations.py --output .local/chat-evaluation-new-run
git diff --check
```

El evaluador real crea y elimina una base aislada y usa únicamente datos sintéticos. Comprueba memoria entre chats, cálculo con total conocido, explicación del resultado existente, informe vinculado, corrección y recuperación semántica de una hipótesis reformulada. Los registros detallados permanecen en almacenamiento local ignorado por Git.
