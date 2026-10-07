# Mi negocio: explorador y línea temporal

Fecha: 7 de octubre de 2026. Refinamiento de presentación de 2.5.5, según la
[secuencia de ejecución](../technical/business-dossier-ui-plan.md).

## Resultado

Información y Datos comparten una navegación de grupos y un área de lectura.
La selección se distingue visualmente, conserva las cantidades y respeta el
orden y los nombres personalizados. Los grupos vacíos siguen disponibles para
añadir información. Por revisar y Sin grupo mantienen las reglas existentes.
Cuando el grupo seleccionado desaparece, la vista utiliza otro grupo disponible.

El diseño se adapta al ancho de su contenedor: navegación lateral desde 608 px
y navegación superior por debajo, también con el chat abierto. Los paneles de
grupo conservan su contenido montado y ocultan los controles inactivos. Tras
confirmar o mover información desde un detalle o menú, la lectura y el foco
siguen al recuerdo en su grupo correspondiente.

Historial muestra las revisiones con una línea temporal y un acceso discreto al
origen. Conserva el orden recibido del servidor, fechas, estados, números de
revisión, texto completo, alternativas y enlaces de procedencia. No calcula
diferencias entre revisiones ni crea nuevos eventos.

Se mantienen los formularios y las acciones de editar, confirmar, descartar,
resolver conflictos, retirar, personalizar/mover grupos, seleccionar contexto,
subir/descargar archivos, abrir tablas y consultar relaciones. No se modifican
API, persistencia, procesamiento de datos ni lógica del agente.

## Comprobaciones

- Regresión completa: `npm test -- --reporter=json` en frontend, 268 pruebas
  correctas. Tras el refinamiento visual final y la comprobación adicional del
  foco al mover un recuerdo, 88 pruebas correctas de dossier, datos y chat
  contextual (`npm test -- dossier contextual-chat`).
- Pruebas conservadas de revisiones exactas, idempotencia, errores/borradores,
  confirmación, conflictos, retirada, grupos personalizados, archivos originales,
  tablas, relaciones y selección de contexto. Las pruebas navegan ahora al grupo
  correspondiente antes de ejecutar su acción.
- Navegación con teclado, selección visible, grupos vacíos, sustitución de un
  grupo eliminado, foco tras guardar/mover y conservación del historial y origen.
- `npm run build`, `npm run lint` y `git diff --check`: correctos. Se conservan
  avisos previos de tamaño de chunks y lint en otros componentes; sin errores
  ni avisos nuevos en los componentes de este cambio.
- Navegador local con el negocio de ejemplo: Información y apertura/cierre de
  detalles, Datos/Archivos/Tablas/Relaciones, tabla Ventas con sus columnas y filas,
  Historial, escritorio a 1440 px, chat abierto a 1024 px y móvil a 390/320 px.
  El explorador ocupó 444 px con el chat abierto y 280 px en la vista móvil más
  estrecha, sin desbordamiento horizontal.

Capturas y resultados completos permanecen en `.local/visual-checks` y `.local`,
fuera de Git. Esta comprobación corresponde a presentación y regresión de los
recorridos existentes; no añade aceptación analítica ni una nueva entrega.
