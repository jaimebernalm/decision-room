# Contrato de interfaz de exportación del motor, versión 1

Interfaz propuesta por Astra y aceptada por Claude el 7 de octubre de 2026 para
coordinar implementación y medición. Claude declaró la adaptación de su
calculadora en `8394755`; esa declaración no sustituye una revisión de su código.
El validador puro `reports.verification_contract` fija y prueba el contrato;
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

Firmas acordadas, pendientes de implementar, en `decision_room.web.report_projection`:

- `project(draft_verified: dict) -> dict`, pura;
- `render(projection: dict, *, marks=True) -> str`, HTML autocontenido sin red.

`export_run` escribirá `informe.html` con `marks=True` e
`informe.contenido.html` con `marks=False`, ambos desde la misma proyección y
con la misma `renderer_version`. `marks=False` solo quita decoración y etiquetas
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
supuestos, nunca coste cero ni exactitud ficticia. El proxy fija ahora
`service_tier="default"` (Standard) como política del servicio. Rechaza otros
valores antes del conteo y la generación; omitir el campo no hereda el tier del
proyecto. El [parámetro del proveedor](https://developers.openai.com/api/docs/guides/fast-mode)
distingue tier solicitado y efectivo; la captura de este último para el catálogo
sigue pendiente. No se ha ejecutado ninguna llamada facturable.

Con los topes de 3 M de entrada y 64 k de salida, 0,332 USD es el escenario de
contexto corto sin lecturas ni escrituras de caché, no el peor caso. A tarifa larga,
el escenario sin caché es 0,648 USD; si toda la entrada se cobra como escritura
larga, es 0,798 USD por trabajo (4,788 para seis; 9,576 para doce). Son escenarios
bajo esos supuestos de tarifas, no costes medidos ni límites absolutos de factura.
Los controles que no imponen topes tampoco tienen un máximo demostrado por su
consumo histórico. La autorización de ensayos debe usar un presupuesto explícito
con esas limitaciones.
