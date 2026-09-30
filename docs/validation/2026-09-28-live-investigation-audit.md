# Revisión independiente del paso 3.8

Fecha: 28 de septiembre de 2026. Código revisado: `fcb4e1d`.

**Dictamen:** existe trazabilidad útil y las pruebas focalizadas pasan, pero la
experiencia todavía requiere correcciones antes de aceptarla como producto.
El cierre técnico anterior no demuestra que el progreso sea claro en todos los
recorridos. Esta revisión documenta defectos; no implementa sus soluciones.

## Qué se revisó

- Último turno real del usuario, sobre los datos conocidos de Bruma Café:
  proceso `94cfba0b-b06b-5942-96e6-45d10bc81bac`.
- Última generación analítica real de Bruma:
  proceso `bf5bb200-1851-55a4-8df3-04258980d36f`, informe
  `44717add-6254-409f-af3c-7e103deebf9c`.
- Interfaz de cliente y monitor en el navegador, API y registros originales de
  PostgreSQL. Despliegue de historial, datos relacionados, filtro por agente y
  selección de eventos. Chat a 375 px: documento sin desbordamiento horizontal;
  tamaño restaurado después.

No se generó otro informe ni se modificaron los datos del negocio. Los procesos
revisados ya habían terminado: esto no constituye una nueva medición de latencia
de un informe completo en vivo. Los escenarios en ejecución, interrupciones y
reintentos se comprobaron mediante las suites existentes.

## Evidencia favorable

El último chat finalizó en 7,15 s. Registra una llamada conversacional y una
revisión de respuesta, ambas completadas; la revisión devuelve `approved=true`
y ninguna objeción. No creó cálculos ni delegaciones innecesarias.

El informe conserva tres subanalistas, cuatro consultas de negocio, tres cálculos
únicos y 22 llamadas/22 intentos HTTP. El tiempo registrado de generación es
303,91 s, con 46,37 s esperando al usuario. No hay tareas activas pendientes y el
historial declara captura completa. Estos recuentos coinciden con los registros
consultados; no implican una nueva evaluación de calidad de sus conclusiones.

Los intercambios explícitos sí permiten entender decisiones. Por ejemplo, el
evento 83 del planificador pidió profundizar en producto×canal y usar nombres
legibles, en función de los resultados recibidos. Después se delegó la tercera
rama para esa comparación. La selección devuelve el evento concreto solicitado.
También son accesibles el código, resultados de cálculo y decisión del revisor.

Esto ofrece encargos, justificaciones explícitas y evidencia. No es una cadena
privada de pensamiento ni un flujo de tokens internos del proveedor.

La línea plegada del cliente es discreta y coherente con la tipografía y colores
de la plataforma. El historial del informe abre una vista de los datos de la
comprobación, manteniendo la navegación de la aplicación.

## Hallazgos y orden de corrección

### 1. Alta: memoria pendiente convierte un informe aprobado en inaccesible

El informe terminó a las 16:53:36. El perfil original se había guardado a las
16:48:32, pero su extracción de memoria se aplicó a las 17:48:20, al activar el
worker de la demo durante la corrección anterior. El manifiesto inicial tenía
`memories=[]`. La incorporación tardía de esos hechos activó
`Applicable business memory changed; replan with current definitions.`

El monitor muestra «El análisis usa contexto anterior». La vista del informe
oculta el contenido y muestra «Este informe no ha superado la revisión o ha
quedado desactualizado». El usuario no corrigió sus datos para provocar esto.
La demo quedó expuesta a este caso porque generó el informe antes de procesar
la memoria pendiente del perfil.

La protección ante cambios de definiciones tiene sentido, pero la experiencia
debe explicar qué cambió y ofrecer recuperación. La cronología actual termina
en tareas completadas y no explica la invalidación posterior.

Propuesta: establecer una barrera explícita de preparación de memoria antes de
fijar el contexto analítico; distinguir incorporación pendiente, información
nueva y corrección de una definición. Registrar la causa de invalidación y
mostrar una acción de actualización. No eliminar los controles de vigencia ni
considerar equivalentes dos definiciones solo por parecido textual.

Referencias: `decision_room/memory/context.py` (`create`, `reason`, `watch`),
`decision_room/web/service.py` (`worker`),
`decision_room/observability/projection.py` (`state`).

### 2. Alta: «Ver proceso» del chat finalizado abre un historial vacío

