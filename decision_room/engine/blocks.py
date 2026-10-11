"""Native v1 report format: free content delivered as data blocks, never markup.

The agent decides what to say, in which order and how much; this module only fixes how
the content is delivered. It is standard-library only so the very same file is mounted
in the engine container as ``comprobar_informe`` (the agent's optional self-check) and
used by the product, which always re-validates the stored bytes with the same version.

parse(raw) -> document (strict JSON, limits, schema) or BlocksError with Spanish messages.
project(document) -> platform projection: English types, path ids, computed changes and
chart fallbacks. canonical_text(projection) -> plain text for chat and search.
priorities(projection) -> priority blocks with their text, for the independent check.
"""
import json
import re
import sys
from decimal import Decimal, ROUND_HALF_UP, localcontext

VERSION = 'informe-bloques-1'
PROJECTOR_VERSION = 'bloques-proyector-1'
MAX_BYTES = 256 * 1024
MAX_BLOCKS = 300            # every block, nested ones included
MAX_DEPTH = 4               # seccion > seccion > prioridad > contenido
MAX_TEXT = 150_000          # characters across all strings
MAX_STRING = 4_000
MAX_TITLE = 200
MAX_CATEGORIES = 60
MAX_SERIES = 8
MAX_POINTS = 4_000          # chart values across the report
MAX_COLUMNS = 12
MAX_ROWS = 200
MAX_CELLS = 6_000           # table cells across the report
MAX_NUMBER = Decimal(10) ** 15
MIN_NUMBER = Decimal(10) ** -15

CHART_KINDS = {'barras': 'bar', 'barras_horizontales': 'bar', 'columnas': 'column', 'barras_verticales': 'column',
               'lineas': 'line', 'linea': 'line', 'cambio': 'change', 'barras_cambio': 'change'}
CONTROL = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\ud800-\udfff]')

FORMAT_GUIDE = '''Formato de informe.json (versión informe-bloques-1)

Decides tú qué contar, en qué orden y cuánto. Solo cambia la forma de entregarlo: escribe
datos, nunca HTML, CSS ni código. La plataforma lo presenta con su diseño y dibuja los
gráficos y las tablas.

{"version": "informe-bloques-1", "titulo": "...", "bloques": [ ...bloques... ]}

Bloques (campo "tipo"); los marcados con ? son opcionales:
- seccion:   {"tipo":"seccion","titulo":"...","bloques":[...]}
- texto:     {"tipo":"texto","contenido": CONTENIDO}
- cifra:     {"tipo":"cifra","etiqueta":"...","valor":123.4,"unidad"?:"€","decimales"?:2,
              "periodo"?:"ene–ago 2026","anterior"?:{"valor":100,"periodo"?:"ene–ago 2025"},"nota"?:"..."}
             Si das "anterior", la plataforma calcula la diferencia y el porcentaje.
- grafico:   {"tipo":"grafico","grafico":"barras|columnas|lineas|cambio","titulo":"...",
              "categorias":["ene","feb",...],
              "series":[{"nombre":"2026","valores":[1,2,null,...],"detalles"?:["107 de 1.240",...]}],
              "unidad"?:"%","decimales"?:1,"eje_categorias"?:"Mes","eje_valores"?:"Tasa","nota"?:"..."}
             barras = horizontales; columnas = verticales; lineas = evolución; cambio = barras con signo
             y eje cero. Usa null para un hueco (no es un cero). "detalles" se muestra al pasar el ratón
             (por ejemplo, numerador y denominador). Otro tipo de gráfico se mostrará como tabla.
- tabla:     {"tipo":"tabla","titulo"?:"...","columnas":["Producto",{"titulo":"Importe","unidad":"€","decimales":2}],
              "filas":[["Magnesio",1234.5],...],"nota"?:"..."}   (celdas: texto, número o null)
- prioridad: {"tipo":"prioridad","titulo":"...","bloques":[...]}   (dentro, lo que quieras)
- aviso:     {"tipo":"aviso","contenido": CONTENIDO}

CONTENIDO es un texto (los párrafos se separan con una línea en blanco) o una lista de:
- "un párrafo" o {"parrafo":[FRAGMENTO,...]}
- {"lista":[ "elemento" o [FRAGMENTO,...], ... ], "numerada"?: true}
FRAGMENTO es "texto" o {"texto":"...","negrita"?:true,"cursiva"?:true}.

Números: valores numéricos de JSON (1234.5), sin separadores de miles ni símbolos; la unidad va
en "unidad". Con "unidad": "%" el valor ya está en porcentaje (13.7 es 13,7 %). La plataforma da
formato español a los números. Como mucho 15 cifras significativas.
Límites: 256 KB, 300 bloques, 4 niveles, 60 categorías y 8 series por gráfico, 12 columnas y
200 filas por tabla.
Comprueba el fichero con: python3 /inputs/herramientas/comprobar_informe.py /work/informe.json
'''


