# Selección de contexto y conversación lateral

27 de septiembre de 2026. Paso 2.5.16 completado dentro del alcance local.

## Comportamiento implementado

La herramienta «Seleccionar» del compositor activa la selección de bloques de
Inicio y los informes. Permite adjuntar hasta ocho gráficos, tablas, indicadores,
hallazgos o secciones. Los adjuntos tienen vista previa, eliminación individual
y apertura a tamaño legible. No hay botones permanentes de preguntar por tarjeta.
Se incorporó `Attachments` desde el registro oficial de Vercel AI Elements,
conservando los componentes y adaptaciones existentes del compositor.

Enviar abre inmediatamente una conversación a la derecha. Su ancho se ajusta
con ratón o teclado; plegar conserva el chat y el borrador. Ampliar abre la misma
conversación, incluso durante una respuesta pendiente. Los adjuntos permanecen
en los mensajes después de recargar, y permiten consultar el gráfico original
y regresar a su bloque del informe. En móvil se usa el ancho completo; seleccionar
o volver al origen deja visible el contenido que se quiere consultar.

El servidor valida negocio, informe, versión, tipo y clave de cada referencia.
Las referencias de varios informes se conservan sin fusionar automáticamente sus
conjuntos. Se resuelve la presentación revisada desde servidor y se comprueba su
vigencia en cada lectura. Una retirada conserva una indicación de indisponibilidad,
pero deja de entregar sus cifras. Se mantiene compatibilidad con `finding_reference`.
El agente recibe los valores de las series seleccionadas y debe abrir y citar
los informes correspondientes; sus dependencias participan en la invalidación.

## Pruebas automatizadas

- Regresión Python: `python -m unittest discover -s tests -q`, **290 pruebas
  correctas** en 150,373 segundos.
- Después de esa regresión se añadieron y ejecutaron **dos pruebas dirigidas**
  de resolución de contexto: cifras exactas, incluidos decimales; forma inválida,
  clave, versión y retirada. Ambas pasan.
- Frontend: `npm test`, **45 pruebas correctas en siete archivos**. Las cuatro
  pruebas de conversación contextual cubren selección, persistencia, ampliación,
  ausencia de reenvíos, plegado durante envío, conservación tras error y cambio
  de adjuntos después de un fallo. Se repitieron las cuatro tras el último ajuste.
- `npm run build` y `npm run lint`: correctos. Persisten avisos de tamaño de bundle
  y de exports Fast Refresh; no errores de compilación o lint.
- Revisión de diferencias y `git diff --check`: correctos. Archivos generados,
  estado de pruebas y credenciales quedan fuera de los commits.

Las pruebas de conversaciones incluyen varios informes, aislamiento entre
negocios, manipulación de referencias, retirada, reintentos e idempotencia,
lectura/citación de todas las fuentes y dependencias de nuevas investigaciones.

## Navegador y modelo real

Se utilizó una copia local aislada del negocio sintético Papelería Aurora, con
el backend y modelo reales. La base y los archivos temporales permanecen bajo
el directorio local ignorado. La prueba no añadió conversaciones al espacio
habitual del usuario.

Recorrido comprobado mediante Computer Use y capturas del navegador:

1. Seleccionar dos gráficos de Inicio y ver ambas miniaturas en el compositor.
2. Enviar una pregunta y mantener dashboard y chat visibles en escritorio.
3. Ampliar mientras se prepara la respuesta, conservando la misma conversación.
4. Abrir adjuntos a tamaño legible y volver al bloque exacto del informe.
5. Añadir los gráficos desde el informe, continuar y recargar la página completa:
   ambos turnos conservan sus dos adjuntos.
6. Comprobar móvil de 390 × 844, selección, retorno al informe y temas claro/oscuro.
7. Ajustar el panel mediante teclado en escritorio: ancho de 420 a 444 píxeles.
   Restaurar el tamaño de ventana al finalizar.

La primera respuesta real reveló un fallo: el agente conocía los gráficos pero
no recibía sus valores completos. Se corrigió la proyección de las fuentes
seleccionadas. En la repetición se pidió leer tres valores, sin cálculos nuevos:

