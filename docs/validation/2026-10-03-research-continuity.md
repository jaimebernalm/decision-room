# Fase 2 — Continuidad dentro de una investigación

Base congelada: `baa0bbb`. Rama `codex/feature/report-quality-continuity`.
[Plan y alcance](../technical/research-continuity-plan.md).

## Activación para el lanzador

- Control: `DECISION_ROOM_RESEARCH_CONTINUITY=false` (valor predeterminado).
- Candidato: `DECISION_ROOM_RESEARCH_CONTINUITY=true`.
- API Python: `research.start(..., research_continuity=True)`; `False` explícito
  prevalece sobre la configuración. `None` usa la configuración cargada.
- CLI: `agent-research --research-continuity`.

El lanzador debe cargar la configuración después de definir la variable. La web
usa la misma configuración, por lo que hay que reiniciar su proceso para cambiar
el valor. No se cambió ninguna instancia existente ni se generaron informes reales.

La opción se congela en `agent_research.options`, se hereda por los trabajadores y
participa en la huella de la petición. Reanudar usa el valor guardado; cambiar la
variable no convierte un ensayo ya iniciado en otro brazo. Una misma request_key
no puede reutilizarse para cambiar de brazo. Las llamadas nuevas de investigación
usan `research-continuity-v1`; el control mantiene versión, prompt y esquema de
`baa0bbb`. No se amplían los presupuestos ni se añade una nueva migración.

## Comportamiento

1. Tras una ejecución correcta el investigador puede ejecutar otro cálculo en la
   **misma investigation_key**. Añade `continuation` con evidencia de partida,
   `next_calculation` y `decision_if_different`. No registra un candidato intermedio,
   no crea una tarea hija y no devuelve la tarea al coordinador entre cálculos.
2. Cada ejecución conserva su registro, código y resultados inmutables. El contexto
   experimental incluye todas las ejecuciones correctas y el último intento de
   cada tarea. Los errores anteriores siguen guardados y contando contra cuotas.
   No hay compresión automática ni aumento del límite de contexto.
3. `record_candidate.evidence_refs` puede seleccionar métricas y series de varias
   ejecuciones correctas de esa tarea. Cada referencia tiene `execution_id`,
   `metric_keys` y `series_keys`. Permite conservar evidencia anterior aunque el
   último cálculo haya fallado. El campo escalar antiguo sigue como abreviatura
   de métricas del último intento, si este fue correcto.
4. Una ampliación selecciona evidencia **registrada** en el candidato padre, no
   cualquier resultado suelto. Los hijos pueden usar `basis_evidence`, con la misma
   referencia a ejecución/métricas/series, sin inventar una métrica escalar para
   representar una serie. `basis_metric_keys` sigue disponible para el contrato
   escalar anterior. No se aceptan series dentro de `metric_keys`.
5. El cierre (`record_candidate`, `block`, `discard`) exige una nota estructurada:
   motivo, cálculo pendiente, qué decisión cambiaría si diera otro resultado y
   explicación. `pending_calculation=null` requiere explicar por qué no queda
   uno material. Presupuesto o falta de datos exige nombrar el cálculo pendiente.
   Esto comprueba el contrato, no la calidad semántica de la explicación.
6. La nota y las referencias viajan en los pasos inmutables y se reconstruyen en
   candidatos y cobertura. La importación del trabajador las conserva; el revisor
   recibe todas las ejecuciones y la nota. Ningún resultado se aprueba por cerrar.

Los límites siguen aplicando a **todos** los intentos, también los errores que ya
no ocupan el contexto. Al agotarse ejecuciones el esquema experimental deja de
ofrecer `execute` y conserva las acciones de cierre. Si se agotan llamadas,
tiempo o turnos antes de obtener una nota, la evidencia permanece y la cobertura
indica `closure_status=not_recorded`; el controlador no inventa una nota ni afirma
que no quedaba trabajo. El estado de un candidato no acredita utilidad ni entrega.

## Fronteras y fallos de los ensayos

Las referencias llevan ejecución y clave para evitar colisiones entre métricas con
el mismo nombre. Se rechazan evidencia inexistente, de otra tarea, fallida,
obsoleta o no visible por omisión de tamaño. El esquema ofrece pares reales; la
validación comprueba además tarea y pertenencia al candidato padre.

No se relajan las referencias del planificador ni se ignoran dos validaciones
fallidas. Conservar las observaciones previas evita perder evidencia por sustituir
el último intento, pero no corrige una referencia que el modelo inventa. El fallo
general del planificador comunicado por los ensayos queda fuera de esta fase.

