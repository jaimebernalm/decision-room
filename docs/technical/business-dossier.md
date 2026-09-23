# Mi negocio y datos reutilizables · 2.5.5

## Resultado y recorrido

La ficha tiene Información, Datos y archivos, y Cambios. Presenta declaraciones,
propuestas, contradicciones y dudas, con texto original, ámbito, fechas y revisiones.
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
