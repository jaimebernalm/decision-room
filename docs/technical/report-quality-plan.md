# 3.9 — Calidad de la entrega y autonomía de investigación y presentación

**Estado:** implementación en curso; evaluación pendiente.  
**Fecha:** 30 de septiembre de 2026.  
**Base inspeccionada:** `5af6cb7`, rama `feature/report-quality`.  
**Continuidad:** este documento conserva decisiones, incrementos y resultados de 3.9.  
**Referencias:** [plan general](../product/Decision%20Room%20-%20Plan%20de%20implementacion.md), [onboarding e informes](../product/onboarding-e-informes-plan.md), [3.7](business-planner-plan.md), [resultados de 3.7](../validation/2026-09-28-business-planner.md), [evaluación de calidad](quality-evaluation-plan.md), [contrato actual del informe](client-report.md).

## 1. Encargo y resultado esperado

El usuario solicita planificar dos mejoras coordinadas:

1. Dar a los agentes más libertad para decidir cómo investigar las señales y cómo
   presentar resultados útiles, más allá de permitir líneas mensuales.
2. Convertir una señal respaldada en una prioridad comprensible y una reacción
   concreta: qué revisar, por qué, qué se puede calcular ya, qué información falta
   y cómo esa información cambiaría la siguiente decisión.

El agente elige la estrategia; el código comprueba integridad y coherencia; el
revisor evalúa evidencia y utilidad. La libertad comprende selección de señales,
métodos, desgloses, hipótesis condicionales, orden de la síntesis y representaciones
soportadas. No se convierte una preferencia editorial en una prohibición técnica.
El objetivo y los entregables confirmados por el propietario siguen siendo la
referencia: profundizar no autoriza sustituirlos por otro encargo.

La petición posterior del propietario autoriza aplicar el plan completo. Los
incrementos se cierran solo tras comprobarlos; la evaluación y la prueba conjunta
no se dan por completadas al implementar capacidades.

## 2. Diagnóstico de entrada

La evaluación de 3.7 no demostró una mejora consistente de utilidad. La prueba
manual posterior de Bruma Café permite examinar un recorrido completo con una
respuesta «no lo sé» sobre importes de ventas y costes. La auditoría independiente
recalculó los CSV y no encontró discrepancias en 38 métricas y 60 puntos de series;
esto no equivale a aceptación de utilidad ni de generalización.

Fallos que debe resolver esta entrega:

- Se identifica la divergencia de Tienda física frente a los canales digitales,
  pero se concreta poco qué productos revisar primero.
- La señal prioritaria es julio-agosto y el cruce detallado entregado compara
  junio-agosto; el desglose válido no se centra en el intervalo de la alerta.
- Algunas contribuciones por producto calculadas y disponibles en el contexto
  del planificador no llegan a la síntesis del cliente.
- Las comprobaciones operativas son pertinentes, pero dejan poco claro qué dato
  falta, qué contraste resolvería y cómo cambiaría la reacción.
- La revisión da por respondidas investigaciones internas sin demostrar que cada
  componente del encargo del propietario tiene una respuesta útil.
- Una objeción a la unidad de marketing termina retirando una vista pedida, sin
  sustituirla por una comparación igualmente legible.
- Se propaga incertidumbre entre conceptos distintos: moneda, unidad, grano y base
  por fila/unidad. La duda sobre una medida no define automáticamente otras.
- El contrato y las instrucciones reservan líneas para series diarias. El frontend
  tiene un renderer de líneas, pero el esquema no ofrece líneas para series
  mensuales guardadas y las coordenadas agrupadas solo admiten barras o tablas.
- Se repiten errores de alias/evidencia autorizada durante la recuperación.

La política `goal_quality.py` y el planificador ya contienen parte de los criterios
deseados. Cambiar solo su redacción no demuestra que se cumplan en la entrega.
Preservar el informe y los intentos originales como referencia local; no ajustar
retroactivamente sus cifras, aprobación ni evaluación. La documentación pública
incluye resultados sintéticos resumidos; CSV, snapshots y datos privados quedan
fuera de Git.

## 3. Responsabilidades y autonomía

