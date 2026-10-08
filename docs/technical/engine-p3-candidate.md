# Candidato A2 para el piloto de P3

Fecha: 2026-10-07. Este documento propone congelar un candidato para comprobarlo;
no declara superada la puerta de P3. La revisión exacta es el último commit candidato que incorpora
este documento y su prompt, con las recetas descritas en su historia. Claude registra el hash en el manifiesto
y el preregistro antes de las ejecuciones evaluadas.

## Cobertura que ofrece el candidato

| Cifras | Receta y alcance | Verificación visible |
| --- | --- | --- |
| Totales, grupos, diferencias, tramos sin registros y bases del panorama | Panorama recalculado con tabla, mapping y ventanas congelados | Facts generados por el servidor; cobertura, causas y prioridades fuera de la certificación |
| Variación porcentual y cuota de los grupos que devuelve el panorama | `engine-panorama-ratios-v1`; operandos explícitos, sin porcentaje con base no positiva | Cifra y ambos operandos con sus spans; no se ajustan ventanas ni estacionalidad |
| Suma, media por registro, mínimo, máximo y recuento con filtros explícitos | `engine-scoped-aggregates-v1`, nueva herramienta `calculo`; una tabla, filtros por pertenencia o intervalo ISO, sin código del agente | Fuente, columna, filtros, nulos y denominadores generados por el servidor y recalculados desde Parquet |
| Python arbitrario, tablas unidas, porcentajes entre selecciones arbitrarias, predicción | `consulta` conserva ejecución y resultados; no hay receta independiente general | Sin certificación semántica; conservar lo necesario y su incertidumbre |
| Cifras en prosa libre o etiquetas de gráficos del agente | Una coincidencia numérica no prueba atribución | Cada ocurrencia sigue sin verificar aunque otra ocurrencia del mismo valor sí lo esté |

La cobertura se mide sobre las cifras y recomendaciones que necesita el informe,
no se reduce el denominador al catálogo de recetas. El prompt pide vincular los
facts al hallazgo correspondiente y conservar cifras relevantes sin receta. No
ordena cambiar conclusiones, omitir alternativas ni afirmar verificación global.
Evita llamadas de `verify_numbers` redundantes: el exportador final recalcula los
facts. Este comportamiento debe comprobarse con el modelo, no se deduce de las
pruebas con proveedor simulado.

## Cambios que deben constar antes de medir

- Exportación sigue en contrato v1; `renderer_version=report-evidence-v4`.
- Verificador `engine-number-checks-v4`; nueva receta de agregaciones v1 con hash
  del módulo y versión de DuckDB. Migración de almacenamiento 37.
- Herramienta MCP aditiva `calculo`, prompt actualizado y descripciones/diagnósticos
  de `consulta` corregidos desde el lote de P2. CSV y encargo plano sin cambios.
- Nuevos límites de cálculo: 32 recetas, 8 filtros por receta, 16 valores por filtro,
  4 KiB por receta, 200.000 filas, 128 MiB Parquet y 30 s. Rechazo sin truncamiento.
  Informe: 32 facts por lista, 256 en total. Exceso conserva el bruto como fallback.
- Ningún cambio de fórmulas de la puerta, emparejamiento, lectores o auditor. La
  unión por path/span/text sigue diferenciando prosa, hechos y repeticiones.
- La medida «contenido» usa `informe.contenido.html`, sin marcas pero con las mismas
  frases y limitaciones. El formato puede revelar el brazo, como ya se registra en
  el preregistro; quitar marcas no asegura ceguera perfecta.

## Topes propuestos para P3

