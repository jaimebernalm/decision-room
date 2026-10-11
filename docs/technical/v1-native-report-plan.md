# Informe v1 nativo en la plataforma (plan)

**Estado:** propuesta de Claude revisada por Astra (bridge run 3fcd88db). La versión 1
recibió «revise» con nueve grupos de cambios, ya incorporados aquí. Es un plan: no autoriza
código ni gasto. Cada fase de §7 necesita autorización del dueño.

## 0. Punto de partida

- **Idea del dueño (11 de octubre de 2026):** el informe v1 no debe verse como una página HTML
  aparte, sino integrado en la plataforma, con sus gráficos y su diseño.
- **Matiz del dueño:** v1 debe tener **mucha libertad** para decidir qué cuenta y cómo lo
  organiza. Lo único que cambia es que **no crea el HTML: entrega los datos** y la plataforma
  los presenta. Además pidió tener en cuenta dos cosas: añadir tipos de gráfico, con tabla
  como respaldo, y comprobar las cifras de las prioridades sin pedir declaraciones cifra a cifra.
- **Contexto:** F5 terminó incompleto, con legacy por defecto
  ([resultados](../validation/2026-10-11-f5-results.md)). v1 fue preferido en las 12 lecturas
  y tuvo un error crítico de cifra en una prioridad. Este plan aborda la presentación y la
  comprobación de cifras.
- **Se crea como variante nueva, `blocks-v1`,** junto a `html-v1`. Legacy sigue por defecto y la
  ruta HTML se conserva para los informes históricos.

## 1. Qué pasa hoy

- v1 escribe `informe.html` con sus propios estilos y gráficos SVG.
- Por seguridad (F4, `presentation.py`), ese HTML nunca se pinta en la plataforma. Un navegador
  aislado lo convierte en imágenes, y el dueño ve esas imágenes en un marco, más el texto.
- **Consecuencias para el dueño:**
  - el diseño y los gráficos no son los de la plataforma;
  - no hay PDF;
  - el inicio no extrae tarjetas de cifras de v1 (`home.py` excluye `opencode`);
  - no se puede seleccionar un gráfico o un párrafo para preguntar en el chat.
- **Consecuencias técnicas:**
  - v1 necesita el renderizador aislado (imagen Chrome);
  - el fallo «Rendered pixels do not stabilize» de F5 vino de ahí (corregido en raster-2).

## 2. Principio: libertad en el contenido, datos en la entrega

| Lo decide v1, como ahora | Lo pone la plataforma |
|---|---|
| Qué contar, en qué orden y con qué extensión | Tipografía, colores, espaciado y estructura visual |
| Cuántas secciones, cifras destacadas y prioridades | Cómo se dibuja cada gráfico y cada tabla |
| Qué gráficos y tablas usar, y con qué datos | Ventana con el valor exacto al pasar el ratón |
| Tono, explicaciones y límites | PDF, selección para el chat y, si el dueño lo decide (D2), tarjetas del inicio |

**No es una plantilla.**
- No hay apartados obligatorios ni número fijo de prioridades.
- No se pide evidencia ni declaración cifra a cifra: esa exigencia hundió la cobertura en V1–V3.
- Se mantienen las instrucciones analíticas del encargo. No se convierten en un contrato rígido
  de métricas ni de evidencia.

## 3. Formato de entrega

v1 entrega un fichero JSON con una lista ordenada de bloques. El orden y la cantidad los elige
él, dentro de los límites.

| Bloque | Obligatorio | Opcional |
|---|---|---|
| `seccion` | título; bloques dentro | — |
| `texto` | contenido en un árbol pequeño de formato: párrafo, negrita, cursiva, lista | — |
| `cifra` | etiqueta y valor | unidad, periodo, comparación (valor anterior y diferencia) |
| `grafico` | tipo, título y datos (categoría, serie, valor) | unidad, títulos de ejes, nota |
| `tabla` | columnas y filas | unidad por columna, nota |
| `prioridad` | título; bloques dentro (contenido libre) | — |
| `aviso` | texto | — |

