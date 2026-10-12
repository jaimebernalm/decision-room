"""PDF of a native v1 report from its validated block projection.

Platform template only: every string is escaped data, never agent markup. Charts are
vector drawings followed by their exact values, so nothing depends on reading a drawing.
Disputed figures carry the same notice as on screen; nothing is ever marked verified.
"""
from datetime import datetime
from decimal import Decimal
from html import escape
from io import BytesIO

from reportlab.graphics.shapes import Drawing, Line, PolyLine, Rect, String, Circle
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ..chart_layout import CHART_NEUTRALS, CHART_SEMANTIC, CHART_SERIES_PALETTE
from ..engine.blocks import action_label, cell_decimals, format_number
from ..report_pdf import BORDER, GRAY, INK, STYLES, WIDTH as PAGE_WIDTH, grid, paragraph

WIDTH = PAGE_WIDTH - 12  # frame padding
MAX_DRAWING_HEIGHT = 620
LABELLED_BARS = 24  # value labels on columns up to this many bars
LEGEND_ITEM = 110  # points per legend entry

AMBER = colors.HexColor('#fff7e6')
AMBER_LINE = colors.HexColor('#e0a33a')
NOTICE = ParagraphStyle('notice', parent=STYLES['body'], backColor=AMBER, borderColor=AMBER_LINE, borderWidth=.6,
                        borderPadding=7, spaceBefore=6, spaceAfter=12)
SUBHEAD = ParagraphStyle('subhead', parent=STYLES['heading'], fontSize=11, leading=15, spaceBefore=10)
PRIORITY = ParagraphStyle('priority', parent=STYLES['heading'], fontSize=14, leading=19)
COVER_TITLE = ParagraphStyle('cover_title', parent=STYLES['title'], spaceAfter=10)
COVER_EYEBROW = ParagraphStyle('cover_eyebrow', parent=STYLES['muted'], fontSize=10, leading=14)
COVER_BODY = ParagraphStyle('cover_body', parent=STYLES['body'], fontSize=11, leading=17, textColor=GRAY)
PANEL_TITLE = ParagraphStyle('panel_title', parent=STYLES['heading'], spaceBefore=0, fontSize=12, leading=16)
PANEL_LABEL = ParagraphStyle('panel_label', parent=PANEL_TITLE, fontSize=11, leading=15, spaceAfter=5)
PANEL_BACKGROUND = colors.HexColor('#f8f8f8')


def _text(value):
    return escape(str(value).translate(str.maketrans({'–': '-', '—': '-', '‑': '-', '−': '-'})))


def _spans(spans):
    out = []
    for s in spans:
        text = _text(s['text']).replace('\n', '<br/>')
        if s['italic']:
            text = f'<i>{text}</i>'
        if s['bold']:
            text = f'<b>{text}</b>'
        out.append(text)
    return ''.join(out)


def _content(content, style='body'):
    flow = []
    for node in content:
        if node['kind'] == 'paragraph':
            flow.append(Paragraph(_spans(node['spans']), STYLES[style] if isinstance(style, str) else style))
        else:
            for i, item in enumerate(node['items'], 1):
                marker = f'{i}.' if node['ordered'] else '•'
                parent = COVER_BODY if style is COVER_BODY else STYLES['body']
                flow.append(Paragraph(f'{marker} {_spans(item)}', ParagraphStyle('item', parent=parent, leftIndent=14,
                                                                                  firstLineIndent=-10, spaceAfter=3)))
    return flow


class _Panel(Table):
    def split(self, available_width, available_height):
        # ReportLab can leave a continuation containing only bottom padding after all
        # paragraphs fit. Dropping that empty fragment prevents a blank report page.
        parts = super().split(available_width, available_height)
        has_content = lambda part: any(cell for row in part._cellvalues for cell in row)
        if parts and not has_content(parts[0]):
            return []  # Only padding fit: defer the whole panel to the next frame.
        if parts:
            first = [item for row in parts[0]._cellvalues for cell in row for item in cell]
            if first and all(item.getKeepWithNext() for item in first):
                return []  # A card/branch heading alone must move with its first body line.
        return [part for part in parts if has_content(part)]


