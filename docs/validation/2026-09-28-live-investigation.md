# Validación del paso 3.8 — Actividad e investigación en directo

**Fecha:** 28 de septiembre de 2026. **Resultado:** implementación y comprobaciones
funcionales completadas. Base `2063fc5`, rama `feature/insights-pipeline`, checkout
asignado `.local/insights-pipeline-worktree`. Persistencia inicial guardada en
`551902a`; `4eb62ac` guarda instrumentación/API, `274b5ac` la interfaz y `bc0cdc6` la selección exacta del evento; el commit documental registra el cierre.

[Plan y criterios](../technical/live-investigation-plan.md) ·
[Uso y contratos finales](../technical/live-investigation.md)

## Alcance comprobado

- Línea real de actividad, historial plegable, tareas y propósito cuando existe,
  datos relacionados y acceso desde informe completado. Se usa el mismo componente
  en chat, onboarding, trabajo en curso e informe.
- Monitor independiente: lista y filtros, mapa de participantes reales, tareas
  delegadas, cronología, mensajes explícitos, cálculos, revisión y recursos conocidos.
- PostgreSQL real, migración 24→25, sandbox Docker real, modelo guionizado para
  estados adversos y una creación de informe real de Bruma con Luna.
- La vista original del usuario en 8791 conserva su servidor/base anteriores;
  no se migró ni reinició durante esta validación. La demostración aislada usa 8792.

## Comprobaciones automatizadas

Las pruebas Python usan `PYTHONPATH=tests`, `.venv/bin/python -m unittest` y un
`DECISION_ROOM_DATABASE_URL` local configurado fuera de Git. Crean bases temporales;
PostgreSQL y Docker estuvieron disponibles. No se contabilizaron saltos por falta de entorno.

| Ejecución | Resultado |
|---|---|
| `test_activity test_activity_integration test_internal_monitor`, después de los últimos ajustes | **21 pruebas**, 14,54 s, pasan. |
| `test_activity test_activity_integration.CaptureTests test_internal_monitor test_conversations test_onboarding_conversation test_business_planner test_model_retry`, regresión ampliada previa | **122 pruebas**, 118,64 s, pasan. |
| `test_execution test_review test_review_hardening test_review_context test_parallel_research`, regresión final del dominio | **54 pruebas**, 68,53 s, pasan. |
| Primera regresión integrada, incluyendo `test_web` y paralelismo | **184 pruebas**, 198,16 s, pasan; incluye clases importadas también descubiertas. No sumar a las filas anteriores como pruebas distintas. |
| `test_internal_monitor`, selección exacta del evento y autorización final | **7 pruebas**, 8,11 s, pasan; seis también están en las suites anteriores. |
| `npm --prefix frontend test`, versión final | **92 pruebas / 12 archivos**, 4,44 s, pasan. |
| `npm --prefix frontend run build` | TypeScript y producción pasan. Se conserva el aviso existente de chunks mayores de 500 KB. |
| `npm --prefix frontend run lint` | Salida 0; avisos existentes de React/Fast Refresh en componentes previos, sin avisos nuevos del monitor/actividad. |
| `scripts/dev/start_web.py --help`, `-m decision_room.web --help` | Flag `--internal-monitor` disponible en ambos puntos de entrada. |
| `git diff --check` y revisión de staged | Sin errores de espacios; solo fuente, tests y documentación. |

Los conjuntos se solapan: sus cantidades no son un total de tests únicos.
La prueba del savepoint provoca deliberadamente `UndefinedTable`; es el fallo
inyectado y esperado. Las otras pruebas no dejan `history_complete=false` por
fallos silenciosos del observador.

### Casos específicos

