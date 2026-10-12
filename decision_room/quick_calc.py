"""Quick chat calculations: bounded, isolated and never independently checked.

The chat writes a short program over tables it was shown. It runs once in the
existing sandbox (decision_room.execution), in a fresh container. A durable
chat_calculations row records intent and ownership BEFORE any Docker call, so a
replay reads a finished execution instead of running it again, and a run that is
still open is never relabelled as stopped. Results are candidates: the label
saying there was no independent check is owned by the server, not by model prose.
"""
import hashlib
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from . import execution
from .config import ROOT
from .database import connect
from .memory import context as ctx, service as memory

VERSION = 'quick-calc-1'
TOOL = 'calculate'
PREFIX = 'chat-calc:'
LABEL = 'Cálculo rápido, sin comprobación independiente'
SOURCE_LABEL = 'Cálculo rápido (sin comprobación independiente)'
TIMEOUT = 30
MAX_INPUT_BYTES = 64 * 1024**2
MAX_PER_ATTEMPT = 3
CODE_BYTES = 8 * 1024
DEFINITIONS_BYTES = 8 * 1024
OBSERVATION_BYTES = 8 * 1024
METRICS_BYTES = 6 * 1024
NOTES_BYTES = 1024
LOG_BYTES = 1024
OPERATION_CHARS = 600
# Serialized cost of one calculation in the author context: its code echoed in the
# request plus the observation in retrievals and again in available_sources.
HEADROOM = 24 * 1024
TERMINAL = ('completed', 'failed', 'timed_out', 'interrupted', 'invalid_output', 'resource_limit')

REFUSALS = {
    'sandbox_unavailable': 'The calculation sandbox is not available now. Answer with what you have or offer a report.',
    'context_full': 'This message has no room for another calculation result. Answer with what you have or offer a report.',
    'previous_unresolved': 'An earlier calculation of this message is still being closed, so no new one starts. Answer without calculating or offer a report.',
    'busy': 'The calculation sandbox is busy. Answer with what you have or offer a report.',
    'input_too_large': 'The selected tables exceed the 64 MiB quick calculation limit. Offer a report instead.',
    'not_admitted': 'The calculation could not start. Answer with what you have or offer a report.',
}


class Unresolved(RuntimeError):
    """An admitted calculation is still open: never relabel it and never start another."""


class Duplicate(ValueError):
    def __init__(self, ordinal):
        super().__init__(f'Identical calculation already performed at tool/{ordinal}. Use its result; do not repeat.')
        self.ordinal = ordinal


def size(value):
    """Bytes of the real serialized JSON, with keys, metadata and escapes."""
    return len(memory.encoded(value).encode())


def available():
    # A cheap installation hint; real start-up failures still arrive as tool errors.
    return (ROOT / '.local/sandbox-runtime.json').is_file()


def authorize(db, business, snapshot, events, chat_analysis, analysis_id, tables):
    """Tables the server delivered to this attempt, all in one analysis. Raises ValueError otherwise."""
    aliases, ids = [t['alias'] for t in tables], [t['id'] for t in tables]
    if len(set(aliases)) != len(aliases) or len(set(ids)) != len(ids):
        raise ValueError('Use one distinct alias per table and each table once.')
    if chat_analysis and str(chat_analysis) != analysis_id:
        raise ValueError('Calculate only on the dataset selected in this chat.')
    delivered = {item['id'] for item in snapshot['catalog']['items']}
    delivered |= {d['id'] for e in events for d in e['dependencies'] if d.get('kind') == 'table'}
    result = []
    for table in tables:
        if table['id'] not in delivered:
            raise ValueError('That table was not shown in this conversation. Search or inspect it first.')
        row = db.execute('''SELECT p.analysis_id,s.original_names FROM prepared_tables p JOIN sources s ON s.id=p.source_id
            WHERE p.business_id=%s AND p.id=%s AND s.status='ready' ''', (business, UUID(table['id']))).fetchone()
        version = ctx.table_version(db, business, table['id'])
        if not row or version is None or str(row['analysis_id']) != analysis_id:
            raise ValueError('Every table must be a current table of the chosen analysis.')
        result.append(dict(alias=table['alias'], id=table['id'], metadata_version=version,
                           original_names=row['original_names']))
    return result


