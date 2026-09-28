# 3.7 — Planificador de negocio: validación

Estado: implementación y evaluación terminadas. Mejora general de calidad no demostrada.

## Qué se compara

El [plan](../technical/business-planner-plan.md) introduce un rol especializado que
mantiene el encargo y dialoga con el analista principal. El conversacional sigue
presentando todas las preguntas. Los trabajadores conservan su tarea analítica y
no crean otro nivel de agentes ni conversaciones con el cliente.

La matriz parte de los CSV originales de Bruma Café y WWI usados en 3.6. Tres casos:
Bruma-descubrir, WWI-organizar y WWI-descubrir. Dos repeticiones por caso, alternando
el orden de control/planificador: 12 intentos. Ambos modos usan tres trabajadores,
la misma configuración de modelo y el mismo presupuesto amplio. El control desactiva
las consultas al planificador; no se confunde esta comparación con serial/paralelo.

El perfil amplio permite 12 investigaciones, 8 rondas, 48 programas, 128 llamadas y
192 decisiones; una hora desde el inicio, descontando la espera del cliente. Revisión: 8 rondas y
6 programas por rol. Los límites de contexto y contratos numéricos siguen vigentes.
El coste no se usa para seleccionar la calidad mínima; el consumo se registra.

Cada caso tiene negocio y estado aislados. Fuentes, modelo, configuración, código y
referencias independientes quedan congelados. Una importación/consulta real en Docker
comprueba el entorno antes de llamar al modelo. Los oráculos CSV/Decimal no llegan a
los agentes. Una pregunta nueva en la matriz recibe «desconocido»; no se inventan
respuestas operativas después de ver los resultados esperados.

Los 16 intentos de 3.6 permanecen intactos. Su comparación con 3.7 es histórica:
además del planificador cambian presupuesto y algunos prompts, por lo que no permite
atribuir causalmente toda mejora al nuevo rol. El control del lote 3.7 separa esas
variables en la medida que permite una muestra pequeña y estocástica.

## Aceptación

Se conserva la rúbrica del 3.6 y el vínculo al hash de cada informe. Aprobación del
producto no equivale a aceptación independiente. Se comprueba cada cifra citada y
punto visual contra la fuente, además de significado, cobertura, profundidad,
prioridad, siguientes comprobaciones, comparabilidad, claridad y duplicación.

La revisión independiente la realiza el desarrollo leyendo las entregas, sin usar
la aprobación del agente como criterio ni pasar respuestas esperadas al sistema.
No es una evaluación ciega de clientes reales. Los fallos siguen en el denominador;
no se sustituyen por reintentos mejores. Los tiempos de informes aceptados se
comparan solo cuando ambos miembros de una pareja cumplen los criterios.

## Comprobaciones de integración

- Persistencia del encargo, consultas por fase, costes registrados y transmisión
  del contexto a los trabajadores y a la revisión.
- Pausa después de obtener resultados, respuesta contextual y reanudación sin
  repetir ramas/cálculos; respuestas desconocidas conservadas.
- Respuestas que cambian definiciones requieren planificación sucesora; la evidencia
  antigua queda obsoleta y el mismo trabajo web continúa en la nueva sesión.
- Aislamiento de negocio, claves idempotentes, rechazo de cambios a una respuesta
  ya guardada y recuperación de un fallo del planificador sin repetir las ramas.
- Referencias a columnas entregadas al componente existente de datos, tanto en
  detalle de trabajo como en la conversación. Los trabajadores no pueden consultar
  al planificador ni preguntar directamente al propietario.

Pruebas iniciales: 122 de regresión correctas y pruebas web específicas. Se corrigió
la serialización de identificadores en respuestas y su desaparición del resumen
al comenzar la revisión. Son correcciones de protocolo; no evidencias de utilidad
analítica del modelo.

## Lotes reales y correcciones

Se conservan tres versiones, sin sustituir intentos fallidos:

1. **Inicial:** 12 intentos, planificador v1, contexto 200 KB, tres intentos por
   investigación y dos reparaciones de contrato de revisión.
2. **Corrección dirigida:** ocho intentos, planificador v2 con instrucciones de
   negocio al entregar, contexto 512 KB, seis intentos por investigación y cuatro
   reparaciones de contrato. Cuatro Bruma y dos por cada objetivo de WWI.
