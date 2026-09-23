# Prueba real de GPT-6 Luna por API

Fecha: 22 de septiembre de 2026. Esta prueba comprueba la integración de proveedor
y el recorrido web existente. No cierra la aceptación analítica de la entrega 1
ni inicia la entrega 3.

## Configuración y método

- Disponibilidad de `gpt-6-luna` confirmada en la documentación oficial, en
  `GET /v1/models` de la cuenta y mediante nueve llamadas reales completadas.
- Protocolo OpenAI Chat Completions, JSON Schema estricto, razonamiento `low`,
  límite de 16.384 tokens de salida, timeout de 300 segundos y `store=false`.
- Mismo CSV público de 24 filas: `data/reference-cases/01-daily-sales/input/sales.csv`.
  Mismo contexto de negocio y exploración general que el recorrido local anterior.
- Nueva sesión independiente. Una aclaración contestada con los hechos ya
  confirmados en la sesión anterior: cada fila es un total diario, no un precio
  unitario. No se aportaron referencias numéricas al agente ni se corrigieron
  manualmente su código o informe.
- Python siguió ejecutándose en el sandbox local. Los registros privados de
  llamadas, ejecuciones e informe se conservan fuera de Git.

## Tiempos observados

Suma de duración de llamadas completadas, sin espera de respuestas del propietario
ni fallos de infraestructura de la sesión local anterior:

| Fase | Qwen local anterior | GPT-6 Luna API |
|---|---:|---:|
| Planificación | 85,15 s | 36,04 s |
| Investigación | 70,73 s | 22,29 s |
| Redacción y correcciones del analista | 545,15 s | 9,96 s |
| Revisor | 306,87 s | 4,00 s |
| Total de llamadas al modelo | 1.007,90 s | 72,27 s |
| Ejecuciones Python | 0,87 s | 0,85 s |
| Llamadas al modelo completadas | 11 | 9 |

El recorrido nuevo duró 118,59 segundos de reloj, incluida la espera de una
respuesta. Hizo cuatro llamadas de planificación, tres de investigación y dos
de informe/revisión. Ejecutó Python dos veces y aprobó el primer borrador.
No hubo errores HTTP ni ejecuciones Python fallidas en esta sesión.

La suma de tiempo de modelo bajó aproximadamente 14 veces. Es una observación
de un solo caso, no un benchmark de velocidad equivalente: Qwen usaba
razonamiento desactivado y otro límite de salida, produjo gráficos y pasó por
tres borradores; Luna entregó un informe más breve sin gráfico. El tiempo de
informe depende también de contenido, contexto y correcciones, no es constante.

## Revisión independiente del resultado

Recalculado directamente desde el CSV con `csv` y `Decimal`:

- Total registrado: 73.784,10; media por fecha registrada: 3.074,3375.
- Máximo: 8.569,05 el 28 de abril; mínimo: 28,80 el 12 de abril.
- 24 registros y cuatro fechas sin registro dentro del intervalo de 28 días.
- El informe coincide con estas cifras, conserva la moneda como desconocida y
  no convierte fechas ausentes en ventas cero ni afirma causalidad.
- Los seis controles de evidencia/validez del informe pasan.

Limitación material: aunque el informe plantea una pregunta de evolución,
solo publica suma, media y extremos. No guarda una serie de métricas por fecha
para dibujarla y omite el gráfico con una explicación. El archivo sí permite
crear esa serie; falta aprovecharlo en el recorrido del agente. Se considera
un resumen numéricamente correcto, pero no una respuesta completa sobre
evolución ni la aceptación general del producto.

Computer Use confirmó el estado «Informe disponible» y el HTML integrado con
los tres hallazgos, alcance y limitaciones.

## Tokens y coste estimado

La API registró 44.652 tokens de entrada y 8.321 de salida; estos últimos
incluyen 1.654 tokens de razonamiento. De la entrada, 8.614 fueron lecturas de
caché y 36.011 escrituras de caché.

Con las tarifas estándar publicadas para contexto corto ($0,10/M entrada,
$0,01/M lectura de caché, $0,125/M escritura y $0,50/M salida), la estimación
es **$0,00875 USD** para esta sesión. Se descuentan lectura y escritura de la
entrada ordinaria para no contarlas dos veces. Es una estimación a partir de
`usage`, no una comprobación de facturación de la cuenta.

Fuentes: [modelo](https://developers.openai.com/api/docs/models/gpt-6-luna)
y [precios](https://developers.openai.com/api/docs/pricing).

## Comprobaciones de implementación

- 127 pruebas automatizadas correctas, incluidas cinco nuevas de transporte,
  aislamiento de credenciales, configuración privada y fallos previos al envío.
- Las cinco pruebas nuevas se repitieron con el identificador `gpt-6-luna`.
- La clave permanece en `.env` ignorado por Git. La plantilla solo contiene
  asignaciones vacías de credenciales; la clave OpenAI no se envía al servidor local.
- Sin reintentos automáticos de llamadas facturables inciertas. La configuración
  se fija por sesión; cambiar el proveedor afecta a nuevos análisis.

Siguiente comprobación: repetir los casos y variantes de 1.7 con Luna, incluyendo
calidad y utilidad del informe, antes de atribuirle fiabilidad general.
