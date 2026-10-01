# Mi negocio y datos reutilizables · 2.5.5

## Resultado y recorrido

La ficha tiene Información, Datos e Historial. Información agrupa declaraciones,
propuestas, contradicciones y dudas en filas compactas de Sobre el negocio,
Operativa, Objetivos y preferencias y Por revisar. La presentación original se
despliega dentro de Información; origen, texto original, ámbito, fechas y revisiones
se consultan desde el menú de cada fila. Los ámbitos específicos y periodos siguen
visibles; los avisos distinguen información propuesta o en conflicto. Véanse el
[plan de presentación](business-dossier-ui-plan.md) y su
[validación](../validation/2026-09-30-dossier-ui-check.md).
Los orígenes que son mensajes enlazan a su conversación. El perfil general sigue
siendo editable; las definiciones y prioridades usan `memory.change`, igual que
las correcciones explícitas del chat. No existe otra copia de memoria en Markdown.

Guardar una edición es una declaración explícita. Confirmar solo admite propuestas
sin contradicción ni fecha ambigua. Resolver un conflicto exige indicar el contenido
correcto. Corregir o retirar requiere la revisión que vio el formulario: una segunda
pestaña no sobrescribe una corrección concurrente. La interfaz conserva el texto
si falla el guardado y ofrece actualizar la ficha; no reemplaza formularios mediante
sondeo periódico. Restaurar una información retirada requiere una corrección explícita.
Los cambios futuros conservan el ámbito y necesitan una fecha posterior, según el
contrato de memoria existente.

Las propuestas confirmables ofrecen tic y X directamente al pasar el cursor o
enfocar la fila; en móvil y dispositivos sin cursor permanecen visibles. La X
retira la propuesta al historial. El botón Resolver conflicto permanece visible
junto al aviso y abre las versiones, citas y la pregunta de aclaración disponible.
Usar una versión rellena el borrador, incluido su ámbito y fechas cuando están
estructurados; Guardar solución envía una corrección explícita. También se puede
escribir una solución sin alternativas. Se mantiene el menú para detalles y otras
acciones; fechas ambiguas y preguntas abiertas no se confirman directamente.

La elección de conflictos usa tarjetas con radio y estado Seleccionada. Guardar
solución permanece visible mientras el formulario se desplaza y exige elegir o
escribir una solución. Las alternativas que repiten la información actual se
deduplican; para esa versión se muestra su cita original cuando está disponible.

Personalizar grupos permite crear, renombrar, ordenar y eliminar categorías; el
menú de cada fila permite moverla o recuperar su clasificación automática.
`web_dossier_layouts` (esquema 27) guarda por negocio `groups`, `assignments` y
`revision`, mediante `POST /api/business/dossier-layout`; la ficha los devuelve
en `layout`. La configuración no cambia hechos, procedencia, revisiones de memoria
ni resultados analíticos. Se comprueba negocio activo, pertenencia de los recuerdos,
nombres únicos de hasta 60 caracteres, límite de 20 grupos y revisión concurrente.
Un reintento exacto puede recuperar la respuesta guardada; otra escritura antigua
se rechaza. Por revisar mantiene los pendientes visibles aunque tengan asignación.
Eliminar grupos conserva los recuerdos mediante clasificación automática o Sin
grupo; los grupos personalizados vacíos siguen visibles. Actualizar se sitúa junto
a las pestañas.

Cada cabecera ofrece Añadir información a la derecha: botón circular de 36 px
(44 px con puntero táctil), símbolo más de 20 px, etiqueta en escritorio y sombra
suave al interactuar. Está separado del control de plegado y
también aparece en grupos vacíos. Personalizar grupos permanece arriba. Las
pestañas se separan 16 px más del título y comparten el radio de las cajas; tienen
más superficie y tipografía de 16 px. El menú de
fila aparece con cursor, foco de teclado o apertura y permanece disponible en
dispositivos táctiles.

Cada grupo admite una descripción de hasta 500 caracteres. La creación desde la
interfaz requiere nombre y descripción; las configuraciones anteriores siguen
legibles. El extractor de memoria recibe nombres, descripciones y revisión de los
grupos como datos de clasificación, nunca como declaraciones ni instrucciones.
El contrato `memory-v6` incorpora `group_id` separado del contenido del recuerdo:
el esquema del proveedor limita la elección a los IDs del negocio o null, y el
servidor verifica la pertenencia en el contexto guardado de la llamada.

Solo los recuerdos nuevos reciben esa asignación en la transacción de extracción.
Una contradicción o corrección conserva la ubicación existente; los pendientes
siguen en Por revisar y, al confirmarlos, aparece su grupo. Si la configuración
cambia durante la llamada, se conserva el recuerdo y se omite la asignación
obsoleta. Un fallo SQL permite reaplicar la respuesta ya guardada sin otra llamada
al proveedor. Los grupos siguen sin alterar el ámbito o la vigencia analítica.