**Libertad.** Ningún bloque impone campos analíticos nuevos. Una prioridad es un título más el
contenido que v1 quiera poner dentro. «Qué comprobar después» sigue pedido en el encargo, no en
el esquema.

**Representación y seguridad.**
- **Formato del texto:** el texto con formato se entrega como un árbol de nodos (párrafo,
  negrita, cursiva, lista), no como marcado que haya que interpretar.
- **JSON estricto:**
  - UTF-8 válido, sin claves duplicadas y sin NaN ni Infinity;
  - tipos y precisión numérica definidos;
  - ninguna URL, HTML, CSS ni código que se pueda evaluar;
  - todo el texto se escapa al presentarlo.
- **Identificadores:** cada bloque tiene un id único y estable dentro de su revisión.
- **Versiones fijadas:** esquema, perfil y encargo.
- **Límites globales,** además de los límites por gráfico: el límite actual de 256 KiB,
  profundidad, número total de nodos, caracteres, celdas y puntos. Se fijan en N0 a partir de lo
  que v1 entregó en F5.

**Recepción.** Se generaliza `file_delivery` y `receive_document` tal como funcionan hoy:
- el perfil congelado fija el nombre del fichero (`/work/informe.json`), nunca el agente;
- se guardan los bytes y el hash exactos de forma durable **antes de interpretarlos**;
- se mantienen la idempotencia, el registro de intentos rechazados y las revisiones inmutables.

**Validación.**
- El contenedor incluye una orden de comprobación (`comprobar_informe`, nombre provisional) para
  que v1 corrija errores mientras todavía tiene contexto. Es solo una ayuda: puede omitirse o
  falsearse.
- **La validación que cuenta es la del producto**, con la misma versión del esquema, después de
  guardar los bytes.
- Una entrega malformada se conserva, pero nunca pasa a vigente ni se muestra como informe
  correcto.
- Un **tipo de gráfico desconocido no es un error:** conserva sus datos y se muestra como
  tabla. Se distingue de un contenido inválido.

**Texto canónico** para el chat y la búsqueda: se deriva del JSON, sin renderizador.

**Encargo:** solo cambian el primer y el último párrafo de `informe.md`:
- guardar como datos en lugar de HTML;
- quitar «añade interacción» y «se abran correctamente».

## 4. Gráficos

**Qué usó v1 en F5** (11 informes, inventario de `informe-agente.html`, leído como texto):
- barras horizontales de cambio por canal o segmento, con positivos y negativos;
- barras agrupadas de un año frente a otro;
- barras de contribuciones de producto × canal;
- evolución mensual en barras o en línea con puntos;
- líneas con varias series (app frente al resto de canales; tasa mensual);
- tablas de detalle en todos los informes;
- ventanas emergentes con el valor exacto en casi todos.

No se vieron circulares, de dispersión ni mapas de calor.

**Qué tiene ya la plataforma** (`EvidenceChart`, recharts):
- barras horizontales, agrupadas por series, con medida de nivel o de cambio;
- línea de una serie;
- tablas;
- ventana con el valor exacto.

**Qué hay que añadir:**
1. **Línea con varias series** (hasta 6) y puntos marcados.
2. **Columnas** para series temporales.
3. **Barras de cambio con signo** cuyo eje cero esté siempre visible.
4. **Porcentajes y tasas** con su unidad y su denominador en la ventana emergente, si v1 los da.

**Respaldo:** un tipo que no existe se muestra como tabla con los mismos datos y queda
registrado. Si un tipo aparece con frecuencia, se añade.

**Casos que hay que probar:**
- meses frente a días;
- un hueco frente a un cero;
- porcentajes con unidad y denominador;
- negativos y eje cero;
- etiquetas largas;
- tablas y textos en tamaños extremos.

v1 no elige colores ni estilos, solo los datos y el tipo.

## 5. Comprobación de cifras

**Qué se aprendió en V1–V3.** Obligar al motor a declarar o marcar cada cifra no funcionó:
- en V2 declaró el 24 % de las cifras de las prioridades;
- en V3 la cobertura llegó al 33,8 %;
- en V1 el catálogo cerrado de recetas no cubría ratios ni grupos residuales.

