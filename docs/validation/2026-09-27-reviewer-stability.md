# Validación del refuerzo del revisor — 3.3.1

Fecha: 27 de septiembre de 2026. Rama: `feature/insights-pipeline`.

## Qué se comprueba

El [contrato](../technical/reviewer-stability.md) separa bloqueos de sugerencias,
conserva reparos entre rondas, exige auditoría de la entrega, reutiliza cálculos y
acota reintentos 429/503. Se prueba antes de continuar con el onboarding 3.4.

## Pruebas automatizadas

- **348 pruebas** de la batería completa pasan en **189,020 s**.
- Después de añadir dos casos específicos de interrupción/presupuesto y de aclarar
  las reparaciones factibles: **81 pruebas dirigidas**, **66,746 s**, correctas.
- Con las instrucciones finales sobre alcance observado: **26 pruebas dirigidas**,
  **18,234 s**, correctas; incluyen revisión, investigación parcial, recuperación y HTTP.
- Compilación Python y `git diff --check` correctos.

Las pruebas con PostgreSQL y Docker comprueban:

- No aprobar un bloqueo abierto, una auditoría fallida o una valoración de otro
  borrador. No eliminar reparos por omisión; justificar cierres y reparos tardíos.
- Permitir aprobación con sugerencias abiertas; impedir revisiones motivadas solo
  por ellas. Mantener al revisor como única autoridad para resolver reparos.
- Reutilizar cálculos válidos y permitir comprobación independiente o recálculo
  después de una corrección del propietario.
- Resolver puntos de series del manifiesto desde evidencia y exportar el informe
  completo con el total de prueba 80, calculado de forma independiente.
- Tres rechazos 429, conservación del borrador, recuperación sin repetir Python,
  acumulación de llamadas fallidas y ausencia de llamadas al reanudar una aprobación.
- Interrupción durante la espera: el primer rechazo ya está guardado; reanudar sin
  autorización de petición incierta se bloquea, y la recuperación explícita conserva
  los tres registros de llamada (completada, interrumpida, completada).
- Agotamiento del presupuesto al reanudar: estado `limited`, sin petición adicional,
  borrador conservado y sin aprobación.
- `Retry-After` numérico, fecha, inválido, infinito y excesivo; errores permanentes
  y lecturas inciertas sin reintento automático. Regresión de 503 y contabilización
  de uso desconocido en los intentos rechazados.

Los roles programados de estas pruebas validan mecanismos, no calidad del modelo.
La batería incluye las pruebas anteriores de caída real de proceso tras decisiones
persistidas y tras ejecución Python, sin duplicar llamadas ni ejecuciones.

## Datos y evaluación con modelo real

Se reutilizan las investigaciones guardadas en la evaluación 3.3, sin repetir
importación ni investigación: cinco tablas de Microsoft Wide World Importers,
**299.673 filas**, años 2014 y 2015. Modelo: **GPT-6 Luna**, razonamiento `low`.
Base y almacenamiento de evaluación aislados; no se modifican negocios del usuario.

La referencia independiente procede de CSV y aritmética Decimal del evaluador
3.1. Se verifican métricas citadas y puntos de gráficos, y se inspeccionan la
cobertura, prosa y entrega HTML. El oráculo no se proporciona al modelo. Los
nombres «complete»/«partial» de los directorios designan casos de entrada y no
presuponen aceptación ni el grado final de cobertura.

### Intentos conservados y correcciones

| Versión de instrucciones | Caso | Resultado observado |
| --- | --- | --- |
| `review-v20` | Candidato a completo | `limited`: 14 llamadas, 224,784 s, una ejecución nueva. El revisor pide 20 referencias en un hallazgo limitado a 12; el analista dice corregirlas, pero no las incorpora. No se aprueba. Se registran nueve rechazos HTTP recuperados; su consumo no es conocido. |
| `review-v20` | Parcial | Aprobado en 4 llamadas y 41,520 s, sin nuevo Python. **47 valores** contrastados. |
| `review-v21` | Candidato a completo | Aprobado en 4 llamadas y 53,815 s, sin nuevo Python; **41 valores** correctos. Independientemente no se acepta como informe completo: el revisor convierte la ausencia de certificación del origen en 0/2 preguntas respondidas pese a disponer de comparaciones de los datos aportados. |
| `review-v21` | Parcial | **46 valores** contrastados. El revisor detecta que la prosa afirma contribuciones negativas en un gráfico cuyos cinco valores son positivos; se corrige sin recalcular. |

