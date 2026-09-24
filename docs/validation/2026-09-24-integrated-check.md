# Evaluación integrada de 2.5.7

Fecha: 24 de septiembre de 2026. Datos sintéticos y fixtures públicos; bases de
PostgreSQL aisladas. Los registros con mensajes, llamadas y rutas locales quedan
fuera de Git. Esta aceptación corresponde al producto local y a estos escenarios.

## Fallos reproducidos y correcciones

1. **Conflictos de una fuente ocultos en el chat.** El agente recibía los recuerdos
   del archivo seleccionado, pero la consulta de la interfaz usaba una lista vacía
   de fuentes. No aparecían los controles para resolver la contradicción. El detalle
   del chat y la captura del contexto comparten ahora la consulta de fuentes del
   negocio y conjunto seleccionados. La prueba falla antes del cambio y pasa después;
   otro chat sin ese conjunto no recibe el recuerdo. También se resolvió una
   contradicción de inventario desde la interfaz real.
2. **Trabajo pendiente oculto por informes recientes.** La consulta limitaba los
   doce turnos recientes antes de descartar los informes ya publicados. Catorce
   publicaciones posteriores podían ocultar una pregunta aún en cola. Se priorizan
   los turnos pendientes en SQL y los trabajos pendientes en la selección final de
   Inicio. La prueba reprodujo el fallo y pasó después. La prueba anterior que
   suponía orden exclusivamente cronológico se adapta al orden nuevo, conservando
   las comprobaciones de respuesta lista y retirada por su conversación.

## Recorrido integrado con modelo real

Nuevo comando optativo: `python scripts/evaluate_daily.py --output DIRECTORIO`.
Requiere el entorno de PostgreSQL, sandbox y modelo configurado como los demás
scripts de evaluación. Crea una base aislada y la elimina al terminar; `--keep`
conserva exclusivamente su base de prueba para inspección visual posterior.
Guarda comprobaciones, tiempos, llamadas, consumo, preguntas, trabajos y revisiones.
La aceptación exige que el código de producción no cambie durante la ejecución.

La ronda final pasó **23 comprobaciones**, en **248,14 segundos**, con GPT-6 Luna,
razonamiento bajo. Huella SHA-256 de los archivos Python de producción:
`f1706ab055df09abbbdc2cc20ff3daf7e7d705961627b297d23458866e96e0b2`.

- Alta del negocio por HTTP y conservación de su selección.
- Declaración de cierre dominical reutilizada en otra conversación.
- Hipótesis semanal conservada como propuesta; recuperación de su mensaje original
  mediante una pregunta natural distinta, sin nombrar herramientas.
- Selección de ventas de agosto sin conjunto preseleccionado, frente a ventas de
  julio y existencias distractoras.
- Total y dos series completos calculados independientemente con `Decimal` sobre
  los CSV de entrada, sin tomar como referencia la respuesta del agente.
- Publicación en Inicio y explicación del hallazgo exacto sin otro cálculo.
- Corrección de la definición guardada: retirada del informe dependiente y
  exportación rechazada; recálculo en el mismo chat sin volver a cargar el CSV.
- Nueva versión de datos que conserva el informe histórico; corrección posterior
  que retira solamente el informe afectado.
- Cambio a otro negocio: conversaciones y dashboard separados, acceso ajeno
  rechazado incluso con identificadores válidos de chat y hallazgo.
- Recuperación de negocio, conversaciones e informe seleccionado tanto al recrear
  el servidor HTTP como desde un intérprete Python nuevo, sin caché en memoria.

| Estado | Total EUR | Fechas: 1 y 2 de agosto | Categorías A y B |
|---|---:|---|---|
| Precio unitario | 150,00 | 65,00; 85,00 | 70,00; 80,00 |
| Corregido a total de fila | 87,50 | 52,50; 35,00 | 27,50; 60,00 |
| Actualización de datos | 92,50 | 52,50; 40,00 | 27,50; 65,00 |
| Corrección de datos | 102,50 | 52,50; 50,00 | 27,50; 75,00 |

Se revisaron también texto, método, alcance y limitaciones de los cuatro informes.
No extrapolan a todo agosto ni calculan beneficios. **Cero preguntas de definición
repetidas** y cero preguntas analíticas adicionales en esta ronda.
Los cuatro cálculos tardaron 68,33 / 44,29 / 50,19 / 56,67 s; recuperar memoria,
antecedentes o explicar un hallazgo tardó entre 2,56 y 5,83 s. Son mediciones locales
con concurrencia de evaluaciones, no un SLA ni percentiles de producción.

| Componente | Llamadas | Tokens de entrada | Tokens de salida |
|---|---:|---:|---:|
| Planificación, cálculo y revisión | 26 | 238.568 | 18.477 |
| Conversación | 10 | 25.672 | 672 |
| Extracción de memoria | 9 | 14.850 | 882 |
| Embeddings | 2 | 47 | No aplica |

El consumo está reportado por el proveedor. No se interpreta como coste neto ni
se resta caché. La ronda exploratoria previa también pasó el recorrido, pero no
se usa como aceptación congelada porque se editaron archivos mientras corría.

## Otras matrices reales

- Memoria: **24/24**, ocho escenarios con tres repeticiones: vigencias ambiguas y
  futuras, hipótesis, ámbitos, contradicciones, retirada, instrucciones incrustadas
  no confiables y reformulación equivalente.
- Conversación/ficha: **6/6**, reutilización entre chats, datos existentes,
  explicación de informe, corrección de memoria, antecedentes y corrección de CSV.
