"""Follow-up register: native report actions as owner topics, deterministic and verbatim.

Each action block of a delivered native report revision is stored as an immutable
snapshot (revision + position, full branches). Each snapshot belongs to one owner
topic; a topic follows a new revision only with an exact, unambiguous correspondence
(same position and content, or content that is unique on both sides), so a closure is
never copied to another action. The owner alone sets proposed / checked / closed; the
system only changes availability (a deleted report withdraws its topics, a restore
brings them back with their state). Nothing is summarised by a model.
"""
from uuid import uuid4

from psycopg.types.json import Jsonb

from .database import connect
from .memory import service as memory
from .web.errors import WebError, bounded, identifier

VERSION = 'follow-ups-1'
STATES = ('proposed', 'checked', 'closed')
OPEN = ('proposed', 'checked')
BRANCHES = ('check', 'if_confirmed', 'if_not')
STATE_LABELS = dict(proposed='propuesto', checked='comprobado con datos (declarado por el propietario)', closed='cerrado por el propietario')


def digest(value):
    import hashlib
    return hashlib.sha256(memory.encoded(value).encode()).hexdigest()


def _document(db, business, document_id):
    return db.execute('''SELECT d.*,rev.presentation_state,rev.created_at AS delivered_at,r.status AS run_status,
            w.title AS job_title,w.deleted_at AS job_deleted_at,v.dataset_id
        FROM report_documents d
        LEFT JOIN report_document_revisions rev ON rev.business_id=d.business_id AND rev.document_id=d.id AND rev.id=d.current_revision_id
        LEFT JOIN engine_runs r ON r.business_id=d.business_id AND r.id=d.source_run_id
        LEFT JOIN web_jobs w ON w.business_id=d.business_id AND w.report_document_id=d.id AND w.engine_run_id=d.source_run_id
        LEFT JOIN dataset_versions v ON v.business_id=d.business_id AND v.analysis_id=d.analysis_id
        WHERE d.business_id=%s AND d.id=%s''', (business, document_id)).fetchone()


def snapshots(db, business, document):
    """Every action block of the current revision, verbatim, in document order."""
    from .engine import blocks
    from .reports import native_store
    derived = native_store.result(db, business, document['id'], document['current_revision_id'])
    if not derived or derived['status'] != 'ready':
        return None
    projection = derived['document']
    cover = next((b for b in projection['blocks'] if b['type'] == 'cover'), None)
    headline = (cover['title'] if cover else None) or projection.get('title') or document['job_title'] or 'Informe'
    items, position = [], 0
    for priority in blocks.walk(projection['blocks']):
        if priority['type'] != 'priority':
            continue
        for block in blocks.walk(priority['blocks']):
            if block['type'] != 'action':
                continue
            content = dict(labels={k: blocks.action_label(block, k) for k in BRANCHES},
                           **{k: (blocks._content_lines(block[k]) if block[k] is not None else None) for k in BRANCHES})
            items.append(dict(block_id=block['id'], position=position, priority_title=priority['title'], content=content,
                              content_sha256=digest(dict(priority=priority['title'], content=content)), headline=headline))
            position += 1
    return items


def available(document):
    return bool(document and document['origin'] == 'engine_blocks' and document['deleted_at'] is None
                and document['job_deleted_at'] is None and document['current_revision_id']
                and document['run_status'] == 'delivered' and document['presentation_state'] != 'blocked')


