# Recuperación semántica híbrida — ampliación de 2.5.3

OpenAI genera embeddings; PostgreSQL con pgvector almacena el índice derivado. El
agente conserva sus herramientas y decide cuándo buscar. El punto de partida y
las dudas materiales siguen sujetos al [contrato de contexto](context-retrieval.md).
Esta ampliación inicial busca datos, recuerdos e informes. Desde [2.5.4](conversations.md), `search_chats` usa el mismo índice para fragmentos históricos, tras filtrar negocio y ámbito y comprobar vigencia.

## Configuración y despliegue

El servidor PostgreSQL debe disponer de la extensión `vector`. La migración 11
ejecuta `CREATE EXTENSION IF NOT EXISTS vector` dentro de la transacción de
migración; requiere permisos para instalar extensiones. La instalación local de
Postgres.app utilizada por el proyecto ya incluye pgvector 0.8.6. En otro servidor
hay que instalar una versión compatible antes de migrar; no se descarga ni instala
software de sistema automáticamente. Véase [pgvector](https://github.com/pgvector/pgvector#installation).

La aplicación web carga `.env`. Para activar esta función:

```dotenv
DECISION_ROOM_SEMANTIC_SEARCH=true
DECISION_ROOM_EMBEDDING_MODEL=text-embedding-3-small
DECISION_ROOM_EMBEDDING_DIMENSIONS=1536
```

Configurar también `OPENAI_API_KEY` localmente y reiniciar el trabajador. No guardar
credenciales en Git. El modo predeterminado de una instalación sin configurar sigue
siendo textual, para no convertir el uso de un agente local en llamadas externas
implícitas. La API de embeddings recibe el texto buscable y las consultas; sus
llamadas tienen facturación independiente del modelo conversacional.

Se admiten `text-embedding-3-small` y `text-embedding-3-large`, con dimensión explícita
entre 256 y el máximo de cada modelo. Las consultas y documentos de una búsqueda
usan el mismo modelo y dimensión. El endpoint es exclusivamente
`https://api.openai.com/v1/embeddings`; no se reutiliza la URL del agente, no se
heredan proxies ni se siguen redirecciones. Referencia: [OpenAI Docs](https://developers.openai.com/api/docs/guides/embeddings).

## Corpus, fragmentos y búsqueda

1. Se leen originales del negocio autorizado. En memoria se aplican ámbito y
   periodo; los informes deben superar los controles actuales de publicación y
   compatibilidad temporal antes de indexarse. Las tablas se descubren por título,
   nombres y columnas; no se vectorizan filas. Su cobertura temporal puede ser desconocida.
2. Se preparan fragmentos de hasta 4000 bytes UTF-8, con 400 bytes de solapamiento
   respetando caracteres. El límite por bytes mantiene cada entrada bajo el límite
   del tokenizer byte-BPE de estos modelos sin añadir una dependencia de tokenización.
3. `semantic_chunks` guarda negocio, tipo, referencia, huella de contenido y versión,
   modelo, dimensión, ordinal, fragmento y vector. Solo se generan fragmentos ausentes.
4. La consulta se vectoriza y se compara mediante distancia coseno exacta en pgvector.
   Se combina con búsqueda textual española de PostgreSQL mediante RRF, con peso
   igual y constante 60. Cada buscador aporta hasta 50 candidatos; la herramienta
   devuelve hasta 10. Un documento con varios fragmentos utiliza su mejor coincidencia.
5. Se comprueban de nuevo originales/versiones después de las llamadas externas y
   antes de guardar la recuperación. El bloqueo de memoria se mantiene solo durante
   la comprobación y escritura final, nunca durante la petición al proveedor.

El modo exacto evita pérdidas debidas a filtros sobre índices aproximados. No se
ha añadido HNSW ni se afirma escalabilidad ilimitada: hay un máximo de 1000 objetos
por búsqueda y 512 fragmentos semánticos. Superar 1000 objetos exige acotar; superar
512 fragmentos produce búsqueda textual explícita. No hay paginación general.
Las llamadas se agrupan en lotes de 32 y tienen 30 segundos de timeout por petición.
Una búsqueda fría sobre un corpus amplio puede requerir varios lotes.

La similitud produce candidatos incluso cuando no existe una respuesta pertinente;
no se ha calibrado un umbral global de relevancia. El agente debe inspeccionar las
fuentes y abrir los informes antes de usar conclusiones. Las cifras nuevas siguen
requiriendo cálculo y revisión. Las definiciones, disponibilidad, preguntas abiertas
y recuerdos propuestos/conflictivos se conservan aunque no entren en los primeros
resultados. Si no caben en 48 KB, se pausa; la semántica no los oculta.

## Correcciones, mantenimiento y fallos

El índice se actualiza bajo demanda en la primera búsqueda tras un cambio. Cada
búsqueda une los vectores exclusivamente con las referencias y huellas calculadas
a partir de originales actualmente aplicables. Un embedding viejo puede permanecer
almacenado, pero no puede recuperar un hecho corregido o retirado. Las revisiones
históricas válidas se conservan para su periodo. Cambiar de modelo/dimensión crea
una caché separada, sin mezclar espacios vectoriales.

No hay trabajador de preindexación ni limpieza automática de cachés antiguas en
este incremento. Se pueden eliminar los derivados para reconstruirlos; no se deben
eliminar originales, revisiones ni manifiestos. Una instalación con mucho historial
necesitará evaluar limpieza, preindexación e índices aproximados antes de ampliar
estos límites.

Si falla OpenAI, falta la clave o devuelve vectores inválidos, se entrega la búsqueda
textual con `search.mode=text_fallback` y un diagnóstico sin cuerpo del proveedor ni
credenciales. No hay reintento automático dentro de la búsqueda. Una búsqueda nueva
puede volver a intentarlo. Un proceso interrumpido puede dejar una llamada `running`;
no se interpreta como completada y un nuevo intento puede generar otro cargo.

`semantic_calls` registra llamadas, modelo, dimensión, huella de entrada, propósito,
estado y uso. `context_retrievals.response.search` conserva modo, versión del buscador,
modelo/dimensión, candidatos entregados, versiones, posiciones, puntuaciones y un
extracto del fragmento coincidente. El replay de una recuperación ya persistida no
consulta de nuevo ni llama a embeddings. Toda esa información es privada y se trata
como contenido, nunca como instrucciones.

## Pruebas reproducibles

```sh
.venv/bin/python -m unittest discover -s tests
.venv/bin/python scripts/evaluate_semantic.py --output .local/semantic-evaluation --compare-large
.venv/bin/python scripts/evaluate_context.py --semantic --output .local/semantic-agent-evaluation
```

Las dos evaluaciones usan bases aisladas y datos sintéticos; guardan resultados
locales y eliminan sus bases al terminar. Requieren OpenAI configurado; la segunda
también requiere el sandbox. La primera repite diez consultas contra ocho documentos
tres veces por modelo, sin caché compartida entre repeticiones. El criterio fijado
antes de ejecutar exige 100% de recuperación entre los tres primeros y al menos
80% en primera posición; no equivale a validación general con datos de clientes.
