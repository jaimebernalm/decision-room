# 3.4.1 — Relaciones propuestas por el agente y utilidad de los informes

## Resultado

Implementado y contrastado con Bruma Café, el conjunto sintético de prueba del
onboarding: 1.656 registros de ventas, seis productos, tres canales, nueve filas
de marketing y tres meses. Se reutilizaron los archivos y el alcance confirmado,
incluida la respuesta desconocida sobre importes; no se proporcionaron al modelo
los hallazgos de referencia ni se alteraron los datos para obtener aprobación.

## Cambios

- Descubrimiento por el modelo sobre catálogo, perfiles y muestras acotadas,
  independiente de nombres de archivo, sufijos `id` o idioma. La importación
  sin modelo conserva el perfil técnico, sin inventar relaciones.
- Código sobre archivos completos valida claves simples/compuestas, nulos,
  duplicados, correspondencias, cardinalidad y multiplicación de filas. No se
  ejecuta SQL generado por el modelo para construir este catálogo.
- Propuestas y comprobaciones se guardan en una revisión compartida por chat,
  planificación y Mi negocio antes de capturar sus contextos. Procedencia,
  llamadas, consumo y respuesta quedan registrados. Correcciones del usuario
  prevalecen. Significado inferido nunca equivale a confirmado por el usuario.
- Fechas ISO con hora reconocidas sin modificar valores originales. Una
  actualización del perfilador conserva definiciones en los mismos archivos;
  archivos distintos siguen requiriendo una revisión nueva.
- Planificación/investigación orientadas al objetivo, contrastes y contribuciones.
  Auditoría obligatoria de utilidad por pregunta y frente al objetivo original.
  No se puede aprobar una auditoría fallida u omitir preguntas evaluadas.
- Citas a puntos exactos de series guardadas, tanto en hallazgos como en
  destacados, puntos de gráficos y comprobaciones. Se resuelven por ejecución,
  serie y etiqueta; no requieren copiar valores a métricas ni recalcular.
  Renderizado HTML, React, chat y evaluación usan la misma evidencia.

## Evidencia con el modelo real

Modelo configurado en la prueba: GPT-6 Luna, razonamiento bajo.

1. Descubrimiento: una llamada, aproximadamente 7 segundos; tres relaciones:
   Ventas → Productos, Ventas → Canales, Marketing → Canales. Todas muchos a uno,
   con destinos únicos, sin claves de origen sin correspondencia ni amplificación.
   Permanecen propuestas semánticas. Las limitaciones explican la agregación
   mensual necesaria para contrastar ventas y marketing; no se genera una unión
   directa que multiplique el gasto mensual.
2. Primer intento de informe: falló a los 152 segundos. La revisión sobredemandó
   desglose mensual y el analista intentó recuperar un borrador que debía escribir.
   Se precisaron responsabilidades y alcance, y se documentó el formato válido
   de claves de serie. El fallo permanece registrado, no se cuenta como éxito.
3. Segunda ejecución completa: aprobada en aproximadamente 173 segundos. El
   revisor bloqueó citas incorrectas y destacó la ausencia de contrastes útiles.
   El resultado identifica líderes, cambios por segmento y caída de tienda física.
4. Con las citas a puntos de serie: nueva revisión sobre los mismos resultados
   de investigación, aprobada en 84 segundos, sin nuevas ejecuciones Python.
   Se conserva la evidencia y no se heredan aprobaciones anteriores. Se corrigieron
   etiquetas de destacados y cobertura visual antes de aprobar.
5. Prueba adversarial real: el informe antiguo de distribuciones mensuales fue
   rechazado por la nueva revisión de utilidad. El diagnóstico señaló la ausencia
   de cambios cuantificados por segmento y la necesidad de delimitar datos sintéticos.

## Contraste independiente

Recalculado directamente desde los CSV con `csv`, `Decimal` y acumuladores de
Python, sin reutilizar programas generados ni aceptar el acuerdo del revisor
como prueba aritmética:

- 5.975 unidades; junio 1.541, julio 1.979, agosto 2.455.
- Café de la casa: 1.778 unidades acumuladas; Marketplace: 2.388.
- Marketplace: +275 y +332 unidades en los dos intervalos consecutivos.
- Tienda física: +22 y −93; el crecimiento agregado oculta el último descenso.
- Kit de iniciación: +88 y +153; Café de la casa: +125 y +109.
- Los 30 valores guardados en siete series coinciden con el cálculo independiente.
  Los cuatro gráficos entregan 18 valores; los hallazgos contienen 13 referencias
  verificables. Las contribuciones reconcilian con el cambio agregado.
- Tres relaciones y fechas del catálogo verificadas. Se comprobó proyección del
  informe, respuesta del chat, HTML y visualización de informe y ER en el navegador.

El informe distingue cantidades, cambios y relevancia para una siguiente revisión.
Excluye márgenes, no afirma causalidad, no extrapola fuera del periodo y señala
que la fuente es sintética. Los cambios mensuales son totales, no tasas diarias.

## Regresión

- Batería de 96 pruebas: catálogo, revisor, contexto de revisión, onboarding,
  servicio web e investigación por rondas.
- Batería final de 116 pruebas: evidencia de series, renderizado, esquemas de
  modelo, conversaciones/contexto, revisor, catálogo y evaluación. Todas pasan.
- Frontend: 78 pruebas pasan; comprobación focal del catálogo también pasa.
- Build correcto. Lint sin errores; advertencias existentes de Fast Refresh.
- Casos nuevos: nombres arbitrarios, claves compuestas, aislamiento entre
  negocios, relación insegura, precedencia del propietario, actualización de
  perfiles, petición incierta con reintento explícito, reutilización después de
  interrupción al guardar, rechazo de evidencia ajena/obsoleta y utilidad fallida.

Las bases, archivos de prueba y respuestas del modelo permanecen en almacenamiento
local ignorado. No se publican credenciales ni rutas personales.

## Límites y continuación

El descubrimiento se ejecuta antes de capturar contexto de conversación o
planificación y se reutiliza por versión de archivos/modelo. No extrae relaciones
arbitrarias leyendo código Python de ejecuciones posteriores. Nuevos archivos se
perfilan de nuevo; cambios de conocimiento invalidan aprobaciones antiguas, que
se conservan. Límite explícito de 64 tablas y 150 KB de contexto, hasta 96 propuestas
por llamada; dos respuestas de validación y hasta tres intentos por petición,
con recuperación explícita de peticiones inciertas.

Las comprobaciones técnicas no demuestran significado comercial. La revisión de
utilidad sigue siendo un juicio del modelo: exigir una auditoría no garantiza
hallazgos interesantes en cualquier conjunto. El caso de aceptación mejora,
pero no sustituye la evaluación amplia del 3.6. El paralelismo del 3.5 sigue pendiente.
