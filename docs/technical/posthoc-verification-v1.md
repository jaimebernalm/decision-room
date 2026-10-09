# Verificación posterior a un informe: piloto V1

El propietario autoriza iniciar V1 después del cierre de R0/R1. Se implementa en
un paquete separado, sin modificar sus candidatos congelados ni abrir P4. La
medida sigue el preregistro `2026-10-08-loop-verification-preregistration.md`,
revisión 3 y aclaración de formato, en la rama de evaluación.

## Secuencia

1. Inventario compartido y precisión determinista: implementados y comprobados.
2. Interpretaciones separadas con valor oculto, recetas fundamentadas y recálculo:
   núcleo implementado con proveedor simulado y probado también en desarrollo
   facturable sobre un primer informe.
3. Derivada con invariantes, exportación y contabilidad mediante el proxy:
   implementadas y comprobadas con Chrome/PostgreSQL reales y proveedor simulado.
4. Desarrollo en curso; congelación y evaluación sellada pendientes. Las pruebas técnicas
  no acreditan los umbrales del piloto.

La aclaración de población aprobada durante desarrollo queda registrada en la
rama de evaluación (revisión `1ad423d`): se exige totalidad explícita y veto por
categorías. No se aplica retrospectivamente a los recibos de intentos anteriores.

El presupuesto conjunto de desarrollo y prueba es de 3 USD conocidos. Una llamada
con coste incierto exige parar y consultar. El auditor y los lectores siguen el
procedimiento separado de evaluación; ningún dato de auditoría se pasa al producto.

## Inventario `posthoc-inventory-v1`

`decision_room.reports.posthoc.inventory.build_inventory(html_path)` abre el HTML
original en un perfil efímero de Chrome, a 1280 px, ejecuta sus scripts y espera a
que el texto del DOM se estabilice. No modifica el archivo ni llama a un modelo.
La captura queda incluida para reproducir y revisar el inventario. Una revisión
posterior de scripts, fuentes o contenido puede cambiar la captura: se comparan
hashes antes de reutilizar un inventario.

- `source_sha256`: hash de los bytes originales.
- `text`: texto canónico del DOM renderizado. Las etiquetas inline no insertan
  separadores; los bloques y las celdas sí. No es el HTML fuente ni `textContent`
  que incluya scripts o elementos ocultos.
- `text_sha256`, `snapshot_sha256`: identidades de texto y captura.
- `occurrences[]`: `id`, `text`, `span: [inicio, fin)`, `kind`, `region`, `parts`
  y `context`. Los offsets de `span` son puntos de código Unicode, como en Python.
  La identidad incluye la versión, los hashes del original y texto, y el span.
  No se colapsan repeticiones: cada ubicación conserva su identidad.
- `parts[]`: camino de índices `childNodes` desde `document.body` y span UTF-16
  dentro de cada nodo de texto. Permite localizar números partidos entre nodos y
  conservar el original al añadir marcas.
- `context.section[]` y, en tablas, `context.table.{caption,column_headers,row_headers}`:
  referencias `{text, span}` al mismo texto canónico. `table.unresolved` indica
  falta de correspondencia. La estructura orienta la interpretación; no acredita
  por sí sola que una fila sea una entidad ni que una celda sea una población.
- `region: chart` identifica texto de SVG/canvas: se conserva en el inventario
  aunque su comprobación esté fuera del catálogo. Píxeles de canvas sin texto DOM
  deben registrarse aparte por el auditor y permanecer en el denominador.

La evaluación utiliza estos mismos ids y spans. El ledger posterior será un mapa
por id con `status`: `verified`, `discrepancy`, `not_checkable` o `uncertain`.
El inventario no descarta años, identificadores ni cifras de gráficos; decidir si
una ocurrencia es una cifra de negocio es una fase separada y trazable.

La captura de texto no sustituye a comprobar visualmente los gráficos ni acredita
su estabilidad. CSS generado, texto dibujado en canvas y controles sin nodo de texto
no son cifras DOM certificables. La evaluación debe conservar esas limitaciones.

## Precisión `posthoc-precision-v1`

El parser recibe el literal original; el intérprete del ámbito no recibe su valor.
Se exige evidencia positiva de la convención española y ausencia de formatos
contradictorios. `1.234` solo no acredita miles. No se consulta el recalculado para
resolver formato, unidad, escala o ámbito.