| Rol | Decide y realiza | Evidencia de su decisión |
|---|---|---|
| Planificador de negocio | Qué preguntas y señales merecen atención respecto al objetivo; prioridades, contraste con alternativas y contexto operativo útil. Reconsidera al recibir resultados. | Encargo e instrucciones vinculados a resultados guardados; motivo de prioridad y orientación concreta para redactar. |
| Analista principal | Cómo comprobar las señales: filtros, comparabilidad, métodos, desgloses, seguimientos y coordinación de subanalistas. Elige la presentación del borrador. | Investigaciones con origen, segmento, periodo, cálculo y resultados; síntesis con referencias y límites. |
| Subanalistas | Ejecutan el encargo y proponen seguimientos respaldados al principal. | Cálculos, reconciliaciones y candidatos conservados. |
| Revisor independiente | Si la entrega responde al encargo, la representación es adecuada y las conclusiones/comprobaciones son útiles y respaldadas. | Auditoría sobre el borrador vigente y resolución explícita de reparos materiales. |
| Código | Pertenencia, dependencias, autorización de tablas, vigencia, números, coordenadas, unidades, presupuestos y recuperación. | Controles verificables; no inventa prioridades, causas o acciones comerciales. |

Conservar el diálogo de 3.7 al inicio, en checkpoints relevantes, por consulta del
analista y antes de redactar. No consultar al planificador para cada cálculo.
El analista puede abrir seguimientos dentro del alcance desde evidencia nueva;
el planificador puede proponerlos, pero el principal los convierte en encargos
con dependencias válidas. El revisor puede pedir una comprobación material que
falta, sin asumir la dirección de toda la investigación.

Una ampliación de desglose dentro del objetivo no exige otra confirmación del
cliente. Una propuesta que cambia el alcance utiliza el flujo existente de
confirmación. Las respuestas que cambian definiciones conservan la sucesión de
planes y el recálculo de evidencia afectada; el contexto operativo compatible
no repite cálculos válidos. «No lo sé» y rechazo permanecen límites explícitos.

## 4. Investigación guiada por señales

El agente selecciona libremente un contraste material y justifica su relación
con la intención del propietario. Mayor volumen, un signo negativo o un umbral
universal no determinan por código qué investigar primero.

Para descubrir/priorizar o un objetivo mixto, el ciclo debe permitir:

1. Situar la señal: medida, magnitud, segmento, periodo y comparación pertinente.
2. Comprobar definiciones, grano, cobertura observada y exposición comparable.
   Calcular sensibilidades factibles sin pedirlas al cliente; distinguir fechas
   observadas de apertura o exposición operativa certificadas.
3. Profundizar en el mismo segmento e intervalo que motivaron la prioridad.
   Elegir productos, días, tipos de día, canales u otro desglose que discrimine
   interpretaciones y que los datos permitan; no ejecutar un menú fijo de cruces.
4. Cuantificar componentes y reconciliarlos con el total. Si se informa una
   concentración, precisar el denominador: cambio neto, descenso bruto, volumen
   u otra medida. Conservar signos y compensaciones.
5. Contrastar la prioridad con otras señales relevantes, incluidas oportunidades
   positivas. Indicar qué añade el desglose y cuándo más aritmética ya no aporta.
6. Distinguir contribución calculada, hipótesis y hecho operativo confirmado.
   Identificar qué evidencia permitiría discriminar las hipótesis útiles.
7. Entregar una comprobación concreta o una respuesta parcial explícita; no abrir
   ramas repetidas solo para aparentar profundidad ni aprobar por agotamiento.

En organizar/dashboard o una pregunta factual, la libertad se orienta a cobertura
y claridad. No imponer una recomendación o hipótesis causal a todos los hallazgos.
Los presupuestos siguen siendo cortacircuitos recuperables, no una obligación de
minimizar investigación útil. Ajustarlos solo con evidencia, registrando el motivo.

### Referencia sintética de Bruma

En Tienda física, julio-agosto pasa de 621 a 528 unidades: −93, aproximadamente
−15,0%. Café de la casa, filtros y café de origen aportan −32, −20 y −19: −71,
el 76,3% del descenso. Cinco productos bajan y uno permanece estable. Ese patrón
amplio y esa concentración pueden coexistir; los tres productos no son tres
causas demostradas. En el agregado, el Kit aporta +153 de +476 unidades del
crecimiento julio-agosto, un contraste positivo que puede ser pertinente.

Estos números son referencias para evaluar este fixture, no reglas, textos ni
respuestas que deban insertarse en prompts del producto. El agente recibe fuentes
y objetivo, no el oráculo ni un encargo diseñado para forzar la conclusión.

## 5. De señal a prioridad y reacción concreta

