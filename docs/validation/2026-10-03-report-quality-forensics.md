# 3.9.10 — Investigación de calidad: Decision Room y Luna directo

**Estado: diagnóstico completado; correcciones propuestas, todavía no implementadas.**
Inspección sobre `4815b68`, con las instantáneas originales de los dos intentos de
3.9.9.2. No se han generado informes nuevos ni modificado las entregas evaluadas.
La aceptación de calidad de 3.9.7 permanece abierta.

## Conclusión

El último informe mantiene cifras correctas, pero cierra demasiado pronto la
investigación y convierte un ranking de contribuciones en una prioridad con
escasa justificación adicional. La información y el presupuesto permitían
comprobar persistencia temporal y comparar el descenso generalizado de tienda.
El trabajador considera suficiente el desglose mensual, el planificador acepta
ese criterio, el coordinador termina y el revisor aprueba sin reparos.

Además hay un defecto técnico reproducible: **el esquema exigido al modelo no
admite un gráfico válido con capas, aunque el validador y el renderizador sí lo
admiten**. Las pruebas anteriores no cubrían esa frontera. Atribuir la ausencia
de capas exclusivamente a la elección del agente fue incorrecto. Corregir ese
contrato es necesario; por sí solo no garantiza mejor investigación.

Luna demuestra que el mismo modelo puede hacer más cálculos relevantes y producir
una lectura más útil con otra organización del trabajo. También demuestra que
calcular más y presentar mejor no garantiza narrar correctamente ni entregar
HTML funcional. La solución propuesta conserva evidencia y comprobaciones,
reduce fricción para continuar investigando y cambia qué se exige para cerrar.
No hay evidencia suficiente para atribuir la diferencia al número de agentes o
al tamaño del prompt como causas aisladas.

## 1. Alcance, fuentes y comparabilidad

Se inspeccionaron las **73 llamadas de agente** persistidas de Decision Room:
57 del intento interrumpido y 16 de la repetición. Añadiendo descubrimiento son
75 llamadas contabilizadas en los recursos del piloto. Se leyeron código Python,
resultados, errores, presupuestos, contextos, salidas, revisiones y exportaciones.
Se reconstruyeron sistemas y esquemas dinámicos desde cada instantánea congelada.

Se transcribieron los seis JSONL de Luna: **68 comandos terminados, cinco con
salida de error**, además de mensajes del agente. Un comando puede listar
archivos, calcular, generar HTML o comprobarlo; no equivale a un cálculo. El
análisis detallado contrasta la repetición con ronda 2/run 2 y ronda 2/run 3.

El dossier completo permanece local en `.local/quality-forensics-2026-10-03/`:
cuaderno incremental, Markdown por llamada con contexto/salida exactos, sistemas
reconstruidos, contratos JSON, transcripciones CLI, sondas y 34 huellas de fuentes.
No se incorporan al repositorio trazas privadas, rutas personales ni CSV completos.

La repetición y los tres Luna de ronda 2 comparten cuatro CSV y el encargo del
propietario. Los hashes y la rúbrica histórica están en la
[comparación Luna](2026-10-02-codex-luna-comparison.md) y el
[piloto integrado](2026-10-02-agent-visual-freedom-pilot.md). Son datos sintéticos:
1.656 filas, seis productos, tres canales, 92 fechas de junio a agosto de 2026;
totales mensuales de 1.541, 1.979 y 2.455 unidades registradas.

El encargo pide evolución, prioridades, profundizar señales relevantes, calcular
lo disponible antes de trasladar tareas al propietario, comparar alternativas y
entregar HTML con gráficos. Excluye importes de significado ambiguo, márgenes,
retorno de marketing, predicciones y causas no demostradas. El propietario no
dispone de contexto adicional sobre apertura, stock o cobertura.

Las sesiones usan `gpt-6-luna` y esfuerzo `low`. Difieren herramientas, sistema,
protocolo, continuidad, entorno, autenticación y política de revisión. El CLI usa
ChatGPT; el producto usa API. No se conocen todas las instrucciones internas del
CLI ni se ha aislado la variación del muestreo. Es una comparación de recorridos
observados, **no un ensayo causal entre arquitecturas**.

La inspección de esta entrega usa también sus exportaciones y la validación de
navegador conservada del piloto. La comprobación nueva del truncado se hizo
contra el componente y las etiquetas reales. No se ha repetido una evaluación
completa de interacción y tamaños de pantalla ni cambiado el negocio activo
de la aplicación habitual para este diagnóstico.

