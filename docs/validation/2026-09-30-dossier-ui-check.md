# Mi negocio: ficha organizada y compacta

## Resultado

La cabecera muestra el nombre del negocio y las pestañas Información, Datos e
Historial. La presentación original está plegada dentro de Información, con
acceso a su edición. Cuando no hay recuerdos activos, una presentación de hasta
tres líneas permite reconocer el negocio; el desplegable conserva el texto completo.

Los recuerdos activos se agrupan en Por revisar, Sobre el negocio, Operativa y
Objetivos y preferencias. Se usan estado, tipo, ámbito y temas reconocibles; los
temas sin clasificación específica permanecen en Sobre el negocio. No se generan
resúmenes ni se reescriben declaraciones del cliente. Cada grupo se puede plegar
y muestra su número de datos.

Las filas muestran el texto completo y un menú de acciones. Se omiten las
etiquetas repetitivas de confirmación y ámbito general; los ámbitos específicos,
periodos, contradicciones y fechas ambiguas siguen visibles. Ver detalles abre
origen, cita, alternativas, revisión y enlace a la conversación. Editar, añadir,
confirmar y retirar usan el contrato de memoria existente. Una contradicción o
una fecha ambigua requiere edición; no se ofrece confirmación directa.

## Comprobaciones

- `npm --prefix frontend test`: 125 pruebas aprobadas en 17 archivos, incluidas
  14 pruebas específicas de la ficha. Cubren grupos, plegado, presentación
  original y alternativa, pestañas, detalle/procedencia, teclado y retorno del
  foco, corrección con revisión exacta, creación, retirada, confirmación y errores.
  El borrador y la clave de idempotencia se conservan tras un fallo de edición.
- Selección de contexto: las filas conservan identificador y versión; la
  presentación original se puede seleccionar al desplegarla. Se adapta la prueba
  existente de navegación entre cuatro secciones para abrir ese desplegable,
  conservando panel, borrador y adjuntos durante todo el recorrido.
- `npm --prefix frontend run build`: TypeScript y compilación Vite correctos.
  Persiste el aviso de paquetes de más de 500 kB, incluido el chat ajeno al ajuste.
- `npm --prefix frontend run lint`: sin errores. Los avisos corresponden a
  archivos ajenos al ajuste. La comprobación de los tres archivos de frontend
  modificados con `oxlint` no produce errores ni avisos.
- Navegador sobre la aplicación compilada y una API local de datos ficticios:
  filas, menús y detalle en escritorio; vista de 390 × 844 en móvil, con texto
  largo y formulario completo. Corrección de horario guardada y fila actualizada.
  Ancho del documento móvil: 390 px; ancho desplazable: 390 px.
- `git diff --check` y revisión del contenido preparado para el repositorio
  público. Dependencias, compilación, servidor de prueba y capturas permanecen
  en ubicaciones ignoradas; se conservan en Git código, pruebas y documentación.

## Alcance

La prueba de navegador utiliza una API ficticia aislada, sin modificar negocios
reales. Las pruebas de frontend comprueban las peticiones y respuestas del
contrato, incluida la revisión y los fallos; esta ronda no valida persistencia
en PostgreSQL ni llama a modelos. No cambia el estado de aceptación analítica
de otras entregas.

Durante la validación se corrigieron el retorno del foco desde un diálogo abierto
por menú y el margen de párrafos del componente Accordion, que añadía espacio
innecesario a las filas con avisos.

Plan: [secuencia de ejecución](../technical/business-dossier-ui-plan.md).

## Refinamiento de contraste y separación

Los grupos tienen cajas con borde, esquinas redondeadas, sombra ligera y 16 px
de separación. Sus cabeceras usan texto de 16 px y peso 600, fondo diferenciado
y contador en una cápsula. Las filas conservan su densidad y separadores. Al
pasar el cursor o enfocar sus acciones cambian al mismo color de interacción
de la barra lateral (`sidebar-accent`), con sombra ligera; las cabeceras también
responden al cursor. Las transiciones respetan la reducción de movimiento.

- Pasan las 32 pruebas existentes de ficha y chat contextual en dos archivos.
  No se añaden pruebas que dupliquen las clases de presentación.
- TypeScript y compilación Vite correctos; persiste el aviso de tamaño de
  paquetes ya descrito. `oxlint` sobre la ficha y `git diff --check` sin errores.
- En la demo compilada, el cursor sobre una fila produce `oklch(0.93 0 0)`,
  igual que el acento de la barra lateral. Tab lleva a las acciones de la primera
  fila y activa su resaltado; los grupos se siguen plegando.
- El borde izquierdo de las cajas y del título coincide (304 px en el
  escritorio comprobado). En móvil de 390 × 844 las cajas abarcan de 20 a
  370 px; el ancho del documento y su ancho desplazable son 390 px.
