# Luna directo: dos rondas de tres informes con gráficos

Fecha: 2 de octubre de 2026. Experimento de desarrollo dentro de
[3.9.7](../technical/report-quality-plan.md), autorizado por el propietario tras
su primera ejecución manual. No cambia el producto ni cierra la aceptación de 3.9.

El informe manual tiene cifras correctas, pero poca profundización y una lista de
comprobaciones sin reacciones suficientemente diferenciadas. Añadir gráficos al
prompt conserva esas limitaciones y produce defectos de visualización. La segunda
ronda mejora profundidad y orientación para decidir: una de tres entregas cumple
los criterios analíticos exigidos para descubrir. Ninguna de las seis entregas
nuevas pasa todos los criterios de entrega; incluso la mejor necesita mejorar
etiquetas y lectura móvil. Terminar una sesión CLI no equivale a entregar calidad.

## Secuencia y controles

1. Conservar el informe manual, sus eventos y el intento de arranque fallido.
   Ese fallo (`codex` no encontrado) no es un intento del modelo.
2. Ejecutar tres sesiones independientes con el contexto original más una
   petición de gráficos y HTML. Auditar cálculos y abrir cada artefacto.
3. Ajustar el prompt tras los resultados, sin facilitar cifras correctas, focos
   esperados ni la referencia del evaluador. Ejecutar otras tres sesiones frescas.
4. Conservar todos los resultados, incluidas cifras erróneas, comandos fallidos y
   errores de navegador. Comparar utilidad, presentación y recursos; preparar una
   galería local. No reparar los informes del modelo ni sustituirlos por el mejor.

Las seis sesiones usan Codex CLI 0.160.0, `gpt-6-luna`, esfuerzo `low`, sin búsqueda
web, apps ni agentes secundarios. Se ejecutan tres a la vez dentro de cada ronda;
no comparten historial y los CSV permanecen idénticos. El ejecutor guarda prompt,
argumentos, tiempos, estado, hashes, consumo, eventos JSONL, stderr y respuesta
final, además del HTML. Usa la autenticación guardada de ChatGPT; excluye variables
API del producto. Las instrucciones predeterminadas de Codex siguen presentes:
se compara Codex con el sistema del producto, no el modelo aislado de toda ayuda.

Invocación, dentro de una carpeta independiente con los cuatro CSV en `datos`:

```sh
codex exec --ignore-user-config --ephemeral --skip-git-repo-check \
  --sandbox workspace-write --model gpt-6-luna \
  -c 'model_reasoning_effort="low"' -c 'web_search="disabled"' \
  -c 'features.multi_agent=false' -c 'features.apps=false' \
  --json --output-last-message respuesta.md - \
  < prompt.txt > eventos.jsonl 2> errores.log
```

