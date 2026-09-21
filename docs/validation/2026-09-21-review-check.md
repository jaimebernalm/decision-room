# Validación del paso 1.6 — 21 de septiembre de 2026

Implementación: conversación persistente entre analista y revisor, Python para
ambos roles, preguntas al propietario, comprobaciones y HTML privado.
El recorrido adversarial del importe ambiguo terminó corregido y aprobado; la
repetición diaria detectó un fallo del revisor y quedó bloqueada. La calidad general
del modelo no se considera aceptada.

## Método

Se distinguen dos evaluaciones:

1. Tests del controlador con respuestas de modelos simuladas explícitamente,
   PostgreSQL y Docker reales. Verifican persistencia, reglas y recuperación.
2. Pruebas reales con `qwen3.8-27b-splash` en LM Studio, API nativa, razonamiento
   desactivado y temperatura 0. Ambos roles usan el mismo modelo con instrucciones
   y llamadas separadas; no se afirma independencia estadística de sus errores.

No se instaló un proveedor nuevo ni se enviaron datos a una API externa. El HTML
se genera en la aplicación desde datos estructurados, no desde HTML del modelo.

## Pruebas automáticas

La batería de revisión cubre:

- Reparo del revisor, justificación del analista y aprobación de la versión exacta.
- Rechazo de una justificación que no satisface al revisor.
- Comprobación Python independiente del revisor e incorporación por el analista.
- Recálculo tras detectar la operación incorrecta: de 30 a 80 en el fixture.
- Pausa por una pregunta, respuesta desde otro proceso y continuación con contexto.
- Aclaración que invalida evidencia anterior y revisiones hermanas.
- Respuesta desconocida que no se convierte en una definición confirmada.
- Control numérico fallido que no puede saltarse mediante una aprobación del LLM.
- Límite de rondas sin aprobación por defecto.
- Rechazo de referencias inventadas, empresas ajenas y autoaprobación del analista.
- Invalidación por replanteamiento, escape HTML y CSP.
- Caída tras Python, antes del checkpoint, sin duplicar la ejecución.
- Caída tras guardar una decisión, antes del checkpoint, sin repetir la llamada.
- Presupuesto de contexto que detiene en vez de eliminar reparos silenciosamente.
- Código alterado después de la aprobación que impide exportar evidencia adulterada.
- Bloqueo independiente que retira la disponibilidad del informe conservando la
  aprobación histórica del modelo; reanudar no elimina ese bloqueo.

`python -m unittest discover -s tests -v`: **63 tests superados**, 44,398 s, con
la implementación final. Incluye 18 pruebas de revisión.
`python -m pip check`: sin dependencias incompatibles.

## Ventas diarias con ambos roles reales

Investigación de entrada: la cobertura de fechas del paso 1.5, con totales ya
contrastados independientemente en aquella validación.

El analista produjo un borrador que añadió porcentajes no guardados en las métricas,
incluyendo un 16,13 % para el promedio diario. El revisor detectó la falta de soporte
y pidió retirarlos o calcularlos. El analista recibió ese mensaje con el contexto
original y presentó un segundo borrador.

El segundo borrador incluyó controles `percent_change` mal definidos: comparaba
ventas absolutas con un porcentaje. La aplicación los marcó como fallidos. El
revisor explicó el error y devolvió el informe de nuevo. El analista retiró esos
controles y las cifras porcentuales sin soporte en la tercera versión.

Este intercambio se conserva completo, con mensajes, versiones y métricas. El
recorrido inicial acabó aprobado por Qwen, pero conservó dos controles vacíos de
significado: comparaban una métrica consigo misma. La comprobación independiente durante el desarrollo
detectó esta debilidad. Se añadió rechazo programático de esas comparaciones y
predicados `zero`/`nonnegative`; el prompt explica también cómo referenciar un
porcentaje calculado y cuándo no hace falta inventar controles.

Se reforzaron los controles en `review-v2`; la versión final de la conversación
es `review-v4`, con prompt `review-v3`. La revisión inicial queda obsoleta al cambiar
las reglas, conserva su historial y no puede exportarse ahora como aprobación
vigente. La repetición con las reglas finales terminó con una aprobación **incorrecta**:
el analista volvió a incluir +16,13 % para el promedio diario y el revisor lo
aprobó, aunque la aritmética independiente redondea a +16,14 %. También afirmó
que no se habían proporcionado impuestos/descuentos cuando sí estaban definidos
en el contexto original. Los valores estaban presentes en el contexto de ambos
roles; conservarlos no garantiza que el modelo los interprete bien.