Añadir desde una cabecera abre un formulario con grupo fijo y sin selector de tipo
para información nueva. `POST /api/business/memory` acepta `group_id` en declarar
o proponer; la revisión de memoria, original, comando idempotente y asignación
se guardan en la misma transacción. Se valida que el grupo siga disponible en el
negocio. Un grupo retirado o un fallo SQL no deja un recuerdo creado a medias;
un reintento exacto devuelve la respuesta anterior incluso si después se retira
el grupo, sin recrearlo. Por revisar crea propuestas y Sin grupo puede guardarse
como asignación explícita. La edición de recuerdos existentes conserva el
selector de tipo y sus controles anteriores.

La ficha es consultable por el cliente. No se inyecta entera al agente: se conserva
la selección inicial de contexto, el catálogo y las herramientas de recuperación.
Una política de contexto permanente para futuros agentes especializados sigue fuera
de este paso.

## CSV, conjuntos y versiones

`POST /api/datasets` prepara un CSV UTF-8 de hasta 20 MB sin llamar al modelo,
crear una conversación, iniciar cálculos ni publicar un informe. Utiliza el mismo
importador, originales y tablas preparadas existentes. El cliente puede abrir un
chat con una versión concreta desde la ficha, o dejar que el agente descubra el
catálogo y aclare la selección cuando sea necesario.

El propietario elige una relación explícita:

- **Independiente:** otro conjunto; no se combinan ni se suman sus filas.
- **Actualización:** la versión elegida deja de ser la predeterminada para nuevas
  búsquedas. Sus informes y cálculos conservan sus fuentes originales; se señala
  que hay datos posteriores sin recalcular. Puede seleccionarse explícitamente
  la versión histórica para otra pregunta.
- **Corrección:** además de crear una versión nueva, la fuente anterior queda
  excluida de nuevas investigaciones y sus dependencias pierden vigencia. Los
  registros y originales se conservan, pero las respuestas e informes afectados
  no se entregan como evidencia válida.

Una corrección afecta la versión seleccionada, no reescribe todas las versiones
históricas de su conjunto. El periodo se declara por versión; no se infiere del
nombre ni se considera cobertura verificada. Las definiciones de una fuente
específica no se trasladan automáticamente a la siguiente versión.

Schema 13 añade `dataset_versions` y `dataset_uploads`. Cada versión apunta a un
lote importado inmutable (`analyses`), separado de las investigaciones y trabajos
web que lo usan. Los lotes anteriores o importados por CLI se presentan como
conjuntos independientes, versión 1, sin una migración destructiva. Al sustituir
uno, se registra su relación con la versión sucesora.

La identidad por contenido y preparación existente evita reimportaciones exactas
incluso si cambia el nombre del archivo. Un reenvío conserva periodo, conjunto y
versión originales; no puede mover una versión ya existente a otro conjunto.
Los CSV distintos con filas solapadas siguen separados. No hay deduplicación de
filas ni fusión general de tablas.

## Recuperación y aislamiento

La carga registra su intención durable antes de importar. Un bloqueo por negocio
serializa la asignación de versiones. El registro de versión, sustitución,
invalidación y respuesta guardada se confirma en una sola transacción bajo el
bloqueo de memoria. Un lote a medio publicar queda fuera del catálogo del agente.

El navegador conserva metadatos y clave de envío para reintentar, incluso tras
recargar; hay que volver a elegir el mismo archivo. Si se interrumpe el servidor
tras preparar el CSV, el reintento recupera el lote y termina la misma relación de
versiones. Otras cargas de ese negocio esperan la recuperación de esa intención.
Un CSV mal formado termina con estado de fallo visible y deja intacta la versión
anterior. No se recalculan informes automáticamente.

Las rutas exigen sesión local y la protección de origen existente. Lecturas,
operaciones de memoria, selección de versiones y descargas están acotadas al
negocio. Las descargas verifican la integridad del original. La ficha no expone
configuración del modelo, credenciales ni rutas del almacenamiento.

## Integración

- `GET /api/business/dossier`: perfil, estado de memoria, recuerdos, historial y archivos.
- `POST /api/business/memory`: adaptador validado al servicio de memoria compartido.
- `POST /api/datasets`: metadatos y un CSV mediante multipart.
- `GET /api/datasets/file/{source_id}`: original conservado.

El catálogo inicial y la búsqueda híbrida comparten la política de versiones.
La corrección se comprueba también al abrir datasets, crear investigaciones,
validar respuestas de chat y exportar informes. Inicio, biblioteca y detalle
señalan los informes que conservan una fuente histórica. La ficha y la ruta de
Archivos incluyen también los CSV cargados sin investigación asociada.

Validación: [pruebas del paso 2.5.5](../validation/2026-09-23-dossier-check.md).