| Riesgo | Evidencia |
|---|---|
| Orden por commit | Productor A retrasa commit y B espera; un lector previo no ve un cursor adelantado. Otra prueba emite 1.000 eventos con tres productores concurrentes y obtiene secuencias 1–1.000. |
| Rollback/idempotencia | Evento revertido no avanza contador; reenvío conserva ID y número de eventos; parentesco cíclico/ajeno rechazado. |
| Fallo de captura | Savepoint defectuoso conserva cambio de negocio y señala historial incompleto. Resultados omitidos se reconstruyen desde registros sin repetir modelos/cálculos. |
| Llamada lenta | Otra conexión ve `call.running` y heartbeat mientras el modelo está bloqueado. Worker detenido queda sin confirmar, sin inventar fallo del job. |
| Paralelismo/replay | Dos ramas reales, consulta de negocio, pregunta, respuesta, revisión aprobada; lectura repetida no altera llamadas/eventos. Replay usa resultado guardado y un marcador deduplicado. Regresión de rama interrumpida conserva cálculo y hermano terminado. |
| Sucesor | Respuesta que cambia definición crea dos sesiones dentro del mismo proceso; investigación anterior aparece superseded. |
| Pregunta/continuidad | Pregunta del planificador con referencias y respuesta conserva la investigación; el recorrido conversacional conserva job y conversación ante «no lo sé». |
| Transporte | 429→503→200 con reloj simulado: espera visible en cada retry, tres peticiones reales del transporte simulado, estado recuperado. Política de timeout incierto cubierta por `test_model_retry`. GET nunca lo autoriza. |
| Entrega | Aprobación seguida de hold y ausencia de código guardado dejan `publishable=false`. Regresiones de parcialidad, contexto corregido y revisión conservan sus gates. |
| Páginas | Más de 200 eventos, cursor ajeno rechazado, cursor público avanza por eventos internos filtrados y recorrido de 1.000 sin duplicados. Página de prueba menor de 100 KB. Evento antiguo fuera de los últimos 20 localizado por ID y evento de otra tarea rechazado. |
| Acceso | Cliente sin cookie interna: 401; operador sin cookie cliente: permitido solo interno; flag apagado: 404; origen extraño y detalle de otro proceso: rechazados. Cambio de negocio no permite ver actividad ajena. |
| Privacidad | Canarios en payloads internos no salen por API pública; diagnóstico elimina credenciales, URLs, rutas personales y campos ocultos. Detalles acotados y con truncamiento explícito. |
| Sin efectos de lectura | Cursores/eventos/estado sin cambios tras GET; el monitor no selecciona negocio ni ejecuta mantenimiento. Caso histórico no crea raíz al consultar. |
| Frontend | Teclado y datos, un fetch compartido, catch-up/deduplicación, reconexión, final sin polling, remount, aborto de proceso anterior, login interno independiente, expiración elimina diagnóstico, filtros/detalle/selección estable, pestaña oculta y un historial por proceso tras varias aclaraciones. |

## Demostración real de Bruma

Se preparó un negocio ficticio nuevo con los cuatro CSV ya usados en Bruma:
**1.656 ventas, seis productos, tres canales y nueve registros de marketing**.
La base privada es `dr_live_38_477dac7cf0a5`; el almacenamiento y las claves se
mantienen ignorados en `.local/evaluation/live-38/`.

- Job: `44717add-6254-409f-af3c-7e103deebf9c`.
- Trace: `bf5bb200-1851-55a4-8df3-04258980d36f`.
- Modelo: `gpt-6-luna`, reasoning bajo, límite de salida 16.384, timeout 300 s.
- Una creación de informe, pausada por una aclaración de la base monetaria y
  reanudada en **el mismo job**, con la respuesta introducida por la UI del cliente.
- Resultado: aprobado, cuatro conclusiones y cuatro gráficos. Este paso no evaluó
  su calidad respecto a otra generación.
- **Tres subanalistas reales**: primero dos ramas solapadas; después otra rama
  dirigida a las contribuciones producto×canal. Cuatro consultas al planificador.
- **22 llamadas lógicas / 22 intentos HTTP registrados**, incluyendo descubrimiento
  de relaciones; **tres cálculos únicos**. 481.465 tokens de entrada y 24.487 de salida
  suministrados por el proveedor; coste monetario sin calcular.
- Duración de raíz hasta final de job: **303,91 s**, incluidos **46,37 s** esperando
  aclaración. No se suman duraciones de ramas concurrentes.
- Historial final de 134 eventos, saludable. Dos eventos tardíos, etiquetados como
  reconstruidos, actualizan actor/rol durante ajustes de instrumentación; no son
  nuevas ejecuciones ni pasos inventados. Las fechas de registro y de dominio se
  distinguen en el detalle.

Antes y después de cuatro lecturas completas internas: **21 filas de `agent_calls`,
una llamada de descubrimiento, tres ejecuciones y 134 eventos**. Un mantenimiento
adicional no cambió esos recuentos. Abrir/cerrar/refrescar ambas vistas conservó
los resultados; ninguna llamada extra al modelo se usó para describir actividad.

### Medidas de latencia y tamaño

- Observador de API durante el informe real, muestreo de dos segundos: **69 eventos
  nuevos medidos**, mediana **1,09 s**, máximo **2,00 s** desde `recorded_at` hasta
  disponibilidad en la consulta. Es una medida de API, no del pintado del navegador.
