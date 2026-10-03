# Autopsia de calidad y diseño de pruebas: Decision Room frente a Luna en Codex

Fecha: 3 de octubre de 2026. Estado: **diagnóstico y diseño**. No cambia el
producto. Las pruebas de línea base aún no se han ejecutado; este documento fija
qué se mide y qué resultado refutaría cada propuesta **antes** de verlos.

Otra investigación paralela (GPT-6 Astra, en la rama
`codex/feature/bruma-web-integration`) analiza las mismas trazas. Sus conclusiones
se contrastarán con estas antes de lanzar las pruebas; las discrepancias se
documentarán, no se resolverán eligiendo la opinión preferida.

## 1. Material examinado

- Piloto 3.9.9.2 de Decision Room con el encargo exacto de Luna: intento
  interrumpido (57 llamadas) y repetición aprobada parcial (16 llamadas, 3
  ejecuciones de cálculo, 2 completadas). Contextos persistidos, salidas, código,
  resultados, informe HTML y presupuestos.
- Seis sesiones de Luna en Codex CLI (`gpt-6-luna`, esfuerzo `low`) con eventos
  JSONL, comandos, salidas e informes. Detalle principal: ronda 2, ejecución 2
  (23/24, mejor resultado) y ejecución 3 (15/24).
- Prompts y contratos del producto en la revisión `4815b68`.

Véanse la [comparación Luna](2026-10-02-codex-luna-comparison.md) y el
[piloto con encargo exacto](2026-10-02-agent-visual-freedom-pilot.md). Las trazas
permanecen locales e ignoradas por Git.

## 2. Resultado principal

El modelo es el mismo y el volumen de entrada es parecido: la repetición del
producto usa 348.395 tokens y 246 s; la mejor sesión de Luna, 342.513 y 263 s. No
implica trabajo ni coste equivalentes: buena parte de la entrada de Luna es caché
y transporte e instrucciones difieren. Sí indica **en qué se gasta**: Luna, en
calcular y leer agregados; el producto, en reenviar reglas y contexto estructurado.

La pérdida **empieza** en la investigación y no por falta de presupuesto: la
repetición usó 7 de 192 turnos y 3 de 48 ejecuciones. Redacción y revisión
podían recuperarla (tenían Python) y no lo hicieron.

## 3. Seguimiento de una señal concreta

Señal más útil para el propietario de Bruma: entre julio y agosto la tienda
física baja de 621 a 528 unidades (−93; −15,0 %), con cinco de sus seis productos
en descenso, mientras web (+237) y marketplace (+332) crecen.

| Paso | Luna en Codex (ronda 2, ejecución 2) | Decision Room (repetición) |
| --- | --- | --- |
| Exploración | Quinto comando: imprime mes×canal, totales por producto y canal, semanas. Octavo comando: cambio por canal julio–agosto (−93, +237, +332). | Dos programas: totales mensuales y diferencias mensuales de las 18 combinaciones. Nunca agrega por canal. |
| Registro | No aplica: el mismo agente sigue razonando con todo a la vista. | 16 métricas guardadas; 14 son validaciones (filas, nulos, duplicados, rango). El resumen dice «No propongo ampliar este análisis local». |
| Priorización | Prioridad 1: caída extendida en tienda. Luego Kit–Web y Café–Marketplace. | El planificador ordena +118 > +100. Es el ranking por volumen que su prompt prohíbe. En el intento interrumpido vio caídas en junio–agosto (máximo −24) y las descartó «por magnitud». |
| Redacción | El mismo agente escribe con las cifras que calculó. | El redactor solo cita números guardados y −93 no lo estaba. Tenía Python y seis ejecuciones para calcularlo y no usó ninguna: el contrato eleva la fricción, no lo impide. |
| Revisión | Autoverificación con asserts de reconciliación. | Aprobado con todos los criterios en `pass`; no se comprueba si falta una señal mayor. |

## 4. Causas probables, de mayor a menor peso