def _panel(parts, width=WIDTH):
    """A light, splittable platform panel; even a single long paragraph can cross pages."""
    table = _Panel([[parts]], colWidths=[width], hAlign='LEFT', splitInRow=1, spaceAfter=10)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), PANEL_BACKGROUND),
        ('LEFTPADDING', (0, 0), (-1, -1), 12), ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 12), ('BOTTOMPADDING', (0, 0), (-1, -1), 9),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    return table


def _cover(block, eyebrow=''):
    parts = [Paragraph(_text(eyebrow), COVER_EYEBROW)] if eyebrow else []
    return parts + [Paragraph(_text(block['title']), COVER_TITLE), *_content(block['content'], COVER_BODY)]


def _tone_mark(tone):
    """Small declared-tone symbol, as on screen; surfaces remain neutral."""
    drawing = Drawing(16, 16)
    drawing.add(Circle(6, 8, 5, fillColor=colors.HexColor(CHART_SEMANTIC[tone]), strokeColor=None))
    if tone in ('positive', 'negative'):
        start, tip = (5, 11) if tone == 'positive' else (11, 5)
        wing = tip - 2 if tone == 'positive' else tip + 2
        for x1, y1, x2, y2 in ((6, start, 6, tip), (4, wing, 6, tip), (8, wing, 6, tip)):
            drawing.add(Line(x1, y1, x2, y2, strokeColor=colors.white, strokeWidth=.8))
    elif tone == 'warning':
        drawing.add(String(6, 5, '!', fontName='Helvetica-Bold', fontSize=8, fillColor=colors.white, textAnchor='middle'))
    else:
        drawing.add(Circle(6, 8, .7, fillColor=colors.white, strokeColor=None))
    return drawing


