"""Client presentation from the exact reviewed contract; no generated HTML or JS."""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP, localcontext
from html import escape

from .chart_layout import CHART_PALETTE, panels, series_colors
from .agent.review_contract import ReportDraft, checks
from .series import saved_series, evidence_value, evidence_label, evidence_key
from .chart_evidence import resolve_chart, series_refs


def e(value):
    return escape(str(value), quote=True)


def metric(data, ref):
    return evidence_value(data['observations'], ref)


def formatted(value, decimals):
    with localcontext() as ctx:
        ctx.prec = 120
        number = Decimal(str(value)).quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)
    return f'{number:,.{decimals}f}'.translate(str.maketrans({',': '.', '.': ','}))


def grouped_svg(chart, layout, points, values, colors):
    import textwrap
    def color(label): return colors[label]
    saved = {p['label']: v for p, v in zip(points, values)}
    output = []
    for index, panel in enumerate(layout):
        order = panel['series_order']
        categories = list(dict.fromkeys(p['category'] for p in panel['coordinates']))
        cells = {(p['category'], p['series']): saved[p['label']] for p in panel['coordinates']}
        low, high = min(min(cells.values()), Decimal(0)), max(max(cells.values()), Decimal(0))
        if panel['measure'] == 'change':
            low, high = -max(abs(low), abs(high)), max(abs(low), abs(high))
        span = high - low or Decimal(1)
        def x(value): return 205 + float((value-low)/span) * 390
        top = 25 + 24 * ((len(order)+2)//3)
        category_lines = {c: textwrap.wrap(c, width=23) for c in categories}
        row_height = max(len(order)*24 + 28, max(len(lines) for lines in category_lines.values())*18 + 16)
        height = top + len(categories)*row_height + 10
        shapes = []
        for i, name in enumerate(order):
            left, y = 20 + (i % 3)*230, 18 + (i//3)*24
            shapes.append(f'<rect x="{left}" y="{y-10}" width="10" height="10" fill="{color(name)}"/><text x="{left+17}" y="{y}" class="tick">{e(name)}</text>')
        shapes.append(f'<line x1="{x(0):.2f}" x2="{x(0):.2f}" y1="{top}" y2="{height}" class="axis"/>')
        for i, category in enumerate(categories):
            y = top + i*row_height
            for j, line in enumerate(category_lines[category]):
                shapes.append(f'<text x="10" y="{y+18+j*18}" class="chart-label">{e(line)}</text>')
            for j, name in enumerate(order):
                value = cells.get((category, name))
                if value is None:
                    continue
                number = formatted(value, chart['decimals'])
                shapes.append(f'<rect x="{min(x(value),x(0)):.2f}" y="{y+j*24}" width="{abs(x(value)-x(0)):.2f}" height="18" rx="3" fill="{color(name)}"><title>{e(category)} · {e(name)}: {e(number)}</title></rect>')
                shapes.append(f'<text x="700" y="{y+j*24+14}" text-anchor="end" class="chart-number">{e(number)}</text>')
        title = panel['title'] or chart['title']
        output.append(f'<h4>{e(title)}</h4><div class="plot"><svg viewBox="0 0 720 {height}" role="img" aria-label="{e(title)}">' + ''.join(shapes) + '</svg></div>')
    return ''.join(output)


def temporal_svg(chart, points, values, colors):
    from .chart_layout import temporal_cells
    grain, categories, indices, order, cells = temporal_cells(chart, points, values)
    bounds = [*values] if chart.get('scale') == 'data' else [Decimal(0), *values]
    low, high = min(bounds), max(bounds)
    span = high - low or Decimal(1)
    def x(index): return 110 + (index - indices[0]) / (indices[-1] - indices[0] or 1) * 570
    def y(value): return 230 - float((value - low) / span) * 160
    shapes = []
    for i, name in enumerate(order):
        shade = colors.get(name, CHART_PALETTE[0])
        style = (chart.get('encoding') or {}).get('styles', {}).get(name, {})
        width = 2.8 if style.get('weight') == 'emphasis' else 1.5 if style else 2.5
        dash = {'dashed': '6 4', 'dotted': '2 3'}.get(style.get('style'), '')
        shapes.append(f'<text x="{110+(i%3)*180}" y="{16+(i//3)*20}" class="tick" fill="{shade}">{e(name)}</text>')
        previous = None
        for category, index in zip(categories, indices):
            value = cells.get((category, name))
            if value is None:
                previous = None
                continue
            if previous and index - previous[0] == 1:
                shapes.append(f'<line x1="{x(previous[0]):.2f}" y1="{y(previous[1]):.2f}" x2="{x(index):.2f}" y2="{y(value):.2f}" class="trend" style="stroke:{shade};stroke-width:{width}" stroke-dasharray="{dash}"/>')
            shapes.append(f'<circle cx="{x(index):.2f}" cy="{y(value):.2f}" r="4" style="fill:{shade}"><title>{e(category)} · {e(name)}: {e(formatted(value, chart['decimals']))}</title></circle>')
            previous = index, value
    for tick in range(5):
        value = low + span * Decimal(tick) / 4
        pos = y(value)
        shapes += [f'<line x1="110" y1="{pos:.2f}" x2="680" y2="{pos:.2f}" class="grid"/>',
                   f'<text x="100" y="{pos+5:.2f}" text-anchor="end" class="tick">{e(formatted(value, chart["decimals"]))}</text>']
    for i in sorted({round(i*(len(indices)-1)/min(4,len(indices)-1)) for i in range(min(4,len(indices)-1)+1)}):
        shapes.append(f'<text x="{x(indices[i]):.2f}" y="260" text-anchor="middle" class="tick">{e(categories[i])}</text>')
    return '<div class="plot"><svg viewBox="0 0 720 300" role="img" aria-label="' + e(chart['title']) + '">' + ''.join(shapes) + '</svg></div>'


def chart_html(data, chart):
    """Only fixed SVG primitives. Values resolve from approved evidence, never prose."""
    chart, points = resolve_chart(chart, data['observations'])
    values = [Decimal(str(p['value'])) for p in points]
    labels = [p['label'] for p in points]
    numbers = [formatted(v, chart['decimals']) for v in values]
    title_id = 'chart-title-' + chart['key']
    caption_id = 'chart-caption-' + chart['key']
    from .chart_layout import comparison_tables
    table = ''
    for title, headings, rows in comparison_tables(chart, points, numbers):
        table += (f'<h4>{e(title)}</h4>' if title else '') + '<table><thead><tr>'
        table += ''.join(f'<th scope="col">{e(h)}</th>' for h in headings) + '</tr></thead><tbody>'
        table += ''.join('<tr>' + f'<th scope="row">{e(row[0])}</th>' + ''.join(f'<td>{e(v)}</td>' for v in row[1:]) + '</tr>' for row in rows) + '</tbody></table>'
    svg = ''
    if chart['kind'] != 'table':
        low, high = min(min(values), Decimal(0)), max(max(values), Decimal(0))
        span = high - low or Decimal(1)
        if chart['kind'] == 'bar':
            import textwrap
            wrapped = [textwrap.wrap(label, 65) for label in labels]
            row_height = max(64, max(len(lines) for lines in wrapped) * 18 + 40)
            height = 48 + row_height * len(values)
            def x(v):
                return 20 + float((v - low) / span) * 490
            baseline = x(Decimal(0))
            shapes = [f'<line x1="{baseline:.2f}" y1="34" x2="{baseline:.2f}" y2="{height - 8}" class="axis"/>']
            for i, (label, value, number) in enumerate(zip(labels, values, numbers)):
                y = 28 + i * row_height
                for j, line in enumerate(wrapped[i]):
                    shapes.append(f'<text x="20" y="{y+j*18}" class="chart-label">{e(line)}</text>')
                y += (len(wrapped[i])-1)*18
                shapes.append(f'<rect x="{min(x(value), baseline):.2f}" y="{y+8}" width="{abs(x(value)-baseline):.2f}" height="18" rx="3" class="bar"/>')
                shapes.append(f'<text x="700" y="{y+23}" text-anchor="end" class="chart-number">{e(number)}</text>')
        else:
            height = 300
            shapes = []
        svg = f'<div class="plot"><svg viewBox="0 0 720 {height}" role="img" aria-labelledby="{title_id} {caption_id}">' + ''.join(shapes) + '</svg></div>'
        layout = panels(chart, points)
        if chart['kind'] == 'bar' and layout:
            all_layouts = [p for c in data['report']['charts'] for p in panels(*resolve_chart(c, data['observations']))]
            colors = series_colors(s for panel in all_layouts for s in panel['series_order'])
            svg = grouped_svg(chart, layout, points, values, colors)
        if chart['kind'] == 'line':
            all_labels = [s for c in data['report']['charts'] for p in panels(*resolve_chart(c, data['observations'])) for s in p['series_order']]
            svg = temporal_svg(chart, points, values, series_colors(all_labels))
        table = '<details><summary>Ver los valores del gráfico</summary>' + table + '</details>'
    for detail in chart.get('details', []):
        table += f'<p><strong>{e(detail["point_label"])}</strong>: ' + '; '.join(f'{e(v["label"])}: {e(formatted(metric(data,v["value"]),v["decimals"]))} {e(v["unit"])}' for v in detail['values']) + '</p>'
        if detail.get('claim_key'):
            table += f'<a href="#finding-{e(detail["claim_key"])}">Leer hallazgo vinculado</a>'
    return (f'<figure><h3 id="{title_id}">{e(chart["title"])}</h3><p class="unit">{e(chart["unit"])}</p>' + svg + ('<p class="scroll-hint">Desliza el gráfico para ver todos los valores.</p>' if svg else '') +
            f'<figcaption id="{caption_id}">{e(chart["caption"])}</figcaption>' + table +
            f'<a class="finding-link" href="#finding-{e(chart["claim_key"])}">Leer el hallazgo y su evidencia →</a></figure>')


def evidence_html(data, claim, charts):
    refs = claim['evidence'] + (claim.get('orientation') or {}).get('evidence', []) + [p['value'] for c in charts for p in c['points']]
    refs += [h['value'] for h in data['report'].get('highlights', []) if h['claim_key'] == claim['key']]
    refs += [v['value'] for c in charts for d in c.get('details', []) for v in d['values']]
    selected = {ref['execution_id'] for ref in refs}
    selected.update(c['series']['execution_id'] for c in charts if c.get('series'))
    selected.update(ref['execution_id'] for c in charts for ref in series_refs(c))
    files = sorted({name for o in data['observations'] if o['execution_id'] in selected
                    for item in o['inputs'].values() for name in item['original_names']})
    rows, seen = [], set()
    for ref in refs:
        key = evidence_key(ref)
        if key in seen:
            continue
        seen.add(key)
        rows.append(f'<tr><th scope="row">{e(evidence_label(ref))}</th><td>{e(metric(data, ref))}</td></tr>')
    series_details = []
    for chart in charts:
        for ref in series_refs(chart):
            series = saved_series(data['observations'], ref)
            series_details.append(f'<p><strong>{e(chart["title"])}</strong>: {e(series["evidence"]["operation"])}</p>')
    return ('<details class="evidence"><summary>Ver cómo se ha calculado</summary>'
            f'<p>{e(claim["method"])}</p><p><strong>Archivos utilizados:</strong> {e(", ".join(files))}</p>'
            '<p>Resultados guardados que respaldan este hallazgo:</p><table><thead><tr><th scope="col">Resultado</th>'
            '<th scope="col">Valor guardado</th></tr></thead><tbody>' + ''.join(rows) + '</tbody></table>' + ''.join(series_details) + '</details>')


CSS = ':root{--chart-primary:' + CHART_PALETTE[0] + '}\n' + '''
*{box-sizing:border-box}body{margin:0;color:#203b3b;background:#f3f2ec;font:16px/1.65 system-ui,sans-serif}
main{max-width:1080px;margin:40px auto;background:#fffefa;border:1px solid #d9dfd8;border-radius:18px;overflow:hidden}
header{background:#163e3b;color:#fffefa;padding:42px 48px}.eyebrow{font-size:12px;letter-spacing:.18em;text-transform:uppercase;font-weight:700}
h1{font-size:clamp(28px,4vw,42px);line-height:1.15;max-width:850px;margin:22px 0}h2{font-size:25px;line-height:1.3;margin:0 0 16px}h3{font-size:18px;line-height:1.4;margin:0}
.meta{color:#d1e1d9;font-size:14px}.content{padding:36px 48px}.intro{font-size:19px;line-height:1.7}.coverage{background:#f3f0df;border-left:4px solid #b59031;padding:16px 20px;margin:24px 0}
.highlights{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px;margin:26px 0 36px}.highlight{display:flex;flex-direction:column;padding:22px;border:1px solid #d9dfd8;border-radius:12px;background:#f7f8f3;text-decoration:none;color:inherit}.highlight span{font-size:13px;color:#52665f}.highlight strong{font-size:clamp(22px,3vw,30px);line-height:1.3;margin:12px 0;font-variant-numeric:tabular-nums;white-space:nowrap}.highlight small{font-size:12px;color:#52665f}.highlight:hover{border-color:#26766a}.highlight:focus-visible,a:focus-visible{outline:3px solid #26766a;outline-offset:4px}.visuals{margin:36px 0}.finding-link{font-size:13px;color:#26766a}.plot{overflow-x:auto}.scroll-hint{display:none;font-size:12px;color:#52665f}section[id]{scroll-margin-top:20px}
.finding{padding:30px 0;border-top:1px solid #dbe1db}.number{color:#66837a;font-size:12px;letter-spacing:.15em;font-weight:700}.interpretation{padding:0 0 0 18px;border-left:3px solid #c3d5cb}.next{background:#eaf1eb;padding:18px 22px;border-radius:8px}.next strong{display:block}
figure{margin:26px 0;padding:22px;background:#f7f8f3;border:1px solid #e0e5dc;border-radius:10px}svg{display:block;width:100%;height:auto;margin:8px 0}figcaption,.unit{font-size:14px;color:#52665f}.unit{margin:4px 0}
.bar,.dot{fill:var(--chart-primary)}.trend{stroke:var(--chart-primary);stroke-width:2.5}.axis{stroke:#8a9f97;stroke-width:1}.grid{stroke:#dce4dd;stroke-width:1}.chart-label,.chart-number{font:15px system-ui;fill:#203b3b}.chart-number{font-weight:650}.tick{font:12px system-ui;fill:#52665f}
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
    from .owner_presentation import enabled
    if ready and enabled(data):
        from .web.dashboard import presentation
        from .web.presentation_html import render
        return render(presentation(data), exported_at)
    title = draft['title'] if ready else 'Tu informe está pendiente'
    body = [f'<header><p class="eyebrow">Decision Room · Informe de negocio</p><h1>{e(title)}</h1>']
    if ready:
        scope = draft['scope']
        if (any(q['status'] != 'complete' for q in draft['owner_coverage']) if draft.get('owner_coverage') else any(q['status'] != 'answered' for q in draft.get('question_coverage', []))):
            body += ['<p class="meta">Entrega parcial · Consulta las preguntas pendientes en alcance y límites.</p>']
        body += [f'<p class="meta">{e(scope["business"])} · {e(scope["period"])}</p>']
    body += [f'<p class="meta">Generado: {e(exported_at)}</p></header><div class="content">']
    if ready:
        if data.get('options', {}).get('sales_panorama') or data.get('options', {}).get('sales_panorama_contract', 0) >= 2:
            from .panorama_presentation import owner_sections, render_html
            body.append(render_html(owner_sections(data.get('sales_panorama'), data['observations'])))
        body += [f'<section><h2>La pregunta de negocio</h2><p>{e(scope["question"])}</p>',
                 f'<aside class="coverage"><strong>Qué cubre este análisis</strong><p>{e(scope["coverage"])}</p></aside></section>',
                 f'<section class="intro"><h2>Lo que muestran tus datos</h2><p>{e(draft["summary"])}</p></section>']
        if draft.get('highlights'):
            body += ['<section class="highlights" aria-label="Cifras clave">']
            for highlight in draft['highlights']:
                value = formatted(metric(data, highlight['value']), highlight['decimals'])
                body += [f'<a class="highlight" href="#finding-{e(highlight["claim_key"])}"><span>{e(highlight["label"])}</span><strong>{e(value)}</strong><small>{e(highlight["unit"])}</small></a>']
            body += ['</section>']
        from .panorama_presentation import comparison_statement
        for i, claim in enumerate(draft['claims'], 1):
            charts = [c for c in draft['charts'] if c['claim_key'] == claim['key']]
            body += [f'<section class="finding" id="finding-{e(claim["key"])}"><p class="number">HALLAZGO {i:02d}</p><h2>{e(claim["title"])}</h2><p>{e(comparison_statement(claim))}</p>']
            body += [f'<div class="interpretation"><h3>Qué significa para el negocio</h3><p>{e(claim["interpretation"])}</p></div>']
            from .agent.delivery_contract import orientation_sections
            guidance = orientation_sections(claim.get('orientation'))
            if guidance:
                body += ['<aside class="next">' + ''.join(f'<p><strong>{e(heading)}</strong>{e(text)}</p>' for heading, text in guidance) + '</aside>']
            if claim['next_step'] and not claim.get('orientation'):
                body += [f'<p class="next"><strong>Siguiente comprobación</strong>{e(claim["next_step"])}</p>']
            body += [chart_html(data, chart) for chart in charts]
            body += [evidence_html(data, claim, charts), '</section>']
        if not draft['charts']:
            body += [f'<p class="empty">{e(draft["no_chart_reason"])}</p>']
        body += ['<section class="limits"><h2>Cómo interpretar este informe</h2><ul>' + ''.join(f'<li>{e(x)}</li>' for x in list(dict.fromkeys([*draft['limitations'], *(data.get('controller_resolution') or {}).get('owner_limitations', [])]))) + '</ul></section>']
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
