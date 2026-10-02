# 3.9 — Calidad de la entrega

## Alcance implementado

El [plan](../technical/report-quality-plan.md) amplía la autonomía del principal
para investigar señales dentro del objetivo y elegir representaciones soportadas.
La dirección de negocio orienta prioridades; el revisor audita el encargo y las
decisiones sobre el borrador vigente. La existencia de nuevos campos no demuestra
por sí sola una mejora de utilidad.

- Orientación con segmento, periodo, señal, evidencia, prioridad, comprobación,
  utilidad para decidir, condiciones y límites. Cobertura del propietario separada
  de ramas internas; se conservan desconocidos, respuestas parciales e históricos.
- Seguimientos focales con origen, periodo y comparación, sin menú obligatorio de
  desgloses. Instrucciones de conciliación y denominadores netos/brutos.
- Líneas temporales simples/múltiples, barras y tablas; periodos y coordenadas
  explícitos, huecos sin ceros inventados, cifras exactas y escala declarada.
- Primera lectura con comprobaciones visibles, series activables, tooltip común,
  selección por teclado/táctil y enlaces a hallazgos o desgloses aprobados.
  Valores adicionales guardados forman parte de la huella de aprobación.
- HTML, PDF, informe web, inicio y chat conservan orientación, evidencia y estado
  parcial. Interactuar no ejecuta cálculos ni llama al modelo.

## Comprobaciones técnicas

Los incrementos incluyen pruebas de referencias obsoletas, orientación sin respaldo,
entregable omitido, rechazo de reacciones por el revisor, porcentajes incorrectos,
grano temporal falso, categorías arbitrarias, periodos/celdas ausentes, recuperación,
reparación y replay sin duplicar ejecuciones. Los fixtures guionizados comprueban
protocolo e integridad; no son resultados de autonomía o calidad semántica.

La primera regresión completa detectó tres expectativas desactualizadas:
dos contaban ramas como cobertura del propietario y una búsqueda textual heredaba
búsqueda semántica del entorno. Se corrigieron los fixtures y el aislamiento de
esa prueba. Una expectativa web también ocultaba la siguiente comprobación hasta
desplegar el hallazgo. La reparación elimina notas de cobertura antiguas antes de
añadir la vigente. La inspección del esquema del proveedor detectó y corrigió
campos opcionales internos que el protocolo estricto exige declarar explícitamente.

- Regresión completa: 520 pruebas Python y 117 web pasan; build y lint pasan, con avisos existentes de lint y tamaño
  del bundle. 47 comprobaciones dirigidas y 29 de esquemas/revisión pasan después
  de los ajustes; instrumento independiente conserva rúbrica histórica y añade
  versión 2 para decisiones, representación e incertidumbre de cada fuente.
  Después del ajuste final del esquema, 41 pruebas de proveedor/evaluador pasan.
- QA visual local con fixture sintético identificado: escritorio claro, móvil
  oscuro a 390 px, selección/tabla y navegación al hallazgo. Sin desbordamiento
  horizontal; ejes ajustados en móvil. PDF de dos páginas sin pérdida de valores.
  Son pruebas del renderer, no informes publicados. Artefactos privados en
  `.local/ui-quality/`, excluidos de Git.
- En la primera entrega real de Bruma se comprobó también la línea mensual y
  selección exacta de julio. Ajustado el margen de la línea simple para conservar
  completo el marcador del máximo en el borde; las líneas múltiples ya lo tenían.
  Pruebas web dirigidas y build pasan. Este ajuste visual posterior no modifica
  las copias de producto congeladas para la comparación ni sus informes.
- El esquema de gráficos referenciados hereda el grano de la evidencia guardada;
  para calendarios agrupados se declara en `encoding`. Evita ofrecer al modelo
  un override incompatible que luego exigiría reparación. 24 pruebas de esquemas,
  referencias y entrega temporal pasan tras este ajuste.
- La matriz detectó dos fallos de revisión por incoherencia entre la auditoría de
  cobertura y el estado parcial/no disponible del borrador. El esquema de
  `OwnerUtility` ofrece ahora índices, referencias y estados compatibles con el
  informe vigente, conservando `fail` para el desacuerdo independiente. Un estado
  inexacto debe corregirse en el borrador, no aprobarse por eludir la validación.
- Las líneas agrupadas admiten hasta 366 coordenadas, igual que el límite temporal;
  barras/tablas mantienen 36 puntos. Una prueba de cinco series y 24 meses conserva
  los 120 valores en API, HTML y PDF y rechaza usarlos en una barra de 120 puntos.
  56 pruebas de esquemas, revisión, series y exportaciones pasan; revisión v41.
- Regresión final después de esas correcciones: **531 pruebas Python pasan**.
  QA web adicional con cinco series y 24 meses: selección de diciembre, ocultación
  de una serie y los cinco valores exactos conservados. Artefacto sintético
  identificado, separado del informe real de Bruma y sin llamadas al modelo.

## Comparación y aceptación

