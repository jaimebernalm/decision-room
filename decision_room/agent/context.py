"""Only authorized ingestion metadata and bounded samples reach the model."""
import hashlib
import json

from ..service import describe


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def fingerprint(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


def snapshot(config, business_id, analysis_id, owner_context, *, research_panorama=None):
    if len(owner_context) > 12000:
        raise ValueError('Owner context limit: 12,000 characters.')
    report = describe(config, business_id, analysis_id, detailed=True)
    if report['analysis']['status'] not in ('ready', 'partial'):
        raise ValueError('Finish importing this batch before starting the agent.')
    tables, unavailable = [], []
    for source in report['files']:
        if source['status'] != 'ready' or not source.get('table_id'):
            unavailable.append({'names': source['original_names'], 'status': source['status']})
            continue
        tables.append({
            'id': str(source['table_id']), 'names': source['original_names'],
            'row_count': source['row_count'], 'sha256': source['parquet_sha256'],
            'column_names': [c['name'] for c in source['columns']],
            'columns': source['columns'],
            'sample_rows': source['profile']['sample_rows'][:5],
            'sample_scope': 'First five records, cells truncated at 200 characters; not representative coverage.',
            'null_rule': source['profile'].get('null_rule'),
        })
    if not tables:
        raise ValueError('No prepared tables available.')
    extra = {}
    if research_panorama is not None:
        from ..sales_panorama_store import materialize
        if not {t['table_id'] for t in research_panorama['tables']} <= {t['id'] for t in tables}:
            raise ValueError('Research panorama contains tables outside this source snapshot.')
        observations = research_panorama.get('observations', [])
        materialize(config, business_id, research_panorama, observations[0]['knowledge_sha256'] if observations else '')
        extra['research_panorama'] = research_panorama
    return {**extra, 'owner_context': owner_context, 'tables': sorted(tables, key=lambda t: t['id']),
            'unavailable_sources': unavailable}


def model_context(source, inspected, answers, previous):
    catalog = [{k: table[k] for k in ('id', 'names', 'row_count', 'column_names')}
               for table in source['tables']]
    context = {'owner_context': source['owner_context'], 'catalog': catalog,
               'profiles': [t for t in source['tables'] if t['id'] in inspected],
               'unavailable_sources': source['unavailable_sources'],
               'answers': answers, 'previous_proposal': previous,
               'uninspected_table_ids': [t['id'] for t in source['tables'] if t['id'] not in inspected]}
    from .panorama_research import expose
    context = expose(context, source)
    if len(encoded(context).encode()) > 200000:
        raise ValueError('Model context exceeds 200 KB. Start a smaller analysis batch.')
    return context
