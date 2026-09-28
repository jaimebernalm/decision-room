# Paso 3.6 — Evaluación independiente de calidad

Estado: implementación y evaluación de 3.6 finalizadas el 28 de septiembre. La aceptación general de calidad del producto sigue abierta; los resultados no justifican promover el paralelismo como mejora garantizada.

## Protocolo y separación de responsabilidades

Se aplica el [protocolo previo](../technical/quality-evaluation-plan.md). Los
modelos reciben fuentes y declaraciones del propietario; nunca oráculos,
resultados esperados, puntuaciones ni evaluaciones de otros recorridos.

La política común nueva distingue organizar, descubrir, responder una pregunta,
evolución e intención libre/mixta. Solicitudes de predicción siguen fuera del
alcance del producto. Los tres roles comparten los criterios, pero conservan
funciones y herramientas diferentes.

La matriz compara coordinador con trabajadores en serie (`max_parallel=1`) frente
a hasta tres simultáneos (`max_parallel=3`), con las mismas cuotas globales.
Ambos mantienen delegación. **No compara un único analista sin coordinación**.
Hay dos repeticiones por cada caso, con orden alternado y ejecuciones completas
una detrás de otra. Los planes son independientes y estocásticos; no atribuir
causalmente al planificador toda diferencia de tiempo o calidad.

Casos: Bruma-descubrir; WWI-organizar; WWI-descubrir; WWI-pregunta concreta.
WWI utiliza los cinco CSV completos de 3.1 (299.673 filas). Bruma utiliza los
cuatro CSV originales de 3.4.1, con la definición monetaria desconocida y alcance
aceptado de unidades. No se cambia ese alcance para facilitar la evaluación.

El contexto de entrada equivale al alcance aceptado del onboarding. La interacción
conversacional y su recuperación se cubren por pruebas de integración; no se
presenta esta matriz como dieciséis sesiones de interacción humana completas.

## Aceptación independiente

Cada evaluación se vincula al hash del informe exacto y contiene:

- Mapeos explícitos de cada referencia numérica citada y cada punto visual a una
  referencia CSV/Decimal. Incluye nombres cuando están citados como métricas.
- Revisión de significado, cobertura, profundidad, prioridad, próximas
  comprobaciones, comparabilidad temporal, claridad, duplicación y cifras en prosa.
- Puntuaciones: 0 = defecto material, 1 = útil con límites, 2 = criterio satisfecho.
  Ningún cero puede aprobar. Los criterios esenciales de cada intención requieren 2.
- Una entrega parcial útil queda etiquetada como parcial; no equivale a cobertura
  completa. No calcular un resultado factible no es una limitación de los datos.

La aplicación de referencias permite solo claves del oráculo y operaciones
aritméticas declaradas, sin ejecutar el programa del agente. No se acepta una
cifra simplemente porque coincida con algún número en la referencia. La revisión
semántica de etiquetas, unidades y alcance sigue siendo necesaria.

Los hashes de fuentes, código y referencias impiden mezclar cambios en un lote.
La versión del evaluador independiente queda registrada aparte. La calibración
previa del instrumento se conserva fuera de la matriz: no se usa para seleccionar
solo los mejores informes ni para sustituir repeticiones fallidas.

## Recursos

Se cuentan todas las llamadas de cada sesión, incluidas correcciones, trabajadores,
revisiones y fallos, el descubrimiento de relaciones anterior a la sesión y todas
las ejecuciones del negocio aislado. Se corrigió durante la auditoría una omisión
del recolector: inicialmente no incluía `data_model_discoveries`. Se conservan las
copias anteriores y se completó el uso desde la base de datos sin repetir llamadas. Los reintentos de
transporte se conservan en el uso registrado. Uso desconocido nunca se convierte
en cero. Los tokens de entrada incluyen caché; no son coste facturado.

Se presentan tiempos de todos los intentos terminales y de los aceptados por
separado. Sin uso completo y tarifas explícitas fechadas no se publica un coste
monetario. Las tarifas opcionales distinguen entrada, caché y salida.

## Controles comprobados antes de la matriz

- 165 pruebas backend correctas: onboarding, investigación, revisión, límites,
  concurrencia, recuperación, fuentes/series, entrega, evaluación y recursos.