`review-v21` explicita los límites de estructura y las reparaciones factibles:
dividir hallazgos o usar series, conservando evidencia. `review-v22` distingue una
comparación sobre el conjunto aportado de una auditoría de integridad del origen;
no obliga a declarar no disponibles todos los resultados por esa incertidumbre.
Se conservan los intentos anteriores y no se presentan como éxitos completos.

### Resultado final — `review-v22`

Huella del código Python estable durante ambas ejecuciones:
`dc7acec923788f009cc8ac0dbaaea4dab42a8f4b3981dcccebf072b96a15aff9`.

| Caso | Entrega | Llamadas | Python nuevo | Tiempo | Valores contrastados |
| --- | --- | ---: | ---: | ---: | ---: |
| Completo | Aprobado y aceptado independientemente, **2/2** preguntas | 5 | 1 | 68,449 s | **26**, todos correctos |
| Parcial | Aprobado y aceptado independientemente, **2/3** preguntas | 4 | 0 | 47,070 s | **23**, todos correctos |

El completo entrega evolución anual y contribuciones de productos con selección
explícita de cinco aumentos positivos. El parcial muestra evolución y contribuciones,
pero declara que el detalle de los 219 productos no está visible ni descargable.
Ambos conservan las limitaciones de cobertura del origen, moneda y causalidad.

Se comprueba además la selección y el orden de productos directamente contra el
oráculo: top cinco positivo en el completo y top cinco por magnitud absoluta en el
parcial. En los HTML exportados se verifican **24 valores de gráficos**, sus etiquetas,
la cobertura 2/2 y 2/3 y la ausencia de enlaces a CSV inexistentes. La prosa numérica
principal coincide con la referencia: ventas 49.929.487,20 → 53.991.490,45 y margen
bruto 24.828.462,45 → 26.957.600,65. No se atribuye causalidad comercial.

Las llamadas finales consumen **458.812 tokens de entrada y 15.806 de salida**
registrados, sin rechazos en estas dos ejecuciones. No se estima importe monetario.
La primera tanda registró rechazos recuperados, con consumo desconocido; no se
suman como si fueran peticiones gratuitas ni se oculta el coste de intentos previos.

### Prueba adversarial con modelo real

En una copia de contexto, sin publicar ni alterar el informe original, se introducen
simultáneamente dos falsedades en el resumen: ventas de 2015 de 99.999.999,00 y un
CSV supuestamente adjunto/descargable. En **una llamada de 5,354 s**, el revisor pide
corrección y registra **los dos bloqueos juntos**: contradicción con la métrica
53.991.490,45 y archivo ausente del manifiesto de entrega. Su auditoría marca cifras
y archivos como fallidos. Pasa también la validación estructural del controlador.
Este caso comprueba una intervención real del revisor, sin atribuirle infalibilidad.

Los registros locales están en `.local/evaluation/reviewer-331*`; no se suben
bases, datos, respuestas completas ni exportaciones a Git. La evaluación de
rondas original puede reproducirse con `decision_room.evaluation.research_rounds`.
Para aislar el revisor, invocar `review.start` con el negocio y `research_id`
guardados en cada `run-*/state.json`, un `request_key` nuevo y ambos roles con la
configuración guardada en el manifiesto; exportar solo cuando `publishable` sea
verdadero. No reutilizar la clave de una revisión anterior para sobrescribirla.

## Límites

No es una evaluación estadística general ni prueba de mejora universal de calidad;
es una comprobación dirigida de los fallos encontrados. La clasificación semántica
sigue dependiendo del modelo. El registro de reparos y las auditorías no convierten
sus valoraciones en pruebas independientes. Los límites de contexto, citas, gráficos,
llamadas y ejecución se mantienen. No se habilitan descargas de artefactos internos.
Los límites largos del proveedor pueden requerir reanudación posterior. La
comparación amplia por objetivos, utilidad, latencia y coste sigue en 3.5.

El servidor local que ya estaba atendiendo en el puerto 8787 no se reinició durante
esta evaluación. Las pruebas usan procesos nuevos y la versión modificada; el
servidor existente deberá reiniciarse para ejecutar estas mejoras en nuevos trabajos.
