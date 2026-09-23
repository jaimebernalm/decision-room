# Paso 1.7 — implementación y criterios

1. **Escenarios reproducibles.** Ventas diarias y por producto, ambas con columnas
   originales y renombradas; importe ambiguo con precio unitario, total de fila,
   respuesta desconocida y rechazo a responder. Tres ejecuciones por escenario.
   Los casos iniciales sirven para calibrar. Los cambios y repeticiones posteriores
   conservan identidad y versión; no se sustituyen los fallos por los éxitos.
2. **Ejecutor completo.** Importación, plan, respuestas explícitas del propietario,
   investigación, revisión y exportación. Cada fase se ejecuta en otro proceso.
   No se edita el Python ni el informe del modelo. Guardar manifiesto, identificadores,
   salida, errores, tiempos, uso de tokens e informes. Reanudar el ejecutor no
   repite fases terminadas ni reintenta llamadas inciertas automáticamente.
3. **Evaluación independiente.** Recalcular referencias con CSV/Decimal, fuera del
   contexto del modelo. Separar finalización, exactitud, conducta, utilidad y
   recursos. Los nombres de métricas del modelo son libres: asociarlos explícitamente
   a referencias y conservar esa evaluación. Una rúbrica semántica requiere inspección
   del informe, plan y evidencias; el revisor del producto no es el evaluador único.
4. **Regresiones y correcciones.** Repetir las pruebas de interrupción, recuperación,
   invalidación, permisos y límites ya existentes. Añadir pruebas para los fallos
   nuevos. Evaluar DR-001, DR-002, DR-003 y generación de JSON/timeout; contrastar
   transportes compatibles del modelo local antes de atribuir todo al modelo.
5. **Cierre con evidencia.** Publicar resumen local y documentación de resultados,
   incluyendo fallos. Tres repeticiones son una comprobación inicial, no garantía
   estadística. Un caso solo pasa si cumple resultado esperado y revisión semántica;
   bloquear informes materialmente incorrectos. No declarar aceptada la entrega 1
   mientras existan fallos obligatorios pendientes.

No se añaden roles de agentes, investigación web ni un esquema universal para los datos.
Los resultados esperados y respuestas de evaluación nunca se envían al modelo
salvo la respuesta concreta que el propietario da al contestar su pregunta.
La adaptación multiarchivo y Excel continúa en la entrega 3.

## Código

| Archivo | Responsabilidad |
|---|---|
| `decision_room/evaluation/cases.py` | Doce escenarios, entradas del agente y referencias independientes con CSV/Decimal. |
| `decision_room/evaluation/runner.py` | Ejecutar las fases en procesos separados, conservar estados y errores, responder preguntas de prueba y comprobar correcciones del propietario. |
| `decision_room/evaluation/assess.py` | Contrastar métricas, exigir la rúbrica independiente y generar el resumen JSON/HTML. |
| `tests/test_evaluation.py` | Probar que el evaluador rechaza resultados incorrectos, sin revisión o sin evidencia vigente. |
| `tests/test_model_references.py` | Restringir identificadores, parejas ejecución/métrica y número de operandos sin introducir respuestas esperadas. |
| `tests/test_percentage_precision.py` | Admitir redondeos válidos y rechazar cifras incorrectas, falsa precisión y doble redondeo. |
| `tests/test_evaluation_resources.py` | Recuperar metadatos tras interrupciones y distinguir uso conocido, incompleto y duraciones mínimas. |

Los cambios en `agent/model.py` limitan las acciones ofrecidas a las posibles en
el estado actual y añaden el transporte estructurado de LM Studio. Los controles
de porcentajes están en `agent/review_contract.py`; la eliminación de duplicados
exactos del contexto, en `agent/review_context.py`. Las instrucciones de los roles
permanecen en sus archivos `*_prompts.py`.

## Configuración inicial

Recursos iniciales de evaluación: llamadas con 300 s de plazo, 8192 tokens de
salida, máximo 20 min por fase del proceso y presupuestos del grafo existentes.
Son límites del experimento local, no objetivos de servicio del futuro piloto.
El coste monetario se deja desconocido si no hay precios, nunca se inventa cero.

