# M5: piloto nativo frente a HTML. Borrador de preregistro

**Estado: borrador.** No autoriza iniciar el lote. Claude revisa este documento;
solo se congela después de cerrar M3 y superar M4, antes de inicializar M5 y antes
de observar sus informes. La implementación del análisis debe probarse con
fixtures sintéticos antes de lanzar. No se adapta ninguna regla al resultado.

## Pregunta y alcance

¿La variante nativa completa de v1 alcanza la calidad, presentación y coste del
HTML, con los cambios de M1–M3? Se compara formato, encargo y comprobación juntos;
no se atribuye una diferencia exclusivamente al formato. Las capturas estáticas
no acreditan la interactividad; esta se valida mediante pruebas de componentes.

La autorización del dueño permite el plan M dentro del techo conjunto de 15 USD
para N3–N5 y M. M5 tiene un ledger nuevo de 5 USD. N4 y el smoke consumieron
0,796747250 USD cobrados de catálogo. Los demás gastos posteriores, si los hay,
se suman antes de congelar; no se liberan reservas inciertas para financiar M5.
Legacy sigue por defecto. Ni un resultado favorable cambia el valor por defecto
ni autoriza push o merge a master.

## Brazos e intentos

| Campo | HTML | Nativo |
|---|---|---|
| Ruta | Workspace → job → motor → recepción | La misma ruta |
| Selección | `engine_kind=opencode`, formato HTML | `engine_kind=opencode`, `engine_format=blocks` |
| Modelo y runtime | `gpt-6-luna`, low, imagen congelada | Iguales |
| Contenido | Encargo HTML y entrega `informe.html` | Encargo blocks-brief-2 y entrega `informe.json` |
| Presentación | Derivado raster aislado, nunca HTML del agente en el host | Proyección nativa y componentes web de M3 |
| Comprobador | No | M2, ciclo N3, una sola corrección o reparación |
| Preguntas | Desactivadas | Desactivadas |

Dos negocios sintéticos de F5, uno de ventas y otro de observaciones no
monetarias; cinco repeticiones y dos brazos: **20 intentos, 10 parejas**. Estos
datos ya se usaron en desarrollo y N4; no son una validación sobre negocios
nuevos. El oráculo sigue fuera de los inputs del escritor y del comprobador.

Cada intento tiene negocio, memoria y run propios. La inicialización fija los
mismos CSV, descripción, objetivo y definiciones para ambos brazos. El panorama
solo aparece cuando la ruta de producto lo produce. Cada intento cuenta desde
su `started.json`, incluyendo fallos del agente, exportación, runtime o ejecutor.
No se reemplaza ningún informe ni se vuelve a generar el contenido después.

El orden por pareja se equilibra y se fija antes de empezar: cinco parejas HTML
primero y cinco nativo primero. Se alternan los negocios y se ejecuta un único
job globalmente. Se sellan el spec, el orden, los hashes de los CSV y el oráculo.
El orden A/B de los lectores también se equilibra y se sella por rol antes de
leer los resultados; no se comunica el brazo.

## Ledger y detenciones

- Nuevo ledger: `scope_uncertainty=true`, `explicit_http_rejections=true`, versión
  `SCOPED_REJECTION_VERSION` del código congelado.
- Tope del lote: 5.000.000 micro-USD; por ámbito: 1.000.000 micro-USD. P4 por run:
  1.000.000 micro-USD. No se amplían estos topes durante el lote.
- Cuotas del ámbito: entrada 40.000.000 tokens, salida 1.000.000, 400 llamadas,
  3.600 s. El motor conserva sus cuotas y tiempo de actividad propios.
- Cada envío reserva MAX_INPUT y MAX_OUTPUT: 0,3585 USD. Uso conocido liquida el
  importe conservador de catálogo; un rechazo HTTP explícito conserva la reserva.
- Una llamada incierta conserva la reserva y detiene solo su ámbito. La segunda
  llamada incierta, aunque sea del mismo ámbito, detiene todo el ledger.
  Modelo/tier incompatible o uso fuera del sobre detienen globalmente a la primera.
- Un intento detenido es pérdida y no se reenvía. Se sigue con el siguiente solo
  mientras el ledger global permita enviar. Una continuación de un job en cola
  sigue el mismo intento, presupuesto, sesión y archivos; no crea un análisis nuevo.
- Ante una parada global o techo que impida terminar, no se reabre el ledger ni se
  crea otro para terminar este lote. Los códigos sin iniciar son `not_run`, no
  pérdidas. El veredicto queda incompleto.

Se publican todos los intentos, causa y fuente de coste. Los importes cobrados a
reserva se separan del uso efectivamente conocido; no son facturas. Una fuente de
coste desconocida no vale cero. El mapa código → job → run → ámbito se conserva,
junto con ambos ledgers, P4 y lote, sin doble sumar el mismo envío.

## Material de presentación

