# Plan de implementación del motor de agentes (v3)

Fecha: 2026-10-06. Plan v3 redactado por Claude y revisado por Codex.
Versión pública del plan acordado; la implementación y sus comprobaciones se
registran por paso sin convertir propuestas en capacidades ya terminadas.

Las citas `archivo:línea` están comprobadas en la revisión indicada (por defecto
`c6bda76`). Las de OpenCode remiten a la copia de la versión 1.18.34 del spike.
Lo marcado **propuesta** todavía no existe. Los umbrales son **hipótesis piloto**
fijadas antes de medir; no se ajustan después de ver resultados.

El propietario autorizó la implementación local: rama `codex/agent-engine`,
merge local de la rama de ensayos y commits por paso comprobado. No están
autorizados push, PR, merge a `master` ni borrado de ramas. Los pasos siguientes
son criterios de trabajo; su cierre requiere evidencia de ejecución.

## 0. Punto de partida (ya decidido, no se reabre)

- Un agente principal en bucle (OpenCode 1.18.34, sin fork) investiga y redacta.
- Herramientas deterministas del producto como servidores MCP en Python.
- Verificación al final: corrige o marca y nunca elimina el informe por un fallo
  analítico.
- La cadena LangGraph queda congelada **en `c6bda76`**, sin contratos nuevos. `master`
  (`afc37fe`) no es la misma línea base: los ensayos y la vuelta atrás nombran las
  dos.

## 1. Decisiones de arquitectura

### 1.1 Entrega: opción (a), JSON por herramienta MCP

- **`entregar_informe(request_key, draft_json: string)`**, con un límite inicial
  de 256 KiB.
  - El servidor autentica, guarda bytes + hash y confirma la recepción **antes**
    de parsear o validar, así que conserva incluso un JSON malformado.
  - Un reintento idéntico da la misma versión; un contenido distinto exige una
    clave nueva.
- **Esquema v1 mínimo** (`decision_room/reports/contract.py`, propuesta):
  - obligatorios: `schema_version`, `title`, `summary` y
    `findings[] {key, title, statement}`, que puede estar vacío;
  - opcionales: `scope`, `interpretation` y `next_step` por hallazgo,
    `limitations`, `numbers` y `charts`;
  - el servidor completa los campos vacíos sin inventar hechos.
- **Cifras.** `numbers[] {key, execution_id, metric | series+selector, unit, decimals}`.
  La prosa **puede** usar referencias `{{n:key}}`. Son opcionales: sirven para
  renderizar y corregir, nunca son una obligación narrativa ni un motivo para
  perder el informe. Los valores se resuelven en el servidor. Una referencia prueba
  trazabilidad. «Verificado» exige además una comprobación que corresponda al
  cálculo y a su alcance.
- **Verificación final** (`decision_room/reports/verification.py`, propuesta):
  - Resuelve las referencias contra ejecuciones `completed` del mismo negocio,
    análisis y snapshot.
  - Comprueba operación, filtros, periodo, unidades y denominadores cuando hay una
    receta determinista.
  - Corrige solo los valores recalculables sin ambigüedad y guarda el antes, el
    después y el motivo.
  - Una cifra literal, una referencia rota o una ambigua lleva una **marca visible
    por bloque o cifra**. Nunca se presenta como KPI verificado y las inciertas se
    cuentan aparte.
  - Un error de formato da una salida textual escapada recuperable.
- **«Nunca rechaza»** significa que nunca elimina el informe por un fallo
  analítico. La autenticación, el tamaño y el aislamiento siguen siendo límites. Se
  persisten también los mensajes parciales para recuperar cortes del motor, pero no
  se promete un informe si nunca se generó contenido.
- **Advertencias comprobadas:**
  - `execute` produce candidatas «never analytically approved»
    (`execution.py:51`) con `verification=pending` (`execution_contract.py:69`).
  - Que una cifra coincida con un cálculo del propio agente no prueba su exactitud
    semántica.
  - «0 cifras erróneas» es una métrica de auditoría, no una garantía del
    verificador.
- **Por qué no se reutiliza la vista tal cual:**
  - `_projection` exige `publishable` + `approved`, `ReportDraft.model_validate` y
    todos los `checks` (`web/dashboard.py:24-34`). Se separa la proyección visual
    de la aprobación legacy.
  - `agent_reviews` exige `session_id`/`research_id` de la cadena
    (`schema.sql:205-212`).
  - `report_presentation_revisions` apunta a `agent_reviews`
    (`schema.sql:816-818`).
  - `read_lock` exige `agent_sessions` (`web/report_access.py:8-16`).
  - No se fabrican revisiones legacy ficticias.