class BlocksError(ValueError):
    def __init__(self, problems):
        self.problems = list(problems)[:50]
        super().__init__('; '.join(self.problems))


def _no_duplicates(pairs):
    seen = {}
    for key, value in pairs:
        if key in seen:
            raise ValueError(f'clave repetida «{key}»')
        seen[key] = value
    return seen


def _constant(name):
    raise ValueError(f'valor no permitido {name}')


def _decimal(lexeme):
    # Lexical bound before conversion: no huge exponents or precision reach Decimal.
    if len(lexeme) > 40:
        raise ValueError('número con demasiadas cifras')
    try:
        number = Decimal(lexeme)
        digits = len(number.normalize().as_tuple().digits) if number else 0
        in_range = not number or MIN_NUMBER <= abs(number) < MAX_NUMBER
    except ArithmeticError:
        raise ValueError('número fuera del rango admitido (entre 1e-15 y 1e15 en valor absoluto, o 0)') from None
    if not in_range:
        raise ValueError('número fuera del rango admitido (entre 1e-15 y 1e15 en valor absoluto, o 0)')
    if digits > 15:
        raise ValueError('número con más de 15 cifras significativas')
    return number


def loads(raw):
    if len(raw) > MAX_BYTES:
        raise BlocksError([f'el fichero ocupa {len(raw)} bytes; el máximo es {MAX_BYTES}'])
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError:
        raise BlocksError(['el fichero no es UTF-8 válido']) from None
    if text.startswith('﻿'):
        raise BlocksError(['el fichero empieza con una marca BOM; guárdalo como UTF-8 sin BOM'])
    try:
        return json.loads(text, object_pairs_hook=_no_duplicates, parse_constant=_constant, parse_float=_decimal, parse_int=_decimal)
    except (ValueError, RecursionError, ArithmeticError) as exc:
        raise BlocksError([f'JSON no válido: {exc}']) from None


