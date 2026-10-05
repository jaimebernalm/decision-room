# Contexto de revisión, caché y panorama — 5 de octubre de 2026

Base: 6c91932. Cambios locales separados, sin llamadas reales ni fusión de ramas.

1. Opción de contexto de revisión: presupuesto total de 70.000 tokens incluyendo
   sistema, esquema, correcciones y reserva de salida. Tokenizador local declarado;
   compactación determinista, catálogo de evidencia y lectura paginada de originales.
   Auditoría y validación usan originales, nunca el resumen. Preservar objetivo,
   dudas, objeciones y último borrador. Revisar acumulación de instrucciones.
2. Opción de prefijo estable: esquema independiente de las evidencias variables,
   validación posterior con correcciones concretas, datos estables antes de variables,
   clave de caché por sesión y telemetría de tokens cacheados (desconocido no es cero).
   Sin afirmar ahorros reales: requieren medición del proveedor.
3. Opción de obligaciones del panorama: inventario exacto de huecos materiales,
   ninguno cuando no los hay. Una demanda demostrablemente fuera del contrato no
   puede convertirse en veto de integridad; las objeciones reales siguen bloqueando.
4. Rebasar b0f69de (solo P1b) sobre los tres cambios, con regresiones.

Referencia oficial consultada: https://developers.openai.com/api/docs/guides/prompt-caching
La reutilización requiere prefijos iguales; las claves no garantizan aciertos y
los tokens cacheados también consumen TPM. No modificar el límite por defecto
para todas las cuentas por el aumento de cuota de esta cuenta.

## Paso 1 implementado

`DECISION_ROOM_REVIEW_CONTEXT_BUDGET=true`, por defecto apagado; objetivo configurable
con `DECISION_ROOM_REVIEW_CONTEXT_TOKENS=70000`. Se cuentan todos los campos de la
petición con `o200k_base`, reserva de salida y margen de 2.048 tokens para encuadre
/modelos con tokenización distinta. Es un presupuesto local explícito, no los tokens
facturados por el proveedor. Añadida dependencia tiktoken; instalar requirements.

El presupuesto se aplica después de adjuntar memoria y construir sistema/esquema.
Elimina del envío borradores históricos, checkpoints repetidos y programas/logs,
conserva escalares citables y muestra las series largas como muestras identificadas.
No recorta silenciosamente objetivo, dudas, objeciones ni último borrador. El detalle
se abre con `retrieve/read_review_context` sobre referencias JSON de esta revisión,
con paginación, hash y registro persistente; sin acceso libre al disco/otros negocios.
La API del modelo puede pedir más contexto; son llamadas sujetas a su presupuesto,
no ejecuciones Python adicionales. La auditoría y validación conservan originales.

El sistema de revisión se reescribió como contrato breve de esta fase, con las
reglas de evidencia, alcance, permisos, cobertura, gráficos, ejecución y aprobación,
y las extensiones activadas (P3, panorama, guardián). Requiere evaluación semántica.
Si incluso lo protegido y el esquema no caben, se explica antes de enviar; no se
promete comprimir arbitrariamente cualquier entrada conservando toda su información.

Validación inicial: 25 pruebas locales (contexto grande, lectura paginada y aislada,
PostgreSQL con roles simulados, reanudación, esquemas y contratos del panorama).
Sin llamadas reales. Los dos límites históricos de bytes siguen vigentes con opción
apagada. El cambio no aumenta el TPM por defecto de otras cuentas.

## Paso 2 implementado

`DECISION_ROOM_REVIEW_STABLE_PREFIX=true`, por defecto apagado. Recomendado junto
con el presupuesto anterior. Esquema idéntico entre analista/revisor y correcciones
con las mismas opciones; IDs y claves disponibles se validan contra originales.
Las disposiciones viajan como una lista de pares clave/decisión y se normalizan al
contrato persistido antes de validarlo; duplicados y referencias inventadas fallan.
Las correcciones incluyen una muestra acotada de referencias válidas y remiten al
catálogo completo. Las restricciones semánticas siguen siendo responsabilidad del
validador; estabilizar el esquema no convierte cualquier string en evidencia válida.