Este plan no pide nada cifra a cifra.

**Controles aritméticos (opcionales, deterministas, sin modelo).**
- Comprueban relaciones que ya están en los datos del propio informe. Por ejemplo, que en una
  `cifra` con comparación la diferencia sea igual al valor menos el valor anterior.
- Sirven solo de diagnóstico. **No aprueban ninguna cifra, no reducen el alcance de la
  comprobación independiente y no bloquean la entrega.**
- Que un número aparezca en varios sitios del informe no prueba nada: el 636 podría repetirse en
  todos y seguir siendo incorrecto.
- Por eso no se le exige a v1 una carpeta de resultados. Si en el futuro se añadiera un rastro
  acotado, solo leería formatos de datos seguros y contaría como cambio de variante.

**Comprobación independiente.**
- **Aislamiento:** contenedor nuevo y volúmenes nuevos, sin archivos, estado ni sesión del autor.
- **Qué recibe:**
  - los CSV congelados;
  - el texto de las prioridades;
  - las definiciones, alias, semántica y declaraciones del dueño congeladas que hagan falta para
    entenderlos.
- **Qué no recibe:** el panorama calculado, los resultados del autor ni ningún oráculo.
- **Qué devuelve:** extrae por sí misma las cifras de las prioridades y liga cada comprobación al
  id de bloque, al fragmento con su posición y al hash de la revisión. Para cada cifra registra
  `confirmada`, `discrepancia` (con su cálculo y resultado) o `no comprobable`, además de la
  cobertura y la incertidumbre.
- **Límites:** «no comprobable», o quedarse sin presupuesto o sin tiempo, no confirma nada. La
  independencia es de proceso y de contexto, no una garantía estadística entre modelos.

**Vuelta de corrección.**
- **Con el motor actual no se puede reabrir un informe entregado:**
  - al recoger el fichero, `api._finish` revoca la credencial;
  - `_drive` termina en estado final;
  - `resume_report` no reabre estados terminales;
  - `collect_report` detiene el entorno de ejecución.
- **Nuevo ciclo durable antes del cierre,** conservando la sesión, los archivos y el contexto del
  autor:
  1. borrador;
  2. comprobación;
  3. como mucho una corrección, reiniciando el entorno de ejecución de forma controlada antes del
     turno corrector;
  4. comprobación final;
  5. selección de la revisión y publicación.
- **Se persisten:**
  - la etapa, los recibos, la revisión elegida y los ids de mensajes y comprobaciones;
  - la cola de salida y el límite de una vuelta.
- **Si el proceso muere o el resultado es incierto,** se reconcilia sin reenviar.
- **La comprobación final examina la revisión final**, incluidas las cifras nuevas que añada la
  corrección. Un resultado anterior nunca se aplica a bytes nuevos.
- **Presupuesto:** autor, comprobador y vuelta final comparten el mismo techo P4 y los mismos
  límites acumulados. Hay subpresupuestos dentro del techo, nunca saldo adicional.
- **Hay que definir qué pasa si:** no queda cuota, falla el comprobador, o cambia o caduca el
  contexto. Esa conducta se fija en el contrato de N3 antes de programar. Los borradores de ejecuciones abortadas o fallidas se conservan sin promoverse.

**Qué ve el dueño.** Propuesta, que decide él (§9 D1):
- Si una discrepancia sigue tras la vuelta de corrección, el informe se entrega con un aviso
  visible junto a esa cifra. Por ejemplo: «Una comprobación independiente no obtuvo esta cifra;
  revísala antes de decidir».
- **Nunca se muestra «Revisado»** ni una marca de verificado en las cifras confirmadas (P5).

**Prueba antes de usarlo en el producto (N3).**
- **Desarrollo:** los 11 informes v1 de F5, ya auditados.
  - Herbolario: 141 cifras de prioridades, de ellas 133 correctas, 7 con errores menores y 1
    crítica.
  - Clínica: 108 cifras, de ellas 107 correctas y 1 con un error menor.
  - Se añaden errores sembrados en copias.