Diseñar un contrato versionado de orientación para decidir, integrado en el
encargo final del planificador, la síntesis y el borrador. Reutilizar campos
existentes donde basten; introducir estructura cuando una cadena `next_step`
no permita comprobar referencias, cobertura y decisiones condicionales. Definir
el esquema exacto en 3.9.1, con compatibilidad para registros antiguos.

Para una prioridad de descubrimiento, debe poder expresar:

| Contenido | Exigencia |
|---|---|
| Señal y alcance | Qué ocurre, en qué segmento/periodo y con qué referencias vigentes. |
| Importancia relativa | Magnitud, componentes y motivo para empezar ahí frente a alternativas. |
| Estado de conocimiento | Qué es calculado, confirmado por el propietario o hipotético. |
| Próxima comprobación | Dato o actuación específica que falta; dónde y en qué periodo comprobarla. |
| Utilidad de comprobar | Qué interpretaciones discrimina y qué resultado cambiaría el siguiente paso. |
| Reacción condicional | Qué revisar/corregir si se confirma cada condición relevante, o por qué aún no puede decidirse. |

No exigir un árbol exhaustivo de hipótesis ni rellenar casillas con acciones
inventadas. Cuando los datos permiten una acción respaldada, expresarla; cuando
falta evidencia, dar una comprobación proporcionada, sin prometer mejoras.
La presencia estructural de esos campos no acredita su calidad semántica.

En Bruma, una respuesta útil localizaría la caída de agosto y sus componentes,
y distinguiría, por ejemplo: completar registros si se acredita una omisión;
revisar disponibilidad/reposición si se documenta falta de producto; investigar
actividad del canal si registros y condiciones son comparables. Una coincidencia
o un desglose no demuestra que alguna de esas condiciones ocurriera. Tres meses
no prueban una pauta estacional recurrente.

Preguntar solo por información no disponible cuyo conocimiento pueda cambiar
la interpretación o decisión. Explicar el motivo y usar las preguntas persistentes
existentes; no convertir el onboarding en una entrevista extensa ni repetir dudas
desconocidas. Si el cliente no sabe, conservar una entrega útil y sus límites.

## 6. Libertad de presentación y capacidades reales

El analista elige representaciones según la pregunta, los datos y el mensaje que
quiere comunicar. El revisor evalúa esa elección. Líneas para evolución, barras
para componentes y tablas para cifras exactas son orientaciones, no asignaciones
obligatorias por código. Una representación válida alternativa no es un reparo
material por discrepar de una preferencia editorial.

Capacidades mínimas de esta entrega:

- Líneas temporales simples y con varias series, al menos diarias y mensuales,
  con una definición extensible de otros periodos ordenados. No fingir que una
  cantidad mensual es la observación de un día para eludir un contrato diario.
- Barras simples y agrupadas para niveles y cambios firmados, y tablas legibles
  de varias series/categorías. Conservar las tarjetas de cifras cuando sean útiles.
- Elección de escala, orden y selección explícitos y revisables, con criterios
  de honestidad visual; evitar suavizados que sugieran observaciones inexistentes.
- Vistas focales de una señal con acceso al detalle más amplio cuando aporte valor.
  Top-N/filtros deben declarar selección, cobertura y conciliación pertinente.

Publicar las capacidades reales en el contrato/contexto del modelo. No entregar
tipos que el frontend o la exportación no puedan representar. Otros tipos, como
dispersión o mapas de calor, quedan como extensiones evaluables; un caso que los
necesite debe registrar la limitación y ofrecer una alternativa honesta. La
autonomía se expresa en la estrategia y composición, no en exigir todos los tipos
de gráfico ni en permitir HTML/JavaScript arbitrario generado por el agente.

El código valida procedencia, finitud, unidad, fechas/periodos, orden, coordenadas
y correspondencia de puntos/series. Las cantidades y variaciones derivadas se
calculan y guardan con evidencia; el navegador resuelve, formatea y selecciona,
sin crear una nueva conclusión numérica al interactuar. Distinguir nivel absoluto,
cambio y porcentaje; no mezclar medidas incompatibles en un eje sin una definición
explícita y revisión adecuada. Ausencia no significa cero: preservar huecos y
no conectar intervalos ausentes como observaciones continuas.

### Interacción y primera lectura

En web: tooltip compartido por periodo con valores exactos y variaciones guardadas,
resaltado/activación de series, selección de puntos vinculada al hallazgo y acceso
al desglose del mismo periodo. Soportar teclado, foco, táctil y una tabla accesible;
mantener colores y unidades consistentes. Recargar o abrir el informe no calcula
de nuevo ni modifica el análisis aprobado.