3. **Código final:** cuatro intentos, Bruma y WWI-descubrir, planificador v3. Añade
   transmisión explícita de consulta/síntesis del analista y corrección de
   procedencia de memoria. Estas dos conexiones tienen regresiones específicas.

Todos usan el mismo modelo `gpt-6-luna`, esfuerzo `low`, salida máxima 16.384 tokens,
timeout de proveedor 300 segundos y tres trabajadores. Esta configuración conserva
comparabilidad; no implica que sea la mejor combinación de modelos para producción.
No se aplicó un objetivo de coste bajo. Los tiempos incluyen llamadas, ejecución,
revisión y recuperación; algunos ensayos se solapan y no son un benchmark aislado.

### Lote inicial: 3/12 aceptados

| Caso | Modo | Segundos | Aprobado por producto | Aceptado independientemente | Referencias comprobadas |
|---|---|---:|:---:|:---:|---:|
| Bruma 1 | Control | 252,903 | Sí | No | 45 |
| Bruma 1 | Planificador | 324,394 | Sí | No | 43 |
| Bruma 2 | Planificador | 322,550 | Sí | No | 55 |
| Bruma 2 | Control | 221,515 | Sí | Sí | 35 |
| WWI-organizar 1 | Control | 176,892 | Sí | Sí | 108 |
| WWI-organizar 1 | Planificador | 320,231 | No | No | — |
| WWI-organizar 2 | Planificador | 406,926 | No | No | — |
| WWI-organizar 2 | Control | 222,953 | Sí | Sí | 93 |
| WWI-descubrir 1 | Control | 104,023 | Sí | No | 40 |
| WWI-descubrir 1 | Planificador | 393,153 | No | No | — |
| WWI-descubrir 2 | Planificador | 231,207 | Sí | No | 31 |
| WWI-descubrir 2 | Control | 152,514 | Sí | No | 32 |

Control: 3/6 aceptados y 6/6 publicados. Planificador: 0/6 aceptados y 3/6
publicados. Todas las cifras citadas de las nueve entregas publicadas coinciden
con los oráculos; la utilidad exige más que corrección aritmética. Los tres fallos
son una acción inválida del revisor y dos excesos del contexto disponible. Los
casos de descubrimiento rechazados carecen de suficiente prioridad, profundidad
o comprobaciones concretas. El planificador detectó una divergencia entre ventas
y margen y recuperó cálculos pendientes, pero eso todavía no produjo entregas
consistentemente útiles. Este lote **no muestra mejora**.

Consumo registrado: control 2.718.310 tokens de entrada y 130.873 de salida;
planificador 5.269.986 y 225.969. Uso disponible para todas las llamadas. No se
convierte en importe monetario sin tarifas verificadas. No hay parejas con ambas
entregas aceptadas que permitan comparar tiempo de una entrega útil.

### Corrección y comprobaciones

La orientación final del planificador exige prioridad relativa y una comprobación
operativa concreta; añadir cálculos no basta. Se amplían los límites internos que
interrumpían trabajo útil. Cuatro reparaciones no convierten una respuesta inválida
en aprobación: después del límite se conserva el fallo y su evidencia.

Pruebas: 96 de núcleo y 111 de integración (hay solapamiento), más 46 de revisión,
18 de memoria y 51 finales de protocolo/contratos/evaluación. No sumar estos grupos
como casos únicos. Interfaz: 80/80, compilación y lint sin errores; permanecen
advertencias preexistentes de hooks/componentes y tamaño del bundle.

Regresiones concretas: recuperación de trabajadores después de tres programas
fallidos, contexto amplio sin pérdida silenciosa, respuesta contextual que no
invalida su propia investigación, retirada de memoria que sí la invalida, consulta
explícita y síntesis entregadas al planificador, pregunta con datos abiertos en la
conversación original, desconocido sin bloqueo y nuevo plan ante cambio de definición.
La corrección de memoria se prueba con PostgreSQL real y modelos controlados; los
lotes reales no inventan respuestas operativas para ejercitarla.

Las citas textuales compuestas también se comprueban: sus nombres y cifras se
construyen a partir del oráculo, con formato acotado y sin números literales. La
rúbrica no cambia; el resumen registra la huella del evaluador utilizado.

### Lote corregido: 4/8 aceptados

