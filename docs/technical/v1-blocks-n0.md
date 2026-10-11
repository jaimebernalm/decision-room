# N0: formato de bloques e interfaz entre fases

Fase N0 del [plan del informe v1 nativo](v1-native-report-plan.md). Fija el formato que entrega
v1, la proyección que consume la plataforma y quién toca cada archivo en N1–N3.

## Decisiones del dueño (11 de octubre de 2026)

El dueño autorizó implementar el plan completo, N0–N5, fase a fase y con Astra, y dio permiso
para todos los cambios necesarios.
- **D1. Cifra discutida.** Si se sabe que una cifra está mal, se corrige; si no se puede
  resolver, va con un aviso. En el producto:
  - el comprobador da su cálculo;
  - v1 lo revisa en su vuelta de corrección y cambia la cifra si se equivocó;
  - si después la discrepancia sigue, la cifra lleva un aviso visible;
  - ocultarla no es una opción.
- **D2. Tarjetas del inicio.** Claude decide por delegación del dueño: sí, a partir de los
  bloques `cifra` de la revisión vigente de `blocks-v1`, sin ninguna marca de verificado.
- **D3. N5.** Legacy usa 16.384 tokens de salida.
- **D4. Autorización.** Todas las fases quedan autorizadas. El gasto de API de N3–N5 tiene un tope
  conjunto de 15 USD de catálogo con el ledger durable. Cada preregistro fija su parte.
- **Sin cambios:** la regla de parada del ledger, legacy por defecto, la marca «Revisado», el
  envío a GitHub y la fusión con master.

## Formato

- La especificación ejecutable está en `decision_room/engine/blocks.py` (`VERSION =
  informe-bloques-1`). La guía para el agente está en `FORMAT_GUIDE`, que también muestra
  `comprobar_informe --formato`.
- El módulo solo usa la biblioteca estándar. El mismo fichero se monta de solo lectura en el
  contenedor como `/inputs/herramientas/comprobar_informe.py`, así que no hace falta reconstruir
  la imagen.
- **JSON estricto:**
  - UTF-8 sin BOM;
  - sin claves duplicadas ni NaN o Infinity;
  - números exactos con `Decimal`, menores que 10^15;
  - sin caracteres de control salvo salto de línea y tabulador;
  - ningún campo admite HTML, CSS, URL ni código; todo es texto plano que se escapa al
    presentarlo.
- **Límites globales:**
  - 256 KiB y 300 bloques;
  - 4 niveles de anidación;
  - 150.000 caracteres;
  - 4.000 valores de gráfico y 6.000 celdas;
  - por gráfico, 60 categorías y 8 series;
  - por tabla, 12 columnas y 200 filas.
- **Libertad del agente:**
  - una `prioridad` es un título más los bloques que quiera, sin campos analíticos obligatorios;
  - tampoco hay apartados obligatorios ni número fijo de prioridades.
- **Identificadores:** salen de la posición (`b3-1-2`). Son únicos y estables dentro de cada
  revisión y el agente no los escribe.
- **Cifras calculadas por la plataforma:** si una `cifra` trae `anterior`, la diferencia y el
  porcentaje los calcula la plataforma. Así desaparece esa fuente de errores aritméticos y no hace
  falta un diagnóstico aritmético aparte.
- **Gráficos:** un tipo de gráfico desconocido no es un error. Se proyecta con
  `kind = "table"`, `fallback = true` y el tipo pedido en `requested_kind`.
- **Huecos:** `null` es un hueco, no un cero.

## Proyección (contrato N1 → N2)

`blocks.parse(raw)` devuelve un JSON sin marcado:

```json
{"schema": "informe-bloques-1", "projector": "bloques-proyector-1", "title": "...",
 "blocks": [
  {"id":"b1","type":"text","content":[{"kind":"paragraph","spans":[{"text":"...","bold":false,"italic":false}]},
                                      {"kind":"list","ordered":true,"items":[[{"text":"...","bold":false,"italic":false}]]}]},
  {"id":"b2","type":"figure","label":"...","value":1.5,"unit":"€","decimals":2,"period":"...",
   "previous":{"value":1,"period":"..."},"change":0.5,"change_pct":50.0,"note":null},
  {"id":"b3","type":"chart","kind":"bar|column|line|change|table","requested_kind":"barras","fallback":false,
   "title":"...","categories":["..."],"series":[{"name":"...","values":[1,null],"details":["...",null]}],
   "unit":"%","decimals":1,"category_title":null,"value_title":null,"note":null},
  {"id":"b4","type":"table","title":null,"columns":[{"title":"...","unit":null,"decimals":0}],"rows":[["x",1,null]],"note":null},
  {"id":"b5","type":"section|priority","title":"...","blocks":[...]},
  {"id":"b6","type":"notice","content":[...]}
 ]}
```

**Funciones del módulo:**
- `canonical_text(projection)` da el texto para el chat y la búsqueda, con números en formato
  español.
- `block_lines(block)` da el texto de un bloque, que se usa para seleccionarlo en el chat.
- `priorities(projection)` devuelve las prioridades con su `block_id` y su texto, que es lo que
  recibe el comprobador de N3.

**Vista** (`reading.view` para una revisión `engine_blocks`):

```json
{"mode": "blocks", "blocks": <proyección>, "canonical_text": "...",
 "checks": {"state": "not_run|pending|done|failed|unavailable",
            "items": [{"block_id":"b4","quote":"636 unidades","status":"discrepancy|unverifiable",
                       "independent_value":"342","method":"...","message":"..."}]}}
```

**Qué muestra la interfaz:**
- un aviso junto a cada bloque con `discrepancy` que siga tras la corrección;
- un resumen de las cifras que no se pudieron comprobar;
- nunca nada para las cifras confirmadas (P5).

`metadata.origin` es `engine_blocks`.

## Dueños de archivos

| Fase | Responsable | Archivos |
|---|---|---|
| N0 | Claude | `decision_room/engine/blocks.py`, `tests/test_engine_blocks.py`, este documento |
| N1 | Astra | `engine/file_delivery.py`, `engine/store.py`, `engine/api.py`, `engine/profile.py`, `engine/container.py` (montaje de la herramienta), `engine/brief.py` y `engine/opencode/prompts/` (encargo de `blocks-v1`), `schema.sql` y la migración, `reports/store.py`, `reports/reading.py`, `reports/derive*.py`, `engine/export.py`, `web/report_access.py` y `web/service.py` (despacho por formato) |
| N2 | Claude | `frontend/src/components/workspace/` (vista de bloques, gráficos nuevos, selección), `decision_room/reports/blocks_pdf.py`, guardas de `decision_room/conversations.py` para `engine_blocks`, `decision_room/web/home.py` (D2), fixtures de UI |
| N3 | Astra | comprobador aislado, ciclo durable borrador → comprobación → corrección → comprobación final y su registro; `checks` en la vista |
| N4–N5 | Claude, con revisión de Astra | preregistros, ejecución y evaluación |

**Reglas de coordinación:**
- Si alguien necesita tocar un archivo de otro, lo pide por el bridge.
- `blocks.py` cambia solo con versión nueva. Su `VERSION` se guarda con cada revisión.