- **UI v1 (paso 4):**
  - lectura, fuentes, métricas y operaciones;
  - gráficos de línea, barras y tabla;
  - editor de títulos, unidades y decimales, y PDF, todo mediante una proyección
    neutral hacia el `Report` de `frontend/src/lib/types.ts:170-203`;
  - estado de verificación visible: hoy React muestra «Revisado» fijo
    (`report.tsx:1106`) y el PDF oculta lo parcial (`report_pdf.py:203`).
- **Fuera de v1:** HTML libre, maquetación arbitraria, edición analítica por chat y
  referencias conversacionales a informes nuevos.

### 1.2 Despliegue del motor

- **Un contenedor por trabajo**, con `opencode serve` dentro, conducido por un
  cliente HTTP Python (crear sesión, `prompt_async`, SSE, abortar, exportar).
  - Siempre con `OPENCODE_SERVER_PASSWORD`: sin ella el servidor queda abierto
    (`serve.ts:15-16`).
  - El contenedor por negocio para el chat es una decisión futura: persistir una
    sesión por negocio no requiere un contenedor permanente.
- **Estado.** Copia **consistente** del SQLite de OpenCode en cada checkpoint, con
  restauración comprobada.
  - Exportar el JSON de la sesión no equivale a copiar el SQLite.
  - El spike de reanudación (02b) no prueba por sí solo la recuperación de caídas.
- **Proxy de modelo por host**, como servicio del producto, con una credencial por
  trabajo y topes configurables. Hipótesis iniciales:
  - 3 M tokens de entrada, 60 llamadas y 20 min de actividad (medido en Albor:
    0,84-1,59 M, 19-27 llamadas, 3-5 min);
  - 64 k de salida acumulada y 8 k por solicitud;
  - **reserva** antes de admitir peticiones concurrentes, porque el uso llega tarde;
  - el presupuesto incluye la llamada del título, la compactación y los subagentes.
- **Espera del propietario.** `waiting` vence aparte, a los 7 días. Al vencer se
  conserva el parcial y se permite una reanudación explícita, sin gasto automático.
  Los pasos 1 y 2 pueden revisar estos topes antes del paso 3.
- **Pasarela MCP HTTP del producto** en la misma red interna. La red admite el proxy
  y la pasarela, nada más. `execute` necesita BD, storage y Docker
  (`execution.py:73-87,130-167`; `docker_backend.py:25-42`): ejecutarlo dentro del
  contenedor del agente rompería el aislamiento.
- **Configuración base:**
  - compactación por debajo de 272 k;
  - `OPENCODE_DISABLE_MODELS_FETCH=1`, `share: disabled`, `autoupdate: false`;
  - `read` limitado para CSV grandes;
  - versión fijada.
- **Título de la sesión.** `--title` es una opción de `run`; `serve` solo declara
  opciones de red (`serve.ts:7-8`). El título se fija en la API de sesión
  (`UpdatePayload.title`, `routes/instance/httpapi/groups/session.ts:50`;
  `handlers/session.ts:188`). El paso 2 comprueba que así se evita la llamada
  oculta de título.

### 1.3 Acceso a datos

- **Doble vía.** Snapshot de los CSV de solo lectura en el volumen del trabajo, con
  manifiesto de hashes y correspondencia con las tablas preparadas, **más** la
  herramienta `consulta`.
  - El ensayo ganador usó CSV + panorama (`autopsy-and-trials.md:768-781` en
    `86d2679`).
  - Los CSV no se retiran sin medir CSV+MCP frente a solo MCP.
- **Qué cuenta como verificado.** Los cálculos locales del agente orientan. Una
  cifra publicada como verificada necesita una referencia recalculada y persistida
  por `consulta` o `panorama`.
- **`consulta`:**
  - envuelve `execute` conservando `request_key` y `execution_id`;
  - oculta rutas y archivos de transporte;
  - ayuda a construir el `result.json` rígido
    (`execution_contract.py:29-69,118-121`) sin añadir obligaciones narrativas a la
    investigación.
- **Credencial revocable por trabajo.** Fija `business_id`, `analysis_id`, tablas y
  snapshot, y el servidor rechaza todo lo que salga de ese alcance. Hoy `execute`
  solo acota negocio, análisis y tablas (`execution.py:75-83`); no autentica el
  trabajo (`:53-55`).
