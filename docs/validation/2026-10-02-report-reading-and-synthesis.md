# 3.9.8 — Primera lectura y síntesis conjunta

Fecha: 2 de octubre de 2026. Continuidad sobre la interfaz integrada y la rama
de calidad. El propietario solicita presentación y síntesis de agentes juntas.
Se completan los seis pasos del [plan](../technical/report-reading-plan.md#398-primera-lectura-y-síntesis-sobre-la-interfaz-integrada).
La aceptación analítica de 3.9.7 permanece abierta.

## Comportamiento implementado

- Resumen revisado completo al principio, una sola vez. Índice con los títulos
  existentes que desplaza y enfoca cada hallazgo por teclado dentro de su informe,
  sin abrir detalles, cambiar ruta ni solicitar cálculos o datos nuevos.
- Prioridad, próxima comprobación, utilidad y reacciones condicionales completas
  en bloques legibles. Se conserva el detalle progresivo y la compatibilidad de
  informes históricos; no se extraen ni truncan conclusiones en el navegador.
- Fechas temporales localizadas conservando claves, selección y coordenadas.
  Controles traducidos; cifras exactas intactas. Tooltip agrupado contenido en el
  gráfico, más espacio para nombres y periodos largos que se ajustan en móvil.
- Planificador v10 y revisión v47 coordinan respuesta principal y orden de lectura.
  Resumen, conclusión, interpretación y orientación tienen funciones distintas;
  los límites materiales siguen explícitos. La brevedad es una sugerencia, no un
  nuevo bloqueo de aprobación.
- `report_reading` informa de longitud y localizaciones de repeticiones exactas
  en una copia del contexto del modelo. No elimina texto automáticamente, no
  detecta equivalencia semántica y no cambia el material ni la huella de aprobación.

## Verificación técnica y visual

- **607 pruebas Python** pasan en PostgreSQL aislado y desechable, con proveedor
  simulado. Incluyen contexto, contratos, revisión, evidencia y exportación.
- **223 pruebas frontend** pasan; compilación y lint terminan correctamente.
  Persisten advertencias conocidas de Fast Refresh/efectos y tamaño del bundle.
- Pruebas nuevas comprueban resumen completo una sola vez, navegación por teclado
  acotada al informe incluso con identificadores repetidos, detalles cerrados,
  ausencia de llamadas al navegar, idioma y selección con claves originales,
  precisión decimal, condiciones sin prefijo duplicado y feedback sin mutaciones.
- Se comprueban seis recorridos históricos: Bruma escritorio/móvil en español e
  inglés, WWI organización escritorio/móvil en español. Se corrige un desbordamiento
  real del periodo largo en móvil y se repite la comprobación. Se inspecciona el
  tooltip agrupado en móvil con nombres y valores completos.
- Se comprueban seis vistas de borradores: tres casos, escritorio y móvil. Todos
  conservan sus cuatro gráficos, sin errores JavaScript ni desbordamiento horizontal.

## Prueba de redacción con proveedor real

Tres casos guardados: Bruma descubrimiento, WWI descubrimiento y WWI organización
(este último usa el informe recuperado, conservando el fallo histórico original).
Se congela la investigación, incluyendo cálculos, referencias, gráficos, unidades,
periodos, selección y cobertura. Cada caso realiza una generación de analista y
una revisión con **gpt-6-luna**: seis respuestas reales, sin investigar de nuevo.
Se guardan contexto, respuestas, controles, recursos y fallos en artefactos locales
ignorados bajo `.local/report-reading-3-9-8/`.

| Caso | Palabras de primera lectura, antes → después | Resumen, antes → después | Controles de evidencia | Revisor del experimento |
| --- | --- | --- | --- | --- |
| Bruma descubrimiento | 759 → 578 | 66 → 49 | 14 pasan | Aprueba |
| WWI descubrimiento | 753 → 748 | 36 → 36 | 11 pasan | Aprueba |
| WWI organización | 380 → 378 | 45 → 43 | 13 pasan | Aprueba |

La primera lectura contabiliza resumen, límites globales, conclusiones,
orientación visible y captions; excluye interpretación y método plegados. No
es una medida de tiempo real de lectura ni una rúbrica de utilidad. Ningún caso
tenía repeticiones exactas detectadas antes o después: el diagnóstico no explica
por sí solo la reducción de Bruma y no detecta redundancia semántica.

Bruma conserva la divergencia entre Marketplace y Tienda física y el foco Kit de
iniciación — Web propia como observaciones descriptivas, con calendario operativo
pendiente y reacciones condicionadas. WWI conserva cifras y límites de cobertura.
El control de estructura y evidencia se complementa con inspección de la prosa;
no demuestra por sí solo que cada interpretación sea útil para el propietario.

Consumo declarado en respuestas aceptadas: **708.920 tokens de entrada** y
**19.843 de salida**. No se convierte a coste. El revisor de WWI organización
recibe un **429 por tokens**, espera aproximadamente 9,2 segundos y completa el
reintento. Se conserva el intento rechazado con uso desconocido: el total
anterior no atribuye consumo al rechazo y no demuestra que el rate limit esté
resuelto. La dosificación compartida sigue pendiente.

El ejecutor del experimento tuvo errores de preparación: una ruta apuntaba a un
intento histórico sin informe; el contexto de validación usaba el historial de
direcciones en vez de la vigente; y se trató el resultado de validación como un
objeto cuando devuelve un diccionario. Se corrigió el ejecutor y se reutilizaron
las respuestas de analista ya guardadas, sin generar otras para ocultar fallos.
Se conservan resultados iniciales, contextos y registros de recuperación. Estos
errores del ejecutor no se contabilizan como errores del modelo.

## Entrega y límites

La vista local permite alternar texto original y nuevo en la misma interfaz,
con gráficos y cifras idénticos. Se identifica como borrador de prueba sin
publicación en el producto; los informes históricos permanecen intactos.

Este experimento evalúa redacción con evidencia congelada, **no tres recorridos
completos nuevos**. No prueba la intervención del planificador en investigación
real ni sustituye la evaluación independiente de utilidad: el fallo previo de
prioridad en WWI descubrimiento permanece sin reevaluar. Bruma mejora en concisión;
WWI apenas cambia. No se declara mejora consistente ni cierre de 3.9.7.

Siguiente comprobación: lectura conjunta del propietario para identificar la
prioridad y próxima acción sin ayuda, y después una evaluación de investigación
completa con la misma rúbrica independiente y fallos conservados.