Transporte estructurado: la documentación de
[LM Studio](https://lmstudio.ai/docs/developer/openai-compat/structured-output)
describe JSON Schema en `/v1/chat/completions`. Se verificó en el modelo local instalado durante las series documentadas.
Esta garantía de formato no demuestra corrección semántica ni desactiva por sí
sola el razonamiento del modelo; registrar el uso que devuelve el servidor.

## Ejecutar y revisar

Con PostgreSQL, el sandbox y LM Studio disponibles:

```sh
.venv/bin/python -m decision_room.evaluation.runner run .local/evaluation/batch-01
# Calibración limitada antes de la matriz completa:
.venv/bin/python -m decision_room.evaluation.runner run .local/evaluation/calibration --scenario daily --repeats 1
.venv/bin/python -m decision_room.evaluation.assess .local/evaluation/batch-01
```

La matriz original ejecutaba ocho escenarios tres veces; la ampliación con Luna
descrita abajo ejecuta doce. Cada repetición crea una
empresa y sesión nuevas. El manifiesto conserva los hashes del código, CSV,
contexto y referencia, y la configuración del modelo. La carpeta debe permanecer
privada. `STOP` en la carpeta del lote detiene el ejecutor entre fases; repetir el
mismo comando continúa únicamente fases pendientes. Un fallo o una llamada
incierta permanece registrado y no se reintenta automáticamente. Un cambio de
código o configuración exige un lote nuevo. Las exportaciones HTML son instantáneas;
consultar el estado actual de la revisión antes de usarlas como aprobación vigente.

Cada trabajo guarda `state.json`, `initial-plan.json`, `plan.json`, `research.json`,
`review.json`, `resources.json`, `reference.json`, logs y rutas de exportación.
`summary.html` enlaza los resultados. Para aceptar el trabajo, revisar datos,
programas, preguntas, conversación y todo el informe; crear `assessment.json`:

```json
{
  "reviewer": "development_review",
  "notes": "Descripción concreta de las verificaciones y límites observados.",
  "rubric": {
    "definitions": true,
    "scope_and_limitations": true,
    "narrative_and_charts": true,
    "usefulness": true,
    "questions": true,
    "all_presented_numbers_checked": true
  },
  "bindings": {
    "first_sales": {"execution_id": "UUID_REAL", "metric": "NOMBRE_REAL"},
    "second_sales": {"execution_id": "UUID_REAL", "metric": "NOMBRE_REAL"}
  }
}
```

La terminación del comando significa que el ejecutor ha recorrido los intentos;
no equivale a que hayan pasado. Consultar `accepted`, `passed` y los controles de
cada caso en `summary.json`. Un proceso puede terminar normalmente conservando
casos fallidos, interrumpidos o pendientes de revisión independiente.

No copiar aprobados por defecto: cada booleano es un juicio independiente.
La rúbrica exige definiciones respaldadas por el propietario, cobertura honesta,
texto y gráficos coherentes, respuesta útil a la pregunta, preguntas necesarias y
verificación de **todas** las cifras presentadas. Las asociaciones numéricas mínimas
están en `reference.json`; añadir asociaciones para otras métricas comprobadas.
El código exige que los resultados obligatorios estén citados y sean vigentes.
Un fallo material debe marcarse falso y, si el modelo aprobó, retener la revisión
mediante `review.hold` antes de volver a exportar.

Para comprobar una corrección real del propietario después de un informe aprobado:

```sh
.venv/bin/python -m decision_room.evaluation.runner correct .local/evaluation/batch-01/unit-price-1 .local/evaluation/correction-01
```

Reutiliza exactamente la importación anterior, cambia la definición a total de fila,
replanifica y recalcula. La aprobación anterior debe quedar obsoleta. Conserva la
procedencia del CSV original, sin atribuirle la variante de columnas renombradas.
La corrección tiene su propia evaluación independiente.

El contexto del revisor elimina únicamente duplicados exactos: los programas de
la conversación remiten a `observations` y el borrador idéntico al actual remite a
`report`. Ambos objetos completos están en la misma petición. Las versiones
distintas y toda la conversación permanecen; no hay compactación automática.

La planificación recibe un esquema de acciones adaptado al estado: si todos los
perfiles ya están presentes, únicamente puede proponer; cuando quedan perfiles
por leer, puede inspeccionarlos. El servidor estructurado limita la forma de la
respuesta y la aplicación mantiene su validación posterior. Esto no determina
preguntas, interpretaciones ni cálculos por el agente.

## Interpretar una corrección posterior

El resultado de la matriz describe lo que se verificó en aquel momento. Si después
el propietario cambia una definición, la aprobación anterior queda obsoleta aunque
el caso histórico hubiera pasado. Conservar la evaluación y exportación históricas,
guardar el estado actual y volver a exportar la revisión antigua como bloqueada.
No editar la evaluación histórica para aparentar que el primer resultado ya usaba
la nueva definición. El nuevo informe necesita su propia aprobación y evaluación.

## Controles añadidos tras la matriz

La generación estructurada ofrece los identificadores reales de tablas y las
parejas ejecución/métrica disponibles, pertenecientes a observaciones vigentes,
terminadas y con evidencia. Cada ejecución conserva su propio conjunto de métricas:
no basta con que un nombre exista en otra ejecución. Si no hay evidencia, quedan
acciones de ejecutar, preguntar o retirar; no se inventa una referencia para poder
presentar un informe. La aplicación mantiene sus validaciones de autorización,
contrato y vigencia después de la respuesta del modelo.

Los checks numéricos ofrecen el número de operandos que admite cada operación:
ninguno para cero/no negativo, uno para igualdad, de uno a dieciséis para suma y
dos para cambio porcentual o proporción. Una suma que actúe como numerador debe
guardarse primero como métrica. Esto evita formas de llamada inválidas; no
certifica que se haya elegido el concepto o la fórmula correctos.

El porcentaje del texto se compara con el resultado aritmético redondeado una
sola vez a la precisión escrita. Por ejemplo, 16,149 admite 16,1 % y 16,15 %,
pero no 16,2 % ni 16,10 %. El control literal sigue siendo conservador con
intervalos y desigualdades; no interpreta todo el lenguaje natural del informe.

Cuando vence el plazo de una fase o el proceso sale inesperadamente, el ejecutor
recupera identificadores y recursos persistidos, conserva la causa original y
registra cualquier fallo adicional de recuperación. No reintenta una llamada de
resultado incierto. Los resúmenes mantienen los tokens conocidos y el número de
llamadas sin uso informado; el total exacto queda desconocido si falta información.
Las duraciones recuperadas que solo se conocen como mínimo se muestran con ≥.

## Validación con GPT-6 Luna antes de entrega 3

El ejecutor carga el `.env` privado y admite `openai`, su endpoint HTTPS,
razonamiento y límite de salida. Los valores quedan fijados en el manifiesto;
la clave solo se hereda en el entorno de los procesos, nunca en los registros.
El Python generado sigue ejecutándose localmente, sin red ni credenciales.

```sh
.venv/bin/python -m decision_room.evaluation.runner run .local/evaluation/luna-validation-01 \
  --model gpt-6-luna --protocol openai --reasoning low --max-output-tokens 16384
```

Esta ampliación conserva los ocho escenarios anteriores y añade `duplicates`,
`missing-values`, `returns` e `invalid-dates`, derivados de los fixtures públicos
y documentados en `data/reference-cases/04-data-quality/README.md`. La matriz
actual completa tiene **12 escenarios por tres repeticiones: 36 recorridos**.
Los totales anteriores de ocho escenarios describen la matriz histórica local.
Las incidencias se definen en el contexto sin facilitar resultados esperados:
duplicados técnicos por identificador, importes desconocidos, devoluciones
negativas y exclusión explícita de filas con fecha o importe inválidos.

Las asociaciones independientes pueden referenciar una métrica escalar o un punto
de una serie mediante `{execution_id, series, label}`. La serie debe estar citada
por un gráfico del informe y ser vigente. Las tarjetas también cuentan como citas
de métricas. Esto no acepta automáticamente la narrativa, las etiquetas o la
utilidad: se conserva la rúbrica independiente para cada recorrido.

Tras la matriz de Luna, los esquemas de gráfico emparejan la serie con su unidad
guardada; los gráficos de escalares siguen siendo posibles. La cobertura exige
cada investigación lista y permite explicar una bloqueada solo como no disponible
y sin hallazgos de respuesta. El servidor sigue rechazando referencias obsoletas,
unidades distintas, claves ajenas y omisiones. No se convierten datos ni se
corrigen cifras automáticamente para hacer pasar un informe.

Las instrucciones distinguen agregados definidos por el propietario de importes
por artículo sin base conocida. Para una sola categoría se pide una métrica
escalar; el diagnóstico de series indica si faltan puntos o sobran. Las versiones
son `planning-v6`, `research-v7` y `review-v10`. La validación de estas correcciones
se registra en un lote separado, conservando intactos los fallos iniciales.
