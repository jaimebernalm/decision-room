"""Legacy HTML links export the same scoped presentation as React and PDF."""
from ..client_report import CSS, EMBEDDED_CSS, e
from ..report_pdf import bar_drawings, line_drawing
from reportlab.graphics import renderSVG

def render(report, exported_at):
    from ..report_language import export_view, label
    report = export_view(report)
    tr = lambda text: label(text, report.get('response_language'))
    language = report.get('response_language') or 'es'
    owner = report.get('owner_presentation', False)
    scope = report['scope']
    coverage = f'<aside class="coverage">{e(scope["coverage"])}</aside>' if scope['coverage'] else ''
    output = [f"""<header><p class="eyebrow">{tr('Decision Room · Informe de negocio')}</p><h1>{e(report['title'])}</h1>""", f"""<p class="meta">{e(scope.get('business', ''))} · {e(scope['period'])}</p>""", f"""<p class="meta">{tr('Exportado:')} {e(exported_at)}</p></header><div class="content">""", f"""<p>{e(scope.get('question', ''))}</p>{coverage}""", f"""<p class="intro">{e(report.get('summary', ''))}</p>"""]
    from ..panorama_presentation import render_html
    if report.get('panorama'):
        output.insert(3, render_html(report['panorama']))
    if report.get('partial') and not owner:
        output.append(f"<p>{tr('Entrega parcial · Consulta las preguntas pendientes en alcance y límites.')}</p>")
    output.append(f'''<section class="highlights" aria-label="{tr('Cifras clave')}">''')
    for h in report['highlights']:
        output.append(f"""<a class="highlight" href="#finding-{e(h['claim_key'])}"><span>{e(h['label'])}</span><strong>{e(h['value'])}</strong><small>{e(h['unit'])}</small>""")
        if h.get('unit_origin') == 'owner':
            output.append(f"<small>{tr('Unidad visible indicada por el propietario. Unidad del análisis:')} {e(h['original_unit'])}.</small>")
        output.append('</a>')
    output.append('</section>')
    for c in report['claims']:
        output.append(f"""<section class="finding" id="finding-{e(c['key'])}"><h2>{e(c['title'])}</h2><p>{e(c['statement'])}</p>""")
        if c.get('panorama_priority'):
            output.append('<p>' + e(c['panorama_priority']['alternative']) + ' ' + e(c['panorama_priority']['why_first']) + '</p>')
        for field in ('interpretation', 'next_step'):
            if c.get(field) and not (owner and field == 'next_step' and c.get('orientation')):
                output.append(f'<p class="{field}">{e(c[field])}</p>')
        if owner:
            from ..owner_presentation import guidance
            for heading, text in guidance(c):
                output.append(f'<p><strong>{e(tr(heading))}</strong>: {e(text)}</p>')
        if c.get('method') and not owner:
            output.append(f"<details><summary>{tr('Ver cómo se ha calculado')}</summary><p>{e(c['method'])}</p></details>")
        if owner and c.get('source_summary'):
            output.append(f'<p class="source-summary">{e(c["source_summary"])}</p>')
        evidence = c.get('evidence_details')
        if evidence and not owner:
            output.append(f"<details><summary>{tr('Fuentes y evidencia')}</summary>")
            output.append(f"<p>{e(' · '.join(evidence['files']))}</p>")
            for item in evidence['metrics']:
                output.append(f"<p>{e(item['label'])}: {e(item['value'])}</p>")
            for operation in evidence['operations']:
                output.append(f'<p>{e(operation)}</p>')
            output.append('</details>')
        for chart in [x for x in report['charts'] if x['claim_key'] == c['key']]:
            output.append(f"""<figure><h3>{e(chart['title'])}</h3><p class="unit">{e(chart['unit'])}</p>""")
            if chart.get('unit_origin') == 'owner':
                output.append(f"""<p class="unit">{tr('Unidad visible indicada por el propietario. Unidad del análisis:')} {e(chart['original_unit'])}.</p>""")
            drawings = bar_drawings(chart) if chart['kind'] == 'bar' else [('', line_drawing(chart))] if chart['kind'] == 'line' else []
            for panel_title, drawing in drawings:
                if panel_title:
                    output.append(f'<h4>{e(panel_title)}</h4>')
                svg = renderSVG.drawToString(drawing)
                svg = svg[svg.index('<svg'):]
                if owner:
                    svg = svg.replace('<svg ', f'<svg role="img" aria-label="{e(chart["title"])}" ', 1)
                output.append('<div class="plot">' + svg + '</div>')
            if not owner or chart['kind'] == 'table':
                original = not owner and any(p.get('original_label', p['label']) != p['label'] for p in chart['points'])
                output.append(f"<table><thead><tr><th>{tr('Periodo / categoría')}</th>" + (f"<th>{tr('Código original')}</th>" if original else '') + f"<th>{e(chart['unit'])}</th></tr></thead><tbody>")
                for point in chart['points']:
                    output.append(f'<tr><th scope="row">{e(point['label'])}</th>' + (f"<td>{e(point.get('original_label', point['label']))}</td>" if original else '') + f"<td>{e(point['formatted'])}</td></tr>")
                output.append('</tbody></table>')
            output.append(f"<figcaption>{e(chart['caption'])}</figcaption></figure>")
        output.append('</section>')
    if report.get('no_chart_reason'):
        output.append(f"<p>{e(report['no_chart_reason'])}</p>")
    output.append(f"""<section class="limits"><h2>{tr('Alcance y límites')}</h2>""")
    for question in ([] if owner else report.get('question_coverage', [])):
        output.append(f"<p>{e(question['explanation'])}</p>")
    for limitation in report['limitations']:
        output.append(f'<p>{e(limitation)}</p>')
    output.append('</section></div>')
    if not owner:
        revision = report.get('presentation', {}).get('revision', 0)
        output.append(f"<footer>{tr('Presentación · Versión')} {revision}{tr('. Cálculos y fuentes del análisis original conservados.')}</footer>")
    return f'<!doctype html><html lang="{language}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' + f"<title>{e(report['title'])}</title><style>{CSS}{EMBEDDED_CSS}</style></head><body><main>" + ''.join(output) + '</main></body></html>'
