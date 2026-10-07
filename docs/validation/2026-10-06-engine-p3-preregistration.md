# Preregistro de la medida del paso 3 del motor de agentes

Fecha de registro: 2026-10-06, antes de cualquier ejecución del motor nuevo.
Versión 5, del 2026-10-07 y también antes de medir. La versión 2 incorporó la
revisión de Astra (agregación de lectores, flags y presupuestos congelados,
presupuestos iguales y reemplazos); la 3 define qué cifras «sostienen
prioridades», a partir de la auditoría del paso 1; la 4 fija el encargo de cada
brazo, el orden aleatorio y los presupuestos; la 5, quiénes son los lectores. Los cambios se listan al final.
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
| `legacy` | Cadena LangGraph congelada. | `c6bda76`, con la configuración del brazo «producto» del experimento decisivo (sección 18 del documento de ensayos: sin panorama, la del brazo de referencia de `phase1av4`). Flags: `AGENT_TPM=1800000`, `OWNER_PRESENTATION=true`, `PANORAMA_OBLIGATION_GUARD=true`, `RESEARCH_CONTINUITY=true`, `RESEARCH_VALIDATION_RECOVERY=true`, `REVIEW_LOOP_GUARD=true`, `REVIEW_CONTEXT_BUDGET=false`, `REVIEW_EXPLICIT_CACHE=false`, `REVIEW_STABLE_PREFIX=false`, `SALES_PANORAMA=false` (todas con prefijo `DECISION_ROOM_`). El lanzador copia además al manifiesto los valores efectivos de cada flag `DECISION_ROOM_*`. |
| `afc37fe` | Solo como referencia de regresión técnica; no entra en lectores. | `afc37fe`. |

Los tres primeros reciben los mismos CSV (hashes idénticos, comprobados por el
lanzador) y el mismo encargo, salvo una frase:

- `loop` usa `inputs/<negocio>-panorama`: su encargo añade la frase que señala
  `contexto/panorama.md`, porque es el único brazo que recibe el panorama como
  archivo (como en el lote `loop-panorama`);
- `engine` y `legacy` usan `inputs/<negocio>`, sin esa frase: el motor obtiene el
  panorama con su herramienta `panorama`, y la cadena no lo recibe (como en la
  sección 18). Darles la frase les haría buscar un archivo que no existe.

El lanzador registra el hash del encargo de cada brazo (`--variant
opencode:<negocio>=inputs/<negocio>-panorama`). El modelo es `gpt-6-luna` con
esfuerzo `low` en todos los brazos.

Presupuestos: antes de ejecutar se fijan y se copian al manifiesto los límites de
cada brazo (tokens de entrada y salida, llamadas, tiempo). Deben ser equivalentes
entre brazos. Si un brazo no puede imponer un límite igual (por ejemplo, la cadena
no tiene tope de llamadas), se registra como **desviación** y no se puede afirmar
que se cumplió la condición «mismos presupuestos» del plan. El consumo real de
cada ejecución se informa siempre.

| Brazo | Entrada | Salida | Llamadas | Tiempo |
| --- | --- | --- | --- | --- |
| `engine` | 3.000.000 acumulados | 64.000 acumulados, 8.000 por petición | 60 | 20 min |
| `loop` | sin tope | sin tope | sin tope | 40 min (lanzador) |
| `legacy` | sin tope (ritmo de 1.800.000 tokens por minuto) | sin tope | sin tope | 90 min (lanzador) |

**Desviación registrada:** `loop` y `legacy` son controles congelados y no pueden
imponer los topes del motor sin cambiarlos. En el lote `loop-panorama`, el agente
en bucle consumió como máximo 22 llamadas, 1.182.331 tokens de entrada, 13.665 de
salida y unos 3 minutos: dentro de los topes del motor, así que esos topes no
ponen al motor en desventaja frente a ese control. Se informa qué ejecuciones de
control superan algún tope del motor; si alguna lo hace, se dice en el resultado.

## 3. Tamaño

- 6 ejecuciones independientes por brazo y negocio: 36 ejecuciones (3 brazos × 2
  negocios × 6).
- El orden de ejecución se aleatoriza con una semilla registrada en el manifiesto
  (`--order-seed`): en cada ronda de repetición se ejecuta una vez cada brazo y
  negocio, en orden aleatorio, para que la deriva en el tiempo afecte igual a
  todos. Ningún brazo se ejecuta antes que los demás.
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
- Lectores, elegidos por el propietario: dos modelos, cada uno en una conversación
  nueva abierta solo sobre la carpeta del kit, sin acceso al código, a los lotes, a
  las claves ni a los oráculos:
  - una conversación nueva de Claude Opus 5.5;
  - una conversación nueva de Codex. No es Astra, que implementa el motor: un
    lector que lo ha escrito no es ciego.
  Los dos reciben el mismo papel, fijado en `LECTOR.md` del kit: el dueño o la dueña
  del negocio, no técnico, que quiere entender mejor sus datos y encontrar análisis
  útiles para decidir. Leen los mismos informes en archivos (`parejas/<código>/A` y
  `B`) y responden en `respuestas.json`. Cada medida se hace en conversaciones
  nuevas (cuatro en total), empezando por contenido.
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
     correctas. **Sostiene una prioridad** (campo `sostiene_prioridad_v3` del
     registro del auditor) toda cifra citada en cualquier recomendación explícita
     del informe o en su justificación frente a alternativas, incluidos sus
     denominadores y las cifras enlazadas como soporte, esté en el puesto que
     esté. Quedan fuera las cifras descriptivas o históricas sin ese vínculo. El
     auditor anota la cita de la prioridad y el criterio, para que la
     clasificación se pueda revisar. Como diagnóstico se informa además
     `sostiene_prioridad_principal` (solo las tres primeras prioridades);
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

## Cambios respecto a la versión 2

1. Definición de «cifra que sostiene una prioridad»: en la auditoría del paso 1 el
   auditor marcó así el 93 % de las cifras, lo que hacía equivalentes el umbral del
   100 % y el total. Ahora cuenta toda recomendación explícita con su justificación
   y sus cifras enlazadas, en cualquier puesto (para que no se pueda eludir
   moviéndola al cuarto lugar o a una tabla), y no los descriptivos sin vínculo.

## Cambios respecto a la versión 3

1. Encargo por brazo: solo `loop` recibe la frase sobre `contexto/panorama.md`,
   porque es el único que recibe ese archivo; los CSV son idénticos y el lanzador
   lo comprueba. La versión 3 daba a los tres brazos `inputs/<negocio>-panorama`,
   lo que habría pedido a `engine` y `legacy` un archivo que no tienen, y se
   apartaba de la configuración de la sección 18 para `legacy`.
2. Flags explícitos de `legacy`, copiados del brazo de referencia de `phase1av4`.
3. Orden aleatorio por rondas con semilla, implementado en el lanzador.
4. Tabla de presupuestos y desviación registrada, con el consumo observado del
   control `loop`.

## Cambios respecto a la versión 4

1. Lectores: dos modelos en conversaciones nuevas (Claude Opus 5.5 y Codex), con el
   papel de dueño no técnico, elegidos por el propietario. **Límite:** la puerta
   mide la preferencia de lectores modelo con ese papel, no la de dueños reales; los
   dos lectores pertenecen a familias de modelos distintas para no depender de una.
