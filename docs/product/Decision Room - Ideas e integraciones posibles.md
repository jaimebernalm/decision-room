# Decision Room: ideas e integraciones posibles

Este documento recoge propuestas para explorar más adelante. Registrar una idea
no aprueba su implementación ni modifica el alcance del
[MVP](<Decision Room - MVP.md>) o el
[plan de implementación](<Decision Room - Plan de implementacion.md>).

Cada propuesta debe conservar su fecha, estado, problema que podría resolver,
límites y forma de comprobar su utilidad antes de incorporarla al producto.

## JEV-01: Jev como evaluador de comportamiento

**Registrado:** 22 de septiembre de 2026.  
**Estado:** idea pendiente de evaluación; no integrado ni probado en Decision Room.  
**Decisión actual:** conservar la propuesta; no implementar todavía.

### Qué podría aportar

Jev, de TypeSafe AI, recibe contexto y preguntas concretas y devuelve decisiones
estructuradas: probabilidad de sí/no, elección entre opciones o puntuación.
No genera explicaciones escritas. LangChain anunció su disponibilidad como juez
en LangSmith Evals el 21 de septiembre de 2026.

La propuesta es probarlo primero como evaluador durante el desarrollo, junto a
la [evaluación existente](../technical/evaluation-plan.md). Podría ayudar a
comparar versiones de modelos e instrucciones y detectar regresiones en:

- Definiciones atribuidas al propietario sin respaldo en sus respuestas.
- Aclaraciones esenciales omitidas o preguntas innecesarias.
- Hipótesis presentadas como hechos y conclusiones sin evidencia suficiente.
- Adaptación cuando faltan datos opcionales.
- Capacidad del revisor para detectar errores introducidos deliberadamente.

Estos usos son hipótesis por validar. No se propone delegarle la aprobación de
informes ni sustituir al revisor con acceso a Python.

### Ejemplo del proyecto

En [DR-001](../validation/known-agent-errors.md), el analista atribuye al
propietario una confirmación inexistente sobre la base monetaria de `amount`.
Una pregunta candidata para Jev sería: «¿El propietario confirmó explícitamente
que el importe representa el total de cada fila?».

El contexto debe incluir la respuesta original del propietario y la interpretación
del analista; el resumen del analista por sí solo puede contener el error.
Python y las referencias independientes seguirían comprobando las cifras una
vez establecida la definición correcta.

### Límites y evidencia disponible

La documentación de `jev-1.13` reconoce dificultades con precisión numérica,
conteos y comparaciones de fechas, y recomienda mantener la aritmética en código.
También advierte sobre razonamientos de varios pasos y contexto irrelevante.
Una clasificación favorable no demuestra que un cálculo sea correcto.

El experimento publicado evaluó cinco ejecuciones de un agente meteorológico,
cien veces cada una, contra etiquetas de un único revisor humano. Jev coincidió
con todas las etiquetas, pero son cinco casos distintos repetidos. Ese resultado
no demuestra su fiabilidad en análisis comerciales, español o nuestros errores
conocidos. La estabilidad de un juicio tampoco garantiza su corrección.

### Prueba futura sugerida

1. Preparar ejemplos correctos e incorrectos de los casos de referencia, sus
   variantes y errores conocidos; incluir preguntas y respuestas en español.
2. Etiquetarlos manualmente por criterios concretos y reservar casos que no se
   utilicen para ajustar las preguntas o umbrales.
3. Comparar los juicios de Jev con esas etiquetas, midiendo errores que deja pasar,
   rechazos de resultados correctos, estabilidad, tiempo y coste.
4. Mantener las verificaciones numéricas independientes. Medir por separado la
   calidad semántica y la exactitud de las cifras.
5. Decidir su incorporación solo si aporta una mejora comprobada. Un posible uso
   posterior durante el análisis requeriría otra decisión y validación.

Antes de una prueba, comprobar acceso al proveedor, versión disponible y
condiciones de tratamiento de datos. Empezar con los casos públicos o sintéticos
del proyecto. No se necesitan credenciales ni dependencias para registrar esta idea.

### Fuentes de la investigación del 21 de septiembre de 2026

- [Anuncio de LangChain: Jev en LangSmith Evals](https://www.langchain.com/blog/jev-is-now-available-in-langsmith-evals).
- [Experimento Jev-as-a-judge: método y resultados](https://github.com/danielgshea/jev-as-a-judge).
- [Documentación de TypeSafe: decisiones y preguntas concretas](https://docs.typesafe.ai/introduction).
- [Limitaciones documentadas de jev-1.13](https://docs.typesafe.ai/model-jaggedness/jev-1.13).

Las capacidades y resultados anteriores corresponden a las fuentes revisadas en
esa fecha; deberán comprobarse de nuevo cuando se retome la propuesta.
