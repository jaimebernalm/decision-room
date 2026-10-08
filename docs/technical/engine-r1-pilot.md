# Piloto R1: cambios posteriores a P3

R0 cerró su comparación exploratoria de presentación. R1 sigue autorizado en
secuencia y conserva la presentación común de R0. No modifica el candidato ni
los artefactos medidos en P3, y no abre P4. R1a reúne exploración observable,
panorama legible, entrega sin duplicación y fechas; R1b añadirá evidencia por
ocurrencia. Las revisiones finales se fijarán antes de nuevas ejecuciones.

## Primera pieza: fechas calculables

Las recetas aceptan fechas ISO y timestamps ISO sin zona, con separador espacio
o T, segundos obligatorios y fracción opcional de una a seis cifras. Se valida
el timestamp completo antes de extraer el día civil; los extremos del filtro
siguen siendo fechas ISO inclusivas. La hora no convierte una fila del último
día en una fila fuera del intervalo. El ámbito visible declara esta semántica.

Fechas inválidas, horas imposibles, sufijos arbitrarios y timestamps con zona
permanecen sin certificar. No se deduce la zona del negocio ni se trunca un
prefijo para aceptar datos malformados. La identidad de receta cambia a v2:
las observaciones antiguas no se reinterpretan con el código nuevo.

Validación: 14 pruebas de agregados e integración aprobadas con datos sintéticos,
incluidos año bisiesto, límites de día, Parquet TIMESTAMP frente a VARCHAR,
rechazo de fechas/horas/sufijos inválidos, idempotencia, aislamiento y verificación.
El primer intento de integración no cargó el entorno local de pruebas y falló
al abrir el socket predeterminado; la repetición con ese entorno pasó. Sin
llamadas de modelo. R1a todavía no está listo para congelar ni medir.

## Segunda pieza: exploración y entrega

`explorar` usa el mismo sandbox y las tablas autorizadas que `consulta`, pero
permite terminar sin `result.json` y devuelve stdout paginado. La opción de
ejecución se registra en la identidad de la solicitud; reutilizar una clave con
otro modo se rechaza. La consulta habitual sigue exigiendo resultado estructurado.
Completar un programa no certifica lo impreso. `salida` permite releer únicamente
las ejecuciones del trabajo y distingue paginación de truncamiento de retención.

`panorama_lectura` reúne los bloques de tabla, periodo y señales de la proyección
compacta existente, con sus valores y un índice de referencias. No selecciona
señales mediante un modelo; los detalles y ratios completos siguen en `panorama`.
Sus cursores son posiciones de caracteres, y las respuestas incluyen la siguiente
llamada exacta. Los límites, nulos y códigos sin catálogo conservan su significado.

El encargo del propietario permanece intacto. Las instrucciones del motor aclaran
que `entregar_informe` produce el HTML publicado; escribir otro HTML en el entorno
de trabajo no lo sustituye. Se mantienen los borradores recuperables.

Validación: 29 pruebas de exploración, feedback, panorama y ejecución aprobadas,
con sandbox Docker real: tabla impresa, repetición idempotente, rechazo entre
trabajos, modo incompatible bajo la misma clave, paginación Unicode y regresión
del contrato de consulta. Sin llamadas de modelo.

## R1a: exportación y revisión de partida

La exportación usa la composición R0 congelada y escribe `presentation.map.json`
con sus textos visibles y desplazamientos. La copia `informe.contenido.html`
conserva exactamente esos textos, pero retira las marcas y la leyenda de estados;
`informe.html` las conserva. El registro de verificación sigue siendo v1. No se
modifican los artefactos de R0 ni P3. El manifiesto de entradas se presenta como
JSON indentado para que la lectura por líneas no corte todo su contenido a la vez.

Esta revisión completa R1a para el piloto; no acredita su resultado analítico.
R1b partirá de ella y usará la misma composición. Ambos conservan el encargo
plano de P3, sin quitar ni sustituir texto del propietario: la aclaración sobre
la entrega está en las instrucciones del motor. Imagen común, sin reconstrucción:
`sha256:33ead825a77dfb3e19176fb4d6e42009c2f299a69addc2b9122027d633450342`.
Topes comunes: 6 millones de entrada, 128.000 de salida acumulada, 16.000 por
petición, 60 llamadas y 1.200 segundos; tier `default`.

Validación: 44 pruebas de API, presentación, recetas y exploración aprobadas,
incluidas las pruebas con OpenCode real, sandbox Docker y proveedor simulado.
Se comprobó el mapa de presentación y la igualdad de texto entre copias con y
sin marcas. Sin llamadas facturables. Las dos revisiones finales y sus hashes
se comunicarán juntas antes del orden intercalado de ejecución preregistrado.

## R1b: evidencia en la ocurrencia

`{{e:key}}` en un campo de prosa existente inserta la etiqueta de cálculo, el
valor, la unidad y el ámbito íntegro generados por la receta. El verificador
reutiliza exclusivamente las marcas del fact recalculado; no aprueba la población
que el agente escriba alrededor ni una repetición libre de la cantidad. Las fechas
y otros números del ámbito conservan su estado previo: insertar el segmento no
certifica todas sus palabras ni sus cifras por proximidad.

El soporte completo, con cautelas y operandos, permanece en facts del mismo
hallazgo (o generales para un campo general); se añade una sola vez por clave en
cada ubicación. La presentación R0 conserva sus enlaces y anexo. No se abrevia
el ámbito para reducir longitud. Los límites de 32 claves por ubicación, 256 facts,
256 segmentos y un millón de caracteres de expansión evitan crecimiento sin cota;
el exceso deja un aviso legible y un issue sin conceder marcas.

Los campos visibles y la forma del ledger v1 no cambian. `presentation.map.json`
sigue dando los desplazamientos del texto publicado, tras el formato español.
Los hashes de documento y figuras se reconstruyen; `draft_sha256` sigue correspondiendo
al bruto original, conservado byte por byte. Los tokens que aparezcan en nombres
procedentes del dato no se interpretan recursivamente. Las claves ambiguas o las
referencias sin receta compatible no adquieren certificación.

Validación: 62 pruebas aprobadas de ocurrencias, facts, API, presentación, recetas
y exploración. El humo con OpenCode real y proveedor simulado lee entradas,
calcula con la herramienta real y entrega una cifra insertada verificada junto a
una repetición libre sin verificar. Tras endurecer referencias no finitas, 28
pruebas de ocurrencias, contrato y presentación volvieron a pasar. La QA de una
página sintética en Chrome confirmó cuerpo, marcas, soporte y anexo legibles.
La unión independiente del evaluador también distinguió los segmentos verificados
de sus repeticiones libres y conservó la ambigüedad de citas repetidas.

Límites fijados antes de medir: el ámbito íntegro puede ser largo, incluye la
semántica técnica de fechas y puede duplicar puntuación con la frase vecina.
Las cautelas quedan en el soporte, pero la regla del hueco o fórmula que forme
parte del ámbito sigue en la frase. El prompt no se ha acortado como intervención
independiente. Una cita repetida en resumen, hallazgo y soporte requiere contexto
único del auditor; el mapa no resuelve la ambigüedad por preferir una marca.
R1b frente a R1a mide el paquete de contrato e instrucciones de evidencia, no un
mecanismo aislado. Nada de esto acredita todavía preferencia, exactitud ni P4.