def sync_document(db, business, document_id):
    """Idempotent, in the caller's transaction (memory lock, then the document lock)."""
    document = _document(db, business, document_id)
    if not document or document['origin'] != 'engine_blocks':
        return
    marker = db.execute('SELECT * FROM follow_up_sync WHERE document_id=%s', (document_id,)).fetchone()
    items = snapshots(db, business, document) if available(document) else None
    present = document['deleted_at'] is None
    if items is None:
        db.execute("""UPDATE follow_ups SET availability='withdrawn',withdrawn_reason='source_unavailable',revision=revision+1,updated_at=now()
            WHERE business_id=%s AND document_id=%s AND availability='available'""", (business, document_id))
        # Keep the last synced revision so a restore reattaches the same topics.
        _mark(db, business, document_id, marker['revision_id'] if marker else None, present)
        return
    revision = document['current_revision_id']
    if marker and marker['revision_id'] == revision:
        # Same revision: only a restore can change anything.
        db.execute("""UPDATE follow_ups f SET availability='available',withdrawn_reason=NULL,revision=f.revision+1,updated_at=now()
            FROM follow_up_actions a WHERE a.id=f.current_action_id AND a.revision_id=%s AND f.business_id=%s AND f.document_id=%s
            AND f.availability='withdrawn' AND f.withdrawn_reason='source_unavailable'""", (revision, business, document_id))
        _mark(db, business, document_id, revision, present)
        return
    audit = report_state(db, business, document, revision)  # As it was at this sync; consumers read report_states().
    for item in items:
        db.execute('''INSERT INTO follow_up_actions(id,business_id,document_id,revision_id,block_id,position,priority_title,content,
            content_sha256,headline,report_date,dataset_id,analysis_id,metadata) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (revision_id,block_id) DO NOTHING''',
                   (uuid4(), business, document_id, revision, item['block_id'], item['position'], item['priority_title'],
                    Jsonb(item['content']), item['content_sha256'], item['headline'], document['delivered_at'],
                    document['dataset_id'], document['analysis_id'], Jsonb(audit)))
    new = db.execute('SELECT * FROM follow_up_actions WHERE revision_id=%s AND topic_id IS NULL ORDER BY position',
                     (revision,)).fetchall()
    # Only the topics of the previously synced revision can follow into this one.
    old = db.execute('''SELECT f.*,a.block_id,a.revision_id FROM follow_ups f JOIN follow_up_actions a ON a.id=f.current_action_id
        WHERE f.business_id=%s AND f.document_id=%s AND a.revision_id=%s''',
                     (business, document_id, marker['revision_id'])).fetchall() if marker and marker['revision_id'] else []
    pairs = _match(old, new)
    for topic, action in pairs:
        db.execute("""UPDATE follow_ups SET current_action_id=%s,availability='available',withdrawn_reason=NULL,revision=revision+1,
            updated_at=now() WHERE id=%s""", (action['id'], topic['id']))
        db.execute('UPDATE follow_up_actions SET topic_id=%s WHERE id=%s', (topic['id'], action['id']))
    matched_old = {t['id'] for t, _ in pairs}
    matched_new = {a['id'] for _, a in pairs}
    for topic in old:
        if topic['id'] not in matched_old and topic['availability'] == 'available':
            db.execute("""UPDATE follow_ups SET availability='withdrawn',withdrawn_reason='superseded',revision=revision+1,updated_at=now()
                WHERE id=%s""", (topic['id'],))
    for action in new:
        if action['id'] not in matched_new:
            topic = uuid4()
            db.execute('''INSERT INTO follow_ups(id,business_id,document_id,content_sha256,current_action_id,state,availability)
                VALUES (%s,%s,%s,%s,%s,'proposed','available')''', (topic, business, document_id, action['content_sha256'], action['id']))
            db.execute('UPDATE follow_up_actions SET topic_id=%s WHERE id=%s', (topic, action['id']))
    _mark(db, business, document_id, revision, present)


def report_state(db, business, document, revision_id):
    """The report's current staleness and the state of its independent check, for one revision."""
    from .engine import check_contract, native_checks
    from .reports import store
    checks = native_checks.read(db, business, document['source_run_id'], revision_id)
    return dict(stale_reason=store.reason(db, document), check_state=checks['state'],
                warnings=len(check_contract.visible(checks)['items']))


def report_states(db, business, rows):
    """Per document of these topics, computed now (staleness changes after delivery)."""
    states = {}
    for row in rows:
        key = (row['document_id'], row['revision_id'])
        if key not in states:
            document = db.execute('SELECT * FROM report_documents WHERE business_id=%s AND id=%s', (business, row['document_id'])).fetchone()
            states[key] = report_state(db, business, document, row['revision_id'])
    return {k[0]: v for k, v in states.items()}


