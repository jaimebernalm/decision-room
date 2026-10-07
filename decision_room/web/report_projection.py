"""Pure neutral report projection and offline HTML; no legacy approval implied."""
from copy import deepcopy
from html import escape

from ..reports import contract, charts
from ..series import numeric
from ..reports.verification import VERSION


def project(draft_verified):
    annotations = draft_verified.get('verification_annotations', [])
    blocks = []
    for path, text, recommendation_id in contract.texts(draft_verified):
        if text:
            blocks.append({'path': path, 'text': text, 'recommendation_id': recommendation_id,
                           'figures': [deepcopy(f) for f in annotations if f['path'] == path]})
    facts = [dict(path=path, recommendation_id=rec) for path, fact, rec in contract.fact_entries(draft_verified)]
    fact_paths = {f['path']+'/'+k for f in facts for k in ('text',)}
    return {'renderer_version': VERSION, 'blocks': [b for b in blocks if not b['path'].startswith('/charts/') and b['path'] not in fact_paths],
            'facts': facts, 'fact_text': {b['path']: b for b in blocks if b['path'] in fact_paths},
            'chart_text': {b['path']: b for b in blocks if b['path'].startswith('/charts/')},
            'charts': charts.project(draft_verified.get('charts', []), annotations)}


def render(projection, *, marks=True):
    if projection['renderer_version'] != VERSION:
        raise ValueError('Unsupported report renderer version.')
    blocks = []
    labels = {'verified': 'Verificada', 'unverified': 'No verificada',
              'uncertain': 'Incierta', 'corrected': 'Corregida; alcance semántico no verificado'}
    def text(block):
        value = block['text']; content = ''; end = 0
        if marks:
            for figure in sorted(block['figures'], key=lambda f: f['span']['start']):
                start, stop = figure['span']['start'], figure['span']['end']
                if not end <= start < stop <= len(value) or value[start:stop] != figure['text']:
                    raise ValueError('Verification annotation does not match visible text.')
                label = ('Corregida y comprobada en el ámbito indicado' if figure['status'] == 'corrected' and figure.get('verified')
                         else labels[figure['status']])
                content += escape(value[end:start]) + '<mark class="' + ('checked' if figure.get('verified') else 'unchecked') + '" title="' + label + '">' + escape(value[start:stop]) + '</mark>'
                end = stop
        return content + escape(value[end:])
    def append_facts(recommendation):
        for fact in projection.get('facts', []):
            if fact['recommendation_id'] == recommendation:
                block = projection['fact_text'].get(fact['path']+'/text')
                if block:
                    blocks.append('<aside class="evidence"><p>'+text(block)+'</p></aside>')
    current = None
    for block in projection['blocks']:
        recommendation = block['recommendation_id']
        if recommendation != current:
            append_facts(current)
            current = recommendation
        tag = 'h1' if block['path'] == '/title' else 'h2' if block['path'].endswith('/title') else 'p'
        blocks.append(f'<{tag}>{text(block)}</{tag}>')
    append_facts(current)
    # A finding may contain only facts and no prose blocks.
    visible = {b['recommendation_id'] for b in projection['blocks']} | {current}
    for recommendation in dict.fromkeys(f['recommendation_id'] for f in projection.get('facts', [])):
        if recommendation not in visible:
            append_facts(recommendation)
    for i, chart in enumerate(projection.get('charts', [])):
        def chart_text(path):
            block = projection['chart_text'].get(f'/charts/{i}/' + path)
            return text(block) if block else ''
        blocks.append('<section class="chart"><h2>' + chart_text('title') + '</h2>')
        if chart['caption']:
            blocks.append('<p>' + chart_text('caption') + '</p>')
        graphic, issue = _graphic(chart)
        if graphic: blocks.append(graphic)
        if issue: blocks.append('<p class="limitation">' + escape(issue) + '</p>')
        blocks.append('<div class="table-wrap"><table><thead><tr><th>Serie</th><th>Elemento</th><th>Valor</th></tr></thead><tbody>')
        for j, series in enumerate(chart['series']):
            for k, point in enumerate(series['points']):
                base = f'series/{j}/points/{k}/'
                blocks.append('<tr><th scope="row" style="border-left:4px solid ' + PALETTE[j] + '">' + chart_text(f'series/{j}/label') + '</th><td>'
                              + chart_text(base+'label') + '</td><td>' + chart_text(base+'value_text') + '</td></tr>')
        blocks.append('</tbody></table></div></section>')
    note = '<footer>Las marcas indican el estado de comprobación. Una corrección numérica no certifica su interpretación.</footer>' if marks else ''
    return '''<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">
<title>Informe</title><style>body{max-width:850px;margin:48px auto;padding:0 24px;color:#18252c;font:17px/1.6 system-ui,sans-serif}h1{font-size:32px;line-height:1.2}h2{font-size:23px;margin-top:2em}p{white-space:pre-wrap;overflow-wrap:anywhere}mark{background:#fff0c2;color:inherit}mark.checked{background:#d5eee1}.evidence{border-left:3px solid #167b80;background:#f2f7f7;padding:16px 22px;margin:24px 0}.evidence h3{margin:0;font-size:17px}.evidence p{margin:8px 0}.evidence small{color:#52616a}.chart{margin-top:2.5em;break-inside:avoid}.chart svg{display:block;width:100%;height:auto}.table-wrap{overflow-x:auto}table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}th,td{padding:8px 12px;border-bottom:1px solid #d9e1e5;text-align:left}td:last-child{text-align:right}.limitation{color:#695120}footer{border-top:1px solid #ccd5da;margin-top:40px;padding-top:16px;font-size:13px;color:#52616a}@media print{body{margin:0;max-width:none}h2{break-after:avoid}}</style></head><body><main>''' + '\n'.join(blocks) + '</main>' + note + '</body></html>'