## 2. Dónde se cierra la investigación

Numeración del dossier `product-retry`; el prompt de revisión es `review-v48`.

| Llamada | Papel y acción | Evidencia y decisión |
| --- | --- | --- |
| 1–2 | Planificación, `inspect` → `propose` | Inspecciona actividad y catálogos. Propone evolución y contribución producto×canal. |
| 3 | Planificador, `guide` | Pide comparar señales, fechas, alternativas y comprobaciones útiles. |
| 4 | Coordinador, `delegate` | Encarga evolución temporal. |
| 5 | Trabajador, `execute` | Lee todas las filas mediante Python/DuckDB; valida granularidad y calcula totales mensuales y media por fecha observada. |
| 6 | Trabajador, `record_candidate` | Registra resultado; remite contribuciones a la otra investigación. |
| 7–8 | Planificador y coordinador | Orientan y delegan contribuciones entre meses. El encargo al trabajador se concreta en ese desglose mensual. |
| 9 | Trabajador, `execute` | Falla al acceder a `r.product` en una fila de pandas cuyo campo no tiene ese nombre. |
| 10 | Trabajador, `execute` | Corrige; valida joins y calcula niveles de los 18 cruces y cambios en ambos intervalos. |
| 11 | Trabajador, `record_candidate` | Declara suficiente el análisis mensual y no propone ampliación. |
| 12 | Planificador, `guide` | Prioriza Kit–Web y Café–Marketplace; desaconseja reabrir salvo inconsistencia. |
| 13 | Coordinador, `finish` | Cierra pudiendo elegir `expand`; solo se han intentado tres ejecuciones de 48. |
| 14 | Planificador, `ready` | Acepta material para redactar; interpreta la parcialidad principalmente como falta de contexto operativo. |
| 15 | Analista/redactor, `submit` | Presenta informe directamente, sin usar Python propio. Dos gráficos de barras. |
| 16 | Revisor, `approve` parcial | Ningún reparo; `decision_support=pass`. No ejecuta cálculos propios ni ve el render real. |

En la llamada 11 aparece la justificación explícita:

> «No propongo ampliar este análisis local: la fuente no contiene ese contexto y el desglose mensual ya responde a las comparaciones de contribución solicitadas».

Es cierto que los CSV no contienen causas operativas. No se sigue de ello que
ya esté agotado lo que permiten calcular. Se podía distinguir un salto mantenido
de unos pocos días excepcionales, o una caída amplia de tienda de una anomalía
en un solo producto. Esa distinción permite elegir mejor qué comprobar después.

El planificador refuerza el cierre en la llamada 12:

> «No vuelvas a abrir un desglose ya calculado salvo que detectes una inconsistencia concreta».

No es una prohibición global del sistema, pero sí la orientación inmediata que
recibe el coordinador. El esquema todavía ofrece `finish`, `expand`,
`consult_business` y `retrieve`. El redactor y el revisor disponen después de
seis ejecuciones Python cada uno; ambos usan cero. **No fue un cierre obligado
por presupuesto, ausencia de herramientas o agotamiento de contexto.**

Tampoco faltaban todas las señales relevantes en el contexto: los 18 cambios
producto×canal estaban visibles al decidir `finish`. Permiten obtener Tienda
−93, Web +237 y Marketplace +332; cinco de seis productos de tienda caen y el
otro permanece estable. No hay `result_omitted` en los contextos de la repetición.

Sí existe una pérdida más localizada de accesibilidad: los 54 niveles mensuales
por cruce se guardan en un CSV de ejecución, pero el resultado visible conserva
principalmente las dos series de cambios. Tener un archivo guardado no equivale
a haber puesto sus valores a disposición del siguiente modelo. Las series
diarias focales ni siquiera se calcularon en este recorrido.

## 3. Qué habría aportado profundizar

Se recalcularon de forma independiente, con `csv` de Python, los registros por
fecha de las señales elegidas. No se añadieron fuentes externas ni conocimiento
de las causas que generaron los datos sintéticos.

| Señal | Julio | Agosto | Qué permite distinguir |
| --- | --- | --- | --- |
| Kit–Web | 115 unidades; todos los días entre 3 y 5; mediana 4 | 233; todos los días entre 6 y 10; mediana 8 | El aumento se mantiene durante el mes; no depende de un único pico. |
| Café de la casa–Marketplace | 243; rango diario 7–10; mediana 8 | 343; rango diario 10–14; mediana 11 | También aumenta el nivel diario típico. |
| Tienda física | 621; media diaria 20,03; mediana 21 | 528; media diaria 17,03; mediana 18 | La caída afecta a cinco productos; las medias por cada día de la semana también son inferiores. |