| Valor consultado | Respuesta del modelo | Contraste independiente |
| --- | --- | --- |
| Ventas del 7 de septiembre | 310,00 € | 310,00 € |
| Cuadernos | 870,00 € | 870,00 € |
| Escritura | 385,00 € | 385,00 € |

El contraste utilizó los Parquet sintéticos vigentes y aritmética decimal. No se
crearon trabajos analíticos para contestar: se leyeron las series revisadas.
La comprobación de estos valores no constituye una evaluación general del modelo.

También se corrigieron el botón de regreso que podía superponerse al contenido,
el panel móvil que ocultaba el origen al volver, la pérdida del estado plegado
cuando terminaba un envío y los reintentos que conservaban adjuntos ya quitados.
La navegación cancela el modo selección sin borrar los adjuntos elegidos.

## Alcance y trazabilidad

Selección por bloques completos; no hay lazo de píxeles ni selección arbitraria
de otras páginas. Las miniaturas proceden de datos del informe, no de capturas
subidas. Los borradores guardan referencias y etiquetas, sin series ni imágenes.
La resolución se incorpora a la lectura existente del chat, sin endpoint nuevo.
Se limita la selección a ocho referencias y a un tercio del presupuesto de bytes
del contexto del agente; un exceso produce un error conservando el borrador.

- `3cfaaa8`: referencias versionadas, validación y recuperación en backend.
- `a785c61`: interfaz integrada, adjuntos oficiales, selección, panel y correcciones
  verificadas con el modelo y el navegador. Los pasos técnicos 2–4 se guardaron
  juntos; no se reconstruyeron commits intermedios.
- El cierre documental incluye la cancelación del modo selección al navegar,
  comprobada con compilación, lint y las cuatro pruebas de interfaz contextual.

La ampliación no cierra la entrega 3 ni modifica la aceptación analítica general.

## Ajuste posterior: desplazamiento sin carril permanente

El contenido principal utiliza ScrollArea de Radix en modo `scroll`. Su indicador
fino se superpone al contenido, sin carril visible ni ancho reservado, y se oculta
600 ms después del fin del desplazamiento. Se conserva `main-content` en el
viewport para navegación por teclado y retorno al bloque de origen.

Comprobado en navegador de escritorio con dashboard y chat lateral abiertos:
barra nativa oculta, indicador visible durante el desplazamiento, fondo del carril
transparente y ausencia del indicador en reposo. PageDown/End y desplazamiento
normal mantienen acceso al contenido. Pasan las 45 pruebas frontend, compilación,
lint sin errores y revisión de diferencias.

## Ajuste posterior: navegación y acciones del panel

Abrir la navegación pliega el chat, conservando la conversación para retomarla.
Abrir de nuevo el chat cierra la navegación; la coordinación responde a cambios
de apertura, sin volver a cerrar la navegación que el usuario acaba de solicitar.
Incluye el estado de navegación móvil y el atajo del componente Sidebar.

Las acciones del panel tienen etiquetas al pasar el ratón o recibir foco:
«Nueva conversación», «Ampliar» y «Cerrar». El botón + mantiene el panel abierto
con un compositor vacío; la conversación nueva se crea al enviar. La conversación
anterior permanece en el historial. Se distingue el panel vacío del envío inicial
en curso y se conserva el borrador dentro del panel si falla ese envío.

Validación: 51 pruebas de frontend correctas, incluidas dos nuevas de alternancia
de paneles y creación/envío desde el panel vacío; compilación y lint sin errores.
Recorrido en navegador con dashboard real de pruebas: abrir navegación, retomar
chat, pulsar + y comprobar el compositor dentro del panel y la etiqueta de cierre.

## Conversaciones existentes: Abrir en panel

La cabecera de cualquier conversación completa incluye «Abrir en panel». El
listado y los chats de la navegación incorporan un menú con la misma acción y
la eliminación con confirmación existente. Abrir un chat desde un informe o
dashboard conserva la ruta; desde otra página recupera el último origen visitado
del negocio, con Inicio como alternativa. Se conserva el identificador del chat,
el historial y el borrador de texto, sin crear conversaciones ni reenviar mensajes.
El proveedor compartido abarca ahora navegación y cabecera. Un envío inicial
tardío no sustituye una conversación que el usuario haya abierto mientras tanto.

