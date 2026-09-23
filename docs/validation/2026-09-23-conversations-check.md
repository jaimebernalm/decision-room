# Validación de conversaciones · 2.5.4

**Fecha:** 23 de septiembre de 2026.  
**Resultado:** incrementos A–D implementados y comprobados. Se mantiene pendiente la ficha completa de 2.5.5 y el dashboard de 2.5.6.

## Pruebas automatizadas

- Suite general: **230 pruebas aprobadas** (`unittest discover`), incluyendo PostgreSQL real, migración desde esquema anterior y repetición/rollback, aislamiento, extracción de memoria, selección de contexto, ejecución analítica, revisión y HTTP.
- Ronda final específica: **17 pruebas de conversaciones aprobadas**, incluyendo dos casos añadidos tras la suite general: reintento analítico obsoleto conservando la respuesta anterior y descubrimiento de un informe desde un chat sin conjunto seleccionado. Total combinado: **232 pruebas distintas aprobadas**.
- Sintaxis JavaScript (`node --check`), revisión estática de los nuevos módulos Python y `git diff --check` correctos.

Los casos de conversación cubren mensajes persistidos antes de procesar, doble envío concurrente, rechazo de cambios de contenido con la misma clave, orden, recuperación de una llamada completada sin volver al proveedor, petición incierta y reintento explícito, doble reintento, aislamiento de negocios/conjuntos, cambios durante la llamada, memoria entre chats, corrección y retirada, aclaraciones analíticas, continuación de contexto al planificador, respuesta revisada, explicación del mismo informe, exportación explícita y versión exacta del resultado citado. La ronda final comprueba también que el turno conserva su respuesta anterior al recalcular y que un nuevo chat puede abrir antecedentes con su ámbito original antes de seleccionar datos.

## Modelo real

Proveedor OpenAI, modelo **gpt-6-luna**, razonamiento bajo; datos sintéticos y base temporal aislada. No se utilizaron datos privados del espacio de trabajo.

El recorrido final de `scripts/evaluate_conversations.py` pasó sus cinco comprobaciones en aproximadamente 107 segundos, con 10 llamadas del enrutador de chat, además de extracción, agentes analíticos y embeddings:

1. Declarar el cierre dominical y consultarlo desde otra conversación sin repetirlo.
2. Reutilizar un CSV existente con filas `(quantity=2, amount=10)` y `(quantity=3, amount=20)`, definido como precio unitario: resultado revisado **80**, sin nueva subida ni publicación automática del informe.
3. Abrir el resultado anterior y explicar sus afirmaciones exactas, sin crear otro cálculo; generar y abrir el informe vinculado bajo petición.
4. Corregir el horario, confirmar la alternativa y reutilizarla en un nuevo chat; ocultar como obsoleta la respuesta dependiente del contexto anterior.
5. Recuperar mediante `search_chats` una hipótesis sobre agrupar cobros por semana a partir de una consulta reformulada sobre consolidar ingresos semanalmente; citar el mensaje original. La recuperación registró modo **hybrid**, con OpenAI embeddings y pgvector.

La petición hipotética puede producir una pregunta aclaratoria del analista: es un resultado válido y queda como antecedente recuperable, sin convertir la hipótesis en declaración de memoria.

Se volvió a ejecutar la evaluación de extracción existente con el prompt `memory-v2`: **24/24 casos aprobados** (ocho casos, tres repeticiones). Incluye definiciones de campos, disponibilidad, fechas futuras/ambiguas, hipótesis, contradicciones, retirada, instrucciones citadas y reformulaciones equivalentes. Una ejecución preliminar identificó una definición fiscal clasificada como contexto; se precisó el contrato de tipos antes de la ronda final.

Los registros completos de llamadas, contexto, recuperaciones e intentos fallidos de desarrollo quedan en `.local/`, fuera de Git. El evaluador es reproducible mediante el comando del [contrato técnico](../technical/conversations.md).

## Navegador y actualización local

Se comprobó en el navegador una base sintética aislada: creación de chat, envío, estado en curso, recarga conservando el mensaje, conflicto de memoria, elección explícita de la corrección y lectura del recuerdo corregido en otro chat. Se inspeccionó la presentación visual y se ajustaron espaciado y etiquetas.

Se actualizó el servidor de vista previa existente después de comprobar que no había análisis en curso. Se conserva su base de datos y conexión de TablePlus. La nueva sección «Conversaciones» abre correctamente sobre ese espacio, sin añadirle los datos sintéticos de las pruebas.

## Límites prácticos

- Las explicaciones son selecciones de afirmaciones revisadas y sus cifras citadas. La primera versión prioriza trazabilidad sobre redacción libre.
- Una consulta por un horario puede responder con lo conocido —por ejemplo, que se abre el domingo— sin inventar horas de apertura/cierre que el cliente no haya declarado.
- La revisión de memoria invalida conservadoramente fragmentos históricos de chat; puede omitir antecedentes no afectados. Los originales se conservan. Las aclaraciones propias de una sesión analítica se distinguen para no invalidar su continuación por el mero hecho de responderlas.
- Sin conjunto seleccionado se permite descubrir antecedentes del mismo negocio, indicando el conjunto original. Con un conjunto seleccionado se excluyen los de otros conjuntos. La similitud no confirma hechos ni autoriza combinar fuentes.
- El caso semántico real es una comprobación de integración pequeña, no una evaluación general de precisión del buscador ni del producto completo.
- La gestión completa de archivos/recuerdos y la navegación definitiva siguen en los pasos siguientes.