- **Este conjunto ya es conocido:** sirve para desarrollar, no para afirmar exactitud ni
  generalidad. Que el comprobador cace el 636 no lo acredita en general.
- **Validación retenida nueva,** preregistrada, antes de usarlo en el producto. Mide:
  - cobertura;
  - detección;
  - falsas alarmas;
  - casos no comprobables;
  - coste y latencia;
  - anotaciones independientes.

## 6. Compatibilidad con lo construido en F1–F4

- **Formato nuevo `engine_blocks`** en `report_documents`, con una migración aditiva. Hoy hay un
  CHECK `origin = engine_html`; `adopt` asigna siempre esa fuente y encola Chrome. La migración
  no cambia ids, hashes ni contenidos HTML históricos.
- **Despacho por formato** en recepción, derivados, export y chat:
  - export en JSON con su tipo MIME (hoy se llama `informe.raw.html`);
  - estados separados: bruto guardado, validado, presentable y terminal;
  - derivado nativo inmutable, con versiones de esquema, proyector y política, sin necesitar la
    imagen Chrome.
- **Publicación atómica,** con las mismas guardas de negocio, documento, revisión, vigencia y
  borrado. Cada corrección es una revisión nueva.
- **N2 no fabrica `Claim`, `MetricRef` ni aprobaciones de legacy** para encajar en los
  componentes. Reutiliza piezas visuales, no el contrato de legacy.
- **Chat:**
  - Las guardas de `conversations` excluyen hoy solo `engine_html`. `engine_blocks` debe
    tratarse por su fuente y su aprobación, sin caer en la decoración de evidencia de legacy.
  - La selección usa `block_id`, distinto del `claim_key` de legacy.
  - Las referencias son exactas: revisión y hashes del bruto, canónico, proyector y comprobación.
  - Prueba: buscar → abrir → responder.
- **PDF:** sale de una plantilla de la plataforma, escapada, a partir de los bloques. Nunca usa
  marcado del agente. Hay que probar que no se pierden tablas ni gráficos y que muestra el mismo
  estado de comprobación.
- **Inicio:** no cambia de forma implícita (D2).

## 7. Fases

Legacy sigue por defecto en todas.

**N0. Esquema e interfaz** (Claude, revisa Astra)
- **Contenido:**
  - esquema de bloques, límites y versiones;
  - contrato del registro y del proyector canónico entre N1 y N2;
  - dueños de cada archivo.
- **Termina cuando:** el esquema está acordado y aprobado por el dueño.
- **Vuelta atrás:** solo documentos.

**N1. Recepción y registro** (Astra, revisa Claude)
- **Contenido:**
  - perfil `blocks-v1`;
  - generalización de `file_delivery` y `receive_document`;
  - validador del producto y orden `comprobar_informe` en la imagen;
  - migración aditiva y despacho por formato;
  - proyector canónico y export JSON;
  - cambio de los dos párrafos de `informe.md`.
- **Termina cuando:**
  - pasan las pruebas con proveedores falsos y sin gasto;
  - la migración se aplica dos veces sin efecto;
  - los históricos HTML quedan intactos;
  - los casos malformados se conservan sin publicarse.
- **Vuelta atrás:** perfil desactivado; migración solo aditiva.

**N2. Presentación** (Claude, revisa Astra)
- **Contenido:**
  - React con piezas existentes;
  - tipos de gráfico de §4 y respaldo en tabla;
  - selección para el chat;
  - PDF.
- **Termina cuando:**
  - pasan las pruebas sin imagen Chrome configurada y la regresión de legacy;
  - los casos extremos de §4 se ven bien;
  - los 11 informes de F5 convertidos a mano se ven correctamente.
- **Sobre esa conversión a mano:** conserva textos y números, incluidos los errores, con
  trazabilidad por hash. Sirve solo para la interfaz, no mide `blocks-v1`. Los HTML del ensayo no
  se suben al repositorio.
