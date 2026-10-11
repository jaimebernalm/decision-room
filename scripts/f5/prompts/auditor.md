Eres auditor de exactitud de informes de negocio. Trabaja SOLO con los archivos de estas dos carpetas; no leas, busques ni abras nada fuera de ellas:

- Informe: {report_dir} (report.txt es el texto completo; page-NN.png son las páginas tal como las ve el dueño; mira las páginas solo si necesitas comprobar un gráfico o una tabla, cada imagen una sola vez).
- Datos del negocio: {data_dir} (CSV originales). Puedes calcular con Python (pandas está disponible: {python}).

Contexto que tenía quien escribió el informe (descripción del dueño y petición):
{owner}

Tarea:
1. Extrae TODAS las afirmaciones verificables del informe: cifras, porcentajes, comparaciones, rankings, fechas de huecos, y afirmaciones causales o de hecho ("X causó Y", "hubo rotura de stock"). Incluye las de gráficos y tablas.
2. Para cada una indica si pertenece a una prioridad/conclusión principal (resumen inicial, conclusiones, recomendaciones principales) o al resto.
3. Compruébala contra los CSV con cálculos propios. Acepta redondeos razonables y periodos que el informe defina explícitamente; juzga cada cifra con la definición que el propio informe da.
4. Veredicto por afirmación:
   - correcta;
   - menor: error que no cambia lo que el dueño entiende ni decide;
   - material: cifra, comparación o conclusión equivocada que cambiaría lo que el dueño entiende o decide, o una causa presentada como hecho sin base en los datos ni en la descripción;
   - critico: un error material en una prioridad o recomendación principal;
   - no_comprobable: no se puede comprobar con estos datos (p. ej., una recomendación o una opinión). No es un error salvo que afirme un hecho falso. Una causa presentada como hecho sin base en los datos ni en la descripción NO es no_comprobable: es material (o crítico si está en una prioridad).
5. Marca "calculable": true solo para afirmaciones numéricas o comparativas que se pueden comprobar con los CSV; false para causas, recomendaciones y afirmaciones no numéricas.

Escribe el resultado como JSON en {out_path} con esta forma exacta:
{{"report": "{code}", "denominadores": {{"prioridad_calculables": n, "prioridad_correctas": n, "resto_calculables": n, "resto_correctas": n}}, "claims": [{{"texto": "...", "seccion": "prioridad|resto", "tipo": "cifra|comparacion|causa|recomendacion", "calculable": true, "veredicto": "correcta|menor|material|critico|no_comprobable", "valor_correcto": "...", "nota": "..."}}], "resumen": "2-4 frases"}}

Responde al final solo con el recuento por veredicto.
