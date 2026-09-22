# Evaluación integrada — paso 1.7

## Método

Se implementó el [plan de evaluación](../technical/evaluation-plan.md): ocho
escenarios, tres repeticiones por escenario, referencias calculadas
independientemente con CSV/Decimal y evaluación semántica explícita. Cada caso
importa únicamente su CSV y contexto; las respuestas preparadas solo se entregan
cuando el agente pregunta. El modelo nunca recibe el resultado esperado.

Cada fase arranca en un proceso nuevo y recupera sesión, respuestas, ejecuciones
y revisión desde PostgreSQL. El analista y el revisor usan Qwen local, generan
sus propios programas y borradores, y ejecutan Python en el sandbox existente.
No se modifica manualmente su código ni sus informes para convertir fallos en
éxitos. Las retenciones de informes incorrectos son intervenciones del evaluador,
no detecciones atribuibles al revisor del producto.

Configuración de la serie: `qwen3.8-27b-splash`, `lmstudio_structured`, razonamiento
`off`, 8192 tokens de salida, 300 s por llamada y 1200 s por fase. Se conservan
identificadores, versiones, hashes de entradas, tiempos y tokens. No se inventa un
coste monetario para inferencia local. No hay un segundo modelo instalado ni se
ha probado un proveedor externo en esta evaluación.

## Calibración y correcciones

| Intento | Resultado observado | Acción |
|---|---|---|
| `calibration-01` | El transporte genérico no enviaba control de razonamiento; pregunta innecesaria sobre total frente a promedio; ejecución interrumpida por el operador. | Transporte específico estructurado con control verificado; aclaración del criterio de preguntas. |
| `calibration-02/daily-1` | Recorrido de 754,6 s. Error Python corregido por el propio analista. Totales, 16,14 %, medianas y 24 valores diarios correctos. El revisor aprobó una gráfica que mezclaba sumas y medias. | Informe retenido por evaluación independiente; DR-004 documentado. |
| `calibration-02/unit-price-1` | Recorrido de 302,0 s. Ambos roles aceptaron 257,50 sin preguntar la base monetaria: reproducción autónoma de DR-001. | Informe retenido; ejemplos explícitos de definiciones suficientes e insuficientes. |
| `matrix-01` | Serie detenida entre fases para aplicar la corrección surgida de la calibración. | Conservar la investigación parcial; nueva identidad de lote. |
| `matrix-02` | Once sesiones fallaron al pedir una inspección ya suministrada. El resto de la matriz no se ejecutó. | Esquema de planificación restringido según perfiles pendientes. |
| `matrix-03` | Pregunta correcta, respuesta guardada y cálculo correcto de 1.220,00/59; bloqueo posterior por intentar registrar de nuevo una investigación terminada. Segunda sesión detenida entre fases. | Esquema de investigación con claves pendientes y acciones disponibles; restricciones por rol y presupuestos de revisión. |

La eliminación de duplicados exactos redujo un contexto de revisión de 68.210 a
51.014 bytes (25,21 %) conservando los cuatro turnos y todos los objetos distintos.
Esto no es un resumen de memoria ni una solución general de compactación.

Los porcentajes literales del informe necesitan una comprobación aritmética
recalculada; un margen de tolerancia amplio no permite justificar texto incorrecto.
Se conservaron las pruebas de recuperación, invalidación de evidencias, aislamiento,
integridad y límites anteriores, y se añadieron regresiones para el evaluador,
porcentajes, contexto y acciones disponibles. La suite de 87 pruebas pasó de nuevo
tras el reinicio en 50,517 s. El comprobador independiente de fixtures verificó tres casos, tres
variantes, procedencia y referencias numéricas.

Las pruebas automatizadas de fallos deliberados utilizan modelos controlados
para provocar transiciones concretas, con PostgreSQL y el sandbox reales. No
son 87 ejecuciones de Qwen ni demuestran su exactitud semántica. La matriz real
ejecuta cada fase desde un proceso nuevo; comprueba la recuperación del estado
y una reanudación final sin repetir llamadas. Se informa por separado de las
correcciones posteriores del propietario.