Validación: 54 pruebas de frontend correctas, compilación y lint sin errores.
Tres casos nuevos comprueban cabecera con regreso al informe, listado sin origen
y cambio de chat desde navegación conservando el borrador anterior. La prueba de
eliminación se adaptó al menú y mantiene las comprobaciones de cancelación y
confirmación. En navegador se abrió un chat guardado desde su cabecera y otro
desde la navegación, manteniendo el dashboard y mostrando el historial correcto.

## Barra derecha independiente y transición de la tarjeta central

El chat lateral queda fuera de la tarjeta principal, al mismo nivel que ella.
Comparte el fondo `sidebar` de la navegación y ocupa toda la altura disponible;
su cabecera y acciones empiezan arriba, sin la franja de la cabecera del dashboard.
La tarjeta central mantiene su fondo, esquinas redondeadas y separación de 8 px.
El compositor del chat comparte el fondo del panel.

La apertura y el cierre animan el ancho y la opacidad durante 280 ms, con la
misma curva y duración que la navegación izquierda. Abrir la navegación retira
gradualmente el chat y desplaza la tarjeta central; ya no desmonta el espacio
del panel de golpe. Durante la salida los controles quedan inertes y fuera del
árbol accesible. La preferencia de movimiento reducido elimina estas transiciones.

Comprobaciones: 54 pruebas frontend correctas; nueve pruebas contextuales repetidas
tras ajustar la interpolación de ancho; compilación y lint sin errores. Revisión
visual en escritorio claro/oscuro y móvil de 390 × 844, incluido el compositor y
la selección de contexto. En escritorio se comprobó la separación geométrica:
tarjeta a 8 px del borde superior y panel desde el borde superior, fuera de ella.
Se observó un ancho intermedio de 35 px durante la apertura hacia 444 px y la
conservación del panel al empezar el cierre. El dashboard termina desplazado a
la derecha al abrir la navegación. La ventana de pruebas se restauró al finalizar.

## Contraste de mensajes y navegación

El fondo compartido por el mensaje del usuario y los estados activo/hover de la
navegación pasa de luminosidad OKLCH 0,97 a 0,93 en tema claro. Los mensajes usan
el token `sidebar-accent` para mantener coherencia con el resaltado de navegación.
Se conserva el valor del tema oscuro. Verificación visual con ambos elementos
en pantalla, compilación y lint sin errores; ajuste exclusivamente de color.


## Panel transversal y selección de negocio

- Inicio, Mi negocio e Informes comparten el panel abierto, el identificador del
  chat, el borrador y los adjuntos. Menú ordenado en ese orden y Conversaciones
  al final, con icono de bocadillos superpuestos distinto de los chats individuales.
- Mi negocio permite seleccionar presentación y hechos activos; Informes permite
  adjuntar el resumen de una revisión publicable desde el listado. No se convierten
  archivos ni hechos retirados en bloques seleccionables.
- Referencias de propietario resueltas en servidor, limitadas al negocio y a la
  revisión. Pruebas de versión antigua, identidad ajena, clave inexistente e intento
  de inyectar contenido. Un cambio posterior al envío retira el contenido del
  adjunto y permite continuar con el contexto vigente, sin tratarlo como informe.
- Regresión: **297 pruebas Python** correctas; tras enriquecer la selección para
  extracción de memoria con autoridad/estado/ámbito, se repiten las **48 pruebas
  de conversaciones**, correctas. **55 pruebas de frontend** correctas, incluida
  navegación real de componentes Inicio → Mi negocio → Informes → Inicio con
  borrador, dos tipos de adjunto y un único envío al chat existente.
- Compilación TypeScript/Vite correcta y lint sin errores. Persisten avisos de
  Fast Refresh y tamaño del fragmento de chat; la función exportada de selección
  añade otro aviso de la misma clase. Revisión de diferencias sin errores.
- Navegador con negocio ficticio y modelo real: seleccionar presentación, escribir
  una pregunta, ir a Informes y enviar; respuesta correcta «Es una tienda de
  papelería ficticia, creada para probar la experiencia de uso». Se comprueban
  adjunto en conversación completa, reacoplamiento, navegación y selección desde
  Informes. Revisión visual de Mi negocio con panel abierto, sin errores de consola.
- Servidor local actualizado tras verificar que no había trabajos ni turnos activos.
