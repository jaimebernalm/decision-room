# Paso 3.6 — Protocolo de calidad, utilidad y rendimiento

## Decisiones tras 3.5

La aprobación del producto no implica aceptación del evaluador. La evaluación
incluye fallos y limitaciones; no exige fabricar una mejora del paralelismo.
Conservar las referencias históricas de 3.1 y Bruma 3.4.1/3.5. La comparación
histórica es descriptiva: modelos, presupuestos y código han cambiado.

1. Adaptar selección, profundidad y revisión a la intención expresada, incluida
   intención libre o mixta. Organización necesita cobertura ordenada; descubrimiento
   requiere priorización, desglose de una señal material y próximas comprobaciones;
   una pregunta concreta necesita respuesta directa. Predicciones siguen fuera del
   producto: explicitar el límite y ofrecer análisis histórico si está autorizado.
2. Matriz real: WWI con organizar/descubrir/pregunta concreta y Bruma con descubrir;
   dos repeticiones por caso en modo serial y paralelo: 16 recorridos. Mismos CSV,
   definiciones, modelo y presupuestos. Alternar orden de modos. El modo serial
   conserva coordinador y encargos, pero usa un solo trabajador simultáneo. Las
   decisiones del modelo pueden variar: esto compara el producto completo, no
   demuestra aisladamente la aceleración del planificador.
3. Congelar fuentes, código y configuración antes del lote. Base de datos y
   almacenamiento aislados; respuestas del propietario limitadas a definiciones
   escritas. Oráculos CSV/Decimal separados del contexto del modelo. Registrar
   todos los estados, recursos, borradores, errores y resultados aprobados.
4. Evaluación independiente vinculada al hash de la entrega: referencias numéricas
   explícitas y exhaustivas para cifras citadas/visuales, revisión semántica de
   etiquetas, unidades, selección, narrativa, redondeo, cobertura y utilidad. No
   aprobar por coincidencia de números sueltos ni por acuerdo entre agentes.
5. Comparar por caso y repetición: aprobación, aceptación independiente, profundidad,
   utilidad, duplicación, comparabilidad, tiempo hasta resultado terminal, llamadas,
   fallos, tokens conocidos/desconocidos y coste solo con tarifas suministradas.
   Los fallos forman parte del denominador. Latencia de éxitos y de todos los
   intentos se presentan por separado. Uso incompleto implica coste desconocido.
6. Pruebas controladas: informe parcial, desacuerdos, caída y recuperación, cuotas,
   ausencia de predicciones inventadas, evaluaciones incompletas/obsoletas,
   cobertura numérica incompleta y comparación sin datos suficientes.

## Gates y límites

El evaluador debe detectar las regresiones introducidas deliberadamente. Solo se
acepta una entrega sin errores materiales y con cobertura útil para su intención.
Una entrega parcial puede aceptarse si responde una parte útil y declara exactamente
lo no resuelto; nunca puntúa como cobertura completa. Mantener todos los intentos;
una corrección posterior necesita otro lote y no sustituye los resultados iniciales.

La comparación de fechas observadas no prueba apertura ni cobertura completa.
Cuando cambia la exposición, medir tasas sobre esa exposición antes de interpretar
crecimiento/caída de rendimiento; mostrar totales si son lo pedido. Una muestra de
16 recorridos orienta prioridades, no demuestra generalización ni significación.
La matriz parte de contexto de propietario equivalente al alcance aceptado del
onboarding; su interacción se comprueba por pruebas de integración separadas.

## Entregables

- Política común de calidad por intención para planificador, analista y revisor.
- Ejecutor reproducible, oráculos, evaluación independiente y comparación de modos.
- Pruebas adversariales del evaluador y controles integrados del producto.
- Registro de resultados reales, comparación histórica y decisión documentada
  sobre paralelismo. El cierre distingue capacidad evaluada de calidad alcanzada.

## Controles añadidos durante la preparación

