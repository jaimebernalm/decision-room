# Contrato de interfaz de exportación del motor, versión 1

Interfaz propuesta por Astra y aceptada por Claude el 7 de octubre de 2026 para
coordinar implementación y medición. Claude declaró la adaptación de su
calculadora en `8394755`; esa declaración no sustituye una revisión de su código.
El validador puro `reports.verification_contract` fija y prueba el contrato;
no verifica cifras ni aprueba informes. La API y el exportador mínimo ya existen;
la verificación semántica y la presentación completa de P3 siguen pendientes.

## Identidad y correspondencia

`verification.json` contiene:

- `contract_version: 1`;
- `draft_sha256`: SHA-256 de los bytes exactos de `draft.raw`, incluso si son JSON inválido;
- `verified_sha256`: SHA-256 de la representación JSON canónica de `draft.verified.json`;
- `renderer_version`: versión explícita del renderizador;
- `figures`, `summary` e `issues`.

Cada figura contiene `id`, `path`, `span`, `text`, `value`, `unit`, `status`,
`verified`, `corrected_from`, `evidence` y `recommendation_id`.

`path` es un JSON Pointer RFC 6901 en el documento verificado. Apunta a un campo
string con el texto que se muestra. `span: {start, end}` usa índices de puntos de
código Unicode, inicio incluido y final excluido. `text` coincide exactamente con
esa parte del campo, antes de escapar HTML. `id` deriva de versión, hash del
verificado, path y span. Dos cifras iguales en un párrafo tienen spans distintos.
Un mismo contenido mostrado dos veces puede compartir referencia; el auditor
registra afirmaciones según su protocolo, no deduce independencia por repetición.

`value` y `corrected_from` son decimales representados como strings o null. `unit`
es string o null. La evidencia usa objetos `{kind: execution|observation, id,
metric?}`; un ID no demuestra por sí mismo verificación semántica.
`recommendation_id` es orientativo: no sustituye la clasificación independiente
`sostiene_prioridad_v3` del auditor.

## Corrección no equivale a verificación

`status` es `verified`, `unverified`, `uncertain` o `corrected`. `verified` es además
un booleano obligatorio. Un estado `verified` exige true; `unverified` y
`uncertain` exigen false. `corrected` puede tener cualquiera de los dos: corregir
un valor no certifica atribución, unidad o denominador en la prosa. Guarda siempre
antes y después. No se promueve automáticamente `verified_in_scope` de una
herramienta a verificación del uso de esa cifra en el informe.

`summary` cuenta exactamente los cuatro estados, sin solaparlos. La puerta de
exactitud usa cada figura y exige `verified=true` más el resultado correcto del
auditor; no se calcula a partir de estos contadores. Una cifra sin correspondencia
única cuenta como no verificada. No se elige arbitrariamente entre duplicados por
coincidir el valor. La validación estructural nunca precede a guardar el borrador
raw ni autoriza descartarlo si falla.

## Proyección y dos medidas

Firmas implementadas en `decision_room.web.report_projection`:

- `project(draft_verified: dict) -> dict`, pura;
- `render(projection: dict, *, marks=True) -> str`, HTML autocontenido sin red.

`export_run` escribe `informe.html` con `marks=True` e
`informe.contenido.html` con `marks=False`, ambos desde la misma proyección y
con la misma `renderer_version`. `marks=False` solo quita decoración y etiquetas
automáticas de verificación. Conserva cifras corregidas, texto y limitaciones
analíticas; no genera otra interpretación del informe. La medida de contenido
normaliza los tres brazos por igual. La medida de artefacto conserva las marcas y
reconoce que pueden revelar el brazo. El contrato de proyección debe reutilizarse
en P4; el renderizador presenta texto, bloques de evidencia y gráficos acotados.

## Auditor y coste

Conviene un auditor nuevo elegido por el propietario, con snapshots, informes e
instrucciones congeladas, sin código, claves de los brazos ni oráculos. Astra
implementa el motor y ya conoce la auditoría previa; Claude conoce las claves.
Este documento no crea otra conversación ni autoriza ensayos.