- **Vuelta atrás:** la vista queda inaccesible si el perfil está desactivado.

**N3. Ciclo de comprobación** (Astra, revisa Claude)
- **Contenido:**
  - comprobador aislado;
  - ciclo durable de §5 y aviso;
  - prueba de desarrollo y validación retenida preregistradas.
- **Termina cuando:**
  - la validación retenida pasa su regla;
  - pasan las pruebas de muerte del proceso, dos workers a la vez, corrección única y límites
    compartidos.
- **Vuelta atrás:** `blocks-v1` sin comprobación no se publica.

**N4. Piloto solo de v1** (Claude, revisa Astra)
- **Contenido:** variante completa `blocks-v1` (formato más comprobación) frente a `html-v1`, con
  los mismos datos y lectores y auditor nuevos. El resultado no se atribuye solo al formato.
- **Termina cuando:** se cumple la regla preregistrada. Como mínimo, no perder lectura ni
  señales; también se miden la exactitud y las pérdidas.
- **Vuelta atrás:** se queda `html-v1`.

**N5. Ensayo completo frente a legacy** (Claude y Astra)
- **Contenido:** 24 informes con la regla preregistrada y la política vigente del ledger.
- **Termina cuando:** se cumple la regla. Solo entonces se propone v1 por defecto.
- **Vuelta atrás:** legacy sigue por defecto.

**Notas:**
- N1 y N2 van en paralelo solo cuando N0 haya fijado la interfaz y los dueños de archivos.
- N3, N4 y N5 preregistran la muestra, los denominadores, las reglas, las pérdidas y el
  presupuesto.
- **Gasto:** el camino nuevo todavía no tiene medición, así que no se dan cifras. Cada
  preregistro fija su presupuesto y el dueño lo autoriza. Como referencia, un informe v1 costó en
  F5 entre 0,06 y 0,07 USD de media. La auditoría con Opus de F5 no es coste de API de este
  comprobador.

## 8. Riesgos

- **Que v1 pierda calidad al cambiar de formato.** Es el riesgo principal; lo mide N4. Se mitiga
  no exigiendo estructura y dando ayuda de validación durante la ejecución.
- **Que el comprobador se equivoque.** Una falsa alarma pone un aviso sobre una cifra correcta, y
  un error no detectado da falsa tranquilidad. Se mide en N3 con datos retenidos y nunca se
  presenta como verificación (P5).
- **Más tiempo y gasto por informe** por la comprobación y la posible corrección, siempre dentro
  del mismo techo P4. Se mide en N3 y N4.
- **Ensayos incompletos.** Con la política vigente del ledger, una llamada incierta detiene el
  ensayo, como en F5. Este plan no la cambia.
- **Complejidad del ciclo durable** de §5. Es la parte más delicada; se cubre con las pruebas de
  N3.
- **Tipos de gráfico sin cubrir.** Se ven como tabla; el registro dirá cuáles añadir.

## 9. Decisiones del dueño

- **D1. Qué hacer con una discrepancia que sigue tras la corrección:** presentar el informe con
  un aviso visible junto a la cifra (recomendado), o no presentar el informe. Ocultar la
  discrepancia y presentar el informe sin aviso no es una opción.
- **D2. Tarjetas del inicio desde v1:** ahora el inicio solo muestra acceso y estado (P7). ¿Se
  activan con los bloques `cifra`?
- **D3. Legacy a 16.384 tokens** de salida en N5, como en la instalación del dueño.
- **D4. Autorización por fases** del código y del gasto de §7.

## 10. Lo que no cambia

- Legacy sigue por defecto hasta que N5 pase. Aun así, el cambio no se fusiona sin el dueño.
- **La regla de parada del ledger se conserva tal como está.** Este plan no la cambia ni la
  esquiva.
- Nada específico de Albor, Bruma, el herbolario o la clínica en el producto; los oráculos no
  llegan a los agentes.
- Nunca «Revisado» ni marca de verificado en v1 (P5).
- Sin envío a GitHub ni fusión con master sin petición expresa.
