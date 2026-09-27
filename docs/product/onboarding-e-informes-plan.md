# Plan: onboarding orientado al objetivo e informes con hallazgos útiles

Fecha: 27 de septiembre de 2026.

**Estado: planificación acordada; implementación y evaluación pendientes.**
Este documento desarrolla la entrega 3 del [plan de implementación](<Decision Room - Plan de implementacion.md>).
No da por construidas las capacidades propuestas ni por validado el análisis de
una base de datos sustancial.

## 1. Objetivo de producto

Ayudar a una persona a entender su negocio y tomar mejores decisiones utilizando
sus datos. El resultado debe responder a lo que busca: descubrir oportunidades,
ordenar su información, seguir indicadores o resolver una pregunta concreta.
Un informe lleno de cifras no demuestra por sí solo que el producto aporte valor.

El onboarding debe recoger ese propósito, entender lo necesario del negocio y
preparar una primera entrega útil. La investigación debe conectar tablas,
comprobar cálculos y profundizar en los hallazgos relevantes. El usuario podrá
seguir trabajando con el mismo interlocutor después del primer resultado.

## 2. Preguntar qué quiere conseguir el usuario

### Pregunta abierta con opciones sugeridas

Antes de iniciar el primer informe, preguntar:

> ¿Qué te gustaría conseguir con este primer análisis?
>
> Cuéntamelo con tus palabras o elige alguna de estas ideas. Puedes combinarlas.

| Opción sugerida | Texto de ayuda | Entrega esperada |
|---|---|---|
| Descubrir oportunidades y problemas | Encuentra cambios, patrones o puntos de mejora que quizá no haya visto. | Hallazgos priorizados, comprobados y explicados con evidencia. |
| Tener mi negocio organizado y a la vista | Ayúdame a entender mis cifras y tener un dashboard claro. | Indicadores definidos, periodos visibles y gráficos útiles para consultar. |
| Responder una pregunta concreta | Quiero entender algo que me preocupa o una decisión que tengo que tomar. | Respuesta centrada en esa pregunta, con cálculos, límites y posibles siguientes pasos. |
| Saber cómo va el negocio | Quiero comparar periodos y seguir la evolución de mis resultados. | Resumen de evolución, desviaciones y comparaciones pertinentes. |
| Ayúdame a decidir por dónde empezar | Todavía no sé qué puedo sacar de estos datos. | Propuesta breve de objetivos basada en los archivos disponibles, para que la persona elija. |

Las opciones son ayudas para expresarse, no categorías obligatorias ni agentes
distintos. Mantener un campo de texto libre visible; permitir varias opciones y,
si hay prioridades incompatibles, preguntar cuál importa más para esta entrega.
No obligar a quien quiere ordenar sus datos a pedir hallazgos sorprendentes.

Ejemplo de respuesta combinada:

> Quiero tener las ventas y el margen bien organizados, pero sobre todo descubrir
> qué productos venden mucho y aportan poco margen.

El asistente devolvería una síntesis editable del objetivo, las preguntas que
intentará responder y qué quedará fuera. Tras inspeccionar los datos, ajustará la
propuesta si faltan fuentes necesarias, explicándolo antes de empezar.

### Predicciones: capacidad futura

Reservar en el diseño la intención «Anticipar qué podría pasar», pero no ofrecer
una opción ejecutable de predicción mientras no exista y se haya evaluado esa
capacidad. Si alguien la pide en texto libre, explicar la limitación y ofrecer
un análisis histórico útil sin presentarlo como pronóstico.

Cuando se incorpore machine learning, esta intención requerirá definir variable,
horizonte y decisión que se quiere apoyar; comprobar historial y calidad de datos;
comparar con una referencia sencilla; evaluar con separación temporal y sin fuga
de información; y comunicar incertidumbre. Una extrapolación o una hipótesis del
asistente no equivale a una predicción validada.

### Persistencia del objetivo

Guardar el texto original, las opciones elegidas, la prioridad, el alcance
confirmado, las preguntas concretas y las limitaciones conocidas. Distinguir:

- Objetivo de este informe, que puede cambiar en la siguiente solicitud.
- Preferencias duraderas del negocio, que solo se incorporan a la memoria cuando
  la conversación lo justifique.
- Disponibilidad técnica: lo que se puede entregar con los datos y capacidades actuales.

El objetivo debe guiar la selección de tablas, el presupuesto de investigación,
la presentación y la revisión. El usuario puede cambiarlo; si cambia durante una
ejecución, conservar la versión original y revisar qué trabajo necesita ampliarse.

## 3. Onboarding propuesto

1. **Conocer el negocio.** Conversación breve sobre qué hace, qué vende o presta,
   a quién y qué le preocupa. Aprovechar lo que ya haya contado. Pedir ubicación,
   canales u otros detalles cuando aporten utilidad al caso.
2. **Elegir el resultado.** Presentar la pregunta abierta y las opciones anteriores.
   Permitir «Ayúdame a decidir» y concretar después de ver los archivos.
3. **Recibir y explorar los datos.** Explicar qué tablas se han reconocido, qué
   periodos cubren y qué parece posible estudiar. Distinguir metadatos observados
   de interpretaciones que aún necesitan confirmación.
4. **Preguntar con contexto visible.** Abrir los datos relevantes junto a cada
   pregunta sobre una columna o un registro. Hacer preguntas sobre el negocio
   cuando ayuden a interpretar o priorizar: devoluciones, campañas, canales,
   cambios de actividad o significado de costes, por ejemplo.
5. **Confirmar el alcance.** Mostrar un resumen editable: qué entendimos del
   negocio, qué quiere conseguir, qué analizaremos y qué no podemos comprobar.
6. **Crear y explicar la primera entrega.** Presentar el informe o dashboard
   correspondiente al objetivo, con resultados revisados y acceso a evidencia.
7. **Continuar la conversación.** Mantener contexto, objetivo e historial al entrar
   en la plataforma; permitir profundizar, corregir o iniciar otra pregunta.

### Preguntas necesarias y contexto opcional

- Una definición necesaria para un cálculo bloquea únicamente el análisis que
  depende de ella. Otras investigaciones válidas pueden continuar.
- El contexto útil para el futuro puede omitirse y recuperarse más adelante.
- «No lo sé» es una respuesta válida; no debe transformarse en una confirmación.
- Evitar un cuestionario exhaustivo antes de aportar valor. Preguntar en pequeñas
  tandas según la información que falta y la utilidad de conocerla.
- No volver a preguntar datos ya confirmados y vigentes en la memoria del negocio.

### Un interlocutor con distintos modos

Reutilizar el asistente conversacional como interlocutor del onboarding y de la
plataforma. Compartir instrucciones básicas, memoria y herramientas; añadir un
modo de onboarding que guíe activamente y un modo cotidiano que responda a la
intención del momento.

Persistir etapa, pregunta pendiente, respuestas, hechos confirmados, datos
desconocidos y contexto omitido. Vincular cada respuesta a su pregunta: «En Sevilla»
debe conservar que responde a la ubicación. El extractor actual de memoria no lee
toda la conversación y no se debe confiar en que reconstruya esa relación solo.

Al añadir otro negocio desde la plataforma, conservar el flujo de onboarding sin
el botón de volver a Bienvenida, como ya hace la interfaz. Mantener separados los
datos, la memoria y las conversaciones de cada negocio.

## 4. Mejorar la comprensión de varias tablas

### Límites actuales observados

La planificación permite inspeccionar hasta ocho tablas. Una ejecución de
investigación utiliza dos investigaciones por defecto y admite como máximo tres.
El contexto de planificación incluye el catálogo de columnas, utiliza muestras
iniciales de cinco filas y tiene un límite de 200.000 bytes. Estos límites y la
selección actual requieren revisión para investigar bases extensas.

Referencias: [contratos](../../decision_room/agent/contracts.py),
[contexto](../../decision_room/agent/context.py) e
[investigación](../../decision_room/agent/research.py).

### Catálogo y relaciones verificables

