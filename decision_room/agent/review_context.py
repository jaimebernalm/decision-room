"""Reconstruct both roles' context from durable records, not process memory."""
import json
from copy import deepcopy

from ..execution import get_execution
from ..storage import Storage, digest
from .context import encoded, fingerprint
from .persistence import answers
from .review_contract import checks


def events(db, review_id):
    return db.execute('SELECT * FROM agent_review_events WHERE review_id=%s ORDER BY step', (review_id,)).fetchall()


def latest_report(history, knowledge):
    for event in reversed(history):
        if event['action']['action'] == 'submit' and event['knowledge_sha256'] == knowledge:
            return event['action']['report'], event['step']
    return None, 0


def observation(config, business_id, execution_id, knowledge, current_knowledge, verified_files):
    row = get_execution(config, business_id, execution_id)
    store = Storage(config.storage)
    path = store.path(business_id, row['code_key'])
    if digest(path) != row['code_sha256']:
        raise ValueError('Stored Python code failed its integrity check.')
    for item in row['inputs'].values():
        key = item['parquet_key']
        if key not in verified_files:
            if digest(store.path(business_id, key)) != item['parquet_sha256']:
                raise ValueError('Prepared source failed its integrity check.')
            verified_files.add(key)
    return {'execution_id': str(row['id']), 'status': row['status'], 'current': knowledge == current_knowledge,
            'knowledge_sha256': knowledge, 'code': path.read_text(), 'code_sha256': row['code_sha256'],
            'inputs': {alias: {k: t[k] for k in ('id', 'original_names', 'parquet_sha256', 'row_count')}
                       for alias, t in row['inputs'].items()},
            'result': row['result'], 'logs': row['logs'], 'issue': row['issue'],
            'artifacts': [{k: a[k] for k in ('name', 'sha256', 'byte_count')} for a in row['artifacts']]}


def material(config, db, session, run):
    history = events(db, run['id'])
    sources = {i['execution_id']: run['snapshot']['initial_knowledge'] for i in run['snapshot']['executions']}
    sources.update({str(e['execution_id']): e['knowledge_sha256'] for e in history if e['execution_id']})
    verified_files = set()
    observations = [observation(config, session['business_id'], execution_id, key,
                                run['knowledge_sha256'], verified_files) for execution_id, key in sources.items()]
    report, report_step = latest_report(history, run['knowledge_sha256'])
    owner_answers = answers(db, session['id'])
    conversation = [{'step': e['step'], 'role': e['role'], 'action': e['action'],
                     'knowledge_sha256': e['knowledge_sha256'], 'execution_id': str(e['execution_id']) if e['execution_id'] else None}
                    for e in history]
    # Answers are attached to their question in the dialogue as well as in owner_answers.
    replies = db.execute('SELECT * FROM agent_review_answers WHERE review_id=%s ORDER BY step', (run['id'],)).fetchall()
    by_step = {r['step']: {'text': r['text'], 'disposition': r['disposition']} for r in replies}
    for event in conversation:
        if event['step'] in by_step:
            event['owner_answer'] = by_step[event['step']]
    return {'owner_context': run['snapshot']['source']['owner_context'], 'owner_answers': owner_answers,
            'plan': run['snapshot']['proposal'], 'candidate_history': run['snapshot']['findings'],
            'planning_history': run['snapshot']['planning_history'], 'tables': run['snapshot']['tables'],
            'conversation': conversation, 'observations': observations,
            'report': report, 'report_step': report_step, 'checks': checks(report, observations),
            'budgets': {**run['options'], 'turns_used': len(history),
                        'review_rounds_used': sum(e['role'] == 'reviewer' and e['action']['action'] != 'execute' for e in history),
                        'python_used': {role: sum(e['role'] == role and e['action']['action'] == 'execute' for e in history)
                                        for role in ('analyst', 'reviewer')},
                        'questions_used': sum(e['action']['action'] == 'ask_owner' for e in history)}}


def model_context(materialized, role):
    context = deepcopy(materialized)
    context['role'] = role
    # Keep every turn and every distinct payload, but send identical code/report
    # only once. Explicit references point to full objects in this same request;
    # this is lossless deduplication, not a generated memory summary.
    observations = {item['execution_id']: item for item in context['observations']}
    for event in context['conversation']:
        action = event['action']
        observed = observations.get(event.get('execution_id'))
        if action.get('code') and observed and action['code'] == observed['code']:
            action['code'] = ''
            event['code_reference'] = {'execution_id': event['execution_id'], 'field': 'observations.code'}
        if action.get('report') is not None and action['report'] == context['report']:
            action['report'] = None
            event['report_reference'] = 'report'
    for item in context['observations']:
        item['logs'] = {k: v[-3000:] if isinstance(v, str) else v for k, v in item['logs'].items()}
        item['logs_may_be_truncated'] = True
        if item['result'] and len(encoded(item['result']).encode()) > 64000:
            item['result'] = None
            item['result_omitted'] = True
    # Full conversation is retained. Exceeding the budget pauses safely, rather
    # than dropping an objection or silently presenting a truncated conversation.
    if len(encoded(context).encode()) > 200000:
        raise ValueError('Review context exceeds 200 KB; automatic compaction is not implemented.')
    return json.loads(encoded(context))


def approval_digest(materialized, knowledge):
    cited = {ref['execution_id'] for claim in materialized['report']['claims'] for ref in claim['evidence']}
    for chart in materialized['report'].get('charts', []):
        cited.update(point['value']['execution_id'] for point in chart['points'])
        if chart.get('series'):
            cited.add(chart['series']['execution_id'])
    cited.update(h['value']['execution_id'] for h in materialized['report'].get('highlights', []))
    for check in materialized['report']['checks']:
        cited.update(ref['execution_id'] for ref in [check['actual'], *check['operands']])
    return fingerprint({'report': materialized['report'], 'knowledge': knowledge,
                        'evidence': [o for o in materialized['observations'] if o['execution_id'] in cited],
                        'checks': materialized['checks']})
