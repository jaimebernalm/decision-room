# Validación del onboarding conversacional — 3.4

Fecha: 27 de septiembre de 2026. Rama: `feature/insights-pipeline`.

## Alcance

Se implementa el [plan técnico](../technical/conversational-onboarding-plan.md):
el asistente habitual guía el primer análisis, conserva el chat y entrega un
informe revisado después de una confirmación explícita. Se utilizan PostgreSQL,
el ejecutor Docker y bases de evaluación aisladas con datos ficticios.

## Pruebas automatizadas

- Batería completa Python: **364 pruebas**, **187,519 s**, correctas.
- Tras reforzar la procedencia de las preguntas, las dependencias del encargo y
  el procesamiento inicial de memoria: **15 pruebas de onboarding**, **5,472 s**,
  correctas, incluyendo el informe completo y su continuación.
- Frontend: **71 pruebas en 11 archivos**, correctas; compilación TypeScript y
  Vite correctas. Lint de los componentes modificados sin errores. Al incluir
  toda la carpeta de utilidades aparecen cinco avisos existentes de Fast Refresh
  en `assistant.tsx`; Vite mantiene el aviso de paquete superior a 500 kB.
- `git diff --check` y compilación Python correctos.

Los modelos programados verifican mecanismos, no calidad del modelo real:

- Inicio repetido y confirmación concurrente crean un chat y un trabajo.
- Objetivo libre y opciones combinables; cambios invalidan la propuesta anterior.
- Propuesta revisada, datos inspeccionados, ámbito de negocio y versiones actuales.
- Ningún `investigate` del modelo puede saltarse la confirmación inicial.
- Pregunta original, motivo, obligatoriedad, tabla/columna y turno de origen se
  conservan junto a respuestas desconocidas u omitidas.
- El contexto opcional no bloquea la confirmación; una definición esencial requiere
  respuesta o reducir el alcance. La vista abre la columna referida automáticamente.
- Interrupción incierta y recuperación explícita mantienen conversación e historial.
- Pérdida de respuesta al confirmar o contestar «No lo sé» conserva clave y contenido
  del envío; no convierte lo desconocido en una afirmación al reintentar.
- Carga parcial exige aceptación; edición de alcance utiliza el mismo chat.
- Un negocio distinto no puede leer los datos ni confirmar el encargo anterior.
- HTTP con autenticación y sesión vacía, migración repetible y compatibilidad de
  decisiones antiguas. La descripción inicial se procesa antes del primer snapshot.
- Entrega aprobada, continuación en el mismo chat y recuperación diferenciada de
  informes bloqueados o desactualizados.

## Evaluación con modelo real

Modelo **GPT-6 Luna**, razonamiento `low`, salida máxima 16.384 tokens por llamada.
El modelo no recibe el oráculo de verificación. Se conservan localmente entradas,
conversaciones, trabajos, informes y comprobaciones independientes en
`.local/evaluation/onboarding-34/`; no se versionan bases, credenciales ni trazas.

### Comparación completa

Se usa [`ventas.csv`](../../data/onboarding-example/ventas.csv): 12 filas,
cinco columnas, julio y agosto de 2026. El propietario explica la base monetaria
(total de fila), euros sin IVA y costes de producto. El recorrido produce una
propuesta confirmable, un informe aprobado y una respuesta posterior que conserva
el objetivo en la misma conversación.

Repetición final: evaluación `3163321733d0`, informe
`df5f51e6-2fa7-4087-81a7-5782b97c8acb`. Se comprueban con CSV y aritmética Decimal
los **10 puntos de cuatro gráficos y dos indicadores** (12 valores):

| Medida | Julio | Agosto | Cambio |
| --- | ---: | ---: | ---: |
| Ventas | 615 | 1.035 | 420 |
| Margen bruto | 285 | 477 | 192 |

Las contribuciones al cambio de ventas son 60, 120 y 240; las de margen, 36, 60 y
96, para bolígrafos, cuadernos y mochilas. Las afirmaciones principales coinciden.
La entrega distingue registros observados de meses completos y contribución de
causalidad. Tras reconectar, el informe sigue publicable y no queda ninguna fuente
de memoria pendiente. Respuestas iniciales: 13,3 s, 9,5 s y 12,5 s; continuación: 7 s.
Estos tiempos puntuales no constituyen una evaluación de rendimiento.