La comparación se hace en la escala mostrada, con medio lejos de cero: `1,2 M`
compara el recalculado dividido por un millón a un decimal. Los recuentos y sumas
enteras sin abreviar exigen igualdad exacta. La dirección fundamentada en el texto
se comprueba además del valor y no borra un signo explícito contradictorio.

## Comprobaciones de la primera pieza

`python -m unittest discover -s tests -p test_posthoc_inventory.py -v`: nueve casos,
con Chrome real para contenido dinámico/oculto, tablas y SVG; fixtures para nodos
inline, Unicode/UTF-16, identidades repetidas y reglas adversarias de precisión.
Sin proveedor facturable y sin inspeccionar el conjunto de prueba de V1.

## Núcleo de interpretación y recálculo

`interpretation.verify(inventory, sources, ask, dest)` conserva primero el
inventario, política y cada solicitud. Llama dos veces a `ask(prompt, input,
call_key)` sin pasar respuesta ni historial de la otra llamada. El adaptador
`ask` es responsable de admisión, proveedor y recibos de coste; el núcleo todavía
no habilita llamadas facturables por sí mismo.

Se oculta el literal objetivo y las repeticiones con escritura numérica equivalente según el parser;
las fechas conservan contexto. La agrupación solo oculta: no comparte estados.
Cada interpretación aporta citas con spans del texto enmascarado. Se validan por
separado y se compara todo el contenido de cálculo de las recetas. Las citas pueden
ser distintas si ambas están fundamentadas; no se confunden con el ámbito calculado.
Un acuerdo con sus dos respuestas queda persistido antes del recálculo. Sigue siendo
una hipótesis semántica sometida a auditoría, no una garantía por doble votación.

`recipes.py` usa el evaluador existente sobre Parquet fijado por hash, con
operandos ordenados, filtros explícitos y unidad declarada. No admite base cero o
negativa, selección vacía ni cuotas sin contención estructural de poblaciones.
La fecha final es inclusiva. Las medias diarias dividen por días naturales, no por
filas observadas. Un fallo del proveedor no se oculta como incertidumbre semántica:
termina el run y preserva los recibos, sin reenvío.

`sources.prepare(csv_files, dest)` prepara snapshots locales y solo permite pasar
al intérprete hashes, columnas y categorías acotadas. Las medidas numéricas no se
exportan como ejemplos. Las correspondencias de dimensiones se basan en una clave
única observada y nombres normalizados sin ambigüedad; no acreditan la granularidad
de negocio. Las unidades por defecto son los nombres de columna, sin inferir euros,
ventas ni pedidos. Los archivos preparados y catálogos son privados.

Validación del núcleo: 19 pruebas sin proveedor facturable, incluyendo las diez de
inventario/precisión, agregados reales en DuckDB, derivados, último día inclusivo,
datos cambiados, lecturas que discrepan aunque produzcan el mismo número y
repeticiones con ámbitos distintos que reciben estados distintos.

## Recorrido integrado y presupuesto

La CLI `python -m decision_room.reports.posthoc` separa `prepare`, `estimate` y
`run`. Preparar no llama a un modelo. El run exige una clave por entorno, un archivo
SQLite de presupuesto compartido por todo V1 y una carpeta no ejecutada antes.
`api.run` usa el proxy existente y fija gpt-6-luna, low, tier default; no arranca
OpenCode ni cambia los candidatos anteriores.

Se admiten grupos de cuatro ocurrencias en orden de inventario (parámetro que se
fijará al congelar). En cada grupo se ocultan simultáneamente todos los objetivos
y sus escrituras equivalentes, con dos llamadas sin historial cruzado. Cada
ocurrencia conserva dos recetas y un estado propios. Una forma ilegible o un grupo
incompleto queda incierto, sin reparación usando resultados. Se guardan las
interpretaciones textuales para comparar bytes, y aparte la igualdad canónica de
sus objetos JSON. La agrupación no depende de lo que responda el modelo.

El proxy cuenta entrada antes de generar. Un transporte de servicio reserva en
SQLite la cota del catálogo aplicable (toda entrada como escritura de caché y toda
salida autorizada) antes de enviar generación. Los costes confirmados liberan la
parte no consumida; coste desconocido, proceso interrumpido o reserva excedida
bloquean llamadas posteriores. Techo global 3 USD y por informe 0,50 USD. Son guardas
contra el catálogo, no garantía sobre la factura. La política persistida no se
resetea al abrir otro proceso ni se reescriben llamadas ya registradas.

