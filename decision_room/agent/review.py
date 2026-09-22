"""Business-scoped entry points for persistent review, owner replies and reports."""
from uuid import uuid4

from langgraph.types import Command
from langsmith import tracing_context
from psycopg.types.json import Jsonb

from ..database import connect
from ..execution import execute
from .context import fingerprint, snapshot as source_snapshot
from .model import ModelClient, ModelSettings
from .persistence import checkpointer, session_lock
from .research import knowledge, mark_stale
from .research_graph import findings, steps
from .review_context import approval_digest, material
from .review_graph import REVIEW_GRAPH_VERSION, build


def _key(key):
    if not isinstance(key, str) or not key.strip() or len(key) > 160:
        raise ValueError('Request key must contain 1–160 characters.')


def _stale(config, db, session, run):
    _, _, current_key = knowledge(db, session)
    current_source = source_snapshot(config, session['business_id'], session['analysis_id'], session['source_snapshot']['owner_context'])
    return bool(session['superseded_by'] or run['status'] == 'stale' or run['graph_version'] != REVIEW_GRAPH_VERSION
                or current_key != run['knowledge_sha256']
                or fingerprint(current_source) != fingerprint(run['snapshot']['source']))


def start(config, business_id, research_id, *, request_key, analyst=None, reviewer=None,
          max_review_rounds=4, executor=execute):
    _key(request_key)
    if type(max_review_rounds) is not int or not 1 <= max_review_rounds <= 6:
        raise ValueError('Review rounds must be between 1 and 6.')
    with connect(config) as db:
        research = db.execute('SELECT * FROM agent_research WHERE id=%s AND business_id=%s', (research_id, business_id)).fetchone()
    if not research:
        raise ValueError('Research does not belong to this business.')
    with session_lock(config, business_id, research['session_id']) as (db, session):
        research = db.execute('SELECT * FROM agent_research WHERE id=%s', (research_id,)).fetchone()
        _, _, key = knowledge(db, session)
        if session['superseded_by'] or research['status'] == 'stale' or research['knowledge_sha256'] != key:
            raise ValueError('Research is obsolete. Recalculate with the current owner knowledge first.')
        if research['status'] in ('new', 'running'):
            raise ValueError('Wait for research to stop before reviewing its snapshot.')
        candidates = findings(db, research_id)
        if not any(f['status'] == 'candidate' for f in candidates):
            raise ValueError('Research needs at least one registered candidate before review.')
        analyst = analyst or ModelClient(ModelSettings(**session['model_settings']))
        reviewer = reviewer or ModelClient(ModelSettings(**session['model_settings']))
        if analyst.identity != session['model_settings']:
            raise ValueError('The analyst must retain the original session model settings.')
        executions = [{'execution_id': str(s['execution_id'])} for s in steps(db, research_id)
                      if s['action']['action'] == 'execute' and s['execution_id']]
        snapshot = {**research['snapshot'], 'findings': candidates, 'executions': executions, 'initial_knowledge': key,
                    'planning_history': db.execute('SELECT revision,proposal FROM agent_revisions WHERE session_id=%s ORDER BY revision',
                                                   (session['id'],)).fetchall()}
        options = {'max_review_rounds': max_review_rounds, 'max_turns': 20, 'max_calls_per_role': 16,
                   'max_python_per_role': 3, 'max_questions': 3, 'python_timeout': 30}
        request_hash = fingerprint({'snapshot': snapshot, 'reviewer': reviewer.identity, 'options': options, 'version': REVIEW_GRAPH_VERSION})
        row = db.execute('''INSERT INTO agent_reviews(id,business_id,session_id,analysis_id,research_id,request_key,
            request_sha256,knowledge_sha256,snapshot,reviewer_settings,options,graph_version,status)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'new')
            ON CONFLICT (session_id,request_key) DO NOTHING RETURNING *''',
            (uuid4(), business_id, session['id'], session['analysis_id'], research_id, request_key, request_hash,
             key, Jsonb(snapshot), Jsonb(reviewer.identity), Jsonb(options), REVIEW_GRAPH_VERSION)).fetchone()
        if not row:
            row = db.execute('SELECT * FROM agent_reviews WHERE session_id=%s AND request_key=%s', (session['id'], request_key)).fetchone()
        if row['request_sha256'] != request_hash:
            raise ValueError('Review request key already used with different inputs or settings.')
        _drive(config, db, session, row, analyst=analyst, reviewer=reviewer, executor=executor)
    return show(config, business_id, row['id'])