- El evaluador rechaza entrega modificada, cifra incorrecta, evidencia antigua,
  etiqueta de serie duplicada, unidad incompatible y puntos sin validar.
- Los fallos y los recorridos no ejecutados permanecen en el denominador; no se
  atribuye una ventaja de velocidad a una ejecución fallida más corta.
- El oráculo comprueba uniones únicas y referencias, signos y granularidad en WWI;
  en Bruma detecta una inversión de la lectura al corregir una exposición desigual.
- Una interrupción conserva identidad, duración y uso desconocido de la llamada.

## Comparación histórica

La referencia 3.1 aceptó 4/6 recorridos WWI; los dos fallos se conservan. Usaba dos
investigaciones y prompts anteriores. Su comparación con la matriz actual es
orientativa, no una prueba controlada de velocidad o de la aportación individual
de cada cambio. La referencia Bruma 3.4.1 y la entrega 3.5 también permanecen
intactas. La matriz nueva no reemplaza esos resultados históricos.

## Fallos encontrados durante la preparación

- La primera copia congelada no conservó el enlace al directorio de entrada
  compartido con la VM de Docker. Dos recorridos fallaron al montar los datos y
  otro al interpretar una tabla no inspeccionada. Se conservan los tres estados;
  los trece recorridos no iniciados no se presentan como ejecutados. Este lote
  queda fuera de la comparación de rendimiento por su entorno inválido.
- Se añadió una comprobación real de importación y consulta en Docker antes de
  cualquier llamada al modelo. La nueva copia conserva el montaje autorizado.
- Las salidas estructuradas del planificador ahora solo ofrecen tablas/columnas
  inspeccionadas; las de síntesis solo candidatos guardados. El caso sin candidatos
  no permite confundir trabajos bloqueados/descartados con evidencia a excluir.

## Resultados y decisión

### Matriz inicial congelada

Los 16 intentos están conservados. Ocho alcanzaron aprobación del producto y
**cuatro aceptación independiente**. La ausencia de errores aritméticos no basta
para aprobar cobertura o utilidad. No se aceptaron automáticamente los informes
que solo presentaban listas de contribuciones sin profundizar ni precisar la
siguiente comprobación.

| Caso | Serial: aceptados / intentos | Paralelo: aceptados / intentos |
| --- | --- | --- |
| Bruma — descubrir | 1/2 | 1/2 |
| WWI — organizar | 0/2 | 2/2 |
| WWI — descubrir | 0/2 | 0/2 |
| WWI — pregunta concreta | 0/2 | 0/2 |

- **Bruma:** dos entregas útiles verificadas, 39 y 49 referencias. Una investiga
  las 18 combinaciones producto/canal y compara unidades por fecha observada; otra
  profundiza en los productos de Tienda física, pero no entrega esa sensibilidad.
  Los otros intentos perdieron una ejecución correcta antes de registrarla o
  retiraron toda la entrega por un seguimiento secundario sin completar.
- **Organizar:** los dos paralelos cubren las medidas y desgloses solicitados.
  Los seriales tienen cifras correctas pero omiten el promedio mensual/por categoría
  o las ventas y margen mensuales. Uno declara la entrega parcial; ninguno cumple
  la cobertura completa exigida por esta intención.
- **Descubrir WWI:** dos entregas aprobadas tienen números correctos pero poca
  profundización y siguientes comprobaciones demasiado generales. Usan ventas con
  impuestos, expresadas así en métodos/visuales; no se confundieron con la referencia
  de ventas sin impuestos. Una promete un visual de unidades que no entrega.
  Otros dos intentos terminan por timeout del proveedor.
- **Pregunta WWI:** dos revisiones fallan por el esquema de nombres con comillas;
  otro intento termina por timeout y otro por fallo de conexión. No se presentan
  como errores aritméticos ni como entregas aceptadas.

No hay ninguna pareja caso/repetición con **ambos** modos aceptados. Por tanto, la
matriz no permite afirmar una aceleración comparable entre entregas aceptadas.
Las medianas de todos los intentos terminales son 193,97 s serial y 162,64 s paralelo;
las medianas de aceptados son 271,75 s y 150,67 s, pero corresponden a muestras de
composición diferente y no prueban una ventaja causal.