Se congela una sola versión del frontend, proyector, política HTML y renderizador
antes de capturar. Las capturas se hacen desde las vistas web del producto, en
el mismo ancho de 1.440 píxeles, escala 1, tipografía disponible y zoom 100 %.
Serie completa visible, tablas en su estado inicial y detalles de comprobación
cerrados; las discrepancias y la comprobación incompleta siguen visibles (D1).

Protocolo probado en M4: página completa a 1.440 píxeles de ancho, cortada en
tramos consecutivos de 1.500 píxeles de alto (el último puede ser menor), sin
reducir escala. En ambos brazos se ocultan la barra lateral, el compositor y los
avisos de la copia local; no los avisos del informe. El marco de la instantánea
HTML se amplía a la altura de todas sus páginas. Las tablas permanecen en su
estado inicial: las de más de ocho filas están plegadas, como las vería el dueño.
No se fuerza un número de capturas con relleno blanco ni se eligen tramos por
calidad. Los cortes cubren toda la página y conservan su orden.

El límite se fija en **16 imágenes por pareja**, antes del lote. Si el contenido
completo excede ese límite, se conserva entero, sin truncarlo ni componerlo a
menor escala; la lectura de esa pareja queda sin acreditar y el veredicto es
incompleto. Se conserva la entrega: no se reemplaza el informe. El anexo fija los
scripts y hashes de la captura, y la altura y el número de cortes de cada vista.

El lector recibe solo las capturas web completas de A y B y la pregunta
congelada. El auditor recibe CSV y el texto canónico sin el estado del comprobador,
además de una vista equivalente sin avisos del comprobador, para no usar esos
avisos como respuesta. El juez recibe ese informe y el oráculo. Las imágenes sin
avisos no se usan para juzgar apariencia; el lector ve lo que vería el dueño.

Los kits y el mapa de brazos están separados. Se sellan los materiales completos
antes de abrir evaluadores, y sus resultados antes de desvelar los brazos.
Ningún evaluador recibe recibos de coste, resultados de otro brazo, borradores
anteriores ni explicaciones del autor.

## Evaluación única

Cada informe entregado tiene una pasada de auditor, agrupador y juez en sesiones
Opus nuevas, sin contexto de construcción. Cada pareja completa tiene un lector
como dueño y otro como asesor en sesiones nuevas: hasta 20 decisiones modelo.
No son clientes humanos. Se conserva el prompt, material, salida y hash por rol.

El auditor cuenta afirmaciones calculables y errores menores, materiales y
críticos, en prioridades y resto por separado. El agrupador conserva críticos
como subconjunto de materiales y deduplica con la gravedad máxima; cada índice
queda cubierto una sola vez. El juez puntúa las señales S1–S5 (0–2 cada una,
total 0–10) y publica el señuelo S6 por separado.

No se repite una evaluación para cambiar un juicio. Una respuesta malformada,
ausente o estructuralmente inválida queda como falta de evaluación y no se
imputa como cero. No hay selección de la mejor salida de varios evaluadores.
Un verificador estructural válido no demuestra verdad matemática ni cobertura
completa del ensayo.

### Lectura con informes perdidos

El denominador es fijo: 20 posiciones (10 parejas × 2 roles). Cuando ambos
informes se entregan, se usa la elección A/B/empate (1/0/0,5 para nativo). Cuando
solo uno se entrega, gana ese brazo automáticamente; cuando ninguno se entrega,
son 0,5 puntos por posición. Estas posiciones se publican como **resultado por
entrega**, separado de las opiniones de sesiones lectoras. Un `not_run`, un
material sin captura completa o una lectura faltante deja (c) sin acreditar.

### Comprobador

El cruce mecánico se fija antes del lote: un item final debe estar localizado,
ser `confirmed` o `discrepancy`, y su cita debe corresponder inequívocamente con
una afirmación calculable de una única prioridad de la revisión publicada. Se
usan cita literal y solape por subcadena; lo ambiguo se cuenta como no examinado.
Coverage, `unverifiable`, `unknown` e `incomplete` no son confirmaciones ni
alarmas sobre una cifra. Se cuentan todos los items finales, sin elegir el inicial
cuando convenga. Una `discrepancy` sobre una cifra que el auditor considera
correcta es falsa alarma; una confirmación de esa cifra es negativo correcto.

Se publican denominadores por negocio y en total: correctas examinadas,
negativos correctos, falsas alarmas, errores examinados/detectados y no
examinadas. Las confirmaciones del comprobador no son verdad independiente. El
auditor es un modelo y no una certificación. No se usa la herramienta de errores
sembrados deshabilitada como evidencia de validación.

## Regla congelada propuesta (a–f)