def _drive(config, db, session, run, *, analyst=None, reviewer=None, executor=execute, retry_uncertain=False):
    if db.execute('SELECT 1 FROM agent_review_holds WHERE review_id=%s', (run['id'],)).fetchone():
        raise ValueError('Review has an independent validation hold; correct the work in a new review.')
    if _stale(config, db, session, run):
        db.execute("UPDATE agent_reviews SET status='stale',issue='Knowledge or source changed.',updated_at=now() WHERE id=%s", (run['id'],))
        raise ValueError('Review is stale; start from current research.')
    try:
        if run['graph_version'] != REVIEW_GRAPH_VERSION:
            raise ValueError('Review graph needs migration before resuming.')
        analyst = analyst or ModelClient(ModelSettings(**session['model_settings']))
        reviewer = reviewer or ModelClient(ModelSettings(**run['reviewer_settings']))
        if analyst.identity != session['model_settings'] or reviewer.identity != run['reviewer_settings']:
            raise ValueError('Resume must retain both original role model settings.')
        with checkpointer(config) as saver, tracing_context(enabled=False):
            graph = build(config, db, session, run, analyst, reviewer, saver, executor=executor, retry_uncertain=retry_uncertain)
            setting = {'configurable': {'thread_id': 'review:' + str(run['id'])}, 'recursion_limit': 100}
            state = graph.get_state(setting)
            waiting = any(t.interrupts for t in state.tasks)
            argument = None
            if waiting:
                reply = db.execute('SELECT 1 FROM agent_review_answers WHERE review_id=%s AND step=%s', (run['id'], state.values['turn'])).fetchone()
                if not reply:
                    db.execute("UPDATE agent_reviews SET status='waiting',updated_at=now() WHERE id=%s", (run['id'],))
                    return
                argument = Command(resume={'answer_saved': True})
            elif not state.values:
                argument = {'turn': 0, 'role': 'analyst', 'action': {}, 'outcome': ''}
            db.execute("UPDATE agent_reviews SET status='running',issue=NULL,updated_at=now() WHERE id=%s", (run['id'],))
            if not state.values or state.next:
                graph.invoke(argument, setting, durability='sync')
            state = graph.get_state(setting)
            status = 'waiting' if any(t.interrupts for t in state.tasks) else state.values['outcome']
            issue = 'Review budget reached; no approval.' if status == 'limited' else state.values['action'].get('message')
            db.execute('UPDATE agent_reviews SET status=%s,issue=%s,updated_at=now() WHERE id=%s', (status, issue, run['id']))
    except Exception as error:
        issue = str(error)[:2400] if isinstance(error, ValueError) else type(error).__name__
        db.execute("UPDATE agent_reviews SET status='failed',issue=%s,updated_at=now() WHERE id=%s", (issue, run['id']))
        raise ValueError(f'Review {run["id"]} failed: {issue}') from None


def _parent(config, business_id, review_id):
    with connect(config) as db:
        row = db.execute('SELECT session_id FROM agent_reviews WHERE id=%s AND business_id=%s', (review_id, business_id)).fetchone()
    if not row:
        raise ValueError('Review does not belong to this business.')
    return row['session_id']


def resume(config, business_id, review_id, *, analyst=None, reviewer=None, executor=execute, retry_uncertain=False):
    with session_lock(config, business_id, _parent(config, business_id, review_id)) as (db, session):
        run = db.execute('SELECT * FROM agent_reviews WHERE id=%s', (review_id,)).fetchone()
        _drive(config, db, session, run, analyst=analyst, reviewer=reviewer, executor=executor, retry_uncertain=retry_uncertain)
    return show(config, business_id, review_id)


