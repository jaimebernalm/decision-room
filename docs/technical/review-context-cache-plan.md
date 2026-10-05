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
