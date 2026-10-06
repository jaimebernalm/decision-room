# Contraste del plan de ensayos con la investigación 3.9.10

Fecha: 3 de octubre de 2026. Revisión documental, sin cambios de producto ni
llamadas de modelo. Se ha leído el plan `report-quality-autopsy-and-trials.md`
y las partes del generador/lanzador que definen oráculos, aislamiento y evaluación
en `claude/report-quality-trials`, commit `af40d99`. No es una auditoría completa
del lanzador. Referencia propia congelada antes de leer Albor:
[diagnóstico 3.9.10](2026-10-03-report-quality-forensics.md), commit `8a2e66f`.

## Acuerdo central

Separar las reparaciones técnicas de los cambios de comportamiento es correcto.
También lo son conservar intentos fallidos, evaluar fidelidad entre cálculo y
relato, distinguir ranking de prioridad, aislar temporales y contrastar otro
negocio. El coste de formular y registrar cada consulta merece una hipótesis
propia, distinta de la continuidad dentro de una investigación.

No se propone adaptar el producto a las seis señales de Albor. Las propuestas de
`8a2e66f` permanecen como referencia previa. Los ajustes siguientes afectan al
protocolo experimental y a la distinción entre explorar y verificar, no añaden
reglas específicas sobre productos, canales, fechas o anomalías de Albor.

## 1. Tercer negocio reservado

De acuerdo con diseñarlo de forma independiente, pero **no utilizarlo como otro
conjunto de desarrollo en todas las fases**. Si sus resultados se inspeccionan
para decidir el siguiente cambio, deja de ser una prueba reservada aunque el
oráculo no se comparta. Hasta una puntuación agregada repetida permite ajustar
indirectamente al conjunto.

Protocolo recomendado:

1. Acordar y congelar previamente el alcance de tareas, tipos de archivos,
   recursos y rúbrica. Las entradas deben permitir responder sin conocer el
   generador; no convertir la reserva en una prueba deliberadamente imposible.
2. Diseñar otro tipo de negocio con estructura y objetivo distintos, sin publicar
   sus señales. Congelar generador, semilla, CSV, prompt y oráculo mediante huellas.
   El objetivo es generalización, no derrotar a una variante concreta.
3. Mantener el oráculo y el generador fuera del entorno legible por los agentes.
   El lanzador copia oráculos a `BATCH/oracles`: separación de carpetas no prueba
   por sí sola que las herramientas de ejecución no puedan leerlos. Hay que
   verificar esa frontera. Lo mismo vale para el código público de un generador
   cuyas constantes revelen las señales.
4. Usar Bruma y Albor para desarrollar; ejecutar el reservado después de congelar
   candidatos, criterios y evaluadores. No comunicar resultados intermedios a
   quienes ajustan la implementación.
5. Puntuar la reserva una vez. Si se usa para corregir el producto después, pasa
   a ser desarrollo y será necesario otro conjunto reservado para validar.

El oráculo debe distinguir **verdad del generador**, **conclusiones inferibles de
las fuentes entregadas** y **decisiones razonables para el encargo**. Una causa
plantada no se vuelve demostrable para el agente si no hay datos que la
identifiquen. Varias prioridades pueden estar bien justificadas: no evaluar
imitación de una única lista de hallazgos esperada.

El autor de este diagnóstico conocería el caso si lo diseña; por ello no debería
usar ese conocimiento para ajustar luego sus propuestas ni ser el único juez
de su utilidad. Los cálculos del oráculo deben verificarse desde CSV por una ruta
independiente del generador; la puntuación subjetiva requiere otra mirada.

Estado: propuesta aceptada como diseño del experimento; **el tercer negocio no
se ha generado en esta revisión** y no se revelan señales ni oráculo.

## 2. Continuidad y exploración barata son hipótesis distintas

La propuesta B original reduce los traspasos para seguir una señal. No resuelve
por sí sola el coste de preparar un resultado formal antes de saber qué merece
atención. La distinción propuesta por Opus es útil.

Permitiría una acción exploratoria: ejecutar una consulta Python/SQL y obtener
una tabla, resumen o salida acotada sin fabricar un hallazgo ni completar el
contrato de métricas del informe. Esa salida puede orientar el siguiente cálculo.
Para publicar una cifra o apoyar una conclusión, la evidencia debe promoverse
al contrato verificable y quedar vinculada a la entrega.

