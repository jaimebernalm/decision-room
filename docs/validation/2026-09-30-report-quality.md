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
Referencias independientes adicionales por SKU/categoría, precios y notas de crédito
extienden el oráculo sin sobrescribirlo ni entrar en el contexto del producto.
41 pruebas del instrumento, referencias y conservación de intentos pasan.

Pendiente: matriz base/nueva congelada, tres casos (Bruma descubrir, WWI descubrir,
WWI organizar), dos repeticiones por versión: doce intentos. Mismos archivos,
contextos, objetivos, modelo, razonamiento y presupuestos. Oráculos CSV/Decimal
separados de los agentes, rúbrica versión 2 idéntica para ambas versiones y revisión
independiente del hash final. Conservar fallos en el denominador, desconocidos,
recursos y límites; no sustituir silenciosamente intentos fallidos.

La aceptación de utilidad sigue pendiente. La comprobación conjunta final requiere
que el propietario reconozca la prioridad y el siguiente paso en una entrega real.
No se atribuye ese juicio a pruebas automatizadas. Consulta web posterior 3.95
fuera de este alcance.