- Revisión visual en temas claro y oscuro, con capturas locales ignoradas.
  La demo abierta se actualiza con la compilación nueva y conserva datos ficticios.

## Propuestas y conflictos con acciones directas

- Las propuestas confirmables muestran tic y X al pasar el cursor o recibir foco
  de teclado. En anchos inferiores a 640 px y dispositivos sin cursor siempre
  se ven. Usan nombres accesibles, explicaciones al cursor/foco y deshabilitación
  durante la petición. Descartar conserva la información en el historial.
- Resolver conflicto permanece visible. El diálogo permite comparar las versiones
  con ámbito, fechas y citas disponibles; elegir una solo actualiza el borrador.
  Guardar solución envía `correct` con revisión exacta; conserva la clave de
  reintento y el borrador si falla. Cancelar no escribe y devuelve el foco.
- Pasan 132 pruebas de frontend en 17 archivos, incluidas siete nuevas pruebas
  de confirmación directa, descarte al historial, error de confirmación, selección
  de alternativa con ámbito/fechas, corrección sin alternativas, cancelación y
  reintento tras conflicto de revisión. Tras el ajuste de presentación móvil
  pasan nuevamente las 39 pruebas de ficha y chat contextual.
- Compilación TypeScript/Vite correcta y lint de ambos archivos sin errores.
  Persiste el aviso conocido de tamaño de paquetes. Diff revisado para el
  repositorio público; demo, estado y capturas siguen ignorados.
- Navegador con API ficticia: cursor revela ambos botones; confirmar mueve la
  información al grupo activo, descartar la conserva en Historial, y resolver
  el ejemplo 20 %/30 % actualiza la fila y elimina el aviso. Una propuesta de
  más de 500 caracteres se muestra completa en escritorio y móvil de 390 × 844,
  sin desbordamiento horizontal; los botones están visibles en móvil.

Estas comprobaciones mantienen el alcance de API ficticia descrito arriba;
no validan almacenamiento PostgreSQL ni modifican negocios reales.

## Elección de conflicto, grupos propios y Actualizar

La elección anterior rellenaba el formulario sin señalar la versión elegida.
Ahora las tarjetas son opciones de radio con borde destacado, círculo marcado y
etiqueta Seleccionada. Se puede pulsar toda la tarjeta o utilizar las flechas del
teclado. Guardar solución exige elección explícita o texto personalizado y se
mantiene en el pie, separado del contenido desplazable. Se deduplican versiones
repetidas en el contrato de memoria y se conserva la cita original disponible.

La barra de pestañas y Actualizar quedan separados por 8 px en escritorio. Junto
a Añadir información aparece Personalizar grupos. La configuración permite crear,
renombrar, reordenar y eliminar; las asignaciones se guardan desde Mover a grupo.
No se oculta información al retirar una categoría ni se mezclan grupos entre
negocios. Por revisar permanece separado de la clasificación elegida.

- Pasan 138 pruebas de frontend en 17 archivos. Las pruebas de ficha incluyen
  elección marcada y deduplicada, guardado sin selección bloqueado, creación/
  renombrado/orden de grupos, traslado con teclado, eliminación sin pérdida,
  pendientes siempre visibles, validación de nombres, error concurrente,
  cancelación con retorno del foco y grupos vacíos sin recuerdos activos.
- Pasan 40 pruebas Python de configuración de la ficha, migraciones y memoria
  sobre bases PostgreSQL aisladas. Se verifica la ruta HTTP autenticada, lectura
  posterior, migración repetible, conservación de memoria, asignaciones ajenas,
  grupos inválidos, escrituras concurrentes y reintento exacto. El esquema 27
  añade la tabla de presentación sin cambiar los contratos analíticos.
- TypeScript/Vite y lint de los archivos de frontend modificados correctos;
  permanece el aviso conocido de paquetes grandes. Diff revisado y sin errores.
- Navegador con datos ficticios: selección visible del 30 %, guardado desde móvil
  y desaparición del conflicto; creación de Clientes, traslado con ratón de una
  fila y conservación al recargar. En 390 × 844, el botón Guardar solución queda
  dentro de la pantalla (borde inferior a 786 px) y ambos diálogos tienen ancho
  desplazable igual al visible, 358 px. Controles de grupos comprobados en móvil.

La persistencia y los límites de grupos sí se comprueban con PostgreSQL real en
bases de pruebas desechables. El recorrido visual continúa en la demo aislada;
no se modifica información real del cliente ni se llama a modelos.

## Controles destacados y descripciones que utiliza el extractor

