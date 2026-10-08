"""R1b: insert recipe-generated evidence at its point of use in ordinary fields.

The R1a verifier remains responsible for recalculation and scoped certification.
We copy only its generated segment and labels, never certify neighbouring prose.
"""
from collections import defaultdict
from copy import deepcopy
import hashlib
import json
import re

from . import contract, verification
from .verification_contract import canonical, figure_id, validate

VERSION = 'report-occurrences-v1'
TOKEN = re.compile(r'\{\{e:([^{}]{1,100})\}\}')
MAX_SEGMENTS = 256
MAX_SEGMENT_TEXT = 1_000_000


def prose(document):
    for key in contract.TEXT_FIELDS:
        yield '/'+key, document[key], None
    for index, finding in enumerate(document['findings']):
        for key in contract.FINDING_FIELDS:
            yield f'/findings/{index}/{key}', finding[key], finding['key']


def build(raw, *, resolver=None):
    initial, references, issues = contract.load(raw)
    if issues:  # A malformed draft is retained as text, not interpreted as a template.
        return verification.build(raw, resolver=resolver)
    matches = [(path, list(TOKEN.finditer(text))) for path, text, _ in prose(initial)]
    if not any(tokens for _, tokens in matches):
        return verification.build(raw, resolver=resolver)

    source = json.loads(raw)
    total_facts = sum(1 for _ in contract.fact_entries(initial))
    limits = []
    for path, tokens in matches:
        owner = source['findings'][int(path.split('/')[2])] if path.startswith('/findings/') else source
        for token in tokens:
            keys = owner.setdefault('facts', [])
            if token[1] in keys:
                continue
            if len(keys) >= 32 or total_facts >= 256:
                limits.append('occurrence_support_limit')
                continue
            keys.append(token[1]); total_facts += 1

    cache = {}
    def resolve(ref):
        identity = canonical(ref)
        if identity not in cache:
            try:
                cache[identity] = resolver(ref) if resolver else None
            except Exception:
                cache[identity] = None
        return cache[identity]

    try:
        prepared = canonical(source)
    except (ValueError, RecursionError):
        # A non-finite reference or pathological input must not lose the raw report.
        return verification.build(raw, resolver=resolver)
    document, ledger = verification.build(prepared, resolver=resolve)
    by_path = defaultdict(list)
    for figure in ledger['figures']:
        by_path[figure['path']].append(figure)
    definitions = {ref['key']: ref for ref in references if isinstance(ref, dict) and isinstance(ref.get('key'), str)}
    segments = {}
    for path, fact, recommendation in contract.fact_entries(document):
        text = fact['text']; figures = by_path[path+'/text']
        ref = definitions.get(fact['number_key'])
        check = cache.get(canonical(ref)) if ref else None
        display = check.get('display') if isinstance(check, dict) else None
        primary = next((f for f in figures if f['verified']), None)
        # The base verifier, not the agent's claimed unit or scope, approved this slot.
        if primary and isinstance(display, dict):
            prefix = display['label']+': '+primary['text']+' '+display['unit']+'. '+display['scope']
            if text.startswith(prefix):
                text = prefix
                figures = [f for f in figures if f['span']['end'] <= len(prefix)]
        segments.setdefault((recommendation, fact['number_key']), (text, figures))

    figures = []
    modified = set()
    used_segments = 0; generated_chars = 0
    for path, original, recommendation in list(prose(document)):
        tokens = list(TOKEN.finditer(original))
        if not tokens:
            continue
        modified.add(path)
        output = ''; previous = 0; replacements = []
        for token in tokens:
            output += original[previous:token.start()]
            start = len(output)
            value, labels = segments.get((recommendation, token[1]),
                ('No disponible: referencia sin soporte comprobado.', []))
            used_segments += 1; generated_chars += len(value)
            if used_segments > MAX_SEGMENTS or generated_chars > MAX_SEGMENT_TEXT:
                value, labels = 'No disponible: límite de expansión de evidencia.', []
                limits.append('occurrence_expansion_limit')
            output += value
            replacements.append((token.start(), token.end(), len(value)))
            for label in labels:
                copy = deepcopy(label)
                copy.update(path=path, recommendation_id=recommendation,
                            span={k: v+start for k,v in label['span'].items()})
                figures.append(copy)
            previous = token.end()
        output += original[previous:]
        contract.set_text(document, path, output)
        for label in by_path[path]:
            a,b = label['span']['start'],label['span']['end']
            if any(a < end and begin < b for begin,end,_ in replacements):
                continue
            offset = sum(length-(end-begin) for begin,end,length in replacements if end <= a)
            copy = deepcopy(label); copy['span'] = {'start':a+offset, 'end':b+offset}
            figures.append(copy)
    figures.extend(deepcopy(f) for f in ledger['figures'] if f['path'] not in modified)
    order = {path: i for i,(path,_,_) in enumerate(contract.texts(document))}
    figures.sort(key=lambda f:(order[f['path']],f['span']['start']))
    document['verification_annotations'] = [{k:f[k] for k in ('path','span','text','status','value','unit','verified')} for f in figures]
    digest = hashlib.sha256(canonical(document)).hexdigest()
    counts = dict.fromkeys(('verified','unverified','uncertain','corrected'),0)
    for figure in figures:
        figure['id'] = figure_id(digest,figure['path'],figure['span']['start'],figure['span']['end'])
        counts[figure['status']] += 1
    ledger.update(draft_sha256=hashlib.sha256(raw).hexdigest(), verified_sha256=digest,
                  renderer_version=VERSION, figures=figures, summary=counts,
                  issues=list(dict.fromkeys([*ledger['issues'],*limits])))
    validate(ledger,document,raw)
    return document,ledger
