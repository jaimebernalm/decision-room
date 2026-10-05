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

## 11. Resultados: línea base y fase 1

Ejecuciones el 3 de octubre de 2026. Línea base `4815b68`: 12 intentos (más uno
detenido por el operador, conservado como abandonado). Fase 1 `baa0bbb`: Bruma 1
y Albor 3 del producto, Luna 1 por conjunto. Tres evaluaciones independientes de
los 16 informes completados, con aspecto normalizado (misma tipografía, escala de
grises) y códigos aleatorios:

- **Lector:** dos sesiones nuevas de modelo con el papel de dueño no técnico, sin
  ningún dato del experimento; sustituye la lectura del propietario por decisión
  suya. Es una aproximación a un lector real, no un usuario.
- **Técnica:** Astra, a ciegas, recalculando desde los CSV y comprobando render.
- **Señales:** este autor frente al oráculo. **No ciega.** Una detección por código
  de producto (`P02`) se corrigió tras leer la evaluación del lector.

| Conjunto · sistema (línea base) | Informes | Cifras erróneas / informe | Fidelidad 0–2 | Prioridad justificada 0–2 | Rúbrica /24 | Lector: entiende 1–5 | Lector: confía 1–5 | Lector: puesto medio |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Bruma · Luna | 3 | 3,3 | 0,7 | 1,0 | 16,7 | 3,7 | 3,3 | 3,0 de 7 |
| Bruma · producto | 2 | 0,5 | 1,0 | 0,5 | 15,0 | 2,5 | 2,0 | 6,5 de 7 |
| Albor · Luna | 3 | 0,7 | 0,7 | 1,0 | 17,0 | 3,7 | 3,0 | 3,3 de 9 |
| Albor · producto | 3 | 0,0 | 2,0 | 0,7 | 17,7 | 2,3 | 1,7 | 7,7 de 9 |

Fallos sin informe: el producto pierde 2 de 10 intentos (uno por fase) porque una
salida del modelo no pasa la validación dos veces seguidas (evidencia obsoleta en
el planificador; ampliación sin métricas del candidato padre). Luna no pierde
ninguno, pero 3 de sus 8 informes tienen errores de JavaScript que dejan gráficos
vacíos o rotos.

Lectura:

1. **Utilidad para el dueño: gana Luna con claridad.** En Bruma los cuatro
   primeros puestos del lector son de Luna; en Albor, cuatro de los cinco primeros.
   Las quejas sobre el producto son concretas y repetidas: «Entrega parcial · 0 de
   1 entregables», nombres internos en inglés en tablas (`combo_a_june_july_change`,
   `earlier_window_units`), `TRY_CAST`, «Resultados guardados», `188.0000`,
   cautelas repetidas y ventanas de comparación sin explicar.
2. **Exactitud: gana el producto con claridad.** Cero o casi cero cifras erróneas y
   fidelidad máxima en Albor; Luna llega a 4–5 errores por informe en Bruma, con
   cifras contradictorias dentro del mismo informe. El lector baja su confianza
   cuando ve las contradicciones, pero no detecta las que no son visibles.
3. **Prioridad útil: ninguno.** Ambos priorizan por magnitud sin justificar el
   valor de decisión frente a alternativas (media ≤ 1 de 2 en todos los grupos).
4. **Señales:**
   - En Bruma, Luna menciona la caída de tienda en sus 4 informes; el producto, en
     ninguno de sus 3.
   - En Albor nadie localiza la caída dominical de la tienda (S1), el hueco del
     marketplace (S4), el despegue del molinillo en web (S3) ni la erosión del
     descafeinado (S5). La desaparición en hostelería (S2) solo se lee
     correctamente una vez, en el control de Luna de la fase 1.
   - Nadie cae en el señuelo estacional.
   - Con cinco años de datos, ninguno de los dos investiga más allá de comparar
     bloques anuales o mensuales.
5. **Fase 1:** sin efecto apreciable en contenido ni lectura, como se esperaba de
   una reparación de contratos. La cifra relevante es que no empeora la exactitud.