- Identificar qué representa una fila en cada tabla: factura, línea de factura,
  cliente, producto o movimiento, por ejemplo.
- Registrar tipos interpretados y conversiones, unidades, moneda, periodos,
  nulos, duplicados y cobertura. Los CSV actuales conservan columnas como texto;
  una conversión debe verificarse y no descartar errores silenciosamente.
- Distinguir relaciones declaradas de relaciones candidatas. Comprobar claves,
  cardinalidad, registros sin correspondencia y efecto de cada unión en los totales.
- Evitar sumar importes de cabecera repetidos por cada línea de detalle.
- Definir métricas: ventas con/sin impuestos, descuentos, devoluciones y coste;
  no llamar beneficio neto a un margen que no incluye todos los gastos.
- Ofrecer búsquedas y lecturas selectivas del catálogo y sus perfiles, sin enviar
  toda la base al modelo. Las cinco primeras filas no bastan para describirla.

La selección debe depender de la pregunta y de las relaciones necesarias.
Aumentar límites sin mejorar descubrimiento, selección y comprobación no resuelve
el problema. Conservar procedencia, versiones y evidencia de cada cálculo.

### Memoria persistente de la organización de los datos

Construir este conocimiento progresivamente desde la primera inspección y durante
el análisis. Conservarlo por negocio para reutilizarlo entre informes y
conversaciones, también después de reiniciar la aplicación. Compartirlo mediante
consultas selectivas de los agentes, sin exigir que reconstruyan las relaciones
en cada trabajo.

Distinguir la memoria del negocio —actividad, ubicación, prioridades y contexto—
del conocimiento estructurado de sus datos —tablas, campos, relaciones y
definiciones de métricas—, manteniendo vínculos entre ambos. Las definiciones
aportadas por el usuario complementan las comprobaciones técnicas; no sustituyen
la validación de claves y uniones.

Cada elemento debe conservar procedencia, archivos y versiones a los que aplica,
evidencia, fecha de comprobación y estado: propuesto, comprobado, pendiente de
aclaración u obsoleto. No convertir una inferencia del agente en un hecho validado.

### Modelo de relaciones y diagrama ER

Guardar un modelo estructurado del que se genere el diagrama entidad-relación
(ER). Ese modelo será consultable por los agentes y representable visualmente
para el cliente. Debe incluir:

- Tablas, descripción y significado de cada fila.
- Claves primarias o candidatas, incluidas claves compuestas, y columnas de enlace.
- Relaciones uno a uno, uno a muchos y muchos a muchos; tablas intermedias y
  condiciones de unión cuando sean necesarias.
- Origen de cada relación: declarada por la fuente, explicada por el usuario o
  inferida; por separado, su estado de verificación y la evidencia que lo respalda.
- Cardinalidad observada, duplicados de claves, valores sin correspondencia y
  precauciones para evitar multiplicar filas o sumar importes repetidos.

Por ejemplo, clientes → facturas → líneas de factura, con productos relacionados
con las líneas. El agente podrá consultar este recorrido para conectar entidades
en futuros análisis. Las definiciones de ventas, costes y margen seguirán siendo
necesarias: conocer cómo unir tablas no basta para calcular bien las métricas.

El diagrama y las consultas de los agentes deben derivar de la misma versión del
modelo, para evitar explicaciones visuales distintas de las relaciones utilizadas.

### Vista en «Mi negocio → Tus datos»

Mostrar una vista comprensible con datos disponibles, periodos y actualización;
«Cómo los entendemos», con definiciones relevantes; «Cómo se conectan», con
explicaciones sencillas; y dudas pendientes. Ofrecer «Corregir o aclarar» junto a
las interpretaciones, conservando la procedencia de la corrección.

Añadir «Ver relaciones» como vista opcional del diagrama ER. Permitir seleccionar
una tabla o conexión para consultar sus detalles, estado y precauciones. Para
bases extensas, permitir centrarse en un conjunto de tablas y sus relaciones.
Los nombres técnicos y comprobaciones detalladas quedan desplegables; entender
el esquema técnico no será un requisito para usar el producto.

