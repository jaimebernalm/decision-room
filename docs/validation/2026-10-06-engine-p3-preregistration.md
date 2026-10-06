# Preregistro de la medida del paso 3 del motor de agentes

Fecha de registro: 2026-10-06, antes de cualquier ejecución del motor nuevo.
Versión 2, del mismo día y también antes de medir: incorpora la revisión de Astra
(agregación de lectores, flags y presupuestos congelados, presupuestos iguales y
reemplazos). Los cambios respecto a la versión 1 se listan al final.
Plan de referencia: plan de implementación del motor, v3, paso 3 (acordado entre
Claude y Astra). Este documento fija cómo se mide la puerta del paso 3. Lo que aquí
se fija no se cambia después de ver resultados. Si hay que cambiar algo antes de
medir, se registra como versión nueva con su fecha y su motivo.

## 1. Pregunta

¿La habilidad de informe del motor nuevo (agente principal en OpenCode con
herramientas del producto y verificación final) iguala o supera al agente en
bucle con panorama, y supera a la cadena congelada en `c6bda76`, sin publicar
cifras erróneas como verificadas ni perder informes?

## 2. Brazos

| Brazo | Qué es | Revisión |
| --- | --- | --- |
| `engine` | Motor nuevo, invocado con `engine.run_report` desde el lanzador. | La de `codex/agent-engine` en el momento de la medida, registrada en el manifiesto. |
| `loop` | Agente en bucle (OpenCode) con `contexto/panorama.md`, como el lote `loop-panorama`. Control congelado y reejecutado. | Lanzador y configuración del lote `loop-panorama` (`9da3985`), con la imagen `decision-room-opencode:1.18.34`. |
| `legacy` | Cadena LangGraph congelada. | `c6bda76`, con la configuración del brazo «producto» del experimento decisivo (sección 18 del documento de ensayos: sin panorama). Los valores explícitos de cada flag `DECISION_ROOM_*` y de cada presupuesto se copian al manifiesto antes de ejecutar; la referencia a la sección 18 no basta. |
| `afc37fe` | Solo como referencia de regresión técnica; no entra en lectores. | `afc37fe`. |

Los tres primeros reciben el mismo encargo y los mismos snapshots de datos:
`inputs/albor-panorama` y `inputs/bruma-panorama`, con hashes en el manifiesto.
El modelo es `gpt-6-luna` con esfuerzo `low` en todos los brazos.

Presupuestos: antes de ejecutar se fijan y se copian al manifiesto los límites de
cada brazo (tokens de entrada y salida, llamadas, tiempo). Deben ser equivalentes
entre brazos. Si un brazo no puede imponer un límite igual (por ejemplo, la cadena
no tiene tope de llamadas), se registra como **desviación** y no se puede afirmar
que se cumplió la condición «mismos presupuestos» del plan. El consumo real de
cada ejecución se informa siempre.

## 3. Tamaño

- 6 ejecuciones independientes por brazo y negocio: 36 ejecuciones (3 brazos × 2
  negocios × 6).
- El orden de ejecución se aleatoriza con una semilla registrada en el manifiesto.
- Un intento que no entrega informe (incluido un HTML sin texto legible) cuenta
  como **perdido** para la puerta y no se sustituye en el cómputo de informes
  perdidos. Para la comparación con lectores se sustituye por una ejecución nueva,
  como máximo una vez por puesto, y se informa.
- Si el reemplazo tampoco entrega, la pareja es **insuficiente**: sigue en el
  denominador, no se compara y la puerta no puede darse por superada.

## 4. Emparejamiento y lectores

- Antes de ejecutar, una semilla registrada empareja la ejecución *i* de `engine`
  con la ejecución *i* de `loop` y con la ejecución *i* de `legacy`, por negocio:
  6 parejas `engine`–`loop` y 6 parejas `engine`–`legacy` por negocio.
- Al menos 2 lectores ciegos por negocio. Cada lector ve cada pareja con orden
  izquierda/derecha aleatorio y códigos aleatorios, sin saber qué sistema es cada
  informe.
- Para cada pareja, cada lector elige «A mejor», «B mejor» o «empate», con un
  motivo breve.