class _Checker:
    def __init__(self):
        self.problems, self.blocks, self.text, self.points, self.cells = [], 0, 0, 0, 0

    def fail(self, where, message):
        self.problems.append(f'{where}: {message}')

    def keys(self, where, value, required, optional=()):
        if not isinstance(value, dict):
            self.fail(where, 'debe ser un objeto')
            return False
        missing = [k for k in required if k not in value]
        unknown = [k for k in value if k not in required and k not in optional]
        if missing:
            self.fail(where, 'faltan los campos ' + ', '.join(f'«{k}»' for k in missing))
        if unknown:
            self.fail(where, 'campos no admitidos ' + ', '.join(f'«{k}»' for k in unknown))
        return not missing

    def string(self, where, value, limit=MAX_STRING, empty=False):
        if not isinstance(value, str):
            self.fail(where, 'debe ser texto')
            return ''
        if CONTROL.search(value):
            self.fail(where, 'contiene caracteres de control')
        if not empty and not value.strip():
            self.fail(where, 'no puede estar vacío')
        if len(value) > limit:
            self.fail(where, f'tiene {len(value)} caracteres; el máximo es {limit}')
        self.text += len(value)
        return value

    def number(self, where, value, nullable=False):
        if value is None and nullable:
            return None
        if isinstance(value, bool) or not isinstance(value, Decimal):
            self.fail(where, 'debe ser un número' + (' o null' if nullable else ''))
            return None
        if abs(value) >= MAX_NUMBER:
            self.fail(where, 'número demasiado grande')
            return None
        return value

    def decimals(self, where, value):
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, Decimal) or value != value.to_integral_value() or not 0 <= value <= 4:
            self.fail(where, 'debe ser un entero entre 0 y 4')
            return None
        return int(value)

    def optional_string(self, where, block, key, limit=MAX_STRING):
        return self.string(f'{where}.{key}', block[key], limit) if key in block else None

    def content(self, where, value):
        nodes = []
        if isinstance(value, str):
            self.string(where, value)
            for part in re.split(r'\n\s*\n', value.strip()):
                if part.strip():
                    nodes.append(dict(kind='paragraph', spans=[dict(text=part.strip(), bold=False, italic=False)]))
            return nodes
        if not isinstance(value, list) or not value:
            self.fail(where, 'debe ser un texto o una lista no vacía de párrafos y listas')
            return nodes
        for i, item in enumerate(value, 1):
            here = f'{where}[{i}]'
            if isinstance(item, str):
                nodes.append(dict(kind='paragraph', spans=[self.span(here, item)]))
            elif isinstance(item, dict) and 'parrafo' in item:
                if self.keys(here, item, ('parrafo',)):
                    nodes.append(dict(kind='paragraph', spans=self.spans(f'{here}.parrafo', item['parrafo'])))
            elif isinstance(item, dict) and 'lista' in item:
                if self.keys(here, item, ('lista',), ('numerada',)):
                    ordered = item.get('numerada', False)
                    if not isinstance(ordered, bool):
                        self.fail(f'{here}.numerada', 'debe ser true o false')
                    entries = item['lista']
                    if not isinstance(entries, list) or not entries or len(entries) > 100:
                        self.fail(f'{here}.lista', 'debe ser una lista de 1 a 100 elementos')
                        continue
                    items = [[self.span(f'{here}.lista[{j}]', e)] if isinstance(e, str) else self.spans(f'{here}.lista[{j}]', e)
                             for j, e in enumerate(entries, 1)]
                    nodes.append(dict(kind='list', ordered=ordered is True, items=items))
            else:
                self.fail(here, 'debe ser un texto, {"parrafo": [...]} o {"lista": [...]}')
        return nodes

    def spans(self, where, value):
        if not isinstance(value, list) or not value or len(value) > 200:
            self.fail(where, 'debe ser una lista de 1 a 200 fragmentos')
            return []
        return [self.span(f'{where}[{i}]', v) for i, v in enumerate(value, 1)]

    def span(self, where, value):
        if isinstance(value, str):
            return dict(text=self.string(where, value), bold=False, italic=False)
        if self.keys(where, value, ('texto',), ('negrita', 'cursiva')):
            flags = {}
            for key, name in (('negrita', 'bold'), ('cursiva', 'italic')):
                flags[name] = value.get(key, False)
                if not isinstance(flags[name], bool):
                    self.fail(f'{where}.{key}', 'debe ser true o false')
                    flags[name] = False
            return dict(text=self.string(f'{where}.texto', value['texto']), **flags)
        return dict(text='', bold=False, italic=False)

    def block_list(self, where, value, path, depth, in_priority):
        if not isinstance(value, list) or not value:
            self.fail(where, 'debe ser una lista no vacía de bloques')
            return []
        if depth > MAX_DEPTH:
            self.fail(where, f'demasiados niveles anidados (máximo {MAX_DEPTH})')
            return []
        return [b for i, item in enumerate(value, 1)
                if (b := self.block(f'{where}[{i}]', item, f'{path}-{i}' if path else f'b{i}', depth, in_priority)) is not None]

    def block(self, where, value, ident, depth, in_priority):
        self.blocks += 1
        if self.blocks == MAX_BLOCKS + 1:
            self.fail(where, f'hay más de {MAX_BLOCKS} bloques')
        if not isinstance(value, dict) or not isinstance(value.get('tipo'), str):
            self.fail(where, 'cada bloque debe ser un objeto con un campo «tipo»')
            return None
        kind = value['tipo']
        where = f'{where} ({kind})'
        handler = getattr(self, 'b_' + kind, None) if kind in BLOCK_TYPES else None
        if handler is None:
            self.fail(where, 'tipo de bloque desconocido; usa ' + ', '.join(BLOCK_TYPES))
            return None
        return handler(where, value, ident, depth, in_priority)

    def b_seccion(self, where, b, ident, depth, in_priority):
        if not self.keys(where, b, ('tipo', 'titulo', 'bloques')):
            return None
        return dict(id=ident, type='section', title=self.string(f'{where}.titulo', b['titulo'], MAX_TITLE),
                    blocks=self.block_list(f'{where}.bloques', b['bloques'], ident, depth + 1, in_priority))

    def b_prioridad(self, where, b, ident, depth, in_priority):
        if not self.keys(where, b, ('tipo', 'titulo', 'bloques')):
            return None
        if in_priority:
            self.fail(where, 'una prioridad no puede ir dentro de otra prioridad')
        return dict(id=ident, type='priority', title=self.string(f'{where}.titulo', b['titulo'], MAX_TITLE),
                    blocks=self.block_list(f'{where}.bloques', b['bloques'], ident, depth + 1, True))

    def b_texto(self, where, b, ident, depth, in_priority):
        if not self.keys(where, b, ('tipo', 'contenido')):
            return None
        return dict(id=ident, type='text', content=self.content(f'{where}.contenido', b['contenido']))

    def b_aviso(self, where, b, ident, depth, in_priority):
        if not self.keys(where, b, ('tipo', 'contenido')):
            return None
        return dict(id=ident, type='notice', content=self.content(f'{where}.contenido', b['contenido']))

    def b_cifra(self, where, b, ident, depth, in_priority):
        if not self.keys(where, b, ('tipo', 'etiqueta', 'valor'), ('unidad', 'decimales', 'periodo', 'anterior', 'nota')):
            return None
        value = self.number(f'{where}.valor', b['valor'])
        previous = None
        if 'anterior' in b:
            here = f'{where}.anterior'
            if self.keys(here, b['anterior'], ('valor',), ('periodo',)):
                previous = dict(value=self.number(f'{here}.valor', b['anterior']['valor']),
                                period=self.optional_string(here, b['anterior'], 'periodo', MAX_TITLE))
        decimals = self.decimals(f'{where}.decimales', b.get('decimales'))
        return dict(id=ident, type='figure', label=self.string(f'{where}.etiqueta', b['etiqueta'], MAX_TITLE),
                    value=value, previous=previous, unit=self.optional_string(where, b, 'unidad', 40),
                    decimals=decimals, period=self.optional_string(where, b, 'periodo', MAX_TITLE),
                    note=self.optional_string(where, b, 'nota'))

    def b_grafico(self, where, b, ident, depth, in_priority):
        optional = ('unidad', 'decimales', 'eje_categorias', 'eje_valores', 'nota')
        if not self.keys(where, b, ('tipo', 'grafico', 'titulo', 'categorias', 'series'), optional):
            return None
        requested = self.string(f'{where}.grafico', b['grafico'], 40)
        categories = b['categorias']
        if not isinstance(categories, list) or not 1 <= len(categories) <= MAX_CATEGORIES:
            self.fail(f'{where}.categorias', f'debe ser una lista de 1 a {MAX_CATEGORIES} etiquetas')
            categories = []
        categories = [self.string(f'{where}.categorias[{i}]', c, MAX_TITLE) for i, c in enumerate(categories, 1)]
        if len(set(categories)) != len(categories):
            self.fail(f'{where}.categorias', 'hay categorías repetidas')
        series = []
        raw_series = b['series']
        if not isinstance(raw_series, list) or not 1 <= len(raw_series) <= MAX_SERIES:
            self.fail(f'{where}.series', f'debe ser una lista de 1 a {MAX_SERIES} series')
            raw_series = []
        for i, s in enumerate(raw_series, 1):
            here = f'{where}.series[{i}]'
            if not self.keys(here, s, ('nombre', 'valores'), ('detalles',)):
                continue
            values = s['valores']
            if not isinstance(values, list) or len(values) != len(categories):
                self.fail(f'{here}.valores', f'debe tener un valor (o null) por categoría: {len(categories)}')
                values = []
            values = [self.number(f'{here}.valores[{j}]', v, nullable=True) for j, v in enumerate(values, 1)]
            self.points += len(values)
            details = None
            if 'detalles' in s:
                details = s['detalles']
                if not isinstance(details, list) or len(details) != len(categories):
                    self.fail(f'{here}.detalles', 'debe tener un texto (o null) por categoría')
                    details = None
                else:
                    details = [None if d is None else self.string(f'{here}.detalles[{j}]', d, MAX_TITLE)
                               for j, d in enumerate(details, 1)]
            series.append(dict(name=self.string(f'{here}.nombre', s['nombre'], MAX_TITLE), values=values, details=details))
        if len({s['name'] for s in series}) != len(series):
            self.fail(f'{where}.series', 'hay series con el mismo nombre')
        if series and all(v is None for s in series for v in s['values']):
            self.fail(f'{where}.series', 'no hay ningún valor numérico')
        kind = CHART_KINDS.get(requested.strip().lower())
        return dict(id=ident, type='chart', kind=kind or 'table', requested_kind=requested, fallback=kind is None,
                    title=self.string(f'{where}.titulo', b['titulo'], MAX_TITLE), categories=categories, series=series,
                    unit=self.optional_string(where, b, 'unidad', 40),
                    decimals=self.decimals(f'{where}.decimales', b.get('decimales')),
                    category_title=self.optional_string(where, b, 'eje_categorias', MAX_TITLE),
                    value_title=self.optional_string(where, b, 'eje_valores', MAX_TITLE),
                    note=self.optional_string(where, b, 'nota'))

    def b_tabla(self, where, b, ident, depth, in_priority):
        if not self.keys(where, b, ('tipo', 'columnas', 'filas'), ('titulo', 'nota')):
            return None
        columns = []
        raw = b['columnas']
        if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_COLUMNS:
            self.fail(f'{where}.columnas', f'debe ser una lista de 1 a {MAX_COLUMNS} columnas')
            raw = []
        for i, c in enumerate(raw, 1):
            here = f'{where}.columnas[{i}]'
            if isinstance(c, str):
                columns.append(dict(title=self.string(here, c, MAX_TITLE), unit=None, decimals=None))
            elif self.keys(here, c, ('titulo',), ('unidad', 'decimales')):
                columns.append(dict(title=self.string(f'{here}.titulo', c['titulo'], MAX_TITLE),
                                    unit=self.optional_string(here, c, 'unidad', 40),
                                    decimals=self.decimals(f'{here}.decimales', c.get('decimales'))))
        rows = b['filas']
        if not isinstance(rows, list) or len(rows) > MAX_ROWS:
            self.fail(f'{where}.filas', f'debe ser una lista de como mucho {MAX_ROWS} filas')
            rows = []
        out = []
        for i, row in enumerate(rows, 1):
            here = f'{where}.filas[{i}]'
            if not isinstance(row, list) or len(row) != len(raw):
                self.fail(here, f'debe tener {len(raw)} celdas')
                continue
            cells = []
            for j, cell in enumerate(row, 1):
                if cell is None:
                    cells.append(None)
                elif isinstance(cell, str):
                    cells.append(self.string(f'{here}[{j}]', cell, MAX_TITLE * 2, empty=True))
                else:
                    cells.append(self.number(f'{here}[{j}]', cell))
            self.cells += len(cells)
            out.append(cells)
        return dict(id=ident, type='table', title=self.optional_string(where, b, 'titulo', MAX_TITLE),
                    columns=columns, rows=out, note=self.optional_string(where, b, 'nota'))