| Condición | Cálculo |
|---|---|
| (a) Entregas | Pérdidas nativas ≤ pérdidas HTML + 1, sobre los 20 intentos. Todas cuentan; las paradas se desglosan por causa, sin excluirlas. |
| (b) Exactitud | Cero críticos nativos en todos los informes entregados, aunque tengan aviso. En cada negocio, media de materiales distintos por informe nativo entregado ≤ la de HTML. Se publican totales y n; sin entregas o auditorías completas, no se acredita. |
| (c) Lectura | Nativo ≥10 puntos de 20 posiciones fijas. Separa elecciones lectoras, empates y resultados automáticos por entrega. ≥12 es el objetivo de mejora. |
| (d) Hallazgos | En cada negocio, media de S1–S5 por informe nativo entregado ≥ media HTML − 0,5. No se calcula una media parcial si faltan jueces; sin entregas, no se acredita. |
| (e) Coste | En cada negocio, media del coste conservador cobrado por intento nativo iniciado ≤2× media HTML. Incluye pérdidas y reservas inciertas y publica sus n. Reservas pendientes o fuentes desconocidas dejan la condición sin acreditar. Los topes del lote y de run siguen exigidos. |
| (f) Comprobador | Cero falsas alarmas en las cifras correctas examinadas, con denominador >0 en cada negocio. Denominadores vacíos o auditorías faltantes dejan la condición sin acreditar. Se publica la cobertura; no se concluye sensibilidad total con esos negativos. |

Todas las condiciones toman True, False o None. Se publican además tasas de
exactitud y errores por informe, críticas avisadas/no avisadas, coste por entrega
y latencia con denominadores, como resultados descriptivos que no deciden.

**Veredicto:**
- **Incompleto:** faltan intentos, material o evaluaciones necesarios para decidir.
  Se publican las condiciones conocidas; no se llama «mejor» ni «no peor».
- **Mejor:** a–f son True y (c) ≥12/20.
- **No peor:** a–f son True y (c) está entre 10 y 11,5 puntos, por los empates.
- **No pasa:** el lote y evaluaciones están completos y alguna condición es False.
- Un denominador vacío que impida decidir no se convierte en True por ausencia de errores; deja el veredicto incompleto.

Solo «mejor» abre M6, con preregistro y gasto propios dentro del saldo conjunto.
Los 20 intentos, incluso los fallidos, permanecen en el registro público agregado.

## Analizador preparado antes del lote

`scripts/f5/m5_analyze.py KEY RESULTS OUT` aplica esta regla. Exige 20 códigos
únicos y las diez parejas, valida los esquemas de auditor/agrupador/juez/lector,
y lee los ledgers con SQLite `mode=ro` (la recuperación de un run de un intento
caído usa una consulta PostgreSQL de solo lectura). Comprueba un único ledger
conjunto de 5 USD y el ledger P4 de cada run; no suma P4 otra vez al coste. Los
importes se comparan en nano-USD enteros. `uncertain` y `rejected` son cobros
terminales a reserva, publicados por separado; `reserved` permanece pendiente.
Un coste desconocido conserva, si existe, solo su cota inferior conocida. Un
sobre invalidado por modelo/tier o uso fuera de rango no acredita el coste
aunque la reserva siga cobrada; se distingue de la incertidumbre acotada por
`billing` y la parada de ámbito registrada.

La verificación de los sellos de kits y resultados es un paso previo separado;
el analizador no convierte un sello válido en prueba de cobertura o exactitud.
Las métricas del cruce con el comprobador cuentan afirmaciones del auditor;
los materiales y críticos distintos se cuentan desde los grupos, conservando
ambos denominadores. Si falta un requisito o alguna condición queda en None,
el veredicto es incompleto aunque se publiquen otras condiciones True o False.

Validación previa a M5: **23 fixtures de lotes completos**, sin API, cubren las
pérdidas, intentos sin iniciar, entrega única y doble pérdida, empates y umbrales,
críticos avisados, medias por negocio, auditorías y jueces ausentes, citas
ambiguas, denominadores vacíos, falsas alarmas, reservas inciertas y pendientes,
rechazos, fuentes desconocidas, P4, topes y esquemas inválidos. Con los tests
existentes de N4, F5 y verificación estructural: **54 pruebas OK**. Esta validación
acredita la aplicación de la regla a fixtures, no la calidad de los modelos.

## Anexo de congelación (pendiente)

Antes de iniciar: commit exacto y árbol limpio del producto/runner/análisis,
hashes de ambos prompts y perfiles, imagen y versión de OpenCode, proyector y
política/renderer HTML, spec y orden, CSV/oráculo, ledger y protocolo de capturas,
prompts de todos los evaluadores, revisión de Claude y fixtures del analizador.
El anexo fija también gasto acumulado y saldo antes de asignar los 5 USD.

Después: hashes y sello de kits, hashes y sello de resultados antes de desvelar,
lista completa de los 20 códigos, resultado de verificación estructural, tablas
a–f con denominadores, veredicto y límites. Cualquier desviación se declara con
hora y alcance; no se presenta como el preregistro original sin cambios.
