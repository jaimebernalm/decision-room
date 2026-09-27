# Estabilización del revisor — 3.3.1

## Alcance

Endurecer el circuito existente antes del onboarding 3.4. Mantiene analista y
revisor; no incorpora agentes paralelos ni evalúa todavía toda la calidad por
objetivos de 3.5.

## Reparos persistentes

Las revisiones nuevas guardan `options.review_policy=1`. Cada decisión del revisor
`revise`, `reject` o `approve` incluye una `assessment` ligada al `report_step`
actual. Se guarda dentro del evento existente, antes del checkpoint, sin migración.

- `issues`: hasta 16 reparos con clave estable, gravedad `blocker` o `suggestion`,
  estado `open` o `resolved`, parte afectada, explicación, resolución y motivo de
  incorporación tardía/reapertura/cambio de gravedad.
- Cada valoración conserva todas las claves anteriores. Resolver un reparo exige
  explicar la evidencia, corrección, defensa aceptada o retirada de la afirmación.
- Aprobar con un bloqueo abierto está prohibido. Sugerencias abiertas sí permiten
  aprobar. `revise` y `reject` necesitan al menos un bloqueo material.
- Un reparo nuevo en otra ronda exige explicar la evidencia nueva, cambio de
  borrador o defecto material que se pasó por alto. No se prohíbe descubrir un
  error tardío; se evita convertir cambios cosméticos en requisitos nuevos.
- El analista recibe el registro, responde en su mensaje y presenta el borrador
  completo. Solo el revisor puede declarar resueltos los reparos.

La primera revisión debe reunir todos los problemas materiales detectables. Las
instrucciones requieren reutilizar métricas, series y comprobaciones disponibles.
El controlador rechaza repetir exactamente código y tablas de una ejecución válida
actual del analista; el revisor puede reproducirla una vez como comprobación
independiente. No se deduplica código diferente por supuesto significado equivalente.
Las correcciones del propietario invalidan evidencia anterior y permiten recalcular.

## Auditoría de lo entregado

`delivery_manifest` enumera afirmaciones, gráficos y número de puntos que resolverá
el cliente, cobertura declarada y archivos accesibles. Actualmente la lista de
archivos de ejecución descargables es vacía. Un CSV del sandbox sigue siendo
material interno, aunque aparezca como artefacto en las observaciones.

La valoración examina cinco dimensiones: cifras, significado, gráficos, cobertura y
archivos. Todas deben pasar para aprobar; gráficos admite `not_applicable` solo
cuando el informe no contiene gráficos. La revisión debe comparar la prosa con los
valores y comprobar unidades, selección de categorías, límites y ausencia de
promesas de adjuntos inaccesibles. Una entrega parcial útil y explícita es válida.

Los controles existentes siguen resolviendo las referencias, comprobando las
relaciones numéricas y porcentajes, y validando gráficos y cobertura. La aprobación
queda ligada mediante huella al informe, evidencia, comprobaciones, registro de
reparos, manifiesto de entrega y valoración. Se revalida al guardar y al consultar.
Las revisiones históricas sin esta política conservan su contrato y huella anterior.

**Límite:** el registro obliga a una decisión explícita y auditable; no demuestra
que el modelo haya clasificado bien un reparo o leído correctamente toda la prosa.
No existe un verificador determinista universal del lenguaje natural. La evaluación
independiente y el bloqueo operativo de publicaciones siguen siendo necesarios.

## Reintentos 429 y 503

En la frontera compartida de modelos:

- Máximo tres intentos HTTP por llamada lógica, solo tras rechazo explícito 429/503.
- Para 429, usar `Retry-After` numérico o fecha HTTP; sin cabecera válida, esperas
  de 2 y 4 segundos. Una espera indicada de más de 30 segundos detiene la llamada,
  sin reintentar antes de lo pedido. Como máximo dos esperas, 60 segundos en total.
- Para 503 se mantienen esperas acotadas a cinco segundos, con 1 y 2 segundos por
  defecto. No se reintentan automáticamente rechazos permanentes ni lecturas inciertas.
- Los reintentos no se admiten fuera del plazo de la llamada, calculado con su
  `timeout_seconds`; cada petición usa el tiempo restante. Esto es un límite de
  admisión y espera, no cancelación forzosa de una respuesta que ya está en curso.
- Los rechazos y la espera se guardan en `agent_calls.usage` **antes de dormir**.
  Se conserva uso desconocido de intentos rechazados; no se declara coste cero.
- Los tres intentos pertenecen a una llamada lógica. Las llamadas fallidas,
  correcciones y recuperaciones cuentan contra el mismo presupuesto persistente
  por rol. Agotarlo termina en `limited`, conserva el borrador y no aprueba.
- Tras agotar reintentos, queda `failed` y puede reanudarse. Si el proceso muere
  durante una petición/espera, el registro incierto requiere recuperación explícita;
  no se amplía el presupuesto ni se borran los intentos anteriores.

El registro inmediato de transporte se aplica al circuito persistente de
planificación/investigación/revisión. Otros consumidores del cliente comparten la
política HTTP y reciben el uso al terminar, pero mantienen su propia persistencia.

## Comprobaciones

```sh
PYTHONPATH=tests .venv/bin/python -m unittest test_review_hardening test_model_retry
PYTHONPATH=tests .venv/bin/python -m unittest discover -s tests
```

Ver los [resultados y límites de 3.3.1](../validation/2026-09-27-reviewer-stability.md).

### Reparaciones factibles y alcance observado

Los límites del contrato se entregan también a ambos roles: doce referencias por
hallazgo, seis hallazgos y cuatro gráficos. Si un desglose necesita más referencias,
se debe dividir el hallazgo o usar una serie visible; no volver a calcular ni pedir
una estructura que el contrato impide guardar.

Una comparación anual sobre los datos aportados puede responderse con una
limitación explícita de cobertura. No equivale a certificar todas las transacciones
reales del cliente. La ausencia de una auditoría de integridad del origen no
convierte automáticamente en no disponibles todos los resultados calculados.
Si el cliente pide expresamente verificar esa integridad, se evalúa como pregunta
propia. El revisor comprueba el alcance y los límites del informe en conjunto,
sin exigir repetir la misma advertencia en cada frase.