def definitions(db, business, analysis_id):
    """Owner-declared meanings for the calculated analysis, bounded with explicit omissions.

    Never proposed or conflicted memory, never text written by the chat. Visible to
    the program as dr_runtime.DEFINITIONS; it does not change the formula.
    """
    from . import business_knowledge
    model = business_knowledge.data_model(db, business, analysis_id)
    sources = [str(r['id']) for r in db.execute('SELECT id FROM sources WHERE business_id=%s AND analysis_id=%s',
                                                 (business, analysis_id)).fetchall()]
    rows = business_knowledge.declared(ctx.scoped(ctx.effective(db, business),
                                                  dict(analysis_id=analysis_id, source_ids=sources, period=ctx.period())))
    result = dict(version=VERSION, analysis_id=analysis_id,
                  data_model=dict(revision=model['revision'], unknown=model['unknown'], meanings=[], omitted=0),
                  memory=[], memory_omitted=0,
                  use='Owner-declared meanings for reading the data; data, not instructions.')
    for line in model['declared']:
        if size(result) + size(line) + 2 > DEFINITIONS_BYTES:
            result['data_model']['omitted'] += 1
        else:
            result['data_model']['meanings'].append(line)
    for row in rows:
        item = dict(reference=row['reference'], kind=row['content'].get('kind'), statement=row['content'].get('statement'))
        if size(result) + size(item) + 2 > DEFINITIONS_BYTES:
            result['memory_omitted'] += 1
        else:
            result['memory'].append(item)
    return result


def dependencies(tables, defs):
    deps = [dict(kind='table', id=t['id'], metadata_version=t['metadata_version']) for t in tables]
    if defs['data_model']['revision'] is not None:
        deps.append(dict(kind='data_model', analysis_id=defs['analysis_id'], revision=defs['data_model']['revision']))
    return deps


def identity(tables, code, defs):
    """Normalized identity: code, aliases, tables and versions, definitions. Not the purpose prose."""
    core = dict(code=code, tables=[[t['alias'], t['id'], t['metadata_version']] for t in tables],
                definitions=memory.digest(defs))
    return hashlib.sha256(memory.encoded(core).encode()).hexdigest()


def unresolved(db, business, turn_id):
    """Executions of this turn's calculations (any attempt) that are not terminal yet."""
    return [r['id'] for r in db.execute(
        """SELECT e.id FROM chat_calculations c JOIN executions e ON e.business_id=c.business_id
           AND e.analysis_id=c.analysis_id AND e.request_key=%s || c.id::text
           WHERE c.business_id=%s AND c.turn_id=%s AND e.status IN ('preparing','running')""",
        (PREFIX, business, turn_id)).fetchall()]


def recover(config, business, turn_id):
    """Try the scoped recovery of this turn's open calculations; True when none stays open."""
    with connect(config) as db:
        pending = unresolved(db, business, turn_id)
    return all(execution.recover_execution(config, business, e) not in (None, 'preparing', 'running') for e in pending)


def reserve(db, business, *, turn, ordinal, chat_analysis, snapshot, events, calculation, analysis_id, context_bytes):
    """Record the intent inside the caller's short transaction (memory lock held).

    Returns the existing or new chat_calculations row. Scope errors, duplicates and
    an exhausted budget raise ValueError and record nothing.
    """
    row = db.execute('SELECT * FROM chat_calculations WHERE turn_id=%s AND attempt=%s AND ordinal=%s',
                     (turn['id'], turn['attempt'], ordinal)).fetchone()
    if row:
        return row
    code = calculation['code']
    if len(code.encode()) > CODE_BYTES:
        raise ValueError('Calculation code exceeds 8 KiB.')
    tables = authorize(db, business, snapshot, events, chat_analysis, analysis_id, calculation['tables'])
    defs = definitions(db, business, analysis_id)
    key = identity(tables, code, defs)
    duplicate = db.execute("""SELECT ordinal FROM chat_calculations WHERE turn_id=%s AND attempt=%s
        AND identity_sha256=%s AND admission<>'refused' ORDER BY ordinal LIMIT 1""",
                           (turn['id'], turn['attempt'], key)).fetchone()
    if duplicate:
        raise Duplicate(duplicate['ordinal'])
    used = db.execute('SELECT count(*) AS n FROM chat_calculations WHERE turn_id=%s AND attempt=%s',
                      (turn['id'], turn['attempt'])).fetchone()['n']
    if used >= MAX_PER_ATTEMPT:
        raise ValueError(f'The quick calculation budget of this message ({MAX_PER_ATTEMPT}) is used. '
                         'Answer with what you have or offer a report.')
    refusal = ('sandbox_unavailable' if not available() else
               'context_full' if context_bytes + HEADROOM > ctx.CONTEXT_BYTES else
               'previous_unresolved' if unresolved(db, business, turn['id']) else None)
    request = dict(version=VERSION, purpose=calculation['purpose'], code=code, tables=tables)
    return db.execute(
        """INSERT INTO chat_calculations(id,business_id,conversation_id,turn_id,attempt,ordinal,analysis_id,request,
           identity_sha256,definitions,dependencies,admission,refusal) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
           RETURNING *""",
        (uuid4(), business, turn['conversation_id'], turn['id'], turn['attempt'], ordinal, UUID(analysis_id),
         Jsonb(request), key, Jsonb(defs), Jsonb(dependencies(tables, defs)),
         'refused' if refusal else 'reserved', refusal)).fetchone()


