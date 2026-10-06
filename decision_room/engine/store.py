"""Receive exact draft bytes before any report parsing or analytical validation.

A receipt is not a verified report or a completed engine run. These document IDs
can later be adopted by the neutral report registry without fabricating legacy
sessions or approvals. Raw revisions never have an update path in this module.
"""
import os
import tempfile
from pathlib import Path
from uuid import UUID, uuid4

from ..database import connect
from . import admission

MAX_DRAFT_BYTES = 256 * 1024


def _receipt(row):
    return {'document_id': str(row['document_id']), 'revision_id': str(row['id']),
            'ordinal': row['ordinal'], 'raw_sha256': row['raw_sha256'],
            'status': 'received', 'verification': 'pending'}


def receive_document(config, run_id, token, *, request_key, draft_json):
    """Authenticate and commit first; deliberately never parse the draft.

    The MCP call sends a UTF-8 string. Byte input also supports trusted recovery
    of an interrupted export. Identity is the exact bytes, not normalized JSON.
    """
    if not isinstance(request_key, str) or not 1 <= len(request_key) <= 128:
        raise ValueError('Invalid delivery request key.')
    if not isinstance(draft_json, (str, bytes)):
        raise ValueError('Deliver a JSON string or raw bytes.')
    raw = draft_json.encode('utf-8') if isinstance(draft_json, str) else draft_json
    if len(raw) > MAX_DRAFT_BYTES:
        raise ValueError('Draft exceeds 256 KiB.')
    raw_sha256 = admission.sha(raw)
    admission.authenticate(config, run_id, token)
    with connect(config) as db, db.transaction():
        # Serialize revisions and recheck revocation/waiting at commit admission.
        run = admission._locked(db, run_id, token)
        error = admission._active(db, run)
        if not error:
            document = db.execute('SELECT id FROM engine_documents WHERE run_id=%s', (run_id,)).fetchone()
            document_id = document['id'] if document else uuid4()
            if not document:
                db.execute('INSERT INTO engine_documents(id,business_id,run_id) VALUES (%s,%s,%s)',
                           (document_id, run['business_id'], run_id))
            previous = db.execute('''SELECT * FROM engine_document_revisions
                WHERE document_id=%s AND request_key=%s''', (document_id, request_key)).fetchone()
            if previous:
                if previous['raw_sha256'] != raw_sha256 or bytes(previous['raw']) != raw:
                    raise ValueError('Delivery key already used with different bytes.')
                return _receipt(previous)
            ordinal = db.execute('''SELECT COALESCE(max(ordinal),0)+1 AS n
                FROM engine_document_revisions WHERE document_id=%s''', (document_id,)).fetchone()['n']
            row = db.execute('''INSERT INTO engine_document_revisions
                (id,business_id,document_id,ordinal,request_key,raw,raw_sha256)
                VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING *''',
                             (uuid4(), run['business_id'], document_id, ordinal, request_key, raw, raw_sha256)).fetchone()
            admission._event(db, run_id, 'draft_received', _receipt(row))
    if error:
        raise admission.Aborted(error)
    return _receipt(row)


def read_document(config, business_id, run_id, *, revision_id=None):
    """Trusted product read, permitted after abortion/expiry to recover content.

    The product must authorize business access; a job token is not accepted as
    owner authority. Omitted revision selects the last durably received draft.
    """
    business_id, run_id = UUID(str(business_id)), UUID(str(run_id))
    with connect(config) as db:
        if not db.execute('SELECT id FROM engine_runs WHERE business_id=%s AND id=%s',
                          (business_id, run_id)).fetchone():
            raise admission.Denied('Job not found for this business.')
        condition, params = '', [business_id, run_id]
        if revision_id is not None:
            condition = ' AND r.id=%s'
            params.append(UUID(str(revision_id)))
        row = db.execute('''SELECT r.* FROM engine_document_revisions r
            JOIN engine_documents d ON d.business_id=r.business_id AND d.id=r.document_id
            WHERE d.business_id=%s AND d.run_id=%s''' + condition +
                         ' ORDER BY r.ordinal DESC LIMIT 1', params).fetchone()
    if not row:
        if revision_id is not None:
            raise admission.Denied('Revision not found for this job.')
        return None
    raw = bytes(row['raw'])
    if admission.sha(raw) != row['raw_sha256']:
        raise ValueError('Stored draft failed its integrity check.')
    return {**_receipt(row), 'raw': raw}


def _write_atomic(path, raw):
    """Private export: do not follow an existing file symlink or leave a half file."""
    fd, temporary = tempfile.mkstemp(prefix='.engine-export-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def export_raw(config, business_id, run_id, dest, *, revision_id=None):
    """Materialize raw bytes before future rendering; not the full export_run API."""
    row = read_document(config, business_id, run_id, revision_id=revision_id)
    if row is None:
        return None
    folder = Path(dest)
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    _write_atomic(folder / 'draft.raw', row['raw'])
    receipt = {k: v for k, v in row.items() if k != 'raw'}
    _write_atomic(folder / 'draft-receipt.json', admission.canonical(receipt))
    return receipt