## Serie final

La serie `matrix-04` sufrió una interrupción del ordenador confirmada por el
usuario. LM Studio registró un motor Metal no disponible y estados de recuperación;
la API devolvió HTTP 400 en 23 intentos. El último consiguió terminar tras la
recuperación, pero su informe se retuvo por DR-004. Los errores de disponibilidad
son fallos del entorno, no evidencia de exactitud semántica. Se conservan todos
los registros. La serie `matrix-05` ejecutó los 24 casos tras comprobar PostgreSQL,
el perfil Colima del proyecto y progreso real de inferencia, con inhibición
temporal del reposo. Su código permaneció fijo, con SHA-256
`0cb7f0e8387987c9315ea945b73f266b9c3ef0d8404997a277f8ce91d3789ff5`;
se conserva una copia privada del código para reproducir esa versión.

**Resultado de la matriz: 11 de 24 casos aceptados.** Terminaron 17 recorridos;
se retuvieron seis de sus aprobaciones por fallos semánticos. Otros cuatro
intentos fallaron y tres agotaron el plazo de revisión. Las correcciones del
propietario y las regresiones de una versión posterior se documentan aparte.

| Escenario | Repeticiones terminadas | Aceptadas independientemente | Observación |
|---|---:|---:|---|
| Precio unitario | 3 | 3 | Pregunta material y 1.220,00/59 correctos. Los tres borradores necesitaron revisión de gráficos; el tercero también un porcentaje con su comprobación. |
| Total de fila, columnas renombradas | 3 intentos; 2 recorridos terminados | 0 | Dos aprobaciones retenidas por DR-006 y DR-007. El tercero termina en ReadTimeout tras dos devoluciones. Los totales 257,50/59 son correctos. En las dos primeras repeticiones el analista corrigió por sí mismo un error de sintaxis Python. |
| Respuesta «no lo sé» | 3 intentos; 1 recorrido terminado | 1 | Primer intento falla por identificadores de tabla; segundo, por evidencias inventadas (DR-008). El tercero entrega 59 unidades y las siete fechas correctas tras corregir el gráfico, sin importe monetario ni nuevas preguntas del grafo. |
| Respuesta «prefiero no responder», columnas renombradas | 3 | 3 | Las tres omiten dinero y entregan cantidades sin insistir en el grafo. Una corrige gráfico y porcentaje tras devolución; otra calcula el desglose antes de su primer borrador. Se conservan notas editoriales y límites de los controles de formato. |
| Ventas diarias | 3 intentos; 2 recorridos terminados | 1 | Una aprobación retenida por asignar los mínimos a fechas incorrectas (DR-004); una entrega correcta tras revisión; otra interrumpida a los 20 minutos de revisión, con rechazo innecesario de precisión y mal diagnóstico del revisor (DR-009). |
| Ventas diarias, columnas renombradas | 3 intentos; 2 recorridos terminados | 0 | Un programa repite consultas sobre una conexión cerrada y culpa a fechas válidas (DR-010). Los otros dos calculan correctamente, pero se retienen por mezclar totales y medias en barras (DR-004). |
| Ventas por producto | 3 intentos; 1 recorrido terminado | 1 | Dos agotan 20 minutos de revisión: uno deja un borrador correcto sin aprobación final; otro mantiene una alerta falsa de 108 conflictos de nombres (DR-011) y una referencia no guardada. El tercero entrega comparación y ranking correctos tras retirar porcentajes agregados sin check; también valida correctamente la relación identificador–nombre. |
| Ventas por producto, columnas renombradas | 3 | 2 | Dos informes correctos tras devoluciones. El tercero recalcula porcentajes, pero conserva «Top 5 restantes» para una suma que incluye al líder; aprobación retenida (DR-004). |

### Correcciones posteriores del propietario

Se repitió tres veces el cambio explícito de precio unitario a total de fila,
reutilizando la misma empresa, importación y CSV de una sesión aprobada. Las
**tres** recalcularon 257,50/59, invalidaron la aprobación anterior (`stale`, no
publicable) y terminaron con una reanudación idempotente. Esto no implicó tres
informes aceptables:

