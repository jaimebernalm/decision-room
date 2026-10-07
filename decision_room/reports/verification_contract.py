"""Versioned numerical-audit export contract, not a numerical verifier.

Validation does not approve a document and must never precede raw draft storage.
The evaluator joins individual visible occurrences; correction and independent
verification are separate facts. Summary counts are descriptive, not a gate.
"""
import hashlib
import json
import re

from ..series import numeric

CONTRACT_VERSION = 1
STATUSES = {'verified', 'unverified', 'uncertain', 'corrected'}


def canonical(value):
    """Stable UTF-8 JSON shared by document hashes and occurrence identities."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def _pointer(document, path):
    if not isinstance(path, str) or not path.startswith('/') or re.search(r'~(?![01])', path):
        raise ValueError('Expected an RFC 6901 JSON Pointer.')
    value = document
    for part in path[1:].split('/'):
        part = part.replace('~1', '/').replace('~0', '~')
        try:
            if isinstance(value, list):
                if not re.fullmatch(r'0|[1-9][0-9]*', part):
                    raise ValueError('Invalid array pointer.')
                value = value[int(part)]
            elif isinstance(value, dict):
                value = value[part]
            else:
                raise ValueError('Pointer traverses a scalar.')
        except (KeyError, IndexError):
            raise ValueError('Figure pointer does not exist.') from None
    return value


def figure_id(verified_sha256, path, start, end):
    return 'figure_' + hashlib.sha256(canonical([CONTRACT_VERSION, verified_sha256, path, start, end])).hexdigest()


def validate(ledger, document, raw):
    """Check identity, visible text and labels; return the unchanged ledger.

    document is draft.verified.json's parsed payload. A figure points at a string
    field containing rendered text; offsets count Unicode code points, not UTF-8
    bytes or HTML source. The renderer must consume these same fields verbatim.
    """
    fields = {'contract_version', 'draft_sha256', 'verified_sha256', 'renderer_version', 'figures', 'summary', 'issues'}
    if not isinstance(ledger, dict) or set(ledger) != fields or type(ledger['contract_version']) is not int or ledger['contract_version'] != CONTRACT_VERSION:
        raise ValueError('Unsupported verification export contract.')
    if not isinstance(raw, bytes):
        raise ValueError('Validate against the exact original draft bytes.')
    if ledger['draft_sha256'] != hashlib.sha256(raw).hexdigest() or ledger['verified_sha256'] != hashlib.sha256(canonical(document)).hexdigest():
        raise ValueError('Verification export does not match the document versions.')
    if not isinstance(ledger['renderer_version'], str) or not 1 <= len(ledger['renderer_version']) <= 100:
        raise ValueError('A renderer version is required.')
    if not isinstance(ledger['figures'], list) or not isinstance(ledger['issues'], list):
        raise ValueError('Figures and issues must be arrays.')
    counts = dict.fromkeys(sorted(STATUSES), 0)
    seen = set()
    spans = {}
    for figure in ledger['figures']:
        fields = {'id', 'path', 'span', 'text', 'value', 'unit', 'status', 'verified',
                  'corrected_from', 'evidence', 'recommendation_id'}
        if not isinstance(figure, dict) or set(figure) != fields:
            raise ValueError('Invalid figure fields.')
        span = figure['span']
        if not isinstance(span, dict) or set(span) != {'start', 'end'} or any(type(n) is not int for n in span.values()):
            raise ValueError('Figure span must use integer Unicode offsets.')
        text = _pointer(document, figure['path'])
        start, end = span['start'], span['end']
        if not isinstance(text, str) or not 0 <= start < end <= len(text) or text[start:end] != figure['text']:
            raise ValueError('Figure text is not the indicated visible occurrence.')
        expected = figure_id(ledger['verified_sha256'], figure['path'], start, end)
        if figure['id'] != expected or expected in seen:
            raise ValueError('Duplicate or unstable figure identity.')
        seen.add(expected)
        prior = spans.setdefault(figure['path'], [])
        if any(start < stop and begin < end for begin, stop in prior):
            raise ValueError('Figure occurrences must not overlap.')
        prior.append((start, end))
        status = figure['status']
        if not isinstance(status, str) or status not in STATUSES or type(figure['verified']) is not bool:
            raise ValueError('Invalid verification state.')
        if (status == 'verified' and not figure['verified']) or (status in {'unverified', 'uncertain'} and figure['verified']):
            raise ValueError('Contradictory verification labels.')
        for field in ('value', 'corrected_from'):
            if figure[field] is not None:
                if not isinstance(figure[field], str):
                    raise ValueError('Numerical values must be decimal strings or null.')
                numeric(figure[field])
        if status == 'corrected' and (figure['corrected_from'] is None or figure['value'] is None):
            raise ValueError('A correction requires before and after values.')
        if status != 'corrected' and figure['corrected_from'] is not None:
            raise ValueError('A changed value must declare correction status.')
        if figure['unit'] is not None and not isinstance(figure['unit'], str):
            raise ValueError('Units are text or null.')
        if figure['recommendation_id'] is not None and not isinstance(figure['recommendation_id'], str):
            raise ValueError('Recommendation ID is text or null.')
        if not isinstance(figure['evidence'], list):
            raise ValueError('Evidence must be an array.')
        for ref in figure['evidence']:
            if (not isinstance(ref, dict) or not {'kind', 'id'} <= set(ref) or set(ref) - {'kind', 'id', 'metric'}
                    or not isinstance(ref['kind'], str) or ref['kind'] not in {'execution', 'observation'} or not isinstance(ref['id'], str) or not ref['id']
                    or ('metric' in ref and (not isinstance(ref['metric'], str) or not ref['metric']))):
                raise ValueError('Invalid evidence identity.')
        if figure['verified'] and (figure['value'] is None or not figure['evidence']):
            raise ValueError('Verified figures require a value and evidence.')
        counts[status] += 1
    if (not isinstance(ledger['summary'], dict) or set(ledger['summary']) != STATUSES
            or any(type(v) is not int for v in ledger['summary'].values()) or ledger['summary'] != counts):
        raise ValueError('Summary must count the four status labels exactly.')
    return ledger
