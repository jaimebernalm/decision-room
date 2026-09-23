# Memoria versionada · Paso 2.5.2

## Plan de implementación

1. Añadir esquema 9 con fuentes originales, trabajos de extracción, llamadas registradas, recuerdos y revisiones. Mantener PostgreSQL como autoridad; los archivos originales permanecen en almacenamiento privado. Markdown puede ser una exportación futura.
2. Implementar un servicio de dominio independiente de HTTP: proponer/declarar, confirmar, corregir, retirar, consultar e historial. Serializar cambios por negocio, comprobar revisión esperada e identidad de cada petición. Una corrección conserva el contenido anterior; una retirada bloquea reactivación automática.
3. Capturar el perfil y las nuevas aclaraciones del principal/revisor en la misma transacción que el texto original. Extraer mediante un contrato estructurado, con citas exactas y ámbito autorizado. No importar automáticamente respuestas históricas. Conservar el perfil actual de negocios web al migrar como fuente pendiente.
4. Procesar fuentes en segundo plano con estados persistidos. Guardar la respuesta del modelo antes de aplicar los candidatos; distinguir error recuperable de llamada incierta. Mostrar estado real y permitir reintentar desde la web.
5. Probar persistencia, aislamiento, fechas, conflictos, retirada, concurrencia, idempotencia, interrupciones, integración y extracción real. Registrar resultados antes de cerrar el paso.

## Límites

La memoria no se añade aún a planificación, investigación ni revisión: selección de contexto e invalidación entre sesiones corresponden a 2.5.3. El chat llegará en 2.5.4 y la ficha completa en 2.5.5. Las operaciones del dominio serán reutilizables por esos puntos de entrada. El texto de una respuesta y su efecto en el análisis actual conservan el recorrido existente.

## Contrato y almacenamiento

- `memory_sources`: texto original, pregunta, disposición de la respuesta, origen estable y ámbito. También mantiene el trabajo de extracción y su respuesta persistida. No se reescribe el original al reintentar.
- `memory_facts` y `memory_revisions`: identidad y revisiones inmutables por operación; contenido, tipo, estado, origen, cita y alternativas contradictorias. `memory_heads` serializa cambios y asigna la revisión global del negocio.
- `memory_commands`: clave idempotente, firma de petición y resultado. Repetir la misma petición devuelve su resultado; cambiarla conservando la clave se rechaza.
- `memory_calls`: modelo, versión del prompt, contexto enviado, respuesta, consumo, estado y tiempos de cada llamada. La información queda en PostgreSQL privado; no se publica en Git.

El contenido distingue `context`, `priority`, `definition`, `availability`, `open_question` y `result_reference`. Este último solo guarda una referencia a una revisión del mismo negocio; la extracción de texto no puede fabricar resultados. Su publicación y reutilización deben comprobarse en 2.5.3.

Ámbitos actuales: negocio, lote de análisis y fuente. Una aclaración sobre un lote de un único archivo queda ligada a esa fuente; si hay varias, al lote completo. No se amplía automáticamente a todos los archivos ni se asigna por nombre. Los futuros chats podrán llamar al mismo servicio con un ámbito resuelto por el servidor; todavía no hay ámbito de conversación persistido.

`temporal_scope` distingue fecha no indicada (`unspecified`), fecha conocida (`dated`) y restricción temporal sin resolver (`unresolved`). Las fechas son inclusivas. Una restricción ambigua queda como propuesta y exige corrección antes de confirmarse; no se inventa el año. La fecha de registro se conserva separada de la aplicación del hecho.

Estados: propuesto, declarado por el cliente, en conflicto, retirado y sustituido. El historial conserva el estado que tuvo cada revisión y añade `effective_status=superseded` para versiones anteriores. Declarado no significa comprobado externamente. Una hipótesis no desplaza un dato declarado; las contradicciones conservan las alternativas y requieren una corrección explícita. La agrupación por tema y la detección semántica dependen parcialmente del modelo: pueden requerir revisión humana.

## Operaciones del servicio

`decision_room.memory.service.change(config, business_id, ...)` acepta:

