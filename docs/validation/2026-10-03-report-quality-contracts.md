# Fase 1 — Contratos de calidad del informe

Fecha: 3 de octubre de 2026. Base `4815b68`.
Rama `codex/fix/report-quality-contracts`; implementación según el
[plan de fase 1](../technical/report-quality-contracts-plan.md).

## Cambios comprobables

- **Capas:** el esquema efectivo de analista y revisor ya admite el gráfico que
  aceptaban el validador y los renderizadores. Referencias de una misma unidad y
  grano, vigentes y presentes en el contexto. Admite capas con un punto y combinaciones
  superiores al límite de 366 puntos de un gráfico simple; el límite combinado de 800 puntos,
  las derivaciones y demás restricciones semánticas siguen en el validador.
  Las variantes escalares y de una sola serie no pueden llevar capas simultáneas.
- **Entrega:** `delivery_capabilities.report_exports` identifica al controlador,
  los formatos y el requisito de aprobación. `delivery_state` diferencia revisión,
  disponibilidad a petición y entrega no disponible. `review.show` deriva la
  disponibilidad de `publishable`, incluyendo obsolescencia, retención, huella y
  evidencia. No afirma que ya se haya generado un archivo ni que un navegador lo
  haya comprobado. Los prompts distinguen exportación y artefactos del cálculo;
  esta instrucción no garantiza por sí sola que el modelo redacte sin errores.
- **Errores:** `artifact_invalid_name`, `artifact_unsupported_type` y
  `artifact_duplicate_name` sustituyen el diagnóstico ambiguo. HTML no es un
  artefacto permitido; renombrarlo no resuelve el problema. El límite de un
  trabajador, de la investigación, de una investigación concreta, del rol revisor
  y de llamadas por fase/ámbito se comunica por separado. No se amplían presupuestos.
- **Etiquetas:** texto completo en las barras web, con ajuste de altura para cada
  categoría; se conservan los sufijos. PDF elimina el recorte a cuatro líneas y
  pagina con altura suficiente. HTML calcula el espacio de etiquetas largas.
- **Auditoría:** migración 30, columnas `effective_request` y `request_sha256` en
  `agent_calls`, `data_model_discoveries`, `chat_calls`, `chat_answer_reviews` y
  `memory_calls`. Se registra protocolo, endpoint relativo, corrección y cuerpo
  enviado. Incluye sistema, esquema efectivo, contexto, idioma y opciones del
  modelo; excluye cabeceras y credenciales. Los reintentos de validación conservan
  su propia petición, y una respuesta perdida no borra lo que se envió. La
  recuperación reutiliza la llamada guardada. Los registros antiguos o modelos
  simulados que no construyen una petición siguen con `null`, no con una
  reconstrucción supuesta. Las columnas permanecen en la base privada; no se
  añaden al informe público. No se incorpora razonamiento interno no proporcionado
  por el modelo. La selección opcional del panel de inicio queda fuera de este
  circuito de análisis y no adquiere un registro durable en esta fase.
- **Orden:** `runtime.row_order_check` registra política, huellas, estado y entorno
  de la segunda ejecución. Se invierte el orden físico de cada Parquet conservando
  columnas, tipos, nulos, duplicados y números de procedencia. Se usan copias en
  una nueva carpeta de montaje: modificar un archivo ya expuesto a la VM produjo
  lecturas obsoletas durante la prueba, y se corrigió con montajes separados.
  `row_order_dependent` rechaza cambios; `row_order_unverified` rechaza una segunda
  ejecución incompleta. No se publica evidencia ni artefactos del candidato
  rechazado. Se comparan todas las métricas y series guardadas, con equivalencia
  numérica decimal exacta y sin depender del orden de los puntos.

## Coste y límites para el lanzador

Un cálculo nuevo que completa su primera ejecución utiliza **dos contenedores
secuenciales**; no dos llamadas al modelo. Su duración incluye ambas ejecuciones
y la preparación de la permutación. El presupuesto de investigaciones sigue
contando la ejecución lógica; `limits.max_program_runs=2` y la traza distinguen
los programas realmente ejecutados. Un error anterior a la verificación solo
utiliza el primer contenedor. La huella incluye la nueva política y su código.