PALETTE = ('#167b80', '#c46536', '#496fba', '#8a5e9e', '#4d8250', '#987219')


def _graphic(chart):
    """Geometry from resolved decimals only; missing/mixed values keep a table."""
    if chart['kind'] == 'table':
        return '', None
    series = chart['series']
    units = {p.get('unit') for s in series for p in s['points']}
    if len(units) > 1:
        return '', 'Las referencias tienen unidades distintas o incompletas; se muestran en tabla.'
    labels = [[p['label'] for p in s['points']] for s in series]
    if any(row != labels[0] for row in labels[1:]):
        return '', 'Las series tienen categorías distintas; se muestran en tabla.'
    if any(p['value'] is None for s in series for p in s['points']):
        return '', 'Hay valores sin resolver; se conserva la tabla sin dibujar una escala incompleta.'
    try:
        values = [[numeric(p['value']) for p in s['points']] for s in series]
    except ValueError:
        return '', 'Hay valores que no pueden representarse en el gráfico.'
    lower = min(0, min(min(s) for s in values)); upper = max(0, max(max(s) for s in values))
    span = upper-lower or 1
    def y(v): return 210 - float((v-lower)/span)*170
    columns = len(labels[0]); slot = 520/columns
    if columns > 30:
        return '', 'Se muestran los valores en tabla para mantener legibles todas las categorías.'
    result = ['<svg viewBox="0 0 600 250" role="img" aria-label="' + escape(chart['title'], quote=True) + '">',
              '<title>' + escape(chart['title']) + '</title>',
              f'<line x1="40" x2="560" y1="{y(0):.3f}" y2="{y(0):.3f}" stroke="#b3c2c9"/>']
    for j, row in enumerate(values):
        color = PALETTE[j]
        points = [(40+slot*(k+0.5), y(v)) for k, v in enumerate(row)]
        if chart['kind'] == 'line':
            result.append('<polyline fill="none" stroke="' + color + '" stroke-width="2" points="'
                          + ' '.join(f'{x:.3f},{yp:.3f}' for x, yp in points) + '"/>')
            for x, yp in points:
                result.append(f'<circle cx="{x:.3f}" cy="{yp:.3f}" r="3" fill="{color}"/>')
        else:
            bar = min(36, slot*0.8/len(series))
            for k, (x, yp) in enumerate(points):
                left = x - bar*len(series)/2 + bar*j
                result.append(f'<rect x="{left:.3f}" y="{min(yp,y(0)):.3f}" width="{bar:.3f}" height="{abs(yp-y(0)):.3f}" fill="{color}"/>')
    for k, label in enumerate(labels[0]):
        # Preserve full labels in the data table; long labels need not collide.
        shown = label if len(label) <= 18 else label[:15]+'…'
        if columns <= 12:
            result.append(f'<text x="{40+slot*(k+0.5):.3f}" y="235" text-anchor="middle" font-size="10" fill="#33454f">{escape(shown)}</text>')
    result.append('</svg>')
    return ''.join(result), None
