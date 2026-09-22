# Informe del cliente — paso 1.6

El análisis conserva un registro persistente y genera dos presentaciones de la
misma revisión. No son dos análisis independientes ni una caché desechable.

- `report.html`: informe del cliente con pregunta de negocio, periodo, cobertura,
  resumen, hallazgos, gráficos, interpretación, siguientes comprobaciones y evidencia.
- `internal.html`: registro de desarrollo con decisiones del analista y revisor,
  aclaraciones, comprobaciones, resultados antiguos y código ejecutado.
- `review.json`: instantánea estructurada para inspección técnica.

`report-export` genera los tres archivos privados. Su respuesta mantiene `path`
para el informe del cliente y añade `internal_path`; `audit_path` conserva el JSON.
Un informe bloqueado, obsoleto o sin aprobación muestra únicamente un estado
pendiente y las preguntas al propietario, nunca sus conclusiones provisionales.
La vista interna sí conserva el borrador para depurarlo.

## Contenido y revisión

El principal prepara el contrato `ReportDraft`. `scope` contiene negocio, pregunta,
periodo y cobertura. Cada hallazgo incluye observación, interpretación, siguiente
comprobación opcional y explicación sencilla del cálculo, además de referencias a
métricas guardadas. No se inventan nombre del negocio, moneda, causas, beneficios
ni actuaciones para rellenar apartados. Se mantiene el límite de seis hallazgos
por informe de esta primera implementación.

Los gráficos también forman parte del borrador que recibe el revisor. Este debe
comprobar etiquetas, unidades, comparabilidad, selección, interpretaciones y
siguientes pasos, además de las cifras. Sus objeciones vuelven al analista por el
mismo diálogo persistente. El principal puede ejecutar Python antes de presentar
el informe para obtener las métricas necesarias. La aplicación no añade narrativa
ni conclusiones nuevas después de la aprobación.

## Gráficos y tablas

Componentes disponibles: tarjetas de cifras, barras, líneas diarias y tablas.
Las tarjetas (`highlights`) referencian una métrica y un hallazgo. Los gráficos
aparecen antes de los hallazgos y enlazan con su explicación y evidencia.
Cada gráfico puede referenciar una serie completa mediante
`series: {execution_id, series}`, con `points: []`. La aplicación conserva todos
sus valores, etiquetas y unidad. Alternativamente, cada punto contiene una
referencia `{execution_id, metric}`, con `series: null`, nunca un valor numérico escrito por el modelo.
La aplicación resuelve y formatea la cifra desde la evidencia vigente. Cada gráfico
pertenece a un hallazgo y declara unidad, título y explicación de cobertura.

Límites: cuatro gráficos. Las referencias escalares admiten hasta 36 puntos por
gráfico y 72 en total; las series diarias admiten hasta 366 puntos y las barras o
tablas hasta 36 categorías/periodos. Las
líneas requieren fechas ISO únicas y ordenadas; se respetan las distancias reales
entre fechas y se interrumpe la línea cuando falta un día. Para intervalos mensuales
u otros agregados, usar barras o tablas en esta versión. Las barras incluyen cero
y admiten negativos. El redondeo de presentación usa Decimal, mitad hacia arriba.
No se transforma una fecha ausente en una venta cero.

Las referencias inexistentes, obsoletas, sin evidencia o no numéricas bloquean el
gráfico. Las fuentes citadas solo por gráficos también entran en la huella de la
aprobación. La correspondencia semántica de una etiqueta, unidad o recomendación
sigue necesitando revisión; la validación estructural no demuestra esa corrección.
Si no hay una comparación útil, el analista explica por qué no incluye gráficos.
Que una serie todavía no se haya calculado no justifica omitir una visualización
útil cuando los datos permiten obtenerla. El revisor debe pedir que se complete.

### Guardar series desde Python

`write_result(metrics, evidence=evidence, notes=notes, series=series)` conserva
las métricas escalares y añade opcionalmente un diccionario de series. Cada una
incluye `unit`, `grain` (`day`, `month` o `category`), `points` con `label`/`value`
y `evidence` con `tables`/`operation`. Las operaciones deben explicar agregación,
filtros y selección. Los valores son finitos; las etiquetas son únicas y las
fechas están ordenadas. Máximo cuatro series por ejecución, 366 puntos por serie
y 800 puntos en total. No se truncan silenciosamente: se debe agregar en Python.
Los contextos conservan resultados hasta 64 KB, dentro del límite global de 200 KB.
Al actualizar desde la versión anterior, reconstruir la imagen con
`.venv/bin/python scripts/dev/local_sandbox.py build` para incorporar el nuevo
argumento `series` de `dr_runtime.write_result`, y reiniciar el servidor web
cuando no haya análisis en ejecución.

`question_coverage` vincula cada investigación lista con los hallazgos que la
responden o documenta que no se puede responder. El controlador exige todas las
claves y referencias; el revisor comprueba la correspondencia semántica y el
objetivo original. La existencia de ese campo no demuestra por sí sola utilidad.

El HTML usa SVG construido por la aplicación y tablas de valores accesibles por
teclado. No admite SVG, HTML, URLs o JavaScript generados por el modelo. No necesita
red, servidor ni dependencias nuevas. Los textos se escapan, hay CSP, etiquetas
accesibles, estilos móviles e impresión. No se añaden vídeos ni dashboard al MVP.

## Compatibilidad y archivos

Esta ampliación usa prompts `review-v9` y `research-v6`, sin cambiar la estructura
del grafo. Los campos nuevos conservan valores vacíos por defecto para leer los
informes anteriores. Las nuevas respuestas del modelo los incluyen explícitamente.
No se convierte una aprobación antigua en aprobación del contenido nuevo.

- `decision_room/agent/review_contract.py`: contenido y comprobaciones.
- `decision_room/agent/review_prompts.py`: instrucciones de negocio y revisión.
- `decision_room/agent/review_context.py`: huella con evidencia de gráficos.
- `decision_room/client_report.py`: componentes del cliente y formato de cifras.
- `decision_room/internal_report.py`: presentación del registro interno.
- `decision_room/report.py`: exportación privada de ambas vistas y JSON.
- `tests/test_client_report.py`: publicación, trazabilidad y representación.
- `decision_room/series.py` y `tests/test_series.py`: contrato de series y regresiones.

La entrega 2 integra estos resultados en el recorrido web de subida, preguntas y
consulta. Ver la [prueba con 36.331 filas](../validation/2026-09-22-visual-report-check.md).
Las copias exportadas son instantáneas fechadas: no se revocan ni actualizan solas.


## Ejemplo de referencia y prueba autónoma

`scripts/checks/check_client_report.py --business ID --research ID` utiliza la
investigación guardada del caso `01-daily-sales`, prepara cálculos y contenido
controlados y los entrega al revisor real. Registra `fixture_seed: true` en las
acciones del analista. Si el revisor plantea una objeción, retira el borrador en
vez de repetirlo hasta obtener aprobación. Es una prueba de presentación e
integración, **no una prueba de autonomía del analista**.

Para probar ambos roles reales, utilizar `scripts/checks/check_review.py`.
Los resultados y fallos observados se documentan en la
[validación del informe](../validation/2026-09-21-client-report-check.md).