- Medida independiente hasta pantalla: escenario determinista en un job marcado
  «Fixture 3.8 · Latencia de pantalla», sin llamadas al modelo. Dos tareas activas,
  transición confirmada en PostgreSQL y espera del botón real con el texto nuevo:
  **1,54 s** desde registro hasta visible. Cumple el objetivo local de menos de 3 s;
  no demuestra un SLA en conexiones remotas.
- Página pública real de 100 eventos: **34.669 bytes** serializada; código y entradas
  de modelos solo se solicitan al abrir el detalle interno. Prueba sintética de
  1.000 eventos comprueba el objetivo de página menor de 100 KB.

## Revisión visual y artefactos privados

En el navegador se comprobó informe terminado → Ver proceso → datos de una tarea,
consulta del planificador → entrada `analyst_message`/salida → refresco sin perder
selección, filtro de cálculo → código/resultados. Cliente e interno se comprobaron
a **375 px** sin desbordamiento de documento; cliente también en tema oscuro.
Se restauró el tamaño al terminar.

Capturas y mediciones ignoradas bajo `.local/evaluation/live-38/`:

```text
client-collapsed.png       client-expanded.png
client-data.png            client-mobile.png
client-dark-mobile.png     client-concurrent-fixture.png
internal-exchange.png      internal-call.png
internal-calculation.png   internal-mobile.png
observed.json              screen-latency.json
manifest.json              result.json
```

`client-concurrent-fixture.png` muestra una tarea acabada mientras otra sigue
activa; es una fixture, no otra ejecución analítica. El escenario termina con un
fallo marcado de prueba para comprobar que no se presenta como informe entregable.
La pregunta del planificador y las revisiones con corrección se cubrieron con
modelos deterministas: en Bruma la aclaración fue del planificador inicial y el
revisor aprobó el primer borrador.

## Defectos encontrados y corregidos

1. El registro de preguntas iniciales no tenía `created_at`; se obtiene desde su
   revisión. Se añadió comprobación de salud en teardown para detectar fallos de
   captura aunque el recorrido analítico terminara.
2. El éxito del modelo sobrescribía metadata de transporte: se conserva al guardar
   uso final. Para registros anteriores, se cuentan tareas de intento vinculadas
   exactamente a esa llamada, sin estimar intentos faltantes.
3. La duración crecía tras mantenimiento: se usa final confirmado del job/turno y
   las esperas se acotan a esa ventana. Prueba de evento reconstruido tardío.
4. Dos identidades del mismo redactor y numeración de subanalistas: se normaliza
   actor del redactor y se numera solo a las ramas reales.
5. El viewport del ScrollArea del workspace usaba una envoltura `display:table`
   que ensanchaba el informe a 737 px en móvil. Se fuerza envoltura de bloque a
   ancho completo; actividad del cliente comprobada a 335 px dentro de viewport 375.
6. Sesión interna caducada conservaba datos guardados: los 401/403 limpian recurso
   y caché de diagnóstico y muestran acceso interno; prueba de interfaz incluida.
7. Varias respuestas de aclaración repetían el historial en cada turno: se muestra
   en el último turno del proceso. El informe generado desde chat también enlaza
   al historial mediante su endpoint autorizado; ambos casos tienen prueba de UI.
8. El detalle de un evento antiguo podía mostrar solo los últimos 20 de su tarea:
   el clic envía su ID, el servidor valida ámbito y devuelve `selected_event`,
   separado del estado actual y del historial reciente. Selección #99 verificada
   en pantalla con código y resultado del cálculo.

## Límites de este cierre

Polling incremental local, no SSE/WebSocket. Mapa de participantes y relaciones
mediante tarjetas accesibles, con cronología como alternativa; detalle JSON
estructurado, acotado y bajo demanda. No hay replay animado ni controles para
cancelar/modificar ejecuciones desde el monitor.

La integridad completa de archivos y la publicación final mantienen sus controles
existentes del informe. El monitor comprueba gates y existencia, sin materializar
informes en cada poll. Historial previo se reconstruye solo desde datos disponibles;
no certifica la secuencia exacta ni reproduce razonamiento privado.

La implementación mejora inspección y seguimiento. **La aceptación de calidad
analítica de 3.7 permanece abierta**; no se repitió su matriz de calidad ni se
cambiaron modelos, selección de ramas o presupuesto para favorecer una captura.
No se hizo push a GitHub.
