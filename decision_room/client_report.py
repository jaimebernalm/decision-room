"""Client presentation from the exact reviewed contract; no generated HTML or JS."""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP, localcontext
from html import escape

from .agent.review_contract import ReportDraft, checks
from .series import saved_series


def e(value):
    return escape(str(value), quote=True)


def metric(data, ref):
    observation = next(o for o in data['observations'] if o['execution_id'] == ref['execution_id'])
    return observation['result']['metrics'][ref['metric']]


def formatted(value, decimals):
    with localcontext() as ctx:
        ctx.prec = 120
        number = Decimal(str(value)).quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)
    return f'{number:,.{decimals}f}'.translate(str.maketrans({',': '.', '.': ','}))


def chart_html(data, chart):
    """Only fixed SVG primitives. Values resolve from approved evidence, never prose."""
    series = saved_series(data['observations'], chart['series']) if chart.get('series') else None
    points = series['points'] if series else chart['points']
    values = [Decimal(str(p['value'] if series else metric(data, p['value']))) for p in points]
    labels = [p['label'] for p in points]
    numbers = [formatted(v, chart['decimals']) for v in values]
    title_id = 'chart-title-' + chart['key']
    caption_id = 'chart-caption-' + chart['key']
    table = '<table><thead><tr><th scope="col">Referencia</th><th scope="col">' + e(chart['unit']) + '</th></tr></thead><tbody>'
    table += ''.join(f'<tr><th scope="row">{e(label)}</th><td>{e(value)}</td></tr>' for label, value in zip(labels, numbers)) + '</tbody></table>'
    svg = ''
    if chart['kind'] != 'table':
        low, high = min(min(values), Decimal(0)), max(max(values), Decimal(0))
        span = high - low or Decimal(1)
        if chart['kind'] == 'bar':
            height = 48 + 64 * len(values)
            def x(v):
                return 20 + float((v - low) / span) * 490
            baseline = x(Decimal(0))
            shapes = [f'<line x1="{baseline:.2f}" y1="34" x2="{baseline:.2f}" y2="{height - 8}" class="axis"/>']
            for i, (label, value, number) in enumerate(zip(labels, values, numbers)):
                y = 28 + i * 64
                shapes.append(f'<text x="20" y="{y}" class="chart-label">{e(label)}</text>')
                shapes.append(f'<rect x="{min(x(value), baseline):.2f}" y="{y+8}" width="{abs(x(value)-baseline):.2f}" height="18" rx="3" class="bar"/>')
                shapes.append(f'<text x="700" y="{y+23}" text-anchor="end" class="chart-number">{e(number)}</text>')
        else:
            height = 300
            days = [date.fromisoformat(label).toordinal() for label in labels]
            def x(day):
                return 110 + (day - days[0]) / (days[-1] - days[0]) * 570
            def y(value):
                return 230 - float((value - low) / span) * 190
            shapes = []
            for tick in range(5):
                value = low + span * Decimal(tick) / 4
                pos = y(value)
                shapes += [f'<line x1="110" y1="{pos:.2f}" x2="680" y2="{pos:.2f}" class="grid"/>',
                           f'<text x="100" y="{pos+5:.2f}" text-anchor="end" class="tick">{e(formatted(value, chart["decimals"]))}</text>']
            for i, (day, value) in enumerate(zip(days, values)):
                # Do not interpolate absent dates; a gap remains a gap.
                if i and day - days[i-1] == 1:
                    shapes.append(f'<line x1="{x(days[i-1]):.2f}" y1="{y(values[i-1]):.2f}" x2="{x(day):.2f}" y2="{y(value):.2f}" class="trend"/>')
                shapes.append(f'<circle cx="{x(day):.2f}" cy="{y(value):.2f}" r="4" class="dot"><title>{e(labels[i])}: {e(numbers[i])}</title></circle>')
            ticks = sorted({round(i * (len(days)-1) / min(4, len(days)-1)) for i in range(min(4, len(days)-1)+1)})
            for i in ticks:
                shapes.append(f'<text x="{x(days[i]):.2f}" y="260" text-anchor="middle" class="tick">{e(labels[i])}</text>')
        svg = f'<div class="plot"><svg viewBox="0 0 720 {height}" role="img" aria-labelledby="{title_id} {caption_id}">' + ''.join(shapes) + '</svg></div>'
        table = '<details><summary>Ver los valores del gráfico</summary>' + table + '</details>'
    return (f'<figure><h3 id="{title_id}">{e(chart["title"])}</h3><p class="unit">{e(chart["unit"])}</p>' + svg + ('<p class="scroll-hint">Desliza el gráfico para ver todos los valores.</p>' if svg else '') +
            f'<figcaption id="{caption_id}">{e(chart["caption"])}</figcaption>' + table +
            f'<a class="finding-link" href="#finding-{e(chart["claim_key"])}">Leer el hallazgo y su evidencia →</a></figure>')


