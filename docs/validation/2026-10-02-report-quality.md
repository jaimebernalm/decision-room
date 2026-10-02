# 3.9 — Encargo estable y cobertura de la entrega

Continuación de la [evaluación del 1 de octubre](2026-10-01-report-quality.md).
El fallo de entrada fue una ampliación interna del encargo: ocho rondas de revisión,
cifras correctas y una entrega que decía mostrar 18 combinaciones, pero contenía 12.
Los 25 intentos anteriores se conservan; los puestos reservados sin ejecución no
se cuentan como intentos ni fallos.

## Implementación y comprobaciones

- `1fb9e64`: política 5 para revisiones nuevas. La petición original y las
  aclaraciones reales son la autoridad; el brief es una interpretación. El
  entregable de referencia contiene el encargo completo y exige auditar todos
  sus componentes. Pasan 48 pruebas dirigidas de alcance, revisión y planificación.
- `f62496c`: objeciones clasificadas como obligación del propietario, integridad
  de la entrega o mejora opcional. Los bloqueos requieren procedencia comprobable;
  las mejoras opcionales no bloquean. Se permite aplazar honestamente una vista
  interna sin dar por cumplido un componente solicitado por el propietario.
- La selección de vistas declara el eje y grupos mostrados. El código cuenta la
  unión de identidades actuales y comprueba cualquier población de referencia.
  Rechaza 18 declarados/12 mostrados, vistas eliminadas, coordenadas inventadas y
  poblaciones obsoletas. Una selección focal honesta conserva su validez y las
  alternativas de líneas, barras y tablas permanecen disponibles.
- Manifiesto, aprobación y notas visibles vinculan la selección vigente. HTML y
  PDF preservan sus recuentos; una reanudación conserva borrador y huella. Los
  recuentos no interpretan prosa libre: el revisor contrasta títulos, conclusiones
  y cobertura con el manifiesto y juzga pertinencia respecto al objetivo.
- Pasan 53 pruebas dirigidas, la regresión completa de **547 pruebas Python**
  (331,321 s) y una prueba nueva de persistencia/reanudación. También pasan
  **117 pruebas web**, build y lint; build/lint conservan advertencias anteriores.
- Seis informes históricos conservan contenido, huella almacenada y estado de
  publicación frente a `9421aa1`, sin llamadas al modelo. Cinco siguen publicables;
  una referencia base antigua ya tenía una discrepancia de huella con esa versión.
  Este ajuste no reescribe ni restablece su aprobación. La galería conserva los
  snapshots originales, con su evaluación histórica.

## Recorrido real acotado

Se congela `f62496c` con fuentes, objetivos, modelo y presupuestos de la matriz
original. Usa otra base de datos y almacenamiento, sin modificar el entorno del
propietario ni enviarle el oráculo al modelo. Se lanza primero Bruma; los demás
puestos quedan reservados hasta su auditoría independiente. Si falla, conservar
el intento y resolver el defecto antes de ampliar ejecuciones pagadas.

### Primer piloto — `f62496c`

Bruma termina aprobado en **336,524 s y tres rondas**. Las **16 referencias**
numéricas y de nombres coinciden con CSV/Decimal y catálogos independientes.
Una línea focal y barras mensuales muestran dos selecciones de tres meses; solo
la vista total afirma exhaustividad respecto a su serie de referencia. No se
repite la declaración falsa de 18 combinaciones. Exportación y reanudación pasan
con la misma huella. Los bloqueos del revisor corrigen trazabilidad de identidades
y una cifra sin cita; no exigen un inventario opcional.

**No se acepta su utilidad de desarrollo.** El orden de prioridad se basa casi
solo en +188 frente a +171 y crecimiento mensual; no explica suficientemente qué
decisión justifica empezar ahí frente a una alternativa material. La comprobación
de captura es concreta, pero la rama posterior pide un «registro operativo
pertinente» sin nombrar evidencia, contraste y reacción diferenciada. Rúbrica 2:
prioridad, siguiente comprobación y respaldo de decisión reciben 1; cifras,
significados, cobertura y selección pasan. Un borrador aprobado no equivale a
una mejora de utilidad aceptada.

