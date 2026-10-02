# Diagnóstico y tratamiento de HTTP 429

Incremento de fiabilidad del [plan 3.9](../technical/report-quality-plan.md),
posterior a los [pilotos del 2 de octubre](2026-10-02-report-quality.md).
Las fuentes, informes, snapshots y resultados anteriores permanecen congelados.
No cierra 3.9.7 ni demuestra una mejora de utilidad.

## Evidencia actual e histórica

El propietario comunica 200.000 TPM y 500 RPM para GPT-6 Luna. Una única petición
mínima al endpoint oficial configurado, sin datos de negocio ni reintentos, responde
HTTP 200 el 2 de octubre a las 16:31 UTC. Sus cabeceras confirman esos límites:
499 peticiones y 199.995 tokens disponibles en esa respuesta. Uso informado:
9 tokens de entrada y 4 de salida. No se induce un 429 ni se repite un informe
completo como prueba de transporte. El identificador de solicitud permanece local.

Auditoría sobre `resources.json` de tres recorridos originales con `646b35c`:

| Recorrido | Máximo de entrada en una llamada conocida | Mayor suma conocida asignada a inicios en 60 s | Rechazos 429 |
| --- | ---: | ---: | ---: |
| Bruma descubrir | 125.114 | 330.065 | 4 |
| WWI descubrir | 157.864 | 343.536 | 19 |
| WWI organizar, original | 38.303 | 223.136 | 7 |
| Combinación de esos tres recorridos | 157.864 | 405.697 | 30 |

Método: asignar `prompt_tokens` conocidos a `created_at` de cada llamada lógica;
sumar ventanas móviles de 60 segundos, excluyendo su frontera izquierda. No se
duplican llamadas entre planificación y revisión ni se añade la recuperación de
organización al original. Se incluyen 116 llamadas con entrada conocida; otra
llamada fallida de organización carece de ella.

**Estas sumas no son el contador TPM de OpenAI.** No incluyen la hora exacta de
cada reintento, consumo de rechazos, reservas del proveedor ni tráfico ajeno a
estos recorridos. Los rechazos históricos no guardaban cuerpo ni cabeceras de
límite; solo estado y espera. La presión de tokens, reforzada por recorridos
concurrentes y contextos crecientes, es una hipótesis plausible, no una causa
confirmada de cada rechazo. El saldo agotado de la evaluación del 30 de septiembre
ya tenía otro diagnóstico y no se reclasifica.

La documentación distingue RPM y TPM, límites por organización/proyecto y modelo,
y cuotas de cuenta. Tier 1 requiere **5 dólares pagados**, no cinco consumidos;
un consumo declarado de 4,14 dólares es compatible con estar en Tier 1. La cifra
de la columna **Batch queue limits** corresponde a tokens de entrada pendientes
en Batch; no establece por sí sola el límite diario de estas llamadas síncronas.
Véase [límites de OpenAI](https://developers.openai.com/api/docs/guides/rate-limits).
No se consulta ni modifica la facturación de la cuenta.

## Cambio aplicado

- Nuevo extractor de diagnóstico con cuerpo de error limitado a 16 KiB. Conserva
  códigos/tipos conocidos, identificador de solicitud restringido y cabeceras
  numéricas permitidas; no guarda mensajes, parámetros, cookies, autorización ni
  texto arbitrario. Un cuerpo ausente, demasiado grande o interrumpido no convierte
  un rechazo HTTP conocido en una petición de resultado incierto.
- Categorías separadas para límite temporal, ralentización, sobrecarga y cuota o
  crédito de cuenta. Las últimas no se reintentan; códigos desconocidos se
  registran como tales. [Códigos del proveedor](https://developers.openai.com/api/docs/guides/error-codes).
- Espera mínima indicada por `Retry-After`, incluido formato fecha. Si quedan cero
  peticiones o tokens, se respeta también su reset disponible. Se añade hasta un
  segundo aleatorio en OpenAI sin reducir la espera. Tres intentos como máximo y
  el plazo total existente siguen vigentes. Una espera superior a 30 segundos se
  conserva como fallo para recuperación explícita; también un 503 deja de acortar
  esa indicación a cinco segundos. No se implementa una cola de recuperación nueva.
- Los intentos y sus metadatos se guardan antes de dormir en la persistencia
  existente. El monitor interno puede inspeccionarlos bajo `usage`. Cabeceras de
  una llamada correcta no vuelven incompleto su consumo; un rechazo sigue con
  consumo desconocido. No se calcula un coste completo donde falta uso.

## Comprobaciones

- **14 pruebas de transporte**: recuperación de 429/503; fechas y plazos; cuota y
  saldo sin retry; límites agotados; éxito con uso completo; exclusión de secretos;
  cuerpos no JSON, grandes o interrumpidos; jitter sin anticiparse al servidor.
- Caso de PostgreSQL: interrupción durante la espera conserva código, tipo,
  límites y reset, excluye mensaje libre y reanuda sin repetir cálculos previos.
- **Regresión completa: 555 pruebas Python, 319,256 segundos, correctas**, con
  PostgreSQL y almacenamiento independientes. Las pruebas simulan el transporte;
  no generan llamadas pagadas. No hay cambios de interfaz en este incremento.
- Petición mínima real: HTTP 200 y 13 tokens informados, sin garantía de que una
  investigación grande evite el límite. No se provoca una ráfaga para forzar error.
- Script del experimento manual: sintaxis zsh correcta; opciones contrastadas con
  la CLI instalada. Los cuatro CSV copiados conservan sus SHA-256. No se lanza el
  experimento como parte de esta validación ni se añaden sus datos o eventos
  privados a Git. Al finalizar la preparación se detecta una ejecución manual
  terminada en esa carpeta; sus salidas se conservan, sin evaluar todavía su
  informe ni atribuirle los controles añadidos al script después de esa ejecución.

## Experimento manual y trabajo pendiente

**Luna directo · Bruma Café** entrega las cuatro fuentes del piloto y un texto
breve con negocio, significado de unidades, información desconocida y objetivo.
No incluye instrucciones del planificador, analista o revisor, resultados previos
ni oráculo. Se prepara fuera del repositorio, con Luna y razonamiento `low`,
configuración de usuario ignorada, sesión efímera, búsqueda web y subagentes
desactivados. Las herramientas e instrucciones base de Codex siguen presentes:
compara Decision Room con Codex, sin aislar exclusivamente el modelo.

`codex exec --json` guarda eventos de comandos, archivos, mensajes y herramientas,
además del uso agregado que informa la CLI; `--output-last-message` guarda su
última respuesta. Si genera un informe en otro archivo, también se conserva.
No se atribuye coste individual a cada herramienta ni se identifica este registro
con todas las llamadas internas del proveedor.
[Modo no interactivo](https://learn.chatgpt.com/docs/non-interactive-mode).

Queda pendiente una política compartida de presupuesto de tokens para que varios
procesos no sumen ráfagas superiores al límite, y reducir contexto repetido sin
perder evidencia. Limitar solo el número de peticiones concurrentes no controla
el TPM de una sucesión de llamadas grandes. Esa prevención y la comparación manual
tienen validación propia; no se dan por ejecutadas con este diagnóstico.
