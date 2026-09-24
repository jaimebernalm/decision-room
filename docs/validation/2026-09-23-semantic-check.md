# Validación de búsqueda semántica — 23 de septiembre de 2026

Ampliación de 2.5.3 solicitada antes de iniciar los chats. [Contrato técnico](../technical/semantic-retrieval.md).
Implementa OpenAI embeddings + pgvector + búsqueda textual en las herramientas
existentes; no cambia la autoridad de los originales ni la evidencia numérica.

## Pruebas automatizadas

- Suite final completa: **214 pruebas, OK**, 100,446 segundos; `compileall` y revisión de diferencias correctos.
- Primera suite completa: **212 pruebas, OK**, 92,076 segundos.
- Tras añadir comprobaciones de caché entre negocios, replay híbrido, recuperación
  de indexación parcial y límite de fragmentos: **13 pruebas semánticas, OK**.
- PostgreSQL real con pgvector 0.8.6; embeddings controlados para comprobar mecánica,
  sin presentarlos como evaluación de lenguaje.
- Migración 10→11: rollback de extensión/tablas ante fallo, reintento e idempotencia.
- Corrección y retirada excluyen vectores antiguos que deliberadamente siguen en
  la base. Las revisiones históricas se recuperan solo en su periodo aplicable.
- Negocio, fuente y periodo se filtran antes de enviar texto al proveedor. Un vector
  de otro negocio con la misma clave/huella no participa en la recuperación.
- Correcciones durante embeddings y cambios en metadatos de tablas descubiertas
  impiden persistir contexto obsoleto. Informes retenidos o incompatibles no entran.
- Caída del proveedor: diagnóstico textual explícito, dudas preservadas y sin
  reintento automático. Un segundo lote fallido conserva el primero para recuperar
  después. Replay de una recuperación persistida no repite llamadas.
- Fragmentos Unicode acotados; búsqueda sobre fragmentos posteriores; cachés
  separadas por modelo/dimensión; límites de 1000 objetos y 512 fragmentos.
- Transporte oficial validado, vectores malformados rechazados y errores sin
  credenciales ni cuerpos privados del proveedor.

## Calidad con embeddings reales

Comando: `scripts/evaluate_semantic.py --output .local/semantic-eval-first --compare-large`.
Ocho descripciones sintéticas, diez consultas españolas con distractores y tres
repeticiones independientes por modelo. No se modificaron consultas, expectativas ni
criterios después de observar los resultados. Se prueba el buscador compartido;
no representa todavía un historial amplio de clientes o chats.

| Buscador | Esperado entre los 3 primeros | Esperado primero | Repeticiones |
|---|---:|---:|---:|
| Textual PostgreSQL | 1/10 | 1/10 | 3 por modelo |
| Híbrido, `text-embedding-3-small`, 1536 dimensiones | 10/10 | 8/10 | 3 |
| Híbrido, `text-embedding-3-large`, 1536 dimensiones | 10/10 | 9/10 | 3 |

La consulta «facturación de mercancías» recuperó ventas en **segunda posición con
ambos modelos**. `small` situó primero proveedores y `large` inventario. «Qué nos
queda guardado para poder vender» situó inventario tercero con `small` y primero
con `large`. Se mantienen estos fallos de ordenación en los resultados; no se
presenta la similitud como una identificación inequívoca.

Los dos modelos superan el criterio prefijado (100% entre los tres primeros y al
menos 80% primero). Se conserva `small` como configuración inicial: la diferencia
de un caso no justifica exigir `large` en este corpus pequeño. El modelo es
configurable y habrá que ampliar la evaluación al añadir conversaciones.

Ronda completa: **60 búsquedas híbridas**, 26,88 segundos; 33 llamadas y 837 tokens
de entrada por modelo (incluye indexación de los ocho textos en cada repetición).
Los originales y vectores se generaron en una base aislada eliminada al terminar.

## Recorrido real con Luna y corrección de memoria

Comando: `scripts/evaluate_context.py --semantic --output .local/semantic-agent-first`.
Modelo conversacional `gpt-6-luna`, razonamiento `low`, embeddings
`text-embedding-3-small`, 1536 dimensiones. Datos sintéticos: dos filas con
cantidades 2 y 3 e importes 10 y 20.

1. Primera sesión: utiliza la definición persistente de precio unitario; total
   revisado **80**, sin repetir la pregunta sobre significado del importe.
2. Segunda sesión: busca «facturación de mercancías» con `search_reports`, recibe
   `search.mode=hybrid`, abre el antecedente con `open_report` y produce total **80**.
3. Corrección histórica: el importe pasa a ser total de fila. Los dos informes
   anteriores dejan de ser publicables; replanificar produce total revisado **30**.

Resultado: **correcto**, 106,4 segundos, 21 llamadas a Luna; 142.858 tokens de
entrada y 10.068 de salida. Dos llamadas de embeddings (documento y consulta),
558 tokens de entrada. Las búsquedas sin antecedentes no llamaron al proveedor.
La evaluación verifica las cifras citadas contra valores esperados independientes.

## Operación y límites

Activación en el entorno privado local con `DECISION_ROOM_SEMANTIC_SEARCH=true`.
La preview existente en el puerto 8792 se reinició sin trabajos en curso y conservó
su estado; se verificaron esquema 11 y extensión 0.8.6. No se modificaron credenciales.
Las nuevas instalaciones requieren activar la opción y disponer de pgvector.

El índice se mantiene bajo demanda, no mediante un trabajador de preindexación.
La primera búsqueda puede tardar más; los derivados antiguos se conservan pero
quedan excluidos por huella/versión. No hay limpieza automática, paginación general,
índice aproximado ni umbral global de relevancia. La búsqueda puede devolver un
candidato poco pertinente: el agente sigue teniendo que comprobar originales.
No hay UI nueva en este incremento. Los chats y su evaluación siguen en 2.5.4.

Los resultados privados están en `.local/semantic-eval-first/`,
`.local/semantic-agent-first/` y los logs de pruebas, excluidos de Git. La suite y
los casos reales demuestran estos escenarios; no certifican la calidad general
de todas las respuestas ni cierran las incidencias analíticas anteriores.