def _match(old, new):
    """Exact and unambiguous only: same position and content, then content unique on both sides."""
    pairs, used_old, used_new = [], set(), set()
    for topic in old:
        action = next((a for a in new if a['block_id'] == topic['block_id'] and a['content_sha256'] == topic['content_sha256']), None)
        if action and action['id'] not in used_new:
            pairs.append((topic, action)); used_old.add(topic['id']); used_new.add(action['id'])
    rest_old = [t for t in old if t['id'] not in used_old]
    rest_new = [a for a in new if a['id'] not in used_new]
    for topic in rest_old:
        same_old = [t for t in rest_old if t['content_sha256'] == topic['content_sha256']]
        same_new = [a for a in rest_new if a['content_sha256'] == topic['content_sha256']]
        if len(same_old) == 1 and len(same_new) == 1 and same_new[0]['id'] not in used_new:
            pairs.append((topic, same_new[0])); used_new.add(same_new[0]['id'])
    return pairs


def _mark(db, business, document_id, revision, present):
    # `available` records the deletion flag the reconciliation compares; availability itself is per topic.
    is_available = present
    db.execute('''INSERT INTO follow_up_sync(document_id,business_id,revision_id,available) VALUES (%s,%s,%s,%s)
        ON CONFLICT (document_id) DO UPDATE SET revision_id=EXCLUDED.revision_id,available=EXCLUDED.available,synced_at=now()''',
               (document_id, business, revision, is_available))


def reconcile_once(config, limit=20):
    """Paginated catch-up for existing reports and missed events; decided per document."""
    with connect(config) as db:
        rows = db.execute('''SELECT d.id,d.business_id FROM report_documents d LEFT JOIN follow_up_sync s ON s.document_id=d.id
            WHERE d.origin='engine_blocks' AND (s.document_id IS NULL OR s.revision_id IS DISTINCT FROM d.current_revision_id
                OR s.available IS DISTINCT FROM (d.deleted_at IS NULL)) ORDER BY d.id LIMIT %s''', (limit,)).fetchall()
        for row in rows:
            from .reports import store
            with db.transaction():
                memory.lock(db, row['business_id'])
                store.lock(db, row['id'])
                sync_document(db, row['business_id'], row['id'])
                bump(db, row['business_id'])
    return bool(rows)


# ---- Owner states --------------------------------------------------------------------

