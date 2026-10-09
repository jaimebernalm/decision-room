# 2.5.35 — Entrada compartida para preguntas e informes

## Objetivo

El cliente cuenta qué quiere conseguir desde un único inicio. El chat conserva
la conversación y los informes conservan las entregas. Reutilizar el asistente,
la creación idempotente y las acciones de informe existentes; no añadir capacidades
futuras ni cambiar publicaciones, evidencias o permisos.

## Secuencia

1. **Entrada y navegación.** Botón visible «+ Nuevo chat» en la cabecera lateral,
   acceso legible en móvil, retirar plus de Chats/Informes y duplicados de listados.
   Mantener bibliotecas, recientes, búsqueda y acciones de cada elemento.
2. **Inicio centrado.** «¿En qué te ayudo con tu negocio?», texto libre y tres
   sugerencias: analizar datos, resolver una pregunta y ayuda para empezar.
   Sugerencias editables, sin envío automático ni sobrescribir borradores.
   Compartir transición de posición del compositor entre página, inicio y chat,
   respetando movimiento reducido, teclado y una única entrada activa.
3. **Informes por conversación.** Estado vacío «Crear mi primer informe» abre
   el inicio con una intención editable. `#new` conserva compatibilidad y apunta
   al mismo recorrido. Datos existentes siguen disponibles; añadirlos desde
   Mi negocio cuando falten, sin exigir volver a subirlos para preguntar.
4. **Validación y cierre.** Verificar navegación expandida/contraída/móvil,
   sugerencias, intención de informe, datos, borradores, envío, reintento,
   contexto, rutas antiguas, ausencia de capacidades futuras y regresiones.
   Build/lint, revisión visual escritorio/móvil y commit local enfocado.

## Criterios de cierre

- La acción principal se entiende sin depender de un icono aislado.
- El nuevo chat deja de ser una pantalla vacía y permite escribir inmediatamente.
- Pulsar una sugerencia o entrar para preparar un informe no ejecuta un análisis.
- Enviar utiliza el negocio y el contexto vigentes; la conversación queda guardada.
- Los resultados existentes siguen ofreciéndose como informes desde el chat.
- Las rutas y borradores de otros chats y negocios se conservan.

Estado: implementado y validado el 2026-10-08.

## Resultado y validación

- «Nuevo chat» es la entrada principal; Chats e Informes conservan sus bibliotecas.
  El primer informe y la ruta antigua `#new` abren el mismo inicio editable.
- Compositor compartido de posición, con sugerencias que aparecen al terminar
  el desplazamiento. Inicio disponible sin carga diferida; la conversación mantiene
  el compositor y su borrador mientras carga el módulo de respuestas. Movimiento
  reducido elimina desplazamientos y esperas; teclado y foco conservan una entrada.
- `npm test`: **290 pruebas, 39 archivos, todas correctas**. Incluyen selección sin
  envío, borradores personalizados, reinicio, primer informe, ruta antigua, negocio
  y contexto, reintento idempotente, creación de informe desde respuesta,
  escritura durante carga, movimiento reducido y regresiones de navegación.
- `npm run build` y `npm run lint`: correctos. Se mantienen los avisos existentes
  de tamaño de chunks y lint; sin errores. `git diff --check`: correcto.
- Navegador local: escritorio 1280×720 y móvil 390×844, sin desbordamiento
  horizontal y un solo compositor. Revisados menú móvil, bibliotecas contraídas,
  sugerencias sin sobrescribir texto y envío real a un chat guardado. Capturas y
  logs de comprobación en `.local/checks/unified-entry-*`, fuera de Git.

No se modifican los contratos de análisis o publicación ni se anuncian capacidades
futuras de predicción o investigación.