Uso conocido, incluyendo descubrimiento: serial 2.957.660 tokens de entrada y
148.581 de salida; paralelo 2.909.391 de entrada y 137.851 de salida. Ambos modos
tienen llamadas con uso desconocido. Son mínimos conocidos, no totales completos
ni coste facturado. No se publica una estimación monetaria.

### Correcciones posteriores y controles

1. Guardar la ejecución correcta como candidato antes de ampliar, con revisión
   todavía pendiente. Una ejecución fallida posterior no oculta ese resultado.
2. Entrega parcial explícita para seguimientos secundarios, auditada por el revisor;
   un resultado central o una comprobación necesaria no puede aplazarse así.
3. Revisar medidas × desgloses × periodos para asignar las vistas y cubrir lo pedido.
4. Opciones del juicio de utilidad coherentes con lo realmente entregado: un
   revisor puede considerar mala una respuesta marcada como respondida, usando
   `fail`, sin generar el estado incompatible `unavailable`.
5. Adaptar exclusivamente las enumeraciones que contienen comillas al formato
   del proveedor; conservar datos y nombres originales y validar referencias exactas
   después. Un diagnóstico aislado reproduce HTTP 400 antes y HTTP 200 después.
   Esta restricción concreta procede de la respuesta observada del proveedor;
   la [documentación de salidas estructuradas](https://developers.openai.com/api/docs/guides/structured-outputs#limitations-on-enum-size)
   describe otros límites de esquema, no ese rechazo particular.

Un primer lote de cuatro comprobaciones posteriores tuvo tres fallos de conexión
antes de planificar y un fallo del juicio de utilidad que motivó el punto 4.
Queda conservado, separado de la matriz inicial y de la comprobación final.

Control real adicional: una petición exclusivamente predictiva termina como
`not_possible`, sin inventar valores futuros ni sustituirla por historia no aceptada.
Este control verifica el límite de capacidad; no demuestra calidad predictiva.

### Comprobación final de correcciones

Cuatro nuevos recorridos, conservados aparte:

| Caso y modo | Resultado del producto | Aceptación independiente |
| --- | --- | --- |
| Bruma descubrir, serial | Aprobado, 296,81 s | No: 33 referencias correctas, tasas por fecha observada y caída de Tienda física identificadas, pero falta profundizar dentro del canal. |
| Bruma descubrir, paralelo | Fallo de descubrimiento, 17,59 s | No: el modelo compuso un identificador de tabla inexistente. |
| WWI organizar, serial | Aprobado, 254,45 s | Sí: 108 referencias, todas las medidas anuales, mensuales y por categoría solicitadas. |
| WWI organizar, paralelo | Límite de revisión, 294,45 s | No: el revisor detectó que faltaban categorías pedidas; el último borrador quedó sin aprobación al agotarse las rondas. |

La restricción nueva de identificadores de tabla se añadió **después** de ese lote:
el esquema permite únicamente los identificadores reales disponibles. Se comprobó
con pruebas de contrato y una llamada real sobre el contexto fallido de Bruma:
cuatro tablas y tres relaciones, con validación sobre todos los registros. El agente
sigue proponiendo significado y relaciones; el código comprueba identidad y datos.
No se sustituyó el recorrido fallido ni se presenta este control aislado como un
nuevo informe completo aprobado.

Dos recuperaciones explícitas de las revisiones HTTP 400 originales:

| Modo original | Tiempo adicional de recuperación | Resultado |
| --- | --- | --- |
| Serial | 38,62 s | Aprobado y aceptado independientemente: 46 referencias. |
| Paralelo | 68,59 s | Aprobado y aceptado independientemente: 40 referencias. |

Ambas mantienen los identificadores de investigación y el número de llamadas de
investigación; reabrir la aprobación es idempotente y no crea llamadas. Conservan
la política histórica de revisión 2, usando el adaptador corregido. Las cifras,
nombres, rankings, contribuciones y cambios de porcentaje se comprobaron contra
los CSV originales. Para las referencias textuales con identificador se añadieron
etiquetas derivadas directamente del catálogo a un oráculo separado de recuperación,
con procedencia y hash; ninguna cifra numérica original cambió.

Se conservan los estados y recursos **anteriores** a recuperar. Los recursos de
recuperación son acumulados y no se suman de nuevo a los originales. Estos ensayos
funcionales se solaparon con diagnósticos y pruebas locales: sus tiempos no sirven
para comparar rendimiento con la matriz inicial ni entre modos. Ningún resultado
posterior sustituye los 16 iniciales.

## Verificación final y cierre

- 209 pruebas backend: investigación paralela, rondas, revisión, evidencias,
  recursos, recuperación, onboarding, entrega web y evaluación.
- Después de las últimas restricciones de esquema: 21 pruebas de acciones,
  referencias y formato; 18 de conocimiento de datos/formato. Tras ampliar la
  comprobación de identidades textuales: 29 pruebas de evaluación/formato.
  Estas suites se solapan; no se suman como si fueran casos distintos.
- 78 pruebas frontend correctas; compilación y lint sin errores. Persisten los
  avisos existentes de Fast Refresh y tamaño del bundle.
- Diagnósticos reales: HTTP 400/200 del esquema, cuatro tablas/tres relaciones de
  Bruma validadas, rechazo de predicción no soportada y dos recuperaciones aceptadas.
- Evaluación adversarial: referencias obsoletas/incompletas, cifras erróneas,
  unidades incompatibles, identidad textual incorrecta, falta de profundidad,
  entrega parcial, interrupción y coste desconocido no se convierten en éxito.

**Conclusión:** la capacidad de evaluación de 3.6 y las correcciones descritas están
implementadas y comprobadas. La matriz inicial acepta 4/16, el lote final 1/4 y las
dos recuperaciones 2/2; son conjuntos distintos y no se fusionan en una tasa de
mejora. Se conserva el modo serial como control y no se atribuye al paralelo una
ventaja general de tiempo, coste o calidad. No se cambia automáticamente el modo
predeterminado del producto basándose en esta muestra.

La siguiente prioridad de producto es estabilizar **cobertura de lo solicitado,
profundidad y siguientes comprobaciones concretas**. Para organizar, la cobertura
completa debe caber en una entrega legible, preferiblemente con tablas compactas;
para descubrir, una señal relevante debe conducir a un desglose útil dentro del
segmento. El revisor aún aprueba algunas entregas poco profundas y otras agotan sus
rondas al corregir cobertura. Estos límites quedan abiertos y medidos; añadir más
trabajadores o seguir reintentando hasta aprobar no los resuelve.


## Configuración reproducible

- Modelo registrado: `gpt-6-luna`, protocolo OpenAI, razonamiento `low`, límite de
  16.384 tokens de salida por llamada y timeout de 300 segundos.
- Investigación: hasta 6 investigaciones ejecutadas, 3 rondas, 12 ejecuciones
  Python, 32 llamadas y 900 segundos; 30 segundos por programa. Mismo presupuesto
  en ambos modos, incluidos los trabajadores; cambia `max_parallel` de 1 a 3.
- Revisión: 4 rondas, hasta 3 programas Python por rol. Los límites no se elevan
  para conseguir una aprobación en el lote inicial.
- Matriz congelada: planificación v15, investigación v23, revisión v32/política 2.
  Correcciones: planificación v16, investigación v25, revisión v34/política 3,
  junto a las correcciones de esquema que identifica el hash de cada lote.
- Los hashes exactos de fuentes, código, referencias y configuración quedan en
  los manifiestos locales. Datos, informes, conversaciones y rutas de máquina no
  se incorporan al repositorio público.

La revisión del evaluador añadió referencias derivadas (diferencias, ratios,
conciliaciones booleanas y nombres ligados a fuentes). Esto permite comprobar
una diferencia pedida sin exigir una disposición concreta de sus cifras base.
No añade cifras esperadas a los agentes, no altera el oráculo congelado y no
sustituye la revisión de unidades, significado, cobertura o narrativa. El hash del
evaluador se registra separado del sistema sometido a prueba. Todas las entregas
se resumen con la misma versión final del evaluador.
