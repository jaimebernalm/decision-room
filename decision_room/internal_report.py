"""Private static HTML snapshots. Model prose is always escaped, never executable."""
import json
from html import escape



def render(data, exported_at):
    def e(value):
        return escape(str(value), quote=True)

    labels = {'approved': 'Revisado por el agente', 'waiting': 'Pendiente de una respuesta',
              'held': 'Bloqueado por comprobación independiente',
              'stale': 'Obsoleto', 'limited': 'Revisión incompleta', 'rejected': 'Rechazado',
              'withdrawn': 'Retirado', 'failed': 'Revisión interrumpida'}
    approved = data['publishable']
    label = labels.get(data['status'], 'Borrador en revisión')
    if not approved and data['status'] == 'approved':
        label = 'Aprobación no válida'
    draft = data['report']
    title = draft['title'] if draft and approved else 'Estado de la revisión'
    body = [f'<header><p class="eyebrow">DECISION ROOM · REGISTRO INTERNO</p><span class="badge {"ok" if approved else "pending"}">{e(label)}</span>',
            f'<h1>{e(title)}</h1><p class="muted">Instantánea del {e(exported_at)}</p></header>']
    if approved:
        body.append(f'<section class="summary"><h2>Resumen</h2><p>{e(draft["summary"])}</p></section>')
        for claim in draft['claims']:
            links = ' · '.join(f'<a href="#evidence-{e(ref["execution_id"])}">{e(ref["metric"])}</a>' for ref in claim['evidence'])
            body.append(f'<section><h2>{e(claim["title"])}</h2><p>{e(claim["statement"])}</p><p class="source">Evidencia: {links}</p></section>')
        body.append('<section><h2>Alcance y limitaciones</h2><ul>' + ''.join(f'<li>{e(x)}</li>' for x in draft['limitations']) + '</ul></section>')
    else:
        body.append('<section class="summary"><h2>Este informe todavía no está aprobado</h2>'
                    f'<p>{e(data.get("issue") or "La revisión no ha terminado.")}</p>'
                    '<p>Las conclusiones provisionales no se presentan como resultados revisados.</p></section>')
        for question in data['pending_questions']:
            body.append(f'<section><h2>Necesitamos tu aclaración</h2><p>{e(question["action"]["question"])}</p></section>')
    if draft:
        body.append('<details><summary>Comprobaciones automáticas</summary><ul>')
        for check in data['checks']:
            body.append(f'<li><strong>{"Correcta" if check["passed"] else "Pendiente"}</strong> · {e(check["check"])}: {e(check["detail"])}</li>')
        body.append('</ul><p>Estas comprobaciones no prueban por sí solas el significado de los datos.</p></details>')
        if draft.get('question_coverage'):
            body.append('<details><summary>Cobertura de las preguntas del análisis</summary><ul>')
            for entry in draft['question_coverage']:
                body.append(f'<li>{e(entry["investigation_key"])} · {e(entry["status"])}: {e(entry["explanation"])}</li>')
            body.append('</ul></details>')
    body.append('<section><h2>Evidencia y cálculos</h2><p class="muted">Código, métricas y operaciones guardadas. Los resultados obsoletos se conservan para explicar el recorrido.</p>')
    for observation in data['observations']:
        payload = observation['result'] or {}
        body.append(f'<details id="evidence-{e(observation["execution_id"])}"><summary>Cálculo {e(observation["execution_id"][:8])} · '
                    f'{e(observation["status"])} · {"vigente" if observation["current"] and data["status"] != "stale" else "obsoleto"}</summary>')
        body.append('<table><thead><tr><th>Métrica</th><th>Valor</th></tr></thead><tbody>')
        for key, value in payload.get('metrics', {}).items():
            body.append(f'<tr><td>{e(key)}</td><td>{e(value)}</td></tr>')
        body.append('</tbody></table><h3>Operaciones y fuentes</h3><ul>')
        for item in payload.get('evidence', []):
            body.append(f'<li>{e(item["metric"])} · {e(", ".join(item["tables"]))}: {e(item["operation"])}</li>')
        body.append('</ul>')
        for key, series in payload.get('series', {}).items():
            body.append(f'<details><summary>Serie {e(key)} · {len(series["points"])} valores · {e(series["unit"])}</summary>'
                        f'<p>{e(series["evidence"]["operation"])}</p><table><thead><tr><th>Referencia</th><th>Valor guardado</th></tr></thead><tbody>')
            body.extend(f'<tr><td>{e(p["label"])}</td><td>{e(p["value"])}</td></tr>' for p in series['points'])
            body.append('</tbody></table></details>')
        body.append('<h3>Archivos utilizados</h3><ul>')
        for alias, item in observation['inputs'].items():
            body.append(f'<li>{e(alias)} · {e(", ".join(item["original_names"]))} · {e(item["row_count"])} filas · SHA-256 {e(item["parquet_sha256"])}</li>')
        body.append(f'</ul><h3>Python guardado</h3><pre><code>{e(observation["code"])}</code></pre>')
        if observation['issue']:
            body.append(f'<p>{e(observation["issue"])}</p>')
        body.append('</details>')
    body.append('</section><details><summary>Contexto aportado y aclaraciones</summary>')
    body.append(f'<p>{e(data.get("owner_context", ""))}</p><p class="muted">Las aclaraciones posteriores actualizan el contexto original.</p>')
    for answer in data['owner_answers']:
        body.append(f'<article><p><strong>{e(answer["question"].get("text", "Aclaración"))}</strong></p>'
                    f'<p>{e(answer["text"])} · {e(answer["disposition"])}</p></article>')
    body.append('</details><details><summary>Conversación entre analista, revisor y propietario</summary>')
    for event in data['conversation']:
        role = 'Analista' if event['role'] == 'analyst' else 'Revisor'
        body.append(f'<article><h3>{event["step"]}. {role} · {e(event["action"]["action"])}</h3><p>{e(event["action"]["message"])}</p>')
        if event['action']['question']:
            body.append(f'<blockquote>{e(event["action"]["question"])}</blockquote>')
        if event.get('owner_answer'):
            body.append(f'<p><strong>Propietario ({e(event["owner_answer"]["disposition"])}):</strong> {e(event["owner_answer"]["text"])}</p>')
        body.append('</article>')
    body.append('</details>')
    if draft and not approved:
        body.append(f'<details><summary>Borrador sin aprobar · solo para inspección</summary><pre>{e(json.dumps(draft, ensure_ascii=False, indent=2))}</pre></details>')
    body.append('<footer>Revisión automática de IA: no garantiza ausencia de errores. Esta exportación es una instantánea privada; '
                'no se actualiza ni se revoca automáticamente si cambian los datos o las respuestas. Vuelve a exportar para consultar el estado actual.</footer>')
    return '''<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src 'none'; base-uri 'none'; form-action 'none'">
<title>''' + e(title) + ''' · Decision Room</title><style>
*{box-sizing:border-box}body{margin:0;background:#f3f5f8;color:#1c2a39;font:16px/1.65 system-ui,sans-serif}
main{max-width:960px;margin:48px auto;padding:44px;background:#fff;border:1px solid #e1e6ed;border-radius:16px}
header{border-bottom:1px solid #dde4eb;padding-bottom:26px;margin-bottom:28px}.eyebrow{font-size:12px;letter-spacing:.16em;font-weight:750;color:#395c7e}
h1{font-size:36px;line-height:1.2;margin:20px 0 12px}h2{font-size:22px;margin-top:0}h3{font-size:16px}.muted,.source,footer{color:#576779;font-size:14px}
.badge{padding:6px 12px;border-radius:24px;font-size:13px;font-weight:650}.ok{background:#ddf3e8;color:#185f40}.pending{background:#fff0d6;color:#795017}
section{margin:28px 0}.summary{padding:24px;background:#edf3f8;border-radius:10px}p,li,td{overflow-wrap:anywhere}p{white-space:pre-line}
a{color:#145d9d}details{margin:16px 0;padding:16px;border:1px solid #dde4eb;border-radius:8px}summary{cursor:pointer;font-weight:650}
pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f5f7fa;padding:16px;font:12px/1.55 ui-monospace,monospace}
table{width:100%;border-collapse:collapse;margin:16px 0}th,td{text-align:left;border-bottom:1px solid #e4e9ee;padding:10px}th{font-size:13px;color:#576779}
article{padding:10px 0;border-bottom:1px solid #e4e9ee}blockquote{border-left:3px solid #7698b8;margin-left:0;padding-left:16px}footer{border-top:1px solid #dde4eb;padding-top:20px;margin-top:32px}
@media(max-width:640px){main{margin:12px;padding:22px}h1{font-size:28px}.summary{padding:18px}}
@media print{body{background:white}main{border:0;margin:0;padding:0}details{break-inside:avoid}}
</style></head><body><main>''' + ''.join(body) + '</main></body></html>'
