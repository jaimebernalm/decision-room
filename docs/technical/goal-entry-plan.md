# 2.5.36 — Inicio por objetivo

## Secuencia

1. **Seleccionar.** Cuatro tarjetas en una cuadrícula: pregunta (Chat), análisis
   (Informe), predicciones e ideas (Próximamente). Cambiar título, ejemplo y
   selección sin enviar ni reemplazar el texto. Conservar el objetivo junto al
   borrador de cada negocio y reiniciarlo con Nuevo chat. Mantener la transición
   del compositor, un solo campo y movimiento reducido.
2. **Enviar.** Las opciones disponibles transmiten una intención validada al
   asistente. Pregunta favorece respuesta directa; análisis orienta la conversación
   hacia un informe con datos y revisión existentes. Un informe revisado puede
   guardarse al terminar ese análisis; no publicar resultados pendientes o antiguos.
   Predicciones e ideas permiten probar el inicio pero bloquean botón y Enter:
   aún no hay ejecución. Mantener contexto, aislamiento e idempotencia.
3. **Comprobar.** Pruebas frontend y backend del contrato, cambios de objetivo,
   borradores, reinicio, reintentos y bloqueo de futuros. Build/lint, escritorio y
   móvil, revisión del diff y commit local sin cambios ajenos ni datos privados.

Estado: completado y validado el 2026-10-08.

## Validación

- 296 pruebas frontend correctas (39 archivos): selección y texto conservado,
  títulos y ejemplos, futuros bloqueados por botón y Enter, recarga, reinicio,
  traducción, rutas de informe, reintento e intención de envío.
- 60 pruebas de conversaciones correctas sobre PostgreSQL temporal y modelo
  controlado: validación e idempotencia del objetivo, persistencia entre mensajes,
  aclaraciones, informe guardado solo tras revisión, obsolescencia y regresiones.
- Build y lint correctos; permanecen los avisos existentes de chunks y lint.
- Navegador local en 1280×720 y 390×844: cuatro tarjetas, selección visible,
  texto conservado tras recarga y cambio de objetivo, un solo compositor y sin
  desbordamiento horizontal. Enter en las opciones futuras conserva el inicio.
- Capturas y registros en `.local/checks/goal-entry-*`, fuera de Git.

La orientación del modelo se aplica al enviar. No se ejecutaron predicciones ni
brainstorming; sus tarjetas permiten seleccionar y escribir un objetivo futuro.