- Cada voto se convierte en puntuación de `engine`: 1 si elige su informe, 0,5 si
  es empate, 0 si elige el otro.
- Resultado de la pareja: la media de los votos decide. Por encima de 0,5 es
  victoria (1); exactamente 0,5, empate (0,5); por debajo, derrota (0). Con dos
  lectores, un voto y un empate es victoria; dos votos opuestos, empate.
- Se guarda además la media cruda de los votos de cada pareja, como información.

## 5. Las dos medidas

1. **Contenido:** los informes de los tres brazos se muestran con la misma
   presentación normalizada (misma tipografía, escala de grises, sin marca), como
   en los kits anteriores. Se juzga qué ayuda más al dueño a decidir.
2. **Artefacto final:** cada informe con su presentación real (el del motor, con el
   renderizador que usará el producto). Se juzga qué entregaría el dueño.

Las dos medidas se hacen con lectores distintos o en sesiones separadas, empezando
por contenido.

## 6. Puerta

El brazo `engine` pasa si se cumplen **todas**:

1. Media de los resultados de las parejas ≥ 0,5 frente a `loop` y > 0,5 frente a
   `legacy`, **en cada negocio y en cada medida** (8 condiciones), sin parejas
   insuficientes.
2. Juez de señales en Albor (conoce la verdad plantada, no el sistema): media
   ≥ 11/3 puntos por informe en S1-S5 (escala 0-10 por informe), y 0 en el señuelo
   S6. Umbral piloto derivado del lote `loop-panorama` (11 puntos en 3 informes de
   OpenCode con panorama).
3. Exactitud, con un auditor independiente que recalcula desde los CSV y clasifica
   las cifras (el denominador no lo decide el agente):
   - 100 % de las cifras calculables que sostienen prioridades, verificadas y
     correctas;
   - ≥ 95 % de las demás cifras calculables, verificadas;
   - 0 cifras erróneas presentadas como verificadas.
   Se informan todos los errores, también los de cifras marcadas como no
   comprobadas, y las inciertas aparte.
4. 0 informes perdidos sobre todos los intentos del brazo `engine`, incluidos los
   fallidos. Un registro vacío no cuenta como informe entregado.

No es una prueba estadística de equivalencia: con 6 parejas por negocio, la puerta
detecta diferencias grandes, no pequeñas.

## 7. Qué se informa siempre

Por brazo y negocio:

- informes entregados y perdidos;
- puntuaciones por pareja y por lector, con los motivos;
- concordancia entre lectores;
- puntuación del juez por señal;
- tabla de exactitud (cifras revisadas, correctas, erróneas, no comprobadas,
  inciertas);
- tokens de entrada, salida y caché, llamadas, duración y coste de catálogo.

## 8. Ceguera y aislamiento

- Los oráculos y la verdad plantada solo los ve el juez de señales; nunca llegan a
  los agentes, al producto ni a los lectores.
- Las claves de desciego se guardan fuera de las carpetas de los lectores.
- Nada específico de Albor o Bruma entra en el producto.

## 9. Si la puerta falla

El paso 4 no empieza. Se escribe un análisis de qué condición falló y por qué, y
cualquier cambio para un segundo intento se registra aquí como versión nueva antes
de volver a medir. Un segundo intento usa ejecuciones nuevas, no reutiliza las de
este registro.

## 10. Herramientas

- Emparejamiento, kit de lectores y puntuación: `decision_room/evaluation/trial_pairs.py`
  (`plan` antes de ejecutar, `kit` por medida, `score`).
- Brazo `engine` del lanzador: `decision_room/evaluation/trials.py` y `trial_worker.py`.

## Cambios respecto a la versión 1

1. Agregación de lectores: la versión 1 daba 0,75 a un voto más un empate, lo que
   contradecía la puntuación 1 / 0,5 / 0 por pareja del plan. Ahora la media de
   votos decide victoria, empate o derrota, y la media cruda se guarda aparte.
2. Brazo `legacy`: valores explícitos de flags y presupuestos en el manifiesto.
3. Presupuestos: equivalentes entre brazos o desviación registrada.
4. Reemplazos: un reemplazo perdido deja la pareja insuficiente y bloquea la puerta.
