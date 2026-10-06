# Anchura inmediata y botón del asistente

Validación del paso 2.5.24 en `feature/ui-ux-refinements`.

## Cambio

El contenedor del chat interpolaba cada anchura durante 280 ms, mientras el
tirador usaba directamente la anchura solicitada. Esto separaba temporalmente
el borde y el tirador y dejaba movimiento después del ajuste.

La anchura ahora se aplica directamente como estilo del contenedor; solo se
conserva el fundido de apertura/cierre. Arrastre y teclado actualizan juntos
panel, página y tirador. Los límites y el almacenamiento siguen iguales.

El acceso superior al asistente usa `BotMessageSquare` y un botón circular con
el azul primario del tema. Conserva nombre accesible y tooltip de preguntar o
continuar, visibilidad según ruta y apertura de la conversación existente.

## Comprobaciones

- `npm --prefix frontend test`: **225 pruebas en 30 archivos, todas pasan**.
  La regresión verifica que el contenedor cambia de 420 a 444 px y vuelve a
  420 px inmediatamente al usar el teclado, conservando escritura de anchura.
  Las pruebas existentes cubren apertura, cierre, continuación y borradores.
- `npm --prefix frontend run build`: TypeScript y Vite pasan. Hay avisos de
  paquetes superiores a 500 kB, sin errores de compilación.
- `npm --prefix frontend run lint`: sin errores; 27 avisos existentes.
- Localhost 8788, escritorio: al arrastrar de x=533 a x=509, la anchura del
  contenedor queda en 444 px, y borde y centro del tirador coinciden en x=509.
  Una observación posterior conserva esas mismas medidas. ArrowRight devuelve
  el panel a 420 px. Se comprobó apertura y cierre desde el botón nuevo.
- Botón visible: fondo `rgb(40, 101, 138)` y cabeza de agente con bocadillo;
  nombre accesible de preguntar conservado.
- Móvil 390 × 844: botón azul visible y funcional; panel a 390 px, sin
  tiradores de escritorio. Se cerró el panel y restauró la vista de escritorio
  con navegación expandida al terminar.
- Revisión de cambios y `git diff --check` sin incidencias. Capturas privadas
  en `.local/checks/`; no se enviaron preguntas al modelo ni se crearon informes.

La vista previa permanece en 8788. El servidor del otro checkout en 8787 se
dejó intacto. No se modifica la persistencia entre recargas del navegador,
cuya limitación está documentada en la validación del paso 2.5.23.
