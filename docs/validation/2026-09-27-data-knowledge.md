# Paso 3.2 — catálogo persistente y diagrama ER

**Completado, 27 de septiembre de 2026.**

## Entrega

Modelo estructurado y versionado de tablas, columnas, claves, relaciones y
métricas; recuperación compartida por informes y chat; diagrama y aclaraciones
en «Mi negocio → Datos y versiones»; revalidación de archivos nuevos e
invalidación de resultados dependientes. [Contrato y límites](../technical/data-knowledge.md).

También se corrigen las recuperaciones nulas/identificadores inválidos detectadas
en 3.1 y se incorporan hasta dos reintentos ante un HTTP 503 explícito.

## Base sustancial

Fuente: los CSV públicos de Microsoft Wide World Importers preparados en el
repositorio; atribución y descarga en [su README](../../data/wide-world-importers/README.md).
No se incorporan los archivos grandes a Git.

| Comprobación | Resultado |
|---|---:|
| Tablas preparadas y perfiladas | 48 |
| Filas, incluidas tablas históricas | 4.713.833 |
| Importación y perfilado, una ejecución local | 29,928 s |
| Relaciones inferidas por nombre de entidad | 71 |
| Comprobación técnica sin multiplicación ni filas huérfanas | 64 |
| Relaciones cuyo significado sigue propuesto | 71 |
| Claves foráneas declaradas en el modelo original contrastadas | 98 |
| Claves de destino duplicadas / filas huérfanas en esas 98 | 0 / 0 |
| Inspecciones por tabla dentro del límite de recuperación | 48 / 48 |

Las 98 relaciones del esquema original se leen por separado como referencia de
validación; no se atribuyen al descubrimiento automático. Los 71 enlaces
propuestos no se presentan como semánticamente confirmados. Se conserva la
separación entre inferencia, declaración y evidencia técnica.

En la unión `Sales.InvoiceLines → Sales.Invoices`, las 228.265 líneas encuentran
su factura entre 70.510 cabeceras: la unión conserva 228.265 filas, sin
multiplicación ni filas sin correspondencia. La inspección del asistente y el
modelo del diagrama coinciden en revisión y relaciones.

Reproducción del perfil y contraste con el esquema público:

```sh
.venv/bin/python -m decision_room.evaluation.data_catalog \
  --output .local/evaluation/catalog-nueva-ejecucion
```

Requiere PostgreSQL local, los CSV exportados y el BACPAC público. Crea una base
**aislada**, conserva sus datos localmente y no modifica el negocio activo de la
aplicación habitual.

## Informes reales y reutilización

Se utilizó el proveedor/modelo ya configurado (`gpt-6-luna`, razonamiento bajo),
con cinco tablas y 299.673 filas. La petición solo pidió comparar 2014 y 2015 y
reutilizar las definiciones guardadas. La fórmula y las convenciones se guardaron
una vez en el catálogo: ventas netas = `ExtendedPrice - TaxAmount`, margen bruto
monetario = `LineProfit`, porcentaje = margen / ventas netas; fechas por
`InvoiceDate`, signos conservados y moneda sin declarar.

| Ejecución final | Resultado antes de la corrección deliberada | Tiempo | Nuevas preguntas |
|---|---|---:|---:|
| Primer informe | Aprobado y publicable | 97,906 s | 0 |
| Segundo informe | Aprobado y publicable | 62,934 s | 0 |

Ambos recuperaron la revisión 3 del mismo catálogo. Se verificaron de forma
independiente **22 valores citados o representados** contra el cálculo CSV/Decimal
fuera del contexto del modelo. Totales comprobados:

| Métrica | 2014 | 2015 |
|---|---:|---:|
| Ventas netas | 49.929.487,20 | 53.991.490,45 |
| Margen bruto monetario | 24.828.462,45 | 26.957.600,65 |
| Porcentaje de margen bruto | 49,72705277 % | 49,92935076 % |

Otro chat real recuperó y explicó las tres fórmulas y el enlace
`InvoiceLines.InvoiceID = Invoices.InvoiceID`, citó la inspección y terminó sin
crear un nuevo informe (`job_id=null`).

Después se aclaró la granularidad de las líneas, creando la revisión 4. Los dos
informes pasaron a `stale`, dejaron de ser publicables y conservaron exactamente
sus huellas de aprobación anteriores. El contexto del chat anterior dejó de
considerarse vigente. Esto comprueba propagación sin reescribir la historia.

### Fallos conservados durante el desarrollo

No se presenta una selección de los éxitos como una nueva tasa de aceptación:

- Dos intentos iniciales revelaron que el plan no admitía referencias del nuevo
  catálogo. Se añadió `kind=data_model`, referencias entregadas y validación de
  ámbito/estado. Las referencias inventadas, ajenas o inferidas siguen rechazadas.
- Los dos intentos siguientes usaban una definición de prueba que explicaba
  impuestos e importes, pero no definía explícitamente «ventas netas». Uno retiró
  el informe; el otro bloqueó la investigación sin registrar candidato. Se
  corrigió **la declaración de la prueba**, haciendo explícita la fórmula, antes
  de las dos ejecuciones finales de la tabla anterior.
- La primera de esas ejecuciones incompletas también mostró límites del bucle de
  revisión al recalcular después de respuestas insuficientes. La mejora de
  investigación por rondas y selección final sigue correspondiendo a 3.3/3.5.

El lote original 3.1 permanece intacto. Esta comprobación acredita reutilización,
citas y vigencia del catálogo; no demuestra por sí sola una mejora general en
calidad de insights ni cierra la evaluación final de 3.5.

## Pruebas automatizadas y visuales

- **54 pruebas Python** en la regresión final: catálogo, claves simples/compuestas,
  muchos a muchos, vacíos, claves duplicadas, ceros iniciales, revalidación,
  aislamiento, HTTP/autenticación, edición concurrente, citas, dos informes
  completos con ejecución real en Docker, historial, recuperación de las dos
  peticiones inválidas de 3.1 y reintentos 503/uso de tokens incompleto.
- Además pasaron los bloques de regresión de web/revisión (**38 pruebas**) y de
  conversaciones/contexto (**92 pruebas**, con solapamiento; no se suman como
  pruebas únicas).
- **65 pruebas frontend**; tras el ajuste final de anchura y campos editados,
  repetidas las **2 pruebas dirigidas** del modelo ER. Compilación TypeScript/Vite
  correcta. Lint sin errores, con avisos previos en otros componentes.
- Chrome: navegación a la ficha, búsqueda, foco en líneas de factura, inspección
  mediante teclado, formulario de relación y guardado efectivo de revisión 2.
- A 390 px, corregida la propagación del ancho mínimo del SVG: tarjetas de
  350/318 px y mapa de 640 px dentro de su contenedor desplazable de 286 px;
  documento de 390 px. Se restaura el tamaño del navegador después de la prueba.

Comandos principales:

```sh
PYTHONPATH=tests .venv/bin/python -m unittest \
  test_data_knowledge test_model_retry test_agent test_context_memory \
  test_review_context test_conversation_context test_evaluation_resources
npm --prefix frontend test
npm --prefix frontend run build
npm --prefix frontend run lint
git diff --check
```

Evidencia privada: `.local/evaluation/catalog-32/`: modelo completo, comprobaciones
de las 98 claves, intentos reales conservados, oráculo independiente, 22 contrastes
numéricos, recuperación del chat, corrección y registros de pruebas. Los CSV,
originales y estados de ejecución permanecen ignorados por Git.
