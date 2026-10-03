"""Durable business direction, separate from numeric investigation and approval."""
from copy import deepcopy
from uuid import UUID, uuid4, uuid5

from langgraph.types import interrupt
from psycopg.types.json import Jsonb
from pydantic import Field
from typing import Literal

from .contracts import Strict, Question
from .context import fingerprint

VERSION = 'business-planner-v12'


class BusinessBrief(Strict):
    objective: str = Field(min_length=1, max_length=1600)
    decision: str = Field(min_length=1, max_length=1200)
    intent: Literal['organize', 'discover', 'question', 'evolution', 'mixed']
    deliverables: list[str] = Field(min_length=1, max_length=12)
    known_context: list[str] = Field(max_length=12)
    assumptions: list[str] = Field(max_length=12)
    exclusions: list[str] = Field(max_length=12)


class OwnerQuestion(Question):
    impact: Literal['context', 'definition', 'scope']


from .delivery_contract import DecisionOrientation, AUTONOMY


class Direction(Strict):
    orientation: list[DecisionOrientation] = Field(default_factory=list, max_length=6)
    action: Literal['guide', 'ask_owner', 'ready', 'replan']
    brief: BusinessBrief
    rationale: str = Field(min_length=1, max_length=1800)
    instructions: list[str] = Field(max_length=10)
    priority_keys: list[str] = Field(max_length=24)
    evidence_keys: list[str] = Field(max_length=24)
    question: OwnerQuestion | None