| Caso | Modo | Segundos | Aprobado | Aceptado | Referencias |
|---|---|---:|:---:|:---:|---:|
| bruma-discover · 1 | control | 150.533 | Sí | No | 21 |
| bruma-discover · 1 | planner | 416.661 | Sí | Sí | 51 |
| bruma-discover · 2 | planner | 305.896 | Sí | Sí | 35 |
| bruma-discover · 2 | control | 221.694 | Sí | Sí | 26 |
| wwi-organize · 1 | control | 313.19 | Sí | Sí | 101 |
| wwi-organize · 1 | planner | 121.695 | No | No | — |
| wwi-discover · 1 | control | 228.347 | Sí | No | 58 |
| wwi-discover · 1 | planner | 292.776 | Sí | No | 39 |

En Bruma, control 1/2 frente a planificador 2/2. Las dos entregas con planificador
incluyen un cruce útil, prioridad relativa y comprobación de disponibilidad o días
efectivos de venta. La pareja con ambas aceptadas tarda 84,202 segundos más con
planificador (305,896 frente a 221,694); no se demuestra reducción de latencia.

En WWI-organizar, el control entrega las tres métricas anuales, mensuales y por
categoría. El planificador se interrumpe por 429 tras agotar los reintentos. En
WWI-descubrir, el planificador profundiza en cantidades e importe por unidad de
dos productos con trayectorias opuestas y propone comprobar surtido/disponibilidad;
el control profundiza en productos dentro de una categoría, pero conserva acciones
genéricas. Ninguno alcanza aceptación completa: entre otros límites, la primera
presentación de «ventas» no aclara suficientemente que incluye impuestos, aunque
sí figure en métodos, unidades de algún gráfico o limitaciones.

Consumo conocido de Bruma: control 791.874/41.698 tokens entrada/salida;
planificador 1.577.470/72.569, completo. WWI: control 1.015.382/56.871 y planificador
970.557/44.406, **parciales** por intentos de transporte con uso desconocido. No
interpretar ausencia de uso como cero ni sumar estimaciones como coste exacto.

### Código final: 0/4 aceptados en el primer intento

| Caso | Modo | Segundos | Aprobado | Aceptado | Referencias |
|---|---|---:|:---:|:---:|---:|
| bruma-discover · 1 | control | 168.331 | No | No | — |
| bruma-discover · 1 | planner | 230.667 | Sí | No | 56 |
| wwi-discover · 1 | control | 107.543 | No | No | — |
| wwi-discover · 1 | planner | 140.312 | No | No | — |

Tres interrupciones por HTTP 429; se mantuvieron los intentos rechazados y el
trabajo guardado. El Bruma publicado contiene 56 referencias correctas, pero vuelve
a priorizar la mayor celda por volumen sin justificar su importancia relativa;
además, no entrega directamente los totales mensuales requeridos por la evaluación.
Se rechaza aunque la aritmética sea correcta. No se seleccionan solo los dos Bruma
favorables del lote anterior para declarar una mejora general.

Uso conocido: control 494.910/26.561 tokens; planificador 586.510/36.187. Ambos
incompletos por los 429. Las interrupciones coinciden con tandas solapadas; no se
ha establecido su causa exacta en el proveedor. No prueban por sí mismas un defecto
analítico del planificador ni permiten una comparación justa de tiempos.

### Recuperación real

Tres reanudaciones explícitas, en secuencia y después de terminar las otras tandas.
Todas conservan las ejecuciones previas y llegan a informe aprobado por el producto;
volver a reanudar el informe final no repite llamadas ni cambia su hash aprobado.

| Caso recuperado | Recuperación (s) | Original + recuperación (s) | Aceptado | Referencias |
|---|---:|---:|:---:|---:|
| Bruma · control | 228,772 | 397,103 | Sí, parcial útil | 40 |
| WWI-descubrir · control | 209,702 | 317,245 | No | 45 |
| WWI-descubrir · planificador | 328,612 | 468,924 | No | 48 |

Los tiempos acumulados suman los dos intentos; no incluyen la espera entre tandas.
Las tres recuperaciones permanecen separadas de los 24 intentos originales. Bruma
entrega la caída de tienda descompuesta por productos con una comprobación concreta.
WWI-control conserva un problema de claridad monetaria. WWI-planificador profundiza
en compradores y productos, pero el informe omite explicar que ExtendedPrice incluye
impuestos y propone al cliente desgloses que ya están calculados o que los datos
permiten calcular. La identidad del comprador con mayor caída tampoco queda clara
en el texto. La aritmética comprobada es correcta; la entrega no supera el estándar
de significado y utilidad. No se realizan más repeticiones para buscar aprobación.