Son hipótesis apoyadas por las trazas, no causas aisladas por experimento. El
diagnóstico de Astra (`2026-10-03-report-quality-forensics.md`, commit `8a2e66f`
en `codex/feature/bruma-web-integration`) señala con razón
que no hay evidencia para atribuir la diferencia al número de agentes o al tamaño
de los prompts por separado; las fases de la sección 8 los aíslan uno a uno.

1. **Mirar es caro en el producto y barato en Codex.** Cada ejecución exige
   `write_result` con 3–8 métricas escalares, una evidencia por métrica,
   assertions y registro de candidato antes de ampliar. Imprimir para explorar
   «no es un resultado». El agente minimiza las veces que mira y llena métricas
   con validaciones. Luna imprime tablas de agregados (no filas) y decide después.
2. **La evidencia llega al que decide poco preparada para usarse.** El coordinador
   tenía los 18 cambios y podía obtener −93; faltaba el agregado listo y nadie
   decidió calcularlo. Cada llamada es independiente (`store=False`, un mensaje de
   sistema y otro con el contexto JSON), sin razonamiento persistente; cinco roles
   se pasan resúmenes y el investigador cierra sin interpretar. Codex mantiene un
   único bucle continuo.
3. **Prompts enormes y defensivos.** Sistema de investigación ≈ 5.000 palabras,
   planificador ≈ 2.350, analista ≈ 7.050, revisor ≈ 7.270, acumulados como parches
   «Do not…». El encargo de Luna tenía ≈ 350 palabras sobre las instrucciones de
   Codex. La salida refleja cautela, no análisis: la reacción final es «mantener
   el aumento como señal descriptiva» y cada comprobación añade «si existen».
4. **Texto no dirigido a un propietario no técnico.** El informe muestra
   «P06×WE», «unidades registradas de cambio», «118.0000» y
   «51.36666666666666666666666667». Luna titula «Revisar primero la caída
   extendida en tienda física».
5. **La entrega HTML contamina la investigación.** El intento interrumpido gasta
   seis ejecuciones efectivas intentando generar HTML. En la repetición, el analista
   comunica al cliente que no puede afirmar que exista `informe.html`, aunque la
   aplicación lo exporta después.
6. **El revisor valida campos, no omisiones.** Aprueba orientación, reacciones y
   cifras sin comparar el informe con lo que los datos muestran a nivel agregado.

Lo que **no** explica la diferencia: el modelo, el esfuerzo de razonamiento
(ambos `low`) ni los presupuestos.

## 5. Lo que hay que conservar del producto

Luna sola no es fiable. En la ronda 2, dos de tres sesiones tienen cifras
erróneas o gráficos rotos; ninguna de las seis nuevas pasa todos los criterios de
entrega. La verificación de cifras, el rastro de evidencia, la exportación
controlada y el aislamiento del cálculo son valor del producto. El objetivo es
un híbrido: **libertad de exploración como en Codex y garantías al final**.

## 6. Propuestas (hipótesis a probar, no decisiones)

| # | Cambio | Hipótesis comprobable | Coste |
| --- | --- | --- | --- |
| P1 | Panorama determinista de los datos antes de investigar: totales por dimensión × periodo, subidas y bajadas, último periodo frente al anterior y al mismo del año previo, día de la semana, huecos de fechas. Calculado por código, sin modelo. | Aumenta la detección de señales plantadas, en especial las que van contra el total. | Bajo |
| P2 | Revisor crítico con comprobaciones propias: puede calcular, contrastar alternativas materiales y pedir justificación de un descarte. No bloquea mecánicamente por cada movimiento de signo contrario. Independiente de P1; solo el brazo con panorama le da ese panorama. | Reduce aprobaciones sin justificar frente a una alternativa material. | Bajo |
| P3 | Sacar el HTML del contexto de investigación; redacción para un no técnico (sin IDs, cifras redondeadas, cautelas una vez, reacciones de negocio condicionadas). | Mejora claridad y orientación sin empeorar cifras. | Bajo-medio |
| P4 | Exploración provisional: consulta Python/SQL que devuelve una tabla o salida acotada sin exigir ficha de hallazgo. Se registra todo (consulta, fuentes, resultado, errores, truncados); lo que apoye una conclusión se promueve a evidencia verificable en el momento en que se vuelve material, y la entrega se comprueba al final. Variante posterior: bucle continuo con razonamiento conservado. | Más contrastes útiles por señal manteniendo 0 errores numéricos publicados. | Medio-alto |
| P5 | Planificador reducido a encargo inicial y crítica final; prompts reescritos (≈ 1.000 palabras por rol). | Menos tokens por llamada sin pérdida de calidad. | Medio |