Antes de cualquier llamada pagada, el ejecutor comprueba una importación mínima y
una consulta dentro del Docker real. Una copia congelada del código debe conservar
el montaje local autorizado de `sandbox-inputs`; un directorio arbitrario puede
no estar compartido con la máquina virtual. El resultado del preflight queda
separado de las cifras del negocio y del tiempo del informe.

Las primeras trazas justificaron dos correcciones de contrato: el esquema de
planificación solo permite interpretar tablas/columnas inspeccionadas, y el de
síntesis solo permite referenciar candidatos guardados, no trabajos bloqueados o
descartados. Se mantienen las validaciones posteriores: restringir la generación
no convierte una interpretación del modelo en evidencia verificada.

El primer recorrido del entorno válido encontró que una ampliación podía ocultar
un cálculo correcto si el siguiente fallaba. La corrección posterior obliga a
registrar el resultado acotado como candidato pendiente de revisión antes de
ampliarlo; un resultado omitido por tamaño aún puede regenerarse de forma más
pequeña. Un resultado demostrado inútil puede bloquearse con su motivo. La
corrección se prueba aparte de la matriz congelada, conservando el fallo original.

## Entrega parcial y preservación de evidencia

La política de revisión 3 distingue `unavailable` (limitación de evidencia) de
`deferred` (seguimiento secundario que este informe no entrega). Solo una pregunta
creada como seguimiento puede aplazarse, con explicación y sin enlaces a
conclusiones que aparenten responderla. El revisor puede rechazar ese aplazamiento;
para aprobar debe justificar que el objetivo original conserva una respuesta útil.
Una validación necesaria o un resultado central solicitado siguen bloqueando.
Las versiones históricas conservan su política y no se vuelven a aprobar por cambiar
el código. La web y la exportación identifican expresamente una entrega parcial.

## Ejecución y revisión independiente

Con PostgreSQL, Docker y proveedor configurados mediante las variables habituales:

```sh
python -m decision_room.evaluation.quality_runner run outputs/quality-36 \
  --wwi data/wide-world-importers/exports/csv \
  --bruma /ruta/a/los/csv-sinteticos --repeats 2
python -m decision_room.evaluation.quality_runner summary outputs/quality-36
```

El lote debe ejecutarse desde una copia congelada: cambiar fuentes o archivos
invalida la comparabilidad. Un archivo `STOP` detiene antes del siguiente recorrido;
no elimina estados ni reintenta un intento fallido. Antes de reanudar un proceso
interrumpido, inspeccionar sus identificadores y llamadas inciertas. Para probar una
corrección, crear otro directorio de lote. Los datos grandes y artefactos permanecen
locales; las rutas de ejemplo no son archivos distribuidos en el repositorio.

Cada directorio conserva `state.json`, plan, investigación, revisión, recursos y,
si existe, exportación. La revisión independiente añade `assessment.json` con el
hash del informe, notas, rúbrica y mapeos de todas las referencias de la entrega.
`summary` nunca completa esa evaluación con otro modelo ni acepta automáticamente
la decisión del revisor. El HTML permite abrir las evidencias; el JSON conserva los
controles, parejas comparables y medidas. Se requiere leer la prosa, las etiquetas y
los límites además de verificar las referencias numéricas.

La matriz encontró además omisiones de métricas solicitadas en entregas de
organización. La política común posterior exige comprobar medidas × desgloses ×
periodos antes de repartir las vistas disponibles. Un resumen correcto de solo
algunas medidas no pasa la aceptación de organización completa. Esta corrección
se valida en otro lote con ambos modos y no mejora retroactivamente sus puntuaciones.


## Decisión tras la ejecución

La [validación final](../validation/2026-09-27-quality-evaluation.md) conserva la
matriz inicial, los lotes correctivos y las recuperaciones por separado. La
implementación del protocolo queda cerrada; sus resultados no satisfacen todavía
la aceptación general del producto ni prueban ventaja global del paralelismo.
Los cambios de contrato encontrados se incorporan con pruebas específicas, sin
reemplazar fallos por reintentos exitosos. El siguiente trabajo debe cerrar los
fallos medidos de profundidad/cobertura y volver a usar este mismo instrumento.