Julio y agosto tienen 31 fechas observadas cada uno. Ninguna cifra certifica
apertura, exhaustividad, pedidos completados ni demanda. La comparación por día
de la semana es descriptiva; no identifica causalidad ni elimina otros factores.

Una reacción mejor fundamentada para Kit–Web sería: «El aumento aparece desde
el comienzo del mes y se mantiene. Comprueba primero si cambió la captura o la
configuración del producto alrededor del cambio de mes y concilia con pedidos.
Si el aumento se confirma en pedidos, contrasta existencias y plazo de reposición
antes de decidir una compra». Las dos últimas fuentes faltan: no corresponde
inventar una cantidad de reposición. Si no hay historial, queda una señal
descriptiva más precisa, no una explicación confirmada.

Para tienda, el patrón amplio justifica contrastar una comprobación del canal
con la revisión de una única combinación creciente. **No demuestra que tienda
deba ser siempre la primera prioridad**: faltan objetivo comercial, costes de
comprobación y consecuencias. Sí demuestra que +118 frente a +100 es insuficiente
para descartar esa alternativa sin discutirla.

No propongo calcular todas las estadísticas ni exigir un análisis diario en
todos los informes. El criterio es si un cálculo disponible puede cambiar
la interpretación, la prioridad o la siguiente comprobación.

## 4. Defectos y restricciones comprobados en el código

### 4.1 Capas permitidas en ejecución, imposibles en el esquema productor

[`ModelClient._review_references`](../../decision_room/agent/model.py) construye
las variantes del gráfico: una rama escalar exige al menos dos `points`; las
ramas de series exigen `series` no nula y `points=[]`. No incorpora una rama
para `layers` con `series=null` y `points=[]`, precisamente la combinación que
requiere [`chart_evidence`](../../decision_room/chart_evidence.py).

Sonda offline, usando el fixture público de
[`test_chart_layers.py`](../../tests/test_chart_layers.py):

| Control | Resultado |
| --- | --- |
| Gráfico con capas, validación de informe y resolución de evidencia | Pasa; 18 puntos resueltos. |
| El mismo gráfico, esquema generado para el modelo con esas observaciones | Falla en las 13 variantes. |
| Gráfico mensual anterior, mismo esquema | Pasa. |

Las pruebas existentes cubrían cálculo, referencias y representación; faltaba
pasar por el esquema que restringe la generación. Esto reabre la parte de
integración de 3.9.9.1. No prueba que, arreglada esa frontera, el agente hubiera
calculado una media móvil: no la solicitó y no tenía una serie derivada guardada.
Los gráficos simples de líneas sí estaban permitidos.

### 4.2 Continuar investigando requiere volver a abrir una tarea

Después de una ejecución correcta con resultado visible,
[`generate_research`](../../decision_room/agent/model.py) restringe al trabajador
a registrar candidato o bloquearlo, además de recuperación de memoria cuando
está habilitada. No permite otra ejecución inmediata antes del registro. El
grafo termina ese trabajo y el coordinador debe expandir y delegar de nuevo.

La intención es conservar evidencia antes de que otro programa la oculte; es
razonable. La consecuencia es que una investigación natural de «calcular → ver
una señal → contrastarla» se divide en varios traspasos y checkpoints. El primer
intento sí supera esa fricción; no es una imposibilidad de profundizar. Que la
fricción favorezca el cierre es una hipótesis apoyada por la secuencia, pendiente
de una comparación controlada.

Otros dos acoplamientos merecen revisión: `Followup.basis_metric_keys` referencia
métricas escalares aunque muchas señales viven en series; y la síntesis ordena
investigaciones, no señales de negocio. En esta repetición, la razón asociada
a evolución en la síntesis menciona Café–Marketplace, calculado en la otra
investigación. Las citas finales pueden ser correctas y aun así ese mapeo
dificulta distinguir agenda, evidencia y prioridad.

### 4.3 Capacidad de exportación comunicada de forma ambigua

El contexto diferencia `execution_artifact_downloads=false` de las superficies
web, HTML estático y PDF disponibles. El redactor generaliza la primera señal
a que no puede entregar el HTML local solicitado; el revisor acepta esa
limitación. El controlador exporta HTML/PDF posteriormente.

