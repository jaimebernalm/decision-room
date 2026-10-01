"""Legacy HTML links export the same scoped presentation as React and PDF."""
from ..client_report import CSS, EMBEDDED_CSS, e
from ..report_pdf import bar_drawings, line_drawing
from reportlab.graphics import renderSVG


def render(report, exported_at):
    scope = report['scope']
    output = [f'<header><p class="eyebrow">Decision Room · Informe de negocio</p><h1>{e(report["title"])}</h1>',
              f'<p class="meta">{e(scope.get("business", ""))} · {e(scope["period"])}</p>',
              f'<p class="meta">Exportado: {e(exported_at)}</p></header><div class="content">',
              f'<p>{e(scope.get("question", ""))}</p><aside class="coverage">{e(scope["coverage"])}</aside>',
              f'<p class="intro">{e(report.get("summary", ""))}</p>']
    if report.get('partial'):
        output.append('<p>Entrega parcial · Consulta las preguntas pendientes en alcance y límites.</p>')
    output.append('<section class="highlights" aria-label="Cifras clave">')
    for h in report['highlights']:
        output.append(f'<a class="highlight" href="#finding-{e(h["claim_key"])}"><span>{e(h["label"])}</span><strong>{e(h["value"])}</strong><small>{e(h["unit"])}</small></a>')
    output.append('</section>')
    for c in report['claims']:
        output.append(f'<section class="finding" id="finding-{e(c["key"])}"><h2>{e(c["title"])}</h2><p>{e(c["statement"])}</p>')
        for field in ('interpretation', 'next_step'):
            if c.get(field):
                output.append(f'<p class="{field}">{e(c[field])}</p>')
        if c.get('method'):
            output.append(f'<details><summary>Ver cómo se ha calculado</summary><p>{e(c["method"])}</p></details>')
        evidence = c.get('evidence_details')
        if evidence:
            output.append('<details><summary>Fuentes y evidencia</summary>')
            output.append(f'<p>{e(" · ".join(evidence["files"]))}</p>')
            for item in evidence['metrics']:
                output.append(f'<p>{e(item["label"])}: {e(item["value"])}</p>')
            for operation in evidence['operations']:
                output.append(f'<p>{e(operation)}</p>')
            output.append('</details>')
        for chart in [x for x in report['charts'] if x['claim_key'] == c['key']]:
            output.append(f'<figure><h3>{e(chart["title"])}</h3><p class="unit">{e(chart["unit"])}</p>')
            drawings = bar_drawings(chart) if chart['kind'] == 'bar' else [('',line_drawing(chart))] if chart['kind'] == 'line' else []
            for panel_title, drawing in drawings:
                if panel_title:
                    output.append(f'<h4>{e(panel_title)}</h4>')
                svg = renderSVG.drawToString(drawing)
                output.append('<div class="plot">' + svg[svg.index('<svg'):] + '</div>')
            original = any(p.get('original_label', p['label']) != p['label'] for p in chart['points'])
            output.append('<table><thead><tr><th>Periodo / categoría</th>' + ('<th>Código original</th>' if original else '') + f'<th>{e(chart["unit"])}</th></tr></thead><tbody>')
            for point in chart['points']:
                output.append(f'<tr><th scope="row">{e(point["label"])}</th>' + (f'<td>{e(point.get("original_label", point["label"]))}</td>' if original else '') + f'<td>{e(point["formatted"])}</td></tr>')
            output.append(f'</tbody></table><figcaption>{e(chart["caption"])}</figcaption></figure>')
        output.append('</section>')
    if report.get('no_chart_reason'):
        output.append(f'<p>{e(report["no_chart_reason"])}</p>')
    output.append('<section class="limits"><h2>Alcance y límites</h2>')
    for question in report.get('question_coverage', []):
        output.append(f'<p>{e(question["explanation"])}</p>')
    for limitation in report['limitations']:
        output.append(f'<p>{e(limitation)}</p>')
    revision = report.get('presentation', {}).get('revision', 0)
    output.append(f'</section></div><footer>Presentación · Versión {revision}. Cálculos y fuentes del análisis original conservados.</footer>')
    return '<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' + f'<title>{e(report["title"])}</title><style>{CSS}{EMBEDDED_CSS}</style></head><body><main>' + ''.join(output) + '</main></body></html>'
