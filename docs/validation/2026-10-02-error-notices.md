# Avisos de error compactos

Los avisos destructivos comparten fondo rojo al 10 % y texto rojo con la etiqueta
de conflicto; en oscuro se usa fondo al 20 %. Tienen esquinas redondeadas de
18 px y ancho ajustado al mensaje, limitado al espacio disponible. Se conserva
el texto completo, la traducción y el rol de alerta. Los mensajes largos se
envuelven en lugar de provocar desplazamiento horizontal.

- Pasan 211 pruebas frontend en 27 archivos, compilación TypeScript/Vite y lint
  sin errores. Se mantienen los 27 avisos previos de lint en otros archivos y
  el aviso de tamaño del paquete de chat.
- Comprobación de navegador con aplicación compilada y API ficticia: error
  superior de conexión y fallo de confirmación dentro de los detalles. En
  escritorio, el aviso superior ocupa unos 414 px dentro de un área de 596 px.
  Se comprueban el fondo y el color calculados y el radio de 18 px.
- A 390 × 844, el error del detalle ocupa 326 px y se reparte en dos líneas;
  documento y ancho desplazable siguen siendo 390 px. Las acciones permanecen
  visibles y se conserva la propuesta después del fallo.
- Se simulan respuestas de error solo en el servidor local de datos ficticios,
  sin escribir memoria. Se elimina la simulación al terminar, se restablece el
  tamaño del navegador y se deja la vista previa activa. Capturas, servidor y
  estado de ejecución permanecen en ubicaciones ignoradas.

El cambio es de presentación; no modifica recuperación, peticiones, persistencia
ni clasificación de errores. No se llama a modelos ni se prueba PostgreSQL.
