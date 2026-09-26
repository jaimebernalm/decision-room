# Conversación autónoma con fuentes · 25 de septiembre de 2026

## Alcance

Ampliación de 2.5.4 según el [plan](../technical/autonomous-chat-plan.md).
`conversation-v5` permite consultar herramientas, solicitar investigación o responder
con prosa propia. El contrato del proveedor ya no ofrece `remember`, respuestas de
catálogo prefabricadas ni categorías de saludo/agradecimiento. Se conservan respuestas
históricas y la salida revisada del pipeline de nuevos cálculos.

## Comprobaciones automatizadas

- Regresión general inicial: 261 pruebas Python; 260 correctas y un error en el fixture
  que simula una migración antigua, porque no eliminaba la nueva tabla dependiente
  `chat_answer_reviews`. Se actualizó explícitamente ese fixture.
- Verificación final dirigida: 39 pruebas correctas (34 conversaciones, 4 contratos
  del modelo y el caso de migración corregido). Incluyen inspección de CSV, continuidad,
  rechazo de referencias inventadas y borradores sin respaldo, recuperación tras revisión
  incierta, replay sin llamadas duplicadas, fuente corregida, hallazgo/version exactos,
  exportación de informe, protección entre negocios y consultas repetidas.
- 15 pruebas JavaScript correctas, incluida salida con negrita, código, listas y HTML
  malicioso escapado. `node --check`, compilación Python y `git diff --check` correctos.
- Los errores inyectados en las pruebas producen trazas esperadas; no se interpretan como
  fallos de la suite. Los tests con proveedores simulados verifican contratos y persistencia,
  no calidad semántica del modelo.

## Modelo real

Proveedor OpenAI, modelo configurado `gpt-6-luna`; prompts y resultados conservados en el
almacenamiento privado local, sin credenciales ni datos del espacio de trabajo en Git.

1. Recorrido exploratorio de ocho turnos: saludo, petición informal de cortesía, datos
   disponibles, referencia «ellos» al CSV, significado de una columna, fecha, información
   reciente y explicación de su procedencia. El caso del CSV abrió el archivo correcto
   una vez y describió filas/columnas/ejemplos. Saludó y continuó con lenguaje propio.
2. Este recorrido detectó dos límites: uso de extractos de búsqueda como evidencia final y
   revisión demasiado restrictiva de ofertas de ayuda. Se aclaró que las búsquedas de
   informes son descubrimiento, se exige abrir el original y se entrega al revisor la
   capacidad real de analizar archivos. No se presenta ese primer recorrido como aceptación
   completa de los informes.
3. Repetición de los dos turnos sobre actualidad y procedencia: búsqueda → apertura del
   informe → respuesta breve; el seguimiento volvió a abrir el mismo informe. Ambos
   aprobados, sin trabajo analítico nuevo y conservando periodo y límites de cobertura.
4. Recorrido completo en PostgreSQL y almacenamiento temporales, con el proveedor real:
   saludo → archivos → «y q hay en ellos?» → declaración de cierre dominical → pregunta
   sobre el horario en otro chat. Los cinco turnos terminaron correctamente, persistieron
   al consultar de nuevo y usaron `grounded_answer`. La memoria se reutilizó entre chats.
   Se registraron 8 decisiones, 7 revisiones y 1 consulta de herramienta; los borradores
   rechazados no se publicaron. La instancia de prueba se eliminó al terminar.

## Navegador y aplicación local

Instancia local reiniciada con el mismo almacenamiento y configuración de modelo. En el
navegador se creó una conversación de comprobación: «Hola, ¿qué archivos tenemos disponibles?»
y «y q hay en ellos?». El primer mensaje listó el CSV; el segundo lo inspeccionó y describió
sus columnas y ejemplos, con fuentes visibles. Verificado visualmente el formato de texto,
negrita y nombres de columnas. Las conversaciones anteriores se conservaron.

## Límites

- Un segundo pase del modelo comprueba pertinencia y significado de las fuentes; no es
  una garantía formal de veracidad. Aumenta el tiempo y consumo por respuesta.
- La muestra de conversación real es pequeña y debe ampliarse con uso. Se conservan
  límites de contexto, 12 continuaciones, un lote por investigación y ausencia de web.
- Los turnos antiguos mantienen sus respuestas guardadas. El nuevo comportamiento se
  aplica a nuevos mensajes. Las dependencias de las respuestas nuevas se comprueban
  al publicar y al reabrir; una corrección no convierte una respuesta antigua en vigente.
- El historial reciente conserva mensajes del propietario y oculta respuestas desactualizadas;
  las citas históricas nunca sustituyen a la memoria o evidencia actual.