No se incorpora exploración provisional, panorama, lógica de señales de un negocio,
revisión nueva ni cambios de presentación. Las pruebas usan cantidades mínimas y
operaciones genéricas; no usan informes, datasets ni oráculos de los ensayos.

## Validación local

Se usa un worktree nuevo desde la referencia, PostgreSQL con cluster y socket
propios, almacenamiento y temporales del worktree y una VM Docker propia. La imagen
inmutable se copia y verifica contra las mismas fuentes del runtime; no se cambia
la VM ni los montajes de los ensayos. El intérprete/dependencias se reutilizan.
Todas las respuestas de modelos son fixtures o transporte simulado, sin llamadas
reales al proveedor y sin claves de API habilitadas.

Resultado: 103 pruebas de regresión correctas (investigación, rondas, delegación,
planificador, contratos de fase 1 y entrega). Tras añadir la comprobación del
esquema al agotar ejecuciones y la ampliación delegada basada solo en series,
las 17 pruebas finales de continuidad pasan. Estos grupos se solapan; no son
120 pruebas distintas. También pasan compilación Python y `git diff --check`.

Cobertura específica: continuidad sin reapertura del coordinador, selección de
varias ejecuciones, fallo posterior sin pérdida de evidencia, referencias inválidas,
series como fundamento de ampliación, presupuestos incluso con errores omitidos,
cierre incompleto al interrumpir por límite, recuperación sin ejecutar dos veces,
importación de trabajadores, traspaso al revisor y conservación del modo control.
El esquema y prompt se comprueban mediante el transporte simulado efectivo.

La implementación y su validación local quedan completas. No se ha medido mejora
en profundidad, utilidad, coste o tasa de aceptación: queda pendiente ejecutar el
mismo lanzador contra `baa0bbb` y el candidato, con la opción activada únicamente
en este último. La revisión local no incorpora resultados de los kits ciegos.

## Corrección del esquema estricto tras el ensayo

El candidato `2cd836e` fue rechazado en su primera llamada de investigación con
HTTP 400: `EvidenceRef` declaraba `metric_keys` y `series_keys` como propiedades,
pero solo exigía `execution_id`. Las pruebas anteriores validaban respuestas con
JSON Schema; no comprobaban las restricciones adicionales del proveedor. Por tanto,
los resultados locales anteriores no acreditaban la admisibilidad de la petición.

La corrección exige las tres propiedades en el esquema productor, antes de copiar
sus variantes por ejecución. También se aplica a la definición sin evidencia de
la primera llamada. Una referencia usa `[]` para el tipo de evidencia no utilizado;
los valores por defecto internos se conservan para compatibilidad. No cambia el
prompt, las referencias autorizadas, la lógica analítica ni los esquemas del control.

`tests/test_model_strict_schemas.py` comprueba las peticiones HTTP finales y su
igualdad con `effective_request`, usando únicamente `MockTransport`. Recorre todos
los objetos, incluidos `$defs`, elementos de arrays y ramas `anyOf`, y exige
`additionalProperties: false` y `required` exactamente igual a sus propiedades,
sin duplicados. Comprueba además la validez JSON Schema y las referencias locales.
La regla procede de la [documentación oficial de Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs).

Cobertura final: los diez métodos productores, 49 contextos genéricos y 90
peticiones simuladas al incluir recuperación de memoria donde se utiliza. Incluye
coordinador y trabajador en su primera llamada, éxitos, varias ejecuciones,
fallos posteriores, métricas solas, series solas, evidencia obsoleta u omitida,
ampliación, presupuestos y gráficos con capas en redacción/revisión. Un control de
cobertura exige incorporar a la matriz los nuevos métodos productores. Las pruebas
negativas reproducen la omisión de `required` y los objetos abiertos, y comprueban
que omitir una lista falla mientras una lista vacía explícita es válida.

Antes de corregir el código, la primera matriz reprodujo el fallo en los 16 casos
experimentales y en la prueba de lista omitida. Después pasan las 30 pruebas de
esquemas, transporte OpenAI, contrato de continuidad y productor de capas. También
pasan `compileall` y `git diff --check`. Los 31 esquemas de control capturados antes
del cambio coinciden con los posteriores. No se ha llamado a ningún modelo real,
ni iniciado bases de datos o servicios compartidos. Esta es una comprobación
local de contratos, no una garantía de aceptación de cualquier esquema futuro por
el servicio. El lote corregido y su medición permanecen pendientes.
