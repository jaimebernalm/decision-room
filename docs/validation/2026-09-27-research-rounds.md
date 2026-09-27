# Validación del paso 3.3 — investigación por rondas

## Alcance y criterios

El [contrato de implementación](../technical/research-rounds.md) fija la aceptación:
profundización útil vinculada a evidencia, cifras reproducibles, límites explícitos,
recuperación sin duplicar trabajo y resultados parciales revisables. La selección
editorial por objetivo y la comparación completa contra 3.1 siguen en 3.5.

Pruebas de control: PostgreSQL y Docker reales; modelos simulados identificados
como tales. Evaluación analítica: GPT-6 Luna, razonamiento `low`, cinco tablas
públicas de Wide World Importers y 299.673 filas. Los agentes reciben definiciones
del propietario, datos y objetivo; no reciben el oráculo CSV/Decimal ni los
resultados esperados. Cada lote usa una base aislada, huellas de fuentes y código,
registros de llamadas, programas, evidencia y resultados locales.

## Intentos iniciales conservados

Lote local `rounds-33-a`, dos repeticiones, sin cambios de código durante cada
recorrido. No se presentan como informes aceptados:

| Recorrido | Investigación | Revisión y resultado | Tiempo | Llamadas / Python |
|---|---|---|---:|---:|
| A1 | Cuatro candidatos, tres rondas; evolución anual, contribuciones por producto y comparabilidad mensual. | Alcanzó el límite del revisor; no publicable. | 276,244 s | 20 / 5 |
| A2 | Tres intentos sobre una investigación; hubo un cálculo correcto intermedio. | El último intento impuso erróneamente presencia de cada producto en ambos años, falló y el agente bloqueó el trabajo; sin candidato revisable. | 59,387 s | 6 / 3 |

A1: 177 métricas/puntos de serie de investigación contrastados con el oráculo,
sin discrepancias dentro de una tolerancia absoluta de 0,000001. Esto valida los
cálculos contrastados; no equivale a aprobar su informe. El revisor pidió completar
la presentación de contribuciones y, en una ronda, interpretó `report=null` del
contexto deduplicado como ausencia del borrador que estaba en el mismo mensaje.

A2: el primer intento tuvo un error de sintaxis SQL; el segundo sí calculó los
agregados. El analista amplió la misma investigación antes de registrar ese
resultado, y su tercer intento falló. Este caso muestra por qué hay que conservar
un resultado parcial antes de profundizar.

## Correcciones motivadas por la prueba

- El borrador deduplicado usa una referencia explícita `{"$ref":"#/report"}`;
  no representa la presencia del informe mediante un valor nulo.
- Las instrucciones piden registrar resultados válidos antes de ampliar alcance,
  formular seguimientos acotados y guardar contribuciones visibles como métricas
  o series, sin depender exclusivamente de CSV no leídos por el revisor.
- Se distingue la contribución observada cero de un grupo sin filas en un periodo
  de afirmar que no hubo actividad real o que un calendario incompleto vale cero.
  La aparición/desaparición de grupos no debe fallar una aserción de integridad.
- La nota del controlador sobre cobertura conserva todas las limitaciones
  sustantivas del informe; no elimina una para hacer sitio a la nueva nota.

## Repetición y comprobación adicional

Lote `rounds-33-b`, con los ajustes anteriores:

| Recorrido | Investigación | Revisión y resultado | Tiempo | Llamadas / Python |
|---|---|---|---:|---:|
| B1 | Tres candidatos en dos rondas; incluye distribución completa por producto y reconciliación. | Falló al proponer gráficos de 219 categorías, superiores al límite visual de 36. | 155,204 s | 13 / 4 |
| B2 | Dos candidatos del plan inicial; no abre seguimientos innecesarios. | Aprobado y exportado después de que el revisor exigiera cuantificar los productos destacados. | 127,658 s | 12 / 3 |

B2: **27 referencias numéricas y puntos de gráficos citados comprobados**, sin
error material: cantidades/importes con tolerancia absoluta 0,000001; porcentajes
almacenados a cuatro decimales con tolerancia 0,00005. También se revisó la prosa:
comparación 2014–2015, cinco productos por cambio absoluto, signos conservados,
moneda no declarada y contribución aritmética separada de causalidad.

B1 motivó una corrección del esquema de salida: ahora solo se ofrecen referencias
de series que caben enteras en el tipo de gráfico elegido. Las series extensas
siguen disponibles como evidencia; para mostrarlas hay que guardar un resumen
calculado con selección explícita. La prueba de regresión cubre 219 categorías,
24 meses, 100 días y un resumen de cinco grupos, evitando combinaciones inválidas.

El lote `rounds-33-c`, ejecutado con esa corrección, completó dos rondas y dos
candidatos. El segundo verificó una duda concreta surgida del primero: existencia
de líneas sin factura que no podrían asignarse al periodo solicitado. Sus conteos
fueron cero y el agente se detuvo sin nuevas rondas de escaso valor.

C tuvo un error SQL corregido y llegó a revisión. Se contrastaron 31 referencias
numéricas/puntos del borrador inicial sin discrepancias. La revisión quedó
interrumpida por HTTP 429. Una reanudación conservó los cálculos anteriores y
avanzó en las objeciones; ejecutó dos programas nuevos solicitados por el revisor
(uno falló por restar textos) y volvió a recibir 429. Es **un informe no aprobado**,
no una ejecución aceptada. Se conserva el intento original y la recuperación.
No se añadió reintento automático de 429 en este paso.

