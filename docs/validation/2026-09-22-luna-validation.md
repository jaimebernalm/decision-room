# Validación de GPT-6 Luna antes de la entrega 3

## Método

Validación del recorrido existente, sin añadir analistas especializados, Excel ni
investigación web. Importación, planificación, respuestas del propietario,
investigación, revisión y exportación se ejecutan en procesos separados. Cada
repetición tiene su propia empresa, sesión y evidencia persistida.

La matriz amplía los ocho escenarios de 1.7 con cuatro casos controlados de
calidad: duplicados técnicos, importes vacíos, devoluciones negativas y fechas o
importes inválidos. Son **12 escenarios × 3 repeticiones = 36 recorridos**. Los
fixtures proceden de la muestra pública ficticia Microsoft Wide World Importers;
las alteraciones de calidad se describen en
[su README](../../data/reference-cases/04-data-quality/README.md).

Se usa `gpt-6-luna` mediante OpenAI, razonamiento `low`, máximo de salida de
16.384 tokens y plazo de 300 s por llamada. Python sigue en el sandbox local sin
red ni credenciales, con una ejecución simultánea. Los límites del grafo se
mantienen. No se corrige manualmente ningún programa ni informe generado.

Las referencias se calculan desde el CSV con Decimal, fuera del contexto de los
agentes. La evaluación independiente inspecciona definiciones, preguntas,
programas, conversación, narrativa, cifras, tarjetas y etiquetas/valores/orden de
las visualizaciones. La aprobación del modelo no determina la aceptación. Los
informes materialmente incorrectos se retienen, conservando la decisión original.

Los logs, llamadas, tokens, código generado, informes y evaluaciones particulares
permanecen en `.local/evaluation/luna-validation-01`, fuera de Git. Cada fase
registra la huella del código ejecutado; no se cambia el código durante el lote.

## Incidencias encontradas en la matriz inicial

- **DR-016:** preguntas redundantes sobre una medida ya definida como agregada por
  producto y fecha. Una respuesta «no lo sé» a esa pregunta adicional hizo retirar
  resultados monetarios que sí eran calculables. Se retuvo el informe aprobado
  incorrectamente; la aprobación original se conserva como evidencia.
- **DR-017:** el analista asignó a un gráfico una unidad distinta de la serie
  referenciada. El contrato lo bloqueó correctamente, pero no pudo terminar.
- **DR-018:** el contrato rechazó explicar una investigación bloqueada junto a
  otra respondida. Los importes se habían retirado correctamente ante una
  definición desconocida; el rechazo era excesivo.
- **DR-019:** series de una sola categoría rechazadas reiteradamente. El
  diagnóstico genérico recomendaba agregar periodos incluso cuando faltaban
  puntos, y un caso agotó sus intentos.

El ordenador entró en reposo durante la matriz. La llamada afectada de
`unit-price-2` acabó en un timeout después de despertar. Su intento original se
conserva como fallido: no se sustituye por el resultado de una recuperación. Su
tiempo no debe mezclarse con la latencia normal del modelo. Para terminar los
lotes siguientes se inhibe únicamente el reposo automático mientras dura el
proceso de validación.

También hay mejoras menores de presentación: algunos resúmenes de totales no
indican el rango de fechas, aunque puede calcularse; ciertas cantidades aparecen
con decimales innecesarios. No alteran los totales solicitados, pero conviene
mejorarlas antes del piloto.

## Resultado inicial

**27 de 36 aceptados independientemente.** Los otros nueve se mantienen como
fallos de esa versión; una recuperación o corrección posterior no cambia ese
resultado histórico. Todas las fases conservaron la misma huella de código.

| Escenario | Aceptados / intentos iniciales | Observación |
|---|---:|---|
| Ventas diarias | 3 / 3 | Totales por periodo y cifras adicionales contrastados. |
| Diarias, columnas renombradas | 3 / 3 | Misma referencia independiente. |
| Productos | 3 / 3 | Ranking, importes y etiquetas comprobados. |
| Productos, columnas renombradas | 1 / 3 | DR-016 y DR-017. |
| Importe unitario | 2 / 3 | Un timeout tras reposo; recuperación separada. |
| Importe total de fila | 3 / 3 | Pregunta pertinente y fórmula correcta. |
| Respuesta desconocida | 0 / 3 | DR-018 bloquea la entrega de un resultado parcial válido. |
| Rechazo a responder | 0 / 3 | DR-018 en dos casos; DR-019 en otro. |
| Duplicados técnicos | 3 / 3 | 13 filas → 12 líneas únicas; 1.220 y 59 unidades. |
| Importes vacíos | 3 / 3 | Subtotal conocido 870; 59 unidades de todas las filas; total monetario desconocido. |
| Devoluciones | 3 / 3 | Netos 1.195 y 58; se conservan negativos. |
| Fechas/importes inválidos | 3 / 3 | 21 de 24 filas incluidas; 69.494,35; exclusiones explícitas. |