BLOCK_TYPES = ('seccion', 'texto', 'cifra', 'grafico', 'tabla', 'prioridad', 'aviso')


def _validate(value):
    check = _Checker()
    blocks = []
    title = ''
    if check.keys('informe', value, ('version', 'titulo', 'bloques')):
        if value['version'] != VERSION:
            check.fail('informe.version', f'debe ser «{VERSION}»')
        title = check.string('informe.titulo', value['titulo'], MAX_TITLE)
        blocks = check.block_list('informe.bloques', value['bloques'], '', 1, False)
    for total, limit, name in ((check.text, MAX_TEXT, 'caracteres de texto'), (check.points, MAX_POINTS, 'valores de gráficos'),
                               (check.cells, MAX_CELLS, 'celdas de tablas')):
        if total > limit:
            check.fail('informe', f'hay {total} {name}; el máximo es {limit}')
    if check.problems:
        raise BlocksError(check.problems)
    return title, blocks


def _num(value):
    """JSON-safe exact number: int when integral, otherwise a float of the exact decimal."""
    if value is None:
        return None
    return int(value) if value == value.to_integral_value() else float(value)


def _project_numbers(block):
    if block['type'] == 'figure':
        value, previous = block['value'], block['previous']
        change = pct = None
        if previous and previous['value'] is not None and value is not None:
            change = value - previous['value']
            if previous['value'] != 0:
                try:
                    with localcontext() as ctx:
                        ctx.prec = 60
                        pct = (change / abs(previous['value']) * 100).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)
                except ArithmeticError:
                    pct = None
        decimals = block['decimals'] if block['decimals'] is not None else _default_decimals(
            [value] + ([previous['value']] if previous else []))
        block.update(value=_num(value), change=_num(change), change_pct=_num(pct), decimals=decimals,
                     previous=dict(value=_num(previous['value']), period=previous['period']) if previous else None)
    elif block['type'] == 'chart':
        values = [v for s in block['series'] for v in s['values']]
        if block['decimals'] is None:
            block['decimals'] = _default_decimals(values)
        for s in block['series']:
            s['values'] = [_num(v) for v in s['values']]
    elif block['type'] == 'table':
        for c, column in enumerate(block['columns']):
            if column['decimals'] is None:
                column['decimals'] = _default_decimals([r[c] for r in block['rows'] if isinstance(r[c], Decimal)])
        block['rows'] = [[_num(c) if isinstance(c, Decimal) else c for c in row] for row in block['rows']]
    for child in block.get('blocks', ()):
        _project_numbers(child)


