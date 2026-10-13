"""Which numbers of each priority an independent check covers, line by line.

Standard-library only: the product counts with these same functions, and the very same file
is mounted in the checker container as ``comprobar_cobertura`` so the checker can see, before
it finishes, which numbers the platform would publish as not independently recalculated.

numbers(text) -> the figures of one priority's text (its own «Prioridad: N.» ordinal is not one).
lines(text) -> each line that has figures, with exact start/end offsets, for quoting whole lines.
uncovered(text, items) -> the figures outside every located item's [start, end).
"""
import json
import re
import sys

VERSION = 'priority-check-1'
NUMBERS = re.compile(r'(?<![\w])[-−+]?\d+(?:[.,]\d+)*(?:\s*%)?(?![\w])')
ORDINAL = re.compile(r'Prioridad: (\d{1,2})[.)]\s')
FIELDS = {'priority_id', 'quote', 'start', 'end', 'status', 'independent_value', 'method', 'message'}
STATUSES = ('confirmed', 'discrepancy', 'unverifiable')
PRIORITIES = '/inputs/prioridades.json'
PREVIEW = 120


def numbers(text):
    ordinal = ORDINAL.match(text)
    skip = ordinal.span(1) if ordinal else None
    return [m for m in NUMBERS.finditer(text) if m.span() != skip]


def lines(text):
    found, start, spans = [], 0, numbers(text)
    for line in text.split('\n'):
        end = start + len(line)
        count = sum(1 for m in spans if start <= m.start() and m.end() <= end)
        if count:
            found.append(dict(start=start, end=end, cifras=count, texto=line))
        start = end + 1
    return found


def uncovered(text, items):
    spans = [(i['start'], i['end']) for i in items if type(i.get('start')) is int and type(i.get('end')) is int]
    return [m for m in numbers(text) if not any(s <= m.start() and m.end() <= e for s, e in spans)]


def problems(data, check):
    """What the platform would refuse in /work/comprobacion.json, in Spanish; [] when usable."""
    if not isinstance(check, dict) or set(check) != {'version', 'revision_sha256', 'items', 'coverage_notes'}:
        return ['El objeto debe tener exactamente version, revision_sha256, items y coverage_notes.']
    found = []
    if check['version'] != VERSION:
        found.append(f'version debe ser "{VERSION}".')
    if check['revision_sha256'] != data['revision_sha256']:
        found.append('revision_sha256 debe ser el valor copiado de prioridades.json.')
    if not isinstance(check['items'], list):
        return found + ['items debe ser una lista.']
    texts, seen = {p['block_id']: p['text'] for p in data['priorities']}, set()
    for number, item in enumerate(check['items'], 1):
        where = f'item {number}'
        if not isinstance(item, dict) or set(item) != FIELDS:
            found.append(f"{where}: debe tener exactamente {', '.join(sorted(FIELDS))}.")
            continue
        text = texts.get(item['priority_id'])
        if text is None:
            found.append(f'{where}: priority_id no es ninguno de prioridades.json.')
            continue
        if item['status'] not in STATUSES:
            found.append(f"{where}: status debe ser {', '.join(STATUSES)}.")
        if not isinstance(item['quote'], str) or not item['quote']:
            found.append(f'{where}: quote debe ser el fragmento literal.')
            continue
        start, end = item['start'], item['end']
        if start is None and end is None:
            if item['status'] == 'confirmed':
                found.append(f'{where}: un item sin start/end no puede ser confirmed.')
        elif not (type(start) is int and type(end) is int and 0 <= start < end <= len(text) and text[start:end] == item['quote']):
            found.append(f'{where}: quote no es exactamente el texto entre start y end de esa prioridad.')
        if item['status'] in ('confirmed', 'discrepancy') and not (isinstance(item['method'], str) and item['method'].strip()):
            found.append(f'{where}: falta method (cómo se calculó).')
        identity = (item['priority_id'], start, end, item['quote'])
        if identity in seen:
            found.append(f'{where}: repite el fragmento de otro item.')
        seen.add(identity)
    return found


def pending(data, check):
    """Lines with figures outside every item, in prioridades.json order."""
    result = []
    for priority in data['priorities']:
        items = [i for i in check['items'] if i['priority_id'] == priority['block_id']]
        missing = uncovered(priority['text'], items)
        for line in lines(priority['text']):
            left = sum(1 for m in missing if line['start'] <= m.start() and m.end() <= line['end'])
            if left:
                preview = line['texto'] if len(line['texto']) <= PREVIEW else line['texto'][:PREVIEW - 1] + '…'
                result.append(dict(priority_id=priority['block_id'], start=line['start'], end=line['end'],
                                   cifras_sin_item=left, inicio=preview))
    return result


def main(argv, priorities=PRIORITIES):
    if len(argv) != 2:
        print('Uso: comprobar_cobertura.py /work/comprobacion.json')
        return 2
    with open(priorities, encoding='utf-8') as handle:
        data = json.load(handle)
    try:
        with open(argv[1], encoding='utf-8') as handle:
            check = json.load(handle)
    except OSError as exc:
        print(f'No puedo leer el fichero: {exc.strerror}')
        return 1
    except ValueError:
        print('El fichero no es JSON válido.')
        return 1
    found = problems(data, check)
    if found:
        print('El fichero todavía no es válido. Corrige esto y vuelve a comprobarlo:')
        for problem in found:
            print('- ' + problem)
        return 1
    total = sum(len(numbers(p['text'])) for p in data['priorities'])
    left = pending(data, check)
    if not left:
        print(f'Válido. Las {total} cifras de las prioridades están dentro de algún item.')
        return 0
    print(f"Válido, pero {sum(x['cifras_sin_item'] for x in left)} de {total} cifras no están dentro de ningún item "
          'y se publicarán como no comprobadas. Líneas con cifras sin item (el texto completo está en '
          'prioridades.json, entre start y end):')
    for line in left:
        print(json.dumps(line, ensure_ascii=False))
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