- **Límites por respuesta MCP** (propuesta):
  - 64 KiB UTF-8, 100 filas, 32 columnas y celdas de hasta 512 caracteres;
  - campos `truncated`, `total_rows` y cursor explícitos;
  - el resultado íntegro queda en storage, paginable con autorización, y la
    verificación usa el íntegro.
- **Máximos existentes que se mantienen:**
  - código de 128 KiB, 64 tablas, timeout de 30 s por defecto y 120 s como máximo
    (`execution.py:59-70`);
  - sandbox con 512 MiB de entradas, 2 MiB por archivo, 4 MiB de artefactos y
    64 KiB de logs (`docker_backend.py:14-18`).

### 1.4 Preguntas al propietario a mitad de trabajo

- **Herramienta MCP `preguntar_propietario(request_key, text, reason, options)`.**
  - Una transacción de PostgreSQL guarda la pregunta, la referencia al último
    checkpoint confirmado y el estado «pausando».
  - Detener el turno, hacer la copia del SQLite y pasar a `waiting` es una
    transición recuperable aparte: SQLite y PostgreSQL no comparten transacción.
  - Devuelve `question_id`/`pending` y no mantiene HTTP abierto.
- **Durante `waiting`,** el proxy y la pasarela deniegan las operaciones costosas y
  las entregas tardías; no se confía en el prompt.
- **Se reutiliza el flujo de respuesta existente,**
  `reply`/`web_replies`/`pending_answer` (`web/service.py:650-679`), con una fase
  nueva `engine`. Hay que ampliar el CHECK de fases (`schema.sql:284`). Las
  respuestas «no sé» o rechazadas también reanudan, con una limitación.
- **Reanudación sin duplicados:**
  - outbox duradero por `question_id`/`request_key`;
  - reconciliar con la sesión antes de reenviar;
  - limpiar `pending_answer` solo tras confirmación;
  - restaurar la sesión persistida, sin reiniciar el análisis;
  - una recepción tardía nunca sobrescribe el borrador ni contamina otro turno.
- **`question: deny`** (`config/opencode.json:21` del spike; auto-rechazo en modo
  headless, `run.ts:430-448`) afecta a la herramienta nativa. La herramienta MCP
  tiene nombre y permiso propios.

### 1.5 Interruptor de modo y convivencia

- **`engine_kind`.**
  - `engine_kind = 'legacy' | 'opencode'`, con versión y configuración, se fija
    **al crear** cada trabajo; por defecto `legacy` hasta el paso 6.
  - Cambiar el valor por defecto no cambia los trabajos existentes.
  - Columnas nuevas `engine_run_id` y `report_document_id`; no se reutilizan
    `session_id` ni `review_id`.
- **Bifurcación** tras la ingesta lista o parcial (`web/service.py:857-861`),
  antes de la planificación (`:863`). Hay que proteger también la sincronización y
  el preludio legacy (`:799-824`: modelo, memoria, stale/replan).
- **Se reutiliza:**
  - `import_batch`/`resume`/`describe` y los hashes (`:829-859`);
  - la recuperación del sandbox (`:825-828`);
  - los perfiles deterministas (`data_knowledge/service.py:121-156`);
  - la memoria versionada.
- **`discover` no es determinista:** llama al modelo
  (`data_knowledge/discovery.py:88-115`). No se impone al motor nuevo.
- **Bifurcar solo `run_job` no basta.** Los informes nuevos quedarían fuera de la
  portada y de la recuperación. Hay que adaptar también:
  - listado, portada, detalle y sincronización (`web/service.py:423-450, 489-503,
    553-582, 710-728`);
  - la edición de presentación (`presentation_editing.py:217-242, 312-340`).
- **API única** (propuesta): `engine.run_report` / `engine.resume_report`, con
  eventos de preguntas, en `decision_room/engine/__init__.py`. La llaman `run_job`
  y el lanzador de ensayos. `trial_worker.py` no pasa por `run_job`: llama
  directamente a la investigación y a la revisión (`trial_worker.py:53-54, 68-69,
  85-86` en `86d2679`).

## 2. Ramas