def _default_decimals(values):
    """Up to 2 decimals, or as many as needed so no nonzero value is shown as 0."""
    numbers = [v for v in values if isinstance(v, Decimal)]
    places = [max(0, -v.normalize().as_tuple().exponent) for v in numbers]
    decimals = min(max(places, default=0), 2)
    smallest = min((abs(v) for v in numbers if v), default=None)
    if smallest is not None and smallest < Decimal(1).scaleb(-decimals) / 2:
        decimals = min(15, max(decimals, -smallest.adjusted()))
    return decimals


def parse(raw):
    """Strictly parse and validate stored bytes; returns the projection (never markup)."""
    title, blocks = _validate(loads(raw))
    for block in blocks:
        _project_numbers(block)
    return dict(schema=VERSION, projector=PROJECTOR_VERSION, title=title, blocks=blocks)


project = parse


def walk(blocks):
    for block in blocks:
        yield block
        yield from walk(block.get('blocks', ()))


def format_number(value, decimals):
    if value is None:
        return '—'
    with localcontext() as ctx:
        ctx.prec = 80  # derived values (differences, percentages) can exceed 15 digits
        number = Decimal(str(value)).quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)
        text = f'{abs(number):,.{decimals}f}'.translate(str.maketrans({',': '.', '.': ','}))
    return ('−' if number < 0 else '') + text


