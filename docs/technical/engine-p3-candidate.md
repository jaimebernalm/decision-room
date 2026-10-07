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

Se mantienen **3.000.000 entrada / 64.000 salida / 8.000 por llamada / 60 llamadas /
1.200 s activos**, con `service_tier=default`. P2 observó como máximos 1.952.976,
44.302, 41 y 419 s respectivamente para entrada/salida/llamadas/tiempo. Hay margen
observado, pero A2 puede consumirlo con más cálculos y texto. Se mantienen constantes
para la comparación inicial; no se amplían después de ver resultados evaluados.

Antes del lote de 36, Claude comprueba el brazo sin modelo y un canario de
comportamiento/consumo con el presupuesto que gestione el propietario. Si hay un
fallo técnico o de topes, el candidato se retira, se documenta y se propone una
revisión nueva antes de la medición formal. No se incluye ese canario como una
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