Las primeras cinco entregas aprobadas de la matriz (cuatro Bruma y WWI descubrir
base, repetición 1) tienen todos sus valores entregados cotejados con CSV/Decimal.
La revisión independiente detecta que las siguientes comprobaciones y reacciones
aún son imprecisas. Algunos desgloses mejoran; tener campos de orientación o dos
condiciones redactadas no basta para aceptar utilidad.

Se reforzaron las instrucciones compartidas para exigir un hecho observable y un
contraste ejecutable, con una operación, ajuste, investigación o revisión concreta
según el resultado. La cautela y «podría cambiar la interpretación» no completan
este componente. No se fuerzan actuaciones comerciales ni causas: conservar una
entrega parcial si falta el dato material, y calcular primero lo que permiten los
archivos. Prompts de revisión v39, investigación v31 y planificador v5; 70 pruebas
de contratos, revisión, planificador, rondas y esquemas pasan. La matriz congelada
continúa con las versiones originales; el ajuste necesita comprobación adicional
identificada por separado, sin sustituir resultados desfavorables.

La primera repetición nueva de WWI descubrir también muestra una ampliación del
encargo: el brief convierte la selección de pocos hallazgos en listados completos
y porcentajes por categoría, y el revisor exige esas vistas como si el propietario
las hubiera pedido. Se refuerza el contraste del brief y la revisión con el texto
original: métodos y vistas opcionales no pasan a ser requisitos del cliente por
ser calculables. En organización se mantienen todas las vistas solicitadas.
Prompts posteriores: revisión v40, investigación v32 y planificador v6. Este ajuste
también necesita la evaluación adicional; no modifica la comparación congelada.
79 pruebas de contratos, revisión, planificador y rondas pasan tras el cambio.

El instrumento conserva sus controles históricos para la rúbrica anterior y las
respuestas/dashboard. En descubrir con rúbrica 2, cobertura y comparabilidad se
juzgan contra el encargo original por revisión independiente, en vez de exigir
una lista fija de totales globales: una comparación focal por categoría/producto
puede ser una respuesta válida. Todas sus cifras siguen necesitando vinculaciones
exhaustivas al oráculo. El cambio se aplica por igual a ambas versiones, con hash
del evaluador; no cambia fuentes, oráculos ni el criterio sobre reacciones vagas.
La matriz exige la misma versión de rúbrica en cada evaluación.
El ejecutor `evaluation/report_quality_runner.py` congela revisiones Git, fuentes,
modelo y oráculos, y separa bases y almacenamiento. Conserva los intentos iniciados
y sus fallos; una reserva todavía sin actividad puede continuar con la misma clave.
Permite un lote adicional identificado que reutiliza las seis bases históricas y
ejecuta seis nuevas entregas, una vez terminado el lote original. No representa
esa continuación como una alternancia nueva ni cuenta dos veces sus bases.
Referencias independientes adicionales por SKU/categoría/comprador, precios y notas de crédito
extienden el oráculo sin sobrescribirlo ni entrar en el contexto del producto.
La concentración usa cambios observados y denominadores firmados/absolutos
separados; no crea niveles anuales para grupos ausentes.
41 pruebas del instrumento, referencias y conservación de intentos pasan.

### Matriz original cerrada

Copias congeladas: base `2e10028` (mismo producto que `5af6cb7`) y nueva
`ed92625`. Tres casos y dos repeticiones por versión, con orden alternado:
doce intentos únicos. Mismos archivos, objetivos, contexto, modelo `gpt-6-luna`,
razonamiento `low`, límite de salida 16.384 y presupuestos `quality_first`, con
planificador activo y tres trabajadores máximos en ambas versiones. Los oráculos
CSV/Decimal no entran en el contexto de los agentes. Rúbrica 2 idéntica en ambas
versiones, vinculada al hash de cada borrador final y al del evaluador.

La auditoría semántica es de desarrollo, no ciega ni una valoración del propietario;
los cálculos de referencia son independientes de los programas de los analistas.
No se exige una prioridad literal, un gráfico de líneas ni el inventario ampliado
por el planificador. Aprobación del producto y aceptación de desarrollo son
resultados distintos.

| Caso | Rep. | Versión | Publicable | Aceptación | Referencias cotejadas | Segundos |
|---|---:|---|---|---|---:|---:|
| Bruma descubrir | 1 | Base | Sí | No | 47 | 278,604 |
| Bruma descubrir | 1 | Nueva | Sí | No | 34 | 194,499 |
| Bruma descubrir | 2 | Base | Sí | No | 47 | 200,475 |
| Bruma descubrir | 2 | Nueva | Sí | No | 42 | 191,204 |
| WWI descubrir | 1 | Base | Sí | No | 46 | 441,170 |
| WWI descubrir | 1 | Nueva | Sí | No | 91 | 1.151,711 |
| WWI descubrir | 2 | Base | Sí | No | 44 | 622,683 |
| WWI descubrir | 2 | Nueva | Sí | No | 20 | 314,386 |
| WWI organizar | 1 | Base | Sí | Sí | 117 | 209,494 |
| WWI organizar | 1 | Nueva | No | No | 64 del borrador | 285,667 |
| WWI organizar | 2 | Nueva | No | No | 111 del borrador | 270,284 |
| WWI organizar | 2 | Base | No | No | Sin informe | 11,291 |

