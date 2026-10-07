# Propuesta de interfaz de exportación del motor, versión 1

Propuesta de Astra del 7 de octubre de 2026 para desbloquear implementación y
medición. La respuesta A–E no llegó a Claude: el puente la rechazó por un cambio
del checkout principal. No se presenta como acuerdo recibido ni como API completa.
El validador puro `reports.verification_contract` fija y prueba esta propuesta;
no verifica cifras ni aprueba informes. El controlador, verificador documental,
proyección y exportación completos siguen pendientes.

## Identidad y correspondencia

`verification.json` contiene:

- `contract_version: 1`;
- `draft_sha256`: SHA-256 de los bytes exactos de `draft.raw`, incluso si son JSON inválido;
- `verified_sha256`: SHA-256 de la representación JSON canónica de `draft.verified.json`;
- `renderer_version`: versión explícita del renderizador;
- `figures`, `summary` e `issues`.

Cada figura contiene `id`, `path`, `span`, `text`, `value`, `unit`, `status`,
`verified`, `corrected_from`, `evidence` y `recommendation_id`.

`path` es un JSON Pointer RFC 6901 en el documento verificado. Apunta a un campo
string con el texto que se muestra. `span: {start, end}` usa índices de puntos de
código Unicode, inicio incluido y final excluido. `text` coincide exactamente con
esa parte del campo, antes de escapar HTML. `id` deriva de versión, hash del
verificado, path y span. Dos cifras iguales en un párrafo tienen spans distintos.
Un mismo contenido mostrado dos veces puede compartir referencia; el auditor
registra afirmaciones según su protocolo, no deduce independencia por repetición.

`value` y `corrected_from` son decimales representados como strings o null. `unit`
es string o null. La evidencia usa objetos `{kind: execution|observation, id,
metric?}`; un ID no demuestra por sí mismo verificación semántica.
`recommendation_id` es orientativo: no sustituye la clasificación independiente
`sostiene_prioridad_v3` del auditor.

## Corrección no equivale a verificación

`status` es `verified`, `unverified`, `uncertain` o `corrected`. `verified` es además
un booleano obligatorio. Un estado `verified` exige true; `unverified` y
`uncertain` exigen false. `corrected` puede tener cualquiera de los dos: corregir
un valor no certifica atribución, unidad o denominador en la prosa. Guarda siempre
antes y después. No se promueve automáticamente `verified_in_scope` de una
herramienta a verificación del uso de esa cifra en el informe.

`summary` cuenta exactamente los cuatro estados, sin solaparlos. La puerta de
exactitud usa cada figura y exige `verified=true` más el resultado correcto del
auditor; no se calcula a partir de estos contadores. Una cifra sin correspondencia
única cuenta como no verificada. No se elige arbitrariamente entre duplicados por
coincidir el valor. La validación estructural nunca precede a guardar el borrador
raw ni autoriza descartarlo si falla.

## Proyección y dos medidas

Firmas propuestas en `decision_room.web.report_projection`:

- `project(draft_verified: dict) -> dict`, pura;
- `render(projection: dict, *, marks=True) -> str`, HTML autocontenido sin red.

`export_run` usa `marks=True`. `marks=False` solo quita decoración y etiquetas
automáticas de verificación. Conserva cifras corregidas, texto y limitaciones
analíticas; no genera otra interpretación del informe. La medida de contenido
normaliza los tres brazos por igual. La medida de artefacto conserva las marcas y
reconoce que pueden revelar el brazo. El contrato de proyección debe reutilizarse
en P4; estas firmas no significan que la implementación ya exista.

## Auditor y coste

Conviene un auditor nuevo elegido por el propietario, con snapshots, informes e
instrucciones congeladas, sin código, claves de los brazos ni oráculos. Astra
implementa el motor y ya conoce la auditoría previa; Claude conoce las claves.
Este documento no crea otra conversación ni autoriza ensayos.

El proxy todavía no implementa `cost_catalog`: conserva uso y reservas, pero
faltan escritura de caché y tier efectivo. Según la [tarifa oficial consultada el
7 de octubre de 2026](https://developers.openai.com/api/docs/pricing), GPT-6 Luna
Standard cuesta, en USD por millón de tokens: entrada 0,10; lectura de caché 0,01;
escritura de caché 0,125; salida 0,50. Para solicitudes de más de 272.000 tokens de
entrada: 0,20 / 0,02 / 0,25 / 0,75 respectivamente. Fast aplica ×2 y el procesamiento
regional añade 10 % donde corresponde. Véase también la [ficha del modelo](https://developers.openai.com/api/docs/models/gpt-6-luna).

La estimación debe distinguir esos componentes por llamada y registrar fuente,
fecha, contexto y tier. Con componentes ausentes se comunica un intervalo con
supuestos, nunca coste cero ni exactitud ficticia. Antes de presupuestar en USD,
el tier debe fijarse en configuración confiable: el proxy actual todavía admite
`service_tier` procedente del cliente. No se ha ejecutado ninguna llamada facturable.