Implicaciones para el orden de las fases: el mayor desfase para el dueño está en
presentación (P3) y, en datos grandes, en descubrimiento (continuidad,
exploración, panorama). P3 son correcciones baratas y concretas que el lector ha
enumerado; conviene no dejarlas para el final. Con tres repeticiones y un lector
simulado, son tendencias de desarrollo, no resultados concluyentes.

## 12. Resultados: fase 2 (continuidad)

- `2cd836e` con continuidad: el esquema de `EvidenceRef` dejaba campos fuera de
  `required` y OpenAI lo rechazaba (HTTP 400) en la primera llamada de
  investigación. Tres intentos retirados sin sustituto. Corregido en `b47c9da`.
- `b47c9da`: 3 de 4 intentos murieron por validación doble (`continuation`
  anulable en el esquema pero exigida por el validador; ampliación con evidencia
  ajena al candidato). Corregido en `af64f48`. La recuperación tras rechazos va
  aparte en `5d3087c`, con su propia opción.
- Lote `phase2c`, intercalado: A = `af64f48` con continuidad; B = `5d3087c` con
  continuidad y recuperación. **8 de 8 completados y aprobados, cero muertes por
  validación** (frente a 3 de 12 en `4815b68`/`baa0bbb`). La recuperación no llegó
  a activarse, así que su efecto no está medido. En Albor se pasa de unos 4 a unos
  9 cálculos por informe. Controles reutilizados del lote `phase2` (referencia
  `baa0bbb` y Luna, horas antes).

Segunda ronda de lectores independientes sobre los 24 informes mezclados. Su
orden coincide con la primera ronda en los 16 comunes (Spearman 0,93 en Bruma y
0,88 en Albor; diferencias medias de puntuación ≤ 0,12).

| Grupo | Albor: puesto (0 mejor) | Albor: entiende / confía | Bruma: puesto | Bruma: entiende / confía |
| --- | ---: | ---: | ---: | ---: |
| Luna | 0,38 | 3,8 / 3,0 | 0,19 | 4,0 / 3,5 |
| Producto línea base | 0,79 | 2,7 / 2,0 | 0,69 | 3,0 / 2,5 |
| Producto fase 1 | 0,64 | 2,5 / 2,5 | 0,50 | 3,0 / 3,0 |
| A · continuidad | 0,45 | 3,0 / 2,7 | 1,00 (n=1) | 3,0 / 2,0 |
| B · continuidad + recuperación | 0,33 | 3,3 / 3,0 | 0,88 (n=1) | 2,0 / 2,0 |

En Albor la continuidad lleva al producto a la altura de Luna para el lector; en
Bruma no mejora, porque allí pesa la redacción y no la profundidad. La diferencia
A/B no es atribuible a la recuperación. Señales (no ciegas): la caída de
hostelería aparece en los 6 informes de Albor con continuidad (frente a 1 de 3 en
la línea base), aunque solo uno dice que no hay registros desde abril, y en un pie
de gráfico. S1, S3, S4 y S5 siguen sin detectarse.

Evaluación técnica a ciegas de Astra (`kits/phase2c/tecnica`, solo esa carpeta),
cruzada con la clave. Medias por informe; rúbrica sobre 24.

| Grupo | n | Cifras comprobadas | Errores | Prioridad justificada (0–2) | Siguiente comprobación (0–2) | Fidelidad (0–2) | Rúbrica |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Albor A · continuidad | 3 | 146 | 0,33 | 1,00 | 1,67 | 1,67 | 16,0 |
| Albor B · + recuperación | 3 | 142 | 0,33 | 0,67 | 1,67 | 1,67 | 15,3 |
| Albor producto línea base | 3 | — | 0 | 0,67 | 2,00 | 2,00 | 17,7 |
| Albor Luna línea base | 3 | — | 0,67 | 1,00 | 2,00 | 0,67 | 17,0 |
| Bruma A / B | 1 + 1 | 9 / 20 | 0 / 0 | 0 / 0 | 1 / 2 | 2 / 2 | 15 / 14 |