Las preguntas del evaluador contestan con la definición asignada al escenario
solo cuando se pregunta por la base del importe. Otras preguntas reciben
`unknown`; el evaluador no ayuda al agente con cifras, métodos o preferencias.

### Recuperación real

`luna-recovery-01` reanuda la revisión original de `unit-price-2`, con la misma
versión de código y reintento explícito de la petición incierta. Termina en
**26,803 s**, con tres llamadas nuevas al modelo y **cero ejecuciones nuevas de
Python**. Las respuestas del propietario y las observaciones guardadas coinciden
exactamente antes y después. El informe obtiene 1.220 y 59, y pasa la revisión
independiente. Volver a reanudar la revisión aprobada no añade llamadas.

### Tiempo y recursos iniciales

Excluyendo el intento afectado por reposo, la mediana de la suma de tiempos de
fase es **64,33 s**, con rango **33,06–126,57 s**. No equivale al tiempo de pared
de todo el lote ni incluye todos los costes de arranque de procesos. En esos
35 intentos se registran **2.252,6 s de llamadas al modelo** frente a **32,059 s
de ejecución Python**: el trabajo del modelo domina claramente en estos fixtures
pequeños. No es una medida de escalabilidad sobre archivos grandes.

La matriz registra 283 llamadas, 16 solicitudes `revise`, 17 ejecuciones Python
con salida fallida y una llamada incierta sin uso informado. Muchos fallos de
Python son resultados rechazados por contener series de un punto y se corrigen
autónomamente; no todos provocan un fallo final. Se conservan también los
intentos inválidos de generación y no se contabilizan como devoluciones del revisor.

El uso conocido suma 2.187.144 tokens de entrada y 259.605 de salida. La estimación
del uso informado es **0,3712 USD**, sin atribuir coste cero a la llamada sin
respuesta. Es un subtotal estimado, no la factura ni un total exacto. Se distingue
entrada ordinaria, caché leída y caché escrita; no se suman de nuevo los tokens de
razonamiento incluidos en la salida. Ninguna llamada superó 24.238 tokens de entrada.