| Repetición | Evaluación del nuevo informe | Observación |
|---|---|---|
| 1 | Aceptado | El revisor detectó un gráfico que repetía el máximo; el analista calculó las siete fechas y corrigió también el alcance hasta el 15 de abril. |
| 2 | Retenido | El revisor aprobó limitaciones falsas sobre el precio neto por unidad y las sumas por producto, y pidió usar el rango de la muestra como rango completo (DR-007 y DR-004). |
| 3 | Retenido | Corrigió los gráficos, pero aprobó la afirmación falsa de que no puede derivarse un precio neto por unidad por faltar costes y ser un total de fila (DR-007). |

Duraciones registradas: 578,18 s, 505,81 s y 373,13 s; 26 llamadas en conjunto,
217.639 tokens de entrada y 23.771 de salida, con uso informado completo. Las
exportaciones antiguas se volvieron a generar como bloqueadas; su evaluación y
exportación históricas se preservan por separado. El éxito histórico no convierte
una aprobación obsoleta en vigente.

### Regresiones del controlador

Después de terminar la matriz y las tres correcciones se aplicaron restricciones
de identificadores reales, parejas de evidencia válidas y aridad de checks;
precisión de porcentajes según el texto; recuperación de metadatos tras muerte
del proceso y contabilidad explícita del uso desconocido. No se introducen valores
de referencia ni se reescribe el Python del agente.

**101 pruebas automatizadas pasaron en 41,407 s**, junto con el comprobador de
los tres fixtures y sus tres variantes y `git diff --check`. Incluyen pruebas
reales de infraestructura y modelos controlados para transiciones deliberadas;
no son 101 ejecuciones de Qwen. Las nuevas regresiones cubren referencias
inexistentes, fórmulas con operandos de más, precisión falsa y doble redondeo,
interrupciones con fallos de recuperación y consumo incompleto.

La serie separada `focused-06` prueba respuestas desconocidas, rechazadas y ventas
diarias, tres veces cada una, con código
`6bd2e81529cc03755940a51c259fbe5ca8eeed37ed0863c1c9d18e57715c6617`.
Su resultado no se mezcla con la matriz anterior ni sustituye sus fallos.
**Resultado: 6 de 9 aceptadas; dos aprobaciones retenidas y un fallo.** Terminaron
ocho recorridos y no hubo interrupciones por tiempo en esta serie.

Las seis repeticiones sobre respuestas opcionales produjeron cuatro informes
aceptados, una aprobación retenida y un fallo antes de la revisión:

| Escenario | Aceptadas | Observación |
|---|---:|---|
| Respuesta «no lo sé» | 2 de 3 | Las tres preguntan una vez, omiten dinero y conservan cantidades. El revisor solicita y obtiene los siete valores diarios tras detectar gráficos que repetían el total global. La segunda aprobación se retiene por afirmar actividad no diaria a partir de un archivo seleccionado (DR-006). |
| Respuesta «prefiero no responder» | 2 de 3 | La primera corrige tanto el gráfico como el máximo diario. La segunda bloquea cantidades por una incertidumbre exclusivamente monetaria: no ejecuta Python ni llega al revisor (DR-012). La tercera presenta cantidades correctas, pero conserva un contador auxiliar de SKU erróneo que el informe no usa (DR-013). |
| Ventas diarias | 2 de 3 | Las dos primeras entregan cifras y gráficos admisibles tras devoluciones. La tercera calcula correctamente, pero el revisor aprueba barras de totales y medias sobre el mismo eje: informe retenido por DR-004. |

No aparecieron identificadores inexistentes ni referencias inventadas en estas
seis repeticiones. La API aceptó las restricciones estructuradas añadidas. Esto
no elimina las interpretaciones erróneas ni garantiza el comportamiento ante
otros archivos.