Orden acordado con Astra: sección 8, «Fases».

## 7. Escala: por qué Bruma no basta

Bruma tiene 1.656 filas, 92 días, 6 productos y 3 canales: cabe entero en una
salida de terminal. Un propietario puede subir cinco años. Riesgos esperados:

- **Luna en Codex:** su ventaja es leer agregados completos de un vistazo. Con
  cientos de combinaciones y años de fechas tendrá que seleccionar; previsiblemente
  aumenta la variabilidad, los errores de agregación y la compactación de contexto.
- **Decision Room:** el cálculo escala (DuckDB, agregados), pero crece el riesgo de
  perder señales en los traspasos y de comparar ventanas inadecuadas (meses
  consecutivos frente a estacionalidad anual). La especialización en varios
  agentes podría ayudar con datos amplios; es una hipótesis a medir, no un supuesto.

## 8. Diseño de las pruebas

### Conjuntos de datos

1. **Bruma (pequeño):** los cuatro CSV congelados y el encargo de la ronda 2, con
   los hashes publicados en la comparación Luna.
2. **Albor Café (grande, generado):** negocio ficticio y datos sintéticos; cinco
   años diarios (septiembre de 2021 a agosto de 2026), 30 productos y 4 canales.
   Generador determinista con semilla en
   [`decision_room/evaluation/trial_data.py`](../../decision_room/evaluation/trial_data.py).
   Incluye señales plantadas cuya verdad se calcula desde los propios CSV y se
   guarda en un oráculo fuera de la carpeta de entradas. El oráculo separa la
   **verdad del generador** (la causa plantada), lo **deducible de los archivos**
   y las **comprobaciones razonables**. No contiene un orden de prioridad: varias
   prioridades pueden estar justificadas, y una causa plantada no es exigible si
   los archivos no la identifican.

| Clave | Señal | Deducible de los archivos |
| --- | --- | --- |
| S1 | Desde el 7 de junio de 2026 la tienda casi no registra unidades en domingo, en todos los productos. | Caída de tienda frente al año anterior aunque el total crece; concentrada en domingos desde una fecha. El motivo no se deduce. |
| S2 | Hostelería deja de registrar un producto a partir de abril de 2026. | Desaparición de una combinación; comprobar cliente o pedido recurrente. |
| S3 | Un molinillo eléctrico salta en web desde mediados de junio de 2026. | Oportunidad concreta; comprobar stock y origen del aumento. |
| S4 | Marketplace no tiene registros del 10 al 18 de marzo de 2026. | Nueve días sin ninguna fila del canal; no distingue fallo de extracción de canal inactivo. |
| S5 | Un descafeinado pierde ≈ 2,5 % mensual desde marzo de 2025 en todos los canales. | Erosión lenta que solo se ve con horizonte largo. |
| S6 | El café frío triplica en verano todos los años (señuelo). | Estacional; no presentarlo como novedad por comparar mayo con junio. |

### Sistemas y repeticiones

- **Luna en Codex:** mismo comando que la comparación Luna (CLI, `gpt-6-luna`,
  esfuerzo `low`, sin búsqueda ni agentes secundarios), carpeta aislada por sesión.
- **Decision Room:** código congelado con `git archive` en la revisión indicada,
  base de datos y almacenamiento nuevos por lote, mismo modelo y esfuerzo.