| Rama | Qué se hace |
| --- | --- |
| `codex/report-quality-product` (`c6bda76`) | Base del trabajo nuevo y cadena legacy congelada. |
| `claude/report-quality-trials` (`86d2679`) | Se fusiona (merge, no cherry-pick) en la rama de trabajo. Único conflicto: `docs/product/Decision Room - Plan de implementacion.md`, donde se conservan ambas entradas. Los docs duplicados se fusionan sin conflicto (comprobado con `git merge-tree`). |
| **`codex/agent-engine`** (nueva) | `c6bda76` + merge de `86d2679`. Aquí se construye el motor. |
| `master` (`afc37fe`) | Sin cambios hasta el paso 6. Entonces recibe **una sola PR** (base revisada + motor), con aceptación y regresión del delta completo de `c6bda76` (189 archivos frente a `afc37fe`). |
| `feature/ui-ux-refinements` (`dcebd00`) | PR propia e independiente a `master`. Se fusiona sin conflictos con `c6bda76`. |
| `codex/report-quality-p1b` (`858ed5f`) | Se conserva congelada y excluida (`32ae3ac` + 1 commit). Archivarla o borrarla lo decide el propietario más adelante. |
| `feature/landing-onboarding` (`6a8a7c6`) | Intacta, fuera de este plan. |

Por qué no se hace una PR temprana a `master`: aunque todos los flags estén
apagados (`config.py:45-57`), `c6bda76` cambia el comportamiento por defecto:
- TPM de 200.000 (`agent/model.py:77`);
- comprobación del orden de filas en cada ejecución (`execution.py:178-183`);
- validación de la orientación (`agent/review_contract.py:356`);
- prompts y contratos fuera de flags.

## 3. Pasos

**Reparto:** Astra implementa el motor y el producto. Claude mide (lanzador, kits
ciegos, lectores, juez de señales) y es dueño de
`decision_room/evaluation/{trials,trial_worker,trial_kit}.py` y
`tests/test_trials.py`. Cada paso termina con un commit local, como pide
`AGENTS.md`. Push, PR y merge son acciones separadas que el propietario autoriza.

**Orden:** P0, P1 y P2 (P1 y P2 pueden avanzar en paralelo) → P3 (puerta) → P4 → P5
→ P6.

### Paso 0. Rama de trabajo

- **Qué:** crear `codex/agent-engine` desde `c6bda76` y fusionar `86d2679`.
  Enlazar los pasos nuevos desde el plan canónico sin dar por completados criterios
  antiguos abiertos (plan actual, 3.9, l. 669-674).
- **Quién:** Astra.
- **Hecho cuando:** la suite completa y `tests/test_trials.py` pasan, y hay un
  commit de merge con hash reportado.

**Estado P0:** completo; merge `c503129`, reparación de pruebas heredadas y
[validación completa](../validation/2026-10-06-engine-p0.md).

### Paso 1. Auditoría técnica de exactitud de `loop-panorama`

- **Qué:** recalcular los 12 informes: todas las cifras comparativas con sus
  denominadores y periodos, y las afirmaciones que sostienen prioridades.
- **Quién:** Claude prepara el manifiesto y el kit congelado
  (`kits/loop-panorama/tecnica`). Astra recalcula contra los snapshots con un
  método independiente.
- **Hecho cuando:**
  - existe un registro por cifra (cifra, esperado, fuente, severidad, límites) y
    la tasa de errores por informe y sistema;
  - el registro detallado está en un destino privado, fuera de Git, con un resumen
    público sin datos privados;
  - con eso se fija la línea base de exactitud de P3 y se revisan los topes del
    1.2.
- Los oráculos solo se usan en la evaluación.

### Paso 2. Servicio de motor

- **Qué:**
  - imagen, script de descarga de binarios con hash y plantilla de configuración,
    llevados al repo desde `.local/engine-spike/` (hoy fuera de Git;
    `trials.py:163` los invoca desde ahí);
  - ciclo de vida del contenedor por trabajo;
  - cliente de `opencode serve`;
  - proxy con topes y reservas;
  - pasarela MCP con credencial por trabajo y las herramientas `panorama`,
    `consulta`, `verify_numbers`, `entregar_informe` y `preguntar_propietario`;
  - persistencia propia (`engine_runs`, `engine_events` y revisiones de documento
    con IDs y hashes compatibles con el futuro `report_documents`);
  - verificación mínima y recuperación funcionando, no simuladas.
- **Archivos (propuesta):**
  - `engine/opencode/` (Dockerfile, descarga de binarios, plantilla
    `opencode.json`);
  - `decision_room/engine/__init__.py` (API `run_report`/`resume_report`);
  - `decision_room/engine/{client,container,proxy,gateway,store}.py`;
  - `decision_room/engine/tools/{panorama,consulta,verify_numbers,entregar_informe,preguntar_propietario}.py`;
  - `decision_room/reports/contract.py`;
  - tablas en `decision_room/schema.sql`;
  - `tests/test_engine_*.py`.
