# Validación del paso 1.5 — 21 de septiembre de 2026

El agente principal está conectado al ejecutor aislado. Estas comprobaciones
separan el funcionamiento del controlador, las ejecuciones reales de Qwen y la
corrección de cifras concretas. No constituyen aceptación del modelo ni del MVP.
El fallo semántico [DR-001](known-agent-errors.md) continúa abierto por decisión
explícita de avanzar y evaluar posteriormente el recorrido con revisor.

## Entorno y alcance

- Python 3.12, LangGraph, PostgreSQL local y Docker en Colima; sin dependencias
  nuevas para este paso. Se conserva el entorno del paso 1.3.
- Modelo real: `qwen3.8-27b-splash`, LM Studio local, API nativa, razonamiento
  desactivado, temperatura 0. No se llamó a un proveedor externo.
- Prompt de investigación `research-v2`; controlador final `research-v3`.
- Referencias públicas pequeñas de ventas diarias e importe ambiguo. El modelo
  recibe CSV, contexto y aclaraciones del propietario; nunca `expected.json`.
- Nadie editó los programas generados para conseguir las cifras esperadas.

## Pruebas automáticas

`python -m unittest discover -s tests -v`: **45 pruebas superadas**, 31,510 s.
`python -m pip check`: sin dependencias incompatibles.

Diez pruebas nuevas del controlador de investigación usan PostgreSQL y Docker
reales y un modelo **simulado explícitamente**. Verifican:

- Código, resultados y evidencia persistidos; repetición idempotente.
- Error SQL real devuelto al modelo y corrección posterior.
- Muerte de un proceso después de Python y antes del checkpoint: otro proceso
  recupera el trabajo con una sola ejecución, sin duplicarla.
- Cambio de precio unitario a total de fila: resultado anterior obsoleto y
  recálculo de 80 a 30, conservando el vínculo entre sesiones.
- Rechazo de tablas ajenas y consultas de otra empresa.
- Rechazo de métricas inexistentes y límite de tres intentos Python.
- Dependencias bloqueadas y límite de contexto.
- Investigación independiente mientras se espera una respuesta; responder
  invalida conservadoramente el trabajo anterior.
- Corrección acotada de JSON malformado antes de ejecutar.
- Rechazo de terminar sin registrar o bloquear una investigación ya ejecutada.

Estas pruebas demuestran reglas del programa, no competencia analítica del LLM.

## Ventas diarias: ejecuciones reales

El primer recorrido (`research-v1`) falló: tres programas omitieron evidencia
para algunas métricas de validación. Una respuesta intermedia también contenía
JSON inválido. Ningún resultado fue aceptado como candidato. Se conservaron
programas, diagnósticos y llamadas. Se mejoraron el diagnóstico de métricas sin
evidencia y la corrección acotada de JSON; no se relajó el contrato.

En el segundo recorrido, con prompt `research-v2`, Qwen generó dos programas
válidos: comparación entre periodos y cobertura de fechas. La comprobación
independiente leyó el CSV con `csv`, `Decimal` y aritmética de fechas:

| Magnitud | Resultado comprobado |
|---|---:|
| Ventas registradas 1–14 abril | 34.137,85 |
| Ventas registradas 15–28 abril | 39.646,25 |
| Diferencia | 5.508,40 / +16,14 % |
| Fechas presentes por periodo | 12 de 14 |
| Fechas ausentes | 3, 10, 17 y 24 de abril |

El agente no imputó ceros a las fechas ausentes y advirtió que el extracto no
representa todo el negocio. No inventó margen, tickets ni causas.

Registró el primer candidato, pero intentó terminar sin registrar el segundo.
El controlador mantuvo `partial`, aunque el texto del modelo decía que todo
estaba terminado. A partir de `research-v3`, `finish` exige registrar o bloquear
las investigaciones ejecutadas. El estado visible distingue ahora una ejecución
correcta pendiente de candidato de una investigación sin empezar. Una prueba de
regresión verifica esta corrección. Una tercera prueba real, limitada a cobertura
de fechas y ejecutada con `research-v3`, terminó `completed`: Qwen registró el
candidato. Se contrastaron de nuevo ambos totales, los días presentes y las fechas
ausentes directamente contra el CSV.

Los totales y la cobertura han sido contrastados, pero no se aprueba por ello
cada detalle del programa: usa flotantes y su selección de máximos reutiliza
máscaras anteriores a una ordenación. En este CSV ordenado no cambia las cifras;
no se ha validado ese programa para entradas desordenadas. La revisión de código,
definiciones y afirmaciones sigue correspondiendo al paso 1.6.

## Cambio de definición monetaria

Con aclaración explícita de que `amount` es precio unitario, Qwen generó
`amount * quantity`: **1.220,00**, **59 unidades**. Se contrastaron ambas cifras
leyendo el CSV con `Decimal`. También generó dos CSV de desglose, por producto y
por fecha, conservados como artefactos con huellas de integridad.

Ese recorrido usó aún el controlador anterior y terminó sin registrar candidato;
quedó `partial`, no aprobado. Al reemplazar el contexto con la aclaración de que
`amount` es total de fila, el recorrido anterior pasó a `stale` inmediatamente.
La nueva ejecución con `research-v3` generó una suma simple, sin multiplicar por
cantidad: **257,50**, manteniendo **59 unidades**. Ambas cifras se contrastaron
con `csv` y `Decimal`. Registró el candidato y dos nuevos CSV de desglose. El
recorrido queda `partial` porque el plan tiene una segunda investigación y se
autorizó un presupuesto de una; la investigación monetaria sí terminó.

Esto comprueba adaptación ante una definición explícita. No demuestra que Qwen
sepa pedirla cuando falta: DR-001 permanece abierto.

## Evidencia local y límites

Los recorridos completos están en `.local/research-checks/`, fuera de Git:

- `daily-v1/`: fallo de evidencia inicial.
- `cdfd6d495d7f4004b39b37fee21f0c8d/`: comparación y cobertura de fechas.
- `0850373257fc48a4bef782e97905fddd/`: precio unitario y artefactos CSV.
- `d77174fa354f4ef29d7c1feb6f6eabd2/`: total de fila corregido, candidato y CSV nuevos.
- `f478be5ffbf54d6b97bab0743854d59f/`: cobertura final completada con candidato.

Cada carpeta contiene `trace.md`, `research.json` y programas exactos; los
contrastes independientes añaden `independent-check.json`. PostgreSQL conserva
sesiones, llamadas, checkpoints, acciones, resultados y contexto versionado.
Las rutas de artefactos privados y los identificadores de empresas no se publican
como datos de clientes en este informe.

Todos los resultados permanecen `publishable=false`; aún no hay revisor ni
informe automático. No se ha probado aquí una investigación autónoma sobre las
48 tablas de WWI ni un análisis largo con compactación. La invalidación es
conservadora, el presupuesto es pequeño y las nuevas ambigüedades durante Python
requieren replantear con el contexto completo. Estas limitaciones están descritas
en la [guía de investigación](../technical/research.md).
