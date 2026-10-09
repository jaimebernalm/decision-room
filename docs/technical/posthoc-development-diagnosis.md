# V1: diagnóstico offline de las interpretaciones de desarrollo

El segundo informe de desarrollo terminó en `70146b2`, con 11 ocurrencias
verificadas, 107 inciertas y 39 no comprobables de 157 inventariadas. No hubo
discrepancias. Las invariantes de fuente, DOM y los tres gráficos pasaron.
Esto no mide exactitud ni cobertura sobre cifras auditadas: el inventario incluye
etiquetas, fechas e identificadores. La prueba sellada sigue pendiente.

El gasto conocido acumulado de desarrollo es 0,213905560 USD; este informe costó
0,075909795 USD. El diagnóstico utiliza respuestas ya guardadas, sin llamadas
nuevas ni cambios en el ledger. Una reproducción offline con `3b2fb93`, que añade
el veto de negación, no cambió los estados ni el HTML de este informe; no es otra
ejecución de modelo ni sustituye su revisión original.

## Desglose del grupo sin acuerdo

La razón `No agreed supported interpretation.` aparece en 80 ocurrencias:
**73 inciertas y 7 no comprobables**, no 80 inciertas. Esta precisión corrige el
resumen anterior del desarrollo.

| Dos respuestas por ocurrencia | Ocurrencias |
| --- | ---: |
| Ambas inciertas | 48 |
| Una receta propuesta y otra incierta | 22 |
| Ambas no comprobables | 7 |
| Una incierta y otra no comprobable | 3 |

Ninguna de estas 80 contiene dos recetas propuestas que fallen validación: esos
fallos tienen otras razones en el ledger. Una receta propuesta no equivale a una
verificación; aquí falta el acuerdo de las dos interpretaciones.

Se clasificaron manualmente las razones declaradas en las **121 respuestas
inciertas** de este grupo. Las etiquetas no son exclusivas y describen lo que
alega el modelo, no una causa demostrada.

| Motivo declarado | Respuestas | Ocurrencias con al menos una respuesta |
| --- | ---: | ---: |
| Población o filtros | 55 | 39 |
| Periodo | 39 | 32 |
| Valor oculto | 14 | 12 |
| Limitación del catálogo | 13 | 12 |
| Magnitud, operación o dirección | 11 | 9 |
| Contexto o receta insuficiente, sin precisar campo | 7 | 7 |
| Columna | 2 | 2 |
| Unidad, por sí sola | 0 | 0 |

«Valor oculto» incluye una lectura de un componente de fecha; no significa que
las otras trece hayan perdido una etiqueta necesaria del ámbito. «Limitación del
catálogo» incluye afirmaciones incorrectas del modelo sobre las operaciones
admitidas. No se suman las filas para estimar causas independientes.

## Muestra de lectura y límites

Antes de clasificar se fijaron 15 posiciones equidistantes del grupo ordenado por
inventario: 0, 6, 11, 17, 23, 28, 34, 40, 45, 51, 56, 62, 68, 73 y 79.
Es una muestra sistemática de un único informe, no aleatoria ni representativa.
El juicio del implementador fue: **11 con significado claro para un lector,
2 con alcance inferido o dependiente de referencias y 2 etiquetas**. Los textos,
ubicaciones, respuestas y justificación individual quedan en el registro privado.
Claridad al leer no acredita corrección numérica, citas suficientes ni
admisibilidad bajo las reglas del piloto.

Hay evidencia concreta de dificultades de interpretación:

- Una respuesta rechaza una diferencia entre dos sumas mensuales porque cree que
  necesita una operación anidada no admitida. `difference` admite precisamente
  dos operandos primitivos `sum`.
- Varias respuestas rechazan celdas de tabla por falta de periodo o filtros aunque
  se suministran la cabecera del mes, el texto de la fila y la introducción con el
  año y la comparación entre meses completos. En nueve objetivos revisados, el
  año y los meses seguían visibles; en uno estaba oculto el día inicial, no el año.
  Esto permite investigar la interfaz, pero no demuestra que toda receta sea
  válida ni que el modelo deba completar silenciosamente cualquier periodo.
- Algunas respuestas invocan el valor oculto como impedimento para interpretar
  la receta. El procedimiento exige interpretar su significado, no reconstruir
  ese valor. También hay lecturas que confunden el objetivo con una cifra vecina.

Otros obstáculos sí pertenecen al diseño actual:

- Una contribución al crecimiento neto puede necesitar
  `100 * (A - B) / (C - D)`. El catálogo implementado admite operandos primitivos,
  no ese cociente de diferencias. No debe reemplazarse por una cuota de niveles.
- Una fila residual de combinaciones no enumeradas puede exigir un complemento
  de pares de categorías que no cabe directamente en filtros conjuntivos `in`.
- Un recuento de entidades no hereda el significado de un recuento de filas por
  observar una clave única. Una etiqueta de fecha u orden no es una cifra de
  negocio, aunque siga en el inventario y el ledger.
- La totalidad explícita y el veto de categorías siguen aplicándose también a
  denominadores. Una población que resulta comprensible al lector puede ser
  inadmisible para este piloto. No se amplía la lista cerrada de totalidad.

## Siguiente paso propuesto

Antes de congelar tiene sentido una única iteración acotada de la interfaz:
explicar con un ejemplo sintético la diferencia de dos sumas, la combinación de
citas de fila, cabecera y periodo global cuando sea inequívoca, y la separación
entre interpretar la receta y recuperar un valor oculto. Debe preservar todos los
validadores, las dos lecturas, las máscaras y el catálogo. Primero se comprueba
sin modelo que los ejemplos válidos pasan y sus variantes ambiguas se rechazan;
después se mide en desarrollo si cambia el acuerdo, con el gasto registrado.

Esta propuesta no asegura alcanzar la cobertura exigida y no autoriza ampliar
operaciones ni relajar fundamentos. Si una mejora exige cambiar esas reglas, se
registra y decide expresamente antes de usarla. No se congela ni se ejecuta la
prueba sellada basándose solo en este diagnóstico.

La siguiente revisión implementa únicamente esas aclaraciones del prompt. Un
fixture sintético resuelve citas de fila, cabecera y periodo global para una
diferencia de dos sumas con los valores ocultos; rechaza perder la cita del año y
no admite un operando derivado dentro de un cociente. Las 28 pruebas de recetas y
población pasan sin proveedor. Los validadores y las reglas siguen iguales.
La última iteración de desarrollo comparará el segundo informe ya usado con un
informe aún no usado, elegido por orden lexicográfico antes de ejecutarlo. Su
techo conjunto de coste conocido es 0,25 USD, además de los límites existentes;
la reserva se comprueba antes de cada llamada. Después se decide si proponer la
congelación o presentar el diagnóstico al propietario, sin más rondas abiertas.