Una permutación no prueba invariancia universal ni verdad causal. No se comparan
el texto libre de las notas ni la ordenación de CSV auxiliares. La comparación
numérica exacta puede descubrir inestabilidad de sumas en coma flotante; para
importes deben utilizarse operaciones decimales reproducibles. No se certifica que
un mismo modelo elija la misma investigación si se cambia el orden de sus entradas.

No cambia la imagen del sandbox: cambian el controlador y las instrucciones.
Los informes aprobados históricos conservan su evidencia y su huella. Las nuevas
peticiones almacenadas aumentan el volumen privado de auditoría; no deben subirse
al repositorio público como fixtures.

## Validación

Entorno propio: worktree de contratos, PostgreSQL y socket exclusivos, almacenamiento
local y perfil Docker `report-contracts`. La imagen inmutable se copió sin modificar
el entorno de la línea base. Pruebas con claves retiradas y transporte HTTP real
bloqueado hacia proveedores; respuestas de modelo mediante `MockTransport` o
modelos de prueba. **Cero llamadas reales al modelo.**

Resultados:

- Batería Python completa inicial: **637 pruebas**, 636 pasan y una falla en
  el fixture de memoria. Pedía 2 GiB en una VM de 2 GiB: `malloc` devolvía
  `MemoryError` antes de activar el límite del contenedor. Se ajustó el fixture a
  1 GiB, todavía superior al límite de 768 MiB; se mantiene la exigencia de
  `resource_limit`. El comportamiento del producto no se relajó.
- Repetición final dirigida: **115 pruebas pasan**, incluyendo toda ejecución
  Docker, contratos, peticiones efectivas, esquemas, exportaciones, memoria y
  migraciones. Incluye las pruebas añadidas durante la regresión; la colección
  final contiene **642 pruebas**, no se volvió a ejecutar toda la colección.
- Último endurecimiento de la firma decimal: **5 pruebas de orden pasan**,
  incluyendo Docker real y exponentes grandes sin expandirlos en memoria.
- Frontend: **238 pruebas pasan** en 30 archivos. Compilación y lint completados;
  se conservan los avisos preexistentes de Fast Refresh y tamaño del bundle.
- `git diff --check`, revisión de cambios y de ficheros preparados: sin rutas
  personales, datos de clientes, credenciales ni artefactos generados. El secreto
  que aparece en la prueba de cabeceras es un literal sintético de test.

La verificación usa el sistema real de cálculo y PostgreSQL, pero no evalúa la
calidad de una nueva respuesta de Luna. Esa medición corresponde al lanzador de
Opus después de recibir esta revisión.

Pruebas nuevas cubren: esquema del proveedor frente al contrato runtime y tres
superficies; referencias obsoletas, mezclas de unidad/grano y formas incompatibles;
mensajes de artefactos y presupuestos; petición efectiva, corrección, idioma,
memoria, recuperación y respuesta perdida; registros de descubrimiento,
conversación, revisión de respuesta y corrección de memoria; valores estables,
precisión decimal, nulos, duplicados, procedencia y errores de la segunda pasada.
La prueba Docker reproduce un límite temporal incorrecto obtenido de la primera
fila, lo rechaza y acepta tanto `min/max` como ordenación explícita.

Comprobación de navegador con el componente real: categorías de prefijo común y
sufijos Marketplace/Tienda física/Web propia, caracteres anchos y Unicode, barras
simples y agrupadas, en escritorio y ancho móvil de 390 px. Se conserva el texto
completo y los nombres accesibles, dentro del área visible de sus ejes.

## Entrega a Opus

Instalar dependencias bloqueadas, aplicar migración habitual y ejecutar el mismo
lanzador contra esta revisión. `jsonschema` se añade para validar independientemente
el esquema productor. Mantener bases y almacenamiento separados de la referencia.
Los registros efectivos se consultan en las columnas indicadas de la base privada.

Bruma 3 + Albor 3 y controles quedan a cargo de Opus, después de congelar esta fase.
No hay nuevos informes reales ni resultados comparativos inventados. La aceptación
3.9.7 sigue abierta y el negocio reservado se diseñará al congelar candidatos.
