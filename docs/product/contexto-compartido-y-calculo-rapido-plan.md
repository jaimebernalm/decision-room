# Plan: contexto compartido, informes que se continúan y cálculo rápido en el chat

Fecha: 12 de octubre de 2026.

**Estado:**

- Pasos 0, 1 y 2 terminados. Paso 2, cálculo rápido en el chat: implementado, revisado por Codex y validado con el modelo real ([calculo-rapido-implementacion.md](../technical/calculo-rapido-implementacion.md)).
- Paso 3, indicadores guardados y registro de seguimiento: implementado y revisado dos veces por Codex ([indicadores-seguimiento-implementacion.md](../technical/indicadores-seguimiento-implementacion.md)). Las correcciones de su segunda revisión se integraron a petición del propietario sin una tercera revisión. La prueba con el modelo real está pendiente.
- Orden revisado con el propietario el 12 de octubre de 2026: se añade el paso 3 (indicadores guardados y registro de seguimiento) y las predicciones pasan a ser el paso 4.

Este plan continúa el trabajo de informes nativos. El formato nativo de bloques
es el predeterminado desde el PR #9 y la plataforma lo presenta con su propio
estilo desde el PR #10. Sigue al [plan de implementación](<Decision Room - Plan de implementacion.md>).

## Orden

| Paso | Qué | Por qué en este orden |
|---|---|---|
| 0 | ~~Diagnosticar los fallos del motor nativo~~ (hecho) | No era un fallo del código: el Mac se suspendió durante la prueba. |
| 1 | ~~Contexto compartido e informes anteriores~~ (hecho) | El chat y los informes saben lo mismo del cliente, y cada informe recibe los anteriores. |
| 2 | ~~Cálculo rápido en el chat~~ (hecho) | Lo que más se nota en el uso diario. Genera las fórmulas que el paso 3 permitirá guardar. |
| 3 | ~~Indicadores guardados y registro de seguimiento~~ (hecho, sin la prueba real) | Hace que el contexto no crezca aunque haya muchos informes, y recalcula las cifras recurrentes sin modelo. |
| 4 | Predicciones | Necesita las series fijas del paso 3 para probarse contra el pasado. Se planificará aparte. |
| Más adelante | Buscador de informes anteriores para el agente de informes | Solo hace falta cuando un negocio acumule decenas de informes. |

## Arquitectura que se mantiene

- **Chat:** un bucle propio de decisión, del tipo razonar, actuar y observar.
  - Corre en `decision_room/chat_agent.py` y `decision_room/conversations.py`.
  - Las herramientas están acotadas por el servidor y la conversación se guarda en PostgreSQL.
  - No se adopta LangGraph ni OpenCode en el chat. El chat necesita responder en segundos, controlar cada herramienta y leer la memoria y los informes del cliente. Ninguno de los dos aporta una capacidad que hoy falte.
  - Se reconsiderará si aparecen varios subagentes en paralelo o pausas largas con aprobaciones.
- **Informes:** un agente autónomo dentro de un contenedor aislado, hoy OpenCode.
  - Lo propio del producto queda fuera del agente: el encargo, el formato de bloques, el comprobador independiente y el control de presupuesto.
  - Con esa separación, el agente del contenedor se puede sustituir sin tocar el resto.
- **Sistema antiguo de informes con LangGraph** (`decision_room/agent/`): sigue como respaldo cuando el motor no está configurado. Se retirará cuando el nativo sea fiable, después del paso 0, para no mantener dos formas de hacer informes.

## Paso 0. Fallos del motor nativo

En la prueba de adopción del 11 de octubre se lanzaron tres informes:

- La clínica se entregó.
- Un herbolario se detuvo con `provider_usage_unknown` durante la comprobación independiente.
- El otro herbolario terminó con `controller_failure` tras cuatro llamadas, con una llamada que quedó sin cerrar en el contador.

El diagnóstico usa los registros ya guardados y no hace llamadas de pago. Cada causa se corrige con una prueba que la reproduzca. Una nueva ejecución real necesita la aprobación del propietario.

**Resultado, 12 de octubre de 2026:** no hay fallo del código. El registro de energía del Mac muestra que se cerró la tapa y el equipo entró en reposo justo cuando empezaba cada llamada fallida (23:23:27 y 23:35:34). El motor actuó bien: no repitió llamadas de uso incierto. Desde entonces, antes de cualquier prueba de pago se mantiene el equipo despierto y con la tapa abierta.

## Paso 1. Contexto compartido e informes anteriores

**Hecho el 12 de octubre de 2026.**

