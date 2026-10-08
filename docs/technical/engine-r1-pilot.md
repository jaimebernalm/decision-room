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