Topes provisionales del trabajo de verificación: 6M de entrada, 512k de salida,
16k por llamada, 512 llamadas, 3600 s. Son de desarrollo, pendientes del anexo de
congelación; no reinterpretan los topes de P3/R1. Ninguna llamada facturable se
incluye en las pruebas de código.

Salidas: original.html idéntico en bytes, inventory.json, snapshots preparados,
verification/ledger.json, solicitudes/respuestas/acuerdos/recálculos por ocurrencia,
recibos de proxy y presupuesto, derived.html y checks.json. Solo run.json con
status=completed permite usar el ledger en evaluación. Un fallo conserva parciales
sin acreditar entrega. Las credenciales no se persisten.

La derivada conserva los bytes del original como prefijo y solo añade un instalador
identificado. Las marcas no se instalan si el DOM renderizado difiere de la captura.
La QA retira exclusivamente las inserciones y exige igualdad del DOM original y
hashes idénticos de capturas de cada gráfico SVG/canvas. No se cambian sus valores.
Los informes con recursos relativos que no se resuelvan igual en el destino deben
fallar la QA, sin reescribir silenciosamente el original.

El comando de ejecución usa por defecto un techo acumulado de desarrollo de
1,80 USD, aplicado antes de cada generación junto con la reserva de coste y el
tope por informe. Deja al menos 1,20 USD del presupuesto compartido para la prueba.
La prueba congelada debe seleccionar explícitamente un techo acumulado de 3 USD
en la misma base de presupuesto: no borra ni reinicia costes de desarrollo, y
cualquier llamada pendiente o incierta sigue bloqueando. El techo elegido queda
en el registro de inicio y los recibos. Se revisará el desarrollo al aproximarse
a 1 USD si no produce acuerdos en magnitudes simples sobre varios informes.

Validación integrada: 31 pruebas, incluidas PostgreSQL y Chrome reales; proveedor
HTTP simulado en todos los casos. Se comprobaron conservación de un SVG generado
por script, exportación completa, rechazo de reenvío, límites global/por informe,
parada por coste desconocido y ausencia de credenciales en artefactos. El entorno
de pruebas usa el socket corto configurado localmente para PostgreSQL.

## Presentación de estados

La variante `posthoc-presentation-v2` conserva una envoltura por ocurrencia textual:
verificada lleva un subrayado discreto; discrepancia lleva subrayado y enlace por
clic o teclado a su recálculo; incierta y no comprobable conservan `title`, etiqueta
accesible y referencia a la leyenda sin añadir ruido visual. Los valores SVG/canvas
inventariados figuran en los totales, sin insertar marcas en el gráfico. El anexo
lo explica y distingue no comprobable de incorrecto. El anexo usa un contenedor
centrado y los valores originales no se corrigen de forma silenciosa.

Las pruebas en Chrome comprueban los cuatro estados, sus descripciones accesibles,
el enlace de discrepancia y la conservación de DOM/gráfico. La evaluación mantiene
una comprobación independiente de bytes, DOM y píxeles.

## Ayuda de localización en desarrollo

El intérprete recibe para cada objetivo un fragmento de hasta 240 caracteres antes
y después, con span global y foco relativo. Los textos de contexto se extraen del
mismo texto enmascarado conjunto después de ocultar todos los objetivos y sus
escrituras equivalentes. Son una ayuda para localizar el objetivo, no evidencia
nueva ni una reconstrucción del valor. Las citas siguen teniendo offsets globales
y deben superar las mismas comprobaciones antes de cualquier recálculo.

La localización `posthoc-localization-v1` deja fuera de los objetivos las cifras
contenidas en alias de dimensión acreditados, identificadores y nombres de archivo,
ordinales al inicio de encabezados y componentes de fecha con contexto explícito.
Un número seguido de una unidad o sustantivo de cantidad sigue siendo objetivo.
Un año aislado sin contexto de calendario no se descarta. Cada decisión y su regla
quedan en `localization.json`; no se elimina ningún id del inventario ni del ledger.
Una etiqueta se mantiene visible salvo que sea una escritura equivalente de otro
objetivo, en cuyo caso la protección de enmascarado prevalece. Los grupos se forman
en orden de inventario después de esta clasificación, sin usar resultados ni
respuestas del modelo. Un falso descarte cuenta contra la cobertura auditada.

El contexto de tabla añade `row_text` (texto de la fila, sin atribuirle función de
cabecera) y `cell_is_header` derivado exclusivamente de TH/THEAD. Los textos de fila
que recibe el intérprete se vuelven a extraer después del enmascarado conjunto.