El informe quedó bloqueado mediante `review-hold`, con `publishable=false`. Se
conserva por separado la decisión original `approved` del modelo y el motivo
de la comprobación independiente. Este fallo se registra como **DR-002 abierto**.
No se modificó el informe ni el código del modelo para hacerlo pasar.

## Caso adversarial de importe ambiguo

El script `check_review_ambiguity.py` inyecta deliberadamente el fallo conocido
DR-001 en el plan, candidato y primer borrador. Esas tres piezas son **fixtures**,
no salidas nuevas de Qwen. El cálculo equivocado bajo una posible interpretación
se ejecuta en Docker y tiene evidencia real; lo incorrecto es atribuir al dueño
una definición que no ha dado.

Los primeros dos intentos detectaron semánticamente la confirmación inexistente,
pero fallaron el contrato de acciones: mezcla de `revise` con código Python,
pregunta en una devolución y omisión de `report=null`. No se ejecutó ese código
ni se aprobó el informe. Se añadió una pregunta explícita del revisor al analista,
un diagnóstico más preciso para acciones mezcladas y valores vacíos por defecto
para campos omitidos. No se infiere una acción ni se ejecuta código de `revise`.

El revisor y el analista posterior usan el modelo real. No reciben `expected.json`.
El recorrido final devolvió el informe al analista dos veces. En la primera
devolución detectó la confirmación inexistente; el analista retiró esa atribución
y aclaró que sumar `amount` no equivalía a ventas totales. El revisor insistió en
resolver la contradicción del plan provisional o preguntar al propietario.
El analista preguntó entonces si `amount` era precio unitario o total de fila.
La revisión quedó `waiting`, con cinco mensajes persistidos y sin aprobación.

Se reanudó desde otro proceso con la respuesta `unit_price` del caso de referencia
mediante `review-answer`; no se inventó una respuesta dentro del grafo. El analista
generó un nuevo programa que calculó **1.220,00**, mantuvo **59 unidades** y comprobó
que no hubiera importes negativos ni cantidades no positivas. Las cuatro cifras se
contrastaron independientemente con el CSV y `Decimal`. La evidencia anterior de
257,50 quedó obsoleta y la investigación original pasó a `stale`.
El revisor aprobó el nuevo borrador en el paso 8, citando la respuesta de referencia aportada al
caso de prueba, el cálculo nuevo y los controles `zero` sobre los contadores.
El informe final cita únicamente la ejecución vigente. La secuencia completa fue:
`submit → revise → submit → revise → ask_owner → execute → submit → approve`.

Esto demuestra detección y corrección del fallo **inyectado** en este recorrido.
No demuestra que el principal evite producirlo por sí solo ni sustituye las
repeticiones, variantes o evaluación de otros modelos del paso 1.7. DR-001 sigue
abierto como riesgo del principal, con esta mitigación observada.

## HTML y límites

Los tests comprueban estructura, escape de contenido potencialmente ejecutable,
CSP y separación entre borrador, obsoleto y aprobado. Se intentó una comprobación
visual, pero la política del navegador bloqueó el acceso al archivo local. No se
usó otra vía para eludir ese bloqueo; la presentación visual no se ha verificado.

Las exportaciones son instantáneas privadas con fecha. Una exportación antigua no
puede revocarse a distancia; se vuelve a consultar/exportar para conocer la vigencia.
Sigue pendiente la evaluación del producto del paso 1.7: más casos, repeticiones,
variantes y modelos. Aprobación automática no equivale a garantía de corrección.

## Archivos de las comprobaciones

En `.local/review-checks/`, excluido de Git:

- `review-check-ba553b5d5ee64cf685ffc2fe625e47ee/`: conversación diaria inicial; reglas antiguas.
- `ambiguity-review-c1928af7035545fd8b74918372a71b04/`: primer fallo de formato del revisor.
- `ambiguity-review-3742916fde3749d8a55c90eb9c727ac7/`: segundo intento, detenido por formato.
- `ambiguity-review-a6299babd5ce4f80aed0bd8a10dec225/`: pausa ante el importe ambiguo y contraste independiente.
- `review-check-02013256bc82422092535a54bbe8f159/`: recorrido ambiguo completado y HTML vigente.
- `review-check-8b3f75d93c054148b27e198847a1ed9a/`: repetición diaria con aprobación incorrecta; contraste independiente y bloqueo.

Una copia cómoda del último ejemplo está en `outputs/review-demo/`: `report.html`,
`conversation.md`, `review.json` e `independent-check.json`. `daily-blocked.html`
y su JSON muestran el contraejemplo retenido. Es material local
ignorado por Git. Los documentos de producción no contienen rutas personales.
