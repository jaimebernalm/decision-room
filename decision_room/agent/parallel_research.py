"""Principal-directed fan-out with durable reservations and deterministic fan-in.

The parent session lock remains held. Workers own connections and checkpoints,
never session locks or recursive delegates. Quotas are reserved before launch.
"""
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from copy import deepcopy
from uuid import uuid4

from psycopg.types.json import Jsonb

from ..database import connect
from .context import fingerprint
from .research_agenda import ResearchBudgetReached, agenda


def branches(db, run_id):
    return db.execute('''SELECT b.*,r.status,r.issue,r.options,r.created_at,r.updated_at
        FROM agent_research_branches b JOIN agent_research r ON r.id=b.child_id
        WHERE b.parent_id=%s ORDER BY b.dispatch_step,b.ordinal''', (run_id,)).fetchall()


def calls(db, session_id, run_id):
    return db.execute('''SELECT c.id,c.scope,c.status,c.usage,c.issue,c.created_at,c.finished_at,c.prompt_version FROM agent_calls c WHERE c.session_id=%s AND c.phase IN ('research','business_planner')
        AND (c.scope=%s OR c.scope IN (SELECT child_id::text FROM agent_research_branches WHERE parent_id=%s))
        ORDER BY c.created_at,c.id''', (session_id, str(run_id), run_id)).fetchall()


def decisions(db, run_id):
    # Imported worker decisions already count in parent steps. Worker finish
    # stays local but still consumes the global decision budget.
    return db.execute("""SELECT count(*) n FROM agent_research_steps s
        WHERE s.research_id=%s OR (s.action->>'action'='finish' AND s.research_id IN
            (SELECT child_id FROM agent_research_branches WHERE parent_id=%s))""",
        (run_id, run_id)).fetchone()['n']