El adaptador de citas ofrece segmentos deterministas: líneas del texto enmascarado,
divididas cada 800 caracteres si son más largas. Cada cita del modelo da id de
segmento y texto exacto; el servidor exige una sola aparición dentro de ese
segmento, resuelve el offset global y aplica las mismas validaciones. No acepta
una cita hecha solo de máscara/puntuación, no elige la primera de varias y no usa
el valor recalculado para localizarla. Se guardan respuestas crudas y resueltas
antes del acuerdo y del recálculo. Los targets identifican explícitamente su
region; una tarjeta numérica de texto no se confunde con un gráfico SVG/canvas.

Las citas de periodo deben incluir los años de ambos límites de cada filtro de
fecha. Un mes o intervalo de meses citado sin el año no basta aunque el año exista
en otra parte del informe. Esta guarda mecánica no acredita por sí sola el día,
mes, relación con la ocurrencia ni significado del periodo; siguen sujetos a la
doble interpretación y a la auditoría. Regresión: ningún año, solo uno de los dos
años y ambos citados por separado.

Las aproximaciones, cotas explícitas e intervalos numéricos se conservan como
inciertos sin reinterpretarlos como puntos exactos. La decisión y su regla quedan
en la localización; no hay llamadas para esas ocurrencias ni recálculo adaptativo.
La regla distingue un intervalo «entre A y B» de un cambio «pasó de A a B».

## Población sin filtro: totalidad con veto

Cada operando sin filtro categórico necesita una cita de la lista cerrada `total`,
`en total`, `todas`, `todos`, `conjunto`, `el negocio`; «unidades registradas» no
basta. El servidor veta esa población si encuentra un nombre o código de categoría
del catálogo en el segmento objetivo, la cadena de secciones o el contexto de tabla
(caption, cabeceras de columna/fila y texto de fila). Comprueba el texto original
en esos mismos spans, de modo que el enmascarado no oculte una restricción a la
guarda. Ese texto original no se envía al intérprete.

Se aplica a cada operando y ocurrencia; tampoco exime el denominador sin filtrar de
un cociente o cuota. Puede reducir la cobertura cuando el contexto nombra una
categoría que solo corresponde al numerador. No se elige una interpretación para
salvar el rechazo. La doble lectura debe seguir fundamentando los filtros y los
años de los límites deben estar citados. Las alusiones indirectas («estos
productos», «solo online», «excepto…») no quedan resueltas por el veto del catálogo:
son un riesgo residual para la interpretación y la auditoría.

Regresiones: medida sin totalidad, totalidad bajo un encabezado de categoría,
«total de» una categoría y categoría en contexto de tabla quedan inciertas. Dos
ocurrencias del mismo grupo con distinto contexto no heredan sus estados.

El complemento registrado en evaluación (`43f945b`) veta también negación o
exclusión en la oración original que contiene cada cita de totalidad y en la del
objetivo, aunque la negación quede fuera del recorte citado. La lista cerrada es
`no`, `sin`, `excepto`, `salvo`, `menos`, `excluye`, `excluido`, `excluida`,
`excluidos`, `excluidas`. Los delimitadores son punto, punto y coma, interrogación,
exclamación, salto de bloque o celda. No convierte esas palabras en un veto global
sobre otras oraciones. El diagnóstico estructurado registra la palabra y span,
o la categoría, tabla, columna y span que dispararon el veto del catálogo; el
orden de búsqueda es determinista. Se conserva el estado incierto y el motivo
estable, para poder contar los rechazos sin mezclar las categorías.

## Arranque de Chrome después de interpretar

La comprobación de presentación usa los descriptores reales de sus dos pipes,
remapeados a 3/4 en un intérprete hijo antes de ejecutar Chrome. No presupone que
3/4 estén abiertos en el proceso que ya ha usado conexiones HTTP y de base de
datos, ni ejecuta código Python mediante `preexec_fn` en ese proceso.

Una regresión con los pipes trasladados a descriptores altos reproduce el error
EBADF del lanzador anterior y comprueba dos aperturas reales de Chrome con la
corrección. Pasan 44 pruebas del paquete, incluidas persistencia PostgreSQL, Chrome
y transporte simulado. No se hicieron llamadas facturables para esta corrección.
Un intento que falló en la QA mantiene su estado fallido; una comprobación posterior
se guarda aparte y no lo convierte retrospectivamente en una entrega completada.
La navegación también exige la URL exacta del informe y rechaza el error de carga
de Chrome, para no inventariar o comparar accidentalmente su página de error.