Recursos del piloto: **26 llamadas**, cinco ejecuciones (dos completas, dos
fallidas y una salida inválida), **771.021 tokens de entrada y 39.062 de salida**,
con uso completo para este intento. Los errores de ejecución y reparaciones se
conservan. No se estima coste monetario sin tarifas declaradas. Son **26 intentos
únicos acumulados**, incluyendo los 25 anteriores; las cinco reservas de este
lote siguen sin lanzar y no son intentos.

Se añade una instrucción compartida para planificador, investigación y revisión:
nombrar la evidencia operativa que falta, el contraste y cómo cada resultado cambia
la siguiente acción; la conciliación puede ser un primer filtro, sin convertirla
en toda la reacción comercial. Exigir juicio sobre el valor de la prioridad frente
a una alternativa, sin imponer un signo, método o inventario. Mantener parcial la
guía aún incompleta, en vez de aprobarla como completa por tener campos llenos.
El ajuste compartido se guarda en `646b35c`; pasan **62 pruebas dirigidas**.

### Segundo piloto — `646b35c`

Bruma aprueba en **830,263 s y cinco rondas**. Las **114 referencias** coinciden
con CSV/Decimal y un complemento independiente de fechas/medias semanales. Se
acepta como **entrega útil parcial de desarrollo**, con comprobación operativa
pendiente y claramente identificada; no como explicación causal completa.

- Separa volumen acumulado de cambio julio-agosto: +332 de Marketplace frente
  a −93 de Tienda física, con Kit de iniciación en Web propia como foco +118.
  Las 18 contribuciones se calculan y concilian para sustentar el ranking; no se
  afirma entregarlas como inventario.
- Profundiza en 62 fechas y siete categorías semanales: el aumento no depende
  de una fecha extrema, y las medias semanales observadas suben. Sábado pasa de
  4,5 a 9 unidades por fecha observada. Es descripción, sin causa ni apertura
  certificada; no se extrapola una estacionalidad recurrente.
- Entrega cuatro líneas: seis productos por mes, tres canales por mes, total
  mensual y serie diaria focal. Selecciones y notas corresponden al borrador.
- La revisión retira la recomprobación interna ya realizada, exige calcular el
  contraste semanal disponible y mantiene como parcial el cotejo externo. Nombra
  un calendario independiente y la diferencia de exposición que cambiaría la
  comparación; debe corresponder al canal pertinente, sin suponer que la web se
  rige por horarios de tienda física. No pide otra respuesta desconocida al dueño.
- Exportación y reanudación preservan aprobación y contenido. La galería muestra
  tanto el primer piloto no aceptado como esta entrega parcial aceptada.

Recursos: **49 llamadas**, doce ejecuciones (ocho completas, tres fallidas y una
salida inválida), entrada conocida **2.344.710** y salida conocida **93.574 tokens**.
Cuatro rechazos de transporte tienen consumo desconocido: uso incompleto y sin
coste monetario estimado. Se conservan reparaciones y errores. Son **27 intentos
únicos terminados** hasta aquí; no se duplican las bases históricas.

Tras pasar Bruma se lanzan únicamente WWI descubrir y WWI organizar, una vez
cada uno, en la misma copia congelada y con negocios distintos. Las demás reservas
siguen sin ejecutar. Sus resultados se conservan también cuando la auditoría
rechaza utilidad o el proveedor falla. Los seis puestos del manifiesto incluyen reservas: solo tres
se ejecutaron en este lote; las bases copiadas no son nuevas ejecuciones.

### WWI — descubrimiento, `646b35c`

Termina aprobado en **1.152,614 s y siete rondas**, con exportación y reanudación
idempotentes. Las **34 referencias** coinciden con CSV/Decimal. El complemento
independiente deriva la unión de los cinco mayores cambios de compradores por
ventas y margen, verifica sus siete identidades y calcula el resto, sin tomar los
valores del modelo como referencia. Rankings, signos, categorías, 313 fechas
observadas por año y precios ponderados registrados también se comprueban.

Mejora la profundidad: descompone Novelty Shop entre compradores seleccionados y
resto; calcula facturas, presencia en ambos años, mezcla de productos y precios
registrados. El revisor exige hacer esas comparaciones factibles antes de pedir
contexto externo; corrige cifras de orientación sin cita. Las cuatro barras son
adecuadas para cambios entre categorías y selecciones de productos; no hay regla
que fuerce líneas. La selección de cinco productos declara que no es inventario
completo, aunque abarque toda su serie de referencia seleccionada.

