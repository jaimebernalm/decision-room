# Verificación posterior a un informe: piloto V1

El propietario autoriza iniciar V1 después del cierre de R0/R1. Se implementa en
un paquete separado, sin modificar sus candidatos congelados ni abrir P4. La
medida sigue el preregistro `2026-10-08-loop-verification-preregistration.md`,
revisión 3 y aclaración de formato, en la rama de evaluación.

## Secuencia

1. Inventario compartido y precisión determinista: implementados y comprobados.
2. Interpretaciones separadas con valor oculto, recetas fundamentadas y recálculo:
   núcleo implementado con proveedor simulado; pendiente de integración facturable
   y desarrollo sobre informes.
3. Derivada con invariantes, exportación y contabilidad mediante el proxy:
   implementadas y comprobadas con Chrome/PostgreSQL reales y proveedor simulado.
4. Desarrollo, congelación y evaluación sellada: pendientes. Las pruebas técnicas
   no acreditan los umbrales del piloto.

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

Validación integrada: 31 pruebas, incluidas PostgreSQL y Chrome reales; proveedor
HTTP simulado en todos los casos. Se comprobaron conservación de un SVG generado
por script, exportación completa, rechazo de reenvío, límites global/por informe,
parada por coste desconocido y ausencia de credenciales en artefactos. El entorno
de pruebas usa el socket corto configurado localmente para PostgreSQL.