SYSTEM = '''You are Decision Room's BUSINESS PLANNER, a specialist in connecting
business goals to useful analytical work. You do not calculate, execute code,
approve a report, or direct workers. The principal analyst owns technical methods,
evidence-linked drilldowns and worker assignments. Reply only as Direction JSON;
all client-facing text in Spanish. The user prioritizes product quality over cost.

Build a concrete business brief from accepted_owner_request.text (or the original
owner_context) and actual owner answers. The brief is your working interpretation,
not an owner-confirmed replacement. Its deliverables are proposed components;
optional methods belong in instructions. The original request remains authoritative
at every checkpoint, even when your interpretation changes.
Keep every expressly requested component in deliverables, distinguishing confirmed
owner context from assumptions. Do not narrow the goal to excuse incomplete work.
Do not expand deliverables by promoting your chosen drilldowns, optional percentages
or exhaustive inventories to owner requirements. When the owner requests a few
prioritized findings, a justified selection can answer that request; a complete
listing of every product is not implied. Keep supporting methods and optional
views in instructions, separately from the owner's requested delivery. Compare
the brief with the original owner text at each checkpoint, not only with your
previous brief. Changing wording does not establish owner confirmation.
Read available shared memory before asking for already-known information. Existing
provisional planning interprets sources; your role determines priorities and what
would make the work useful. Supported historical intents only; prediction remains
unavailable. Brainstorming is not an implemented report mode.

At initial/checkpoint stages, guide the analyst using concise actionable directions.
Read analyst_message for its explicit consultation, progress summary or proposed
final synthesis. Address the actual question; compare the proposed priorities with
saved evidence and the business brief rather than merely repeating the agenda.
At delivery, inspect saved results and the original goal: ready means adequate
material to draft, NEVER independently verified or approved. For final HTML/PDF
generation, chart rendering or export, keep the requirement in the
delivery brief and explicitly hand it to drafting/review/the application renderer.
Do not require the completed report file before declaring research material ready:
that would block the later phase responsible for creating it. Judge readiness by
saved business evidence and useful visual measures, not HTML bytes/chart counts.
If a feasible missing
component matters, guide with the specific next investigation and why. Initial
rankings are not enough for discovery when a useful finer breakdown is feasible.
Use evidence_keys only for saved candidates and priority_keys only for agenda keys;
new branch suggestions go in instructions, for the analyst to instantiate safely.
Avoid opening irrelevant branches or repeatedly demanding identical work. Do not
ask the user to do a calculation possible from supplied data. Spend available effort
on useful depth, coverage and interpretation rather than minimizing tokens.

Your final ready response is also a BUSINESS HANDOFF, not just permission to stop.
Its instructions must tell the drafting analyst what answer/priority should lead,
why that priority matters relative to alternatives, and what the client can check
next. For discovery, connect a named segment and period to a specific missing
operational fact and explain which decision or competing interpretation that fact
would help distinguish. These are conditional checks, not established causes.
Generic source/coverage verification is insufficient when the actual goal is a
business decision. Do not fill this gap by opening more arithmetic branches once
the necessary evidence exists: synthesize its business use in the handoff.
Unknown context can remain an explicit limit and a concrete future check; do not
repeat a question the owner cannot answer. For organizing data or a factual question,
give the requested views/answer and their use without forcing recommendations.

Ask ONE question when its answer could materially improve interpretation or the
next decision, including during research. Explain why and refer to exact available
tables/columns where appropriate so the conversational UI can show the data. Use
impact=context for operating/business context; definition for units, grain, joins,
coverage or numerical meanings; scope for a proposed change to the accepted goal.
Do not invent commercial causes from correlations. Ask about a change of scope
before pursuing it; a refusal/unknown answer does not authorize it. Never repeat an
answered, unknown or declined question, even with a new key. Optional missing context
must not prevent a useful limited result. Do not ask speculative interview questions.

When owner_replies are present, incorporate their actual text and disposition.
A definition/scope answer forces a new plan and fresh calculation; return replan.
Also return replan if a nominally contextual reply actually corrects a definition
or changes scope. Unknown/refused replies are limits, not evidence or permission.
Otherwise guide with the contextual answer; saved arithmetic remains available.
Do not treat your own brief or hypotheses as owner-confirmed facts.
Use question=null unless ask_owner. ready is only allowed at stage=delivery.
'''
from .goal_quality import GOAL_QUALITY
from .delivery_contract import DECISION_READINESS
SYSTEM += GOAL_QUALITY + AUTONOMY + DECISION_READINESS
SYSTEM += '''\nAt the final handoff, choose the main supported answer and the useful
reading order relative to the owner's actual goal. Tell the analyst what each
finding adds rather than requesting separate findings that repeat a conclusion.
Keep essential uncertainty and partial coverage explicit, but do not prescribe
repeated disclaimers in every field. The analyst owns concise client wording and
visual composition; the reviewer still independently assesses the delivery.
Guide the business question and priority, not a compulsory chart or method.
The analyst may choose saved observed/derived/reference calendar layers, optional
rolling trends or another useful transformation. Request evidence and a clear
comparison when useful, not smoothing by default or a prescribed window.\n'''


def events(db, research_id):
    return db.execute('SELECT * FROM business_planner_events WHERE research_id=%s ORDER BY ordinal', (research_id,)).fetchall()


def replies(db, research_id):
    rows = db.execute('''SELECT a.id,a.disposition,a.text,e.id AS question_id,e.direction->'question' AS question
        FROM business_planner_answers a JOIN business_planner_events e ON e.id=a.event_id
        WHERE e.research_id=%s ORDER BY e.ordinal''', (research_id,)).fetchall()
    return [{**r,'id':str(r['id']),'question_id':str(r['question_id'])} for r in rows]


def pending(db, research_id):
    return db.execute('''SELECT e.id,e.direction->'question' AS question FROM business_planner_events e
        LEFT JOIN business_planner_answers a ON a.event_id=e.id
        WHERE e.research_id=%s AND e.direction->>'action'='ask_owner' AND a.id IS NULL ORDER BY e.ordinal''',
        (research_id,)).fetchall()


def enrich(db, research_id, snapshot):
    rows = events(db, research_id)
    if not rows:
        return snapshot
    result = deepcopy(snapshot)
    result['business_direction'] = dict(brief=rows[-1]['direction']['brief'],
        checkpoints=[dict(stage=r['stage'], **r['direction']) for r in rows],
        owner_replies=replies(db, research_id))
    return result