def exact_number(value):
    """Every digit of the delivered value, in Spanish format."""
    with localcontext() as ctx:
        ctx.prec = 80
        places = max(0, -Decimal(str(value)).normalize().as_tuple().exponent)
    return format_number(value, places)


def shown(value, decimals):
    """Visible format plus the exact value when rounding hides digits (chat and checks need it)."""
    text = format_number(value, decimals)
    if value is not None:
        with localcontext() as ctx:
            ctx.prec = 80
            hidden = Decimal(str(value)) != Decimal(str(value)).quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)
        if hidden:
            text += f' [exacto: {exact_number(value)}]'
    return text


def _with_unit(value, decimals, unit):
    text = shown(value, decimals)
    if unit and value is not None:
        return f'{text} %' if unit == '%' else f'{text} {unit}'
    return text


def _spans(spans):
    return ''.join(s['text'] for s in spans)


def _content_lines(content):
    lines = []
    for node in content:
        if node['kind'] == 'paragraph':
            lines.append(_spans(node['spans']))
        else:
            for i, item in enumerate(node['items'], 1):
                lines.append((f'{i}. ' if node['ordered'] else '- ') + _spans(item))
    return lines


def block_lines(block):
    """Plain-text rendering of one block and its children (canonical, platform-formatted)."""
    kind = block['type']
    if kind in ('section', 'priority'):
        lines = [('Prioridad: ' if kind == 'priority' else '') + block['title']]
        for child in block['blocks']:
            lines += block_lines(child)
        return lines
    if kind == 'text':
        return _content_lines(block['content'])
    if kind == 'notice':
        return ['Aviso: ' + line for line in _content_lines(block['content'])]
    if kind == 'figure':
        text = f"{block['label']}: {_with_unit(block['value'], block['decimals'], block['unit'])}"
        if block['period']:
            text += f" ({block['period']})"
        if block['previous']:
            prev = block['previous']
            text += f"; antes {_with_unit(prev['value'], block['decimals'], block['unit'])}"
            if prev['period']:
                text += f" ({prev['period']})"
            if block['change'] is not None:
                sign = '+' if block['change'] > 0 else ''
                text += f"; cambio {sign}{_with_unit(block['change'], block['decimals'], block['unit'])}"
            if block['change_pct'] is not None:
                sign = '+' if block['change_pct'] > 0 else ''
                text += f" ({sign}{format_number(block['change_pct'], 1)} %)"
        lines = [text]
        if block['note']:
            lines.append(block['note'])
        return lines
    if kind == 'chart':
        unit = f" ({block['unit']})" if block['unit'] else ''
        lines = [f"Gráfico: {block['title']}{unit}"]
        for s in block['series']:
            cells = [f"{c} {shown(v, block['decimals'])}" + (f" [{d}]" if d else '')
                     for c, v, d in zip(block['categories'], s['values'], s['details'] or [None] * len(s['values']))]
            lines.append(f"{s['name']}: " + '; '.join(cells))
        if block['note']:
            lines.append(block['note'])
        return lines
    if kind == 'table':
        lines = [f"Tabla: {block['title']}"] if block['title'] else ['Tabla']
        heads = [c['title'] + (f" ({c['unit']})" if c['unit'] else '') for c in block['columns']]
        lines.append(' | '.join(heads))
        for row in block['rows']:
            lines.append(' | '.join('' if v is None else v if isinstance(v, str) else shown(v, c['decimals'])
                                    for v, c in zip(row, block['columns'])))
        if block['note']:
            lines.append(block['note'])
        return lines
    raise ValueError(f'Unknown projected block {kind}')