- Exactitud: 892 cifras comprobadas, todas coinciden con los datos. Hay dos
  errores de interpretación: un año equivocado al describir pedidos de 2025 y un
  gráfico titulado «cinco mayores descensos» con tres caídas y dos aumentos.
- Más cálculo no ha subido la rúbrica: el producto con continuidad (15,7 en
  Albor) queda algo por debajo de su línea base (17,7). La prioridad sigue
  decidiéndose por magnitud en 5 de 8 informes, y la caída de la tienda física
  (mayor que la de hostelería en la misma ventana) queda como alternativa omitida
  en los 6 informes de Albor. Es el hueco que atacan P1 (panorama) y P2 (revisor).
- El mejor informe (rúbrica 18, prioridad 2) es el único que ordena por
  hostelería sin filas desde abril de 2026, es decir, S2 bien leída.
- Presentación: leyendas solapadas en 4 de 8 gráficos y ningún error de
  JavaScript ni tablas vacías. Pasa a P3.
- La lectura conjunta con los lectores es que la continuidad mejora lo que el
  dueño entiende y cuánto se fía, pero no la calidad del criterio. No la
  empeora de forma significativa (con n = 3 la diferencia de 2 puntos de rúbrica
  queda dentro de la variación entre ejecuciones, de 14 a 18).

Estado: fase 2 cerrada. P3 implementada por Astra en `fbff764` (rama
`codex/feature/report-owner-presentation-v2`, sobre `5d3087c`), detrás de
`DECISION_ROOM_OWNER_PRESENTATION=true`.

## 13. Resultados: fase 3 (presentación P3)

Ejecución:
- Lote `phase3`, congelado en `fbff764` de Astra.
- Brazo con P3 (`DECISION_ROOM_OWNER_PRESENTATION=true`, más continuidad y
  recuperación): 2 informes de Bruma y 3 de Albor.
- Control sin P3 del mismo commit: 1 de Bruma. Control de Luna: 1 de Bruma.
- Como control de continuidad sin P3 en Albor se reutilizan los 6 informes de
  `phase2c`, del mismo código de investigación.

Dos fallos del producto aparecieron en la ejecución:
- **Exportación:** P3 daba por hecho que toda evidencia era numérica, y una
  dimensión de texto («Café de la casa 250 g | Marketplace») hacía fallar la
  exportación de informes ya aprobados (2 casos). Corregido en `f60278d`. Los dos
  informes se reexportaron sin repetir la investigación con el nuevo comando
  `trials.py reexport`.
- **Límite de enum de OpenAI:** el esquema de investigación repetía el enum de
  métricas acumuladas en cada variante del `anyOf`. OpenAI rechazó con HTTP 400
  una llamada con 1.867 valores («at most 1000 enum values in total»); la mayor
  aceptada en `phase2c` tenía 966. El fallo estaba latente desde la continuidad y
  crece con la profundidad de la investigación: es un fallo de escala, no de P3.
  Corregido en `d682b62`/`f0455c1`. El esquema rechazado, acotado, fue aceptado
  por OpenAI (976 valores), y el intento sustituto (`phase3b`, `b91aefb`) llegó a
  590 como máximo. Sesgo de supervivencia: el intento perdido era el de
  investigación más profunda.

`b91aefb` sustituye además el contador «0 de 1 entregables» por la explicación
de lo pendiente. Los cuatro informes con P3 de `phase3` se reexportaron con esa
revisión (`reexport --again`), así que los cinco se presentan igual.

Lectores independientes, tercera ronda:
- 2 lectores por negocio, cada uno con su propio orden aleatorio y sus propios
  códigos.
- Bruma: 9 informes (2 con P3, 3 de continuidad, 3 de Luna y 1 de la línea base).
- Albor: 12 informes (3 con P3, 6 de continuidad y 3 de Luna).
- Cambio de formato: el texto conserva títulos, listas y tablas y marca las
  secciones plegadas (`trial_kit.reading_text`). Las rondas 1 y 2 usaban una sola
  línea plana.
- Concordancia entre lectores: Spearman 0,97 en Bruma y 0,70 en Albor.