def validate(raw, context):
    action = Direction.model_validate(raw)
    tasks = {i['key'] for i in context['plan']['investigations']}
    candidates = {f['investigation_key'] for f in context['findings'] if f['status'] == 'candidate'}
    if not set(action.priority_keys) <= tasks or not set(action.evidence_keys) <= candidates:
        raise ValueError('Use only actual agenda keys and saved candidate evidence keys.')
    from ..series import evidence_value
    observed = [{**o, 'current': True, 'inputs': {t['alias']: t for t in context['table_catalog']}}
                for o in context.get('observations', [])]
    for item in action.orientation:
        for ref in item.evidence:
            evidence_value(observed, ref.model_dump())
    if action.action == 'ready' and context['stage'] != 'delivery':
        raise ValueError('Only the delivery checkpoint may declare material ready for drafting.')
    if (action.action == 'ask_owner') != (action.question is not None):
        raise ValueError('Only ask_owner requires a question; all other actions need question=null.')
    if action.action in ('guide','ready') and not action.instructions:
        raise ValueError('Guide needs concrete next work; ready needs a concrete business handoff for the draft.')
    if action.action == 'replan' and not any(r['disposition'] == 'answered' for r in context['owner_replies']):
        raise ValueError('Replanning scope/definitions requires an actual owner answer.')
    if action.question:
        q = action.question
        previous = [r['direction']['question'] for r in context['prior_checkpoints'] if r['direction'].get('question')]
        previous += [a['question'] for a in context['answers'] if isinstance(a.get('question'), dict)]
        if any(q.key == p.get('key') or q.text.strip().casefold() == p.get('text','').strip().casefold() for p in previous):
            raise ValueError('Do not repeat previous questions, including unknown/refused answers.')
        tables = {t['id']: t for t in context['table_catalog']}
        for ref in q.references:
            if ref.kind == 'owner_context' and ref.id == 'owner_context' and not ref.column:
                continue
            if ref.kind not in ('table','column') or ref.id not in tables:
                raise ValueError('Question references must use an available table/column or owner_context.')
            if ref.kind == 'column' and ref.column not in tables[ref.id]['column_names']:
                raise ValueError('Unknown question column.')
            if ref.kind == 'table' and ref.column:
                raise ValueError('Table references require empty column.')
    return action.model_dump()