Se proponen **6.000.000 entrada / 128.000 salida / 8.000 por llamada / 60 llamadas /
1.200 s activos**, con `service_tier=default`. P2 observó como máximos 1.952.976,
44.302, 41 y 419 s respectivamente para entrada/salida/llamadas/tiempo. Hay margen
observado en P2, pero los canarios de A2 ya alcanzaron el 93–95 % del antiguo
límite de entrada de 3.000.000. La calibración previa al lote formal aumenta solo
la entrada a 6.000.000. El canario siguiente agotó el margen para reservar salida
con 57.912 tokens ya usados; la revisión posterior eleva la salida a 128.000.
Estos límites se fijan antes de la comparación formal;
no se amplían después de ver resultados evaluados. La desviación entre brazos y
el cambio respecto de P2 deben constar en el preregistro y manifiesto.

Antes del lote de 36, Claude comprueba el brazo sin modelo y un canario de
comportamiento/consumo con el presupuesto que gestione el propietario. Si hay un
fallo técnico, de topes o de comportamiento que justifique revisarlo, el candidato
se retira, se documenta y se propone una revisión nueva antes de la medición formal. No se incluye ese canario como una
pareja evaluada ni se lanza el lote a partir de una declaración de éxito local.
Si la puerta falla por cobertura o calidad, se conserva el fallo; las recetas no
cambian el significado de «verificado y correcto» del auditor.

## Validación de código

- 129 pruebas de motor aprobadas con imagen habilitada, PostgreSQL, Docker y
  OpenCode reales y proveedor simulado; incluye el brazo vivo de medición integrado.
- 62 pruebas de agregación, ratios, facts, representación, contrato, actividad y
  migraciones aprobadas durante la implementación.
- Después de acotar la expansión, 51 pruebas de agregación, facts, representación,
  contrato y unión de exactitud aprobadas. Los números anteriores se solapan y no
  se suman como si fueran casos diferentes.
- El recorrido real de descubrimiento lee el manifiesto/CSV, usa `consulta` y
  `calculo`, entrega y exporta la suma verificada con sus recuentos. La misma cifra
  en prosa queda sin verificar. Prueba con proveedor simulado, sin gasto de API.

P2 está cerrado en alcance local. P3 sigue pendiente de canario, congelación del
manifiesto y puerta completa; la integración web, edición y PDF del producto siguen
en P4. No se atribuye mejora de calidad a las pruebas de implementación.


## Ajuste previo al canario: nombres, presentación y coherencia

Un ensayo preparatorio de lectura sobre informes de P2, anterior a este candidato,
señaló códigos sin resolver, atribuciones contradictorias y falta de gráficos. Es
información para preparar el candidato, no resultado de la puerta de P3. Antes del
canario se ajusta únicamente el prompt:

- Resolver nombres con los catálogos disponibles mediante `consulta`, comprobando
  unicidad de claves, cardinalidad de la unión y conservación de totales. Conservar
  códigos sin correspondencia o ambiguos sin adivinar nombres. Vincular nombre y
  código cuando haga falta interpretar el fact, cuyo ámbito original se conserva.
- Usar gráficos o tablas útiles para comparaciones, evoluciones y repartos que
  sostengan decisiones, sin una cuota fija. El renderizador ya ofrece SVG de barras
  y líneas y tablas completas en ambos HTML; `marks=False` no elimina gráficos.
- Revisar atribución entre todas las secciones y distinguir niveles, diferencias y
  ausencia de registros antes de la revisión final. Una referencia no certifica una
  afirmación distinta en prosa ni un nombre de catálogo elegido por el agente.

No cambian herramientas, recetas, ledger, renderer, topes ni fórmulas de la puerta.
La revisión anterior se sustituye antes de gastar en el canario. El efecto del
prompt sobre nombres, coherencia y gráficos deberá medirse; las pruebas locales
solo comprueban la capacidad del renderer y las fronteras de verificación.

Validación de este ajuste: 21 pruebas existentes de charts, proyección y facts
aprobadas (`tests.test_report_charts`, `tests.test_report_projection`,
`tests.test_report_facts`). Sin llamadas facturables. Estas pruebas no acreditan
que el modelo siga las instrucciones nuevas; eso corresponde al canario.


## Retirada del candidato y continuación de la investigación

