# 3.9.9.2 — Informe nuevo con el encargo exacto de Luna

**Nota posterior, 3 de octubre:** la [auditoría del recorrido](2026-10-03-report-quality-forensics.md)
reproduce un defecto del esquema productor que impide generar capas válidas.
La ausencia de capas no puede atribuirse exclusivamente a una elección del agente;
la integración de esa capacidad queda reabierta. La puntuación siguiente conserva
la evaluación histórica: el diagnóstico distingue ranking correcto de prioridad
útil y aclara que la preferencia conversacional por líneas no formaba parte del
prompt controlado. Las cifras del piloto no cambian.

La composición visual está implementada y comprobada, pero este piloto **no
demuestra una mejora de entrega respecto al mejor Luna**. La repetición termina
con cifras correctas y aprobación parcial del producto. No pasa la aceptación
independiente por profundidad, claridad, reacción comercial e integridad visual.
El agente eligió dos barras y no usó capas ni medias móviles; no se modificó su
informe para presentar una adopción que no ocurrió.

## Secuencia y comparabilidad

1. Congelar `466171b`, copiar los cuatro CSV y el prompt exacto de Luna ronda 2,
   ejecución 3; verificar hashes y el montaje real del entorno de cálculo.
2. Ejecutar desde cero: descubrimiento, planificación, planificador, investigación,
   revisión y exportación. No suministrar referencias numéricas, informes anteriores
   ni respuestas operativas inventadas.
3. Conservar el primer intento interrumpido: guardar HTML se convirtió en un
   requisito previo al paso a entrega, con artefactos inválidos y cierres repetidos.
   No reenviar la llamada interrumpida ni sustituir el intento por un éxito.
4. Corregir responsabilidad de las fases y cierre sin progreso en `35760d3`;
   comprobar 147 pruebas focales. Congelar esa revisión y repetir desde cero en
   nueva base/almacenamiento con entradas exactamente iguales.
5. Auditar todas las referencias contra CSV/Decimal independiente, exportar
   HTML/PDF e incorporar la aprobación real a la web habitual en **Bruma Café ·
   comparación Luna**, preservando el negocio y los informes previos.