- **Implementación:** [contexto-compartido-implementacion.md](../technical/contexto-compartido-implementacion.md), planificada con Codex, implementada por Claude y revisada por Codex en dos rondas.
- **Pruebas:** suite completa 1013/1014; el único error es el navegador de informes, que no está construido en la máquina local.
- **Prueba real:** dos informes seguidos sobre un negocio de prueba con los mismos datos.
  - El segundo recibió el primero, lo retomó («la señal anterior se mantiene y se afina») y recalculó sus cifras en vez de copiarlas.
  - Dijo qué propuestas necesitaban registros que no están en los CSV.
  - Comprobación sin discrepancias. Coste: 0,19 USD como máximo, según el límite de gasto.
- **Sin probar todavía con el agente real:** datos sustituidos entre un informe y otro.

### Situación anterior

Hay dos constructores de contexto:

- `conversations.snapshot` para el chat;
- `engine/brief.build` para el agente de informes.

| | Chat | Agente de informes |
|---|---|---|
| Perfil del negocio | Sí | Sí |
| Memoria confirmada, filtrada por alcance | Sí | Sí |
| Significado de las columnas | Todos los conjuntos | Solo el del análisis |
| Otros conjuntos de datos | Sí | No |
| Informes anteriores | Puede buscarlos y abrirlos | No |
| Conversación previa | Sí | No |

Cuando el chat lanza un informe, guarda en el trabajo las citas recientes del propietario y los informes relacionados. El motor nativo no los usa: su objetivo es solo el texto del último mensaje (`web/engine_jobs.py`). Ese contexto lo aprovechaba el sistema antiguo.

### Cambios

1. **Un único constructor del conocimiento del negocio,** usado por el chat y por el encargo de informes. Así no pueden divergir.
2. **Informes anteriores en el encargo:**
   - un resumen breve de cada informe aprobado relevante: fecha, conclusiones principales y acciones pendientes («Qué comprobar», «Si se confirma», «Si no»);
   - los informes completos, como archivos de solo lectura dentro del contenedor.
3. **El chat redacta el encargo.** Es un texto breve con lo que quiere el propietario, por qué y lo ya hablado, en lugar de copiar el último mensaje.
4. **Reglas que se conservan:**
   - La memoria sin confirmar no entra.
   - Lo que dijo un informe anterior se presenta como afirmación de ese informe, no como un hecho verificado ahora.
   - El comprobador recibe el mismo contexto que hoy, más el resumen de los informes anteriores, para poder distinguir lo citado de lo calculado.

### Validación

- **Pruebas automáticas:** los dos agentes reciben el mismo conocimiento, y la memoria no confirmada nunca entra.
- **Prueba real con el negocio de prueba, que requiere aprobación de gasto:** dos informes seguidos. El segundo debe retomar las acciones pendientes del primero y distinguir lo citado de lo recalculado.

## Paso 2. Cálculo rápido en el chat

**Plan técnico acordado el 12 de octubre de 2026:** [calculo-rapido-implementacion.md](../technical/calculo-rapido-implementacion.md). Cambia tres cosas respecto a lo escrito abajo:

- **Sin contenedor siempre activo.** Arrancar un contenedor nuevo del sandbox tarda en torno a medio segundo, así que cada cálculo usa uno nuevo y se mantiene el modelo de seguridad actual: nunca se reutiliza un contenedor entre preguntas ni entre negocios.
- **Imagen del sandbox de cálculo,** no la del agente de informes. Tiene la pila de datos de Python y las mismas restricciones: sin red, datos de solo lectura y límites de recursos.
- **El informe siempre se confirma con un botón.** El chat nunca lanza un informe por sí solo, ni siquiera ante un «hazme un informe» escrito: propone el objetivo, el propietario puede editarlo y lo confirma con «Preparar informe». Así no depende de que el modelo interprete bien un mensaje.

### Situación actual

El chat lee datos, memoria e informes, pero no calcula. Cualquier cifra nueva exige un informe completo de unos cinco minutos.

### Cambios

1. **Herramienta de cálculo rápido.** El chat escribe un fragmento de Python y lo ejecuta en la misma imagen aislada de los informes:
   - sin red;
   - con los datos del cliente en solo lectura;
   - con un límite de tiempo de 30 a 60 segundos y una salida acotada;
   - con un contenedor que se mantiene activo durante la conversación para no pagar el arranque en cada pregunta.
2. **Presentación honesta.** El resultado se muestra como «cálculo rápido, sin comprobación independiente», con el código visible. Se guarda para poder citarlo después.
3. **El chat avisa cuando el cálculo es grande y no decide solo.** Si la pregunta pide más de lo que cabe en un cálculo rápido, el chat lo dice y propone abrir un informe, explicando qué cuesta en tiempo y qué aporta en comprobación. El propietario decide.
   - Ejemplos de pregunta que pide más: varias tablas, muchos periodos o segmentos, buscar causas, o algo que vaya a sostener una decisión importante.
   - También vale el sentido contrario: si un cálculo rápido no termina dentro de su límite, el chat lo explica y ofrece el informe.