| Grupo | Bruma: puesto | Bruma: entiende / confía | Albor: puesto | Albor: entiende / confía |
| --- | ---: | ---: | ---: | ---: |
| Luna | 0,12 | 4,2 / 3,5 | 0,32 | 4,3 / 2,8 |
| Continuidad sin P3 | 0,60 | 3,2 / 2,5 | 0,41 | 3,3 / 3,1 |
| Producto línea base | 0,50 (n=1) | 3,5 / 3,0 | — | — |
| **P3** | **0,91** | **2,3 / 2,0** | **0,86** | **2,2 / 2,3** |

P3 queda el último en ambos negocios y con ambos lectores. La parte visible
mide lo mismo que la de los demás (unas 1.000–1.200 palabras), pero P3 pliega
2–3 veces más material: 1.292 y 2.471 palabras de media, con 14–28 «Cifra de
apoyo N», descripciones de cálculo en inglés, `TRY_CAST` y valores diarios
repetidos. Los lectores lo leen aunque esté plegado y es su queja principal.

Diagnóstico: un lector por negocio, con los mismos informes y el mismo orden que
el lector «a», pero viendo solo el título de cada sección plegada:

| Grupo | Bruma: puesto | Albor: puesto |
| --- | ---: | ---: |
| Luna | 0,12 | 0,30 |
| Continuidad sin P3 | 0,75 | 0,42 |
| P3 | 0,56 | 0,85 |

- **Bruma:** sin lo plegado, P3 pasa de último a ser el mejor producto, aunque
  sigue muy lejos de Luna. El volcado de evidencia es lo que hundía a P3.
  Quejas visibles que quedan:
  - condicionales repetidos («Si Si los registros…») que acaban en «mantener
    como descriptivo»;
  - la cautela causal repetida;
  - notas de «Versión 0» y de exportación HTML en límites;
  - jerga en la prosa («pares focales», «liderazgo aritmético», «residual de
    meses sin pareja»);
  - etiquetas `cafe_casa:2022-01` en los gráficos.
- **Albor:** P3 sigue último, pero por el contenido. P3 solo cambia la redacción
  y la revisión (`budgets.owner_presentation`), y en 2 de los 3 intentos la
  investigación nunca encontró la caída de hostelería. En `phase2c` la encontró
  en los 6. Los dos lectores vuelven a elegir primero el informe de continuidad
  que detecta que hostelería no tiene registros desde abril.

Conclusión:
- P3 no se adopta tal cual. El volcado de evidencia en el informe del dueño
  empeora la lectura; la evidencia debe ir resumida en castellano o en un anexo
  técnico aparte.
- La mejora visible es real pero pequeña frente a Luna, y está medida con muy
  pocos informes.
- Las comparaciones entre lotes mezclan la variación de la investigación con la
  de la presentación. Las próximas pruebas de presentación deben reutilizar la
  misma investigación: volver a redactar y revisar sobre una investigación ya
  hecha, para comparar en pareja.

## 14. Resultados: P3b, comparación por parejas sobre la misma investigación

Diseño:
- Astra implementó P3b en `929d142`, sobre `b91aefb`, detrás de la misma opción.
  Cambios:
  - sin volcado de evidencia en el HTML del dueño, con la auditoría aparte;
  - etiquetas de gráficos con nombres de serie;
  - sin «Si Si» y con las reacciones idénticas unificadas;
  - notas de software fuera de los límites;
  - instrucciones v2 contra la jerga y las cautelas repetidas.
- Nuevo comando `trials.py prepare-rewrite`. Clona la base de datos de cada brazo
  original (PostgreSQL `TEMPLATE`) y su almacenamiento, y sobre cada investigación
  aprobada lanza solo la redacción y revisión, dos veces, con el mismo código
  congelado: con P3b y sin P3.
- Lote `phase3c`: 9 investigaciones (las 8 de `phase2c` y el control de Bruma de
  `phase3`), es decir, 18 reescrituras. El coste equivale a unas 6 ejecuciones
  completas.
