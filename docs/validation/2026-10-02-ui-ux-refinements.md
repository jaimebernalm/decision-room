# Bibliotecas, fijación de chats y filas de informes · 2 de octubre de 2026

Paso 2.5.21, sobre la integración de UI de la rama principal.

- Chats e Informes tienen una superficie de enlace amplia, flecha hacia la
  biblioteca, fondo al pasar el cursor, foco de teclado y resaltado de la página
  activa. El + de nuevo chat conserva una acción independiente.
- Los menús de chats permiten Fijar/Desfijar. PostgreSQL guarda `pinned_at` por
  chat y negocio mediante la migración 29. Los fijados preceden a los recientes
  tanto en la biblioteca como en la navegación. Entre fijados, el último fijado
  aparece primero; repetir la misma petición conserva su fecha y posición.
  Desfijar recupera el orden por último mensaje. La operación no envía mensajes
  al agente ni modifica el contenido del chat.
- Informes mantiene su tabla semántica con Estado y Creado, pero presenta filas
  separadas y redondeadas, con el mismo fondo/hover que Chats. Cada informe tiene
  un icono circular de borde fino sin relleno; cabeceras y estados usan etiquetas
  de contorno. En móvil la fecha se muestra debajo del título. Se conservan
  búsqueda, destinos según disponibilidad, selección de contexto, eliminación
  confirmada y restauración.

## Comprobaciones

- 215 pruebas frontend en 28 archivos pasan. Incluyen fijar/desfijar desde el
  menú, refresco del listado, conservación del orden ante fallo, enlaces activos,
  selección de informes disponibles y rechazo de retirados, papelera y restauración.
- Compilación TypeScript/Vite correcta; lint sin errores. Permanecen los 27
  avisos existentes de lint y el aviso de tamaño del paquete de chat.
- 21 pruebas backend dirigidas pasan. PostgreSQL: fijación persistente e idempotente, varios fijados,
  prioridad frente a mensajes recientes y recuperación del orden al desfijar.
  La API exige autenticación, booleano explícito y negocio correcto; rechaza
  chats ajenos y eliminados. Migración desde 28 y repetición conservan chats y
  fechas de fijación; las migraciones históricas conservan sus datos.
- Navegador sobre localhost: enlaces de biblioteca, resaltado activo y nuevo
  diseño de Informes; fijar desde la navegación, primer puesto en ambos listados,
  recarga conservando fijación y desfijar desde la página de Chats. Se restaura
  la preferencia original después de la comprobación.
- Móvil 390 × 844: filas, estados, fecha y acciones visibles. Documento de 390 px
  y tabla de 350 px, sin desbordamiento horizontal. El enlace de Chats navega y
  cierra la barra móvil. Se restablece el tamaño del navegador.

Capturas y estado de ejecución permanecen en `.local/`, ignorados por Git.
No se prueban inferencias de modelos ni calidad analítica: estos cambios son de
navegación, preferencias y presentación.