El canario de desarrollo de `ff36234` produjo dos entregas: una incluyó facts
verificados; la otra terminó con un informe provisional sin prioridades después
de repetir la primera página del panorama. Se retira esa revisión antes del lote
formal. El canario conserva su condición de evidencia de desarrollo y no cuenta
como pareja de P3. La paginación confusa y la cautela del prompt son hipótesis
sobre el comportamiento observado, no causas demostradas por una comparación.

La revisión siguiente distingue `requested_cursor` y `next_cursor`, conserva
`cursor` como alias del siguiente desplazamiento y devuelve `next_call`. Para
`panorama` y `verify_numbers`, `reuse_previous_arguments=true` indica conservar
los argumentos de esa herramienta y aplicar `arguments` (solo el nuevo cursor).
Para `consulta`, `calculo` y `resultado`, devuelve los argumentos completos de
`resultado` con `reuse_previous_arguments=false`. Así no se repiten recetas
potencialmente grandes dentro de cada respuesta. `next_call=null` marca el final.
Se mantienen cien filas por página y el límite de 64 KiB de la respuesta MCP;
el presupuesto del contenido reserva espacio para los metadatos de continuación.

El prompt aclara que una página truncada tiene continuación, que se pueden hacer
consultas acotadas sin leer páginas irrelevantes, y que una correspondencia de
catálogo incierta limita ese nombre, no todo cálculo sobre la tabla. Tras guardar
un avance debe continuar investigando antes de entregar la revisión final. No se
obliga a inventar prioridades ni a ocultar incertidumbres. El controlador conserva
su comportamiento: un recibo guarda el borrador; finaliza cuando el turno raíz ha
terminado y las sesiones observadas están inactivas. `delivered` no prueba calidad.

Esta revisión no cambia recetas, renderer, ledger, topes ni condiciones de P3.
El manifiesto debe fijar el nuevo commit y registrar las descripciones MCP y el
prompt nuevos antes de otro canario y de la posterior congelación formal.

Validación: 55 pruebas de `test_engine_panorama`, `test_engine_admission`,
`test_engine_api` y `test_engine_calculations` aprobadas. Incluyen recorrer todas
las páginas del panorama y de 32 comprobaciones sin duplicar hojas ni ejecuciones,
continuar agregaciones por `resultado`, conservar celdas Unicode largas y acotar
la respuesta MCP completa. El recorrido con OpenCode real y proveedor simulado
lee el manifiesto, guarda un avance, sigue la página anunciada, consulta, calcula
y reemplaza el avance por la revisión final. La fixture cubre dos meses completos.
Sin llamadas facturables. Esto prueba el protocolo y la persistencia, no que el
modelo adopte la conducta nueva; esa comprobación sigue en el canario.


## Calibración tras el segundo canario y enlace de hechos

El canario de desarrollo de `f1750b0` entregó los tres informes y no repitió el
abandono prematuro observado antes. Dos trabajos consumieron aproximadamente el
93 % y el 95 % del tope de entrada; otra entrega no incluyó facts aunque había
usado `calculo`. Estas observaciones justifican una revisión antes de congelar,
no prueban todavía que se supere la puerta ni permiten cambiar sus condiciones.
La fracción de todas las figuras marcadas no equivale a la cobertura auditada:
el ledger también incluye componentes de fechas y otras cifras no calculables.
La ausencia de facts sí muestra que calcular no basta para presentar evidencia.

Se corrige una contradicción del prompt: el esquema inicial ahora incluye
`findings[].facts` y pide enlazar referencias disponibles de `numbers` con esos
hechos; solo los tokens dentro de prosa siguen siendo opcionales. Un ejemplo
completo muestra ese enlace y exige sustituir el identificador por el devuelto
por la herramienta. El recordatorio final y la descripción de entrega explican
que llamar al cálculo o al verificador no adjunta sus resultados automáticamente.
No se añaden rechazos de borradores ni certificación de frases libres, y se
conservan las cifras necesarias que las recetas aún no pueden verificar.

