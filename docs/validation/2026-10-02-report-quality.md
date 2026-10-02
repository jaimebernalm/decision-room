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
Prueba real del ajuste siguiente pendiente; WWI no se lanza aún.

La comprobación de desarrollo no es ciega ni sustituye la aceptación conjunta del
propietario. 3.9.7 permanece abierto: un informe aislado no demuestra consistencia.
