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
