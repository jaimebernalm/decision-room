"""Tolerant report loading after raw persistence; malformed drafts stay readable."""
import json

from . import charts

TEXT_FIELDS = ('title', 'summary', 'scope', 'limitations')
FINDING_FIELDS = ('title', 'statement', 'scope', 'interpretation', 'next_step')


def load(raw):
    text = raw.decode('utf-8', errors='replace')
    try:
        value = json.loads(text, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        if not isinstance(value, dict) or value.get('schema_version') != 1:
            raise ValueError('Unsupported report format.')
        if any(k in value and not isinstance(value[k], str) for k in TEXT_FIELDS):
            raise ValueError('Text field has another shape.')
        findings = value.get('findings', [])
        if not isinstance(findings, list) or any(not isinstance(f, dict) for f in findings):
            raise ValueError('Findings have another shape.')
        keys = [f.get('key') for f in findings]
        if any(not isinstance(k, str) or not k for k in keys) or len(set(keys)) != len(keys):
            raise ValueError('Finding identities are ambiguous.')
        if any(k in f and not isinstance(f[k], str) for f in findings for k in FINDING_FIELDS):
            raise ValueError('Finding text has another shape.')
        # Unknown fields remain visible in the fallback, not silently discarded.
        if set(value) - {'schema_version', *TEXT_FIELDS, 'findings', 'numbers', 'charts', 'facts'}:
            raise ValueError('Unsupported report content.')
        if any(set(f) - {'key', *FINDING_FIELDS, 'facts'} for f in findings):
            raise ValueError('Unsupported finding content.')
        doc = {'schema_version': 1, **{k: value.get(k, '') for k in TEXT_FIELDS},
               'findings': [{'key': f['key'], **{k: f.get(k, '') for k in FINDING_FIELDS}} for f in findings]}
        def facts(value):
            if not isinstance(value, list) or len(value) > 32 or any(not isinstance(k, str) or not 1 <= len(k) <= 100 or any(c in k for c in '{}') for k in value):
                raise ValueError('Facts must reference number keys.')
            return [{'number_key': k, 'text': ''} for k in value]
        if 'facts' in value:
            doc['facts'] = facts(value['facts'])
        for source, finding in zip(findings, doc['findings']):
            if 'facts' in source:
                finding['facts'] = facts(source['facts'])
        if value.get('charts') is not None:
            doc['charts'] = charts.normalize(value['charts'], set(keys))
        refs = value.get('numbers', [])
        if not isinstance(refs, list):
            raise ValueError('Number references have another shape.')
        return doc, refs, []
    except (ValueError, TypeError, RecursionError):
        return {'schema_version': 1, 'title': '', 'summary': text, 'scope': '', 'limitations': '', 'findings': []}, [], ['report_format_fallback']


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