La entrada predeterminada para trabajos nuevos pasa a 6.000.000; los trabajos
existentes mantienen sus límites persistidos. Salida, llamadas, tiempo y tier
no cambian. El límite de tokens no es un límite monetario: la proporción de caché
observada no garantiza un precio y no amplía el presupuesto aprobado. El evaluador
debe registrar el nuevo límite en los manifiestos, conservar la desviación de
presupuestos respecto a los controles y vigilar su presupuesto monetario antes
de ejecutar. Esta revisión sustituye `f1750b0` para el siguiente canario de desarrollo.

Validación de esta revisión: 42 pruebas de admisión, facts, proyección y gráficos
aprobadas. El ejemplo JSON del prompt pasa el cargador y el contrato de exportación;
su identificador de ejemplo no se certifica sin evidencia. Se comprobó también que
un límite explícito de 3.000.000 sigue aceptándose, aunque el valor predeterminado
sea 6.000.000. Sin llamadas facturables. El cumplimiento de las instrucciones por
el modelo sigue pendiente del canario; estas pruebas no miden cobertura analítica.


## Aborto antes de congelar: salida y diagnóstico

El canario de `7f291b0` entregó uno de tres trabajos. Otro abortó con una llamada
sin recibo de uso y sin borrador; el tercero conservó un borrador legible pero
abortó por cuota: 57.912 tokens de salida más la reserva de 8.000 superan 64.000.
La admisión funcionó como estaba configurada. Se retira el candidato antes del
lote formal y se aumenta la salida acumulada para trabajos nuevos a 128.000.
Entrada 6.000.000, salida por llamada 8.000, 60 llamadas, 1.200 s y tier default
se conservan. No se amplía el presupuesto monetario; el evaluador debe registrar
la nueva calibración y la desviación respecto a los controles antes de medir.

La revisión añade diagnósticos de aborto a `run.json` y diagnósticos por llamada
a `proxy-calls.jsonl`: fase, tipo de excepción y descripciones fijas, sin texto
original del proveedor, credenciales, rutas ni cuerpos. Para cuotas se registra
la dimensión que rechazó la reserva, el pedido y lo ya cargado. Si la cuota ya
abortó el trabajo, el proxy conserva ese motivo, sin volver a etiquetarlo como
uso desconocido. El registro de diagnósticos no impide intentar la liquidación
conservadora si falla su propia escritura.

La duración de la llamada incierta es compatible con alguna espera de 120 s,
pero no identifica su causa. El proxy, el túnel y el relay tienen esperas de ese
orden entre lecturas; no son un plazo total de generación. Esta revisión no
cambia esas esperas ni afirma haber reparado el fallo del proveedor. La próxima
comprobación debe distinguir timeout de cabeceras, lectura de stream, cierre del
cliente y fallo de cuota antes de cambiar el transporte.

Se conserva el cierre conservador ante uso desconocido: reserva retenida, sin
reenvío automático ni continuación. La propuesta del evaluador de continuar
imputando toda la reserva queda como desacuerdo visible; una reserva contable
no confirma que la respuesta ni sus posibles acciones estén reconciliadas.
Tampoco se introduce `delivered_partial`: el borrador de un aborto se conserva
y exporta, pero `aborted` sigue siendo distinto de entrega completa. Se informa
por separado de los parciales recuperados; no se cambia la puerta para contar
el intento abortado como entregado. P3 sigue sin congelarse ni superarse.

Validación de esta revisión: 53 pruebas de diagnósticos de aborto, admisión, API,
costes, fallos, saneamiento y brazo vivo del lanzador aprobadas con la imagen
habilitada. Incluyen fallos al contar, abrir, leer y escribir; rechazo por cuota
con motivo correcto; diagnóstico sin excepción del controlador; fallo de escritura
del propio diagnóstico; SIGKILL de controlador/proxy; reservas concurrentes y
parciales conservados. OpenCode y Docker reales usan proveedor simulado, sin gasto
facturable. Estas pruebas no identifican retrospectivamente la causa del canario.