**No se acepta utilidad de descubrimiento.** La prioridad se justifica sobre todo
por la mayor contribución y la amplitud del resto. No explica suficientemente por
qué cotejar continuidad —con dos compradores presentes en un solo año y 450 en
ambos— merece atención antes que los descensos focales de productos. La siguiente
comprobación identifica un registro y rutas concretas, pero la conexión con qué
debe atender primero el negocio sigue limitada. Prioridad y respaldo de decisión
reciben 1; profundidad, cifras y comprobación reciben 2. La aprobación del revisor
no sustituye esta auditoría independiente ni convierte el resultado en éxito.

Recursos: **56 llamadas**, trece ejecuciones (ocho completas y cinco fallidas),
entrada conocida **3.503.283**, salida conocida **103.546 tokens**, y 19 rechazos de
transporte con uso desconocido. Se conservan fallos y reparaciones; uso incompleto.

### WWI — organización: fallo y recuperación incremental

El recorrido original falla durante investigación en **127,716 s**, sin informe,
por HTTP 429 del proveedor. No se ha establecido una causa concreta del rechazo.
Se conserva como intento fallido: **12 llamadas**, dos ejecuciones completas,
entrada conocida **263.938** y salida conocida **11.936 tokens**. Una llamada
carece de uso y hubo siete rechazos de transporte con consumo desconocido.

La reanudación usa la investigación guardada y el mismo código/modelo, con un
registro de recursos incrementales que excluye las llamadas y ejecuciones previas.
El snapshot del fallo, su evaluación y sus recursos originales permanecen intactos;
el estado vivo de la investigación sí avanza. No es otro recorrido completo ni
reemplaza el fracaso del denominador.

Termina aprobado y aceptado para organización en **387,103 s adicionales y seis
rondas de revisión**. Las **114 referencias** y los **108 componentes numéricos**
solicitados (6 anuales, 72 mensuales y 30 año-categoría) coinciden con las fuentes:
neto sin impuestos, margen bruto y promedio neto consolidado por factura. Cuatro
referencias adicionales de fechas y dos recuentos mensuales también pasan. Las
ventas categóricas llegan mediante evidencia desplegable, el margen mediante
barras y el promedio mediante texto/evidencia; no se exige un gráfico por medida.
Tres líneas mensuales conservan grano real de mes y 24 puntos cada una. No se
impone la intersección mensual por categoría, que el encargo no pide explícitamente
y cuya ausencia se declara. Exportación y replay preservan contenido/aprobación.

Recursos **solo incrementales**: **20 llamadas**, tres ejecuciones (dos completas
y una salida inválida), **1.384.486 tokens de entrada y 43.282 de salida**, con uso
completo para esta recuperación. No se mezclan con las 12 llamadas y dos cálculos
originales ni con los 29 recorridos completos acumulados. No se estima coste
monetario. El snapshot del fallo original sigue igual.

### Lectura de los resultados

Son **29 recorridos completos únicos acumulados**, incluyendo cuatro de esta
continuación: primer Bruma, segundo Bruma, WWI descubrir y WWI organizar. Tres
publican; solo el segundo Bruma se acepta como útil parcial. Las tres reservas
restantes del último lote y las cinco del primero no son intentos. Tampoco lo son
las recuperaciones incrementales ni las copias de bases históricas.

Los recorridos completos acumulan **675 llamadas** y **36 ejecuciones fallidas o
con salida inválida**. Uso conocido: **27.948.687 tokens de entrada y 1.153.324 de
salida**; faltan consumos históricos y rechazos, de modo que no representan uso
total ni coste monetario. Los recursos de recuperaciones se presentan aparte.

La galería local conserva las seis referencias históricas y añade los cuatro
informes aprobados de esta continuación, incluida la recuperación; muestra sus
valoraciones independientes, sin ocultar los dos descubrimientos no aceptados.
La revisión visual de Bruma verifica seis líneas de producto, selector de mes,
valores exactos y ocultar/restaurar una serie sin alterar el borrador. El servidor
y PostgreSQL de este worktree quedan activos en sus puertos independientes.

La comprobación de desarrollo no es ciega ni sustituye la aceptación conjunta del
propietario. Mejoran los controles y la profundidad, pero la prioridad sigue siendo
un límite de calidad y los tiempos de 14–19 minutos en los dos pilotos nuevos son
un límite operativo. **3.9.7 permanece abierto:** estos resultados no demuestran
mejora consistente ni generalización.