- 17 de 18 informes aprobados. Una reescritura con P3b se perdió por un bloqueo
  entre el revisor y el controlador. Las instrucciones v2 del revisor bloquean
  la línea «Cobertura del encargo: 0 de 1 entregables…», pero el controlador la
  reinyecta en `limitations` tras cada `submit` (`review_graph.py:73`), así que
  el analista no puede quitarla y se agota el presupuesto. El revisor no puede
  bloquear lo que el sistema impone; corrección pedida a Astra. Esa pareja (5 de
  Albor) queda fuera.
- Comprobación automática: P3b no tiene nada plegado, ni «Cifra de apoyo», ni
  claves internas, ni decimales largos, ni «Si Si». Su texto visible mide lo
  mismo que sin P3.

Lectores independientes, cuarta ronda:
- 2 por negocio, con orden y códigos aleatorios.
- Bruma: 3 parejas y 3 informes de Luna. Albor: 5 parejas y los mismos 3 de Luna
  de la ronda 3.
- Concordancia entre lectores: Spearman 0,78 en Bruma y 0,83 en Albor.

| Grupo | Bruma: puesto | Bruma: entiende / confía | Albor: puesto | Albor: entiende / confía |
| --- | ---: | ---: | ---: | ---: |
| Luna | 0,12 | 3,8 / 3,5 | 0,12 | 4,5 / 3,5 |
| P3b | 0,62 | 3,0 / 2,5 | 0,59 | 3,1 / 2,7 |
| Sin P3 (misma investigación y código) | 0,75 | 2,3 / 2,2 | 0,63 | 2,6 / 2,6 |

**Por parejas, P3b gana 12 de 16 comparaciones** (Bruma 5/6 y Albor 7/10). Con
una prueba de signos de una cola, p ≈ 0,04. También mejora el entendimiento en
0,5–0,7 puntos. Es un efecto pequeño pero consistente, y ya no depende de la
variación de la investigación. Luna sigue primero en ambos negocios y para los
cuatro lectores.

Quejas que quedan sobre P3b:
- Presentación:
  - «no se comprobó que el informe se abra bien», que resta confianza;
  - «Selección entregada: N elementos…» y «Anexo técnico»;
  - cautelas causales y de datos sintéticos repetidas;
  - jerga: «mitades cronológicas», «unidades por fecha observada», «conciliar
    captura o mapeo», «imputar ceros», «meses emparejados»;
  - bloques Señal / Por qué / Qué permite decidir con las mismas palabras.
- Criterio, que es lo que separa al producto de Luna según los motivos de los
  lectores:
  - no hay panorama por canal (tienda, marketplace);
  - una o dos prioridades, o «no hay una ganadora clara», sin elegir;
  - ventanas de comparación arbitrarias y sin explicar;
  - comprobaciones que dependen de registros que el dueño no tiene;
  - reacciones que no son acciones de negocio («mantener como descriptivo»
    frente a «reponer» o «corregir el recuento» de Luna);
  - lo importante escondido en un pie de gráfico (hostelería sin registros desde
    marzo o abril de 2026).

Conclusión:
- P3b se adopta como base, con los restos de presentación por limpiar.
- Lo siguiente es el criterio. Primero P2 (revisor que exige prioridad
  justificada frente a alternativas, comprobaciones al alcance del dueño y
  reacciones de negocio), que se puede medir barato por parejas sobre las mismas
  investigaciones. Después P1 (panorama), que cambia la investigación y necesita
  ejecuciones completas.

## 15. P1a (panorama determinista): primer intento sin efecto

Lote `phase1a`:
- `5d0aae0` de Astra (P3b más panorama, opción `DECISION_ROOM_SALES_PANORAMA`).
- Reescritura solo del brazo con panorama sobre las 9 investigaciones, con el
  control P3b de `phase3c`, más el control que faltaba de la pareja 5
  (`prepare-rewrite --arms product --paired-source …`).

Se paró tras la primera revisión porque el panorama llegaba como `unavailable`:
- Se identificaron bien las columnas (`fecha`, `canal_id`, `producto_id`,
  `unidades`), pero las 122.154 filas se marcaron inválidas.