No debe decirse que un archivo ya fue generado antes de serlo. Tampoco debe
heredarse en el informe final una negación de una capacidad que sí tiene la
aplicación. Hay que distinguir artefactos del ejecutor, exportación posterior y
verificación real de apertura. `files=pass` en la evaluación del revisor no es
prueba de haber abierto un archivo: revisa la entrega que se le presenta.

### 4.4 Legibilidad invisible para el revisor

El gráfico final incluye 18 etiquetas producto×canal. En la variante de barras
simples, [`report.tsx`](../../frontend/src/components/workspace/report.tsx)
recorta a 20 caracteres más puntos suspensivos. Aplicando exactamente ese formato,
las 18 etiquetas se convierten en **ocho textos distintos**: cinco productos
tienen sus tres canales indistinguibles en el eje. El tooltip permite recuperar
información, pero no resuelve la lectura inicial.

El revisor ve el contrato y los datos, no los píxeles, los recortes ni el estado
de interacción. Su `charts=pass` no verifica la experiencia visual. La revisión
debe disponer de evidencia del render o limitar explícitamente qué acredita.
La solución combina selección del analista y un renderizador capaz de mostrar
identidades completas; no consiste en obligar siempre a usar menos categorías.

### 4.5 Error latente en el rango temporal calculado

El primer programa de la repetición describe su rango como mínimo y máximo,
pero utiliza `rows[0][0]` para el inicio y `max(...)` para el final. La consulta
no garantiza orden. Con estos archivos ordenados el valor coincide; no cambia
las cifras auditadas. Con otra ordenación podría cambiar el inicio informado.
Es un ejemplo de por qué verificar la salida de un caso no sustituye comprobar
la operación declarada ni ensayar invariancia al orden.
Una sonda de la expresión guardada con las mismas dos fechas en orden inverso
cambia el inicio de junio a agosto, mientras el mínimo real sigue en junio.

## 5. Prompts, contexto y condiciones de aprobación

Los sistemas reconstruidos, incluidas instrucciones de recuperación de memoria,
tienen aproximadamente 2.161 palabras en planificación, 2.871 en el planificador,
5.600 en investigación, 7.574 en redacción y 7.788 en revisión. Son palabras de
texto, no tokens de facturación. El contexto del redactor ocupa 107.388 bytes;
el del revisor, 125.293; sus esquemas rondan 44 KB.

En revisión, `business_direction` ocupa 36.613 bytes, las observaciones 29.247 y
el informe 12.894. El planificador genera 8.126 tokens de salida en cuatro
intervenciones, más que los 7.913 de las ocho llamadas de investigación. Esto
no demuestra que planificar sea inútil; muestra que una parte considerable del
trabajo se dedica a volver a expresar objetivos, cautelas y orientación.

El prompt ya contiene buenas instrucciones: no confundir lo computable con
datos ausentes, priorizar frente a alternativas, reaccionar según la evidencia
y no limitarse a clasificaciones. No falta simplemente una frase que diga
«profundiza». Conviven con otras que prefieren métricas existentes, indican que
comparar periodos suele bastar, recomiendan pocos hallazgos/gráficos y desalientan
series diarias largas cuando aporten poco. Son criterios compatibles en teoría,
pero no hay una decisión explícita y verificable que resuelva cuándo se ha hecho
lo suficiente en una señal particular.

La solicitud del propietario se conserva como una única entrada completa en
`owner_deliverables`. Esto evita inventar requisitos del cliente a partir del
plan del agente, pero también permite declarar `partial` el bloque completo
sin localizar con claridad qué parte computable quedó sin resolver. La revisión
requiere estructura, referencias y justificaciones, pero muchos juicios de
utilidad los confirma el mismo tipo de modelo sobre esa estructura.

El revisor concede `decision_support=pass` porque hay una alternativa cuantificada
y comprobaciones condicionales. No exige confrontar que la alternativa más
material pueda ser una señal diferente ni verifica que los cálculos pendientes
cambiarían el siguiente paso. Aprobar exige una respuesta breve; revisar exige
formular reparos materiales correctamente vinculados al encargo. Esa asimetría
podría favorecer aprobación; es hipótesis, no una intención observable del modelo.

La lectura tampoco se resume tanto como se pretende. El diagnóstico guardado
cuenta 726 palabras de primera lectura y 210 en limitaciones, frente a una guía
de unas 500 palabras de prosa. La detección de repetición devuelve vacío porque
busca pasajes idénticos, no paráfrasis. Resumen, afirmación y orientación repiten
señales, cifras y cautelas con redacciones distintas. Añadir campos obligatorios
no garantiza más información útil; puede multiplicar el mismo contenido.