La prioridad, su magnitud y la próxima comprobación deben poder leerse sin abrir
todas las secciones. Reservar método y detalle exhaustivo para desplegables.
Mostrar límites materiales junto a la conclusión que restringen, sin saturar
la primera lectura con explicaciones internas.

En HTML/PDF: representación estática legible, leyenda, periodo, valores y evidencia
equivalentes. No depender de hover o de series ocultables para comunicar la
conclusión esencial. Interactividad es una capacidad de la web; el PDF conserva
el contenido y la selección aprobados con todos sus límites relevantes.

Para Bruma: comparar total mensual mediante una línea es una opción válida; una
vista temporal por canal muestra el contraste 599→621→528 de tienda frente al
crecimiento digital. Las barras de contribuciones responden a otra pregunta y
pueden conservarse como detalle. No cambiar solo `kind` en la serie de cambios
para presentarla como nivel de ventas, ni reescribir silenciosamente el informe
histórico: una entrega modificada requiere su revisión correspondiente.

## 7. Semántica de medidas y revisión de utilidad

Separar por medida y fuente moneda, unidad, grano, base por fila/unidad, definición
y estado de confirmación. Registrar procedencia de la incertidumbre; no propagar
la respuesta sobre ventas automáticamente al marketing. Una etiqueta del archivo
puede ser una definición propuesta con sus límites, no una confirmación del dueño.

Para corregir una unidad o selección, producir una nueva serie o representación
trazable cuando sea necesario; conservar resultados anteriores y invalidar solo
dependencias afectadas. Una corrección no debe hacer desaparecer un entregable
obligatorio sin una alternativa legible o una limitación real de evidencia.

Relacionar cada pregunta/componente confirmado del propietario con las
investigaciones y hallazgos entregados. Conservar `question_coverage` técnico
para investigaciones y añadir la cobertura del encargo del propietario cuando
sea necesaria. No presentar el número de ramas internas como el número de
preguntas del cliente satisfechas. Mantener estados completo, parcial, no
disponible y seguimiento aplazado con explicaciones y evidencias adecuadas.

El revisor debe pedir corrección ante una omisión material calculable, un desglose
que no localiza la señal, una prioridad sin comparación suficiente, una acción
sin apoyo o una comprobación genérica que no responde al objetivo. No basta que
exista un gráfico, una referencia o una declaración del propio analista. Revisar
la entrega actual después de cada cambio; el visto bueno del planificador no
sustituye esa evaluación ni los controles independientes.

## 8. Puntos de implementación inspeccionados

| Área | Punto de entrada actual y trabajo esperado |
|---|---|
| Criterios y dirección | `agent/goal_quality.py`, `agent/business_planner.py`: autonomía, prioridad, contexto y orientación de entrega versionados. |
| Investigación y síntesis | `agent/research_contract.py`, `research_agenda.py`, `research_graph.py`, `parallel_research.py`: seguimientos vinculados a señales, periodo y resultados; recuperación. |
| Redacción y revisión | `agent/review_contract.py`, `review_prompts.py`, `review_policy.py`, `review_context.py`, `agent/model.py`: entrega, cobertura, capacidades de gráficos, esquema dinámico y huella. |
| Evidencia y representación | `series.py`, `chart_layout.py`, `client_report.py`, `web/dashboard.py`: periodos/series/coordenadas, referencias, HTML y datos compartidos. |
| Interfaz | `frontend/src/lib/charts.ts`, `types.ts`, `components/workspace/report.tsx`, `report-chart-tooltip.tsx` y consumidores en inicio/chat: líneas múltiples, tablas, interacción y primera lectura coherentes. |
| Evaluación | `evaluation/quality_runner.py`, `business_planner_runner.py` y evaluador existente: comparar versión base/nueva, fuentes equivalentes y utilidad contra el encargo. |

Las rutas Python de la tabla son relativas a `decision_room/`. Confirmar firmas,
versiones de prompts, esquema/migraciones, consumidores y tests antes de editar;
el plan no sustituye el diagnóstico del checkout real. Evitar ampliar límites
por inercia. Corregir alias/referencias repetidamente inválidos dentro de los
incrementos afectados, con pruebas de recuperación. No convertir 3.9 en un
rediseño general del monitor ni una optimización de coste a costa de utilidad.

## 9. Secuencia de implementación y criterios de cierre

Cada incremento se comprueba, revisa y guarda en un commit local según `AGENTS.md`.
Documentar cambios, validación y límites. No hacer push sin petición explícita.
El estado de cada incremento se registra en la lista inferior:

| Paso | Trabajo | Evidencia necesaria para cerrarlo |
|---|---|---|
| 3.9.1 | Especificar y versionar autonomía, orientación para decidir, cobertura del encargo y capacidades de presentación. | Contratos/políticas integrados con roles existentes; compatibilidad histórica; checks que distinguen elección legítima de evidencia inválida. |
| 3.9.2 | Profundización adaptativa en segmento/periodo relevantes y síntesis orientada a prioridad. | Seguimientos autónomos con origen verificable; cálculos y reconciliación; freno a duplicación; conservación de alcance, contexto desconocido y decisiones entre roles. |
| 3.9.3 | Entrega y revisión de prioridades, comprobaciones y reacciones condicionales. | Un caso con datos suficientes, otro con contexto faltante y otro parcial; el revisor rechaza una recomendación inventada y una respuesta calculable omitida; cobertura del propietario correcta. |
| 3.9.4 | Representaciones flexibles y coherentes en evidencia, contratos y exportación. | Líneas diarias/mensuales simples y múltiples, barras agrupadas y tablas; periodos/huecos/unidades validados; mismos valores y selección en API, HTML y PDF; alternativas válidas aceptadas. |
| 3.9.5 | Interacción y primera lectura en informe, inicio y chat. | Tooltip exacto, control de series, navegación del punto al hallazgo/desglose, teclado/táctil, móvil y temas; prioridad/comprobación visibles; lectura y recarga sin nuevas llamadas/cálculos. |
| 3.9.6 | Pruebas integradas/adversariales y recuperación antes de evaluar con proveedor. | Aislamiento, evidencia obsoleta, errores y reparación, no repetición, revisiones y regresiones de exportación/cobertura; controles automatizados apropiados y revisión visual. |
| 3.9.7 | Comparación controlada y prueba conjunta final. | Lotes conservados base/nuevo con Bruma y WWI, aceptación independiente, recursos/fallos y respuestas desconocidas; usuario puede reconocer prioridad y próximo paso; resultados y límites documentados. |

- [x] 3.9.1 — Contratos y criterios.
- [ ] 3.9.2 — Investigación y síntesis.
- [ ] 3.9.3 — Entrega y revisión de utilidad.
- [ ] 3.9.4 — Evidencia y representaciones.
- [ ] 3.9.5 — Interacción y primera lectura.
- [ ] 3.9.6 — Integración y recuperación.
- [ ] 3.9.7 — Evaluación comparativa y prueba conjunta.

Secuencia recomendada: completar 3.9.1 antes de modificar esquemas de producción;
después 3.9.2–3.9.3 y 3.9.4–3.9.5, con verificación de cada incremento. Cerrar
3.9.6 antes de la matriz de 3.9.7. Un fallo conocido dentro del alcance se corrige
y registra, sin declarar completado el incremento mientras falte su comprobación.

## 10. Evaluación, regresiones y aceptación

Conservar la prueba manual como diagnóstico histórico. La comparación controlada
ejecuta base y nueva versión desde copias congeladas y entornos aislados, con
mismos archivos, objetivo, contexto, modelo, razonamiento y presupuestos. Registrar
las diferencias necesarias de contrato/código. Los oráculos independientes no
entran en el contexto de los agentes. No comparar el mejor informe nuevo solo
con el peor anterior ni reintentar en secreto hasta obtener una entrega favorable.

Matriz mínima: Bruma-evolución/prioridad, WWI-descubrir y WWI-organizar; dos
repeticiones de cada caso en cada versión: 12 intentos. Alternar el orden de
versiones, conservar todos los intentos y medir por pareja comparable. La
respuesta desconocida sobre la base monetaria forma parte de Bruma; contexto
operativo no suministrado recibe «no lo sé», sin instrucciones sobre qué hallazgo
buscar. Añadir pruebas controladas de entrega parcial y recuperación, sin
mezclarlas con el denominador de esa matriz. Una interrupción y su reanudación
son el mismo intento identificado, no una sustitución de un fallo.

Usar el instrumento de 3.6/3.7 con rúbrica ampliada y vinculada al hash final:

- Exactitud exhaustiva de valores/referencias, definiciones y conciliaciones.
- Cobertura del encargo confirmado, separada de la de investigaciones internas.
- Profundidad que añade información útil en el segmento y periodo de la señal.
- Prioridad relativa explicada y comprobación/reacción concreta y proporcionada.
- Claridad de visuales, selección, huecos, escala y primera lectura.
- Separación entre observación, hipótesis y hecho confirmado; ausencia de causas,
  predicciones o beneficios inventados.