En el último turno real, el cliente muestra «Proceso completado · Ver proceso».
Al desplegarlo aparece «Las comprobaciones aparecerán aquí cuando se registren».
El monitor sí contiene nueve eventos, incluida la preparación y revisión de esa
misma respuesta. El mensaje de espera es incorrecto para un turno terminado.

La proyección pública excluye `chat_call` y `chat_review`; el componente también
los filtra. Un chat sin recuperaciones adicionales puede quedar sin actividades
visibles aunque haya trabajado correctamente.

Propuesta: proyectar hitos públicos de preparación, consulta de fuentes cuando
realmente ocurra, y revisión. Para un saludo trivial puede omitirse el desplegable;
si no existe historial, indicar ese hecho con un texto final. Nunca anunciar un
proceso consultable que solo ofrece una promesa futura vacía.

Referencias: `decision_room/observability/projection.py` (`PUBLIC_KINDS`, `visible`),
`frontend/src/components/workspace/analysis-activity.tsx` (filtro y estado vacío).

### 3. Media: detalle interno legible solo como JSON

Los filtros y enlaces funcionan, pero «Encargo, intercambio y evidencia» presenta
un único bloque JSON. Las propiedades de ejecución de Docker, IDs, entradas,
salidas y eventos repetidos compiten visualmente con la decisión que se quiere
entender. A anchuras menores de 1024 px, el detalle queda debajo de la cronología.

Propuesta: encabezado con actor, tarea y resultado; intercambio analista →
planificador → decisión; secciones para evidencia, código, revisión y recursos.
Dejar el JSON como detalle técnico desplegable. Mantener el vínculo al evento
exacto y señalar explícitamente contenido truncado. Mostrar el título/objetivo
del proceso y qué rama investiga cada subanalista.

Referencia: `frontend/src/components/workspace/internal-monitor.tsx`.

### 4. Media: historial del informe demasiado genérico y técnico

En Bruma aparecen cuatro entradas «Enfoque contrastado con tu objetivo» y tres
«Cálculo completado», sin distinguir fácilmente qué resolvió cada una. Una rama
se presenta como un encargo largo que incluye `P06`, `WE`, `TI` y se corta con
puntos suspensivos. «Investigar: ¿…?» permanece igual después de terminar.

Propuesta: textos breves de actividad pública, con tabla o dimensión cuando sea
conocida, estados verbales adecuados y agrupación de pasos técnicos relacionados.
Conservar cambios de enfoque relevantes. No publicar conclusiones candidatas
para hacer el progreso más atractivo ni reemplazar eventos reales por animaciones.

Referencias: `decision_room/observability/collector.py` (etiquetas de ramas,
cálculos y consultas), `frontend/src/components/workspace/analysis-activity.tsx`.

### 5. Media: tiempos de finalización incorrectos en las llamadas de chat

En la revisión del último turno, el detalle muestra inicio y fin iguales:
17:51:08.122184. Su finalización se registró a las 17:51:09.552542. El colector usa
`created_at` tanto para el estado inicial como para el completado de las llamadas
de chat y revisión. La duración total del turno sí es coherente.

Propuesta: persistir la finalización real de esas llamadas y usarla al proyectar
tiempos. Para registros históricos sin ese dato, indicar que es desconocido o
reconstruido. No asignar duración cero a una operación cuyo fin no está registrado.

Referencia: `decision_room/observability/collector.py`, llamadas a `observe` de
`chat_call` y `chat_review`.

## Incidencia adicional de navegación

Una pestaña abierta con una compilación anterior quedó en blanco al navegar al
chat: falló la carga de un módulo JavaScript cuyo nombre ya no existía. Recargar
recuperó la aplicación. Añadir recuperación de errores de carga de módulos y
aviso de versión nueva para evitar una pantalla vacía después de actualizar.

## Pruebas ejecutadas en esta revisión

- `test_activity test_activity_integration test_internal_monitor`: **22 pruebas**,
  13,93 s, pasan con PostgreSQL y sandbox disponibles. La excepción de tabla
  inexistente corresponde a la inyección de fallo prevista por el test.
- `analysis-activity.test.tsx`: **11 pruebas**, pasan.
- Navegador: expansión real de los dos historiales, tabla paginada desde actividad,
  filtro del planificador y selección del evento 83; revisión del último chat y
  vista móvil a 375 px.

Los tests actuales no cubren los cinco defectos anteriores de forma que los
detecten. Antes de cerrar sus correcciones, añadir regresiones para memoria
pendiente al crear un informe, chat finalizado sin tareas públicas, tiempos de
llamadas y una revisión visual del detalle y de los textos de actividad.