def answer(config, business_id, review_id, *, step, text='', disposition='answered', request_key,
           analyst=None, reviewer=None, executor=execute, retry_uncertain=False):
    _key(request_key)
    if disposition not in ('answered', 'unknown', 'declined') or len(text) > 6000 or (disposition == 'answered' and not text.strip()):
        raise ValueError('Provide a bounded answer or explicitly mark it unknown/declined.')
    with session_lock(config, business_id, _parent(config, business_id, review_id)) as (db, session):
        run = db.execute('SELECT * FROM agent_reviews WHERE id=%s', (review_id,)).fetchone()
        if _stale(config, db, session, run):
            raise ValueError('Cannot answer an obsolete review.')
        question = db.execute("SELECT * FROM agent_review_events WHERE review_id=%s AND step=%s AND action->>'action'='ask_owner'",
                              (review_id, step)).fetchone()
        if not question:
            raise ValueError('Question does not belong to this review.')
        prior = db.execute('SELECT * FROM agent_review_answers WHERE review_id=%s AND step=%s', (review_id, step)).fetchone()
        if prior:
            if (prior['request_key'], prior['text'], prior['disposition']) != (request_key, text, disposition):
                raise ValueError('Question already answered differently; use agent-replan for a corrected definition.')
        else:
            if run['status'] != 'waiting':
                raise ValueError('Review must be waiting for this owner answer.')
            with db.transaction():
                db.execute('''INSERT INTO agent_review_answers(id,review_id,step,disposition,text,request_key)
                    VALUES (%s,%s,%s,%s,%s,%s)''', (uuid4(), review_id, step, disposition, text, request_key))
                _, _, key = knowledge(db, session)
                db.execute('UPDATE agent_reviews SET knowledge_sha256=%s,approved_sha256=NULL WHERE id=%s', (key, review_id))
                mark_stale(db, session)
        run = db.execute('SELECT * FROM agent_reviews WHERE id=%s', (review_id,)).fetchone()
        _drive(config, db, session, run, analyst=analyst, reviewer=reviewer, executor=executor, retry_uncertain=retry_uncertain)
    return show(config, business_id, review_id)


def show(config, business_id, review_id):
    with connect(config) as db:
        run = db.execute('SELECT * FROM agent_reviews WHERE id=%s AND business_id=%s', (review_id, business_id)).fetchone()
        if not run:
            raise ValueError('Review does not belong to this business.')
        session = db.execute('SELECT * FROM agent_sessions WHERE id=%s', (run['session_id'],)).fetchone()
        stale = _stale(config, db, session, run)
        context = material(config, db, session, run)
        hold_record = db.execute('SELECT reason,created_at FROM agent_review_holds WHERE review_id=%s', (review_id,)).fetchone()
        valid_approval = bool(run['status'] == 'approved' and not stale and not hold_record and context['report'] and
                              all(c['passed'] for c in context['checks']) and
                              approval_digest(context, run['knowledge_sha256']) == run['approved_sha256'])
        pending = [e for e in context['conversation'] if e['action']['action'] == 'ask_owner' and 'owner_answer' not in e]
        calls = db.execute('''SELECT id,phase,status,usage,issue,prompt_version,created_at,finished_at
            FROM agent_calls WHERE session_id=%s AND scope=%s ORDER BY created_at''', (run['session_id'], str(review_id))).fetchall()
        return {**{k: v for k, v in run.items() if k != 'snapshot'},
                'status': 'stale' if stale else 'held' if hold_record else run['status'],
                'model_decision_status': run['status'], 'independent_hold': hold_record,
                'issue': hold_record['reason'] if hold_record else run['issue'],
                'publishable': valid_approval, 'verification': 'reviewed_by_agent' if valid_approval else 'not_approved',
                'report': context['report'], 'checks': context['checks'], 'observations': context['observations'],
                'owner_context': context['owner_context'], 'plan': context['plan'],
                'planning_history': context['planning_history'],
                'conversation': context['conversation'], 'owner_answers': context['owner_answers'],
                'pending_questions': pending if not stale else [], 'model_calls': calls,
                'remaining_plan': run['snapshot']['proposal']['investigations']}


def hold(config, business_id, review_id, *, reason):
    """Operator-only entry point, never exposed as an LLM action."""
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 4000:
        raise ValueError('An independent validation hold needs a reason of 1–4000 characters.')
    with session_lock(config, business_id, _parent(config, business_id, review_id)) as (db, _):
        previous = db.execute('SELECT reason FROM agent_review_holds WHERE review_id=%s', (review_id,)).fetchone()
        if previous and previous['reason'] != reason:
            raise ValueError('This review already has an independent hold. Preserve it and use a new review for corrections.')
        db.execute('INSERT INTO agent_review_holds(review_id,reason) VALUES (%s,%s) ON CONFLICT DO NOTHING', (review_id, reason))
    return show(config, business_id, review_id)
