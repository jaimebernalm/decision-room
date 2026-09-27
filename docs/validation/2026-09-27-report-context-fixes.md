# Correcciones de conversación e informes

Ampliación del paso 2.5.16 a partir de tres capturas de uso.

## Cambios

1. La conversación completa conserva una única acción «Abrir en panel», con
   destino Inicio. Se retira el botón duplicado «Volver al dashboard». Abrir otra
   conversación desde un panel existente conserva la superficie actual.
2. Seleccionar una fila de Informes adjunta `kind=report`, con la identidad y
   versión de la revisión completa. El adjunto lleva etiqueta «Informe» y su título;
   los datos del propietario llevan «Mi negocio». Los fragmentos anteriores siguen
   siendo compatibles. El servidor obliga a abrir y citar el informe seleccionado.
   Las referencias de memoria incluyen procedencia guardada; autor y revisor
   distinguen el contenido del informe del origen del dato y se centran en los
   elementos seleccionados, sin desviarse a cifras anteriores ajenas a la pregunta.
3. La selección ocupa toda la fila, con relleno alrededor del texto. Un retirado
   presenta estado rojo suave y «No se puede seleccionar» al activar la herramienta;
   Disponible usa verde suave. Se reservó espacio para el aviso de selección para
   evitar tapar títulos, también en móvil.
4. Los informes terminados, retirados o interrumpidos se pueden mover a una papelera
   y restaurar desde ella. La interfaz confirma la acción y conserva el diálogo y
   el listado si falla. Es una eliminación del listado, no una purga de datos ni
   evidencia: las referencias de conversaciones y los originales se conservan.
   Esquema 18, operaciones idempotentes y limitadas al negocio activo; se impide
   eliminar trabajos pendientes/en curso. La papelera tampoco muestra otros negocios.

## Comprobaciones

- 299 pruebas Python aprobadas. Casos nuevos de autenticación, aislamiento,
  retirada, borrado/restauración, reenvío idempotente, conservación de evidencia,
  bloqueo de trabajos activos y selección conjunta de memoria e informe completo.
- 57 pruebas frontend aprobadas: un único acceso al panel con destino Inicio,
  conservación de borradores, envío de referencias de informe completo, selección
  sin navegación, aviso para retirados, cancelación, error de borrado y restauración.
- TypeScript/Vite correctos. Lint sin errores; quedan avisos de Fast Refresh y tamaño
  de paquetes. `git diff --check` correcto.
- Navegador con negocio ficticio: adjuntar un informe desde el listado y dos hechos
  desde Mi negocio; consultar con el modelo real, conservando el chat. El agente
  respondió que los hechos procedían del perfil, nombró el informe y distinguió
  expresamente su presencia en el alcance de la procedencia original. No inició
  una investigación nueva ni se desvió a cifras anteriores.
- Marco medido de 676 × 48 px sobre una fila de 676 × 49 px: ocupa todo el ancho,
  con la diferencia del borde inferior de la tabla. Revisión visual del texto y
  del estado retirado. Eliminación y restauración reales de un informe ficticio,
  con desaparición/reaparición en listado y navegación reciente.
- Ampliar desde Informes y pulsar «Abrir en panel» lleva a Inicio con el mismo chat.
  Comprobación de pantalla móvil a 390 × 844; tamaño habitual restaurado al terminar.

La comprobación con el modelo real es un caso de regresión concreto; no garantiza
que todas las preguntas ambiguas reciban siempre la misma interpretación. La
identidad del informe y su apertura exacta sí se validan en servidor.
