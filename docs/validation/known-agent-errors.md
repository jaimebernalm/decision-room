# Errores conocidos del agente

## DR-001: supuesto monetario atribuido al propietario

**Estado: abierto; conservar al evaluar los pasos 1.5 y 1.6.**

Caso: `data/reference-cases/03-ambiguous-amount/input/`. Una fila con cantidad 4
e importe 25 puede representar 100 si el importe es precio unitario o 25 si es
total de fila. El propietario define unidades, impuestos y descuentos, pero no
esa base monetaria.

`qwen3.8-27b-splash`, con el prompt de planificación v2, asumió total de fila,
lo marcó como confirmado por el propietario y propuso sumar `amount` sin preguntar.
El fallo se observó con razonamiento desactivado y activado. No hubo un cálculo
ejecutado en aquella prueba. Ver [evidencia registrada](2026-09-21-agent-check.md).

La autorización del usuario para continuar permite construir y evaluar Python y
el revisor sin cerrar este fallo. No significa que la interpretación sea aceptable.

Comportamiento esperado del sistema completo:

- Reconocer la ambigüedad y pedir la definición antes de aceptar el total afectado.
- Si el principal omite la pregunta, el revisor debe detectar que la supuesta
  confirmación no está en el contexto original y devolver el trabajo.
- Ante precio unitario, calcular cantidad por precio; ante total de fila, sumar
  una vez; ante respuesta desconocida, mantener pendiente ese total y continuar
  con las unidades cuando sea posible.
- No considerar aprobado un resultado porque Python terminó sin errores o porque
  dos modelos están de acuerdo. Conservar las fuentes y las respuestas originales.

El cálculo independiente de referencia y las respuestas de evaluación permanecen
fuera del contexto del agente. Variar nombres de columnas y las respuestas para
evitar resolver únicamente este archivo concreto.

## Evidencia del revisor en el paso 1.6

En una prueba adversarial se inyectó DR-001 en el plan, candidato y primer borrador.
Qwen como revisor detectó la confirmación inexistente y devolvió el trabajo dos
veces. El analista pidió la definición, se pausó y retomó desde otro proceso. Con
la respuesta de referencia «precio unitario», recalculó 1.220,00 y 59 unidades; el
revisor aprobó el informe basado en esa evidencia nueva. El resultado anterior
quedó obsoleto.

Esto es una mitigación observada, no el cierre de DR-001: el inicio fue un fixture
con fallo deliberado y no una demostración de que el principal ya lo evita. Se
conservan también los intentos donde Qwen detectó la ambigüedad pero incumplió el
contrato de acciones. Ver [método, resultados y límites](2026-09-21-review-check.md).

## DR-002: el revisor aprueba cifras no calculadas y contradice el contexto

**Estado: abierto; informe de prueba bloqueado por comprobación independiente.**

En el caso de ventas diarias, el analista escribió +16,13 % para el cambio del
promedio diario sin guardar ese porcentaje como métrica. El revisor lo aprobó.
La operación `(3303,85 / 2844,82 - 1) * 100` da aproximadamente 16,135643 %, que
redondea a 16,14 %. El informe también afirmó que faltaba información sobre
impuestos/descuentos, aunque el contexto original define ventas sin impuestos
y con descuentos ya reflejados.

Los controles de referencias y contadores pasaban; no validaban esas frases.
Añadir un revisor con el mismo modelo no resolvió este fallo. El informe mantiene
la aprobación histórica del modelo, pero `review-hold` lo deja no publicable.

Antes de aceptar el recorrido: ampliar la evaluación y las comprobaciones de
cifras derivadas en el texto, exigir trazabilidad de sus cálculos y evaluar otro
modelo/revisor. No basta con añadir otra instrucción al prompt ni con que ambos
roles coincidan. Ver [prueba completa](2026-09-21-review-check.md).

## DR-003: mediana incorrecta con un número par de observaciones

**Estado: abierto; observado en métricas auxiliares de la prueba del informe del cliente.**

Qwen generó `sorted(vals)[len(vals)//2]` como mediana de doce ventas diarias.
Ese cálculo toma el elemento central superior; la mediana convencional es el
promedio de los dos centrales. Guardó 2.536,00 y 3.207,65 en vez de 2.491,30 y
3.185,13 redondeados. La discrepancia se detectó comparando con el CSV mediante
Decimal y `statistics.median`, fuera del contexto del modelo.

El primer borrador que intentaba utilizar estas cifras era JSON mal formado y
no obtuvo aprobación. No se atribuye al revisor la detección estadística: ese
intento se detuvo antes de completar la revisión. Incluir este caso en la evaluación
1.7. Ver [validación del informe del cliente](2026-09-21-client-report-check.md).