def evidence_html(data, claim, charts):
    refs = claim['evidence'] + [p['value'] for c in charts for p in c['points']]
    refs += [h['value'] for h in data['report'].get('highlights', []) if h['claim_key'] == claim['key']]
    selected = {ref['execution_id'] for ref in refs}
    selected.update(c['series']['execution_id'] for c in charts if c.get('series'))
    files = sorted({name for o in data['observations'] if o['execution_id'] in selected
                    for item in o['inputs'].values() for name in item['original_names']})
    rows, seen = [], set()
    for ref in refs:
        key = (ref['execution_id'], ref['metric'])
        if key in seen:
            continue
        seen.add(key)
        rows.append(f'<tr><th scope="row">{e(ref["metric"])}</th><td>{e(metric(data, ref))}</td></tr>')
    series_details = []
    for chart in charts:
        if chart.get('series'):
            series = saved_series(data['observations'], chart['series'])
            series_details.append(f'<p><strong>{e(chart["title"])}</strong>: {e(series["evidence"]["operation"])}</p>')
    return ('<details class="evidence"><summary>Ver cómo se ha calculado</summary>'
            f'<p>{e(claim["method"])}</p><p><strong>Archivos utilizados:</strong> {e(", ".join(files))}</p>'
            '<p>Resultados guardados que respaldan este hallazgo:</p><table><thead><tr><th scope="col">Resultado</th>'
            '<th scope="col">Valor guardado</th></tr></thead><tbody>' + ''.join(rows) + '</tbody></table>' + ''.join(series_details) + '</details>')


CSS = '''
*{box-sizing:border-box}body{margin:0;color:#203b3b;background:#f3f2ec;font:16px/1.65 system-ui,sans-serif}
main{max-width:1080px;margin:40px auto;background:#fffefa;border:1px solid #d9dfd8;border-radius:18px;overflow:hidden}
header{background:#163e3b;color:#fffefa;padding:42px 48px}.eyebrow{font-size:12px;letter-spacing:.18em;text-transform:uppercase;font-weight:700}
h1{font-size:clamp(28px,4vw,42px);line-height:1.15;max-width:850px;margin:22px 0}h2{font-size:25px;line-height:1.3;margin:0 0 16px}h3{font-size:18px;line-height:1.4;margin:0}
.meta{color:#d1e1d9;font-size:14px}.content{padding:36px 48px}.intro{font-size:19px;line-height:1.7}.coverage{background:#f3f0df;border-left:4px solid #b59031;padding:16px 20px;margin:24px 0}
.highlights{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px;margin:26px 0 36px}.highlight{display:flex;flex-direction:column;padding:22px;border:1px solid #d9dfd8;border-radius:12px;background:#f7f8f3;text-decoration:none;color:inherit}.highlight span{font-size:13px;color:#52665f}.highlight strong{font-size:clamp(22px,3vw,30px);line-height:1.3;margin:12px 0;font-variant-numeric:tabular-nums;white-space:nowrap}.highlight small{font-size:12px;color:#52665f}.highlight:hover{border-color:#26766a}.highlight:focus-visible,a:focus-visible{outline:3px solid #26766a;outline-offset:4px}.visuals{margin:36px 0}.finding-link{font-size:13px;color:#26766a}.plot{overflow-x:auto}.scroll-hint{display:none;font-size:12px;color:#52665f}section[id]{scroll-margin-top:20px}
.finding{padding:30px 0;border-top:1px solid #dbe1db}.number{color:#66837a;font-size:12px;letter-spacing:.15em;font-weight:700}.interpretation{padding:0 0 0 18px;border-left:3px solid #c3d5cb}.next{background:#eaf1eb;padding:18px 22px;border-radius:8px}.next strong{display:block}
figure{margin:26px 0;padding:22px;background:#f7f8f3;border:1px solid #e0e5dc;border-radius:10px}svg{display:block;width:100%;height:auto;margin:8px 0}figcaption,.unit{font-size:14px;color:#52665f}.unit{margin:4px 0}
.bar,.dot{fill:#26766a}.trend{stroke:#26766a;stroke-width:2.5}.axis{stroke:#8a9f97;stroke-width:1}.grid{stroke:#dce4dd;stroke-width:1}.chart-label,.chart-number{font:15px system-ui;fill:#203b3b}.chart-number{font-weight:650}.tick{font:12px system-ui;fill:#52665f}
p,li,td,th{overflow-wrap:anywhere}p{white-space:pre-line}table{width:100%;border-collapse:collapse;margin:16px 0;font-size:14px}th,td{padding:10px 12px;text-align:left;border-bottom:1px solid #dce4dd}td{text-align:right;font-variant-numeric:tabular-nums}thead th{background:#eaf0e9}tbody th{font-weight:500}
details{margin:16px 0;padding:15px 18px;border:1px solid #d9e1d8;border-radius:8px;background:#fffefa}summary{cursor:pointer;font-size:14px;font-weight:650}summary:focus-visible{outline:3px solid #26766a;outline-offset:5px}
footer{padding:24px 48px;border-top:1px solid #d9e1d8;color:#52665f;font-size:12px}.limits{padding-top:28px;border-top:1px solid #d9e1d8}.empty{color:#52665f;font-size:14px}
@media(max-width:640px){main{margin:0;border:0;border-radius:0}header{padding:30px 22px}.content{padding:24px 22px}footer{padding:22px}figure{padding:12px}.plot svg{min-width:540px}.chart-label,.chart-number{font-size:17px}.highlights{grid-template-columns:repeat(2,minmax(0,1fr))}.highlight{padding:14px}.highlight strong{font-size:24px}}
@media(max-width:500px){.highlights{grid-template-columns:1fr}.highlight strong{font-size:28px}.scroll-hint{display:block}}
@media print{body,main{background:white}main{border:0;margin:0}header{background:white;color:#163e3b}.meta{color:#52665f}.finding,figure{break-inside:avoid}}
'''