- Orden intercalado y ejecución en serie, para no mezclar 429 con calidad.
- **El sandbox de Codex lee todo el disco del usuario** (comprobado: un comando
  dentro de `codex sandbox` lee un archivo de la carpeta superior). Por eso los
  oráculos no se guardan junto a las entradas ni dentro del lote; se pasan solo
  al puntuar. Los comandos de Luna que nombran rutas fuera de su carpeta se
  marcan como **diagnóstico, no como garantía**: no bloquean el acceso ni detectan
  rutas construidas dentro de un programa. En la evaluación reservada, oráculo,
  generador y claves permanecen inaccesibles hasta puntuar. El producto calcula
  en Docker con solo sus entradas autorizadas.

Lanzador: [`decision_room/evaluation/trials.py`](../../decision_room/evaluation/trials.py).
Los resultados se guardan en una carpeta local ignorada; cada intento conserva su
estado aunque falle y nunca se relanza un intento ya iniciado.

### Medidas

1. **Recursos:** segundos, llamadas o comandos, tokens de entrada y salida, fallos.
2. **Señales:** por señal, detectada / cifra correcta / lectura correcta según lo
   deducible (en S6, no presentarla como novedad); falsas alarmas y señales útiles
   fuera del oráculo. La herramienta marca indicios por texto; la puntuación final
   es humana y se registra por separado.
3. **Prioridad útil, separada del ranking:** ¿la prioridad elegida está justificada
   frente a una alternativa material? Se acepta cualquier orden bien justificado.
4. **Fidelidad:** cifras y rankings narrados coinciden con lo calculado.
5. **Decisión del lector:** quien lee responde qué haría primero y qué comprobaría.
6. **Rúbrica 3.9:** doce criterios 0/1/2 de la evaluación existente.
7. **Lectura para no técnicos:** identificadores internos, decimales crudos y
   repetición de cautelas.
8. **Render real:** JavaScript sin errores, tablas no vacías, etiquetas
   distinguibles, móvil. La evaluación ciega del texto (copias sin marca) y la del
   informe completo con su interfaz se hacen por separado.

### Fases

Acordadas con Astra. Cada intervención va detrás de una opción separable, para
compararla sobre la misma base sin reconstruir todo entre ensayos.

| Fase | Intervención sobre la anterior | Producto candidato | Producto de referencia congelado | Luna |
| --- | --- | --- | --- | --- |
| 0. Línea base | `4815b68` sin cambios | 3 × conjunto | — | 3 × conjunto |
| 1. Contratos | Astra A: capas en el esquema productor, exportación sin ambigüedad, errores de artefacto distintos, rango invariante al orden, etiquetas distinguibles, registro de sistema/esquema/correcciones efectivos. Filtrado primero con tests; esta versión pasa a ser la referencia. | 3 × conjunto | — | 1 × conjunto |
| 2. Continuidad | Seguir una señal sin cerrar ni reabrir tarea; nota de cierre: qué cálculo pendiente cambiaría la decisión. | 3 × conjunto | 1 × conjunto | 1 × conjunto |
| 3. Exploración | P4: consulta provisional registrada, promoción de evidencia al volverse material. | 3 × conjunto | 1 × conjunto | 1 × conjunto |
| 4. Revisión | P2: revisor que calcula, contrasta alternativas y acepta descartes justificados. | 3 × conjunto | 1 × conjunto | 1 × conjunto |
| 5. Panorama | P1 como brazo sobre la base de la fase 4. Declara qué cubre y qué omite; permite investigar fuera de él; se miden aciertos, omisiones y falsas alarmas. | 3 × conjunto | 1 × conjunto | — |
| 6. Presentación | P3 + Astra D: lenguaje para propietario no técnico, una idea una vez, verificación real del render. | 3 × conjunto | 1 × conjunto | 3 × conjunto |
| 7. Variantes | Una a una, si compensan: bucle continuo/Responses, prompts consolidados (P5), esfuerzo de razonamiento, reparto de agentes. | 3 × conjunto | 1 × conjunto | — |

Conjuntos de desarrollo: Bruma y Albor. Un control único de Luna es una alarma de
cambios del entorno, no una medida de calidad estable. Ante una decisión dudosa
se amplían repeticiones antes de elegir; se conservan dispersión y fallos y nunca
se presenta la mejor de tres como rendimiento.