## Cobertura de cálculo frente a cobertura de entrega

Al recuperar B1 se confirmó que las referencias visuales ya eran válidas, pero
apareció un defecto de la nota del controlador: contaba tres resultados calculados
como cierre aunque el informe marcara el desglose completo como no entregado. El
revisor pidió retirar esa nota repetidamente y agotó su presupuesto. Las dos
recuperaciones de B1 se conservan; la primera recibió 429, la segunda terminó
`limited`. Ambas mantuvieron las cuatro ejecuciones existentes, sin repetirlas.

La corrección final deriva la nota de `question_coverage`, distingue trabajo
calculado de respuestas entregadas y sustituye su texto anterior sin eliminar
limitaciones sustantivas. Una prueba reproduce tres candidatos calculados y solo
una respuesta entregada, y exige una única nota «1 de 3», sin declarar completitud.
La primera revisión nueva de B1 fue aprobada por el modelo, pero la comprobación
independiente detectó una afirmación incorrecta: decía entregar un CSV adjunto
que la interfaz y el HTML no ofrecían. Se registró un **bloqueo independiente de
publicación**, conservando la aprobación histórica y el export de prueba. Sus 48
cifras contrastadas eran correctas; eso no bastaba para aceptar la entrega.

Se añadió al contexto la capacidad real del canal (`execution_artifact_downloads`
es falso) y la instrucción de no presentar archivos internos como adjuntos. Con el
código final, una revisión nueva de los mismos candidatos fue **aprobada y aceptada
independientemente** en 43,440 s, cuatro llamadas y **ninguna ejecución Python
adicional**. El informe declara **2 de 3 preguntas respondidas**, muestra los cinco
mayores cambios por medida y deja el desglose completo fuera de esta entrega.
Los **48 valores citados/puntos de gráficos coinciden con el oráculo**; se comprobó
además que prosa, cobertura y HTML no prometen el adjunto inexistente. La revisión
bloqueada y todas las recuperaciones anteriores permanecen disponibles.

Ejemplos comprobados: ventas sin impuestos de 49.929.487,20 a 53.991.490,45;
cambio de 4.062.003,25. El producto 161 aporta 370.440,00 al cambio de ventas y
315.560,00 al de margen bruto. Son contribuciones aritméticas observadas, sin
atribución causal ni moneda inventada.

**Cierre de 3.3:** la profundización, los presupuestos, la recuperación y la entrega
parcial con cobertura honesta están implementados y comprobados. Los rechazos
anteriores no se convierten retrospectivamente en éxitos; la aceptación final no
sustituye la evaluación amplia de calidad de 3.5.

## Pruebas automatizadas y límites

- Batería general: **336 pruebas correctas** antes de los ajustes finales de
  presentación del contexto y restricciones visuales.
- Revalidación dirigida tras las correcciones de rondas y cobertura: **63 pruebas correctas**, incluyendo las 12 nuevas
  de rondas, agenda, prioridades, presupuesto, recuperación y conservación de
  limitaciones, más contratos de modelos, contexto y flujo de revisión.
- Tras declarar las capacidades reales del canal: **40 pruebas dirigidas correctas**
  de rondas, contratos, contexto y revisión sobre el código final.
- Compilación de módulos Python, ayuda del CLI y `git diff --check` correctos.
- No hay cambios de componentes frontend ni otra migración de base de datos.

Los modelos simulados comprueban paradas por rondas, investigaciones, ejecuciones,
decisiones, tiempo y llamadas; el límite cuenta consultas y correcciones. La caída
tras ejecutar en la segunda ronda no duplica acciones ni programas. Las preguntas
bloqueadas y el trabajo descartado permanecen explícitos. Un informe parcial con
un candidato y dos investigaciones pendientes puede revisarse y publicarse con
cobertura honesta, sin perder ninguna de sus doce limitaciones sustantivas.

La evidencia demuestra la mecánica de profundización y conservación de resultados,
no una mejora general de calidad frente a 3.1. Los recorridos reales todavía muestran
coste alto, verificaciones redundantes, errores de Python corregibles y revisiones
que pueden agotar su presupuesto. La optimización y evaluación completa por
objetivo continúan en 3.5; los 429 y su recuperación operativa requieren trabajo
posterior. El coste monetario no se estima sin una tarifa comprobada; las llamadas
rechazadas conservan su uso desconocido.



## Reproducción

```sh
.venv/bin/python -m decision_room.evaluation.research_rounds \
  --output .local/evaluation/rounds-new --repeats 2
PYTHONPATH=tests .venv/bin/python -m unittest test_research_rounds \
  test_model_references test_review_context test_review
```

El ejecutor crea una base aislada y conserva fallos. Las referencias se calculan
antes de las llamadas y se guardan fuera del contexto del modelo. El análisis
independiente de valores citados usa nombres de métricas y selecciones observadas;
no toma la aprobación del revisor como resultado del evaluador. Los archivos
privados de cada lote incluyen manifest, fuente exacta mediante huella, recursos,
programas, intentos y comprobaciones. El lote inicial de 3.1 no se modifica.

El servidor principal del entorno local no se reinició durante esta validación;
los experimentos usaron bases y almacenamiento aislados.
