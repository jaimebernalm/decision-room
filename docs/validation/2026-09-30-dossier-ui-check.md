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