El proxy implementa `cost_catalog` y conserva los componentes observados de uso y
modalidad efectiva; los ausentes quedan como null (detalle al final). Según la [tarifa oficial consultada el
7 de octubre de 2026](https://developers.openai.com/api/docs/pricing), GPT-6 Luna
Standard cuesta, en USD por millón de tokens: entrada 0,10; lectura de caché 0,01;
escritura de caché 0,125; salida 0,50. Para solicitudes de más de 272.000 tokens de
entrada: 0,20 / 0,02 / 0,25 / 0,75 respectivamente. Fast aplica ×2 y el procesamiento
regional añade 10 % donde corresponde. Véase también la [ficha del modelo](https://developers.openai.com/api/docs/models/gpt-6-luna).

La estimación debe distinguir esos componentes por llamada y registrar fuente,
fecha, contexto y tier. Con componentes ausentes se comunica un intervalo con
supuestos, nunca coste cero ni exactitud ficticia. El proxy fija ahora
`service_tier="default"` (Standard) como política del servicio. Rechaza otros
valores antes del conteo y la generación; omitir el campo no hereda el tier del
proyecto. El [parámetro del proveedor](https://developers.openai.com/api/docs/guides/fast-mode)
distingue tier solicitado y efectivo; el catálogo conserva ambos sin inferir el efectivo del solicitado. Las pruebas
locales de esta implementación usan un proveedor simulado.

Con los topes de 3 M de entrada y 64 k de salida, 0,332 USD es el escenario de
contexto corto sin lecturas ni escrituras de caché, no el peor caso. A tarifa larga,
el escenario sin caché es 0,648 USD; si toda la entrada se cobra como escritura
larga, es 0,798 USD por trabajo (4,788 para seis; 9,576 para doce). Son escenarios
bajo esos supuestos de tarifas, no costes medidos ni límites absolutos de factura.
Los controles que no imponen topes tampoco tienen un máximo demostrado por su
consumo histórico. La autorización de ensayos debe usar un presupuesto explícito
con esas limitaciones.

## API mínima y recuperación (7 de octubre)

`engine.run_report(config, business_id, analysis_id, *, owner_context, request_key,
limits=None)`, `resume_report(config, business_id, engine_run_id, *, answer=None)`
y `export_run(config, business_id, engine_run_id, dest)` comparten el snapshot
`contract_version: 1`, `engine_run_id`, `status`, `question`, `document_id`,
`revision_id`, `usage`, `issues`. La pregunta usa `question_id`. Una respuesta
incluye `question_id`, `disposition`, `text`, `request_key`; la repetición exacta es
idempotente. Un negocio distinto se rechaza antes de crear archivos de exportación.

Run/resume devuelven tras entrega, espera, aborto o fallo. Una exportación durante
la ejecución conserva el estado real `running` o `pausing`, sin fabricar un estado
terminal. El exportador escribe primero `run.json`, el raw disponible, la sesión y
el registro de llamadas; después el documento, su ledger y ambos HTML. Si falla
el render conserva esos datos, registra `report_export_incomplete` y retira los
HTML antiguos de ese destino para que no parezcan la versión nueva. El registro
persistido es la fuente de recuperación, incluso si falla la escritura del destino.

Sin entrega formal, los textos de asistente ya observados se recuperan como raw,
con `draft_recovered_from_message_text`; no se fabrican IDs de documento/revisión.
Sin contenido generado no se promete un informe. El documento acepta texto, hallazgos y las extensiones acotadas descritas abajo;
formas desconocidas se conservan en una salida textual escapada. No implica integración con edición, PDF ni aprobación legacy.

## Evidencia acotada y gráficos (tramo A2)

El renderizador `report-evidence-v4` conserva el ledger versión 1. Un borrador puede
incluir `facts: [number_key, ...]` en la raíz o en cada hallazgo (hasta 32 por lista y 256 por informe).
Cada clave apunta a `numbers`. El documento verificado sustituye la lista por
objetos `{number_key, text}`; `text` contiene una frase completa con etiqueta,
valor, unidad, grupo, fechas y límites. El servidor genera esos campos a partir
del panorama o de `calculo` recién recalculados y del snapshot autorizado; el agente no puede
proporcionar ni reemplazar la etiqueta, el ámbito o la unidad del bloque.

La cifra principal de ese bloque puede tener `verified=true` solamente con una
receta compatible recalculada. El path es `/facts/N/text` o
`/findings/N/facts/M/text`, y el span identifica exclusivamente la cifra mostrada.
La atribución se limita a registros de esa tabla y columna: no certifica cobertura,
causas, unidad comercial confirmada ni la recomendación adyacente. Las correcciones
guardan el valor anterior. Nombres de origen que parezcan plantillas se conservan
literalmente. Otras cifras del texto, incluidas fechas, conservan sus marcas de
no verificación; el auditor decide cuáles son calculables.

La misma referencia usada en prosa libre sigue sin certificar su atribución.
Los cálculos Python del agente son trazables, pero no reciben certificación
independiente por haber terminado con éxito. Una receta ausente conserva la cifra
y señala el ámbito no comprobado. `marks=False` conserva toda la frase y sus
límites, quitando solo las marcas. Los hechos se sitúan junto a su hallazgo.

`charts` acepta hasta ocho gráficos `bar`, `line` o `table`, con título, leyenda de
serie y puntos `{label, number_key}`. Cada gráfico tiene de una a seis series, de
uno a cien puntos por serie, y el total del informe no supera 800 puntos. Se
resuelven los valores desde `numbers`; el agente no proporciona SVG ni geometría.
El path de una cifra es `/charts/N/series/M/points/K/value_text`. Las etiquetas
escritas por el agente no se certifican por asociarlas a una cifra recalculada.

La representación incluye siempre la tabla completa. Referencias sin resolver,
unidades distintas o categorías incompatibles conservan solo la tabla y su
limitación. Las barras y líneas comparten escala con origen cero, admiten negativos
y escapan texto. No hay scripts ni dependencias de red. No implica integración con
la edición o PDF del producto; eso pertenece a P4.

La extensión de panorama del motor añade variaciones porcentuales entre las
ventanas ya seleccionadas, variaciones de los grupos comparables devueltos y
porcentajes de producto/canal sobre el total. No cambia el calculador ni la cadena
legacy. Su versión y hash se guardan en la especificación de las observaciones,
la huella idempotente y las comprobaciones; una versión distinta no se recertifica.
El recálculo usa el mismo Parquet, mapeo, periodo y reglas de selección.

La sección `ratios` devuelve referencias normales de `numbers` para resultado y
operandos. Una base cero o negativa no produce porcentaje. Una parte negativa o
mayor que el total tampoco se interpreta como cuota. La fórmula usa decimales y
se almacena con doce decimales como máximo antes del formato de presentación.
Los bloques facts muestran ambos operandos y su unidad, además del porcentaje,
fechas y fórmula; cada número generado tiene un span y evidencia propios dentro
del mismo campo. Esos operandos son recalculados, no texto aportado por el agente.
No hay ajuste automático por duración desigual, cobertura o estacionalidad.

**A2 sigue incompleto:** no hay recetas independientes para consultas arbitrarias
ni selectores de series. Tampoco se ha demostrado la cobertura exigida
por el auditor ni la utilidad ante lectores. Este tramo no congela el motor para
P3 ni da por cumplida su puerta.

`proxy-calls.jsonl` incluye por llamada `billing` (modelo/modalidad solicitados y
observados, entrada, salida, caché leída/escrita) y `cost_catalog`. Los recibos SSE
terminales se guardan incluso si se desconecta después el consumidor. Campos ausentes
son null; no se deducen de la modalidad solicitada ni se convierten en cero. Las
reservas inciertas permanecen cargadas. El catálogo público Standard se versiona;
`cost` es null si faltan componentes o el modelo/modalidad no tienen tarifa admitida.
El agregado publica `known_cost` y `unpriced_calls`; tampoco presenta el subtotal
conocido como coste total. Es una estimación sin precios regionales o negociados,
no una factura ni un tope monetario automático. El conteo previo conserva su tiempo
por separado (`count_seconds`).

La fórmula separa entrada ordinaria, lectura y escritura de caché, según la
[documentación de caché](https://developers.openai.com/api/docs/guides/prompt-caching).
Los precios de referencia son los del [modelo](https://developers.openai.com/api/docs/models/gpt-6-luna)
y la [tabla pública](https://developers.openai.com/api/docs/pricing).

## Diagnóstico del controlador

Los eventos `controller_issue` conservan el código existente y, cuando hay una
excepción, añaden `stage`, `exception_type`, `reason`, `message` y opcionalmente
`http_status`. El snapshot y `run.json` los exponen en la lista aditiva
`diagnostics`; `issues` sigue siendo una lista de códigos. Las etapas distinguen
la conexión MCP, lectura de estado, carga/encolado del prompt, observación y
checkpoint. La etapa identifica la operación que estaba activa, no prueba por sí
sola su causa externa.

Los mensajes conocidos se traducen mediante un catálogo de constantes; un mensaje
arbitrario se sustituye por una explicación genérica. No se serializan traceback,
rutas, URL, argumentos o cadenas de causas. Los errores de cierre se registran
separados y no impiden intentar detener el resto de recursos. Un fallo previo al
primer prompt queda registrado como fallo sin contenido; nunca se fabrica un
informe para satisfacer una métrica ni se oculta con el éxito de otro intento.


## Agregaciones acotadas (A2)

`calculo(table_id, request_key, recipes, cursor?)` admite 1–32 recetas sobre una
única tabla autorizada. Cada receta tiene `key`, `operation` (`count`, `sum`,
`mean`, `min`, `max`), `column` (null para contar filas) y `filters`. Un filtro
contiene `column`, `operator` (`in` o `date_between`) y `values`. `in` compara
strings exactos; los dos extremos de fecha son ISO canónicos, inclusivos. Los
filtros se combinan por Y. No acepta SQL, código Python, uniones, deduplicación,
conversiones de moneda ni unidades comerciales propuestas por el agente.

El servidor lee Parquet y acumula con Decimal; admite valores finitos con hasta
26 dígitos enteros y 12 decimales. Redondea el resultado a 12 decimales. Los nulos
numéricos se excluyen; se muestran filas seleccionadas y registros no nulos. La
media muestra además el numerador y declara que su denominador son registros,
no días. Una selección numérica vacía no se convierte en cero. Fechas mal formadas
o valores numéricos no admitidos dejan la métrica sin valor y con un motivo en
`issues`, sin certificar un subconjunto aparentemente válido.

Límites: 200.000 filas del archivo, 128 MiB de Parquet, 30 segundos por cálculo,
hasta ocho filtros y 16 valores por filtro, 4 KiB por receta y 2 KiB de nombres
de fuente. El máximo global de 256 facts evita expansiones sin límite; superar
ese máximo conserva el bruto como texto de fallback. Sobrepasarlos no devuelve un resultado
truncado. DuckDB tiene un hilo y 128 MiB de memoria configurada. Estos límites son
independientes del presupuesto del modelo y no son una cuota total del servicio.

La migración 37 añade `engine_calculations`. La clave y la huella de la receta
son idempotentes y las peticiones concurrentes iguales calculan una sola vez.
La observación guarda versión, hash del código, versión de DuckDB, tabla, hash de
Parquet, nombres originales y filtros. `resultado` pagina la misma observación;
el ID devuelto se usa como `execution_id` en `numbers`, con la key como metric.
La verificación final vuelve a leer y calcular desde Parquet. Un valor guardado
incorrecto se corrige; un ámbito distinto, versión distinta o corrupción no se
recertifican. Las frases visibles identifican el archivo de origen, columna,
filtros, tratamiento de nulos y límites. Mantienen el ledger v1 y distinguen cada
ocurrencia; la prosa y las etiquetas escritas por el agente siguen sin certificación.

No cubre porcentajes entre selecciones arbitrarias, rankings con catálogos unidos,
predicciones ni consultas Python generales. Los porcentajes del panorama siguen
su receta anterior. El prompt exige conservar las cifras necesarias sin receta y
su incertidumbre, y colocar los hechos admitidos junto a la recomendación que
justifican. No obliga a omitir una conclusión para mejorar una tasa. La puerta de
P3 sigue pendiente; añadir esta cobertura no acredita que se alcance el 100 % de
prioridades o el 95 % del resto.


### Diagnósticos de aborto

`diagnostics` incluye abortos de admisión aunque no haya excepción del controlador,
y los fallos del proxy con `stage`, `exception_type`, `reason`, un mensaje fijo y
`call_id` cuando existe. Los rechazos por tokens añaden `limit`, `requested_input`,
`requested_output`, `charged_input` y `charged_output`. Los eventos antiguos sin
fase se exportan como `unspecified`, sin inventar su causa. Cada registro de
`proxy-calls.jsonl` añade `diagnostic` o null, separado de los datos de facturación.
No se exportan mensajes originales de excepciones, URLs, credenciales ni cuerpos
como diagnósticos. El coste sigue incompleto si falta uso; la reserva no se libera.
Los borradores de trabajos abortados permanecen exportables sin cambiar su estado
a entrega completa. Son campos aditivos del contrato v1.
