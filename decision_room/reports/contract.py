"""Tolerant report loading after raw persistence; malformed drafts stay readable."""
import json

from . import charts

TEXT_FIELDS = ('title', 'summary', 'scope', 'limitations')
FINDING_FIELDS = ('title', 'statement', 'scope', 'interpretation', 'next_step')


class FormatError(ValueError):
    def __init__(self, path, expected):
        self.path, self.expected = path, expected
        super().__init__('Report field does not match its expected shape.')


def _parse(raw):
    """Shared shape check for delivery feedback and recovery rendering."""
    try:
        value = json.loads(raw.decode('utf-8', errors='replace'), parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, RecursionError):
        raise FormatError('', 'JSON object with schema_version: 1') from None
    try:
        if not isinstance(value, dict) or value.get('schema_version') != 1:
            raise FormatError('', 'JSON object with schema_version: 1')
        for key in TEXT_FIELDS:
            if key in value and not isinstance(value[key], str):
                raise FormatError('/'+key, 'string (use an empty string if there is no text)')
        findings = value.get('findings', [])
        if not isinstance(findings, list) or any(not isinstance(f, dict) for f in findings):
            raise FormatError('/findings', 'array of finding objects')
        keys = [f.get('key') for f in findings]
        if any(not isinstance(k, str) or not k for k in keys) or len(set(keys)) != len(keys):
            raise FormatError('/findings', 'a unique nonempty string key in each finding')
        for index, finding in enumerate(findings):
            for key in FINDING_FIELDS:
                if key in finding and not isinstance(finding[key], str):
                    raise FormatError(f'/findings/{index}/{key}', 'string (use an empty string if there is no text)')
        # Unknown fields remain visible in the fallback, not silently discarded.
        if set(value) - {'schema_version', *TEXT_FIELDS, 'findings', 'numbers', 'charts', 'facts'}:
            raise FormatError('', 'only schema_version, title, summary, scope, limitations, findings, numbers, charts, facts')
        for index, finding in enumerate(findings):
            if set(finding) - {'key', *FINDING_FIELDS, 'facts'}:
                raise FormatError(f'/findings/{index}', 'only key, title, statement, scope, interpretation, next_step, facts')
        doc = {'schema_version': 1, **{k: value.get(k, '') for k in TEXT_FIELDS},
               'findings': [{'key': f['key'], **{k: f.get(k, '') for k in FINDING_FIELDS}} for f in findings]}
        def facts(value, path):
            if not isinstance(value, list) or len(value) > 32 or any(not isinstance(k, str) or not 1 <= len(k) <= 100 or any(c in k for c in '{}') for k in value):
                raise FormatError(path, 'array of at most 32 number keys: strings of 1–100 characters without braces')
            return [{'number_key': k, 'text': ''} for k in value]
        if 'facts' in value:
            doc['facts'] = facts(value['facts'], '/facts')
        for index, (source, finding) in enumerate(zip(findings, doc['findings'])):
            if 'facts' in source:
                finding['facts'] = facts(source['facts'], f'/findings/{index}/facts')
        if sum(1 for _ in fact_entries(doc)) > 256:
            raise FormatError('', 'at most 256 facts across the report')
        if value.get('charts') is not None:
            try:
                doc['charts'] = charts.normalize(value['charts'], set(keys))
            except (ValueError, TypeError):
                raise FormatError('/charts', 'up to 8 bar/line/table charts with unique keys, text titles, 1–6 series and 1–100 points per series; points have label and number_key; recommendation_id must name a finding') from None
        refs = value.get('numbers', [])
        if not isinstance(refs, list):
            raise FormatError('/numbers', 'array of number reference objects')
        return doc, refs, []
    except (TypeError, RecursionError):
        raise FormatError('', 'report structure matching schema_version: 1') from None


def format_feedback(raw):
    """Safe first error only; call after raw persistence, never echo draft values."""
    try:
        _parse(raw)
        return {'valid': True, 'errors': []}
    except FormatError as error:
        return {'valid': False, 'errors': [{'path': error.path, 'expected': error.expected}],
                'action': 'Raw draft saved. Correct the field and deliver the complete JSON with a new request_key. Shape validation is not analytical verification.'}


def load(raw):
    try:
        return _parse(raw)
    except FormatError:
        return {'schema_version': 1, 'title': '', 'summary': raw.decode('utf-8', errors='replace'),
                'scope': '', 'limitations': '', 'findings': []}, [], ['report_format_fallback']


def texts(document):
    for key in TEXT_FIELDS:
        yield '/' + key, document[key], None
    for index, finding in enumerate(document['findings']):
        for key in FINDING_FIELDS:
            yield f'/findings/{index}/{key}', finding[key], finding['key']
    for path, fact, recommendation in fact_entries(document):
        for key in ('text',):
            yield path+'/'+key, fact[key], recommendation
    yield from charts.texts(document.get('charts', []))


def set_text(document, path, value):
    parts = path.split('/')[1:]
    parent = document
    for part in parts[:-1]:
        parent = parent[int(part)] if isinstance(parent, list) else parent[part]
    parent[parts[-1]] = value


def fact_entries(document):
    for i, fact in enumerate(document.get('facts', [])):
        yield f'/facts/{i}', fact, None
    for i, finding in enumerate(document['findings']):
        for j, fact in enumerate(finding.get('facts', [])):
            yield f'/findings/{i}/facts/{j}', fact, finding['key']
