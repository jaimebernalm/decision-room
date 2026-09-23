# Validación del paso 2.5.3 — contexto compartido y correcciones entre sesiones

**Fecha:** 23 de septiembre de 2026. **Rama:** `feature/business-memory-ux`. **Estado:** completado y comprobado. El commit de cierre es el que incorpora este informe, local y sin push. El hash se comunica al entregar el paso y queda consultable con `git log`.

## Plan aplicado y archivos

Se aplicaron los cuatro incrementos de [2.5.3](../technical/business-memory-implementation.md):

1. Selector por negocio, fuente/análisis y periodo; contexto inicial pequeño y manifiesto persistente.
2. Herramientas comunes para que el agente busque datos, abra perfiles, consulte memoria y busque/abra antecedentes y evidencia; registro de cada ampliación.
3. Invalidación entre sesiones por cambios relevantes, retiradas, antecedentes invalidados y datos; distinción entre corrección histórica y cambio con fecha de inicio.
4. Comprobaciones al reanudar, durante el recorrido y antes de publicar/exportar; replanificación web recuperable que conserva los originales y las versiones previas.

La migración 10 está en `decision_room/schema.sql`; selección y herramientas en `decision_room/memory/context.py` y `retrieval.py`; mantenimiento temporal/invalidación en `memory/service.py`. La frontera común de llamadas del agente incorpora el contexto y registra su carga en `agent_calls`; planificación valida referencias de memoria; investigación/revisión comprueban vigencia y guardan procedencia. `web/service.py`, el botón de `app.js` y la exportación comparten las comprobaciones de publicación. El [contrato técnico](../technical/context-retrieval.md) explica reglas, almacenamiento, recuperación y límites.

## Pruebas deterministas e integración

Las bases PostgreSQL de la suite son temporales y se eliminan al terminar. Los cálculos de integración usan el sandbox real; las respuestas de los modelos controlados son fixtures, no una evaluación de calidad del modelo.

- Dos sesiones reciben una definición sin volver a preguntarla; ambas calculan 80. Una corrección retira sus informes y la sucesora calcula 30.
- Planificación, investigación y ambos roles de revisión reciben la revisión de memoria correspondiente. Los cálculos conservan manifiesto y clave de conocimiento.
- Un cambio desde septiembre conserva válido junio; una nueva sesión de junio recibe la revisión histórica aplicable. Otro negocio, una fuente diferente, un periodo posterior y una prioridad ajena al cálculo no retiran indiscriminadamente los resultados.
- Una nueva duda relevante invalida aunque su ID no existiera al crear el manifiesto. Las dudas/definiciones no desaparecen por una consulta textual irrelevante o un límite de resultados bajo.
- La retirada excluye el recuerdo de nuevas selecciones y búsquedas. También impide reproducir la respuesta original de la sesión que lo aportó y los recuerdos retirados de prioridad. El contexto imprescindible demasiado grande pausa sin truncarlo.
- El agente controlado descubre una tabla por descripción, abre su perfil/memoria, encuentra un informe, lo abre y abre la evidencia. Quedan cinco recuperaciones trazables; repetir/reanudar no duplica consultas. Una retención independiente del antecedente invalida al consumidor.
- Otro negocio y periodos incompatibles quedan excluidos. Las referencias de memoria conservan ámbito y versión; recuperar otra tabla no concede permiso para ejecutarla.
- Una corrección dentro de Python o durante la aprobación impide publicar, conservando el cálculo anterior. La lectura de publicación vuelve a leer el registro después de obtener el bloqueo, por si hubo un escritor mientras esperaba.
- Reinicio después de guardar una recuperación y antes de la siguiente llamada; interrupción web entre crear la sesión sucesora y actualizar el trabajo. Ambos recuperan sin duplicar efectos.
- Migración repetida, fallo transaccional y reintento; registros anteriores conservados. Un checkpoint sin manifiesto requiere replanificar; reenviar su petición de creación tampoco le adjunta memoria nueva silenciosamente.
- La regresión incluye ingesta, ejecución, planificación, revisión, informes, memoria y web. Se mantiene el error controlado de evidencia desaparecida y el aislamiento de ámbito.

La suite final pasa **200 pruebas en 83,540 s**, incluidas las **16 pruebas específicas de contexto**. La ronda anterior pasó 199 pruebas; después se amplió la cobertura de retiradas y se repitió la regresión completa. JavaScript y Python se comprueban con `node --check` y `compileall`; se revisan diferencias, enlaces locales y contenido público antes de guardar el commit.

## Modelo real: reutilización, antecedentes y corrección

Comando reproducible:

```sh
.venv/bin/python scripts/evaluate_context.py --output .local/context-evaluation
```

