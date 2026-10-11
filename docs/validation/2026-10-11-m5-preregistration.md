# M5: piloto nativo frente a HTML. Borrador de preregistro

**Estado: congelado** (anexo al final). Antes era un borrador que no autorizaba iniciar el lote. Claude revisa este documento;
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

## Anexo de congelación (11 de octubre de 2026)

Congelado antes de inicializar M5 y antes de ver ningún informe de M5. El lote corre desde un
worktree desacoplado en el commit de este anexo (código idéntico a `d19f96f` salvo este documento),
con la configuración local del contenedor copiada de N4. Imagen del motor: `sha256:cf6973da73ec313f00143801f38b30e3a2020488341ab7045e0339fc85921459`.

**Gasto acumulado antes de M5:** 0,905103750 USD de 15 (N4 con su smoke: 0,796747250; smoke técnico
de M5: 0,108356500). **Saldo:** 14,094896250 USD. M5 asigna 5 USD con un ledger nuevo.

**Ledger:** gpt-6-luna-standard-envelope-2026-10-11-http-rejections-1-scope-uncertainty-2; tope 5.000.000 micro-USD, por ámbito 1.000.000; cuotas por ámbito
40.000.000 tokens de entrada, 1.000.000 de salida, 400 llamadas y 3.600 s.

**Orden de ejecución** (un único job a la vez; 5 parejas con HTML primero y 5 con el nativo primero, negocios alternos):

`herbolario-1-opencode → herbolario-1-blocks → clinica-1-blocks → clinica-1-opencode → herbolario-2-blocks → herbolario-2-opencode → clinica-2-opencode → clinica-2-blocks → herbolario-3-opencode → herbolario-3-blocks → clinica-3-blocks → clinica-3-opencode → herbolario-4-blocks → herbolario-4-opencode → clinica-4-opencode → clinica-4-blocks → herbolario-5-opencode → herbolario-5-blocks → clinica-5-blocks → clinica-5-opencode`

**Lectura:** kits con `kits.py --captures --balanced --max-pair-images=16`; instrucciones con `prompts.py --quotes --web=16`.
Capturas con `web_captures.py`: modo lector para los lectores y modo auditor (sin avisos del comprobador)
para auditor y juez.

| Fichero | sha256 |
|---|---|
| `scripts/f5/m5_analyze.py` | `cfb63f2dcea8f2e9ce0b69763acef1c466ec5ca0e2453e1daced3fa20817b15b` |
| `scripts/f5/web_captures.py` | `63990a6d65c8f0c55effb89252f6428319080a06225e4af00c63491e0a94e9f4` |
| `scripts/f5/kits.py` | `07341b76d2985fdd051545de4e51e7911dc42dec6e64720b87a133ba3c931794` |
| `scripts/f5/prompts.py` | `d75da47bf359e75a439637614d8e1c6aa77fe546d364ee9e7e9d090a4f35ac20` |
| `scripts/checks/product_trial.py` | `5a8d524679264ef11775d34eca487c751e8dcbfd9cbbd8770b6ca286a8f0f570` |
| `scripts/checks/product_trial_verify.py` | `d0187d476419205c3d14c5622dd5acc1e279be45e9377e282c2b0267b35a014c` |
| `engine/opencode/prompts/informe.md` | `c91844485cfe856f2273bdfb8abd7a2452e578505c5c00670eddbf90e321a6ba` |
| `decision_room/engine/blocks.py` | `1eb22628e49e45a02aba70a1544185be611386b2610f446385fbcb913e2e2a69` |
| `decision_room/engine/brief.py` | `684d7b03ea9d7115a8653da9723d5d045d8239c72bf8dd57fd0a1d1995b0e55a` |
| `decision_room/engine/check_contract.py` | `32c6106327c511884e2bb70dc0286d91e0ef397fe0be5d26b6b0dfa0c86f07b0` |
| `decision_room/agent/api_budget.py` | `227df334421938f77f197779aabec998d28bbbb7220bf1aed035eada2955432f` |
| `decision_room/engine/proxy.py` | `5e6bdfb735c107ae19f7af3af71f31cdd5dc86b50b434b4a5ae302164d34d9a1` |
| `decision_room/chart_palette.json` | `8d46db3a7561a8ccdb2693c47d00704d7f654276b97830a668eb125b80560e68` |
| `scripts/f5/prompts/auditor.md` | `5e69788d76055c351fc9bb84456ab3b112fe95c683c65fbc06e4e0752d1e42f4` |
| `scripts/f5/prompts/auditor_quotes.md` | `aec2a95d5f14d3d350fac4b2ee50a154582b0a5995ba2f28b4173a3ab8292541` |
| `scripts/f5/prompts/grouper.md` | `c0a8b1f3be16fcb9463e6d2590e6e02be4f451ea6ebccda8b866f52c08dd1744` |
| `scripts/f5/prompts/judge.md` | `50e28212a5b55cfc1624185b50a1e83e57eab1ef66cfa039a4b37c75db27a094` |
| `scripts/f5/prompts/reader_advisor.md` | `2f3f518b94a5b8191eb03eda4ed73a4ea0434025ab69b2a525304c7c6d4e0456` |
| `scripts/f5/prompts/reader_advisor_web.md` | `f3acc3402bf638b234309381e0a121f1d68054ea6ff0b595685ffaba57ab4462` |
| `scripts/f5/prompts/reader_owner.md` | `da1b03a325ad32f58771888173aa9a50f5fd961c03d08c51f7cb8d2175f4b795` |
| `scripts/f5/prompts/reader_owner_web.md` | `f74b5b72e000361626109ec72d83d43a2b84a5fc2655f803c188daa4fa7568dd` |