- Recuperación, preguntas necesarias/no repetidas, llamadas, intentos fallidos,
  tiempos y tokens conocidos/desconocidos. Coste solo con uso y tarifas suficientes.

Permitir entregas y representaciones alternativas correctas: la rúbrica no exige
un gráfico de líneas ni repetir literalmente la solución ilustrativa de Bruma.
Una entrega parcial útil se evalúa como parcial; nunca cuenta como cobertura total.
Comparar los mismos informes en ambas versiones con el mismo evaluador actualizado,
conservar evaluación original cuando exista y documentar modificaciones de rúbrica.

Pruebas deliberadas: falso porcentaje de contribución; periodo incorrecto en el
desglose; línea con categorías sin orden temporal; mensual disfrazado de diario;
serie ausente convertida en cero; moneda o base propagada de otra medida; acción
causal no respaldada; entregable retirado al corregir; cobertura inflada contando
ramas; aprobación obsoleta; replay que duplica cálculos. El evaluador debe detectar
esas regresiones, además del comportamiento del producto.

El cierre funcional exige los siete incrementos y ausencia de errores materiales
en los casos de aceptación. La mejora de utilidad requiere evidencia comparativa
independiente en ambos negocios, sin pérdida de cobertura en organización y con
los fallos dentro del denominador. Documentar resultados por caso y desacuerdos;
si no se demuestra mejora, declarar la capacidad implementada/evaluada y mantener
abierta la aceptación de calidad. Doce intentos orientan decisiones, no demuestran
generalización ni significación estadística.

## 11. Alcance posterior: contexto web, propuesta 3.95

La búsqueda web queda fuera de 3.9. El [plan general](../product/Decision%20Room%20-%20Plan%20de%20implementacion.md)
ya contempla contexto externo. 3.95 es la propuesta de continuidad discutida,
pendiente de un plan específico: el planificador puede solicitar una consulta
concreta y el analista proponerla, indicando lugar, fechas, hecho buscado y qué
interpretación podría cambiar. No requiere crear otro agente desde el inicio.

Por ejemplo, vacaciones, festivos o eventos podrían sugerir una hipótesis sobre
la actividad de un barrio, pero una fuente general no confirma la causa de la
caída de un negocio. Conservar fuentes/ámbito/periodo y evaluar el mismo caso con
y sin contexto externo antes de ampliar. 3.9 trabaja con archivos y contexto
aportado por el propietario; no habilita Internet en el sandbox de Python.

## 12. Registro de continuidad

- 30 de septiembre de 2026: plan redactado tras la prueba conjunta y auditoría
  manual; base `5af6cb7`. Documentación integrada en los planes de producto.
- Implementación pendiente; no se han cambiado contratos, agentes, gráficos,
  base de datos o informes aprobados al crear este documento.
- Al continuar, confirmar checkout/estado de Git y entorno aislado de esta rama.
  Guardar artefactos y credenciales localmente; no copiar rutas personales,
  uploads o snapshots privados a documentación pública.
- Registrar aquí el incremento activo, commits reales, pruebas realizadas,
  fallos, decisiones y ubicación relativa de evidencias locales. Publicar solo
  resultados/atribución reproducibles aptos para el repositorio.

### 3.9.1 — Contratos y criterios implementados

- Contrato `delivery-quality-v1`: orientación vinculada a evidencia, alcance,
  prioridad relativa, comprobación y reacciones condicionales; cobertura del
  propietario separada de investigaciones, con estados completo/parcial/no
  disponible/aplazado. Borradores históricos mantienen versión 1; versión 2
  disponible para activar en 3.9.3, sin reescribir aprobaciones anteriores.
- Planificador y roles de investigación/revisión comparten la política de
  autonomía; capacidades reales publicadas en el contexto de entrega.
- Validación: 5 pruebas nuevas de cobertura, referencias y compatibilidad;
  4 de revisión numérica y 2 de contexto existentes pasan; 36 pruebas de
  esquemas, referencias, acciones y endurecimiento pasan en PostgreSQL/Docker
  aislados. Una ejecución inicial sin el lanzador no encontró el socket correcto;
  se repitió con la configuración independiente, sin tocar la base de otro checkout.
- Los campos estructurales no acreditan utilidad semántica. Profundización,
  activación de revisión, representaciones e interacción siguen pendientes.