**Provisional no significa invisible ni sin registro.** Guardar consulta, fuentes,
huellas, resultado, error, truncado y uso de recursos. Mostrar al modelo si mira
una muestra, un resultado truncado o un cálculo completo. Los límites de tiempo,
contexto y ejecuciones siguen contando; abaratar el trámite no elimina el coste
real de la consulta ni abre un recorrido infinito.

Evitar dejar todo el registro para un único programa al final: podría perderse
qué consulta apoyó una conclusión o cambiar silenciosamente una fórmula al
recalcular. Promover evidencia durante la investigación cuando se vuelve
material, conservar el historial y comprobar al final las cifras publicadas.
La promoción puede reutilizar una consulta determinista y sus fuentes congeladas;
no debe exigir volver a transcribir manualmente todos los valores.

Comparación mínima para separar efectos:

| Variante | Cambio respecto a contratos reparados |
| --- | --- |
| Control | Recorrido actual con reparaciones técnicas. |
| Continuidad | Permite continuar la investigación conservando evidencia. |
| Continuidad + exploración | Añade consulta provisional sin registro de candidato. |

La tercera variante mide el efecto adicional de explorar barato **dada** la
continuidad. No identifica el efecto aislado de exploración sin continuidad;
un diseño de cuatro combinaciones serviría si después interesa esa interacción.
Separar de estas variantes la reescritura de prompts, el esfuerzo del modelo y
la distribución de roles, para no atribuir todo el cambio a la herramienta.

## 3. Panorama determinista: útil, pero orienta la atención

Un panorama precalculado puede hacer accesible evidencia que ahora exige varias
consultas. Ser determinista no lo hace neutral: elegir dimensiones, ventanas,
contrastes, umbrales y orden ya dirige la atención. Puede ayudar a encontrar
patrones y también anclar al agente en lo que ese panorama sabe mostrar.

De acuerdo con medirlo como brazo separado sobre la misma base. Debe indicar
qué cubre, qué omite, unidades, denominadores y cobertura; permitir cálculos fuera
de ese inventario y no presentarse como lista completa de hallazgos. No calcular
por defecto sumas de importes cuyo significado no esté definido.

Medir no solo detección de señales incluidas en el panorama: también falsos
positivos, señales útiles fuera de él, cálculos posteriores, prioridad para el
objetivo y coste total, incluido el cálculo previo. Que un agente mencione más
anomalías no significa que ayude a decidir mejor.

La propuesta P2 de bloquear por todo movimiento grande de signo contrario sería
demasiado mecánica. Una alternativa relevante merece examen; puede descartarse
si el objetivo, cobertura o evidencia lo justifican. El revisor debe poder
contrastar, preguntar y calcular, no imponer un catálogo de anomalías.

También debe distinguirse independencia de roles de independencia de evidencia:
si investigador y revisor dependen del mismo panorama, pueden compartir sus
omisiones. El oráculo independiente y comprobaciones fuera del panorama siguen
siendo necesarios para evaluar esa variante.

## 4. Orden de fases y controles

Mantendría reparaciones de contrato primero. Después separaría continuidad,
exploración provisional y crítica de utilidad. La fase 2 del plan combina
recorrido con revisión: es válida como paquete de producto, pero no permite
atribuir la mejora a uno u otro. Además, P2 se define contra el panorama P1, que
no aparece hasta la fase 2b. Resolver esa dependencia explícitamente: crítica
independiente antes del panorama o P2 solo en el brazo que dispone de P1.

Secuencia recomendada: contratos → continuidad → exploración adicional → revisión
con comprobaciones propias → panorama como variante de esa misma base → síntesis
y presentación. Consolidación de prompts, continuidad del protocolo y esfuerzo
de razonamiento quedan como variantes posteriores. Implementar cambios detrás de
opciones separables permite comparar sin reconstruir todo entre ensayos.

Sobre controles Luna, la propuesta de 3 al principio, 1 durante cada fase y 3 al
final es razonable para contener coste, con estas precisiones:

- **Desarrollo:** tres por conjunto al establecer la línea base; un control
  contemporáneo por conjunto en hitos intermedios. Un solo control es una alarma
  de funcionamiento o cambios del entorno, no una estimación de calidad estable.
- **Cambios importantes:** comparar también contra el producto de referencia
  congelado. Luna sola no controla cambios propios del proveedor API o del entorno
  de ejecución del producto. Intercalar o balancear el orden de los brazos.
- **Decisiones dudosas:** ampliar antes de elegir ganador; conservar dispersiones
  y fallos, no solo medias. No seleccionar la mejor de tres como rendimiento.
- **Cierre:** tres por sistema y conjunto para el candidato final. En el reservado,
  incluir tres del producto con contratos reparados, tres del candidato final y
  tres de Luna: nueve ejecuciones para comparar mejora y referencia externa sin
  abrir sucesivamente el caso durante desarrollo.

Tres repeticiones son un piloto, no una garantía de consistencia. Los tests
reproducibles de contratos deben filtrar primero los defectos deterministas;
no hace falta pagar varias generaciones para demostrar de nuevo un esquema inválido.

## 5. Precisiones al diagnóstico y a la evaluación

1. **La tienda no estaba totalmente fuera del contexto del decisor.** Sus cinco
   caídas podían recuperarse de los 18 cambios visibles al cierre. Faltaba el
   agregado listo para usar y no se eligió calcularlo o priorizarlo. Esto refuerza
   el coste de mirar; matiza «quien decide no ve los números».
2. **−93 podía incorporarse con trabajo adicional.** El redactor tenía herramienta
   Python y seis ejecuciones disponibles. No estaba condenado a omitirlo porque
   aún no existiera como métrica. El contrato eleva la fricción, no demuestra una
   imposibilidad de incluir esa conclusión.
3. **El fallo también llega a redacción y revisión.** El investigador cerró pronto,
   pero ambos papeles posteriores pudieron recuperar la señal. La frase «la
   pérdida ocurre antes de redactar» localiza el inicio, no exonera el resto.
4. **Siete decisiones de ejecutar no son siete ejecuciones.** En la rama HTML
   hubo seis ejecuciones efectivas; el siguiente intento encontró el límite.
5. **Tokens comparables no implican trabajo ni coste equivalentes.** Buena parte
   de la entrada de Luna se declara cacheada; los sistemas y transportes difieren.
   El tamaño del encargo del dueño no representa todo el prompt efectivo del CLI.
6. **El oráculo actual tiene `priority_rank` fijo.** Evaluar por defecto coincidencia
   con ese orden contradiría separar ranking y utilidad. Registrar prioridad
   esperada como hipótesis y aceptar órdenes alternativos justificados por el
   objetivo. Igual con las causas: ausencia de registros no acredita por sí sola
   un fallo de extracción ni una caída de demanda.
7. **Evaluación ciega del contenido y de la interfaz son distintas.** `blind()`
   produce texto sin marca, útil para algunas preguntas pero insuficiente para
   gráficos e interacción. Evaluar el informe completo aparte, ocultando autoría
   en lo posible y reconociendo que el estilo puede revelar el sistema. Medir
   comprensión también dentro de la presentación real.
8. **Criterio de éxito general.** La regla de mejorar S1/S2 en dos de tres Albor
   puede ser una prueba de desarrollo, pero no la aceptación general. Exigir
   también fidelidad, falsa alarma, utilidad del siguiente paso y resultado del
   negocio reservado. Detectar el patrón diseñado para P1 no valida generalización.

## Resultado de esta revisión

Acuerdo en las reparaciones y en ampliar las pruebas. Incorporaría exploración
provisional como variante propia y conservaría el panorama como experimento.
Cambiaría cuándo se abre el reservado y separaría intervenciones para aprender
qué mejora el producto. Ninguna propuesta específica se ajusta a los valores de
Albor. No se ha enviado un mensaje a otro chat ni iniciado ensayos en esta revisión.

## Adenda: cierre del protocolo tras `cf1a1d1`

Se ha leído la revisión del plan y comprobado el cálculo de ejecuciones. Esta
adenda responde a coste y reparto; no inicia implementación, creación de datos
reservados ni ensayos.