Sistema y contexto estable preceden evidencia, borrador, rol y corrección. Cambiar
el objetivo o las definiciones sí cambia el prefijo deliberadamente. La petición
audita hashes del esquema y prefijo visible; OpenAI recibe una clave opaca por
sesión, sin datos personales. El transporte usa la estimación completa en tokens
cuando está disponible y no resta caché del presupuesto TPM.

La respuesta conserva la telemetría del proveedor. Comparar dos exportaciones de
`review.show` (o listas de llamadas) con:

```
python scripts/compare_review_cache.py antes.json despues.json
```

El resultado distingue caché ausente de cero y no infiere precio ni ahorro de la
cuenta. Las pruebas HTTP simuladas verifican prefijos idénticos, esquemas estrictos
con 1.500 claves adicionales, rechazo/corrección local y contadores. No hay una
medición real posterior todavía: la hará el lanzador sobre los lotes comparables.

## Paso 3 implementado (punto 4 del encargo)

`DECISION_ROOM_PANORAMA_OBLIGATION_GUARD=true`, por defecto apagado e independiente
del guardián editorial. El contexto enumera exactamente los huecos materiales que
admiten/exigen disposición, su cardinalidad y «Ninguna» si no existen. Los cambios
no añaden obligaciones. Se calcula desde el panorama original antes de compactar.

Una petición estructurada de más disposiciones que las admitidas se comprueba
contra el contrato y contra **todas las disposiciones/prioridades actuales**.
Tras repetirse, puede cerrarse como entrega del controlador con prueba auditada,
aunque el revisor la llamara integridad. No altera ni borra su clasificación o
texto original, no fabrica aprobación y no añade ruido al informe del dueño.

No se interpreta texto libre para perdonar objeciones: debe identificar el campo
y el mínimo solicitado. Si faltan huecos reales, hay evidencia/prioridad inválida,
fallos numéricos/semánticos/gráficos o cualquier otra objeción de integridad, sigue
bloqueando. La opción apagada conserva el enum anterior del esquema. El esquema
estable usa la misma regla y el inventario actual permanece en el contexto variable.

Validación: pruebas de contrato con cambios pero sin huecos, falta real de huecos,
objeciones distintas/históricas, checks fallidos y ambos esquemas estrictos.
Integración con CSV sintético con horas a medianoche, importación real, PostgreSQL
propio y roles simulados: cuatro llamadas de roles, cierre en segunda objeción,
auditoría original y reanudación sin llamadas adicionales. Las tres regresiones
editoriales anteriores siguen pasando. No se han usado modelos reales.

## Correcciones del piloto — 5 de octubre, base 26fcdc4

Plan: (1) metadatos y superposición con contexto compacto; (2) clave de caché por
revisión y evidencia estable antes del sufijo variable; (3) citas del dueño sin
texto libre en enums y lint estricto de todos los productores; (4) rebasar P1b.
Sin llamadas reales y con commits separados.

### Series: implementado

La inspección de 26fcdc4 no reproduce la eliminación de `unit`: la función hace
copia profunda y ya marca la muestra dentro de `points_summary`. Queda pendiente
contrastar la petición concreta del piloto. La nueva vista hace explícitos en cada
serie unidad exacta, grano, etiqueta (identificador si no hay nombre guardado),
conteo total, primero/último, mínimo/máximo sobre **todos** los puntos, `sampled` y
la referencia paginada al original. No deriva el grano del espaciado de la muestra.

`full_series_reference` permite construir `chart.series` o `layers[].series` con
`points=[]`. Las instrucciones exigen copiar la unidad exacta, incluso definiciones
entre paréntesis; la presentación resuelve todos los puntos guardados. Las pruebas
capturan HTTP simulado con/sin prefijo estable, superponen 178 puntos originales y
rechazan una unidad abreviada incompatible. También comprueban extremos que no
están en la muestra. 14 pruebas locales aprobadas; sin modelos.

### Caché del piloto: implementado

La clave opaca usa ahora el ID de **revisión**, estable al reanudar y distinto en
otra revisión; solo contextos sin ese ID usan la sesión como respaldo. Antes ya
había clave por sesión de investigación: la corrección no parte de ausencia de clave.