def canonical_text(projection):
    lines = [projection['title'], '']
    for block in projection['blocks']:
        lines += block_lines(block)
        lines.append('')
    return '\n'.join(lines).strip() + '\n'


def priorities(projection):
    """Every priority block with its canonical text, bound to its id (for the independent check)."""
    return [dict(block_id=b['id'], title=b['title'], text='\n'.join(block_lines(b)))
            for b in walk(projection['blocks']) if b['type'] == 'priority']


def main(argv):
    if len(argv) == 2 and argv[1] in ('--formato', '--ayuda', '-h', '--help'):
        print(FORMAT_GUIDE)
        return 0
    if len(argv) != 2:
        print('Uso: comprobar_informe.py /work/informe.json   (o --formato para ver el formato)')
        return 2
    try:
        with open(argv[1], 'rb') as handle:
            projection = parse(handle.read(MAX_BYTES + 1))
    except OSError as exc:
        print(f'No puedo leer el fichero: {exc.strerror}')
        return 1
    except BlocksError as exc:
        print('El informe todavía no es válido. Corrige esto y vuelve a comprobarlo:')
        for problem in exc.problems:
            print('- ' + problem)
        return 1
    blocks = list(walk(projection['blocks']))
    fallback = [b['requested_kind'] for b in blocks if b['type'] == 'chart' and b['fallback']]
    print(f"Informe válido: {len(blocks)} bloques, {sum(b['type'] == 'priority' for b in blocks)} prioridades, "
          f"{sum(b['type'] == 'chart' for b in blocks)} gráficos, {sum(b['type'] == 'table' for b in blocks)} tablas.")
    if fallback:
        print('Aviso: estos tipos de gráfico se mostrarán como tabla: ' + ', '.join(sorted(set(fallback))))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