### Repeticiones y calendario

Se acepta una ejecución del producto candidato con Bruma en las fases
intermedias, manteniendo tres con Albor. Bruma conserva tres en línea base y
candidato final. Los controles intermedios de referencia y Luna ya eran de una
repetición por conjunto; no se reducen otra vez. Un único Bruma comprueba
regresiones evidentes y funcionamiento, no acredita mejora consistente.

Definir antes de ejecutar cuándo ampliar hasta tres: regresión frente a la
referencia, resultado de utilidad ambiguo o discrepancia material de fidelidad.
Una cifra incorrecta o un gráfico roto se investiga como fallo; no se diluye
repitiendo hasta obtener una entrega buena. Conservar todos los intentos. Si hay
que corregir código, identificar la nueva revisión como otro candidato.

Recuento de la tabla de `cf1a1d1`, suponiendo una sola variante opcional en fase 7:

| Alcance | Plan original | Bruma intermedio reducido | Desglose reducido |
| --- | ---: | ---: | --- |
| Fases 0–6 | 72 | 62 | 42 producto, 20 Luna |
| Fases 0–7, una variante opcional | 80 | 68 | 48 producto, 20 Luna |
| Reservado al final | 9 adicionales | 9 adicionales | 6 producto, 3 Luna |

No presupuestar por adelantado todas las variantes opcionales. Ejecutarlas solo
si el diagnóstico de las fases previas lo justifica. Los defectos deterministas
se comprueban con pruebas locales antes de generar informes.

El rango previo de 4–15 minutos por ejecución implica 2,8–10,5 horas para las
42 ejecuciones del producto en fases 0–6 reducidas. Falta sumar Luna, revisión,
implementación, esperas y el reservado; Albor puede tardar más. Por tanto,
«80 ejecuciones en serie» no demuestra por sí solo días de cómputo. El proyecto
completo sí puede ocupar varios días de trabajo. Medir Albor en la línea base
antes de convertir el rango de Bruma en un calendario comprometido.

### Reparto y alcance de contratos

De acuerdo con que Astra asuma fase 1 en una rama propia desde `4815b68`, con
nombre propuesto `codex/fix/report-quality-contracts`. Opus mantiene el lanzador
y ejecuta la línea base congelada en `4815b68`. Pueden trabajar simultáneamente
si cada proceso usa su instantánea y entorno aislados; no integrar cambios en
la referencia mientras se ejecuta la base.

Alcance de la entrega de contratos: esquema productor de capas coherente con
validación y render; comunicación de exportación y su estado; errores distintos
de artefactos y presupuestos; etiquetas distinguibles; captura del sistema,
esquema y correcciones efectivos con tratamiento de información privada; pruebas
apropiadas. Sin continuidad, exploración provisional, panorama ni cambios de
priorización en ese mismo lote.

El rango temporal incorrecto nació en código generado. No se dará por resuelto
editando aquel programa histórico o una frase de prompt: necesita una prueba de
invariancia y una solución verificable y general, cuyo alcance se documentará
por separado si excede las reparaciones de contrato. No se modifican entregas
antiguas para simular que el problema quedó corregido.

Entregar un commit exacto y sus comprobaciones para que el lanzador congele la
fase 1 como referencia. Esta adenda registra el acuerdo de reparto; la rama de
implementación todavía no se ha creado.

### Protección del reservado

La prueba comunicada demuestra lectura fuera del directorio de trabajo en esa
configuración; no demuestra acceso a cualquier archivo bajo toda configuración
y permiso del sistema. Es suficiente para descartar la separación de carpetas
como garantía del experimento. Marcar rutas en comandos es diagnóstico, no un
bloqueo ni una detección completa: hay rutas calculadas, enlaces y accesos desde
programas que no aparecen literalmente en el comando.

Al ejecutar el reservado se entregan solo sus entradas. Oráculo, generador y
claves deben seguir inaccesibles **durante todas las ejecuciones**, también las
finales; no descifrarlos a una ruta legible mientras Luna sigue trabajando. Se
abren después para puntuar. En Docker se verifica qué está montado; su aislamiento
es respecto a lo no montado, no ausencia de acceso a archivos.
