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