## 6. El primer intento: profundizar y después desviarse

El intento sobre `466171b` sí abre nuevas investigaciones: compara cruces entre
junio y agosto, separa contribuciones positivas y negativas y amplía agregados
mensuales. En algunas ejecuciones calcula más de lo que expone al siguiente
modelo, y luego vuelve a pedir material similar. Esta secuencia refuta una
explicación demasiado simple de «este agente nunca profundiza».

La desviación principal aparece al convertir «guardar informe.html» en una
investigación Python. El ejecutor admite JSON, CSV, PNG y Parquet, no HTML.
[`validate_payload`](../../decision_room/execution_contract.py) devuelve el
mismo error para extensión no admitida y nombre duplicado:
`Invalid or duplicate artifact filename.` Cambiar el nombre no puede resolverlo.
Una sonda con contenido inerte admite `.csv` y rechaza `.html` con ese mensaje.

La rama termina tras seis ejecuciones efectivas, cuatro con artefactos inválidos
y dos fallos de programa. El agente describe el agotamiento como global, pero
el límite era local: otra rama ejecuta después. A continuación se repiten
cierres y rechazos de preparación porque aún no existe el HTML que debería
producir la fase posterior. `35760d3` ya corrigió la responsabilidad de las fases
y acotó el cierre repetido; no se presenta ese cambio como trabajo de este diagnóstico.

| Recorrido | Tiempo | Llamadas con descubrimiento | Cálculos completados / intentados | 429 |
| --- | ---: | ---: | ---: | ---: |
| Primer intento | 738,294 s | 58 | 6 / 14 | 8 |
| Repetición | 245,979 s | 17 | 2 / 3 | 0 |

El primer intento registra al menos 2.094.715 tokens de entrada y 81.680 de
salida; la repetición, 348.395 y 22.651. Falta uso del intento interrumpido y de
los rechazos. No se debe mostrar solo la repetición para presentar eficiencia.

Los ocho 429 aparecen al final del primer recorrido. Los headers observados
indican 200.000 TPM y 500 RPM, con 499 solicitudes restantes y aproximadamente
20.000–56.000 tokens restantes en esos rechazos. Llamadas cercanas aceptadas
consumen aproximadamente 44.000–59.000 tokens de entrada. Esto respalda presión
de tokens, amplificada por contexto grande y llamadas repetidas; no agotamiento
de solicitudes ni una conclusión de saldo insuficiente. No se conoce toda la
actividad concurrente de la organización.

El transporte espera por agotamiento cuando los tokens restantes llegan a cero,
pero un saldo positivo puede ser insuficiente para la próxima petición. La
dosificación debe considerar tamaño estimado y reserva de salida, además del
reset y la concurrencia. Cero 429 en la repetición no valida esa solución todavía.

## 7. Qué hace Luna realmente

Los seis experimentos usan Codex CLI 0.160.0, esfuerzo bajo, búsqueda web y apps
desactivadas, multiagente desactivado y `--ephemeral --json`. Los eventos guardados
contienen `command_execution` y `agent_message`; no contienen eventos de
razonamiento, navegador, MCP ni delegaciones.

| Ejecución | Comandos terminados | Con error |
| --- | ---: | ---: |
| Ronda 1/run 1 | 9 | 1 |
| Ronda 1/run 2 | 8 | 1 |
| Ronda 1/run 3 | 9 | 0 |
| Ronda 2/run 1 | 13 | 2 |
| Ronda 2/run 2 | 17 | 1 |
| Ronda 2/run 3 | 12 | 0 |

### Mejor entrega observada: ronda 2/run 2

Esta es su secuencia real, con números de línea del JSONL original conservados
en el Markdown local:

| Líneas JSONL | Trabajo visible |
| --- | --- |
| 5, 7, 9 | Lista archivos; obtiene cabeceras y número de filas; muestra pequeñas muestras y catálogos. |
| 11, 13 | Intenta pandas, falla por dependencia ausente y comprueba bibliotecas disponibles. |
| 15 | Usa `csv` de Python sobre todas las filas; valida 92 fechas y 18 celdas por fecha; calcula agregados mensuales, canales, productos y semanas. |
| 18 | Calcula los 18 cruces en tres comparaciones temporales y contribuciones positivas y negativas. |
| 20, 22 | Revisa rangos diarios, medias y cuotas; concilia +569 y −93 con +476 en julio–agosto. |
| 23 | Explicita que la divergencia entre canales será la historia principal. |
| 27, 29 | Prepara y lee JSON derivado con niveles mensuales y 92 valores diarios para construir gráficos. |
| 31 | Recomprueba sumas, signos y ranking en los tres intervalos. |
| 33 | Escribe HTML con datos, SVG e interacción JavaScript. |
| 36, 38, 40 | Busca herramientas de navegador, comprueba estructura HTML, cifras y sintaxis JS; no consigue verificación real de navegador. |
| 41 | Entrega y reconoce ese límite de verificación. |