Repeticiones acordadas: Bruma 3 en línea base y candidato final y 1 en las fases
intermedias; Albor 3 por variante. Bruma se amplía a 3 ante una regresión o un
resultado ambiguo. Una cifra incorrecta o un gráfico roto se investiga como fallo,
no se repite hasta obtener una entrega buena.

| Alcance | Ejecuciones |
| --- | ---: |
| Fases 0–6 | 62 (42 producto, 20 Luna) |
| Con una variante opcional de fase 7 | 68 |
| Reservado final | +9 |

A 4–15 min por ejecución del producto, unas 2,8–10,5 h de producto más Luna,
esperas, implementación y evaluación. La línea base en Albor sirve para afinar
esta estimación antes de comprometer las variantes opcionales.

Reparto: Astra implementa la fase 1 en `codex/fix/report-quality-contracts`
desde `4815b68` (incluida una solución general de invariancia al orden, no la
corrección de un programa histórico); este plan mantiene el lanzador y ejecuta la
línea base congelada con instantáneas y entornos separados.

### Negocio reservado

Diseñado por Astra: otro tipo de negocio, otra estructura y otra pregunta. Se
congelan antes el protocolo, la rúbrica y las propuestas. Generador, semilla, CSV,
prompt y oráculo se guardan con huellas y **fuera de cualquier ruta legible por
los agentes** (en la práctica, fuera de la máquina o cifrados hasta la ejecución,
porque el sandbox de Codex lee el disco). No se usa en desarrollo ni se comunican
resultados intermedios. Se ejecuta una sola vez, al final: 3 × producto con
contratos reparados, 3 × candidato final y 3 × Luna. Lo puntúan al menos dos
personas además de quien lo diseñó, incluido el propietario como lector. Si
después se usa para corregir el producto, pasa a ser desarrollo y hará falta otro.

### Uso

```sh
python -m decision_room.evaluation.trial_data albor TRIALS/inputs/albor EVALUATORS/albor.json
python -m decision_room.evaluation.trial_data bruma BRUMA_FROZEN TRIALS/inputs/bruma EVALUATORS/bruma.json
python -m decision_room.evaluation.trials prepare TRIALS/baseline \
    --dataset bruma=TRIALS/inputs/bruma --dataset albor=TRIALS/inputs/albor \
    --product-ref 4815b68 --repeats 3 --env-file PRIVATE_ENV
python -m decision_room.evaluation.trials run TRIALS/baseline
python -m decision_room.evaluation.trials score TRIALS/baseline \
    --oracle bruma=EVALUATORS/bruma.json --oracle albor=EVALUATORS/albor.json
python -m decision_room.evaluation.trials summary TRIALS/baseline
```

`prepare` congela el código, crea base de datos y almacenamiento nuevos, migra y
comprueba el sandbox sin llamar al modelo. `score` solo calcula indicadores
automáticos: recursos, indicios de texto por señal e identificadores internos o
decimales crudos visibles. Además deja una plantilla `evaluation.json` para la
puntuación humana, que es la que cuenta. `TRIALS` debe estar en una carpeta
ignorada por Git.

`EVALUATORS` es una carpeta fuera de `TRIALS` y fuera del repositorio.

Qué refutaría cada intervención en desarrollo: no mejorar la prioridad útil ni
las señales deducibles frente a su fase anterior, aumentar falsas alarmas o
publicar alguna cifra errónea. La aceptación general exige además fidelidad,
utilidad del siguiente paso para el lector y el resultado del negocio reservado;
detectar en Albor lo que el panorama fue diseñado para ver no valida generalización.

## 9. Contraste con el diagnóstico de Astra

Astra (GPT-6) investigó las mismas trazas por separado. Coincidimos en el núcleo:
cifras correctas, cierre prematuro sin presión de presupuesto, el −93 de tienda
calculable con lo que ya estaba en el contexto, ranking +118 > +100 convertido
en prioridad, revisor que aprueba sin reparos y HTML mal comunicado. Comprobado en
el código: las variantes de gráfico del esquema productor no incluyen capas, y
el eje recorta las etiquetas a 20 caracteres.

