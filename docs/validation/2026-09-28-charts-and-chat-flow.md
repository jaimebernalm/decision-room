# 3.8.10 · Gráficos y continuidad del chat

## Entrega

- El analista puede declarar `Chart.encoding`: categoría, serie, orden y tipo de
  medida (cantidad o variación), con coordenadas vinculadas a las etiquetas exactas
  de los puntos guardados. Se rechazan omisiones, celdas duplicadas, series sin
  correspondencia y meses ISO desordenados. Las dimensiones forman parte de la
  aprobación; las cifras siguen resolviéndose contra evidencia vigente.
- Barras horizontales agrupadas y leyenda con colores coherentes en todo el informe.
  Las variaciones tienen escala simétrica y referencia cero. Las combinaciones
  ausentes no se convierten en ceros. Se conservan los decimales exactos en tabla y
  tooltip. Web y exportación HTML comparten las coordenadas y la paleta.
- Compatibilidad conservadora para etiquetas antiguas de categoría/mes explícitas:
  `categoría | mes`, `categoría | cambio mes-mes` y categoría seguida de un mes ISO.
  Si no se reconoce toda la estructura sin ambigüedad, se conserva la vista simple.
  Esta adaptación no modifica el informe aprobado ni recalcula sus datos.
- El historial público agrupa consultas, preparación y revisión. Distingue una
  revisión que pide ajustes de una aprobación. Las llamadas originales permanecen
  en el monitor interno; el resumen es solo una proyección de presentación.
- Las respuestas nuevas aparecen por fragmentos de palabras, aproximadamente a
  180 caracteres/segundo y con un máximo de 4,5 segundos. Solo se presenta texto
  que ya ha pasado el revisor: **no es streaming de borradores del proveedor**.
  Actividad «Mostrando respuesta» durante la presentación y «Respuesta lista» al
  terminar, junto con fuentes y adjuntos. Historial inmediato, opción de mostrar
  todo, compatibilidad con movimiento reducido y limpieza de temporizadores.
- Las herramientas de informes incluyen inicio de revisión y fecha real de
  aprobación. La búsqueda sin texto se ordena por instante de aprobación y declara
  fechas desconocidas. El asistente distingue estas fechas del periodo analizado y
  puede contestar con citas sin adjuntar un informe completo.

## Evidencia

- **110 pruebas Python pasan**: `test_chart_layout`, `test_report_metadata`,
  `test_client_report`, `test_model_wire_schema`, `test_series`,
  `test_review_hardening`, `test_activity`, `test_internal_monitor`,
  `test_conversations` (PostgreSQL y sandbox donde corresponde).
- **104 pruebas frontend pasan**. Incluyen texto parcial y final, fuentes al
  terminar, historial sin repetición, salto a respuesta completa, movimiento
  reducido, finalización de turno pendiente, montaje con React StrictMode,
  agrupación de actividad y transición de su titular.
- Compilación TypeScript/Vite y lint sin errores; persisten los avisos anteriores
  de componentes compartidos y tamaño de bundles. `git diff --check` limpio.
- Bruma Café: los dos gráficos de 30 puntos se presentan como 18 cantidades
  mensuales y 12 variaciones, sin cambiar la evidencia ni el hash de aprobación.
  Verificados visualmente en escritorio y a 390 px: leyendas legibles, etiquetas
  de producto y sin desbordamiento horizontal. También se agrupa la comparación
  por canal/mes con etiquetas ISO.
- Chat real: la pregunta por la fecha del último informe responde con su aprobación
  del 28/09/2026 a las 18:29 EDT, distingue el periodo de datos y conserva citas
  sin adjuntar el informe completo. Su historial desplegado muestra tres hitos.
- Llamada real al analista con otro ejemplo sintético: devuelve un gráfico de
  productos por meses ISO, con `encoding`, leyenda y referencias a puntos guardados.
  Pasa la validación del contrato y de evidencia. No se publica como informe del
  cliente ni sustituye a Bruma.

Esta última prueba detectó un bloqueo previo del schema: una ejecución con solo
series guardadas no permitía `submit`. Se corrigió para aceptar referencias a
puntos de esas series sin exigir métricas escalares redundantes; una regresión
específica y la llamada real verifican el cambio.

Los registros completos y artefactos de las pruebas reales permanecen en `.local/`
(ignorados por Git). No se cambian respuestas históricas ya guardadas: las fechas
corregidas se utilizan al responder nuevas preguntas.
