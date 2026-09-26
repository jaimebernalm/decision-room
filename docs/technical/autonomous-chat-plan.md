# Evolución de 2.5.4: conversación redactada por el agente

Aplicado y validado el 25 de septiembre de 2026. Véase la [validación](../validation/2026-09-25-autonomous-chat-check.md).

## Objetivo

Sustituir la selección de respuestas predefinidas por un ciclo de consulta y redacción.
El agente decide qué necesita consultar y compone una respuesta pertinente al turno.
Las herramientas devuelven información al agente; no eligen el texto final del cliente.

## Plan de aplicación

1. Introducir un contrato pequeño: consultar herramienta, iniciar investigación o responder
   con texto propio y referencias. Retirar del esquema del proveedor `remember`, `catalog`,
   `reply_kind` y las variantes de saludo. Conservar decodificación histórica.
2. Conectar las herramientas existentes de archivos, memoria, informes y chats. Mantener
   ambos lados del historial reciente, nombres de archivos y columnas. Reutilizar resultados
   idénticos y limitar las continuaciones. La captura automática de memoria sigue siendo
   responsable de guardar/corregir; `search_memory` únicamente consulta.
3. Verificar referencias en servidor y revisar pertinencia y apoyo factual de la prosa
   mediante una llamada independiente. Rechazar cálculos nuevos sin investigación revisada,
   resultados basados solo en extractos de búsqueda y cobertura inferida de muestras.
   Persistir borrador, contexto, revisión y consumo. Revalidar dependencias al publicar/abrir.
4. Mostrar la respuesta redactada con formato seguro y fuentes; adjuntar evidencia original
   opcional, conservando la exportación explícita de informes.
5. Probar continuidad, errores, reintentos, aislamiento, cambios de fuentes, referencias a
   hallazgos y conversaciones reales; revisar diferencias y guardar un commit local.

## Decisiones

- `chat_agent.Decision` expresa operaciones y texto libre mediante el adaptador estructurado
  existente. No requiere migrar de proveedor ni incorporar otro framework. El bucle ejecuta
  herramientas y devuelve sus resultados hasta que el agente responde.
- Memoria persistente y contexto conversacional son mecanismos diferentes. El historial
  conserva hasta 12 intercambios, sustituyendo las respuestas desactualizadas por un aviso, con un límite explícito de texto por respuesta;
  `search_chats` recupera antecedentes. No se promete historial ilimitado.
- Guardar memoria conserva la extracción automática, fuentes, revisiones y resolución de
  conflictos existentes. No se añade otra escritura paralela ni una herramienta ambigua
  llamada `remember`. La respuesta puede confirmar el resultado real de la extracción.
- Se conservan permisos por negocio, UUID de idempotencia, revisión de versiones y pipeline
  de cálculos. La salida de un cálculo nuevo sigue siendo su resultado revisado; las preguntas
  de seguimiento pueden explicarlo con redacción propia.
- La nueva tabla `chat_answer_reviews` registra revisiones por turno/intento/paso. Una
  interrupción incierta exige reintento explícito. Una revisión negativa vuelve al agente
  como feedback dentro del presupuesto de 12 continuaciones; nunca publica ese borrador.
- Las llamadas de herramientas son del mismo servicio compartido por los agentes de análisis.
  Un resultado de búsqueda de informes descubre referencias; se abre el original para afirmar
  sus conclusiones. El servidor obliga a conservar el informe/version de un hallazgo seleccionado.

## Límites que se deben medir

La comprobación semántica usa otro pase del modelo y puede equivocarse; no constituye una
prueba formal de veracidad. Añade latencia y consumo, incluso a respuestas sencillas. Los
controles de referencias, alcance, versiones, ejecución de cálculos y aislamiento siguen
siendo deterministas. Evaluar relevancia con diálogos completos, sin comparar frases exactas.