def set_state(config, business, follow_up_id, data):
    """Owner-only transition with audit; a link freezes the indicator value used to check it."""
    from . import indicators
    key = identifier(data.get('request_key'))
    follow_up_id = identifier(follow_up_id)
    state = data.get('state')
    if state not in STATES:
        raise WebError('Elige propuesto, comprobado o cerrado.')
    note = bounded(data.get('note') or '', 'la nota', 300, required=False) or None
    link = data.get('link')
    request = dict(follow_up_id=str(follow_up_id), state=state, note=note, link=link, expected=data.get('expected_revision'))
    sha = digest(request)
    with connect(config) as db, db.transaction():
        memory.lock(db, business)
        prior = db.execute('SELECT * FROM follow_up_events WHERE business_id=%s AND request_key=%s', (business, key)).fetchone()
        if prior:
            if prior['request_sha256'] != sha:
                raise WebError('Este envío ya se guardó con otros datos.', 409)
            return dict(follow_up_id=str(follow_up_id), state=prior['to_state'])
        topic = db.execute('SELECT * FROM follow_ups WHERE business_id=%s AND id=%s FOR UPDATE', (business, follow_up_id)).fetchone()
        if not topic:
            raise WebError('Ese tema no existe en este negocio.', 404)
        if topic['availability'] != 'available' or topic['revision'] != data.get('expected_revision'):
            raise WebError('El tema ha cambiado. Recarga antes de guardarlo.', 409)
        frozen = None
        if link is not None:
            if state != 'checked' or not isinstance(link, dict) or set(link) != {'indicator_id', 'metric_key', 'value_id'}:
                raise WebError('Enlaza un indicador y una de sus cifras solo al marcarlo como comprobado.')
            indicator = identifier(link['indicator_id'])
            values = indicators.current_values(db, business, indicator)
            version = db.execute("SELECT id,metric_keys FROM indicator_versions WHERE business_id=%s AND indicator_id=%s AND state='active'",
                                 (business, indicator)).fetchone()
            # Only the latest value, as the owner saw it; never an older completed one in its place.
            if (not version or link['metric_key'] not in version['metric_keys'] or not values or values[0]['status'] != 'completed'
                    or str(values[0]['id']) != str(identifier(link['value_id']))):
                raise WebError('Esa cifra del indicador ya no es la actual. Recarga antes de enlazarla.', 409)
            value = values[0]
            frozen = dict(indicator_id=str(indicator), version_id=str(value['version_id']), value_id=str(value['id']),
                          metric_key=link['metric_key'], value=value['metrics'][link['metric_key']],
                          dataset_version=value['dataset_version'], meanings_basis=value['meanings_basis'])
        db.execute('UPDATE follow_ups SET state=%s,note=%s,link=%s,revision=revision+1,updated_at=now() WHERE id=%s',
                   (state, note, Jsonb(frozen) if frozen else None, follow_up_id))
        db.execute('''INSERT INTO follow_up_events(id,business_id,follow_up_id,request_key,request_sha256,from_state,to_state,note,link)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)''', (uuid4(), business, follow_up_id, key, sha, topic['state'], state, note,
                                                 Jsonb(frozen) if frozen else None))
        bump(db, business)
    return dict(follow_up_id=str(follow_up_id), state=state)


# ---- Projection and freshness --------------------------------------------------------

def listing(db, business, *, include_closed=False):
    """Available topics with their current snapshot, newest report first, then document order."""
    states = STATES if include_closed else OPEN
    return db.execute('''SELECT f.id,f.state,f.note,f.link,f.revision,f.document_id,a.revision_id,a.block_id,a.position,a.priority_title,
            a.content,a.headline,a.report_date,a.dataset_id,a.analysis_id,a.metadata
        FROM follow_ups f JOIN follow_up_actions a ON a.id=f.current_action_id
        WHERE f.business_id=%s AND f.availability='available' AND f.state=ANY(%s)
        ORDER BY a.report_date DESC,f.document_id,a.position''', (business, list(states))).fetchall()


def counts(db, business):
    row = db.execute('''SELECT count(*) FILTER (WHERE availability='available' AND state=ANY(%s)) AS open,
        count(*) FILTER (WHERE availability='available' AND state='closed') AS closed,
        count(*) FILTER (WHERE availability='withdrawn') AS withdrawn FROM follow_ups WHERE business_id=%s''',
                     (list(OPEN), business)).fetchone()
    return dict(row)


def projection(db, business):
    return dict(items=[{k: str(v) if k in ('id', 'document_id', 'revision_id', 'dataset_id', 'analysis_id') and v else v
                        for k, v in row.items()} for row in listing(db, business, include_closed=True)], counts=counts(db, business))


def bump(db, business):
    """Raise the follow-ups revision only when the owner-visible projection changed (caller holds memory.lock)."""
    sha = digest(projection(db, business))
    row = db.execute('''INSERT INTO knowledge_heads(business_id,follow_ups_revision,follow_ups_sha256) VALUES (%s,1,%s)
        ON CONFLICT (business_id) DO UPDATE SET follow_ups_revision=knowledge_heads.follow_ups_revision+1,follow_ups_sha256=EXCLUDED.follow_ups_sha256
        WHERE knowledge_heads.follow_ups_sha256<>EXCLUDED.follow_ups_sha256 RETURNING follow_ups_revision''', (business, sha)).fetchone()
    return row['follow_ups_revision'] if row else None