| Acción | Entrada y efecto |
|---|---|
| `propose` / `declare` | Contenido nuevo, texto original y clave de petición; no sustituyen un tema existente implícitamente |
| `confirm` | Identidad y revisión esperada; confirma una propuesta sin contradicción ni fecha ambigua |
| `correct` | Identidad, revisión esperada y contenido completo corregido; conserva el anterior y puede restaurar explícitamente un recuerdo retirado |
| `withdraw` | Identidad y revisión esperada; lo retira de consultas vigentes y conserva su historial |

`read` consulta el estado actual o el historial. `applicable_on`, `analysis_id` y `source_id` permiten comprobar fechas y ámbitos; no constituyen todavía el selector de contexto del agente. No se permite solicitar el historial como si fuera memoria vigente. Los adaptadores resuelven el negocio autorizado antes de llamar al dominio.

La retirada conserva una marca por tema, ámbito y periodo: una extracción automática posterior no reactiva ese recuerdo aunque reescriba la frase. Para restaurarlo hace falta una corrección explícita. La marca se conserva incluso tras esa restauración para impedir que vuelva a entrar contenido antiguo automáticamente. Retirar un recuerdo no elimina el texto ni los archivos originales.

## Incorporación y recuperación

El perfil y su fuente pendiente se guardan en una transacción. Lo mismo ocurre con cada nueva aclaración del principal o revisor: si falla el registro de memoria, la respuesta analítica tampoco queda guardada a medias; la respuesta web pendiente permite reintentar. Una respuesta ya existente anterior a la migración no se extrae por el mero hecho de reanudar su sesión.

El trabajador web atiende análisis y después fuentes pendientes de los negocios de su espacio. No procesa las fuentes de evaluaciones o negocios CLI ajenos al espacio. Para las aclaraciones conserva el proveedor/modelo de la sesión; para el perfil usa la configuración web. Sin modelo se conserva la cola. El dominio también permite procesar una fuente explícitamente, con el modelo suministrado por el llamador.

La extracción tiene un máximo de 20 candidatos por llamada y admite hasta 200 recuerdos actuales como contexto, incluyendo retirados y conflictos. Si se supera ese límite, falla de forma recuperable sin truncar recuerdos. Exige citas literales, referencias del mismo negocio y ámbito permitido. Definiciones de archivos sin archivo identificado no se convierten en reglas del negocio.

La respuesta del modelo se guarda antes de aplicar candidatos en una transacción. Si falla la aplicación, un reintento puede reutilizar esa respuesta validada; si cambió la memoria, debe volver a extraerla. Una respuesta obsoleta se descarta de la cola antes de otra llamada, conservándose en el historial de llamadas. Una interrupción durante la llamada queda incierta y necesita reintento explícito. Dos trabajadores no pueden procesar simultáneamente la misma fuente.

La web muestra pendiente, fallo, llamada incierta y procesamiento completado. `POST /api/memory/retry` recibe el identificador de negocio visto por la página y reintenta solo si coincide con el negocio activo, con la autenticación y comprobación de origen existentes. Las operaciones de mantenimiento se prueban mediante el servicio; la ficha para editar recuerdos llegará en 2.5.5.

## Migración y validación reproducible

El esquema 9 conserva el perfil actual de cada negocio web como fuente pendiente. No convierte automáticamente las respuestas históricas en recuerdos. La migración es transaccional y repetible, preserva informes y evidencia, y se aplica al arrancar la aplicación actualizada. Detener antes las instancias antiguas que utilicen esa base.

```sh
.venv/bin/python -m unittest discover -s tests -v
node --check decision_room/web/static/app.js
.venv/bin/python scripts/evaluate_memory.py --model gpt-6-luna --repetitions 3 --output .local/memory-evaluation-new-run
git diff --check
```

El ejecutor real utiliza ocho casos ficticios, una base temporal independiente y el proveedor configurado en `.env`. Conserva cada repetición y sus llamadas en el directorio indicado; requiere PostgreSQL y acceso al modelo, sin cargar datos privados de trabajo. Ver los [resultados y límites del cierre](../validation/2026-09-23-memory-check.md).