En la primera repetición diaria, 16,1 % pasa con precisión completa y el revisor
corrige etiquetas de tabla y una cobertura porcentual sin check. En la segunda,
el controlador rechaza usar un total como porcentaje y después almacenar 16,1
con tolerancia 0,01. El revisor acaba pidiendo precisión completa y aprueba un
informe correcto, tras 1.155,94 s de revisión. Dos programas intermedios guardan
medianas como cero y controles constantes con descripciones falsas (DR-014);
el informe final conserva las estadísticas correctas de la primera ejecución.
Se acepta ese informe, sin certificar las métricas auxiliares defectuosas.

La última repetición diaria tiene fechas de extremos y desviaciones estándar
correctas, pero reproduce DR-004 sin devolución del revisor. El evaluador retiene
la aprobación y vuelve a exportar el informe como bloqueado. En los nueve casos,
la aceptación independiente y el estado actual del informe quedan registrados.

Recursos de `focused-06`: 70 llamadas, 724.398 tokens de entrada y 89.958 de salida,
con uso completo. Suma de fases: 5.547,80 s (92,46 min); mediana por intento
603,60 s (10,06 min), mínimo 85,80 s y máximo 1.269,03 s. El mínimo corresponde
al fallo temprano, no a una entrega rápida de informe.

Tras terminar todos los agentes se corrigió únicamente la navegación HTML del
evaluador para no enlazar registros inexistentes de casos históricos no ejecutados.
Se regeneraron diez índices y se comprobaron sus 427 enlaces locales sin roturas;
las 14 pruebas del evaluador y sus recursos volvieron a pasar. Esta comprobación
es de estructura y enlaces, no una revisión visual en navegador. El código del
agente no cambió; las versiones exactas de las dos series quedan preservadas en
sus copias privadas.

### Recursos de la matriz

Se registraron 216 llamadas. La suma de tiempos por fase es al menos 18.109,26 s
(unas 5,03 h); la mediana registrada por intento es 784,34 s (13,07 min), con
mínimo 191,33 s y máximo registrado 1.416,21 s. No incluyen esperas entre lotes
ni toda la revisión independiente. Tres fases interrumpidas se recuperaron desde
PostgreSQL y conservan 1.200 s como cota inferior; no se inventa una duración exacta.
Estos tiempos no satisfacen una experiencia interactiva de entrega al cliente.

El servidor informó 2.130.337 tokens de entrada y 275.375 de salida conocidos.
Falta el uso de una llamada en cada uno de `line-total-3`, `daily-3`, `products-1`
y `products-2`: los totales completos son desconocidos. No se contabilizan como
cero ni se estima un precio monetario local. Se distinguen tokens informados,
llamadas sin uso disponible y completitud del registro.

La entrega 1 no se declara aceptada por una aprobación del modelo ni por el
resultado de las pruebas del controlador.

Los registros detallados permanecen en `.local/evaluation/`, y los informes
exportados en el almacenamiento privado configurado. No se publican datos de
clientes, registros del modelo ni rutas personales en Git.

## Qué queda abierto

La evaluación mide respuesta a la pregunta, exactitud y límites del caso. No
convierte un informe descriptivo correcto en un análisis comercial profundo.
Los hallazgos triviales, la falta de objetivos del negocio y la amplitud de la
investigación siguen siendo mejoras de producto pendientes, tal como se acordó.

Las restricciones del controlador evitan formas de llamada imposibles; el modelo
todavía puede escoger una interpretación, etiqueta o abstención equivocadas. Se
mantienen abiertos los errores semánticos documentados y la latencia de Qwen local.
Una métrica auxiliar incorrecta aunque no llegue al informe tampoco desaparece:
se registra por separado, sin presentar la aceptación del informe como garantía
de todo el caché analítico.

El trabajo de construcción y ejecución del evaluador puede terminar con casos
fallidos. El criterio de aceptación de la entrega 1 continúa abierto. Antes de
aceptarlo se necesita una iteración acotada sobre los errores materiales y repetir
los casos afectados con identidad nueva. Un cambio de modelo también requiere
medición real. La aplicación web sigue correspondiendo a la entrega 2; no se ha
implementado ni se ha declarado aceptada en este paso.