Los JSONL contienen comandos, resultados y el consumo comunicado al completar el
turno. No ofrecen coste monetario por herramienta ni una medición homogénea de
llamadas internas del proveedor. Véase la [documentación de ejecución no interactiva](https://learn.chatgpt.com/docs/non-interactive-mode).
No aparece un 429 en los eventos de estas seis sesiones; su autenticación y límites
son distintos de la API del producto. No es una prueba de que se hayan resuelto
los [429 de Decision Room](2026-10-02-provider-diagnostics.md).

## Contexto, fuentes y prompts

Se conserva el contexto manual: Bruma Café, tienda de café y accesorios en
Valencia, tres canales, datos sintéticos; cantidades por fecha/producto/canal.
Se desconoce si los importes son por unidad o fila, apertura, disponibilidad y
cobertura completa; se excluyen dinero, márgenes, retorno de marketing y
predicciones. La pregunta pide evolución de unidades y qué productos/canales
revisar primero y comprobar después.

Fuentes congeladas idénticas al piloto de Bruma, no incluidas en este commit:

| Archivo | Filas de datos | SHA-256 |
| --- | ---: | --- |
| Bruma-Cafe-datos-000.csv | 1.656 | `f8322199f217133be01b78a59e2c7f3265266466b04c98ae8abea27f6e1b82f3` |
| Bruma-Cafe-datos-001.csv | 6 | `22f8f1d157e7e96d52c35e2c3b43dc197c04c038cfa4c74e2366eb828582127d` |
| Bruma-Cafe-datos-002.csv | 3 | `a14f6911f080af3d02ce91bd9efbe84368411f15b980da58d9f8139107aece2d` |
| Bruma-Cafe-datos-003.csv | 9 | `e10c1aec1776d7f86b641310b681aa0a4ee11760a77a8b96ce3d738b0466d7b0` |

Los registros de unidades cubren junio–agosto de 2026: 92 fechas, seis productos y
tres canales, sin duplicados ni huecos de esas combinaciones. Esto describe el
archivo; no certifica apertura, disponibilidad ni exhaustividad del negocio.

La ronda 1 añade únicamente:

> Incluye gráficos en el informe; elige los que mejor ayuden a entender los resultados. Guarda el informe con sus gráficos en informe.html, listo para abrir localmente en un navegador.

La ronda 2 conserva eso y añade:

> Profundiza en las señales relevantes: busca qué combinaciones de producto, canal y fechas las explican y cuánto contribuyen. Haz las comprobaciones que permiten los CSV antes de proponerlas como tarea pendiente. Elige pocas prioridades y explica qué decisión justifica revisarlas antes que una alternativa relevante. Para cada prioridad, indica qué comprobar después y cómo cambiaría la reacción según el resultado. Si falta información, nombra la fuente o registro concreto que haría falta y mantén la conclusión parcial, sin inventar causas.
>
> Comprueba que todas las cifras de la prosa, tablas y gráficos proceden de tus cálculos y coinciden en periodo, segmento, unidad y denominador. Verifica también que los gráficos representen las magnitudes correctas, tengan etiquetas legibles y se abran correctamente. Añade interacción para consultar valores exactos cuando ayude a leerlos. Presenta primero las conclusiones. Calcula con los archivos y muestra solo los resúmenes necesarios, sin imprimir todos los CSV.

## Evaluación de utilidad y errores

Se aplican los doce criterios semánticos de `RUBRIC_39`, con escala 0/1/2. Para
aceptar descubrimiento se exige 2 en significado, profundidad, prioridad,
comprobación siguiente y cifras narradas. La entrega exige además 2 en respaldo
de decisiones, claridad, integridad visual e incertidumbre de fuentes, sin ningún
0. Es una revisión de desarrollo no ciega, adaptada a archivos HTML/Markdown;
no se atribuyen al CLI aprobaciones, referencias, replay o gates de exportación
que pertenecen al protocolo del producto. El total /24 es descriptivo, no una
probabilidad de corrección ni una tasa de aceptación.

| Informe | Total /24 | Profundidad | Prioridad | Comprobación | Cifras | Decisiones | Visual | Descubrimiento aceptado | Entrega aceptada |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| Manual original | 19 | 1 | 1 | 1 | 2 | 1 | 2 | No | No |
| Ronda 1, ejecución 1 | 14 | 1 | 1 | 1 | 1 | 1 | 0 | No | No |
| Ronda 1, ejecución 2 | 15 | 1 | 1 | 1 | 2 | 1 | 0 | No | No |
| Ronda 1, ejecución 3 | 13 | 1 | 1 | 1 | 0 | 1 | 1 | No | No |
| Ronda 2, ejecución 1 | 19 | 2 | 2 | 2 | 1 | 2 | 1 | No | No |
| Ronda 2, ejecución 2 | 23 | 2 | 2 | 2 | 2 | 2 | 1 | Sí, parcial | No |
| Ronda 2, ejecución 3 | 15 | 2 | 0 | 2 | 0 | 1 | 0 | No | No |

El original no pedía gráficos: sus tablas válidas no se penalizan por esa ausencia.
La referencia independiente usa CSV y Decimal, con agregados mensuales, cruces,
fechas, contribuciones y tasas. Se conservan 1.600 comprobaciones explícitamente
mapeadas entre los siete informes: incluyen cifras, fechas, estructura, identidades
y una ambigüedad semántica. No son 1.600 referencias numéricas distintas ni una
prueba automática de que toda la prosa sea correcta. Los defectos encontrados:

- **Ronda 1, ejecución 1:** cuatro gráficos vacíos. Una variable global `top`
  colisiona con `window.top` y detiene todo el script. Datos incrustados correctos,
  salvo redondeo de 24,0% en vez de 24,1%; sigue aplazando análisis disponibles.
- **Ronda 1, ejecución 2:** cifras comprobadas correctas, pero barras de mezcla
  idénticas para 1.748, 1.839 y 2.388 unidades, etiquetas tapadas y leyenda
  superpuesta. La explicación de la ventana móvil describe mal su extremo.
- **Ronda 1, ejecución 3:** cuota de tienda del periodo 21,5% en vez de 29,3%
  (confunde agosto con todo el periodo); Kit agosto Web 197 en vez de 233 y
  Marketplace 178 en vez de 142. Una línea carece de fechas en el eje.
- **Ronda 2, ejecución 1:** profundiza en las 18 celdas, semanas completas y
  quincenas; propone rutas concretas según conciliación y exposición. Las cifras
  de origen son correctas, pero un párrafo confunde qué conjunto excede 100%
  (seis mayores 90,5%; todos los aportes positivos 119,5%; suma firmada 100%).
  Mezcla escalas sin segundo eje, carece de leyenda y desborda a 390 px.
- **Ronda 2, ejecución 2:** 381 comprobaciones correctas. Concilia +476 unidades
  julio–agosto: canales online +569 y tienda −93. Localiza cinco caídas en tienda,
  Kit-Web +118 y Café-Marketplace +100; justifica prioridades y concreta registros
  de pedidos, SKU, estados, TPV e inventario. Diferencia corregir registro de
  comprobar disponibilidad si concilia, conservando incertidumbre causal. Tres
  SVG y consulta exacta funcionan; etiquetas se solapan y ejes/textos quedan
  demasiado pequeños en móvil. Es el mejor análisis, útil pero parcial.
- **Ronda 2, ejecución 3:** aporta contribuciones y regularidad, pero afirma que
  Kit-Web es el mayor aumento junio–agosto; Café-Marketplace es mayor (+5,90
  frente a +5,45 unidades/día). Contradice su propio array ordenado. `D.months`
  ausente provoca una excepción y dos tablas vacías. Hay además dos diferencias
  menores de redondeo; no son el motivo principal del rechazo.

Se abren los seis HTML en Chrome, escritorio 1.440×1.000 y móvil 390×844, con
capturas, errores, elementos y trazas de dibujo. Se comprueba interacción en las
tres entregas de ronda 2, en seis contextos de ratón/táctil: consulta exacta
operativa; teclado de la línea diaria funciona en ejecución 2 y no en ejecución 3.
Los doce recorridos visuales no dependen de recursos externos. HTML renderizado
no implica magnitudes bien representadas, legibilidad ni utilidad.

## Recursos y comparación con Decision Room

| Informe | Segundos | Entrada | Entrada en caché | Salida | Comandos | Comandos fallidos recuperados |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Manual original | No registrado | 127.815 | 111.872 | 3.030 | 6 | 1 |
| Ronda 1, ejecución 1 | 193,554 | 135.848 | 115.200 | 7.352 | 9 | 1 |
| Ronda 1, ejecución 2 | 133,804 | 129.723 | 90.112 | 6.608 | 8 | 1 |
| Ronda 1, ejecución 3 | 204,014 | 154.880 | 129.536 | 7.446 | 9 | 0 |
| Ronda 2, ejecución 1 | 538,120 | 365.924 | 323.072 | 12.495 | 13 | 2 |
| Ronda 2, ejecución 2 | 263,057 | 342.513 | 309.760 | 9.867 | 17 | 1 |
| Ronda 2, ejecución 3 | 477,428 | 246.339 | 220.928 | 11.114 | 12 | 0 |

Las seis sesiones terminan con exit 0 y `turn.completed`; cinco comandos internos
fallan y se recuperan. Se conservan esos fallos. Medianas por ronda:

| Medida | Ronda 1 | Ronda 2 |
| --- | ---: | ---: |
| Tiempo | 3,23 min | 7,96 min |
| Entrada | 135.848 | 342.513 |
| Entrada sin caché | 25.344 | 32.753 |
| Salida | 7.352 | 11.114 |
| Entregas aceptadas | 0/3 | 0/3 |

La entrada incluye caché; no sumar ambas columnas. Son contadores agregados de
los turnos, no tamaño del único prompt inicial. La segunda ronda consume más y
tarda más, sin garantizar aceptación. El original imprimió todo el CSV en un
comando: 406.998 caracteres de salida. La ronda 1 ya evita ese volcado; no se
atribuye su eliminación exclusivamente a la instrucción añadida en ronda 2.

Como referencia histórica, el [piloto Bruma de Decision Room](2026-10-02-report-quality.md)
produce una entrega útil parcial aceptada: 830,263 segundos, 49 llamadas al modelo,
12 ejecuciones y cuatro líneas interactivas. Uso conocido: 2.344.710 tokens de
entrada y 93.574 de salida; cuatro rechazos de transporte carecen de uso conocido.
Tiene 114 referencias numéricas correctas, con comprobación independiente
adicional de 62 fechas focales y medias por día de la semana. Es un recorrido congelado, no tres controles frescos emparejados.
Comandos de CLI y llamadas del producto no son la misma unidad; autenticación,
herramientas, revisión y garantías de entrega difieren. No inferir coste API de
los tokens CLI ni una ventaja causal de un sistema sobre el otro.

## Decisión y límites

El prompt explícito ayuda a Luna a hacer desgloses y convertir señales en
comprobaciones y reacciones, sin exigirle un método o visual único. Mantener esas
instrucciones es razonable. La variabilidad observada justifica conservar
verificación de cifras, prioridades y presentación: pedirle que se compruebe no
basta. Un siguiente experimento acotado podría separar cálculo/evidencia
estructurada de un renderer comprobado, para estudiar cuánto aportan las garantías
del producto sin perder autonomía analítica. No se implementa ese cambio aquí.

Tres repeticiones por prompt, un negocio y adaptación sobre los mismos datos son
optimización de desarrollo. No demuestran consistencia en otros negocios ni
sustituyen evaluación independiente con casos no usados para ajustar el prompt.
Los resultados fallidos se conservan y el piloto del producto no se modifica.
La comparación Bruma/WWI y prueba conjunta de 3.9.7 siguen abiertas.

Artefactos privados locales: siete informes, prompts/manifiestos/estados, JSONL,
referencia CSV/Decimal, evaluaciones por criterio, capturas y pruebas de navegador,
más galería de consulta. No se incluyen datos, trazas, credenciales ni rutas de la
máquina en Git. Validación de este incremento: hashes de las seis entradas
inalterados, JSON/eventos y vínculos locales revisados, doce vistas de informes y
seis contextos de interacción, galería en escritorio/móvil y `git diff --check`.
No se repite la regresión del producto porque este incremento solo documenta el
experimento y añade artefactos locales externos al repositorio.
