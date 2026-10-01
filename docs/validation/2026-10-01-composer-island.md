# Validación · Isla para escribir y foco discreto · 2.5.20.6

El usuario pide que la barra inferior flote sobre la página: al desplazarla, el
contenido debe seguir visible a ambos lados, sin una franja opaca horizontal.
También pide quitar el halo exterior que aparece al escribir dentro del chat.

La isla tiene superficie propia, sombra discreta y altura acotada. Su contenedor
exterior es transparente y deja pasar las interacciones en los laterales. El scroll
ocupa toda la página. Un observador de tamaño reserva la altura real al final del
contenido; texto multilínea, contexto y errores pueden crecer sin ocultar el último
bloque. Abrir el panel retira la isla y su reserva. El chat completo mantiene su
campo propio. La anulación del halo está limitada al campo de mensaje, con el borde
neutral original; los botones conservan su foco de teclado.

## Comprobaciones

- 161 pruebas frontend. Nueva regresión de altura observada, actualización de la
  reserva y liberación al abrir el panel; permanecen las pruebas de borrador,
  contexto, navegación, envío único, errores y reintentos.
- Compilación de producción y lint sin errores. Continúan los avisos existentes de
  tamaño de paquetes y Fast Refresh. Se corrigió la sintaxis del observador de
  prueba para cumplir la opción TypeScript `erasableSyntaxOnly`.
- Navegador: el viewport se extiende hasta el fondo y el scroll continúa detrás de
  la isla. En escritorio, reserva de 98 px con campo vacío y 158 px con cuatro líneas.
  Al final del scroll, el contenido termina aproximadamente en y = 614 px y el
  contenedor flotante comienza en y = 630 px: el último bloque queda accesible.
- Pulsar el campo conserva el color de borde y no introduce sombra de foco, tanto
  en la página de nuevo chat como en el panel. Solo hay un campo activo.
- Móvil 390 × 844: márgenes de 16 px, sin desbordamiento horizontal; reserva adaptada
  a la altura del campo. Tema oscuro: superficie opaca de la isla y laterales
  transparentes. Se restablecen el viewport y el modo claro al terminar.

Las capturas permanecen en el directorio local ignorado. Se vacía el borrador de
prueba y no se envían mensajes ni se modifican datos del negocio. Se revisan los
archivos preparados para Git; el commit es local y no se hace push.