- **Quién:** Astra el motor. Claude, el sistema `engine` del lanzador, que llama a
  `engine.run_report`.
- **Hecho cuando:**
  - **Aislamiento:** las pruebas del spike (§3.1) están automatizadas: el canario
    no aparece, no hay DNS externo, otras rutas devuelven 403 y la clave no está
    en el entorno.
  - **Credenciales:** se rechazan la de otro trabajo del mismo negocio, la de otro
    negocio, un token revocado o caducado y un snapshot cambiado.
  - **Idempotencia:** la misma `request_key` con el mismo contenido devuelve la
    misma ejecución o versión sin repetirla; con contenido distinto se rechaza.
    Así opera ya `execute` (`execution.py:97-108`). Se prueban los dos casos.
  - **Topes:** superar cualquiera aborta el trabajo y conserva el borrador; las
    reservas impiden rebasarlos con peticiones concurrentes.
  - **Recuperación:** se prueba matando el contenedor, el controlador y el proxy;
    con un fallo de SSE y su reconexión; con una caída antes y otra después de
    persistir la entrega; con una petición admitida sin `usage` final; y con una
    copia corrupta. No se duplica ningún cálculo ni entrega y no se restauran
    cuotas. Los límites de la recuperación quedan registrados.
  - **Ejecución real:** el sistema `engine` completa 3 + 3 trabajos (Albor y
    Bruma), con la entrega persistida en bruto antes de validarse y el coste por
    trabajo registrado, incluidos título, compactación y subagentes.

### Paso 3. Habilidad de informe (puerta)

- **Qué:**
  - prompt propio del agente principal, herramientas y verificación final;
  - la función **pura** de proyección y el mismo renderizador que usará P4, aquí
    como exportador del lanzador (sin migrar UI, edición ni FK).
- **Archivos (propuesta):** `engine/opencode/prompts/informe.md`,
  `decision_room/reports/verification.py` y `decision_room/web/report_projection.py`.
  El exportador va en el lanzador.
- **Quién:** Astra implementa; Claude mide.
- **Diseño de la medida** (hipótesis piloto, fijada antes):
  - **Brazos:**
    - motor nuevo;
    - «agente en bucle + panorama» (controles congelados reejecutados);
    - cadena legacy `c6bda76`;
    - `afc37fe` solo como referencia de regresión técnica.
  - **Condiciones:**
    - ≥ 6 ejecuciones independientes por brazo y negocio;
    - mismos snapshots, encargo, modelo y presupuestos;
    - ≥ 2 lectores ciegos con asignación aleatoria y regla de empates fijada
      antes.
  - **Dos medidas separadas:**
    1. contenido con la presentación normalizada para todos los brazos;
    2. utilidad del artefacto final con su presentación real.
  - **Puntuación:** por cada ejecución emparejada, los lectores se agregan en
    victoria, empate o derrota (1 / 0,5 / 0).
  - Los puestos normalizados históricos (0,27 / 0,09) no se comparan con estas
    puntuaciones: son estadísticas distintas y se conservan como contexto.
- **Puerta:**
  - media ≥ 0,5 frente a «agente + panorama» y > 0,5 frente a `c6bda76`, **en cada
    negocio y en las dos medidas**;
  - juez de señales en Albor: media ≥ 11/3 puntos por informe (escala 0-10), umbral
    piloto derivado del lote previo, y S6 = 0;
  - 100 % de las cifras calculables que sostienen prioridades verificadas, y ≥ 95 %
    de las demás cifras calculables. El denominador lo clasifica un auditor
    independiente, no el agente. Las inciertas se muestran y se cuentan aparte;
  - 0 errores etiquetados como verificados. Se informan todos los errores, también
    los de las cifras literales marcadas;
  - 0 informes perdidos sobre todos los intentos, incluidos los fallidos. Un
    registro vacío no cuenta como informe entregado.
- Si la puerta falla, P4 no empieza.

### Paso 4. Integración en el producto

- **Qué:**
  - registro neutral (`report_documents`, `report_document_revisions`);
  - migración de la FK de `report_presentation_revisions`;
  - `report_access`;
  - listado, portada, detalle y sincronización;
  - proyección a la vista y estado de verificación en React y PDF;
  - `preguntar_propietario` con `waiting`;
  - `engine_kind` al crear el trabajo y bifurcación en `run_job`.