### Actualización, correcciones y criterios de aceptación

Al incorporar archivos, comprobar si cambian esquema, unidades, granularidad o
cardinalidad antes de reutilizar el conocimiento anterior. Una coincidencia de
nombres de columnas no demuestra que una definición siga siendo aplicable.
Revalidar las relaciones afectadas y mantener explícitas las que no se puedan
comprobar con los datos nuevos.

Al corregir una definición o relación, identificar cálculos e informes
dependientes, marcar lo que requiere revisión y recalcular cuando corresponda.
Conservar las versiones y evidencias históricas sin reescribir los resultados
anteriores como si hubieran usado la nueva interpretación.

Comprobar en el paso 3.2 que un segundo informe y otro chat reutilizan el modelo
vigente; que un archivo cambiado obliga a revisar las relaciones afectadas; que
una corrección identifica los resultados dependientes; que el diagrama coincide
con la versión consultada por el analista; y que ningún acceso mezcla negocios.
Incluir relaciones propuestas, claves duplicadas y muchos a muchos en los casos
de prueba, sin presentarlas como uniones seguras por defecto.

## 5. Investigación por rondas

Ampliar el recorrido actual de planificación, investigación y revisión para que
pueda profundizar según los resultados:

1. **Explorar:** calcular indicadores y comparaciones apropiados para el objetivo.
2. **Detectar:** identificar cambios, concentraciones o anomalías relevantes.
3. **Verificar:** comprobar periodos comparables, cobertura, definiciones y uniones.
4. **Desglosar:** localizar productos, clientes, canales o periodos que explican
   numéricamente la variación y contrastar explicaciones alternativas.
5. **Seleccionar y comunicar:** priorizar lo útil y expresar qué sigue sin saberse.

Por ejemplo, ante una caída de margen, comprobar primero la comparabilidad y
después investigar precio, coste y mezcla de productos cuando haya datos. Un
desglose puede explicar una variación aritmética; no demuestra una causa comercial.

La coordinación debe registrar investigaciones pendientes, completadas, bloqueadas
y descartadas, con presupuestos explícitos de llamadas, tiempo y ejecución.
Priorizar por pertinencia, magnitud, fiabilidad y coste de comprobación. Detenerse
cuando nuevas rondas no aporten suficiente valor o se alcance el presupuesto,
entregando resultados válidos con cobertura y límites explícitos. Recuperar tras
interrupciones sin duplicar trabajo ni perder preguntas pendientes.

Los cálculos nuevos seguirán ejecutándose mediante el analista y sus herramientas,
también cuando el usuario los pida desde el chat. La longitud de la pregunta no
determina si el asistente puede responder sin calcular.

## 6. Calidad de la entrega y papel de los agentes

### Qué debe contener un hallazgo

| Elemento | Comprobación |
|---|---|
| Qué ocurre | Cifra, unidad, periodo y población claramente definidos. |
| Frente a qué | Comparación pertinente y con cobertura comparable. |
| Dónde se concentra | Desglose que permita entender la magnitud, cuando sea posible. |
| Por qué importa | Relación con el objetivo y una decisión del negocio. |
| Qué lo respalda | Cálculo reproducible, fuentes y evidencia vigente. |
| Qué hacer después | Próxima comprobación o acción razonable, separando hechos e hipótesis. |

Preferir pocos hallazgos sólidos; no forzar un número ni inventar sorpresas.
Si el objetivo es organizar la información, valorar claridad, definiciones,
cobertura y utilidad del dashboard. Si es resolver una pregunta, valorar que la
responda de forma directa. La misma rúbrica de «descubrimientos» no sirve para todo.

### Responsabilidades propuestas

- **Asistente conversacional:** interlocutor, guía del onboarding, comprensión de
  objetivos, recuperación de contexto y delegación de nuevos cálculos.
- **Analista:** planificación y ejecución de investigaciones, profundización,
  evidencia y elaboración del informe.
- **Revisor del informe:** exactitud, cobertura, pertinencia, duplicados,
  explicaciones alternativas y distinción entre asociación y causalidad.