def reserve(db, session, run, state):
    from .research_graph import steps, findings, RESEARCH_GRAPH_VERSION
    from .research_context import observations
    existing = [b for b in branches(db, run['id']) if b['dispatch_step'] == state['turn']]
    if existing:
        return existing
    history = steps(db, run['id'])
    current = agenda(run['snapshot'], history)
    from .business_planner import enrich
    current = enrich(db, run['id'], current)
    assignments = state['action']['assignments']
    n = len(assignments)
    options = run['options']
    # Keep room for the principal's reconciliation and synthesis. Sum of all
    # reserved quotas cannot exceed remaining parent budgets, even on recovery.
    quotas = {
        'max_model_calls': min(16 if options.get('quality_first') else 8, (options['max_model_calls'] - len(calls(db, session['id'], run['id'])) - (6 if options.get('quality_first') else 3)) // n),
        'max_turns': min(16 if options.get('quality_first') else 8, (options['max_turns'] - decisions(db, run['id']) - 2) // n),
        'max_executions': min(6 if options.get('quality_first') else 3, (options['max_executions'] - sum(s['action']['action'] == 'execute' for s in history)) // n),
        'max_agenda': 1 + min(3, (options['max_agenda'] - len(current['proposal']['investigations'])) // n),
    }
    if quotas['max_model_calls'] < 2 or quotas['max_turns'] < 2 or quotas['max_executions'] < 1:
        raise ResearchBudgetReached('Presupuesto insuficiente para delegar y sintetizar; se conservan los candidatos.')
    shared = {'findings': findings(db, run['id']),
              'observations': observations(run['_config'], session['business_id'], history)}
    # The immutable parent observations are bounded by the same context formatter.
    from .research_context import prompt_context
    shared['observations'] = prompt_context(current, shared['observations'], shared['findings'], options, state['turn'])['observations']
    with db.transaction():
        for ordinal, assignment in enumerate(assignments):
            task = next(i for i in current['proposal']['investigations'] if i['key'] == assignment['investigation_key'])
            snapshot = deepcopy(current)
            snapshot['proposal']['investigations'] = [task]
            snapshot['coordination'] = shared
            child_options = {**options, **quotas, 'delegation': False, 'business_planner': False, 'worker_assignment': assignment,
                             'max_investigations': 1, 'max_rounds': 1, 'max_parallel': 1,
                             'existing_questions': [i['question'].strip().casefold() for i in current['proposal']['investigations']]}

            child = uuid4()
            request_key = f'branch:{run["id"]}:{state["turn"]}:{ordinal}'
            db.execute('''INSERT INTO agent_research(id,business_id,session_id,analysis_id,plan_revision,
                request_key,request_sha256,knowledge_sha256,snapshot,options,graph_version,status,created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'new',%s)''',
                (child, session['business_id'], session['id'], session['analysis_id'], run['plan_revision'],
                 request_key, fingerprint({'snapshot': snapshot, 'options': child_options}), run['knowledge_sha256'],
                 Jsonb(snapshot), Jsonb(child_options), RESEARCH_GRAPH_VERSION, run['created_at']))
            db.execute('''INSERT INTO agent_research_branches(business_id,parent_id,dispatch_step,ordinal,child_id,assignment)
                VALUES (%s,%s,%s,%s,%s,%s)''',
                (session['business_id'], run['id'], state['turn'], ordinal, child, Jsonb(assignment)))
            db.execute('UPDATE agent_research SET paused_seconds=%s WHERE id=%s', (run.get('paused_seconds',0),child))
    return [b for b in branches(db, run['id']) if b['dispatch_step'] == state['turn']]


def dispatch(config, db, session, run, state, model, executor, retry_uncertain):
    from . import research
    from .research_graph import steps, findings
    reserved = reserve(db, session, {**run, '_config': config}, state)

    def work(branch):
        with connect(config) as worker_db:
            worker_db.execute('UPDATE agent_research_branches SET started_at=COALESCE(started_at,now()) WHERE child_id=%s', (branch['child_id'],))
            child = worker_db.execute('SELECT * FROM agent_research WHERE id=%s AND business_id=%s',
                                      (branch['child_id'], session['business_id'])).fetchone()
            if child['status'] not in ('completed', 'partial'):
                # Actual model clients are stateless HTTP boundaries; create one
                # per worker. Scripted adapters may be shared for deterministic tests.
                from .model import ModelClient, ModelSettings
                worker_model = ModelClient(ModelSettings(**model.identity)) if type(model) is ModelClient else model
                try:
                    research._drive(config, worker_db, session, child, model=worker_model,
                                    executor=executor, retry_uncertain=retry_uncertain)
                finally:
                    worker_db.execute('UPDATE agent_research_branches SET finished_at=now() WHERE child_id=%s', (branch['child_id'],))
        return branch

    errors = []
    with ThreadPoolExecutor(max_workers=run['options']['max_parallel']) as pool:
        futures = [pool.submit(copy_context().run, work, b) for b in reserved]
        for future in futures:
            try:
                future.result()
            except BaseException as error:
                # Drain siblings before propagating an interruption. Their durable
                # checkpoints can be reused; do not swallow process termination.
                errors.append(error)
    if errors:
        raise next((e for e in errors if not isinstance(e, Exception)), errors[0])
    # Atomic import, in assignment order, so crash/replay never changes step IDs
    # or publishes one branch while another is still mutating its evidence.
    turn = state['turn']
    with db.transaction():
        for branch in reserved:
            child_steps = steps(db, branch['child_id'])
            child_findings = {f['step']: f for f in findings(db, branch['child_id'])}
            for item in child_steps:
                # A worker finish is not a coordinator finish.
                if item['action']['action'] == 'finish':
                    continue
                turn += 1
                existing = db.execute('SELECT action,execution_id FROM agent_research_steps WHERE research_id=%s AND step=%s',
                                      (run['id'], turn)).fetchone()
                if existing and (existing['action'] != item['action'] or existing['execution_id'] != item['execution_id']):
                    raise ValueError('Parallel merge differs from saved evidence.')
                db.execute('''INSERT INTO agent_research_steps(research_id,step,business_id,action,execution_id)
                    VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING''',
                    (run['id'], turn, session['business_id'], Jsonb(item['action']), item['execution_id']))
                finding = child_findings.get(item['step'])
                if finding:
                    db.execute('''INSERT INTO agent_research_findings(research_id,investigation_key,step,status,summary,metric_keys)
                        VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING''',
                        (run['id'], finding['investigation_key'], turn, finding['status'], finding['summary'], Jsonb(finding['metric_keys'])))
    return {'turn': turn}


def synthesis(history):
    return next((s['action']['synthesis'] for s in reversed(history) if s['action'].get('synthesis')), None)