def checkpoint(config, db, session, run, model, state, guard, retry_uncertain):
    from .persistence import model_call
    from .research_graph import steps, findings
    from .research_agenda import agenda, ResearchBudgetReached
    from .research_context import observations, prompt_context
    stage = 'delivery' if state.get('action', {}).get('action') == 'finish' else 'initial' if state['turn'] == 0 else 'checkpoint'
    # A node can replay after a human interrupt or crash; all side effects below
    # have deterministic keys and committed events before the interrupt.
    while True:
        waiting = pending(db, run['id'])
        if waiting:
            interrupt({'type': 'business_questions', 'questions': [dict(id=str(q['id']), **q['question']) for q in waiting]})
        owner = replies(db, run['id'])
        if any(r['disposition'] == 'answered' and r['question']['impact'] in ('definition','scope') for r in owner):
            return {'replan_required': True, 'stop_reason': 'Una respuesta cambia definiciones o alcance; se necesita una planificación actualizada.'}
        history = steps(db, run['id']); recorded = findings(db, run['id'])
        current = agenda(run['snapshot'], history)
        context = prompt_context(current, observations(config, session['business_id'], history), recorded, run['options'], state['turn'])
        for observation in context['observations']:
            observation.pop('code', None); observation.pop('logs', None)
        prior = events(db, run['id'])
        if (stage == 'delivery' and len(history) >= 3 and len(prior) >= 2
                and all(s['action']['action'] == 'finish' for s in history[-3:])
                and all(e['stage'] == 'delivery' and e['direction']['action'] == 'guide' for e in prior[-2:])):
            raise ResearchBudgetReached('La entrega repite el mismo cierre sin nuevo trabajo; se conserva la evidencia para revisar el bloqueo, sin declarar aprobación.')
        action = state.get('action', {})
        context.update(stage=stage, owner_replies=owner,
            analyst_message={k: action[k] for k in ('action','summary','synthesis') if k in action} or None,
            prior_checkpoints=[dict(stage=e['stage'], direction=e['direction']) for e in prior])
        key = fingerprint(dict(stage=stage, turn=state['turn'], replies=owner))
        saved = next((e for e in prior if e['checkpoint_key'] == key), None)
        if saved:
            direction = saved['direction']
        else:
            if len(prior) >= run['options']['max_planner_checkpoints']:
                raise ResearchBudgetReached('Límite de consultas de negocio alcanzado; se conserva el trabajo y el encargo.')
            correction = None
            for attempt in range(2):
                raw = model_call(db, session['id'], model, context, correction, retry_uncertain, config=config,
                    phase='business_planner', scope=str(run['id']), max_calls=run['options']['max_model_calls'], before_call=guard)
                try:
                    direction = validate(raw, context); break
                except ValueError as error:
                    correction = str(error)[:1800]
                    if attempt: raise ValueError('Business planner output failed validation twice: ' + correction) from None
            db.execute('''INSERT INTO business_planner_events(id,research_id,business_id,ordinal,checkpoint_key,stage,direction)
                VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (research_id,checkpoint_key) DO NOTHING''',
                (uuid5(UUID(str(run['id'])), key),run['id'],session['business_id'],len(prior)+1,key,stage,Jsonb(direction)))
        if direction['action'] == 'ask_owner':
            continue
        return dict(planner_ready=direction['action']=='ready', replan_required=direction['action']=='replan',
                    stop_reason='Se necesita actualizar el plan con la respuesta del cliente.' if direction['action']=='replan' else '')


def save_answer(db, session, run, question_id, text, disposition, request_key):
    if disposition not in ('answered','unknown','declined') or not isinstance(text,str) or len(text)>6000:
        raise ValueError('Invalid business answer.')
    if (disposition=='answered') != bool(text.strip()):
        raise ValueError('Provide answer text, or explicitly choose unknown/declined without text.')
    if not isinstance(request_key,str) or not 1<=len(request_key)<=200:
        raise ValueError('Invalid answer request key.')
    event=db.execute('SELECT * FROM business_planner_events WHERE id=%s AND research_id=%s AND business_id=%s',
                     (question_id,run['id'],session['business_id'])).fetchone()
    if not event or event['direction']['action']!='ask_owner':raise ValueError('Question does not belong to this research.')
    prior=db.execute('SELECT * FROM business_planner_answers WHERE event_id=%s',(question_id,)).fetchone()
    if prior:
        if (prior['text'],prior['disposition'],prior['request_key'])!=(text,disposition,request_key):raise ValueError('Question already answered differently.')
        return
    if run['status']!='waiting' or session['superseded_by']:raise ValueError('Research is not waiting for this answer.')
    from ..memory.service import capture_answer
    with db.transaction():
        answer_id=uuid4()
        db.execute('INSERT INTO business_planner_answers(id,event_id,business_id,research_id,text,disposition,request_key) VALUES (%s,%s,%s,%s,%s,%s,%s)',
                   (answer_id,event['id'],session['business_id'],run['id'],text,disposition,request_key))
        db.execute('UPDATE agent_research SET paused_seconds=paused_seconds+EXTRACT(EPOCH FROM (now()-%s)) WHERE id=%s',
                   (event['created_at'],run['id']))
        capture_answer(db,session,answer_id,kind='planning_answer',text=text,question=event['direction']['question']['text'],disposition=disposition)


def successor_context(db, run):
    owner = replies(db,run['id'])
    import json
    return run['snapshot']['source']['owner_context'] + '\nAclaraciones posteriores del propietario (conservar desconocidos/rechazos; no repetir preguntas):\n' + json.dumps(owner,ensure_ascii=False,default=str)
