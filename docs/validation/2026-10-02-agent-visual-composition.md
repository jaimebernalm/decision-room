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