Por tanto, **no mete todas las filas del CSV en el contexto para razonar a ojo**.
El programa lee todas las filas y el modelo recibe muestras y agregados. Después
sí lee un JSON derivado relativamente pequeño, con datos útiles para los gráficos.
El producto también lee las filas en Python; la diferencia relevante es qué
agregaciones investiga, conserva visibles y utiliza para decidir su relato.

Luna elige la caída amplia de tienda como foco, seguida de las señales digitales;
propone cotejos de TPV, producto, apertura, stock o pedidos según el caso. El
resultado conecta mejor la evidencia con una comprobación. Su gráfico diario
usa una **media del mes como referencia**, no una media móvil de siete días.
No debe confundirse libertad visual con haber elegido siempre el mismo suavizado.

El mejor resultado sigue teniendo límites: el análisis diario mostrado es
principalmente global, no desarrolla todos los contrastes focales de la sección
3, tiene problemas de legibilidad ya observados y no prueba causas. La puntuación
histórica de 23/24 no lo convierte en referencia infalible.

### Contraejemplo: ronda 2/run 3

Esta ejecución calcula distribución diaria y comparaciones focales, pero después
atribuye a Kit–Web el liderazgo junio–agosto. Los datos calculados indican que
Café–Marketplace es mayor. Es un fallo de fidelidad entre cálculo y relato,
no falta de acceso a la cifra. Además, usa `D.months.indexOf(...)` sin definir
`D.months`, dejando dos tablas sin contenido al ejecutar la página.

Buscar fragmentos de HTML y revisar números no equivale a ejecutar JavaScript.
El código ya contenía el fallo durante las comprobaciones visibles. La ejecución
3 ilustra por qué no sustituiría todas las garantías del producto por generación
libre de HTML: mantendría un contrato de evidencia y añadiría verificación de la
entrega realmente renderizada. La libertad de composición puede convivir con él.

También hay un problema del diseño experimental: algunas sesiones concurrentes
reutilizan `/tmp/analyze_bruma.py` y `/tmp/build_report.py`. Es una vía posible de
interferencia, **no una contaminación demostrada**. Un fragmento posterior de
run 1 coincide con su propio generador. Las próximas rondas deben usar temporales
aislados por ejecución antes de sacar conclusiones de pequeñas diferencias.

La comparación de utilidad debe conservar estas diferencias, sin reducirla a
una única nota:

| Dimensión | Producto, última repetición | Luna, mejor recorrido observado | Riesgo visible en otros Luna |
| --- | --- | --- | --- |
| Exactitud | 25 referencias auditadas correctas; periodo del ranking explícito. | Cálculos y conciliaciones útiles; requiere auditoría de la prosa igualmente. | Ranking junio–agosto narrado incorrectamente pese al cálculo correcto. |
| Profundidad | Dos cálculos completos; cierre en mensual y cruces. | Añade distribución, aportes con signo y contraste entre canales. | Más cálculo no garantiza usar bien los resultados. |
| Próxima decisión | Cotejos condicionados, pero prioridad apoyada sobre todo en magnitud. | Relaciona amplitud de la caída con una comprobación del canal. | Una recomendación convincente puede partir de una prioridad errónea. |
| Lectura | Evidencia trazable; repetición y categorías difíciles de distinguir. | Relato y gráficos más conectados con la conclusión. | Tablas vacías y legibilidad no comprobada en navegador. |
| Control | Contratos, referencias, presupuestos y registro de revisión. | Continuidad para calcular, inspeccionar resultados y componer la entrega. | Los controles finales dependen de lo que decida comprobar el propio agente. |

## 8. Qué se sabe del razonamiento y qué falta registrar

En Decision Room se conserva contexto, versión de prompt, acción JSON, código,
resultado, uso y justificaciones explícitas. El transporte usa Chat Completions:
cada petición reconstruye sistema y contexto JSON; las herramientas son acciones
que despacha el controlador, no llamadas nativas a tools en una conversación
continuada. El uso registra 2.775 tokens de razonamiento en las 16 llamadas de
agente de la repetición, **sin su texto**. Un contador no explica una decisión.

