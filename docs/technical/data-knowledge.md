# Catálogo, memoria de datos y diagrama ER — paso 3.2

## Un modelo compartido

`data_model_revisions` conserva documentos inmutables por negocio, conjunto y
revisión. Guarda la huella de los archivos preparados, las tablas, columnas,
claves candidatas/declaradas, relaciones, definiciones de métricas, procedencia
y fecha de comprobación. La ficha y `inspect_dataset` leen esa misma revisión.
El diagrama no mantiene un esquema independiente.

La importación prepara el catálogo automáticamente. Si la comprobación falla,
los archivos importados permanecen disponibles y la ficha permite reintentarlo.
Los conjuntos anteriores sin catálogo ofrecen «Preparar modelo de datos»;
iniciar un informe también asegura su preparación. Una huella idéntica reutiliza
la revisión, sin volver a perfilar los archivos. Guardar exactamente el mismo
contenido no crea otra revisión.

## Qué se comprueba

Sobre todas las filas de Parquet, con integridad de archivo comprobada:

- Valores ausentes, distintos, repetidos y filas enteras duplicadas.
- Tipos lógicos observados, conversiones numéricas y fechas ISO válidas, rango de
  fechas observado y claves candidatas. El almacenamiento original sigue siendo
  textual: no se eliminan ceros iniciales ni se convierten unidades automáticamente.
- Claves simples y compuestas de hasta seis columnas, declaradas por el usuario.
- Relaciones por igualdad exacta: cardinalidad observada, duplicados en ambos
  lados, claves ausentes, filas sin correspondencia, cobertura, filas resultantes
  de la unión izquierda e incremento por multiplicación.

Las frecuencias se agrupan **antes** de comprobar una unión muchos a muchos.
Así puede medirse la multiplicación sin materializar un producto cartesiano.
DuckDB utiliza dos hilos, 512 MB de memoria, hasta 2 GB temporales y un límite de
tres minutos para preparar/comprobar el modelo. No ejecuta SQL generado por el
modelo en este servicio; los nombres se escapan y los archivos están acotados al negocio.

La inferencia es conservadora: compara identificadores con nombres de entidades
compatibles. No une columnas genéricas `id`, `name` o fechas por mera coincidencia.
Las claves compuestas y nombres diferentes se pueden declarar explícitamente.
No se afirma haber descubierto todas las relaciones ni se conectan entregas
independientes automáticamente.

## Significado y comprobación son estados diferentes

Una relación tiene origen (`inferred` o `owner`), estado semántico (propuesta,
confirmada o descartada) y comprobación técnica (comprobada o necesita atención).
Confirmar el significado no elimina duplicados ni convierte una unión muchos a
muchos en una agregación segura. Una coincidencia técnica no confirma significado.

El usuario puede aclarar descripción, significado de cada fila, significado y
unidad de columnas, conversiones necesarias y definiciones de métricas. Estas
últimas incluyen tablas y periodo. Las fórmulas se guardan como definiciones;
no se ejecutan como código. Las conversiones ambiguas y unidades no declaradas
permanecen sin confirmar. La memoria de negocio existente sigue disponible:
las definiciones contradictorias deben aclararse, no elegirse silenciosamente.

## Recuperación para informes y chat

El contexto inicial incluye un resumen y la revisión del modelo. Los detalles
se recuperan por tabla con `inspect_dataset`, junto a conexiones adyacentes y
métricas aplicables. Sigue vigente el límite de 48 KB por recuperación y el
presupuesto de herramientas; no se inyecta todo el esquema en cada llamada.

Las declaraciones del catálogo incluyen referencias `dm:…@revisión:…`.
El plan debe citarlas con `kind=data_model` y `column=''`. El validador exige que
la referencia se haya entregado, pertenezca a las tablas y al conjunto autorizado,
y sea compatible con el periodo solicitado. Solo una declaración confirmada
puede justificar una interpretación confirmada; una relación propuesta no puede.
El conocimiento estructural no autoriza ejecutar sobre tablas fuera del plan.

Los manifiestos registran la revisión entregada. Una corrección invalida
conservadoramente los análisis que recibieron ese modelo o lo recuperaron; el
historial aprobado y su huella se conservan, pero dejan de ser publicables hasta
replanificar/recalcular y revisar. También se comprueba vigencia en las respuestas
y antecedentes del chat. No se recobran interpretaciones retiradas desde texto viejo.

Cada archivo nuevo se perfila de nuevo. Los significados confirmados no se copian
por coincidencia de nombres. Las versiones anteriores siguen consultables y las
versiones corregidas no pueden editarse ni utilizarse como evidencia vigente.

## Mi negocio

«Datos y versiones → Ver relaciones y cómo entendemos los datos» ofrece:

- Diagrama opcional con búsqueda, foco en una tabla y sus conexiones, selección
  por ratón/teclado y lista alternativa de conexiones.
- Hasta doce tablas visibles por mapa, con aviso y selección del resto.
- Detalles de tablas, columnas, claves, cardinalidad y precauciones.
- Formularios de aclaración, claves compuestas, confirmación/descarte de enlaces
  y definiciones de métricas; revisión esperada para impedir sobrescrituras.
- Historial de revisiones y número de informes que necesitan revisión.

## Recuperación de fallos encontrados en 3.1

Las solicitudes de contexto nulas, identificadores vacíos o inválidos y objetos
fuera del contexto permitido vuelven al bucle de corrección ya acotado del agente.
Los cambios reales de contexto siguen deteniendo la ejecución. Abrir el borrador
actual como si fuera un informe histórico recibe una explicación correctiva.

Un HTTP **503 explícito** permite dos reintentos, como máximo tres peticiones,
con esperas de 1 y 2 segundos o `Retry-After` numérico acotado a cinco segundos.
Otros estados y respuestas interrumpidas no se reintentan automáticamente. Los
intentos se registran con el uso conocido; un rechazo sin uso comunicado impide
presentar el total de tokens como completo. No se asume un precio ni coste cero.

## Alcance de esta entrega

El catálogo aporta estructura reutilizable y definiciones explícitas. No implica
que el sistema ya descubra todos los insights, que un diagrama autorice sumar
medidas de cabecera tras unir detalles, ni que se hayan cerrado investigación
por rondas, onboarding conversacional o evaluación final: son 3.3, 3.4 y 3.5.
