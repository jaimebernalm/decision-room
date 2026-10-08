# Congelación del piloto R1

Fecha: 8 de octubre de 2026. Preparación técnica terminada; resultado del piloto
pendiente. Complementa el preregistro R1 revisión 2, sin abrir P4.

| Brazo | Revisión exacta |
| --- | --- |
| R1a | `95a310ceecde62f76ec469c25e5c4668af8028a4` |
| R1b | `28f3c0faed4f1e6a32177f56a4cd1e9611462fc2` |

Imagen común, sin reconstrucción:
`sha256:33ead825a77dfb3e19176fb4d6e42009c2f299a69addc2b9122027d633450342`.
Modelo `gpt-6-luna`, configuración heredada de P3, tier `default`.
Topes: 6.000.000 de entrada, 128.000 de salida acumulada, 16.000 por llamada,
60 llamadas y 1.200 segundos. Sin relajación ante uso desconocido.

## Encargo exacto y diferencias

`owner_context` conserva el texto plano usado por engine en P3, idéntico en ambos
brazos. No se elimina la petición de guardar `informe.html`, ni se sustituye por
el encargo del brazo loop. Los hashes UTF-8 de los encargos se conservan en el
manifiesto privado de congelación. El mensaje inicial se construye exactamente
como `informe.md + "\n\nEncargo del propietario:\n" + owner_context`.

En ambos brazos, el prompt del motor aclara que `entregar_informe` produce el HTML
publicado y que un HTML paralelo no lo sustituye. R1a añade exploración con stdout,
panorama legible y fechas con hora validada. R1b añade el paquete de evidencia por
ocurrencia del [alcance técnico](engine-r1-pilot.md): pide `{{e:key}}` en el argumento
y conserva el segmento y su soporte. Presentación, datos, modelo y topes son comunes.

Exportaciones: `draft.raw`, `draft.verified.json`, `verification.json`,
`informe.html`, `informe.contenido.html`, `presentation.map.json`, `run.json`,
`session-export.json` y `proxy-calls.jsonl`. Ledger v1 y mapa con forma R0 v3;
el evaluador usa los offsets del mapa y los estados del ledger por id.

## Validación y límites

R1a: 44 pruebas aprobadas, con OpenCode real, sandbox y proveedor simulado.
R1b: 62 aprobadas, incluido cálculo real e inserción verificada junto a una
repetición libre sin verificar; tras endurecer referencias no finitas, 28 pruebas
de ocurrencias, contrato y presentación aprobadas. Chrome real: cuerpo, marcas y
anexo del ejemplo sintético legibles. El evaluador independiente distinguió las
ocurrencias insertadas de sus repeticiones y conservó las citas ambiguas.
Sin llamadas facturables en estas comprobaciones.

Límites fijados antes de medir: ámbito íntegro largo, cláusula técnica de fechas
repetida, posible puntuación duplicada con la prosa vecina y prompt sin acortar.
Las cautelas quedan en el soporte; las reglas o fórmulas que integran el ámbito
siguen en la frase. Una cita repetida requiere contexto único del auditor; no se
resuelve la ambigüedad escogiendo la etiqueta favorable. R1b/R1a mide el paquete
de contrato e instrucciones, no un mecanismo aislado ni exactitud general.

La ejecución de 3+3 por brazo comienza tras registrar este anexo, en el orden
intercalado del preregistro. Umbrales, perdidos, pausa ante coste incierto y
presupuesto se rigen por ese preregistro. Los candidatos y resultados previos
no se modifican.

## Identidades de archivos

SHA-256 de los bytes en las revisiones congeladas:

| Archivo | R1a | R1b |
| --- | --- | --- |
| `engine/opencode/prompts/informe.md` | `349e4df01e3d0e21c000084de8a082cb42024fd7a5cb2db21d8cf31b71323eab` | `fde0953ff2d42d289a1098a423d66629092e7672677fa200d9d3726bc5af4736` |
| `decision_room/reports/presentation_r0.py` | `9e5eec544607b06cb25156a35334e4b22041201a14caeecc2c90375c97ef625b` | `9e5eec544607b06cb25156a35334e4b22041201a14caeecc2c90375c97ef625b` |
| `decision_room/reports/presentation_r1.py` | `bcf4fecee69c961ab1f1eb434e157fe7f0689f4095b6da5da39a3acfe15d0c5d` | `bcf4fecee69c961ab1f1eb434e157fe7f0689f4095b6da5da39a3acfe15d0c5d` |
| `decision_room/engine/container.py` | `00a0bf78ca24ffc4f328c64b0cdb09ad7b2138436e02299ce501a965346bd6a8` | `00a0bf78ca24ffc4f328c64b0cdb09ad7b2138436e02299ce501a965346bd6a8` |
| `decision_room/engine/admission.py` | `f7204c8d1eeb220d523b8eaeb5421dd0bd9846c5f0c7e193804c2965f68efece` | `f7204c8d1eeb220d523b8eaeb5421dd0bd9846c5f0c7e193804c2965f68efece` |
