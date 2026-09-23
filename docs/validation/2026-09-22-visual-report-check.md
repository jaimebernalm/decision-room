# Informe visual con series y cobertura de preguntas

## Alcance implementado

Mejora de la entrega 2. Python puede guardar series con unidad, granularidad,
etiquetas, valores y operación de origen. El informe referencia una serie completa
sin copiar cada punto. La web presenta tarjetas de cifras, gráficos con tablas
desplegables, hallazgos y evidencia. El registro interno también muestra las series.
No incorpora filtros que recalculen el análisis.

El borrador debe vincular todas las investigaciones listas con sus hallazgos o
explicar una limitación real. El revisor recibe instrucciones explícitas de evaluar
la respuesta a la pregunta y exigir cálculos o visualizaciones pendientes cuando
los datos permiten realizarlos. Esa evaluación semántica sigue siendo del modelo;
el contrato comprueba cobertura estructural, no demuestra que una respuesta sea útil.

## Datos de la prueba

Se utiliza Microsoft Wide World Importers v1.0, muestra ficticia pública bajo la
licencia conservada en `data/wide-world-importers/LICENSE.txt`. Fuente y descarga:
[release oficial](https://github.com/microsoft/sql-server-samples/releases/tag/wide-world-importers-v1.0).

`scripts/datasets/prepare_visual_case.py` genera un extracto de todas las líneas de
facturas no rectificativas de julio a diciembre de 2015, unido con fecha y nombre
del producto. No selecciona datos de contacto ni identificadores de clientes.

- 36.331 filas, 219 productos, 11.264 facturas, 158 fechas registradas.
- CSV de 2.962.316 bytes; seis meses completos seleccionados por fecha.
- Importe de línea sin impuestos = `ExtendedPrice - TaxAmount`. No es precio unitario.
- No se atribuye moneda ni se convierten fechas ausentes en ventas cero.
- Datos, referencias y hashes se generan en `.local/visual-case`, fuera de Git.

La referencia independiente usa SQLite y céntimos enteros sobre el CSV guardado.
La generación usa Decimal y reconcilia cada línea con cantidad por precio unitario.
Las referencias no se dan al agente. Solo recibe el CSV, sus definiciones y la
pregunta sobre evolución mensual y principales productos por importe.

## Ejecución real con GPT-6 Luna

OpenAI, razonamiento `low`, mismo presupuesto del recorrido anterior. Sin editar
el Python generado, sus resultados ni la narrativa del informe.

| Fase | Llamadas | Tiempo de modelo |
|---|---:|---:|
| Planificación | 1 | 9,88 s |
| Investigación | 4 | 28,48 s |
| Analista del informe | 2 | 22,96 s |
| Revisor | 2 | 9,44 s |
| Total | 9 | 70,76 s |

Tiempo de reloj: **72,82 segundos**. Dos ejecuciones Python correctas: **0,87 s**
en total. No hubo errores HTTP ni ejecuciones fallidas. No necesitó preguntas,
porque se proporcionaron previamente las definiciones materiales del extracto.

Recorrido de revisión: `submit → revise → submit → approve`.
El revisor pidió respaldar la afirmación de máximo/mínimo mensual con los seis
importes, no solo con los dos extremos. El analista citó los seis valores ya
calculados y conservó el gráfico mensual. No fue necesaria otra ejecución Python.

Resultado: tres tarjetas, seis barras mensuales, diez barras de productos,
dos hallazgos, límites del extracto y evidencia desplegable.

## Comprobación independiente

Los 16 valores de los gráficos, sus etiquetas/orden y las tres cifras destacadas
coinciden con las referencias. Total del semestre: **26.796.504,55**. Julio es el
mes máximo (5.155.672,00) y agosto el mínimo (3.938.163,40). El producto 215 tiene
el mayor importe (1.560.978,00), seguido del 161 (1.104.840,00).

Comando reproducible sobre la exportación privada:

```sh
.venv/bin/python scripts/datasets/prepare_visual_case.py
.venv/bin/python scripts/checks/check_visual_case.py --audit RUTA_PRIVADA/review.json
```

También se presentó al revisor real el informe pequeño anterior, deliberadamente
incompleto para su pregunta de evolución. Se añadió únicamente el nuevo campo de
cobertura para que fuera estructuralmente válido; no se alteró la sesión original.
El revisor respondió `revise` en 3,57 s y pidió guardar la serie diaria, mostrarla
y mantener los huecos como fechas ausentes. Es una prueba dirigida con borrador
controlado, separada del recorrido autónomo de 36.331 filas.

## Comprobaciones técnicas y de interfaz

- Suite completa: **135 pruebas correctas**.
- Pruebas de series inválidas, valores no finitos, etiquetas duplicadas,
  referencias ajenas/obsoletas/omitidas, unidades incompatibles y HTML escapado.
- Huella de aprobación incluye ejecuciones citadas solo por series o tarjetas.
- La cobertura incompleta impide enviar o aprobar un borrador nuevo.
- Compatibilidad de resultados y gráficos anteriores; no se añade contenido
  analítico a una aprobación antigua.
- Computer Use comprobó tarjetas, gráficos, tabla desplegable y vista estrecha.
  Se corrigió la partición de cifras grandes en las tarjetas móviles.

## Límites

Una prueba grande y una prueba dirigida no sustituyen la matriz de aceptación de
1.7. El contenido sigue siendo descriptivo y no evalúa costes ni causalidad. Las
series diarias admiten hasta 366 puntos; para periodos mayores hay que agregar.
Las barras/tablas admiten hasta 36 categorías, con selección explícita si es top-N.
El tiempo observado no garantiza la misma latencia con otros archivos o informes.
