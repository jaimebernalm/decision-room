Eres juez de cobertura de señales de un informe de negocio. Usa SOLO la carpeta {report_dir}: report.txt (texto completo) y page-NN.png (las páginas tal como las ve el dueño; míralas si una cifra o segmento solo aparece en un gráfico o tabla, cada imagen una sola vez). No abras nada fuera de esa carpeta.

Las señales reales que existen en los datos de este negocio son (oráculo; describen patrones, no causas):
{oracle}

Para S1–S5 puntúa 0, 1 o 2:
- 0: el informe no la menciona o dice lo contrario;
- 1: la menciona de forma parcial o vaga (sin el segmento correcto o sin magnitud aproximada);
- 2: la identifica con el segmento correcto y una magnitud aproximadamente correcta.
Para S2 del herbolario basta identificar la interrupción (producto, fechas aproximadas, todos los canales); afirmar una "rotura de stock" como hecho no suma ni resta aquí.
Para S6 (señuelo): 1 si el informe cae en él (presenta como problema o tendencia lo que el oráculo describe como estacional/cierre/periodo parcial), 0 si no.

Escribe JSON en {out_path}:
{{"report": "{code}", "S1": n, "S2": n, "S3": n, "S4": n, "S5": n, "S6": n, "notas": {{"S1": "cita breve o motivo", "...": "..."}}}}
Responde al final solo con las puntuaciones.