4. **Reparto:**
   - una pregunta concreta se resuelve con el cálculo rápido;
   - un análisis a fondo va a un informe, con el encargo del paso 1;
   - cuando el informe termina, el chat lo lee y lo comenta.

### Riesgos

- **Un cálculo rápido puede estar mal sin que se note.** Lo mitigan:
  - el código visible;
  - el uso del significado declarado de las columnas;
  - una etiqueta que nunca lo presenta como comprobado.

  Más adelante podrá añadirse una comprobación ligera.
- **Coste por pregunta:** añade llamadas al modelo. Se medirá en la validación.

### Validación

- **Pruebas automáticas:**
  - aislamiento: sin red, sin escritura y con límite de tiempo;
  - etiquetado del resultado;
  - el aviso de «cálculo grande» ofrece un informe y no lo lanza sin confirmación.
- **Prueba real con preguntas de distinta dificultad, que requiere aprobación de gasto:**
  - las pequeñas se responden en segundos;
  - las grandes acaban en una propuesta de informe.

**Resultado, 12 de octubre de 2026:**

- De cuatro preguntas pequeñas, tres salieron bien a la primera, en 7 a 19 segundos. La cuarta dio un 0 % equivocado: el modelo buscó «no presentado» y el valor guardado era `no_presentado`.
- Se corrigió: el cálculo ahora lee los valores guardados antes de filtrar, y un filtro sin coincidencias se trata como un error. Repetida, dio el 4,78 % correcto.
- Las dos preguntas grandes acabaron en una propuesta de informe, sin lanzar ninguno.
- Coste de toda la prueba: unos 0,04 USD.

## Paso 3. Indicadores guardados y registro de seguimiento

Pensado para cuando un negocio tenga muchos informes.

**Plan técnico acordado el 12 de octubre de 2026:** [indicadores-seguimiento-implementacion.md](../technical/indicadores-seguimiento-implementacion.md). Precisa dos cosas de lo escrito abajo, con las decisiones del propietario:

- **Reparación de un indicador.** Si falla por la estructura de los datos, queda no disponible con el motivo. El chat propone una fórmula nueva, se compara con la cifra guardada sobre los datos anteriores y el propietario la confirma con un botón. Los fallos pasajeros se reintentan solos con la misma fórmula.
- **Cifras de informe.** No pueden pasar directamente a indicador, porque el informe no guarda su fórmula. Primero se recalculan con un cálculo rápido del chat.

### Situación actual

- Cada informe recibe como máximo 3 informes anteriores, en un resumen de hasta 6 KiB más sus textos como archivos, y el contexto no crece. Con muchos informes, lo difícil es elegir bien cuáles 3.
- Las fórmulas no se guardan: el agente escribe su cálculo en cada informe y lo descarta, así que una cifra recurrente se vuelve a calcular cada vez.

### Cambios

1. **Indicadores guardados.**
   - Una cifra recurrente, como una tasa de citas perdidas o las ventas por canal, se guarda como indicador: su cálculo fijo, las columnas que usa y su significado confirmado.
   - Puede nacer de un cálculo rápido del chat («guárdalo como indicador») o de una cifra de un informe.
   - Al subir datos nuevos se recalcula de forma determinista, sin modelo. Los informes y el chat lo reciben ya calculado y el agente solo lo interpreta.
2. **Registro de seguimiento.**
   - Las acciones de los informes nativos («qué comprobar», «si se confirma», «si no») ya están estructuradas. Se reúnen en una lista viva de temas abiertos, con su origen, fecha y estado.
   - El estado puede ser «propuesto», «comprobado con datos» o «cerrado por el propietario».
   - Un informe nuevo recibe esa lista corta en lugar de informes enteros, así que su tamaño no depende de cuántos informes haya.
3. **Determinista.** Nada se resume con un modelo. Un indicador cuyo cálculo deja de cuadrar con los datos, por ejemplo por un cambio de columnas, se marca como no disponible y nunca se adapta en silencio.

### Validación

Se definirá al planificar el paso, con el mismo método: plan con Codex, implementación de Claude y revisión de Codex.

## Más adelante: buscador de informes anteriores

- Cuando un negocio acumule decenas de informes, el agente de informes tendrá una herramienta de búsqueda sobre los informes anteriores, como la que ya tiene el chat, apoyada en la búsqueda semántica existente.
- No se adelanta: con pocos informes, la selección actual y el registro de seguimiento bastan.

## Paso 4. Predicciones

Queda fuera de este plan. Será un tipo de trabajo propio, con estas reglas:

- prueba contra meses ya conocidos;
- rangos en lugar de cifras únicas;
- fiabilidad declarada;
- un comprobador que mida si el modelo habría acertado en el pasado.