Resultado: base 5/6 publicables y 1/6 aceptados; nueva 4/6 publicables y 0/6
aceptados. Los nueve informes publicables conservan **488 referencias correctas**,
incluidos identificadores/fechas cuando corresponden. También se cotejaron 175
referencias de los dos borradores nuevos no publicados: aritmética correcta no
equivale a cobertura, citas completas o aprobación. Los tres fallos permanecen
en el denominador.

- En Bruma, la primera nueva profundiza y prioriza mejor que su primera base;
  la segunda base también profundiza. Ambas nuevas se centran en señales válidas
  distintas de la prueba manual. Ninguna concreta suficientemente la reacción
  posterior; no se acepta por tener campos o condiciones.
- En WWI descubrir, la primera nueva desglosa productos del segmento y compara
  cambios absolutos/relativos, pero amplía el encargo y conserva reacciones vagas.
  La segunda remite a comprobar después clientes, cantidades o precios ya
  disponibles, sin localizar la señal con esos cálculos. La segunda base sí
  caracteriza compradores/concentración, pero tampoco cierra una reacción concreta.
- En WWI organizar, la primera base cubre las tres medidas anual/mensual/categoría.
  Las dos nuevas fallan tras cuatro reparaciones de auditoría por estados/referencias
  incompatibles. El primer borrador además omite dos series mensuales completas;
  el segundo tiene ocho importes de margen por categoría sin cita en su claim.
  Son defectos de entrega, no cifras numéricamente erróneas. La segunda base termina
  por HTTP 429 durante planificación, tras tres rechazos de transporte; no genera
  informe y no permite juzgar calidad semántica.

**La matriz original no demuestra una mejora consistente de utilidad ni conserva
la fiabilidad de organización.** No se sustituye por un informe favorable ni se
atribuyen sus resultados a las correcciones posteriores.

### Continuación y bloqueo del proveedor

Después de corregir instrucciones de reacción/alcance, coordenadas y esquema de
auditoría, se congeló `4499f15` para seis intentos nuevos: dos de cada caso. El lote
reutiliza todas las bases históricas y no es una nueva alternancia. Los doce
originales siguen íntegros: **18 intentos únicos**, no 24.

Los seis adicionales fallan en planificación con HTTP 429, antes de generar
informes. Un único diagnóstico mínimo identificado fuera de la matriz confirma
`insufficient_quota` / `credit_balance_exhausted`. Su respuesta tampoco aporta
uso. No se habilitó otra cuenta/modelo ni se sustituyó un intento. El último ajuste
queda verificado técnicamente y **sin validación semántica con proveedor**.

### Recursos y continuidad

Los 18 intentos contienen 325 llamadas lógicas registradas y 14 ejecuciones fallidas
conservadas. Uso conocido: 12.441.853 tokens de entrada y 485.122 de salida; diez
intentos tienen uso incompleto/desconocido, incluidos rechazos. Son cantidades
conocidas, no el consumo total ni cero para los rechazos. El diagnóstico de una
solicitud queda separado de esos recursos. Sin uso completo y tarifas declaradas
no se estima coste. Los tiempos de la tabla son descriptivos; los fallos y esta
muestra pequeña no permiten una conclusión causal de velocidad o generalización.

Evidencias locales ignoradas: `.local/report-quality-evaluation/` y
`.local/report-quality-followup/`, con manifiestos, estados, revisiones, evaluaciones,
recursos y exportaciones por intento; `.local/provider-diagnostic.json` contiene
solo el diagnóstico acotado. Fuentes, credenciales y rutas de máquina no se publican.
Los manifests y oráculos congelados se conservan sin cambios de resultados.

Para continuar: restablecer saldo de API, conservar el modelo/configuración
comparables y crear otro lote identificado desde la matriz original con la revisión
verificada. Registrar los nuevos intentos además de los 18 existentes. Revisar
independientemente sus informes y después realizar la prueba conjunta con el dueño;
no dar por aceptada la corrección mediante los fixtures de protocolo.

La aceptación de utilidad sigue abierta y la validación real del ajuste está
bloqueada por saldo de API. La comprobación conjunta final requiere
que el propietario reconozca la prioridad y el siguiente paso en una entrega real.
No se atribuye ese juicio a pruebas automatizadas. Consulta web posterior 3.95
fuera de este alcance.

## Continuidad del 1 de octubre

El proveedor vuelve a responder después de restablecer saldo. Los resultados de
este documento se conservan como historial, incluidos los intentos fallidos.
La [evaluación reanudada](2026-10-01-report-quality.md) registra correcciones,
pruebas y nuevos intentos separados; no sustituye esta comparación.