def _card_heading(card, width, label):
    title = Paragraph(_text(card['title']), PANEL_LABEL if label else PANEL_TITLE)
    if not card.get('tone'):
        return title
    heading = Table([[_tone_mark(card['tone']), title]], colWidths=[16, width - 40], hAlign='LEFT', spaceAfter=8)
    heading.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                                ('TOPPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 0)]))
    heading.keepWithNext = True
    return heading


def _cards(cards, *, label=False):
    """Two short cards share a row. Three cards or long contents remain fully paginable."""
    def parts(card, width=WIDTH):
        return [_card_heading(card, width, label), *_content(card['content'])]
    if len(cards) == 2:
        width = (WIDTH - 12) / 2
        panels = [_panel(parts(c, width), width) for c in cards]
        if all(p.wrap(width, 10000)[1] <= 280 for p in panels):
            table = Table([[panels[0], '', panels[1]]], colWidths=[width, 12, width], hAlign='LEFT', spaceAfter=10)
            table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                      ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                                      ('TOPPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 0)]))
            return [table]
    return [_panel(parts(c)) for c in cards]


def _action(block):
    flow = [Paragraph(_text(action_label(block, 'check')), PANEL_LABEL), *_content(block['check'])]
    branches = [dict(title=action_label(block, key), content=block[key])
                for key in ('if_confirmed', 'if_not') if block[key] is not None]
    return flow + _cards(branches, label=True)


def _unit(value, decimals, unit):
    text = format_number(value, decimals)
    if value is None or not unit:
        return text
    return f'{text} %' if unit == '%' else f'{text} {unit}'


GOOD_HINT = {'up': 'según el informe, es mejor que suba', 'down': 'según el informe, es mejor que baje'}


def judged(change, good):
    """Favourable or unfavourable only when the report declares which direction is good."""
    if not good or not change:
        return None
    return 'positive' if (change > 0) == (good == 'up') else 'negative'


def _series_colors(series):
    """As in the web view: a declared tone wins; the rest share the spread, the last one darkest."""
    plain = sum(1 for s in series if not s.get('tone'))
    out, k = [], 0
    for s in series:
        if s.get('tone'):
            out.append(colors.HexColor(CHART_SEMANTIC[s['tone']]))
            continue
        position = plain - 1 - k
        k += 1
        out.append(_color(position, plain))
    return out


def _lightness(hex_color):
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return .299 * r + .587 * g + .114 * b


BY_LIGHTNESS = sorted(CHART_SERIES_PALETTE, key=_lightness)


def _color(i, count=1):
    """Same spread as the web view: dark to light so neighbouring series stay distinguishable."""
    if count <= 1:
        return colors.HexColor(CHART_SERIES_PALETTE[0])
    if count > len(BY_LIGHTNESS):
        return colors.HexColor(CHART_SERIES_PALETTE[i % len(CHART_SERIES_PALETTE)])
    last = len(BY_LIGHTNESS) - (1 if count >= len(BY_LIGHTNESS) else 2)
    # Half-up like JavaScript's Math.round, so web and PDF pick the same tone.
    return colors.HexColor(BY_LIGHTNESS[int(i * last / (count - 1) + .5)])


def _short(text, n=24):
    return text if len(text) <= n else text[:n - 1] + '…'


def _total_label(total, partial, decimals):
    return format_number(total, decimals) + (' (parcial)' if partial else '')


def chart_drawing(chart):
    """Vector drawing for bar, column, line, change and stacked charts (None for tables)."""
    kind, cats, series = chart['kind'], chart['categories'], chart['series']
    values = [v for s in series for v in s['values'] if v is not None]
    if kind == 'table' or not values:
        return None
    stacked = kind in ('stacked_column', 'stacked_bar')
    palette = _series_colors(series)
    # A gap is not a zero: a category with no values has no total, one with some gaps a partial one.
    known = [[s['values'][c] for s in series if s['values'][c] is not None] for c in range(len(cats))]
    totals = [sum(k) if k else None for k in known]
    partial = [0 < len(k) < len(series) for k in known]
    if stacked:
        values = [t for t in totals if t is not None]
    low, high = min(0, min(values)), max(0, max(values))
    if kind == 'change':
        extent = max(abs(low), abs(high)) or 1
        low, high = -extent, extent
    span = (high - low) or 1
    per_row = max(1, int(WIDTH // LEGEND_ITEM))
    legend = 18 * -(-len(series) // per_row) if len(series) > 1 else 0  # wrapped rows, height reserved
    if kind in ('bar', 'change', 'stacked_bar'):
        row = (1 if stacked else len(series)) * 12 + 10
        height = legend + len(cats) * row + 20
        if height > MAX_DRAWING_HEIGHT:
            return 'dense'
        d = Drawing(WIDTH, height)
        left, right = 150, WIDTH - 60
        x = lambda v: left + (v - low) / span * (right - left)
        zero = x(0)
        d.add(Line(zero, 10, zero, height - legend, strokeColor=GRAY, strokeWidth=.6))
        for c, cat in enumerate(cats):
            top = height - legend - c * row - 6
            d.add(String(left - 6, top - row / 2, _short(cat), fontName='Helvetica', fontSize=7.5, fillColor=INK, textAnchor='end'))
            if stacked:
                start, y = 0, top - 12
                for i, s in enumerate(series):
                    v = s['values'][c]
                    if v:
                        d.add(Rect(x(start), y, x(start + v) - x(start), 9, fillColor=palette[i], strokeColor=None))
                        start += v
                if totals[c] is not None:
                    d.add(String(right + 4, y + 1.5, _total_label(totals[c], partial[c], chart['decimals']),
                                 fontName='Helvetica', fontSize=7, fillColor=GRAY))
                continue
            for i, s in enumerate(series):
                v = s['values'][c]
                if v is None:
                    continue
                y = top - (i + 1) * 12
                verdict = judged(v, chart.get('good')) if kind == 'change' and len(series) == 1 else None
                fill = (colors.HexColor(CHART_SEMANTIC[verdict]) if verdict else
                        colors.HexColor(CHART_NEUTRALS['reference']) if kind == 'change' and len(series) == 1 and v < 0 else palette[i])
                d.add(Rect(min(x(v), zero), y, abs(x(v) - zero) or .5, 9, fillColor=fill, strokeColor=None))
                d.add(String(right + 4, y + 1.5, format_number(v, chart['decimals']), fontName='Helvetica', fontSize=7, fillColor=GRAY))
    else:
        height = 170 + legend
        d = Drawing(WIDTH, height)
        left, bottom, top = 50, 28, height - legend - 8
        y = lambda v: bottom + (v - low) / span * (top - bottom)
        step = (WIDTH - left - 10) / max(len(cats), 1)
        d.add(Line(left, y(0), WIDTH - 10, y(0), strokeColor=GRAY, strokeWidth=.6))
        for label in (low, high):
            d.add(String(left - 4, y(label) - 3, format_number(label, 0), fontName='Helvetica', fontSize=7, fillColor=GRAY, textAnchor='end'))
        every = max(1, len(cats) // 12)
        for c, cat in enumerate(cats):
            if c % every == 0:
                d.add(String(left + step * (c + .5), 12, _short(cat, 10), fontName='Helvetica', fontSize=7, fillColor=INK, textAnchor='middle'))
        if kind == 'stacked_column':
            base = [0] * len(cats)
            for i, s in enumerate(series):
                for c, v in enumerate(s['values']):
                    if v:
                        x0 = left + step * c + step * .2
                        d.add(Rect(x0, y(base[c]), step * .6, y(base[c] + v) - y(base[c]), fillColor=palette[i], strokeColor=None))
                        base[c] += v
            if len(cats) <= LABELLED_BARS:
                for c, total in enumerate(totals):
                    if total is not None:
                        d.add(String(left + step * (c + .5), y(total) + 3, _total_label(total, partial[c], chart['decimals']),
                                     fontName='Helvetica', fontSize=6.5, fillColor=GRAY, textAnchor='middle'))
        for i, s in enumerate(series if kind != 'stacked_column' else []):
            if kind == 'column':
                width = step * .7 / len(series)
                for c, v in enumerate(s['values']):
                    if v is not None:
                        x0 = left + step * c + step * .15 + i * width
                        d.add(Rect(x0, min(y(v), y(0)), width, abs(y(v) - y(0)) or .5, fillColor=palette[i], strokeColor=None))
                        if len(cats) * len(series) <= LABELLED_BARS:
                            d.add(String(x0 + width / 2, (y(v) + 3) if v >= 0 else (y(v) - 9), format_number(v, chart['decimals']),
                                         fontName='Helvetica', fontSize=6.5, fillColor=GRAY, textAnchor='middle'))
            else:
                segment = []
                for c, v in enumerate(s['values'] + [None]):
                    if v is None:
                        if len(segment) >= 4:
                            d.add(PolyLine(segment, strokeColor=palette[i], strokeWidth=1.6))
                        segment = []
                        continue
                    px, py = left + step * (c + .5), y(v)
                    segment += [px, py]
                    d.add(Circle(px, py, 2, fillColor=palette[i], strokeColor=None))
    if legend:
        for i, s in enumerate(series):
            lx, ly = 10 + (i % per_row) * LEGEND_ITEM, height - 12 - (i // per_row) * 18
            d.add(Rect(lx, ly, 8, 8, fillColor=palette[i], strokeColor=None))
            d.add(String(lx + 12, ly + 1, _short(s['name'], 18), fontName='Helvetica', fontSize=7.5, fillColor=INK))
    return d


def _chart(chart, appendix):
    """Title and drawing kept together; exact values go to the appendix, not under every chart.

    Only charts that cannot be drawn (tables, too dense) show their values inline.
    """
    head = chart['title'] + (f" ({chart['unit']})" if chart['unit'] else '')
    flow = [Paragraph(_text(head), SUBHEAD)]
    drawing = chart_drawing(chart)
    if drawing is not None and drawing != 'dense':
        flow.append(drawing)
        if chart['note']:
            flow.append(paragraph(chart['note'], 'muted'))
        appendix.append(chart)
        return flow
    if drawing == 'dense':
        flow.append(paragraph('Gráfico demasiado denso para una página: sus valores completos están en la tabla.', 'muted'))
    return flow + _values(chart)


def _exact(value, decimals):
    """Every delivered decimal in the values table, as in the web data view (1.123e-15 keeps 18)."""
    if value is None:
        return decimals
    exponent = Decimal(str(value)).normalize().as_tuple().exponent
    return max(decimals, -exponent if exponent < 0 else 0)


def _values(chart, note=True):
    flow = []
    rows = [[chart['category_title'] or 'Categoría'] + [s['name'] for s in chart['series']]]
    for c, cat in enumerate(chart['categories']):
        rows.append([cat] + [_unit(s['values'][c], _exact(s['values'][c], chart['decimals']), chart['unit']) +
                             (f" ({s['details'][c]})" if s['details'] and s['details'][c] else '') for s in chart['series']])
    cols = len(rows[0])
    first = min(170, WIDTH * .4)
    flow.append(_right_align(grid(rows, [first] + [(WIDTH - first) / (cols - 1)] * (cols - 1)), range(1, cols)))
    if note and chart['note']:
        flow.append(paragraph(chart['note'], 'muted'))
    return flow


NUMERIC_CELL = ParagraphStyle('blocks-number', parent=STYLES['small'], alignment=2)


def _right_align(table, columns):
    """Numbers align right, as in the web view (the shared grid builds left-aligned cells)."""
    for row in table._cellvalues:
        for c in columns:
            if isinstance(row[c], Paragraph):
                row[c].style = NUMERIC_CELL
    return table


def _table(block):
    rows = [[c['title'] + (f" ({c['unit']})" if c['unit'] else '') for c in block['columns']]]
    for r in block['rows']:
        rows.append(['' if v is None else v if isinstance(v, str) else
                     ('+' if c.get('signed') and v > 0 else '') + format_number(v, cell_decimals(v, c['decimals']))
                     for v, c in zip(r, block['columns'])])
    numeric = [c for c in range(len(block['columns']))
               if any(r[c] is not None for r in block['rows']) and all(not isinstance(r[c], str) for r in block['rows'])]
    flow = [Paragraph(_text(block['title']), SUBHEAD)] if block['title'] else []
    table = _right_align(grid(rows, [WIDTH / len(block['columns'])] * len(block['columns'])), numeric)
    for r, row in enumerate(block['rows'], 1):
        for c, (v, column) in enumerate(zip(row, block['columns'])):
            verdict = judged(v, column.get('good')) if isinstance(v, (int, float)) and column.get('signed') else None
            if verdict and isinstance(table._cellvalues[r][c], Paragraph):
                table._cellvalues[r][c].style = ParagraphStyle(f'blocks-{verdict}', parent=NUMERIC_CELL,
                                                               textColor=colors.HexColor(CHART_SEMANTIC[verdict]))
    flow.append(table)
    if block['note']:
        flow.append(paragraph(block['note'], 'muted'))
    return flow


def _figure_cell(block):
    """One figure as a card cell (label, value, period, comparison), for the figure grid."""
    return _figure(block, boxed=False)[0]


GRID_NOTE = 300  # longer notes would make an indivisible grid row taller than a page


def gridable(block, checks):
    """Short, undisputed figures go in the card grid; others stay standalone next to their notice."""
    disputed = any(c.get('status') == 'discrepancy' for c in checks.get(block['id'], []))
    return not disputed and len(block.get('note') or '') <= GRID_NOTE and len(block['label']) <= 200


def _figure_grid(figures):
    """Consecutive figures as a grid of cards, like the web view (3 per row)."""
    rows = [[_figure_cell(f) for f in figures[i:i + 3]] for i in range(0, len(figures), 3)]
    for row in rows:
        row += [''] * (3 - len(row))
    table = Table(rows, colWidths=[WIDTH / 3] * 3, hAlign='LEFT')
    table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('BOX', (0, 0), (-1, -1), .6, BORDER),
                               ('INNERGRID', (0, 0), (-1, -1), .6, BORDER), ('LEFTPADDING', (0, 0), (-1, -1), 9),
                               ('RIGHTPADDING', (0, 0), (-1, -1), 9), ('TOPPADDING', (0, 0), (-1, -1), 8),
                               ('BOTTOMPADDING', (0, 0), (-1, -1), 8)]))
    return [Spacer(1, 4), table, Spacer(1, 10)]


def _figure(block, boxed=True):
    value = _unit(block['value'], block['decimals'], block['unit'])
    lines = [f"<font size=9 color='#707070'>{_text(block['label'])}</font>",
             f"<font name='Helvetica-Bold' size=16>{_text(value)}</font>"]
    if block['period']:
        lines.append(f"<font size=8 color='#707070'>{_text(block['period'])}</font>")
    if block['previous']:
        prev = block['previous']
        text = 'Antes: ' + _unit(prev['value'], block['decimals'], block['unit'])
        if prev['period']:
            text += f" ({prev['period']})"
        if block['change'] is not None:
            change = ('+' if block['change'] > 0 else '') + _unit(block['change'], block['decimals'], block['unit'])
            if block['change_pct'] is not None:
                change += f" ({'+' if block['change_pct'] > 0 else ''}{format_number(block['change_pct'], 1)} %)"
            verdict = judged(block['change'], block.get('good'))
            tone = CHART_SEMANTIC[verdict] if verdict else '#1a1a1a'
            lines.append(f"<font name='Helvetica-Bold' size=10 color='{tone}'>{_text(change)}</font>"
                         + (f" <font size=7 color='#707070'>({_text(GOOD_HINT[block['good']])})</font>" if verdict else ''))
        lines.append(f"<font size=8 color='#707070'>{_text(text)}</font>")
    if block['note']:
        lines.append(f"<font size=8 color='#707070'>{_text(block['note'])}</font>")
    style = (ParagraphStyle('figure', parent=STYLES['body'], borderColor=BORDER, borderWidth=.6, borderPadding=8,
                            spaceBefore=6, spaceAfter=12, leading=17) if boxed else
             ParagraphStyle('figure-cell', parent=STYLES['body'], leading=17, spaceAfter=0))
    return [Paragraph('<br/>'.join(lines), style)]


def _checks(items):
    disputed = [c for c in items if c['status'] == 'discrepancy']
    if not disputed:
        return []
    lines = ['<b>Cifra en revisión:</b> una comprobación independiente no obtuvo el mismo resultado. Revísala antes de decidir.']
    for c in disputed:
        text = f"«{_text(c['quote'])}»"
        if c.get('independent_value'):
            text += f" — cálculo independiente: {_text(c['independent_value'])}"
        lines.append(text)
    return [Paragraph('<br/>'.join(lines), NOTICE)]


def _blocks(blocks, checks, depth, numbers, appendix):
    flow, figures = [], []

    def flush():
        if figures:
            flow.extend(_figure_grid(figures))
            figures.clear()
    for b in blocks:
        kind = b['type']
        if kind == 'figure' and gridable(b, checks):
            figures.append(b)
            continue
        flush()
        if kind == 'figure':
            # Disputed or long figures stay splittable, each followed by its own notice.
            flow += _figure(b) + _checks(checks.get(b['id'], []))
            continue
        own = _checks(checks.get(b['id'], []))
        if kind == 'section':
            flow.append(Paragraph(_text(b['title']), STYLES['heading'] if depth == 0 else SUBHEAD))
            flow += _blocks(b['blocks'], checks, depth + 1, numbers, appendix)
        elif kind == 'priority':
            flow.append(Paragraph(f"Prioridad {numbers[b['id']]:02d} · {_text(b['title'])}", PRIORITY))
            flow += own
            flow += _blocks(b['blocks'], checks, depth + 1, numbers, appendix)
            own = []
        elif kind == 'text':
            flow += _content(b['content'])
        elif kind == 'cover':
            flow += _cover(b)
        elif kind == 'cards':
            flow += _cards(b['cards'])
        elif kind == 'action':
            flow += _action(b)
        elif kind == 'notice':
            flow += _content(b['content'], NOTICE)
        elif kind == 'chart':
            parts = _chart(b, appendix)
            flow.append(KeepTogether(parts[:2]))
            flow += parts[2:]
        elif kind == 'table':
            flow += _table(b)
        flow += own
    flush()
    return flow


def render(projection, checks=None, *, delivered_at=None):
    """Bytes of a complete PDF; raises nothing for valid projections."""
    from ..engine.blocks import walk
    by_block = {}
    for item in (checks or {}).get('items', []):
        by_block.setdefault(item['block_id'], []).append(item)
    numbers = {}
    for b in walk(projection['blocks']):
        if b['type'] == 'priority':
            numbers[b['id']] = len(numbers) + 1
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=44, rightMargin=44, topMargin=44, bottomMargin=44,
                            title=projection['title'], author='Decision Room')
    report_blocks = projection['blocks']
    cover = report_blocks[0] if report_blocks and report_blocks[0]['type'] == 'cover' else None
    story = _cover(cover, projection['title']) if cover else [Paragraph(_text(projection['title']), STYLES['title'])]
    if cover:
        story += _checks(by_block.get(cover['id'], []))
        report_blocks = report_blocks[1:]
    if delivered_at:
        stamp = delivered_at.strftime('%d/%m/%Y') if isinstance(delivered_at, datetime) else str(delivered_at)
        story.append(paragraph(f'Informe entregado el {stamp}. Texto escrito por el motor de informes; '
                               'las cifras en revisión llevan aviso.', 'muted'))
    appendix = []
    story += _blocks(report_blocks, by_block, 0, numbers, appendix)
    if appendix:
        # Exact values stay available for print, once, after the report instead of under each chart.
        story.append(Spacer(1, 12))
        story.append(Paragraph('Valores de los gráficos', SUBHEAD))
        for chart in appendix:
            story.append(KeepTogether([paragraph(chart['title'] + (f" ({chart['unit']})" if chart['unit'] else ''), 'muted')]
                                      + _values(chart, note=False)))
    unverifiable = [c for c in (checks or {}).get('items', []) if c['status'] == 'unverifiable' and not c.get('coverage')]
    uncovered = [c for c in (checks or {}).get('items', []) if c.get('coverage')]
    if unverifiable or uncovered:
        # Limits of the independent check: one plain summary in a discreet appendix, never the
        # repeated per-priority coverage messages (no extra text).
        story.append(Spacer(1, 12))
        story.append(Paragraph('Detalles de la comprobación independiente', SUBHEAD))
        summary = (checks or {}).get('coverage') or {}
        text = ''
        if summary.get('numeric_spans'):
            text = (f"Se examinaron {format_number(summary['addressed_spans'], 0)} de los "
                    f"{format_number(summary['numeric_spans'], 0)} números citados en las prioridades; "
                    f"{format_number(summary['confirmed_spans'], 0)} coincidieron al recalcularlos con los datos. ")
        story.append(paragraph(text + 'Una cifra sin recalcular no está marcada como errónea; '
                               'solo no se revisó por separado.', 'muted'))
        if unverifiable:
            story.append(paragraph('Cifras que no se pudieron recalcular:', 'muted'))
            for c in unverifiable:
                story.append(paragraph(f"«{c['quote']}»" + (f" — {c['message']}" if c.get('message') else ''), 'muted'))
    if checks and checks.get('state') in ('incomplete', 'unknown'):
        story.append(Paragraph('La comprobación independiente de cifras no se pudo completar para este informe.', NOTICE))
    doc.build(story)
    return buffer.getvalue()