- **Revisor de respuestas del chat:** respaldo y coherencia de las respuestas
  conversacionales, sin sustituir la revisión del análisis subyacente.
- **Extractor de memoria:** propuestas de información duradera con procedencia;
  el servicio de memoria valida y conserva versiones y correcciones.
- **Editor del dashboard:** selección y organización de resultados revisados,
  respetando preferencias y sin producir cálculos nuevos por su cuenta.

Empezar con estos roles, mejorando herramientas, contexto y coordinación.
Separar nuevos agentes solo si las evaluaciones muestran una necesidad concreta.
La investigación web de contexto conserva su planificación propia en la entrega 3;
no es requisito para validar primero el análisis de los datos aportados.

## 7. Evaluación con una base sustancial

Utilizar [Wide World Importers](../../data/wide-world-importers/README.md), una
base de negocio ficticia de Microsoft, como primer caso amplio reproducible.
La conversión local documenta 48 CSV y 4.713.833 filas; gran parte del volumen
corresponde a sensores. Las comprobaciones de conversión no validan por sí solas
las conclusiones del producto ni la corrección de todas las uniones analíticas.

1. **Caso de negocio coherente:** empezar con facturas, líneas, clientes y las
   tablas de productos necesarias. Preparar preguntas y cálculos de referencia
   independientes, incluyendo controles de uniones y métricas.
2. **Base completa:** comprobar que el sistema encuentra las tablas relevantes,
   ignora las ajenas al objetivo y amplía el análisis cuando corresponde.
3. **Varios objetivos sobre los mismos datos:** comparar descubrimiento,
   organización/dashboard y pregunta concreta. La entrega debe cambiar según la
   intención sin cambiar las cifras válidas ni prometer capacidades inexistentes.

Seguir el [plan de evaluación](../technical/evaluation-plan.md): mantener las
referencias fuera del contexto del modelo, repetir recorridos, conservar fallos y
realizar una revisión independiente del revisor del producto.

Medir exactitud, calidad de relaciones, hallazgos relevantes encontrados y omitidos,
utilidad respecto al objetivo, preguntas necesarias/redundantes, afirmaciones sin
respaldo, latencia, uso/coste conocido y recuperación tras interrupciones. Incluir
datos incompletos, definiciones ambiguas, correcciones y contexto opcional ausente.
Fijar criterios de aceptación antes de ejecutar; un informe convincente aislado
no demuestra que el sistema generalice.

## 8. Secuencia de implementación y criterios de cierre

Todos los pasos siguientes están **pendientes**. El diseño de objetivos de la
sección 2 queda incluido desde la primera evaluación, aunque su interfaz llegue
en el paso 3.4.

| Paso | Trabajo | Evidencia necesaria para cerrarlo |
|---|---|---|
| 3.1 | Medir el recorrido actual con un caso sustancial y referencias independientes. | Resultados y fallos conservados; métricas de calidad y recursos; límites identificados. |
| 3.2 | Catálogo y memoria de datos persistentes y versionados; definiciones, modelo de relaciones y diagrama ER en «Mi negocio». | Reutilización entre informes y chats, uniones sin duplicación, diagrama coherente, revalidación con datos nuevos y revisión de resultados afectados por correcciones. |
| 3.3 | Investigación por rondas con prioridades y presupuesto. | Profundización útil, parada y recuperación correctas, evidencia y resultados parciales válidos. |
| 3.4 | Onboarding conversacional y elección abierta del objetivo con sugerencias. | Continuidad con el chat, objetivo editable y persistente, datos visibles al preguntar y contexto opcional no bloqueante. |
| 3.5 | Selección y revisión adaptadas al objetivo; evaluación completa repetida. | Mejora demostrada frente a 3.1, entregas útiles para cada intención y ausencia de errores materiales en los casos de aceptación. |

En cada paso: cambios acotados, comprobaciones apropiadas, resultados documentados
y commit local. No marcar un paso como completado por haber escrito este plan.
La predicción mediante machine learning queda fuera de esta secuencia inicial y
necesitará un plan y criterios de aceptación propios.