- La fecha de los dos conjuntos tiene el formato `2021-09-01 00:00:00`, y la
  validación (`sales_panorama.py:149`) solo admite `YYYY-MM-DD` exacto.
- El tratamiento era nulo. Un intento completado, que no se evalúa, y un
  abandonado, sin sustituto.

Lección para las pruebas del producto: validar con el formato real de las
entradas (marcas de tiempo a medianoche), no solo con fixtures construidos para
el test.

## 16. P1a (panorama determinista): medición con datos reales

Revisión `d14c0ed` de Astra, que añade fechas con hora a P3c (`c8a42c5`), la
corrección del bloqueo del revisor (`f740c0b`) y P1a (`5d0aae0`).

Antes de usar el modelo, el panorama se calculó sobre las bases clonadas: 0 filas
inválidas en los dos negocios. En Albor detecta por código dos señales plantadas:
- S4: Marketplace sin filas del 10 al 18 de marzo de 2026. Ningún informe de
  ningún sistema la había detectado.
- S2: Café 1 kg en Hostelería sin filas desde el 31 de marzo de 2026.

Comparación elegida: enero–agosto de 2026 frente a 2025 en Albor, y agosto frente
a julio en Bruma.

Lote `phase1a2`:
- 9 investigaciones, cada una reescrita dos veces con `d14c0ed` y P3c: con
  panorama y sin panorama.
- Todos los brazos sin panorama, aprobados a la primera (9/9).
- Brazo con panorama: 5 de 9 fallaron en el primer intento por transporte, y los
  5 reintentos (`trials.py retry`) se aprobaron. Hay 9/9 aprobados tras el
  reintento.
- Diagnóstico del transporte:
  - el panorama añade entre 20.000 y 50.000 tokens a cada llamada de revisión,
    que en Albor llega a 100.000–160.000;
  - la cuenta admite 200.000 tokens por minuto, así que analista y revisor
    seguidos provocan un 429;
  - el producto reintenta a los 13 s (`retry_after`), cuando el límite se libera
    a los ~44 s (`reset_tokens_seconds`);
  - el reintento acaba en `RemoteProtocolError` y la llamada se marca
    `ModelRequestUncertain`;
  - también hubo un `ReadTimeout` de 300 s y una llamada colgada 23 minutos.
- Es un riesgo de escala del producto: con negocios grandes, el contexto se
  acerca al límite de tokens por minuto.

Uso del panorama en los informes aprobados (texto visible e informe estructurado):

| Grupo | n | Cita alguna métrica del panorama | Menciona el hueco de Marketplace | Menciona Hostelería sin filas |
| --- | ---: | ---: | ---: | ---: |
| Albor con panorama | 6 | 0 | 0 | 3 |
| Albor sin panorama | 6 | 0 | 0 | 3 |
| Bruma con panorama | 3 | 0 | — | — |
| Bruma sin panorama | 3 | 0 | — | — |

El panorama llega al analista: está en el contexto, aunque al final (posición
~245.000 de 272.000 bytes), y sus métricas son citables en el esquema. Las
instrucciones mandan abrir el informe con él y citarlo. Ningún informe lo hace.
El tratamiento no se expresa, así que no se gasta una ronda de lectores.

Lección de arquitectura, coherente con las fases anteriores: el modelo cumple
los contratos de esquema y validador, no las sugerencias de prompt.
- La continuidad funcionó porque era estructural.
- P3 empezó a funcionar cuando la presentación se hizo por código.
- P1a como contexto pasivo no cambia nada.

Siguiente paso pedido a Astra, P1a v2:
- bloque de panorama renderizado por código al principio del informe;
- disposición obligatoria y validada de cada hueco detectado (prioridad o
  descarte con motivo);
- justificación estructurada de cada prioridad frente al panorama;
- panorama compacto al principio del contexto;
- transporte que espere `reset_tokens_seconds`, con tope duro por llamada.

## 17. P1a v2 (panorama obligatorio) con `c6bda76`, sin compactación