| Dato | sha256 |
|---|---|
| `spec.json (privado)` | `ba61263a3e9f1a7d1fee0707b4c78206bd021808cd5b025b91459ce70c0b628e` |
| `order.txt (privado)` | `cf3d39aec65de22e652ee8ccefcccf7b36cb078cd6d0976ec0cb3c2cffa27ed0` |
| `oracle.json (privado)` | `4780fc6274f0e03d62867c71f92b56668918580dbb554b0d79f00a2b93997463` |
| `herbolario/ventas.csv` | `88ca0b155e80a1c7d061f24cbeb8c140e75e6a3dfc5966bf1f67d0a2f12c9c59` |
| `herbolario/productos.csv` | `be97db6b4682ef5201feb4d7c6533f3c522f7ecaae4ad64bf26d95d0e5694c81` |
| `herbolario/canales.csv` | `6e941a6fcfff38185fbb55003fce7cce033a267195e15630f098da4150a2e8f8` |
| `clinica/citas.csv` | `7ebd3bd66c94457b3f7632b4a1ff45ce002f72a70dc0c1e786ae13385d6e8c26` |
| `clinica/encuestas.csv` | `4219480bfa61c4e75256ed67b84127cd0fcb235a9205d762e34440619b5f9488` |
| `clinica/profesionales.csv` | `5a538408df96f9ee40c2a70f47de0957543e7b9f97e0cff59d09aae7f44feffb` |

| Valor derivado | Valor |
|---|---|
| PROJECTOR_VERSION | `bloques-proyector-4` |
| FORMAT_GUIDE | `b6c34addc58ae4af03b887c50f1843aed212507523b5e99f39a8398896ea57c3` |
| encargo nativo (native_fixed) | `07c86b6bae0c7a6f82241f5cbf3b7c7d3b25e660e0c81a6c51a5497cc58c965b` |
| PROMPT del comprobador | `44d1ae12684f3510fdc2f45bfa71dacb9b28142ac5fa61337b2af72f068bdf70` |
| ledger_version | `gpt-6-luna-standard-envelope-2026-10-11-http-rejections-1-scope-uncertainty-2` |

**Después del lote:** se publican los hashes y el sello de las capturas, los kits y las instrucciones antes
de abrir evaluadores, y el sello de resultados antes de desvelar los brazos.
