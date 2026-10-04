"""Static, complete PDF from an already validated client presentation.

No model calls, external assets or internal transcripts. Long sections and exact
value tables paginate instead of clipping, and drawings remain vector graphics.
"""
from datetime import datetime
from decimal import Decimal
from html import escape
from io import BytesIO
import textwrap

from reportlab.graphics.shapes import Drawing, Rect, String, Line, Circle
from reportlab.lib import colors
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, PageBreak

from .chart_layout import CHART_PALETTE
from .client_report import formatted
from .owner_presentation import readable_number
from .report_language import number

WIDTH = A4[0] - 88
BLUE = colors.HexColor(CHART_PALETTE[0])
INK = colors.HexColor('#171717')
GRAY = colors.HexColor('#707070')
BORDER = colors.HexColor('#e5e5e5')
STYLES = {
    'body': ParagraphStyle('body', fontName='Helvetica', fontSize=10, leading=15, textColor=INK, spaceAfter=8, splitLongWords=True),
    'muted': ParagraphStyle('muted', fontName='Helvetica', fontSize=9, leading=13, textColor=GRAY, spaceAfter=8, splitLongWords=True),
    'title': ParagraphStyle('title', fontName='Helvetica-Bold', fontSize=21, leading=26, textColor=INK, spaceAfter=14),
    'heading': ParagraphStyle('heading', fontName='Helvetica-Bold', fontSize=13, leading=18, textColor=INK, spaceBefore=16, spaceAfter=8, keepWithNext=True),
    'small': ParagraphStyle('small', fontName='Helvetica', fontSize=8, leading=11, textColor=INK, spaceAfter=2, splitLongWords=True),
    'metric': ParagraphStyle('metric', fontName='Helvetica-Bold', fontSize=23, leading=28, textColor=INK, spaceAfter=6),
}


def paragraph(text, style='body'):
    # Report text is data, never ReportLab markup.
    text = str(text).translate(str.maketrans({'–': '-', '—': '-', '‑': '-'}))
    return Paragraph(escape(text).replace('\n', '<br/>'), STYLES[style])


def grid(rows, widths, *, header=True, title=None):
    cells = [[paragraph(cell, 'small') for cell in row] for row in rows]
    if title:
        cells.insert(0, [paragraph(title, 'heading')] + [''] * (len(widths) - 1))
    table = Table(cells, colWidths=widths, repeatRows=(2 if title else 1) if header else 0, hAlign='LEFT')
    table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 9),
        ('RIGHTPADDING', (0, 0), (-1, -1), 9),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('LINEBELOW', (0, 0), (-1, -1), .5, BORDER),
        ('BACKGROUND', (0, 1 if title else 0), (-1, 1 if title else 0), colors.HexColor('#f5f5f5')) if header else
        ('BOX', (0, 0), (-1, -1), .5, BORDER),
    ]))
    if title:
        table.setStyle(TableStyle([('SPAN', (0, 0), (-1, 0)), ('LINEBELOW', (0, 0), (-1, 0), 0, colors.white),
                                  ('LEFTPADDING', (0, 0), (-1, 0), 0)]))
    return table


