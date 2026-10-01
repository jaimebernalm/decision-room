# Validación de edición compartida · 2.5.18

Fecha: 30 de septiembre de 2026. Entorno local independiente de UX.

## Resultado

Completados los tres pasos del
[plan](../technical/presentation-editing-plan.md): nombres automáticos del
catálogo, edición directa y corrección de la presentación existente desde el chat.
Inicio, informe, HTML y PDF utilizan la misma presentación. Cada cambio guarda
una revisión independiente del informe analítico aprobado.

- Correspondencias obtenidas de catálogos completos del mismo negocio y conjunto,
  con relación comprobada, integridad, clave única y una columna de nombre.
  Se excluyen relaciones rechazadas, archivos alterados y códigos ambiguos.
- Editor contextual de títulos, nombres y formato de cifras. Un alias de entidad
  se refleja en todas las apariciones de ese código dentro del mismo informe.
  Se conservan códigos originales, claves estables, valores exactos y fuentes.
- Historial persistente con consulta previa y restauración como revisión nueva.
  Control optimista de versión e idempotencia; dos escritores simultáneos no
  sobrescriben silenciosamente sus cambios.
- El chat elige un elemento del catálogo autorizado, revisa la petición actual
  y guarda cambio y recibo en una misma transacción. Una pregunta sobre opciones
  no guarda cambios; un conflicto o campo inválido no produce un recibo de éxito.
- Las vistas permiten lectores concurrentes y mantienen la exclusión del escritor
  analítico. Se vuelve a comprobar publicación, negocio, eliminación y aprobación
  también al consultar una presentación histórica o exportar.

## Pruebas automatizadas

Todas las comprobaciones indicadas finalizaron correctamente. Las suites backend
comparten algunos casos; sus cantidades no se suman como pruebas distintas.

| Comprobación | Resultado |
| --- | --- |
| `test_presentation_editing test_presentation_chat test_conversations test_web test_report_pdf` | 122 pruebas |
| `test_memory test_model_actions test_model_wire_schema test_context_references test_presentation_chat` | 57 pruebas |
| `test_presentation_editing test_home`, tras la corrección final de claves numéricas | 19 pruebas |
| Exportación HTML con texto escapado, gráficos de líneas/barras y valores exactos | Correcta |
| Frontend: `npm test -- --reporter=dot` | 117 pruebas, 19 archivos |
| Frontend: `npm run build` | Correcto; aviso existente de tamaño de chunks |
| Frontend: `npm run lint` | Correcto; avisos existentes de Fast Refresh |
| Revisión de diferencias: `git diff --check` | Correcta |

Los casos incluyen aislamiento entre negocios, publicación retirada, eliminación,
reenvío idempotente, edición concurrente, rollback si no puede publicarse el recibo,
unidades incompatibles, conservación de cantidades y previsualización decimal sin
conversión a coma flotante. Los códigos numéricos, incluido cero, se resuelven como
dimensiones y no sustituyen cantidades dentro de la prosa.

## Aceptación con Bruma y GPT-6 Luna

Se utilizó el informe existente y los archivos locales de demostración, sin
recalcular ni sustituir su evidencia original.

1. Se comprobaron los seis productos y tres canales desde sus catálogos completos.
   Inicio muestra, por ejemplo, «Kit de iniciación en Web propia» y
   «Café de la casa 250 g total», con sus cantidades originales.
2. Desde el lápiz de Inicio se cambió un título de gráfico y se verificó en el informe.
3. GPT-6 Luna guardó el título «Unidades por mes y canal» del gráfico seleccionado.
   Se comprobó el recibo del servidor y la misma revisión en las vistas.
4. GPT-6 Luna guardó un alias de producto; el botón de deshacer del chat recuperó
   el nombre del catálogo como revisión nueva. Al recargar, los recibos anteriores
   aparecen como «Versión anterior» y no ofrecen deshacer sobre una revisión nueva.
5. Una pregunta que pedía exclusivamente explicar las opciones terminó sin
   cambiar la presentación ni crear hechos del negocio.
6. Se comprobaron previsualización, nombres e historial en escritorio y a
   390 × 844: diálogo y botones dentro de la pantalla, sin desbordamiento horizontal.
   Se cancelaron las previsualizaciones sin guardar y se restauró el tamaño normal.
7. HTML y PDF real de seis páginas contienen los nombres actuales y ambos títulos
   editados. El hash de aprobación analítica sigue siendo el original; la métrica
   de 410 conserva su valor exacto original. Ocho lecturas simultáneas alternando
   Inicio e informe devolvieron 200.

La aceptación deja los nombres originales del catálogo y los dos títulos mejorados.
Los chats anteriores del usuario permanecen disponibles. Capturas, PDF, archivos,
credenciales y resultados detallados se conservan solamente en el entorno privado.

## Fallos encontrados y corregidos

La primera petición real de alias se clasificó erróneamente como contexto duradero
del negocio y dejó el informe desactualizado antes de editarlo. Se corrigió el
contrato de extracción de memoria para distinguir preferencias de presentación de
declaraciones comerciales. Las pruebas cubren también mensajes mixtos y correcciones
reales del significado de un producto. El reintento con el modelo real y la pregunta
posterior produjeron `presentation_only=true`, sin candidatos ni cambios de memoria.

La recuperación local revirtió únicamente las revisiones de memoria creadas por
esa prueba fallida, con copia privada y comprobación de que no existían cambios
legítimos posteriores. Antes de recuperar la disponibilidad del informe se
comprobaron huellas de las fuentes, contexto, conocimiento, verificaciones y hash
original de aprobación. No se añadió una excepción de publicación al producto.

También se detectaron y corrigieron la serialización de fechas del historial,
una exportación HTML que utilizaba los títulos antiguos y el conflicto entre
lectores al abrir varias vistas. La prueba del HTML real permitió corregir el
consumo de los diagramas de barras antes de cerrar la aceptación.

## Límites de esta edición

La edición de presentación admite títulos, nombres, decimales y variantes de una
misma unidad. Cambiar cantidades, fórmulas, significado de unidades, cobertura o
explicaciones factuales requiere la corrección del análisis. No se eliminan las
limitaciones de la evidencia aprobada. Los alias pertenecen al mismo informe y
no se propagan silenciosamente a informes o conjuntos distintos.
