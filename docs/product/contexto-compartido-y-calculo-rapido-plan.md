# Plan: contexto compartido, informes que se continúan y cálculo rápido en el chat

Fecha: 12 de octubre de 2026.

**Estado: propuesto y aprobado en orden por el propietario. Ningún paso está
implementado todavía.**

Este plan continúa el trabajo de informes nativos. El formato nativo de bloques
es el predeterminado desde el PR #9 y la plataforma lo presenta con su propio
estilo desde el PR #10. Sigue al [plan de implementación](<Decision Room - Plan de implementacion.md>).

## Orden

| Paso | Qué | Por qué en este orden |
|---|---|---|
| 0 | Diagnosticar y corregir los fallos del motor nativo | En la prueba de adopción del estilo A, dos de tres informes no llegaron al cliente. El nativo ya es el formato predeterminado. |
| 1 | Contexto compartido e informes anteriores | El chat y los informes deben saber lo mismo del cliente. Es la base de los pasos siguientes. |
| 2 | Cálculo rápido en el chat | Calcula mejor si ya conoce los datos y los informes anteriores. |
| 3 | Predicciones | Necesita un tipo de trabajo propio, con prueba contra el pasado. Se planificará aparte. |

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

## Paso 1. Contexto compartido e informes anteriores

### Situación actual

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

## Paso 3. Predicciones

Queda fuera de este plan. Será un tipo de trabajo propio, con estas reglas:

- prueba contra meses ya conocidos;
- rangos en lugar de cifras únicas;
- fiabilidad declarada;
- un comprobador que mida si el modelo habría acertado en el pasado.