- **Archivos:** `decision_room/reports/store.py` (propuesta), `schema.sql`,
  `web/service.py`, `web/presentation_editing.py`, `web/report_access.py`,
  `web/dashboard.py`, `report_pdf.py`,
  `frontend/src/components/workspace/report.tsx` y `tests/test_report_documents.py`.
- **Quién:** Astra.
- **Hecho cuando:**
  - **Migración:** se prueba sobre una BD poblada con informes y revisiones de
    edición existentes, y después se crean informes legacy nuevos. Se conservan
    IDs, historial, aislamiento y `base_version`.
  - **Modos:** los dos funcionan tras reiniciar y tras cambiar el valor por
    defecto.
  - **Conservación:** una entrega inválida, una cifra mala o un corte quedan
    conservados.
  - **Edición y versiones:** siguen funcionando la edición, el PDF y las versiones
    antiguas, y retirar o corregir datos o memoria y borrar o restaurar un informe
    funciona en los dos modos.
  - **Acceso:** el acceso entre negocios se deniega.
  - **Espera:** `waiting` está probado con respuesta, «no sé», rechazo, respuesta
    tardía, duplicados, caídas antes y después del envío y carrera con una
    herramienta o entrega en vuelo.
  - **Recorrido:** un informe con `engine_kind=opencode` se recorre en la
    aplicación.

### Paso 5. Panorama ampliado

- **Qué:** patrón por día de la semana (S1) y picos producto × canal (S3).
- **Archivos:** `decision_room/sales_panorama.py` y sus tests.
- **Quién:** Astra implementa; Claude mide.
- **Hecho cuando:**
  - hay fixtures genéricos con positivos, negativos, huecos de cobertura y
    variaciones de columnas, sin condiciones específicas de Albor o Bruma en el
    producto;
  - el juez da S1 > 0 y S3 > 0 en informes del motor;
  - Bruma no tiene falsos positivos nuevos y el señuelo S6 sigue en 0.

### Paso 6. Negocio reservado, valores por defecto y PR única

- **Qué:**
  - negocio reservado (held-out) con señales y negativos propios, predefinidos
    antes de ejecutar;
  - la misma puerta de calidad y exactitud que P3, con los dos controles;
  - un solo uso confirmatorio, sin afinar nada contra su oráculo;
  - después, `engine_kind=opencode` por defecto y PR única a `master`.
- **Quién:** Claude construye y mide el negocio reservado; Astra prepara la PR.
- **Hecho cuando:**
  - se pasa la puerta del negocio reservado;
  - pasan la suite completa de backend y frontend y la regresión del delta
    integrado, incluidos los informes legacy y la migración sobre una BD poblada;
  - hay un commit local.
- Push, creación de la PR y aprobación o merge son pasos separados que autoriza el
  propietario.

### Paso 7. Después

- chat sobre una sesión persistente del motor;
- predicción con validación obligatoria;
- vigía proactivo;
- medir CSV+MCP frente a solo MCP antes de retirar los CSV.

Cada uno tendrá un plan propio.

## 4. Desacuerdos y decisiones abiertas

1. **PR temprana a `master`** (propuesta inicial de Claude) frente a **PR final
   única** (Astra). Resuelto a favor de Astra, con evidencia comprobada (§2).
2. **`p1b`.** Claude proponía etiquetarla y borrarla; Astra, conservarla congelada,
   porque borrarla no hace falta ni está autorizado. Queda conservada y la decisión
   es del propietario.
3. **Contenedor por negocio para el chat:** abierto (paso 7).
4. **Retirar los CSV del volumen:** abierto hasta medir CSV+MCP frente a solo MCP.

Coste acordado (no es un desacuerdo, pero el propietario debe conocerlo): la puerta
de P3 exige ≥ 6 ejecuciones × 3 brazos × 2 negocios = 36 ejecuciones y ≥ 2
lectores por negocio, frente a 3 por brazo hasta ahora. Este plan no inicia ni
autoriza ese gasto. Los umbrales son una puerta piloto; no afirman equivalencia
estadística.

## 5. Lo primero que hay que hacer (pasos futuros, no iniciados)

1. Astra: paso 0 (rama `codex/agent-engine`) y comprobar la suite.
2. Claude: congelar el kit de `loop-panorama`; Astra hace la auditoría (paso 1).
3. En paralelo, Astra empieza el paso 2 por el proxy con topes y reservas y por la
   pasarela con credencial por trabajo, que es lo que bloquea todo lo demás.
