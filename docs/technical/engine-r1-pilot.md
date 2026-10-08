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
