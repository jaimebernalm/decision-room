"""Reconstruct both roles' context from durable records, not process memory."""
import json
from copy import deepcopy

from ..execution import get_execution
from ..storage import Storage, digest
from .context import encoded, fingerprint
from .persistence import answers
from .review_contract import checks
from .review_policy import ledger, delivery_manifest
from .delivery_contract import owner_deliverables


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


def delivery_state(status, *, publishable=False):
    """Approval alone does not establish current, unheld export availability."""
    return {'content': status,
            'report_exports': 'available_on_request' if publishable else
                              'pending_approval' if status in ('new', 'running', 'waiting', 'draft_under_review') else 'unavailable',
            'browser_verification': 'not_performed_by_review'}


def material(config, db, session, run):
    history = events(db, run['id'])
    sources = {i['execution_id']: i.get('knowledge_sha256', run['snapshot']['initial_knowledge']) for i in run['snapshot']['executions']}
    sources.update({str(e['execution_id']): e['knowledge_sha256'] for e in history if e['execution_id']})
    verified_files = set()
    observations = [observation(config, session['business_id'], execution_id, key,
                                run['knowledge_sha256'], verified_files) for execution_id, key in sources.items()]
    panorama = None
    if run['options'].get('sales_panorama'):
        from ..sales_panorama_store import materialize
        panorama = materialize(config, session['business_id'], run['snapshot']['sales_panorama'], run['knowledge_sha256'])
        observations = panorama.pop('observations') + observations
    report, report_step = latest_report(history, run['knowledge_sha256'])
    controller_annotations = None
    if report and run['options'].get('owner_presentation'):
        from .research_agenda import limitation
        from .delivery_selection import selection_notes
        controller_annotations = {
            'coverage_note': limitation(run['snapshot'].get('research_coverage') or {}, report)
                if run['snapshot'].get('research_coverage') or report.get('owner_coverage') else None,
            'selection_notes': selection_notes(report, observations),
            'instruction': 'Controller-owned audit metadata, not writer prose. Do not block its wording; review actual structured coverage and evidence.'}
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
    return {**({'controller_annotations': controller_annotations} if controller_annotations else {}), **({'sales_panorama': panorama} if panorama is not None else {}), 'owner_context': run['snapshot']['source']['owner_context'], 'owner_answers': owner_answers,
            **({'accepted_owner_request': run['snapshot'].get('accepted_owner_request') or
                 {'text': run['snapshot']['source']['owner_context']},
                'owner_confirmed_answers': [a for a in owner_answers if a['disposition'] == 'answered']}
               if (run['options'].get('review_policy') or 0) >= 5 else {}),
            'plan': run['snapshot']['proposal'], 'candidate_history': run['snapshot']['findings'],
            'planning_history': run['snapshot']['planning_history'],
            'review_policy': run['options'].get('review_policy') or 0,
            'previous_review': run['snapshot'].get('previous_review'),
            'review_issues': ledger(conversation) or (run['snapshot'].get('previous_review') or {}).get('issues', []), 'delivery_manifest': delivery_manifest(report, observations),
            'research_coverage': run['snapshot'].get('research_coverage'),
            'research_synthesis': run['snapshot'].get('research_synthesis'),
            'business_direction': run['snapshot'].get('business_direction'),
            'owner_deliverables': owner_deliverables({'review_policy': run['options'].get('review_policy'),
                'accepted_owner_request': run['snapshot'].get('accepted_owner_request'),
                'business_direction': run['snapshot'].get('business_direction'),
                'owner_context': run['snapshot']['source']['owner_context']}),
            'delivery_capabilities': {'execution_artifact_downloads': False, 'chart_categories': 36, 'daily_line_points': 366,
                                      'temporal_line_points': 366, 'grouped_temporal_coordinates': 366,
                                      'whole_series_temporal_grain': 'inherited from saved observations; chart.temporal_grain=null is required, not missing metadata',
                                      'claim_evidence_refs': 12, 'claims': 6, 'charts': 4,
                                      'surfaces': ['web_report', 'static_html', 'pdf'],
                                      'report_exports': {'provider': 'application_controller',
                                          'formats': ['html', 'pdf'], 'available_after': 'approval',
                                          'requires_execution_artifact': False},
                                      'representations': {'bar': ['single', 'grouped'], 'table': ['single', 'grouped'], 'line': ['day', 'month', 'quarter', 'year', 'single', 'grouped']},
                                      'layers': {'selection': 'agent', 'max_layers': 6, 'max_points': 800, 'same_saved_unit_and_calendar_grain': True, 'styles': ['solid', 'dashed', 'dotted'], 'weight': ['normal', 'emphasis'], 'rolling_mean': 'optional; verified complete trailing calendar windows from saved source'},
                                      'selection': 'agent', 'orientation_contract': 'delivery-quality-v1'}, 'tables': run['snapshot']['tables'],
            'delivery_state': delivery_state(run['status']),
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
    if context.get('report'):
        from .report_reading import reading_feedback
        context['report_reading'] = reading_feedback(context['report'])
        if context.get('budgets', {}).get('owner_presentation'):
            from .owner_presentation import feedback
            context['owner_reading_feedback'] = feedback(context['report'], context.get('controller_annotations'))
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
            action['report'] = {'$ref': '#/report'}
            event['report_reference'] = 'report'
    for item in context['observations']:
        item['logs'] = {k: v[-3000:] if isinstance(v, str) else v for k, v in item['logs'].items()}
        item['logs_may_be_truncated'] = True
        if item['result'] and len(encoded(item['result']).encode()) > 64000:
            item['result'] = None
            item['result_omitted'] = True
    # Full conversation is retained. Exceeding the budget pauses safely, rather
    # than dropping an objection or silently presenting a truncated conversation.
    limit = context.get('budgets', {}).get('max_context_bytes', 200000)
    if len(encoded(context).encode()) > limit:
        raise ValueError(f'Review context exceeds {limit // 1000} KB; automatic compaction is not implemented.')
    return json.loads(encoded(context))


def approval_digest(materialized, knowledge):
    cited = {ref['execution_id'] for claim in materialized['report']['claims'] for ref in claim['evidence']}
    cited.update(ref['execution_id'] for claim in materialized['report']['claims']
                 for ref in (claim.get('orientation') or {}).get('evidence', []))
    for chart in materialized['report'].get('charts', []):
        cited.update(point['value']['execution_id'] for point in chart['points'])
        cited.update(item['value']['execution_id'] for detail in chart.get('details', []) for item in detail['values'])
        if chart.get('series'):
            cited.add(chart['series']['execution_id'])
        cited.update(layer['series']['execution_id'] for layer in chart.get('layers', []))
    cited.update(h['value']['execution_id'] for h in materialized['report'].get('highlights', []))
    cited.update(s['population']['execution_id'] for s in materialized['report'].get('delivery_selections', [])
                 if s.get('population'))
    for check in materialized['report']['checks']:
        cited.update(ref['execution_id'] for ref in [check['actual'], *check['operands']])
    policy = {'review_issues': materialized['review_issues'], 'delivery_manifest': materialized['delivery_manifest'],
              'assessment': next((e['action'].get('assessment') for e in reversed(materialized['conversation']) if e['role'] == 'reviewer'), None)} if materialized.get('review_policy') else {}
    if (materialized.get('review_policy') or 0) >= 5:
        policy['accepted_owner_request'] = materialized['accepted_owner_request']
        policy['owner_confirmed_answers'] = materialized['owner_confirmed_answers']
    return fingerprint({**policy, 'report': materialized['report'], 'knowledge': knowledge,
                        'evidence': [o for o in materialized['observations'] if o['execution_id'] in cited],
                        'checks': materialized['checks']})
