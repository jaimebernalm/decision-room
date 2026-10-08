# Experimento local R0: presentación de informes congelados

R0 es una variante de presentación posterior a la evaluación de P3. No modifica
el motor congelado, su verificador, el exportador del producto ni los resultados
medidos. Su código vive en `decision_room/reports/presentation_r0.py` y solo se
invoca de forma explícita para el piloto. Su resultado no autoriza P4.

## Entradas y salida

Por informe se leen `draft.raw`, `draft.verified.json`, `verification.json` e
`informe.html` originales. Antes de renderizar, se valida el contrato de
verificación y la identidad del bruto/documento. Un directorio nuevo recibe:

- `<id>.html`: lectura principal, gráficos asociados y anexo visible completo;
- `<id>.map.json`: texto original, transformaciones permitidas, destinos HTML y
  desplazamientos Unicode de cada ocurrencia; conserva las figuras originales;
- `<id>.checks.json`: atestación con `id`, `invariants_passed` y comprobaciones;
- `manifest.json`: SHA256 de todos los archivos de entrada y salida.

Ejemplo con rutas locales elegidas por quien ejecuta:

```sh
python -m decision_room.reports.presentation_r0 sources.json output-new
```

`sources.json` es un mapa de identificadores a directorios de exportación. Ese
archivo y todos los materiales del piloto deben permanecer privados, fuera de Git.
El comando rechaza sobrescribir un directorio existente y valida todos los
informes antes de empezar a escribir las salidas.

## Cambios de presentación

La lectura principal conserva las afirmaciones y el orden de los hallazgos.
Muestra sus comprobaciones siguientes en un bloque distinto y primeras frases de
soporte junto a la lectura. El estado de cada ocurrencia aparece en el texto donde se publica. El anexo
conserva una sola copia completa de cada soporte, con ámbito y cautelas; las
referencias desde el cuerpo se limitan a esos soportes. No repite los campos de
prosa ni las etiquetas de los gráficos. No hay
contenido oculto en desplegables para las capturas.

Los gráficos existentes se sitúan junto al hallazgo que nombran explícitamente;
los que no tienen asociación van después de los hallazgos. Conservan la geometría
del renderer congelado y sus tablas. No se añade una serie ni se dibujan valores
sin resolver.

Solo se transforman textos mediante reglas explícitas:

1. Decimales con valor y unidad conocidos: formato español, sin cambiar precisión
   ni cantidad. Los números libres, fechas y códigos ambiguos se dejan intactos.
2. Referencias sin valor que el ledger identifica como token: «No disponible»;
   conservan su estado y la referencia original en el mapa. Esto no recupera ni
   certifica la cantidad ausente.
3. Etiquetas completas de gráfico `CODE — nombre`: `nombre (CODE)`, solo cuando
   todas sus ocurrencias se pueden remapear sin partirlas. No se buscan ni inventan
   correspondencias de catálogo. El texto de nombres y códigos se conserva.

No se abrevia un periodo inferido de prosa libre. Las marcas discretas diferencian verificada,
no verificada, incierta y corregida; en esta última también explicita si el ámbito
está verificado. Las marcas no convierten la interpretación en una afirmación
certificada. La variante conserva el ledger original y emite un mapa propio: no
pretende que los desplazamientos de la versión congelada describan el nuevo HTML.

## Comprobaciones y límites

Las pruebas cubren identidades y hashes, inmutabilidad de entradas, fechas/códigos
sin reinterpretación, referencias ausentes, nombres con cifras y desplazamientos,
figuras repetidas, correcciones sin aprobación semántica, texto escapado, enlaces,
orden visible de hallazgos, tablas sin valores y rechazo de alteraciones de texto,
estado y mapa. Cada exportación repite las invariantes sobre su HTML final.

La atestación automática no sustituye la revisión visual en navegador. Antes de
los lectores deben revisarse capturas completas con anexo visible, dimensiones
idénticas y sin desbordamientos. El kit debe usar exactamente los HTML atestados y
registrar sus hashes. R0 puede facilitar la lectura; no corrige errores analíticos,
no añade hallazgos y no demuestra mayor cobertura de verificación.

## Preparación técnica del piloto

La variante quedó preparada con 29 pruebas aprobadas (presentación R0, proyección,
gráficos y contrato de verificación). Los doce HTML privados pasan las invariantes,
incluida la posición real de las marcas en el DOM; cada fuente conserva su hash.
Se revisaron las capturas de composición en Chrome a 1280 px: la revisión conjunta
cubre los doce informes, con inspección directa de muestras de cuerpo, tablas,
referencias ausentes y final de anexo. El anexo conserva los soportes completos sin
reimprimir la prosa. Los materiales generados y las capturas permanecen fuera de Git.

Esta preparación permite construir el kit. La medida posterior se resume a continuación.

## Resultado exploratorio

La puntuación entregada por el evaluador para las doce parejas registra preferencia
por R0 de ambos lectores en las doce (seis por negocio); supera el umbral fijado de
siete. Ninguna respuesta señaló información ausente. Este resultado apoya una
mejora de presentación frente al renderer original con contenido congelado.
No compara con el agente en bucle ni demuestra mejora analítica o equivalencia
con dueños reales. Un lector informó de imágenes ocultadas después de verlas;
la coincidencia del otro no elimina esa limitación.

Con esta medida, R0 queda cerrado en su alcance exploratorio. R1, autorizado
secuencialmente, mantendrá esta presentación en ambos brazos; P4 sigue cerrado.