- Añadir información abre su formulario desde un botón circular de 56 × 56 px,
  con símbolo más de 28 px y etiqueta visible. Las pestañas usan texto de 16 px
  y superficies de 55 px en escritorio y 47 px en móvil. En 390 × 844 caben las
  tres pestañas y el ancho total del documento permanece en 390 px.
- El menú de fila tiene opacidad 0 en reposo y 1 cuando el cursor entra en ella.
  Se comprueba apertura con Enter y retorno con Escape. Foco y menú abierto
  mantienen la visibilidad; la regla de ocultación requiere cursor fino con
  hover, por lo que no oculta los controles de dispositivos táctiles.
- El editor permite descripciones de hasta 500 caracteres. Un grupo nuevo exige
  nombre y descripción; el borrador de un grupo antiguo acepta la incorporación
  de una descripción sin alterar sus asignaciones. En móvil el diálogo mide
  358 px de ancho, sin desbordamiento, y Guardar grupos termina a 786 px.
  La descripción del grupo Clientes de ejemplo se conserva después de recargar.
- Pasan 139 pruebas frontend en 17 archivos, TypeScript/Vite y lint de los
  archivos modificados. Permanece el aviso conocido de paquetes grandes.
- Pasan 47 pruebas sobre PostgreSQL aislado: descripciones normalizadas y
  persistentes, compatibilidad de grupos anteriores, límite y tipos válidos;
  contexto de extracción con descripciones, enum de IDs del proveedor,
  clasificación de recuerdos nuevos, rechazo de grupos ajenos, confirmación de
  propuestas sin perder grupo, conservación de movimientos manuales, cambios de
  configuración durante la llamada y recuperación de un fallo SQL sin repetir
  el proveedor. Las descripciones no se convierten en hechos.

La clasificación se valida con un modelo determinista de prueba y almacenamiento
real aislado. No se evalúa la precisión semántica de un proveedor remoto en este
incremento. La demo visual mantiene datos ficticios y sus grupos existentes.

## Añadir dentro del grupo y navegación alineada

Cada cabecera contiene un botón + de 48 × 48 px a la derecha, con etiqueta en
escritorio y nombre accesible que identifica el grupo. Está separado del plegado;
abre con teclado incluso estando cerrado el grupo y devuelve el foco al cancelar
o guardar. Se elimina el botón global y permanece Personalizar grupos. Las
pestañas bajan 16 px y su radio, selección activa y cajas coinciden en 14 px.

El formulario muestra el grupo fijo y omite Tipo de información para nuevos
recuerdos. Por revisar crea una propuesta; los grupos propios reciben una
declaración con asignación persistente. Sin grupo queda como destino explícito,
incluso si existiría una clasificación automática. La información y su grupo se
guardan en una sola petición y transacción.

- Pasan 142 pruebas frontend en 17 archivos: grupos vacíos, formulario de grupo
  fijo, independencia del plegado, creación de propuestas, destino Sin grupo,
  borrador conservado después de error y retorno del foco. Las pruebas anteriores
  de edición, conflictos, grupos, contexto y navegación siguen pasando.
- Pasan 50 pruebas PostgreSQL aisladas: ruta HTTP de creación con grupo,
  lectura posterior, reintento exacto sin duplicación, conflicto de clave al
  cambiar destino, propuestas y Sin grupo; grupos inválidos/retirados, ausencia
  de hechos y originales parciales y rollback real al fallar SQL. Un reintento
  posterior a eliminar el grupo recupera la respuesta sin restaurar la categoría.
- TypeScript/Vite, lint focalizado y diff correctos; continúa el aviso conocido
  de paquetes grandes.
- Navegador con datos ficticios: ejemplo añadido a Clientes, conservación tras
  recargar y cabecera plegada durante la creación. En 390 × 844 no hay
  desbordamiento horizontal; el diálogo mide 358 px y Guardar información termina
  a 656 px. Solo permanece el selector de ámbito. Cabeceras con títulos largos,
  botones derechos y pestañas legibles comprobados en móvil y escritorio.

La demo conserva sus grupos e información de ejemplo; el almacenamiento del
producto se valida en bases PostgreSQL de prueba y no se modifica un negocio real.

## Botón individual más discreto

El círculo de cada grupo pasa de 48 a 36 px y el símbolo de 24 a 20 px. No hay
sombra en reposo y el hover usa una sombra suave; la regla para puntero táctil
mantiene 44 px. TypeScript/Vite, lint focalizado y revisión del diff correctos.
En el navegador se comprueban las dimensiones, ausencia de sombra en reposo,
apertura del formulario con grupo fijo y cancelación. Se conserva el estado
plegado de las cabeceras al actualizar la demo. Ajuste de estilos sin nuevas
pruebas de comportamiento; se verifica la compilación de la regla táctil.