### Objetivo reducido por información desconocida

Evaluación `07059f794d54`, informe `3bb17851-aadd-4bde-a45c-f02a3b80c660`.
Dos tablas ficticias: tres ventas y dos categorías. Ventas: cuadernos con 2 y 3
unidades, mochilas con 4; fechas del 1 al 3 de julio de 2026. El significado de
`importe` no está definido. Se solicita organizar unidades y ventas, además de
predecir septiembre.

El asistente explica que las predicciones no están disponibles. Después de
inspeccionar las tablas pregunta si `importe` es precio unitario o total de fila,
con referencia exacta a la columna. Ante «No lo sé» propone analizar unidades y
fechas, excluyendo cálculos monetarios y pronósticos. El propietario confirma ese
alcance reducido; el informe responde **2/2 preguntas del alcance confirmado**.
Esto no equivale a satisfacer todas las intenciones originales.

Se verifican independientemente **cinco puntos de gráficos y dos indicadores**:
5 y 4 unidades por categoría, un registro en cada fecha, 9 unidades totales y
3 fechas. No se suman importes desconocidos. La respuesta que propone el alcance
tras «No lo sé» tardó **76,7 s**: el recorrido funciona, pero esta latencia merece
medición y mejora en 3.6.

## Intentos conservados y correcciones

- El primer intento real detectó un esquema estricto del proveedor incompleto para
  propiedades opcionales. El envío incluye ahora todas las propiedades; las
  decisiones históricas siguen aceptando campos ausentes.
- Hubo confirmaciones redundantes del objetivo, citas de catálogo para valores
  inspeccionados y ambigüedad sobre capacidades de predicción. Se explicita la
  etapa, se citan inspecciones y el runtime declara que no puede predecir.
- Una revisión agotó 12 continuaciones por discrepancias entre pregunta estructurada
  y texto, entre otros reparos. El servidor incorpora la pregunta exacta antes de
  revisar y publicar, evitando exigir al modelo duplicarla literalmente.
- Un intento incluía importes cuya base no se conocía. Se exige aclarar precio por
  unidad frente a total de fila o excluir ese cálculo; el caso final lo demuestra.
- La respuesta «No lo sé» llegaba al trabajador analítico con texto no vacío;
  el adaptador conserva su disposición y envía el formato esperado por el servicio.
- Al arrancar el trabajador después de una evaluación directa, la extracción tardía
  del perfil invalidó un informe anterior. El primer turno referencia ahora esa
  fuente y resuelve la extracción antes de tomar contexto. La repetición final
  conserva publicación válida después de reconectar.
- La prueba HTTP detectó la respuesta vacía sin serializar; la sesión inexistente
  devuelve JSON `null`. Los fixtures de migración se adaptaron a las nuevas claves
  foráneas y a la versión 21.

Los intentos fallidos no se presentan como éxitos ni se eliminan de la evidencia.

## Comprobación visual y límites

Se comprueban escritorio y móvil en una instancia local separada: objetivo con
opciones y texto libre, alta de un segundo negocio sin botón «Bienvenida», subida
de dos CSV, pregunta real sobre `importe`, apertura automática de la tabla y
columnas resaltadas, respuesta «No lo sé», presentación de la conversación y
entrega breve con evidencia expandible. En móvil (390 × 844) la tabla conserva
su desplazamiento horizontal dentro del panel y la página no desborda. La
revisión visual complementa las pruebas de componentes.

No se añade un agente independiente para onboarding, un dashboard configurable,
pronósticos ni analistas concurrentes. **3.5** implementará el reparto de análisis;
**3.6** evaluará calidad, coste, latencia y utilidad por objetivo en bases grandes y
casos repetidos. Estos ejemplos pequeños acreditan el recorrido y sus límites,
no una mejora cuantificada de calidad sobre bases sustanciales ni una validación
con clientes reales. Los reintentos limitados de 429/503 de 3.3.1 se reutilizan.