El registro original no guarda la petición completa: faltan el sistema renderizado,
el esquema dinámico y el mensaje adicional de corrección después de ciertos
errores de validación. Los dos primeros se reconstruyeron desde código congelado;
el último no se puede recuperar íntegramente del registro actual. Los archivos
`contracts-*` usan corrección nula y no deben presentarse como una captura exacta
de todas las peticiones HTTP.

En Luna se conserva el prompt del propietario, los argumentos CLI, mensajes,
comandos y salidas. No se conserva todo el sistema interno. Los JSONL concretos
no tienen items de razonamiento; el contador `reasoning_output_tokens=0` no
demuestra que el modelo no razonara. Con `--ephemeral` tampoco se espera un
rollout de sesión persistente adicional. La documentación describe tanto los
eventos JSONL como esa persistencia en
[Codex no interactivo](https://developers.openai.com/codex/noninteractive).

La API no expone la cadena interna de razonamiento. Puede ofrecer resúmenes
cuando se solicitan y están disponibles; no son el pensamiento completo ni una
prueba causal de por qué se tomó una decisión. Véase la
[guía oficial de razonamiento](https://developers.openai.com/api/docs/guides/reasoning).
Este análisis usa decisiones y justificaciones visibles; no inventa pensamientos.

Para próximas pruebas conviene guardar sistema/schema efectivos, correcciones,
versiones de tools, respuesta y error normalizados, y una decisión breve de
continuar/cerrar con evidencia. Si se usa Responses, conservar la continuidad
documentada del protocolo puede ser una variante a evaluar. No hay prueba de
que cambiar de endpoint por sí solo resuelva estos fallos.

## 9. Qué conclusiones anteriores deben matizarse

1. **«El agente no eligió capas».** Describe la salida, pero omite que el contrato
   productor no permitía una capa válida. La capacidad no estaba integrada de
   extremo a extremo. Queda corregida esa interpretación.
2. **«Prioridad 2/2 porque el ranking es correcto».** Acredita periodo y comparación,
   pero no que se haya elegido la comprobación más útil. Conservar el 18/24 como
   registro histórico; una futura rúbrica debe separar ranking y prioridad.
3. **Preferencia por líneas.** Existe en la conversación del usuario, pero no en
   el prompt idéntico de esta comparación. No es válido penalizarla como una
   instrucción ignorada en este experimento. Sí se puede evaluar legibilidad.
4. **Más cálculos o mejores gráficos implican más calidad.** Run 3 contradice esa
   equivalencia. Hay que comprobar fidelidad del relato y funcionamiento real.
5. **Más reglas de profundidad resolverán el problema.** Ya existen muchas. Hace
   falta una decisión de cierre mejor y capacidad efectiva para continuar.

## 10. Solución propuesta, en orden verificable

Estas son recomendaciones de implementación, no cambios realizados en este paso.

### A. Reparar capacidades y sus contratos

Unificar las variantes válidas de gráfico entre productor, validación y render.
Añadir pruebas que generen el esquema real con evidencia disponible y pasen
capas, series simples y gráficos escalares por todo el recorrido, además de
controles negativos de referencias, unidades y alineación. Separar capacidad
de exportación, estado de export y verificación de apertura. Dar errores distintos
para extensión no admitida, duplicado y límite local/global.

Aceptación: ningún gráfico válido queda bloqueado por un contrato divergente;
ninguna salida promete verificaciones no realizadas ni niega exportaciones
disponibles. Añadir prueba de invariancia del rango al orden de filas.

### B. Dejar que el investigador siga una señal sin perder evidencia

El analista investigador decide el siguiente cálculo a partir de resultados.
El planificador mantiene objetivo, alternativas y prioridad; no prescribe todos
los cortes ni monopoliza cada paso. El revisor contrasta conclusiones y entrega.
Permitir registrar evidencia de forma acumulativa y continuar una investigación
en el mismo recorrido; delegar cuando haya preguntas realmente independientes.
Conservar límites y procedencia; no sobrescribir resultados anteriores.

Antes de cerrar una señal material, registrar brevemente qué se sabe, qué cálculo
pendiente podría cambiar la decisión, qué exige una fuente ausente y por qué
compensa continuar o parar. No hacer obligatorios todos los desgloses ni una
media móvil. Separar señales, investigaciones y prioridades para no confundirlas.

Aceptación: en casos nuevos puede investigar y justificar un cierre suficiente,
sin una regla específica para Kit, tienda o agosto. Los intentos sin aportación
deben detenerse; la profundidad no se medirá por cantidad de llamadas.

### C. Exigir fidelidad y utilidad en la revisión

Descomponer el encargo en componentes con referencia al texto del propietario,
sin convertir métodos inventados por agentes en obligaciones del cliente.
Examinar si una alternativa material omitida cambia la prioridad, y si una tarea
trasladada al dueño ya era calculable. Comparar prosa, periodo, denominador y
ranking contra evidencia, además de validar IDs y cifras.

Las objeciones deben poder modificar el análisis. Evitar premiar un formulario
completo o bloquear una entrega por una investigación decorativa. Consolidar los
prompts por responsabilidad, retirando duplicación y contradicciones; no añadir
otra capa de instrucciones a miles de palabras existentes.

Aceptación: rechazar ejemplos con ranking narrado incorrecto y cierre prematuro,
aceptar parciales honestos donde falta una fuente indispensable, y permitir
informes breves cuando ya resuelven el encargo.

### D. Una presentación que comunique una vez cada idea

Cada hallazgo debería unir conclusión, evidencia visual y siguiente comprobación;
los detalles metodológicos permanecen accesibles sin repetir la conclusión en
múltiples campos. Permitir al agente composición, granularidad, selección y capas
útiles. El renderizador debe preservar identidades y valores exactos.

Añadir comprobación real de la vista generada: JavaScript, elementos vacíos,
etiquetas indistinguibles, tamaños de pantalla e interacción. Si el revisor debe
juzgar estética o legibilidad, necesita esa evidencia visual; si no la recibe,
su veredicto debe limitarse al contrato y datos que conoce.

Aceptación: no reducir 18 identidades a ocho etiquetas, no tablas vacías y no
líneas adicionales por mera decoración. Evaluar rapidez para entender qué pasa
y qué comprobar, además de corrección.

### E. Medir la mejora sin ocultar fallos

Congelar entradas, código, configuración, prompts efectivos y temporales por run.
Tres repeticiones por variante, como pidió el usuario, con Bruma y otro negocio
de reserva. Primero comparar corrección de contratos con la base; después el
cambio de recorrido y cierre. Mantener un control Luna contemporáneo y conservar
todos los fallos, reintentos, recursos y entregas parciales.

Tres repeticiones sirven para orientar la siguiente iteración; no bastan por sí
solas para demostrar consistencia general ni significación estadística. Mantener
el segundo negocio fuera de los ejemplos usados para ajustar las instrucciones.

Evaluar a ciegas cuando sea posible: exactitud de afirmaciones, alternativa
material considerada, cálculo que cambia una comprobación, acción condicionada
por evidencia, comprensión y funcionamiento visual. Preguntar al lector qué
haría primero y qué dato comprobaría; no contar gráficos ni palabras como
sustitutos de utilidad. Auditar los casos donde un informe bonito da una
prioridad equivocada y donde un informe correcto resulta difícil de usar.

Más esfuerzo de razonamiento, continuidad mediante Responses y diferente
reparto de agentes son variantes posteriores, una a una. La dosificación TPM
compartida y el registro completo de capacidades son condiciones para que los
fallos operativos no confundan la evaluación.

## 11. Validación de esta investigación

- 34 huellas de las fuentes originales verificadas sin cambios.
- 73 llamadas del producto conservadas y 73 sistemas/esquemas reconstruidos;
  limitación de correcciones no persistidas identificada explícitamente.
- Seis JSONL parseados; 68 comandos terminados y cinco errores comprobados.
- Reproducción offline del defecto de capas con fixture público; control anterior
  válido y resolución de 18 puntos válida.
- Las seis pruebas existentes de `test_chart_layers` pasan. Precisamente no
  cubren el esquema productor donde la sonda reproduce el defecto.
- Sonda de extensión de artefactos; CSV admitido y HTML rechazado con error ambiguo.
- Sonda de la expresión guardada del rango: cambia al reordenar las mismas filas.
- Recálculo independiente de señales focales y comprobación de evidencia disponible
  al cierre; comprobación exacta del truncado de etiquetas.
- No se invocaron modelos, no se cambiaron datos ni informes y no se repitió la
  batería general de producto para una entrega documental. Las pruebas de las
  correcciones propuestas deberán ejecutarse cuando se implementen.

Los defectos reproducibles están separados de las hipótesis de comportamiento.
Esta investigación localiza fallos y propone cómo contrastar soluciones; todavía
no demuestra que la siguiente versión entregue mejor de forma consistente.
