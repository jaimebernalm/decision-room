# Mi negocio: lectura compacta y cabeceras completas

## Resultado

Cada declaración de Información muestra una sola línea, con puntos suspensivos
cuando no cabe. El texto no se modifica: pulsarlo, Enter o Espacio abre los
detalles completos sobre la página, con procedencia, revisión, estado y ámbito.
El cuerpo permite desplazamiento y la cabecera y el cierre permanecen visibles.
Cerrar o Escape devuelve el foco a la declaración. Los avisos de revisión,
conflictos y fechas relevantes siguen visibles en la lista.

Información ocupa el mismo ancho disponible que Datos. Toda la cabecera de cada
grupo responde al cursor y al foco con el acento de la barra lateral, incluida
la zona del +. El botón + se coloca antes de la flecha del extremo derecho;
añadir y plegar siguen siendo controles independientes. Se conservan grupos,
descripciones, asignaciones y formulario con destino fijo.

La referencia consultada fue la documentación oficial de
[Intercom sobre formato y secciones plegables](https://www.intercom.com/help/en/articles/56978-format-an-article).
Su patrón de mostrar el detalle a petición informa la lectura compacta; la
colocación de los controles es una decisión de esta interfaz. Se reutiliza el
diálogo de detalles existente para conservar origen y accesibilidad.

## Comprobaciones

- Frontend completo: 205 pruebas en 27 archivos, todas aprobadas. La ficha tiene
  36 pruebas; las nuevas comprueban texto de más de 1.800 caracteres con saltos
  de línea, lectura directa sin escrituras, apertura con Enter/Espacio y cierre
  con retorno del foco. Pasan también conflictos, propuestas, menú, selección
  versionada, creación por grupo y errores de guardado.
- Compilación TypeScript/Vite correcta. Persiste el aviso previo del paquete de
  chat mayor de 500 kB. Lint sin errores, con 27 avisos previos en otros archivos.
- Navegador con la aplicación compilada y API local de datos ficticios:
  escritorio de 1280 × 800, móvil de 390 × 844 y lector de 390 × 600.
  Información y Datos abarcan ambos de x=304 a x=1232 en escritorio (928 px).
  Las cajas móviles abarcan de x=20 a x=370 (350 px); documento y ancho
  desplazable son ambos 390 px, sin desbordamiento horizontal.
- La declaración larga de la demo conserva sus 553 caracteres completos al
  abrirla. En la lista tiene 24 px de alto, `nowrap` y `ellipsis`; su texto
  excede el ancho disponible, por lo que se comprueba el recorte real.
- El cursor sobre el + aplica `oklch(0.93 0 0)` a toda la cabecera. El formulario
  abre el grupo correcto. La lectura móvil conserva la página detrás; a 600 px
  de altura, el diálogo ocupa 540 px, el cuerpo se desplaza y el cierre sigue
  dentro de la pantalla. Escape devuelve el foco al texto original.
- Se restablece el tamaño habitual del navegador y queda abierta Información.
  Capturas y estado de la demo permanecen en ubicaciones locales ignoradas.

## Alcance

Este incremento cambia presentación y acceso al detalle. La API, la memoria
guardada, los informes y el extractor mantienen sus contratos. La comprobación
visual usa datos ficticios aislados; no valida PostgreSQL ni invoca modelos.

Plan: [secuencia de ejecución](../technical/business-dossier-ui-plan.md).
