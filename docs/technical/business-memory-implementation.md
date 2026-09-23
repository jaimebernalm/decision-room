# Entrega 2.5: ejecución incremental en siete pasos

**Fecha:** 23 de septiembre de 2026.  
**Estado:** pasos 2.5.1–2.5.3 completados y comprobados; pasos 2.5.4–2.5.7 pendientes. Véase la [validación del primer paso](../validation/2026-09-23-business-identity-check.md).  
**Referencias:** [alcance y criterios del plan](<../product/Decision Room - Plan de implementacion.md#51-entrega-25-memoria-del-negocio-y-experiencia-cotidiana>) y [diagnóstico y diseño de memoria/UX](business-memory-plan.md).

## Cómo ejecutar este plan

Implementar un paso por vez en el orden indicado. Cada incremento de sus listas debe dejar el recorrido anterior utilizable y tener una comprobación concreta. Se puede guardar un incremento terminado en un commit propio; el paso completo requiere superar todas sus comprobaciones y guardar un commit local con su cierre. No crear commits de estados intermedios que no se hayan implementado ni marcar un paso completo por tener únicamente tablas o una pantalla.

Al terminar cada paso, registrar archivos modificados, comprobaciones y resultados, limitaciones, commit y siguiente incremento en un informe de validación de esa fecha dentro de `docs/validation/`. Actualizar el estado del plan principal. GitHub solo se actualiza cuando se solicite el push.

Mantener la aplicación local con un propietario, PostgreSQL y archivos privados. Las modificaciones de esquema se prueban en bases temporales o copias controladas; no usar los datos privados de trabajo como fixtures públicos. Conservar migraciones, identificadores y datos previos. Un fallo de migración o una incompatibilidad de checkpoint debe tener recuperación explícita, sin borrar el estado anterior.

| Paso | Depende de | Resultado que se podrá demostrar al cerrarlo |
|---|---|---|
| 2.5.1 | Recorrido web actual | Crear dos análisis del mismo negocio sin volver a describirlo |
| 2.5.2 | 2.5.1 | Guardar, corregir y retirar conocimiento persistente mediante el servicio y el onboarding |
| 2.5.3 | 2.5.2 | Otro análisis reutiliza ese conocimiento y una corrección afecta a las sesiones correspondientes |
| 2.5.4 | 2.5.3 | Conversar en una pantalla sencilla, reutilizar memoria y obtener respuestas comprobables |
| 2.5.5 | 2.5.4 | Consultar/editar «Mi negocio» y actualizar archivos desde el navegador |
| 2.5.6 | 2.5.5 | Entrar al dashboard, preguntar desde el prompt y navegar por chats e informes |
| 2.5.7 | 2.5.6 | Recorrido completo probado con modelo real, reinicios y escenarios difíciles |

Las comprobaciones acompañan a cada incremento. El paso 7 integra y amplía esas comprobaciones; no aplaza hasta el final las pruebas de memoria, corrección o aislamiento.

## 2.5.1. Un negocio persistente

**Resultado:** el perfil y el avance del onboarding tienen identidad propia. Crear otro trabajo ya no crea otra empresa.

**Incrementos, en orden:**

- [x] **A. Identidad y migración.** Definir y persistir la vinculación del espacio local con el negocio activo y su estado de onboarding. Añadir la migración compatible con registros actuales. Ante varios negocios históricos, exigir una selección explícita para continuar; conservar el acceso a sus registros sin fusionarlos.
- [x] **B. Servicio y acceso.** Separar operaciones de crear/recuperar negocio, actualizar el contexto inicial y crear un trabajo. Resolver el negocio desde el espacio autorizado y comprobarlo en listados, detalle, respuestas, reintentos, informes y descargas. Una petición de otro ámbito no puede ejecutarse por conocer su identificador.
- [x] **C. Formulario actual adaptado.** Guardar nombre/descripción y avance del onboarding antes de ejecutar el análisis. Los siguientes análisis usan el negocio existente; el objetivo de una pregunta permanece en el trabajo y no sustituye la descripción del negocio. Mantener los límites de carga actuales.
- [x] **D. Compatibilidad y demostración.** Adaptar las pruebas del recorrido web y demostrar un primer análisis, un segundo objetivo del mismo negocio y recuperación tras reiniciar. Distinguir identidad del lote e identidad del trabajo: un CSV repetido puede reutilizar datos sin impedir investigar una pregunta diferente.

**Zona de código:** [`schema.sql`](../../decision_room/schema.sql), [`database.py`](../../decision_room/database.py), [`service.py`](../../decision_room/service.py), [`web/service.py`](../../decision_room/web/service.py), [`web/server.py`](../../decision_room/web/server.py) y el formulario de [`app.js`](../../decision_room/web/static/app.js).

**Contrato que deja al paso 2:** un identificador estable de negocio, perfil recuperable, estado del onboarding y operaciones que comprueban el ámbito. Conservar los identificadores de trabajos, fuentes y evidencia previos.

**Comprobaciones de cierre:** migración vacía y con datos anteriores; migración repetida sin cambios duplicados; dos trabajos del mismo negocio; dos negocios aislados; reenvío idempotente; nombre coincidente sin fusión; negocio histórico y evidencia accesibles; reinicio durante onboarding; regresión de ingesta y web. Probar la recuperación ante una migración fallida antes de aplicarla al espacio de trabajo.

**Todavía pendiente:** memoria estructurada, chat y nueva navegación. El formulario actual basta para probar esta base.

## 2.5.2. Memoria versionada y corregible

**Cierre:** [implementación y validación](../validation/2026-09-23-memory-check.md); [contrato y guía del servicio](memory.md).

**Resultado:** el sistema puede mantener conocimiento del negocio independientemente de una sesión del agente.

**Incrementos, en orden:**

- [x] **A. Contrato y persistencia.** Definir hechos y revisiones con contenido, tipo, origen, ámbito, estado, fecha de registro y vigencia conocida o desconocida. Distinguir declaraciones, propuestas, dudas y referencias a resultados. Las revisiones anteriores permanecen identificables.
- [x] **B. Operaciones de mantenimiento.** Implementar proponer, confirmar/declarar, corregir, retirar, consultar vigentes e historial. Validar ámbito y revisión esperada; rechazar una sobrescritura concurrente y hacer idempotentes los reintentos. Una retirada registra también qué contenido de origen no debe volver a activar el recuerdo.
- [x] **C. Entrada desde onboarding y aclaraciones.** Conservar el texto original y extraer candidatos mediante un contrato estructurado del modelo. El servicio valida y decide la transición permitida. Declaraciones claras pueden guardarse; una inferencia o contradicción material queda pendiente. No convertir automáticamente respuestas antiguas en reglas generales.
- [x] **D. Recuperación de cambios pendientes.** Conservar la relación entre respuesta del cliente y actualización de memoria, aunque falle la extracción o la persistencia. Reintentar sin duplicar hechos ni respuestas; mostrar aviso de guardado solo tras completar la operación.

**Zona de código:** esquema; un módulo de dominio de memoria separado de la web; contratos/prompts y entrada del modelo en [`agent/model.py`](../../decision_room/agent/model.py); registro de respuestas en [`agent/service.py`](../../decision_room/agent/service.py) y [`agent/review.py`](../../decision_room/agent/review.py). Los nombres de los módulos nuevos se fijarán al implementar.

**Contrato que deja al paso 3:** consultar memoria aplicable y su revisión; cambios con identidad y alcance; referencias a su procedencia; resolución explícita de conflictos. No hacer que la lectura de memoria dependa de cargar checkpoints.

**Comprobaciones de cierre:** guardar y recuperar en otro proceso; corregir sin borrar el histórico; retirar sin reaparición desde el origen; definición de un archivo que no pasa a otro; fecha futura; hipótesis frente a declaración; «no lo tengo»; conflicto entre ediciones simultáneas; fallo entre respuesta y guardado; reintento idempotente. Añadir casos del modelo real para comprobar la extracción, además de pruebas controladas del servicio.

**Todavía pendiente:** reutilización automática en el agente y edición mediante «Mi negocio». La demostración de mantenimiento puede hacerse desde pruebas de integración y el onboarding existente.

## 2.5.3. Memoria utilizada por el agente y correcciones entre sesiones

**Cierre:** [implementación y validación](../validation/2026-09-23-context-check.md); [contrato de selección, herramientas y vigencia](context-retrieval.md).

**Resultado:** una segunda investigación utiliza información pertinente del negocio; una corrección invalida los resultados afectados aunque procedan de otra sesión.

**Decisión que debe aplicarse:** [RAG y relaciones entre datos, memoria e informes](business-memory-plan.md#41-rag-y-relaciones-entre-datos-memoria-e-informes). Recuperación dirigida por el agente con relaciones explícitas y búsqueda; los índices semánticos serán derivados y se incorporarán según evaluación, sin vectorizar cada fila ni sustituir los originales.

**Incrementos, en orden:**

- [x] **A. Selección y manifiesto de contexto.** Seleccionar perfil, hechos, dudas, fuentes y resultados según negocio, objetivo y periodo. Guardar identificadores/versiones utilizados, reglas de selección y límites. Preparar catálogo con descripciones/columnas/periodos/cobertura y relaciones entre recuerdos, fuentes, investigaciones e informes. Empezar con referencias, filtros y búsqueda textual; evaluar omisiones con preguntas reformuladas antes de exigir búsqueda vectorial.
- [x] **B. Integración con el recorrido actual.** Incorporar el manifiesto en planificación, investigación y revisión, manteniendo las mismas versiones relevantes. Mantener el contexto libre del objetivo actual separado de los hechos del negocio. Ofrecer herramientas acotadas para que el agente busque candidatos, inspeccione datos y abra antecedentes/evidencia; registrar cada ampliación del contexto. Registrar qué fuentes y definiciones respaldan cada resultado reutilizable.
- [x] **C. Propagación de cambios.** Extender la invalidación por sesión a dependencias entre sesiones. Distinguir corrección histórica, nuevo dato y cambio futuro; conservar resultados históricos válidos. Bloquear reutilización/publicación de los afectados hasta su revisión. Si no se conoce bien el alcance, ampliar la revisión.
- [x] **D. Carrera de publicación y recuperación.** Comprobar versiones al reanudar y justo antes de publicar; una corrección durante el cálculo no puede dejar publicada una respuesta obsoleta. Replanificar el trabajo afectado usando los mecanismos actuales y conservar la evidencia anterior.

**Zona de código:** [`agent/context.py`](../../decision_room/agent/context.py), [`agent/research_context.py`](../../decision_room/agent/research_context.py), [`agent/review_context.py`](../../decision_room/agent/review_context.py), [`agent/research.py`](../../decision_room/agent/research.py), [`agent/review.py`](../../decision_room/agent/review.py), el servicio de memoria y las consultas web de resultados publicables.

**Contrato que deja al paso 4:** selección de contexto reutilizable, manifiesto versionado y comprobación común de vigencia. La selección acepta contexto de la petición actual; el adaptador al historial de mensajes se conecta en el paso 4, cuando existan conversaciones. Este paso se demuestra con sesiones de análisis y no depende de un chat futuro.

**Comprobaciones de cierre:** dos sesiones reutilizan una aclaración sin repetirla; una corrección afecta a ambas; un cambio futuro conserva una revisión anterior válida; un cambio irrelevante no invalida todos los cálculos; un hecho retirado no aparece en resúmenes/contexto; historial amplio conserva las dudas materiales; otro negocio queda excluido; contenido recuperado no altera reglas del sistema. Probar una corrección durante ejecución y otra antes de reanudar un checkpoint. Repetir planificación, investigación y revisión existentes, más un caso real de reutilización/corrección.

**Comprobaciones adicionales de recuperación:** localizar una tabla por su descripción y abrir sus aclaraciones e informes relacionados; excluir antecedentes ajenos o incompatibles con el periodo; conservar dudas materiales pese al límite de contexto; distinguir evidencia numérica de comentarios; registrar las recuperaciones adicionales. Si se incorpora índice semántico, probar un resultado de índice obsoleto contra el original corregido/retirado. Registrar la decisión de incorporarlo o aplazarlo y la evaluación que la respalda.

**Todavía pendiente:** historial de chats y dashboard. La web actual debe seguir indicando correctamente los informes pendientes o retirados.

## 2.5.4. Conversaciones funcionales

**Resultado:** una pantalla sencilla permite escribir, recibir una respuesta con evidencia y continuar o abrir otro chat sin repetir el contexto.

**Incrementos, en orden:**

- [ ] **A. Persistencia de conversaciones y turnos.** Crear conversaciones vinculadas al negocio y mensajes con identidad, orden, estado y referencias. Persistir el envío antes de procesarlo. Garantizar orden dentro de cada conversación y recuperación tras recargar, sin exigir ejecución paralela de varios chats.
- [ ] **B. Primera conversación útil.** Añadir operaciones de crear/listar/abrir/enviar/reintentar y una vista básica en la web existente. Resolver explicaciones de evidencia vigente y aportaciones de contexto mediante los servicios de los pasos 2–3. Si todavía no se puede ejecutar una intención, mostrar su límite sin una respuesta ficticia.
- [ ] **C. Investigación desde un mensaje.** Conectar selección de un conjunto de datos existente, planificación, aclaraciones, cálculo y revisión. Reutilizar el trabajador durable y los servicios analíticos; separar el trabajo de chat de la obligación actual de subir un CSV. Persistir las referencias entre turno, investigación y resultado.
- [ ] **D. Respuesta breve e informe.** Definir contenido estructurado de respuesta y validación de afirmaciones, referencias y cifras. Las explicaciones que reutilizan evidencia no introducen cifras ni conclusiones nuevas sin comprobarlas. Añadir «Generar informe» como revisión vinculada al chat; no transformar automáticamente cada mensaje en un informe. Conectar el historial al selector del paso 3 mediante fragmentos con referencias a sus mensajes originales y contexto suficiente. Recuperar los mensajes pertinentes vinculados a datos, recuerdos o informes, sin cargar todo un chat por compartir una tabla ni crear una memoria paralela.

**Zona de código:** esquema; servicio/contratos de conversación nuevos; [`web/service.py`](../../decision_room/web/service.py) y [`web/server.py`](../../decision_room/web/server.py); adaptadores del agente y revisión; vista básica de conversación en [`app.js`](../../decision_room/web/static/app.js). Reutilizar el renderizado controlado y escapado; el modelo no genera HTML ejecutable.

**Contrato que deja al paso 5:** conversación durable con referencias a memoria, fuentes, análisis e informes; misma vía de mantenimiento de memoria para onboarding y chat; estado recuperable del turno.

**Comprobaciones de cierre:** explicación con evidencia; nueva pregunta calculada/revisada; falta de datos; declaración guardada y reutilizada en un segundo chat; chat antiguo con contexto vigente; corrección que afecta a una respuesta publicada; informe vinculado; doble envío; interrupción y reintento. Una petición incierta al proveedor conserva el tratamiento explícito existente. Verificar con modelo real al menos una explicación, una nueva investigación y una actualización de memoria entre chats.

**Comprobaciones adicionales de chats:** encontrar una aclaración anterior aunque se reformule la pregunta; recuperar el contexto que distinga una cita o hipótesis de una declaración; no mezclar conversaciones por similitud sin comprobar negocio y ámbito; impedir que un mensaje antiguo reactive información retirada.

**Todavía pendiente:** diseño definitivo de navegación y gestión completa de archivos desde la ficha. Usar fuentes ya aceptadas basta para cerrar este paso.

## 2.5.5. «Mi negocio» y datos reutilizables

**Resultado:** el cliente entiende qué recuerda la aplicación, puede corregirlo y aportar datos para nuevas consultas desde una página propia.

**Incrementos, en orden:**

- [ ] **A. Ficha consultable.** Añadir «Mi negocio» a la navegación actual y presentar Información, Datos y archivos, y Cambios. Separar hechos declarados, propuestas y dudas; mostrar origen y vigencia cuando sean relevantes. Los campos vacíos no bloquean el uso.
- [ ] **B. Edición y retirada.** Conectar edición, confirmación de propuestas, resolución de conflictos y retirada al servicio de memoria existente. Mostrar guardado, fallo o conflicto concurrente; permitir volver a consultar el estado persistido. No escribir directamente desde la pantalla en una copia independiente del perfil.
- [ ] **C. Alta de datos independiente de una pregunta.** Separar subir/preparar un CSV de generar un informe. Mostrar conjunto, versión, periodo y disponibilidad; reutilizarlo desde el chat. Un archivo repetido no duplica actividad. Si su relación con otra fuente no está clara, mantenerlo separado y solicitar selección antes del cálculo.
- [ ] **D. Sustitución y efectos visibles.** Permitir elegir una nueva versión o un conjunto separado, conservando originales e informes históricos. Propagar correcciones sobre fuentes mediante las dependencias del paso 3; distinguir datos recién cargados de resultados ya recalculados.

**Zona de código:** interfaz y rutas web; servicios de negocio/memoria; [`service.py`](../../decision_room/service.py) y referencias de fuentes en el esquema. Conservar la separación entre lotes importados e investigaciones; un mismo lote puede respaldar varias preguntas.

**Contrato que deja al paso 6:** datos y perfil editables, catálogo de fuentes con versiones/periodos, estado de vigencia y enlaces navegables a conversaciones e informes.

**Comprobaciones de cierre:** corregir desde ficha tiene el mismo efecto que desde chat; retirar evita reutilización; conflicto entre dos pestañas; archivos repetidos y solapados no se suman; nuevo archivo no altera la revisión anterior; fallo de carga conserva el resto. Comprobar visualmente origen, edición, errores y estados vacíos, además de ingesta y pruebas web.

**Todavía pendiente:** composición del dashboard. Excel, combinación general de tablas y conectores siguen fuera de 2.5.

## 2.5.6. Dashboard y navegación cotidiana

**Resultado:** onboarding y visitas posteriores tienen recorridos distintos; el cliente vuelve a su negocio, pregunta y encuentra su trabajo anterior.

**Incrementos, en orden:**

- [ ] **A. Estructura de navegación.** Componer Inicio, Informes, Mi negocio, Nueva conversación y chats recientes. Resolver destinos según estado del onboarding y permitir volver a trabajos en curso mediante enlaces estables. Mantener accesibles las vistas anteriores necesarias durante la transición.
- [ ] **B. Datos de Inicio y biblioteca de informes.** Preparar una lectura del servidor que selecciona una revisión publicable e identifica periodo/fuentes/estado. Reutilizar contenido y valores revisados para resumen, tarjetas y gráficos; permitir abrir detalle/evidencia o elegir otra revisión. Separar los estados de informe aprobado, histórico, pendiente y retirado.
- [ ] **C. Prompt y sugerencias.** Colocar el prompt inferior sin tapar contenido. Enviar crea una conversación mediante las operaciones del paso 4; navegar a ella conservando el mensaje. Añadir pocas preguntas sugeridas sustentadas por capacidades y datos presentes, y «Preguntar sobre esto» con referencia al hallazgo.
- [ ] **D. Estados y adaptación.** Resolver primer acceso, falta de datos, análisis en curso, datos nuevos sin informe, informe retirado y fallo recuperable. Comprobar escritorio, móvil y teclado; ajustar foco, desplazamiento, lectura de evidencia y persistencia de borradores.

**Zona de código:** composición de [`app.js`](../../decision_room/web/static/app.js), [`styles.css`](../../decision_room/web/static/styles.css), rutas/consultas web y componentes de informe existentes. Mantener la presentación de la aplicación separada del contenido que propone el modelo.

**Contrato que deja al paso 7:** recorrido cotidiano completo observable en el navegador. Una tarjeta y un informe comparten las mismas cifras y versiones; una corrección retira ambos del conjunto de resultados vigentes.

**Comprobaciones de cierre:** nuevo usuario frente a regreso; prompt crea exactamente un chat y conserva su mensaje; sugerencias abordables; continuidad al cambiar de pantalla; revisión seleccionada identificable; ausencia de mezcla entre periodos; tarjetas retiradas al invalidar el informe. Pruebas de rutas/estados, sintaxis JavaScript y verificación visual en escritorio/móvil, incluyendo teclado.

**Todavía pendiente:** aceptación integrada. No incorporar personalización libre de widgets, PDF o predicciones durante el rediseño.

## 2.5.7. Evaluación y cierre de la entrega

**Resultado:** evidencia reproducible de que memoria, conversaciones y web funcionan juntas dentro del alcance acordado.

**Incrementos, en orden:**

- [ ] **A. Matriz integrada.** Reunir los casos creados en los pasos anteriores y sus resultados de referencia; añadir secuencias entre chats, edición desde ficha y recuperación. Adaptar el ejecutor de evaluación al nuevo recorrido, con versiones, tiempos y consumo registrados.
- [ ] **B. Ejecución controlada y real.** Ejecutar pruebas de contratos/persistencia con modelos controlados, suite de regresión y conversaciones con el modelo real configurado. Para casos semánticos críticos, realizar tres repeticiones independientes como mínimo y conservar cada resultado; documentar el ajuste si el coste requiere cambiar esa cantidad antes de ejecutar la ronda.
- [ ] **C. Prueba completa del navegador.** Recorrer onboarding → Inicio → pregunta → dato nuevo → segundo chat → corrección en ficha → revisión del resultado → informe → reinicio. Comprobar también una interrupción real, dos pestañas y pantalla móvil. La comprobación técnica no sustituye la validación de utilidad con comercios del piloto.
- [ ] **D. Correcciones y aceptación.** Convertir los fallos en casos reproducibles, corregirlos y repetir los escenarios afectados. Registrar resultados por caso, fallos abiertos, límites y veredicto; cerrar 2.5 solo cuando se cumplan los criterios siguientes.

**Zona de código:** [`evaluation/runner.py`](../../decision_room/evaluation/runner.py), [`evaluation/cases.py`](../../decision_room/evaluation/cases.py), [`evaluation/assess.py`](../../decision_room/evaluation/assess.py), pruebas de los pasos anteriores y documentación de validación. Reutilizar pequeños fixtures públicos/ficticios con referencias independientes.

**Criterios de cierre:** todas las comprobaciones obligatorias del paso 2.5.7 del plan principal pasan; ningún caso evaluado mezcla negocios, reutiliza un hecho retirado como vigente, publica cifras sin evidencia o conserva como válida una aprobación afectada por una corrección. Los fallos materiales deben resolverse antes de aceptar. Registrar por separado límites de cobertura, exactitud, preguntas repetidas, latencia y consumo; no convertir una media satisfactoria en excusa para omitir un caso fallido.

**Próximo trabajo:** retomar entrega 3 con la nueva base. No dar por aceptada la generalización a formatos, negocios o capacidades todavía no evaluados.

## Verificación y registro de avance

Los comandos existentes se ejecutan desde la raíz del repositorio. Antes de las pruebas integradas, comprobar los requisitos locales de PostgreSQL y sandbox descritos en la [guía web](web.md). Utilizar bases y almacenamiento de prueba aislados. Los módulos de pruebas nuevos se añaden cuando exista la capacidad, evitando pruebas que solo repitan la implementación.

| Paso | Base de pruebas existente que se debe conservar | Cobertura nueva que se debe añadir |
|---|---|---|
| 2.5.1 | `test_ingestion.py`, `test_web.py` | Migración, negocio persistente y ámbito de todas las rutas |
| 2.5.2 | `test_agent.py`, `test_review.py` | Memoria, revisiones, extracción y cambios concurrentes |
| 2.5.3 | `test_agent.py`, `test_research.py`, `test_review.py`, `test_review_context.py` | Selección de contexto, dependencias entre sesiones y publicación concurrente |
| 2.5.4 | `test_web.py`, contratos del modelo y revisión | Turnos, recuperación, evidencia breve y memoria entre chats |
| 2.5.5 | `test_ingestion.py`, `test_web.py` | Edición del perfil, fuentes/versiones y sus efectos |
| 2.5.6 | `test_web.py`, `test_client_report.py`, `test_series.py` | Inicio, navegación, vigencia y estados visuales |
| 2.5.7 | Suite completa y evaluación analítica | Matriz integrada y recorrido real de principio a fin |

Para ejecutar un módulo existente o nuevo, sustituir el patrón por su nombre real, por ejemplo:

```sh
.venv/bin/python -m unittest discover -s tests -p 'test_web.py' -v
node --check decision_room/web/static/app.js
git diff --check
```

Al cerrar la integración de la entrega, ejecutar la suite completa:

```sh
.venv/bin/python -m unittest discover -s tests -v
```

Cada cierre indica qué comandos y casos reales se ejecutaron, sus resultados y qué quedó sin comprobar. Las pruebas escritas o planificadas no cuentan como pruebas pasadas. Si aparece una dependencia circular o hace falta mover trabajo entre pasos, actualizar este desglose y el plan principal antes de declarar un cierre.
