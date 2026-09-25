# Ajustes de conversación y navegación, 25 de septiembre de 2026

## Alcance

- El envío desde un chat desplaza la página con suavidad hasta el bloque de respuesta, incluidos los tres puntos de espera, y lo mantiene visible al avanzar el turno. Si la persona desplaza la página manualmente, deja de seguirlo. Respeta la preferencia de movimiento reducido.
- Los mensajes propios se alinean a la derecha y ocupan solo el ancho necesario, hasta un límite para los textos largos. Se elimina el encabezado «Tú»; la posición distingue quién envió el mensaje.
- Mientras hay una respuesta en curso, el botón de envío muestra actividad y acepta nuevos mensajes. Cada uno se guarda en una cola visible y se procesa por orden; las aclaraciones pendientes se insertan antes de los mensajes posteriores. La extracción de memoria de un mensaje en cola comienza cuando llega su turno.
- Las conversaciones se pueden eliminar de la navegación y recuperar en **Conversaciones**. Los informes y los datos compartidos en **Mi negocio** se conservan. Los enlaces hacia chats eliminados dejan de mostrarse en las vistas que se generan de nuevo.
- El panel lateral se ajusta mediante arrastre o teclado, entre 216 píxeles y el 40 % de la ventana, con espacio reservado para el contenido. La anchura se recuerda localmente. La barra de desplazamiento es fina y aparece al desplazar; se conserva el comportamiento compacto en móvil.

## Comprobación

- Las pruebas de conversación cubren el orden de cola, el reintento tras un fallo, la aclaración insertada antes de mensajes pendientes, la captura de memoria diferida y la recuperación de un chat eliminado.
- Pasan 268 pruebas Python en la regresión general y 16 pruebas JavaScript del dashboard/chat, incluida la geometría del bloque de respuesta sobre el compositor fijo. La sintaxis JavaScript y `git diff --check` también pasan.
- Se comprobó en el navegador local el cambio de anchura del panel y el diseño del chat a 390 píxeles; después se restauraron la anchura y el tamaño originales.
- El borrado es reversible desde la papelera de la aplicación. No borra recuerdos compartidos ni informes que ya existían, porque pueden seguir siendo necesarios en otras conversaciones.