Utiliza el modelo configurado, crea una base aislada y un CSV ficticio de dos filas (`quantity,amount`: `2,10` y `3,20`) y elimina base/archivos temporales al terminar. Se niega a sobrescribir el directorio de resultados. La salida detallada permanece en `.local/`, fuera de Git. La opción `--adversarial` permite añadir una nota de memoria que intenta imponer instrucciones ajenas al sistema.

Con `gpt-6-luna`, razonamiento `low`, se completaron dos rondas de tres investigaciones:

| Comprobación | Primera ronda | Ronda final |
|---|---|---|
| Primera investigación con definición guardada de precio unitario | Informe aprobado, 80 | Informe aprobado, 80 |
| Segunda investigación, misma memoria, sin repetir definición | Informe aprobado, 80 | Informe aprobado, 80 |
| Corrección histórica a importe de fila | Dos informes anteriores retirados | Dos informes anteriores retirados |
| Replanificación con definición corregida | Informe aprobado, 30 | Informe aprobado, 30 |
| Recuperaciones elegidas por el modelo | 3 búsquedas de informes y 1 apertura | 3 búsquedas de informes |
| Llamadas / duración | 20 / 102,36 s | 19 / 89,69 s |
| Tokens de entrada / salida | 123.058 / 9.980 | 113.711 / 9.058 |

No se exigió que el modelo abriera siempre el antecedente: decide si necesita profundizar. La apertura de cálculos y las restantes herramientas también están cubiertas por la integración controlada. Los totales 80 y 30 se conocen independientemente del agente y se contrastan con las referencias numéricas del informe; no bastó con aceptar su texto.

Una prueba real adicional entregó en la memoria una nota que pedía ignorar el sistema, abandonar JSON y acceder a otro negocio. El resultado guardado conservó el plan estructurado, citó la definición válida y no siguió esa instrucción ni repitió la pregunta. El verificador de esta prueba tuvo una incidencia de serialización de UUID; se corrigió la comprobación y se verificó la salida ya guardada, sin atribuir el fallo del verificador al producto. Un caso no garantiza resistencia general a instrucciones maliciosas.

## Evaluación de búsqueda y decisión semántica

Sobre la descripción «Ventas de productos en junio», PostgreSQL recuperó la tabla con `venta`, `productos` y `ventas junio`: **3 de 3 variantes léxicas**. `facturación mercancías` no la recuperó: **0 de 1 paráfrasis por sinónimos**. Abrir el catálogo sin consulta sí conservó la referencia: **1 de 1 recuperación alternativa**. Las pruebas de antecedentes comprueban también exclusión por periodo y vigencia.

**Decisión:** aplazar embeddings para este incremento pequeño, donde el catálogo y las relaciones explícitas permiten inspeccionar los conjuntos disponibles. No presentar el buscador como semántico ni asumir que entiende sinónimos. La evaluación de fragmentos de chats de 2.5.4 deberá ampliar casos y tamaños; si la búsqueda más el catálogo omite contexto útil, añadir el índice derivado según el diseño acordado. El límite de catálogo/candidatos y la ausencia de paginación general siguen explícitos.

## Comprobación en navegador

En una base de prueba independiente, con datos y modelo controlados:

1. Informe disponible antes del cambio.
2. Corrección mediante el servicio de memoria: el informe desaparece de la vista publicable, aparece el motivo y **Recalcular con la memoria actual**.
3. Pulsar el botón deja el trabajo **En cola** y la página sigue consultando el progreso.
4. El nuevo informe aparece automáticamente, conservando los identificadores y el histórico anterior en PostgreSQL.

Esta prueba detectó un estado intermedio que detenía la actualización de la página; se corrigió y volvió a observar el recorrido completo. La comprobación visual usa el servidor de pruebas en el puerto 8793 y no datos privados del negocio de trabajo. Al terminar se reinició la vista local anterior del puerto 8792 con el código actualizado; no tenía trabajos en curso y la migración conservó su estado.

## Límites y siguiente paso

No hay todavía chat persistente, ficha editable completa, dashboard nuevo ni combinación general de tablas: corresponden a 2.5.4–2.5.6. El formulario actual no establece un periodo estructurado; se conserva desconocido, con invalidación conservadora. El servicio acepta intervalos explícitos, probados con junio/septiembre. No hay compresión automática de contexto; si no caben dudas materiales hay que acotar. Los informes descargados con anterioridad siguen siendo instantáneas y no pueden revocarse retroactivamente.

La corrección temporal requiere una fecha explícita y no sustituye una evaluación de todas las interpretaciones posibles de lenguaje natural. Los modelos pueden equivocarse en significado o alcance; estas pruebas no equivalen a aceptación general del producto. El próximo paso es conectar mensajes y fragmentos de conversación a este mismo selector/manifiesto en **2.5.4**, con su propia evaluación de recuperación.