**Incorporado de Astra a este plan:**

1. Defectos deterministas que no había encontrado: capas imposibles en el esquema
   productor; error idéntico para extensión no admitida y nombre duplicado; rango
   temporal dependiente del orden de filas; 18 etiquetas convertidas en 8 textos
   distintos; registro sin sistema, esquema ni correcciones efectivos. Pasan a la
   fase 1, antes de tocar comportamiento.
2. El investigador no puede ejecutar de nuevo tras un resultado correcto sin
   registrar y reabrir mediante el coordinador. Concreta mi causa 1 en el punto
   exacto del grafo. El redactor y el revisor disponían de seis ejecuciones Python
   cada uno y usaron cero.
3. Rúbrica: separar «ranking correcto» de «prioridad útil»; añadir fidelidad entre
   cálculo y relato (el fallo de Luna en la ronda 2, ejecución 3); preguntar al
   lector qué haría primero y qué comprobaría; puntuar sin conocer el sistema.
4. Ejecuciones de Luna aisladas: algunas sesiones concurrentes reutilizaron
   nombres fijos en `/tmp`. El lanzador ya ejecuta en serie, con `TMPDIR` propio
   por ejecución, y marca los comandos que usan `/tmp` igualmente.
5. Verificación real del render (JavaScript, tablas vacías, etiquetas
   indistinguibles, móvil) en la puntuación y, más adelante, en el producto.
6. Presión de tokens por minuto como factor de confusión: el producto se ejecuta
   en serie y los 429 se registran por intento.

**Lo que este plan añade al de Astra:**

1. **Escala.** Bruma cabe en una pantalla. Albor (5 años, 30 productos, 4 canales)
   prueba ambos sistemas donde no se puede mirar todo.
2. **Señales plantadas con verdad conocida**, incluido un señuelo estacional, para
   medir detección y no solo exactitud de las cifras citadas.
3. **Panorama determinista (P1)** como brazo separado: no es una regla más para
   el agente, sino un cálculo previo por código.
4. **Riesgo de circularidad propio:** las señales de Albor (domingos, huecos,
   desapariciones) son justo lo que P1 detectaría. Por eso se pide a Astra un
   tercer negocio cuyas señales no conozca el autor de P1, con su oráculo guardado
   fuera de este análisis. Simétricamente, Astra no debería ajustar sus propuestas
   mirando Albor.
5. **Lectura para un propietario no técnico** como criterio propio, no solo como
   ausencia de repetición.
6. **El bucle continuo (P4)** como variante a probar, no a descartar: el
   planificador produce más tokens de salida que la investigación (8.126 frente a
   7.913) y los contextos de redacción y revisión superan los 100 KB.

**Resuelto en la discusión** (revisión de Astra, commit `644df24`):

- Continuidad y exploración barata son hipótesis distintas y se miden en fases
  separadas. Provisional no significa sin registro, y la evidencia se promueve
  cuando se vuelve material, no en un único programa final.
- El panorama orienta la atención aunque lo calcule código: brazo propio, con
  cobertura declarada y medida de omisiones y falsas alarmas.
- El revisor no bloquea mecánicamente; P2 ya no depende de P1.
- El negocio reservado se abre una sola vez, al final.
- Matices aceptados sobre el diagnóstico: la señal estaba al alcance del
  coordinador, del redactor y del revisor; seis ejecuciones efectivas de HTML, no
  siete; tokens parecidos no significan coste equivalente.
- Sin `priority_rank` fijo en el oráculo.
- Presupuesto y reparto: adenda de la revisión de Astra, commit `0f41cf5`.

## 10. Límites

Tres repeticiones son pocas para afirmar consistencia; sirven para detectar
diferencias grandes. Albor es sintético y sus señales las diseñó el mismo autor
del análisis: hay riesgo de que el diseño favorezca las propuestas. Por eso las
señales y su lectura esperada se fijan aquí, antes de cualquier ejecución, y se
incluye un señuelo. Autenticación, transporte y límites de Codex CLI y de la API
del producto difieren; no se infiere coste API de los tokens CLI.
