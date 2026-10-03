# 3.9.9.1 — Composición visual elegida por los agentes

El analista puede superponer hasta seis series temporales guardadas (800 puntos
en total), elegir nombre, función, trazo y énfasis, y decidir si una transformación
ayuda al objetivo. El planificador orienta la pregunta; no impone gráfico ni
ventana. El revisor comprueba utilidad, definiciones y evidencia.

Las capas requieren unidades y grano temporal iguales. Sus fechas se alinean
sin transcribir, agregar ni rellenar ausencias. La media móvil opcional declara
serie original, ventana de 2–90 días, alineación hacia atrás, redondeo y tratamiento
de ausencias. Se recalcula cada ventana completa contra la serie original:
se rechazan valores falsos, anticipación, ventanas parciales y puntos omitidos.
No se impone suavizado. Otras medidas derivadas conservan la revisión de su
código y fórmula ejecutados.

Web, HTML y PDF conservan valores, estilos y procedencia. La huella de aprobación
incluye las capas y sus productores. Los informes históricos siguen admitidos.

## Comprobaciones

- 621 pruebas de servidor pasan en una base temporal independiente; 393 segundos.
- 237 pruebas de interfaz pasan, incluidas visibilidad y restitución de una curva
  derivada, trazo discontinuo y grosor elegidos por el agente.
- Build y lint completados; permanecen avisos previos de tamaño del paquete y lint.
- Regresiones focales: 45 pruebas de series, fechas ausentes, redondeo, fuentes
  obsoletas, unidades incompatibles, huella, selección, web, HTML y PDF pasan.
- Revisión del diff y archivos públicos; datos, credenciales y resultados
  generados permanecen en almacenamiento local ignorado.

Estas pruebas verifican capacidad y coherencia. La adopción real por los agentes
y la utilidad comparada requieren el nuevo recorrido de 3.9.9.2. La aceptación
repetida de 3.9.7 permanece abierta.

## Corrección detectada en el primer recorrido

El prompt exacto de Luna pide `informe.html`. El primer recorrido produjo evidencia
comercial, pero intentó generar HTML dentro del cálculo (formato no permitido) y
el planificador exigió ese archivo antes de entregar el material a la fase que lo
genera. Se interrumpió tras 738,294 segundos; se conservan 58 llamadas (incluido
el descubrimiento de datos), ocho
rechazos de transporte 429, catorce ejecuciones (seis completadas y ocho fallidas),
incluida la llamada interrumpida y su uso incompleto. No es una entrega aceptada.

La corrección conserva HTML/gráficos como requisito de entrega, asigna medidas y
composición a los agentes y render/exportación a la aplicación después de revisar.
Tres cierres consecutivos sin nuevo trabajo y con dos guías de entrega pendientes
detienen el recorrido como parcial; no conceden aprobación automáticamente. La
evaluación independiente ahora exige vincular cada punto de todas las capas a la
referencia CSV, también cuando la serie solo aparece en el gráfico.

Validación de la corrección: 147 pruebas focales de planificación, planificador,
investigación, delegación, revisión, evaluación y capas pasan en una base temporal
independiente (111,244 segundos). Incluyen detener el bucle sin aprobar y reanudar
sin duplicar llamadas, además de rechazar puntos derivados incorrectos o sin
vínculo independiente. El build de interfaz anterior no cambia.

La repetición conservó fuentes y prompt; ambos intentos y sus errores siguen
separados y contabilizados. Véanse los [resultados del piloto](2026-10-02-agent-visual-freedom-pilot.md).