Se encontró una barrera local concreta: el objeto variable ordenado alfabéticamente
situaba presupuestos y conversación antes de las observaciones. Ahora el bloque
`review_evidence` (panorama y evidencia actual) precede al borrador, presupuestos,
conversación, recuperaciones y correcciones. No se duplica la evidencia. Cambiar o
añadir evidencia sí cambia su prefijo deliberadamente; nunca se reutilizan datos
obsoletos. Se auditan hashes hasta contexto estable y hasta evidencia, y estimaciones
de tokens por bloque para comparar con los tokens cacheados reales del proveedor.

14 pruebas offline de caché/series/presupuesto: mismos prefijos entre roles y
correcciones, invalidación ante nueva evidencia y claves distintas por revisión.
El ahorro sigue pendiente de lote; ni una clave ni un hash garantizan reutilización.
Referencia OpenAI Docs consultada: https://developers.openai.com/api/docs/guides/prompt-caching

### Citas y lint estricto: implementado

`GapOwnerProof.quote` es texto libre, nunca el encargo completo dentro de un enum.
`source` identifica un mensaje del dueño; `owner_message/<id>` usa el ID guardado,
con alias antiguos conservados para informes existentes. El contexto enumera los
IDs disponibles. El validador exige una subcadena literal no vacía del mensaje
seleccionado, normalizando espacios en ambos textos (sin cambiar letras, números,
puntuación o negaciones). No permite mezclar mensajes ni citar un origen ajeno.
El revisor sigue juzgando la pertinencia de la cita y del descarte.

Antes de cualquier envío OpenAI, el esquema final pasa por un lint que revisa
**todos** los nodos, incluidas definiciones: objetos cerrados y required idéntico
a las propiedades; ausencia de LF/CR/TAB reales en enum/const/pattern; máximo de
1.000 valores de enum y el límite adicional de longitud existente. Los enums de
etiquetas con caracteres rechazados se convierten en strings validados localmente,
sin alterar etiquetas originales. Un patrón inválido restante impide abrir HTTP.
Esto cubre reglas conocidas, no pretende replicar todo el validador del proveedor.

La matriz recorre todos los productores existentes, las 64 combinaciones de seis
opciones de revisión en ambos roles (128 peticiones simuladas), más continuidad y
recuperación de investigación. Incluye más de 1.000 claves, historial grande y
mensajes multilínea. Detectó además `ReviewIssue.required` incompleto bajo políticas
antiguas; corregido. Las pruebas verifican tanto rechazo del lint como peticiones
finales válidas. Referencia oficial: https://developers.openai.com/api/docs/guides/structured-outputs

## Piloto 0/2 — contratos congelados y presupuesto

Base de estas correcciones: 32ae3ac. Plan: restaurar enums constantes por revisión
con inventarios completos; corregir mensajes sin recortes; ampliar compactación y
presupuesto por defecto; revisar el límite real de caché. Prueba final a través de
HTTP simulado: las respuestas se construyen exclusivamente desde el payload visible.

### Contratos constantes restaurados

El esquema de prefijo estable vuelve a enumerar investigaciones conocidas, estados
permitidos por tarea y referencias de métricas del panorama. Una nueva ejecución
del revisor o un nuevo borrador no cambia esos enums. Se conservan referencias
libres para cálculos que sí aparecen durante la conversación.

El contexto expone íntegros `required_coverage_keys`, `allowed_coverage_keys` y
`citable_panorama_metrics`, sin muestras ni recortes. Son datos del controlador,
no claves inferidas del texto del plan. Las listas completas viajan también en el
sufijo variable cuando se usa prefijo estable, como contrato explícito de cada turno.

### Correcciones exactas

Los errores de cobertura identifican faltantes, desconocidas, duplicadas y todas
las claves válidas. Los errores de prioridad identifican las referencias inválidas
y todos los pares válidos del panorama. Un error tipado conserva esa información
sin el recorte de 1.800 caracteres del controlador. Los demás errores de referencias
incluyen el catálogo actual completo; ya no se añade una muestra de 16 métricas.
13 pruebas locales de contratos/correcciones aprobadas, incluida una corrección
mayor de 1.800 caracteres cuyo último elemento debe permanecer visible.