Precios estándar de contexto corto usados: entrada 0,10 USD/millón, caché leída
0,01, caché escrita 0,125 y salida 0,50, consultados en la
[documentación del modelo](https://developers.openai.com/api/docs/models/gpt-6-luna)
y [precios](https://developers.openai.com/api/docs/pricing). La separación de tokens
se aplica según la [guía de caché](https://developers.openai.com/api/docs/guides/prompt-caching).

## Correcciones y comprobación posterior

Se ajustan las instrucciones genéricas y los contratos, sin incluir cifras ni
nombres de los fixtures en las reglas del agente:

- `planning-v6` y `review-v10` distinguen medidas agregadas ya definidas de importes
  individuales ambiguos, y conservan definiciones explícitas no contradichas.
- El esquema empareja cada serie con su unidad guardada. El control del servidor
  sigue rechazando unidades distintas y evidencia obsoleta u omitida.
- La cobertura requiere todas las investigaciones listas y permite explicar una
  bloqueada solo como no disponible, sin afirmaciones de respuesta.
- `research-v7` y el diálogo piden escalares cuando hay un único grupo. El error
  indica qué serie tiene pocos puntos, en lugar de sugerir agregarla aún más.

Las pruebas específicas reprodujeron los defectos antes del cambio y pasan
después. La suite completa pasa **141 pruebas** con PostgreSQL y Docker reales;
los modelos de esa suite son simulados. Se comprueban aparte las llamadas reales
a Luna, sin confundir ambos tipos de evidencia.

La huella de las fuentes Python iniciales es
`17d6ffa4b4bdc5a50a734e43d734ca1f2a1421a259ca6d0c271ff074b4b432c5`;
la de la repetición con correcciones es
`ef42a3eaad7022b48aee631d0c7f40baee18ee86fda2b292eab6f3dafd5c5d58`.
Los manifiestos conservan configuración y hashes de entradas. Se guardan parches
locales de ambas versiones contra el commit de partida `9f8dbf7`; se verificó que
el parche inicial reconstruye exactamente su huella. El commit final representa
las correcciones realmente guardadas, no un estado histórico reconstruido.

### Repetición dirigida: 18 de 18

`luna-regression-02` repite tres veces cada uno de seis escenarios: productos con
columnas renombradas, precio unitario, total de fila, respuesta desconocida, rechazo
a responder y devoluciones. **Los 18 informes pasan la revisión independiente.**
No sustituye a la matriz inicial de 36 ni representa una nueva matriz completa: los
otros seis escenarios no se repitieron con esta versión. Son datos de calibración
conocidos, no un conjunto nuevo y ciego de generalización.

| Comprobación posterior | Resultado |
|---|---|
| Medida agregada con columnas renombradas | 3/3; sin preguntas redundantes. |
| Precio unitario | 3/3; pregunta pertinente, 1.220 y 59 unidades. |
| Total de fila | 3/3; pregunta pertinente, 257,50 y 59 unidades. |
| Respuesta desconocida | 3/3; cantidades correctas, importe no disponible. |
| Rechazo a responder | 3/3; respeta la respuesta y entrega la parte sustentada. |
| Devoluciones | 3/3; importes y unidades netos correctos. |

Se registran 148 llamadas, ocho solicitudes de revisión, dos ejecuciones Python
fallidas con recuperación autónoma y ningún fallo de API. La mediana de tiempos
de fase es **56,57 s**, con rango **35,73–101,78 s**. Las llamadas suman
1.032,49 s y Python 16,271 s. Esta selección es diferente de la matriz inicial;
no se atribuye toda diferencia de tiempo al cambio de código.

Uso informado completo: 1.168.725 tokens de entrada y 121.565 de salida; coste
estimado **0,19513 USD** con los mismos precios. Ninguna llamada supera 20.767
tokens de entrada. El coste de esta repetición se suma al inicial, no lo reemplaza.

Los reintentos residuales son `unit-price-2` y `declined-3`: el programa exige al
menos dos productos aunque solo hay uno. Ambos se corrigen sin intervención y
terminan correctamente. En varios casos el revisor solicita guardar la identidad
y las cantidades del único producto como escalares; eso evita inferir una etiqueta
sin evidencia, pero añade trabajo que conviene resolver desde la investigación.
DR-019 permanece parcialmente mitigado, no cerrado como clase general de fallo.

### Correcciones del propietario: 3 de 3

Los lotes `luna-correction-01`, `02` y `03` reutilizan respectivamente las
importaciones de los tres casos `unit-price` de la repetición. El propietario
corrige la definición a total de fila. **Los tres informes nuevos pasan**, con
257,50 en lugar de 1.220, conservando las 59 unidades. No se vuelven a solicitar
definiciones ya proporcionadas.

Las tres aprobaciones anteriores quedan `stale`, no publicables, y se exportan
como bloqueadas. Los informes nuevos usan cálculos nuevos y su reanudación
aprobada no añade llamadas. Las evaluaciones históricas del precio unitario se
conservan: fueron correctas bajo la definición que después cambió; sus snapshots
no constituyen aprobaciones vigentes tras la corrección.

Duraciones: 32,503, 83,023 y 46,120 s. El segundo caso recibió dos devoluciones;
el revisor además ejecutó su propio cálculo para comprobar que las 12 cantidades
no eran negativas ni fraccionarias. Los otros dos se aprobaron directamente.
Ninguna corrección tuvo un fallo de ejecución o API. El coste estimado conjunto
de las tres es 0,032795 USD, contabilizando únicamente ejecuciones nuevas.

### Balance y límites para avanzar

Se completaron la matriz inicial, la repetición dirigida, una recuperación real y
tres cambios de definición. Son **36 intentos iniciales + 18 repeticiones + tres
correcciones**, además de la recuperación de una sesión existente. En conjunto
se registran 459 llamadas, de las que una no informa uso. El coste estimado del
uso conocido es **0,6048 USD**; los consumos de recuperación y corrección no se
duplican con sus historiales. La factura completa sigue siendo desconocida.

La ronda previa a entrega 3 queda terminada y permite continuar el desarrollo por
escenarios acotados, conservando revisión y evidencia. **No constituye aceptación
general del MVP ni autorización del piloto comercial.** Quedan abiertos:

- Intentos ocasionales innecesarios con un único grupo y revisiones de presentación
  que podrían evitarse guardando evidencia suficiente desde la investigación.
- Variación en la presentación del periodo, precisión numérica y cantidad de gráficos.
- Evaluación con datos nuevos no usados para ajustar las instrucciones, diferentes
  sectores y archivos reales: estos fixtures pequeños no prueban generalización,
  escalabilidad ni un tiempo constante de informe para cualquier volumen.

Las capacidades de Excel, múltiples tablas, tickets e investigación web siguen
requiriendo sus propios escenarios de entrega 3. La prueba anterior de 36.331
filas se conserva como evidencia separada; no se ha repetido aquí con las nuevas
instrucciones. En esta ronda el recorrido web se comprueba mediante las pruebas
de integración; no se atribuye una nueva inspección visual con Computer Use.
Al terminar se reinicia el servidor local con las correcciones, sin interrumpir
análisis activos, y se comprueba que la página responde con HTTP 200.

## Reproducción de las comprobaciones

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m decision_room.evaluation.runner run .local/evaluation/luna-regression-new \
  --model gpt-6-luna --protocol openai --reasoning low --max-output-tokens 16384 \
  --scenario products-renamed --scenario unit-price --scenario line-total \
  --scenario unknown --scenario declined --scenario returns
.venv/bin/python -m decision_room.evaluation.assess .local/evaluation/luna-regression-new
```

El último comando conserva los casos pendientes de inspección como no aceptados;
no sustituye la evaluación independiente de cada informe. Las 141 pruebas pasan,
y las ocho pruebas de referencias se repitieron tras ampliar el caso de evidencia
omitida. `git diff --check` no detectó errores de formato. Estado y datos privados
se conservan localmente; Git contiene únicamente código, pruebas, documentación
y fixtures públicos pequeños.