def bar_drawings(chart):
    points = {p['label']: p for p in chart['points']}
    layouts = chart.get('panels') or [{
        'series_order': ['Valor'], 'coordinates': [
            dict(category=p['label'], series='Valor', label=p['label']) for p in chart['points']],
        'colors': {'Valor': CHART_PALETTE[0]}, 'measure': 'level', 'title': '',
    }]
    for panel in layouts:
        categories = list(dict.fromkeys(c['category'] for c in panel['coordinates']))
        series = panel['series_order']
        mapped = {(c['category'], c['series']): points[c['label']] for c in panel['coordinates']}
        values = [Decimal(p['value']) for p in mapped.values()]
        low, high = min([Decimal(0)] + values), max([Decimal(0)] + values)
        if panel.get('measure') == 'change':
            extent = max(abs(low), abs(high))
            low, high = -extent, extent
        span = high - low or Decimal(1)
        left, plot_width = 142, WIDTH - 158
        def x(value):
            return left + float((Decimal(value) - low) / span) * plot_width
        category_lines = {c: textwrap.wrap(c, 27) for c in categories}
        row_height = max(len(series) * 13 + 28, max(len(lines) for lines in category_lines.values()) * 10 + 14)
        legend_lines = []
        line, used = [], 0
        for name in series:
            size = min(210, max(65, len(name) * 5 + 24))
            if used + size > WIDTH and line:
                legend_lines.append(line); line, used = [], 0
            line.append((name, used)); used += size
        legend_lines.append(line)
        legend_height = len(legend_lines) * 40
        rows_per_chunk = max(1, (600 - legend_height - 28) // row_height)
        # Chunk large charts with a common scale and repeated complete legend.
        for offset in range(0, len(categories), rows_per_chunk):
            batch = categories[offset:offset + rows_per_chunk]
            height = len(batch) * row_height + legend_height + 28
            drawing = Drawing(WIDTH, height)
            for line_index, entries in enumerate(legend_lines):
                for name, pos in entries:
                    shade = panel.get('colors', {}).get(name, CHART_PALETTE[0])
                    if shade not in CHART_PALETTE: shade = CHART_PALETTE[0]
                    y = height - 12 - line_index * 40
                    drawing.add(Rect(pos, y - 2, 6, 6, fillColor=colors.HexColor(shade), strokeColor=None))
                    for n, label in enumerate(textwrap.wrap(name, 36)):
                        drawing.add(String(pos + 10, y - n * 10, label, fontSize=8, fillColor=GRAY))
            drawing.add(Line(x(0), 22, x(0), height - legend_height - 7, strokeColor=GRAY, strokeWidth=.6))
            for t in range(5):
                value = low + span * Decimal(t) / 4
                tx = x(value)
                drawing.add(Line(tx, 22, tx, height - legend_height - 7, strokeColor=BORDER, strokeWidth=.3))
                drawing.add(String(tx, 8, number(readable_number(value) if chart.get('owner_presentation') else formatted(value, 0), chart.get('response_language')), fontSize=7, textAnchor='middle', fillColor=GRAY))
            for i, category in enumerate(batch):
                y = height - legend_height - 17 - i * row_height
                for n, label in enumerate(category_lines[category]):
                    drawing.add(String(left - 12, y - n * 10, label, textAnchor='end', fontSize=8, fillColor=GRAY))
                for j, name in enumerate(series):
                    point = mapped.get((category, name))
                    if point is None: continue  # Never turn missing cells into zero.
                    shade = panel.get('colors', {}).get(name, CHART_PALETTE[0])
                    if shade not in CHART_PALETTE: shade = CHART_PALETTE[0]
                    vx = x(point['value'])
                    drawing.add(Rect(min(x(0), vx), y - j * 13 - 9, max(.5, abs(vx - x(0))), 10,
                                     fillColor=colors.HexColor(shade), strokeColor=None, rx=2))
            yield panel.get('title', ''), drawing


def line_drawing(chart):
    from .chart_layout import temporal_cells
    points = chart['points']
    values = [Decimal(p['value']) for p in points]
    _, categories, indices, order, cells = temporal_cells(chart, points, values)
    bounds = [*values] if chart.get('scale') == 'data' else [Decimal(0), *values]
    low, high = min(bounds), max(bounds)
    span = high - low or Decimal(1)
    owner = chart.get('owner_presentation', False)
    legend_lines = []
    if owner:
        # One complete label per row, wrapping by measured glyph width. Truncating
        # a shared prefix can make different series indistinguishable.
        for name in order:
            lines, line = [], ''
            for character in name:
                if line and stringWidth(line + character, 'Helvetica', 9) > WIDTH - 92:
                    lines.append(line); line = ''
                line += character
            lines.append(line)
            legend_lines.append(lines)
    height = max(250, 225 + sum(len(lines) * 12 + 5 for lines in legend_lines)) if owner else 250
    drawing = Drawing(WIDTH, height)
    legend_y = height - 15
    def x(index): return 50 + (index - indices[0]) / (indices[-1] - indices[0] or 1) * (WIDTH - 64)
    def y(value): return 32 + float((value - low) / span) * 165
    for i in range(5):
        value = low + span * Decimal(i) / 4
        pos = y(value)
        drawing.add(Line(50, pos, WIDTH - 14, pos, strokeColor=BORDER, strokeWidth=.5))
        drawing.add(String(43, pos - 3, number(readable_number(value) if chart.get('owner_presentation') else formatted(value, 0), chart.get('response_language')), textAnchor='end', fontSize=8, fillColor=GRAY))
    palette = (chart.get('panels') or [{}])[0].get('colors', {})
    for i, name in enumerate(order):
        shade = palette.get(name, CHART_PALETTE[i % len(CHART_PALETTE)])
        style = (chart.get('panels') or [{}])[0].get('styles', {}).get(name, {})
        width = 2.8 if style.get('weight') == 'emphasis' else 1.5 if style else 1.8
        dash = {'dashed': [6, 4], 'dotted': [2, 3]}.get(style.get('style'), [])
        color = colors.HexColor(shade if shade in CHART_PALETTE else CHART_PALETTE[0])
        if owner:
            drawing.add(Line(50, legend_y + 3, 69, legend_y + 3, strokeColor=color, strokeWidth=width, strokeDashArray=dash))
            for line in legend_lines[i]:
                drawing.add(String(76, legend_y, line, fontSize=9, fillColor=INK))
                legend_y -= 12
            legend_y -= 5
        else:
            drawing.add(String(50 + (i%3)*135, 235 - (i//3)*15, name[:28], fontSize=8, fillColor=color))
        previous = None
        for category, index in zip(categories, indices):
            value = cells.get((category, name))
            if value is None:
                previous = None
                continue
            if previous and index - previous[0] == 1:
                drawing.add(Line(x(previous[0]), y(previous[1]), x(index), y(value), strokeColor=color, strokeWidth=width, strokeDashArray=dash))
            drawing.add(Circle(x(index), y(value), 2.5, fillColor=color, strokeColor=None))
            previous = index, value
    for i in sorted({0, len(categories)-1}):
        drawing.add(String(x(indices[i]), 12, categories[i], textAnchor='middle', fontSize=8, fillColor=GRAY))
    return drawing


def render_pdf(report):
    """Accept only a validated presentation obtained through the publication gate."""
    from .report_language import export_view, label
    report = export_view(report)
    tr = lambda text: label(text, report.get('response_language'))
    owner = report.get('owner_presentation', False)
    appendix = []
    stream = BytesIO()
    story = [paragraph('Decision Room', 'heading'), paragraph(report['scope'].get('business', ''), 'muted'),
             paragraph(report['scope']['period'], 'muted'),
             paragraph(tr('Revisado') + (tr(' · Entrega parcial') if report.get('partial') and not owner else ''), 'muted'),
             paragraph(report['title'], 'title')]
    if report.get('summary'): story.append(paragraph(report['summary']))
    for offset in range(0, len(report.get('highlights', [])), 3):
        batch = report['highlights'][offset:offset + 3]
        cells = [[paragraph(h['label'], 'muted'), paragraph(h['value'], 'metric'), paragraph(h['unit'], 'muted')] for h in batch]
        metrics = Table([cells], colWidths=[WIDTH / len(batch)] * len(batch))
        metrics.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP'), ('BOX', (0,0), (-1,-1), .5, BORDER),
                                    ('INNERGRID', (0,0), (-1,-1), .5, BORDER), ('TOPPADDING', (0,0), (-1,-1), 12),
                                    ('LEFTPADDING', (0,0), (-1,-1), 12), ('BOTTOMPADDING', (0,0), (-1,-1), 6)]))
        story += [Spacer(1, 8), metrics, Spacer(1, 8)]
        for h in batch:
            if h.get('unit_origin') == 'owner':
                story.append(paragraph(f"{h['label']}: {tr('unidad visible indicada por el propietario. Unidad del análisis:')} {h['original_unit']}.", 'muted'))
    story += [paragraph(tr('Contexto y alcance'), 'heading'), paragraph(report['scope']['coverage'], 'muted')]
    if report['scope'].get('question'):
        story += [paragraph(tr('Pregunta del análisis'), 'heading'), paragraph(report['scope']['question'])]
    for i, claim in enumerate(report['claims']):
        story += [paragraph(f"{i+1:02d} · {claim['title']}", 'heading'), paragraph(claim['statement'])]
        if claim.get('interpretation'): story.append(paragraph(claim['interpretation'], 'muted'))
        from .agent.delivery_contract import orientation_sections
        from .owner_presentation import guidance
        for heading, text in (guidance(claim) if owner else orientation_sections(claim.get('orientation'))):
            story.append(Paragraph('<b>' + escape(tr(heading)) + '</b>: ' + escape(text), STYLES['body']))
        if claim.get('next_step') and not claim.get('orientation'):
            story += [paragraph(tr('Siguiente comprobación'), 'heading'), paragraph(claim['next_step'])]
        if owner and claim.get('source_summary'):
            story.append(paragraph(claim['source_summary'], 'muted'))
        for chart in report.get('charts', []):
            if chart['claim_key'] != claim['key']: continue
            chart_heading = [paragraph(chart['title'], 'heading'), paragraph(chart['unit'], 'muted')]
            if chart.get('unit_origin') == 'owner':
                chart_heading.append(paragraph(f"{tr('Unidad visible indicada por el propietario. Unidad del análisis:')} {chart['original_unit']}.", 'muted'))
            if chart['kind'] == 'bar':
                for panel_title, drawing in bar_drawings(chart):
                    # Keep the overall heading with its first diagram, too.
                    story.append(KeepTogether(chart_heading +
                                              ([paragraph(panel_title, 'heading')] if panel_title else []) + [drawing]))
                    chart_heading = []
            elif chart['kind'] == 'line':
                story.append(KeepTogether(chart_heading + [line_drawing(chart)]))
            else:
                story += chart_heading
            story.append(paragraph(chart['caption'], 'muted'))
            for detail in chart.get('details', []):
                story.append(paragraph(detail['point_label'] + ': ' + '; '.join(v['label'] + ': ' + v['formatted'] + ' ' + v['unit'] for v in detail['values'])))
            from .chart_layout import comparison_tables
            for title, headings, rows in comparison_tables(chart, chart['points'], [p['formatted'] for p in chart['points']]):
                if not owner or chart['kind'] == 'table':
                    story.append(grid([headings, *rows], [WIDTH/len(headings)]*len(headings), title=title or tr('Valores exactos')))
            if owner:
                appendix.append(grid([[tr('Periodo / categoría'), chart['unit']],
                                      *[[p.get('original_label', p['label']), p['value']] for p in chart['points']]],
                                     [WIDTH * .65, WIDTH * .35], title=chart['title']))
        detail_story = appendix if owner else story
        if owner:
            detail_story.append(paragraph(claim['title'], 'heading'))
        if claim.get('method'):
            detail_story += [paragraph(tr('Cómo se ha calculado'), 'heading'), paragraph(claim['method'])]
        details = claim.get('evidence_details')
        if details:
            detail_story += [paragraph(tr('Fuentes y evidencia'), 'heading')]
            for name in details['files']: detail_story.append(paragraph(name, 'muted'))
            if details['metrics']:
                detail_story.append(grid([[tr('Resultado guardado'), tr('Valor')]] +
                                  [[m.get('original_label', m['label']), m.get('raw_value', m['value'])] for m in details['metrics']], [WIDTH * .65, WIDTH * .35]))
            for operation in details['operations']: detail_story.append(paragraph(operation, 'muted'))
    if report.get('no_chart_reason'): story.append(paragraph(report['no_chart_reason'], 'muted'))
    if report.get('owner_coverage') and not owner:
        story.append(paragraph(tr('Cobertura del encargo'), 'heading'))
        names = {'complete':'Completo','partial':'Parcial','unavailable':'Información no disponible','deferred':'Pendiente'}
        for q in report['owner_coverage']:
            story.append(paragraph(tr(names[q['status']]) + ': ' + q['explanation']))
    elif report.get('question_coverage') and not owner:
        story.append(paragraph(tr('Cobertura de las preguntas'), 'heading'))
        names = {'answered': 'Respondida', 'unavailable': 'Información no disponible', 'deferred': 'Pendiente'}
        for q in report['question_coverage']:
            story.append(paragraph(tr(names[q['status']]) + ': ' + q['explanation']))
    if report.get('limitations'):
        story.append(paragraph(tr('Limitaciones'), 'heading'))
        for item in report['limitations']: story.append(paragraph('• ' + item, 'muted'))

    if owner:
        appendix.extend(paragraph(note, 'muted') for note in report.get('technical_notes', []))
    if owner and appendix:
        story += [PageBreak(), paragraph(tr('Fuentes, cálculos y valores originales'), 'title'), *appendix]

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(BORDER); canvas.line(44, 39, A4[0] - 44, 39)
        canvas.setFont('Helvetica', 8); canvas.setFillColor(GRAY)
        canvas.drawString(44, 25, tr('Decision Room · Informe revisado'))
        canvas.drawRightString(A4[0] - 44, 25, str(doc.page))
        canvas.restoreState()

    doc = SimpleDocTemplate(stream, pagesize=A4, leftMargin=44, rightMargin=44,
                            topMargin=38, bottomMargin=52, title=report['title'], author='Decision Room')
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return stream.getvalue()