- Búsqueda semántica: **30 consultas**, diez casos repetidos tres veces sobre ocho
  documentos, incluidos candidatos distractores; recall@3 **1,00**, top-1 **0,80** en cada repetición, frente a
  recall@3 léxico **0,10**. `text-embedding-3-small`, 1.536 dimensiones.
  Un candidato semántico sigue requiriendo comprobar fuente, ámbito y vigencia.

## Comprobación visual y recuperación

- Primer acceso en una base vacía: guardar una librería ficticia, abrir Inicio,
  enviar una pregunta sugerida y reutilizar el cierre de los martes indicado en
  el onboarding. No exige CSV ni pide otra vez nombre y descripción.
- Ficha con memoria declarada/propuesta, ámbito y definición de archivo; resolución
  desde el chat de una contradicción asociada a su fuente.
- Dos pestañas editando la misma prioridad: la segunda escritura recibe conflicto,
  conserva su texto y no pisa la primera revisión.
- Inicio cambia entre v3 (102,50) y v1 (87,50), con series correspondientes y aviso
  histórico. La versión retirada no se ofrece como informe disponible.
- Servidor detenido antes del envío: aviso de conexión y borrador conservado.
  Reinicio y reenvío por teclado: un solo chat y mensaje, respuesta con memoria
  compartida correcta. Los datos previamente guardados permanecen.
- Escritorio 1.280 × 720, móvil 390 × 844 y altura reducida a 390 × 420:
  sin desbordamiento horizontal; compositor y botón de envío accesibles por Tab.
  Inspección visual del compositor enfocado, sin superposición con resultados.
- Sin errores de JavaScript registrados durante ese recorrido.

El móvil se prueba con viewport y teclado de escritorio, no con un teléfono físico.
No se validan carga elevada, lector de pantalla, despliegue comercial ni capacidades
fuera de 2.5. Las respuestas de memoria aún usan una presentación estructurada;
esta evaluación no promete calidad general para cualquier pregunta o conjunto.

## Regresión y cierre

- Suite final: **245 pruebas Python**, OK, 121,55 s.
- **12 pruebas JavaScript**, OK; sintaxis de `app.js` y `dossier.js`, OK.
- Las dos pruebas nuevas fallaban antes de los cambios y pasan con la corrección.
  La suite incluye recuperación de respuestas guardadas, reintentos simultáneos,
  pérdida de enlaces entre trabajos, revisiones concurrentes, aislamiento y
  propagación de invalidación. No se sustituyen estas comprobaciones por que el
  modelo diga que un informe es correcto.
- Regresión analítica: **12/12 escenarios aceptados**, una repetición por caso,
  con revisión de desarrollo explícita de definiciones, alcance, narrativa,
  preguntas y todos los números presentados. Las cifras se vinculan a referencias
  `Decimal`; las series se contrastan por fecha/producto contra los CSV originales.

| Caso | Resultado comprobado |
|---|---|
| Ventas diarias y columnas renombradas | 34.137,85 / 39.646,25 por intervalo; diferencia 5.508,40 |
| Productos y columnas renombradas | Mismos intervalos; producto líder 3 con 32.745,00; ocho productos verificados |
| Precio unitario | 1.220,00 y 59 unidades, tras aclarar la definición |
| Total de fila | 257,50 y 59 unidades, sin multiplicar otra vez |
| Definición desconocida / respuesta declinada | 59 unidades; total monetario no disponible; sin insistir |
| Duplicados | 13 filas → 12 líneas únicas; 1.220,00 y 59 unidades |
| Importes ausentes | 870,00 solo en 10 filas con importe; 59 unidades en las 12 filas |
| Devoluciones | 1.195,00 y 58 unidades netas; signos y ambas series conservados |
| Fechas/importes inválidos | 69.494,35 en 21 filas; tres exclusiones explicadas |

La matriz analítica usa una copia congelada de `66e396c`, huella Python
`b3dd46f734494850ae4822aa5e004e2f77390e775d7d9ba837dad354110bee8b`.
Las correcciones posteriores afectan a la presentación de memoria y actividad;
el motor analítico no cambió. El recorrido HTTP final y la suite completa sí
corren sobre el código corregido. Cada caso completado se reanuda sin nuevas
llamadas al modelo. La matriz consume 87 llamadas, 800.573 tokens de entrada y
77.639 de salida; suma 876,66 s de fases medidas. El consumo está completo para
estas ejecuciones y no incluye rondas exploratorias ni fallos de preparación.

Los intentos de preparación se conservan separados: primero se apuntó a una base
antigua sin la migración de contexto; después la copia congelada no tenía el
manifiesto del sandbox ni su directorio de entradas compartido con Docker.
Se corrigió el entorno con una base aislada migrada y los recursos de sandbox
correctos. Esos intentos fallidos no se cuentan como casos aceptados ni como
fallos de exactitud del modelo. No se borraron sus registros para mejorar la tasa.

Artefactos privados de esta ronda: `.local/257-daily-final`,
`.local/257-memory`, `.local/257-semantic`, `.local/257-conversations-baseline`
y `.local/evaluation/257-legacy-final`, incluidas las evaluaciones independientes
por escenario. Los servidores locales habituales se reiniciaron con las
correcciones después de comprobar que no tenían trabajos activos; sus datos
permanecen conservados.

Se cierra **2.5.7** dentro de este alcance local, sin fallos materiales abiertos en
la matriz ejecutada. Sigue siendo necesario comprobar otros datos y preguntas
al ampliar cobertura; no se afirma exactitud universal ni preparación comercial.