Configuración (los dos brazos): continuidad, recuperación, P3c, guardián de
bucles, `PANORAMA_OBLIGATION_GUARD`, TPM 1.800.000. Compactación, prefijo
estable y caché explícita **apagados**: con ellos encendidos, dos pilotos de una
pareja aprobaron 0 de 2, porque el analista no veía datos que el validador
seguía exigiendo (`question_coverage`, `panorama_priority`, `delivery_selection`,
`owner_coverage`). Brazo de tratamiento: `DECISION_ROOM_SALES_PANORAMA=true`.
Lotes `pilot-c6bda76-nocompact` (pareja 1) y `phase1av4` (8 parejas).

| Brazo | Aprobados | Marketplace sin filas 10–18 mar. (S4) | Hostelería 1 kg sin filas (S2) |
| --- | ---: | ---: | ---: |
| Albor con panorama | 4/6 | 4/4 | 4/4 |
| Albor sin panorama | 6/6 | 0/6 | 1/6 |
| Bruma con panorama | 2/3 | — | — |
| Bruma sin panorama | 3/3 | — | — |

Pérdidas con panorama (3/9), todas por contratos nuevos:
- 2 por «linked finding must cover its source and combination»: la
  investigación no trató esa combinación;
- 1 por justificar con métricas del panorama (agosto frente a julio) cifras de
  otra ventana de la investigación; integridad, bloqueo correcto.

Lectores independientes, quinta ronda:
- 2 por negocio, con las 6 parejas completas (4 de Albor y 2 de Bruma) y los
  mismos 3 informes de Luna por negocio.

| Grupo | Bruma: puesto | Bruma: entiende / confía | Albor: puesto | Albor: entiende / confía |
| --- | ---: | ---: | ---: | ---: |
| Luna | 0,17 | 3,8 / 3,5 | 0,48 | 4,2 / 2,8 |
| Con panorama | 0,71 | 2,5 / 2,3 | 0,49 | 2,6 / 3,0 |
| Sin panorama | 0,79 | 3,0 / 2,0 | 0,53 | 3,0 / 2,8 |

- Por parejas, el panorama gana 6 de 12 (Albor 4/8, Bruma 2/4): sin efecto para
  el lector.
- En Albor, los dos lectores eligen primero un informe del producto **sin**
  panorama, el que pone primero «Café 1 kg en hostelería sin pedidos desde
  abril». El producto ya iguala a Luna en Albor (0,49–0,53 frente a 0,48); en
  Bruma sigue lejos.
- Quejas específicas del panorama:
  - dos comparaciones distintas en el mismo informe: el panorama dice
    enero–agosto, −957, y el redactor primeros y últimos 12 meses, −604;
  - en Bruma se contradicen los «mayores cambios»: Kit/Web +118 en el panorama
    frente a Café/Marketplace +188 en el informe;
  - repeticiones;
  - jerga del detector («regla de detección», «días esperados»);
  - prioridad a lo que crece antes que a lo que desaparece.

Conclusión:
- El panorama mejora la detección de forma objetiva (S4 y S2 en el 100 % de
  los informes de Albor), pero no la preferencia del lector. Pega un análisis
  determinista con su propia ventana a una investigación con otras ventanas, y
  el informe se contradice.
- Además, sus contratos rígidos pierden 1 de cada 3 informes.
- Cualquier versión siguiente necesita **una sola historia**: que la
  investigación parta del panorama y use su ventana (P1b), o que el informe se
  ordene sobre la comparación del panorama. Los contratos de enlace no pueden
  bloquear el informe cuando la investigación no cubrió la combinación.

## 10. Límites

Tres repeticiones son pocas para afirmar consistencia; sirven para detectar
diferencias grandes. Albor es sintético y sus señales las diseñó el mismo autor
del análisis: hay riesgo de que el diseño favorezca las propuestas. Por eso las
señales y su lectura esperada se fijan aquí, antes de cualquier ejecución, y se
incluye un señuelo. Autenticación, transporte y límites de Codex CLI y de la API
del producto difieren; no se infiere coste API de los tokens CLI.