El prompt tiene SHA-256
`906ffd097108352e1e4f0656138748f1533c6246fb7701216f81c87f75480e06`.
Los CSV conservan los cuatro hashes publicados en la
[comparación Luna](2026-10-02-codex-luna-comparison.md#contexto-fuentes-y-prompts).
Hay 1.656 filas, seis productos, tres canales y 92 fechas de junio–agosto de
2026: 1.541, 1.979 y 2.455 unidades registradas. Se excluyen importes, márgenes,
retorno de marketing y predicciones; no se confirma apertura, disponibilidad,
exhaustividad ni causas externas.

El contexto del propietario se conserva exactamente, sin añadir objetivo ni
resultados esperados. Se usa `gpt-6-luna`, esfuerzo bajo, sin internet, investigación
serial y presupuestos normales de calidad. La referencia permanece fuera de las
entradas de los agentes y del entorno de cálculo. Sistema, herramientas, revisión
y autenticación API difieren del CLI autenticado con ChatGPT; es desarrollo, no
un ensayo causal. El mejor Luna de la misma ronda también usa ese prompt y CSV.

## Resultado y recursos

| Recorrido | Estado | Segundos | Llamadas API, incluido descubrimiento | Ejecuciones completadas / intentos | Rechazos 429 |
| --- | --- | ---: | ---: | ---: | ---: |
| Primera instantánea | Interrumpido, sin entrega | 738,294 | 58 | 6 / 14 | 8 |
| Repetición corregida | Aprobado parcial, exportado | 245,979 | 17 | 2 / 3 | 0 |

La repetición incluye dos llamadas de planificación, cuatro del planificador,
ocho de investigación, una de redacción, una del revisor y una de descubrimiento.
Un programa falló por un nombre de columna de pandas y se corrigió. El primer
intento conserva cuatro fallos de programa, cuatro resultados inválidos por HTML
y la llamada interrumpida durante espera de reintento.

La repetición registra 348.395 tokens de entrada y 22.651 de salida, con uso completo.
El intento interrumpido registra **al menos** 2.094.715 de entrada y 81.680 de salida;
faltan el uso de una llamada y el de ocho rechazos. Ambos suman 75 llamadas y
984,273 segundos de recorrido. No se infiere coste API del CLI ni se excluye el
intento fallido para atribuir eficiencia. Cero 429 en la repetición no resuelve la
dosificación compartida.

Contextos, respuestas, código, resultados, errores, eventos, revisiones, manifiestos,
uso y exports permanecen locales e ignorados por Git. Reanudar la revisión aprobada
no añade llamadas ni cambia su huella. Código y fuentes congelados siguen iguales.
No se corrigió manualmente prosa, cifras ni gráficos del informe.

## Calidad independiente

Las **25 referencias numéricas distintas** de gráficos, hallazgos, orientación y
tarjetas se vinculan explícitamente a expresiones CSV; todas coinciden. También se
comprueban rango, filas, grupos, ranking y redondeo de prosa. Kit–Web es el mayor
aporte positivo individual **julio–agosto** (+118), frente a Café–Marketplace (+100);
el intervalo anterior se presenta separado (+53 y +88). No repite el error de
Luna ejecución 3 de declarar Kit líder junio–agosto, donde Café–Marketplace es mayor.

Rúbrica 3.9, revisión de desarrollo no ciega:

| Criterio | Puntos / 2 | Evidencia o limitación |
| --- | ---: | --- |
| Significado | 2 | Unidades registradas y datos sintéticos; sin importes ambiguos ni causas inventadas. |
| Cobertura | 1 | Evolución global y combinaciones; falta síntesis de evolución por canal y del descenso de tienda. |
| Profundidad | 1 | Contribuciones de los 18 cruces; no contrasta fechas más finas pese a disponer de ellas. |
| Prioridad | 2 | Periodo reciente explícito, ranking correcto y alternativa material. |
| Siguientes comprobaciones | 2 | Fuentes, segmentos, fechas y rutas según conciliación e historial, si existen. |
| Comparabilidad | 2 | Totales y sensibilidad por fechas observadas definidos; no presupone apertura. |
| Claridad | 1 | Advierte que no existe HTML, aunque el export posterior lo crea; lista visual larga. |
| Ausencia de repetición | 1 | Resumen, hallazgo y orientación repiten cifras y segmentos; cautelas duplicadas. |
| Cifras narradas | 2 | Referencias y afirmaciones adicionales contrastadas con fuentes independientes. |
| Decisiones | 1 | Corregir captura es concreto; ante coincidencia operativa propone otra revisión genérica. |
| Integridad visual | 1 | Valores e interacción correctos; 18 etiquetas recortan la identidad del canal en la vista habitual. |
| Incertidumbre de fuentes | 2 | Registros externos y disponibilidad no inventados; límites explícitos. |

Total **18/24**, descriptivo. No pasa descubrimiento ni entrega independiente;
aprobación del modelo y aceptación son distintas. No usar una media móvil no es
por sí mismo un fallo: debe aportar a la pregunta. El fallo visual es legibilidad
y selección de categorías. La progresión en barras tampoco aprovecha la preferencia
previa del propietario por líneas.

Luna ejecución 3 obtuvo 15/24, con ranking de periodo incorrecto y dos tablas vacías.
El mejor Luna de la ronda, ejecución 2, obtuvo 23/24: profundiza en tienda, propone
reacciones y muestra distribución diaria, aunque conserva problemas de legibilidad.
La nueva entrega mejora corrección respecto a ejecución 3, pero no supera la
utilidad del mejor Luna. Una repetición completada de dos intentos, un negocio y
adaptación tras un fallo no prueban consistencia.

## Publicación y siguiente trabajo

La aplicación conserva aprobación, evidencia y los cuatro CSV idénticos. Web,
PDF y actividad devuelven 200 autenticados; 401 anónimo y 404 desde otro negocio.
El historial real queda enlazado. Se comprueban página, tooltip de junio (1.541),
fuentes y valores, etiquetas recortadas y hallazgo temporal en navegador. Capturas
y JSON permanecen locales. La actualización inicial de assets requirió recargar
una vista; después se verificó la entrega cargada.

La capacidad está entregada; queda mejorar su uso: justificar composición por
pregunta, seleccionar un foco legible con detalle completo accesible, contrastar
señales dentro del periodo cuando ayude a decidir y evitar advertencias del modelo
sobre una exportación realizada después. Mantener libertad de método y ventana,
sin exigir siete días ni líneas adicionales por decoración. **3.9.7 permanece
abierto**, igual que la dosificación global de tokens.