Uso conocido acumulado de las recuperaciones: control 1.472.058/81.630 tokens de
entrada/salida en dos casos; planificador 1.394.514/50.728 en uno. Incluye sus llamadas
originales y sigue siendo incompleto por los 429; **no sumar** estos valores a los
del lote final porque duplicaría esas llamadas originales.

### Extensión independiente del oráculo

La rama categoría×producto de WWI necesitó una dimensión no prevista en el oráculo
inicial. Se generaron 8.760 valores con CSV/Decimal para todos los pares observados,
y se conciliaron ventas netas, impuestos, margen y cantidades con **todos** los
totales año/categoría congelados. El suplemento identifica fuentes, productor y
oráculo base; no puede reemplazar claves originales ni relajar requisitos. No
llega a los agentes. El resumen registra su huella y las del evaluador/productor.
Esta ampliación de evaluación es posterior al código congelado final; el producto
no cambia. Pasan 29 pruebas del evaluador, incluyendo rechazo de sobrescritura de
resultados esperados o referencias a fuentes distintas.

## Lectura de los resultados y pendientes

La separación de roles, el diálogo y las preguntas funcionan en las comprobaciones
de integración. Hay entregas mejores y señales de mayor profundidad, pero **no queda
demostrada una mejora consistente de aceptación general**. Más trabajo y más agentes
no garantizan una mejor síntesis; tampoco se acredita ahorro de tiempo o coste.

Antes de ampliar agentes, priorizar:

1. Selección de la señal por importancia para una decisión, evitando regresar al
   mayor volumen como justificación única.
2. Definición visible de cada medida monetaria en su primera presentación, coherente
   con gráficos, texto y contexto del propietario.
3. Entrega completa de los componentes solicitados y una síntesis más breve, con
   menos cautelas repetidas y menos rankings extensos.
4. Evitar que el siguiente paso pida al cliente cálculos disponibles y conservar
   identificados los segmentos relevantes al sintetizar.
5. Control de concurrencia/cuotas del proveedor para cargas simultáneas, conservando
   evidencia y distinguiendo fallos de transporte de calidad analítica.

La implementación de 3.7 se cierra con estas limitaciones documentadas; la
aceptación general del producto continúa abierta. Predicción y brainstorming no
se presentan como modalidades ya disponibles.

## Reproducción y artefactos

Con PostgreSQL, Docker y configuración del proveedor preparados:

```sh
python -m decision_room.evaluation.business_planner_runner .local/evaluation/planner-new \
  --wwi /ruta/a/wwi/csv --bruma /ruta/a/bruma/csv --repeats 2
```

Cada lote guarda manifest, huellas de fuentes/código/modelo, oráculos, informes,
llamadas/ejecuciones, assessment ligado al hash del informe, resumen JSON y HTML.
Los artefactos locales están en `.local/evaluation/business-planner-37/`:
`matrix`, `targeted-v2`, `wwi-targeted-v2`, `final` y `final-recovery`. No se publican credenciales,
rutas personales, CSV privados ni grandes registros de ejecución. Las evaluaciones
independientes se realizan después de la generación, leyendo cada entrega; ejecutar
el runner por sí solo no certifica utilidad ni produce esa revisión del contenido.

Huellas de código de generación (SHA-256, no commits): inicial
`1c23f3c9380b72070aff5216afab4d6dd17dc6767a43e3378f956ef78f9226cb`,
corregido `e86a4f4670085a566231128765f9d515730080fe39e27a1ed92328d9126cca22`,
final `6155eec322e48b5ad98fe2e4bae151bfc2f35fdb7b720b1a79bf84dce500393c`.
El último cambio del evaluador admite suplementos independientes; su huella se
registra por separado y no representa un cambio del producto durante las pruebas.

Vista local actualizada y comprobada por HTTP autenticado (200), esquema 24.
El código de producto y el esquema coinciden con la copia del lote final; únicamente
se amplió después el evaluador para los cruces independientes. Revisión de cambios
y de archivos preparados para Git: sin credenciales, rutas personales, datos privados
ni artefactos grandes; sin cambios ajenos descartados. Commit local, sin push.