EMBEDDED_CSS = '''
body{background:#fffefa;font-size:14px}main{margin:0;border:0;border-radius:0}
header{padding:30px}h1{font-size:32px}.content{padding:28px}footer{padding:24px 28px}
@media(max-width:500px){header,.content,footer{padding:22px}h1{font-size:27px}
.chart-label,.chart-number{font-size:17px}.tick{font-size:13px}}
'''


def render_client(data, exported_at, *, embedded=False):
    draft = data.get('report')
    ready = bool(data.get('publishable') and data.get('status') == 'approved' and draft)
    if ready:
        # Legacy approvals never acquire new client content without a fresh review.
        try:
            ReportDraft.model_validate(draft)
            ready = all(c['passed'] for c in checks(draft, data['observations']))
        except ValueError:
            ready = False
    title = draft['title'] if ready else 'Tu informe está pendiente'
    body = [f'<header><p class="eyebrow">Decision Room · Informe de negocio</p><h1>{e(title)}</h1>']
    if ready:
        scope = draft['scope']
        body += [f'<p class="meta">{e(scope["business"])} · {e(scope["period"])}</p>']
    body += [f'<p class="meta">Generado: {e(exported_at)}</p></header><div class="content">']
    if ready:
        body += [f'<section><h2>La pregunta de negocio</h2><p>{e(scope["question"])}</p>',
                 f'<aside class="coverage"><strong>Qué cubre este análisis</strong><p>{e(scope["coverage"])}</p></aside></section>',
                 f'<section class="intro"><h2>Lo que muestran tus datos</h2><p>{e(draft["summary"])}</p></section>']
        if draft.get('highlights'):
            body += ['<section class="highlights" aria-label="Cifras clave">']
            for highlight in draft['highlights']:
                value = formatted(metric(data, highlight['value']), highlight['decimals'])
                body += [f'<a class="highlight" href="#finding-{e(highlight["claim_key"])}"><span>{e(highlight["label"])}</span><strong>{e(value)}</strong><small>{e(highlight["unit"])}</small></a>']
            body += ['</section>']
        if draft['charts']:
            body += ['<section class="visuals"><h2>Los datos, en perspectiva</h2>']
            body += [chart_html(data, c) for c in draft['charts']]
            body += ['</section>']
        for i, claim in enumerate(draft['claims'], 1):
            charts = [c for c in draft['charts'] if c['claim_key'] == claim['key']]
            body += [f'<section class="finding" id="finding-{e(claim["key"])}"><p class="number">HALLAZGO {i:02d}</p><h2>{e(claim["title"])}</h2><p>{e(claim["statement"])}</p>']
            body += [f'<div class="interpretation"><h3>Qué significa para el negocio</h3><p>{e(claim["interpretation"])}</p></div>']
            if claim['next_step']:
                body += [f'<p class="next"><strong>Siguiente comprobación</strong>{e(claim["next_step"])}</p>']
            body += [evidence_html(data, claim, charts), '</section>']
        if not draft['charts']:
            body += [f'<p class="empty">{e(draft["no_chart_reason"])}</p>']
        body += ['<section class="limits"><h2>Cómo interpretar este informe</h2><ul>' + ''.join(f'<li>{e(x)}</li>' for x in draft['limitations']) + '</ul></section>']
    else:
        body += ['<section><h2>Aún no hay un informe disponible para entregar</h2><p>Estamos pendientes de completar o corregir la revisión. Los resultados provisionales no se muestran como conclusiones.</p>']
        for question in data.get('pending_questions', []):
            body += [f'<p><strong>Necesitamos tu aclaración:</strong> {e(question["action"]["question"])}</p>']
        body += ['</section>']
    body += ['</div><footer>Informe elaborado con asistencia de IA y revisión automática. Consulta su alcance y evidencia. '
             'Esta copia refleja los datos y respuestas disponibles en la fecha indicada; no se actualiza automáticamente.</footer>']
    return ('<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; img-src \'none\'; base-uri \'none\'; form-action \'none\'">'
            f'<title>{e(title)} · Decision Room</title><style>{CSS}' +
            (EMBEDDED_CSS if embedded else '') +
            '</style></head><body><main>' + ''.join(body) + '</main></body></html>')
