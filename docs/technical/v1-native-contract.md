# N0: contrato de informes nativos

Estado: contrato inicial de implementación del plan `v1-native-report-plan.md`, autorizado por el dueño. Legacy conserva el valor por defecto. La variante nueva se selecciona explícitamente con `engine_kind=opencode, engine_format=blocks` y queda congelada por trabajo. Los perfiles HTML históricos no cambian.

## Datos y límites (blocks-v1-1)

Documento UTF-8 JSON estricto: `{schema_version: "blocks-v1-1", title: texto, blocks: [...]}`. No claves desconocidas ni duplicadas; no NaN/Infinity, booleanos como números o valores fuera de ±10^15; números con un máximo de 15 cifras significativas. Los valores nulos de gráficos son huecos, nunca ceros. Los porcentajes usan puntos porcentuales cuando `unit="%"`; no se infiere una multiplicación por cien.

Cada bloque lleva `id` único en la revisión (1–80 caracteres ASCII alfanuméricos, guion o guion bajo) y `type`. Tipos:

- `seccion`, `prioridad`: `title`, `blocks` libres; sin campos analíticos adicionales.
- `texto`: `content`, lista de nodos. Nodos de texto `{type:"text", text}`, o `{type:"paragraph"|"bold"|"italic"|"list"|"item", children:[...]}`. Sin marcado, enlaces ni atributos ejecutables. El texto literal, incluso signos `<` y `>`, siempre se escapa.
- `cifra`: `label`, `value`; opcionales `unit`, `period`, `comparison:{previous,difference}`.
- `grafico`: `kind`, `title`, `data:[{category,series,value,denominator?}]`; opcionales `unit`, `x_label`, `y_label`, `note`. Tipos conocidos `bar`, `line`, `columns`, `change`; un tipo distinto conserva todos los datos como tabla. Máximo seis series. Categorías temporales ISO, sin conversión implícita de categorías de texto a fechas.
- `tabla`: `columns:[{key,label,unit?}]`, `rows:[{key: texto|numero|null}]`; opcionales `title`, `note`. Claves y celdas coherentes con columnas.
- `aviso`: `text`.

Límites iniciales globales: 256 KiB de bytes brutos, profundidad 12, 2.048 nodos (bloques y texto), 120.000 caracteres de texto, 20.000 celdas y 10.000 puntos. Texto individual hasta 20.000 caracteres, título/etiqueta hasta 500, seis series por gráfico. No se recorta silenciosamente; exceso o JSON inválido conserva el recibo, registra el error y no publica.

## Interfaz y versiones

El perfil congela `/work/informe.json`, `schema_version`, `format=blocks` y el encargo. La CLI `comprobar_informe` y el validador del producto comparten exactamente la misma implementación. La CLI es ayuda, no autoridad. Recepción durable e idempotente por clave y bytes antes del parseo.

`reports.blocks.validate(raw)` produce un documento validado o `InvalidReport`; `project(raw)` produce datos nativos, texto canónico y hashes. Proyector `blocks-projector-1`, política `blocks-escaped-1`, versión de derivado 1. N1 es dueño de estos módulos y del registro/migración; N2 consume la interfaz, sin fabricar Claim/MetricRef ni approvals de legacy. `reading.view` ofrece `mode=native`, `document` y `canonical_text`, o bloqueo neutro; nunca ejecuta un navegador.

Fuente `engine_blocks`, revisiones brutas existentes conservadas. Derivados inmutables por negocio/documento/revisión/hash bruto/esquema/proyector/política. La vigencia sigue F1. Datos validados, comprobación terminada y ejecución entregada son estados diferentes. N1/N2 no hacen vigente un informe nativo sin la comprobación de N3.

## Ciclo de N3 y decisiones de producto

Autor → borrador durable → comprobador aislado → como máximo una corrección en la sesión escritora → comprobación final → revisión elegida. La cobertura y los resultados se ligan a la revisión exacta. Se conserva todo recibo, sin reutilizar resultados sobre bytes nuevos.

Autor/comprobador/corrección comparten el techo P4 y límites acumulados. No hay saldo adicional ni modificación de la parada por incertidumbre. Sin cuota, error de comprobador, expiración o contexto revocado: conservar borrador, marcar comprobación incompleta y no promoverlo a informe actual. Una discrepancia tras corrección se presenta con aviso explícito, sin ocultarla ni indicar «Revisado». Los casos no comprobables quedan visibles como tales.

Inicio mantiene acceso y estado (sin nuevas tarjetas automáticas). Los ensayos N3–N5 requieren presupuesto y preregistro propios; ni la conversión manual de F5 ni los proveedores simulados acreditan calidad general. No se cambia el motor por defecto por aprobar pruebas de código.

## Comprobación de salida

N1: validación hostil y límites, recepción/repetición, migración dos veces, históricos intactos, export JSON, ningún renderizador. N2: gráficos y tabla fieles, selección por block_id, chat sin evidencia inventada, PDF escapado, extremos y regresión legacy. N3: recuperación y concurrencia, una corrección, comprobación final y techo compartido; validación retenida aparte. N4 mide lectura, señales, exactitud y pérdidas de la variante completa; N5 compara con legacy.
