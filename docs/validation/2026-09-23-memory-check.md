# Paso 2.5.2: memoria versionada y corregible

**Fecha:** 23 de septiembre de 2026.  
**Resultado:** incrementos A–D implementados y comprobados. Los pasos 2.5.3–2.5.7 siguen pendientes.  
**Referencias:** [plan incremental](../technical/business-memory-implementation.md#252-memoria-versionada-y-corregible) y [plan aplicado, contrato y guía del servicio](../technical/memory.md).

## Implementación

PostgreSQL conserva originales, recuerdos, revisiones, ámbitos, vigencia, llamadas del modelo y operaciones idempotentes. No se ha introducido Markdown como almacenamiento de autoridad. Las fuentes de memoria se capturan en la misma transacción que el perfil o la nueva respuesta del cliente. El trabajador procesa la extracción después; una respuesta analítica ya existente no se reinterpreta automáticamente.

El servicio permite proponer, declarar, confirmar, corregir, retirar y consultar estado e historial. Comprueba revisión y negocio, conserva alternativas contradictorias y marca las versiones sustituidas. La extracción exige citas del original y referencias autorizadas. Las hipótesis y las fechas ambiguas permanecen propuestas; una definición de archivo conserva su ámbito. La retirada impide reactivación automática por tema/ámbito/periodo, conservando origen e historial.

La cola distingue pendiente, extracción en curso, respuesta recibida, aplicada, fallo, llamada incierta y perfil sustituido. La respuesta del modelo se persiste antes de aplicar recuerdos. Un reintento reutiliza una respuesta válida cuando puede, pero debe extraer de nuevo si cambió la memoria. Las llamadas inciertas no se repiten automáticamente. La web muestra estos estados y permite reintentar dentro del negocio activo.

Archivos principales: `decision_room/memory/`, esquema 9, adaptador del modelo, captura de respuestas del principal/revisor, servicio y formulario web; pruebas de memoria, migración y web; ejecutor reproducible `scripts/evaluate_memory.py`.

## Pruebas automatizadas

```sh
.venv/bin/python -m unittest discover -s tests -v
node --check decision_room/web/static/app.js
git diff --check
```

**181 pruebas correctas en 77,317 segundos**, incluidas 22 pruebas específicas de memoria, 30 web y 5 de migración. PostgreSQL y sandbox reales; roles controlados en la suite. Sintaxis JavaScript y revisión de diferencias correctas.

| Comprobación | Resultado |
|---|---|
| Declaración → corrección → retirada | Historial conservado; lectura desde otro proceso recupera el estado |
| Reenvíos y dos ediciones concurrentes | Sin duplicación; una edición gana y la obsoleta recibe conflicto |
| Propuesta, hipótesis y «no lo sé / prefiero no responder» | No se convierten en una definición confirmada |
| Fuente ajena, otro negocio y periodos diferentes | Acceso rechazado o conocimiento excluido del ámbito correspondiente |
| Fechas futuras y vigencia ambigua | Fecha futura respetada; ambigüedad exige corrección antes de confirmar |
| Contradicción y retirada con frase reformulada | Alternativas conservadas; no se reactiva lo retirado |
| Cita inventada, ámbito ampliado o resultado fabricado | Toda la aplicación de candidatos se revierte |
| Fallo al registrar memoria junto al perfil/respuesta | Transacción revertida; el reintento web conserva el texto pendiente |
| Fallo/interrupción durante llamada | Estado recuperable o incierto; sin repetición automática |
| Interrupción después de guardar respuesta del modelo | Recuperación sin otra llamada ni recuerdos duplicados |
| Cambio de memoria mientras se extrae | Reextracción obligatoria; respuesta obsoleta no reutilizable tras otro fallo |
| Dos extractores simultáneos | Una sola llamada y aplicación |
| Migración 8 → 9 y repetición | Perfil como fuente pendiente; informes, originales y respuestas anteriores intactos |
| Migración fallida | Reversión transaccional, incluidos los objetos de memoria |
| HTTP de reintento | Autenticación y negocio activo respetados; pestaña con selección obsoleta rechazada |

## Evaluación con modelo real

Se ejecutó `scripts/evaluate_memory.py` con `gpt-6-luna`, proveedor OpenAI, ocho escenarios ficticios y tres repeticiones independientes por escenario. Cada repetición utilizó un negocio distinto en una base temporal. Los originales, respuestas completas, consumo y criterios por caso están en `.local/memory-evaluation-252-temporal/`, excluido de Git.

| Escenario | Repeticiones aceptadas |
|---|---|
| Negocio declarado, apertura futura e intención de vender online | 3/3 |
| Definición de IVA y costes ausentes, limitados al archivo | 3/3 |
| «No lo sé» escrito como respuesta libre | 3/3 |
| Corrección contradictoria de una definición anterior | 3/3 |
| Recuerdo retirado expresado de otra forma | 3/3 |
| Instrucciones citadas de un correo ajeno | 3/3 |
| «Desde septiembre» sin año conocido | 3/3 |
| Repetición equivalente con otras palabras | 3/3 |

**Ronda final: 24/24 aceptados.** Duración acumulada de extracción/aplicación: 89,69 segundos; mediana 3,045 s, mínimo 1,55 s y máximo 7,19 s por caso. El proveedor registró 22.127 tokens de entrada y 4.508 de salida. No se ha estimado coste monetario.

Hubo dos rondas previas conservadas: una inicial de siete escenarios aceptó 21/21; la ampliación a ocho aceptó 22/24 y detectó dos fallos en fecha ambigua. El modelo podía marcar una frase como explícita y dejar las fechas nulas, sin distinguir ausencia de restricción de una restricción temporal sin resolver. Se añadió `temporal_scope`, validación y bloqueo de confirmación para `unresolved`, una prueba de regresión y una repetición completa de la matriz. Los 24 resultados finales corresponden al contrato corregido; no se han ocultado los fallos anteriores.

La rúbrica comprueba invariantes concretos sobre los recuerdos guardados y se revisaron los textos producidos. Estos resultados no demuestran detección universal de contradicciones ni eliminan la dependencia semántica del modelo. Los temas ambiguos pueden requerir revisión; no se certifica todavía el uso de esta memoria para publicar análisis.

## Navegador y persistencia

En una base ficticia separada se guardó una papelería con dos tiendas, apertura dominical futura y posible venta online. La web mostró primero memoria pendiente y luego una propuesta pendiente de confirmar; PostgreSQL conservó las declaraciones y la fecha futura separadas de la hipótesis.

Se simuló un fallo recuperable de extracción, se pulsó «Reintentar memoria» y se comprobó que reutilizaba el original sin rellenar otra vez el formulario. También se verificó la recuperación tras reiniciar el servidor. Revisión visual en escritorio y a 390 × 844, sin desbordamiento horizontal; consola sin errores. Los avisos se actualizan sin reemplazar el borrador del formulario.

## Límites y siguiente incremento

No se ha migrado la base privada de trabajo durante las pruebas; la migración se aplicará al arrancar la aplicación actualizada, tras detener instancias antiguas de esa base. La extracción tiene límites de 20 candidatos por respuesta y 200 recuerdos actuales de contexto; superar el límite conserva el original y deja un fallo explícito.

Las operaciones de mantenimiento están disponibles en el servicio; la ficha de edición de recuerdos llegará en 2.5.5. No se ha añadido chat ni reutilización automática de recuerdos en planificación, investigación o revisión. Tampoco se ha implementado propagación de correcciones entre sesiones: corresponde a 2.5.3.

**Siguiente incremento:** 2.5.3.A, selección y registro de las versiones de contexto utilizadas. El commit de cierre incorpora este informe; su hash se comunica al entregar el paso. No se realiza push sin petición expresa.