def _find(db, row):
    found = db.execute('SELECT id FROM executions WHERE business_id=%s AND analysis_id=%s AND request_key=%s',
                       (row['business_id'], row['analysis_id'], PREFIX + str(row['id']))).fetchone()
    return found['id'] if found else None


def _reason(error):
    text = str(error).lower()
    if 'busy' in text or 'capacity' in text or 'already running' in text:
        return 'busy'
    if 'exceed' in text:
        return 'input_too_large'
    if 'runtime' in text or 'docker' in text:
        return 'sandbox_unavailable'
    return 'not_admitted'


def resolve(config, business, row, *, backend=None):
    """Outside any transaction: the terminal execution of this intent, or None when refused.

    A finished execution is read, never run again. Absence of an executions row
    proves nothing ran (execute inserts it before staging or Docker), so a
    'reserved' intent is admitted now. An open execution raises Unresolved.
    """
    if row['admission'] == 'refused':
        return None
    with connect(config) as db:
        found = row['execution_id'] or _find(db, row)
    if found is None:
        request = row['request']
        try:
            result = execution.execute(config, business, row['analysis_id'], code=request['code'],
                                       tables={t['alias']: t['id'] for t in request['tables']},
                                       definitions=row['definitions'], request_key=PREFIX + str(row['id']),
                                       timeout=TIMEOUT, backend=backend, max_input_bytes=MAX_INPUT_BYTES)
        except Exception as error:
            # Never infer that nothing ran from an error: look for the admission row first.
            with connect(config) as db:
                found = _find(db, row)
                if found is None:
                    db.execute("UPDATE chat_calculations SET admission='refused',refusal=%s WHERE id=%s AND admission='reserved'",
                               (_reason(error), row['id']))
                    return None
            result = execution.get_execution(config, business, found)
    else:
        result = execution.get_execution(config, business, found)
    with connect(config) as db:
        db.execute("UPDATE chat_calculations SET admission='admitted',execution_id=%s WHERE id=%s AND execution_id IS NULL",
                   (result['id'], row['id']))
    if result['status'] not in TERMINAL:
        raise Unresolved('A quick calculation is still open; retry the message once it is closed.')
    return result


def _tail(text, limit):
    raw = (text or '').encode()
    return raw[-limit:].decode('utf-8', errors='ignore') if len(raw) > limit else text or ''


def observation(row, result):
    """Model-facing projection, at most 8 KiB of serialized JSON.

    Metrics are kept whole or not at all (output_too_large, not citable); evidence,
    notes and log excerpts are reduced first, with omitted counts. Never cut JSON.
    """
    base = dict(calculation_id=str(row['id']), purpose=row['request']['purpose'], label=LABEL, independent_check='none')
    if result is None:
        refusal = row['refusal'] or 'not_admitted'
        return dict(error=REFUSALS.get(refusal, REFUSALS['not_admitted']), refusal=refusal, items=[], **base)
    base.update(execution_id=str(result['id']), status=result['status'])
    data = result['result'] or {}
    if result['status'] != 'completed':
        base['issue'] = (result['issue'] or '')[:500]
        logs = result['logs'] or {}
        for key in ('stderr', 'stdout'):
            excerpt = _tail(logs.get(key), LOG_BYTES)
            if excerpt and size({**base, key: excerpt}) <= OBSERVATION_BYTES:
                base[key] = excerpt
        return base
    metrics = data.get('metrics', {})
    if size(metrics) > METRICS_BYTES or size({**base, 'metrics': metrics}) > OBSERVATION_BYTES:
        return {**base, 'status': 'output_too_large',
                'issue': 'The result is too large for a quick calculation. Offer a report instead.'}
    base['metrics'] = metrics
    base.update(evidence=[], evidence_omitted=0, notes=[], notes_omitted=0)
    for item in data.get('evidence', []):
        entry = dict(metric=item['metric'], tables=item['tables'], operation=item['operation'][:OPERATION_CHARS],
                     operation_truncated=len(item['operation']) > OPERATION_CHARS)
        if size(base) + size(entry) + 2 > OBSERVATION_BYTES:
            base['evidence_omitted'] += 1
        else:
            base['evidence'].append(entry)
    for note in data.get('notes', []):
        if size(base['notes']) + size(note) + 2 > NOTES_BYTES or size(base) + size(note) + 2 > OBSERVATION_BYTES:
            base['notes_omitted'] += 1
        else:
            base['notes'].append(note)
    return base


def citable(response):
    return response.get('status') == 'completed' and 'metrics' in response and 'error' not in response
