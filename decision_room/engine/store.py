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
            'status': 'received', 'verification': 'not_requested', 'presentation': 'not_evaluated',
            'delivery_via': row['delivery_via']}


def receive_document(config, run_id, token, *, request_key, html, via="mcp", _business=None):
    """Authenticate and commit first; deliberately never parse the draft.

    The MCP call sends a UTF-8 string. Byte input also supports trusted recovery
    of an interrupted export. Identity is the exact bytes, not normalized JSON.
    """
    if via not in ("mcp", "file"):
        raise ValueError("Invalid delivery route.")
    if not isinstance(request_key, str) or not 1 <= len(request_key) <= 128:
        raise ValueError('Invalid delivery request key.')
    if not isinstance(html, (str, bytes)):
        raise ValueError('Deliver a HTML string or raw bytes.')
    raw = html.encode('utf-8') if isinstance(html, str) else html
    raw_sha256 = admission.sha(raw)
    if len(raw) > MAX_DRAFT_BYTES:
        record_rejected(config, run_id, token, size=len(raw), sha256=raw_sha256, via=via, _business=_business)
        raise ValueError('Draft exceeds 256 KiB.')
    if _business is None:
        admission.authenticate(config, run_id, token)
    with connect(config) as db, db.transaction():
        # Serialize revisions and recheck revocation/waiting at commit admission.
        if _business is None:
            run = admission._locked(db, run_id, token)
            error = admission._active(db, run)
        else:
            from .control import _run
            run = _run(db, _business, run_id)
            error = None
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
                (id,business_id,document_id,ordinal,request_key,raw,raw_sha256,delivery_via)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *''',
                             (uuid4(), run['business_id'], document_id, ordinal, request_key, raw, raw_sha256, via)).fetchone()
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


def record_rejected(config, run_id, token, *, size, sha256, via, _business=None):
    """Count oversized attempts without retaining or exposing their content."""
    if type(size) is not int or size <= MAX_DRAFT_BYTES or via not in ('file', 'mcp') or not isinstance(sha256, str) or len(sha256) != 64 or any(c not in '0123456789abcdef' for c in sha256):
        raise ValueError('Invalid rejected-delivery metadata.')
    if _business is None:
        admission.authenticate(config, run_id, token)
    with connect(config) as db, db.transaction():
        if _business is None:
            row = admission._locked(db, run_id, token)
            error = admission._active(db, row)
            if error:
                raise admission.Aborted(error)
        else:
            from .control import _run
            _run(db, _business, run_id)
        admission._event(db, run_id, 'delivery_rejected',
                         {'bytes': size, 'sha256': sha256, 'via': via, 'reason': 'receipt_limit'})


def receive_file(config, business_id, run_id, collected):
    """Trusted controller recovery of a stopped runtime, including partials.

    The caller authorizes the business and verifies the runtime identity. Agent
    tokens cannot use this path; preserving bytes never changes execution status.
    """
    business_id, run_id = UUID(str(business_id)), UUID(str(run_id))
    if collected['status'] == 'missing':
        return None
    if collected['status'] == 'oversized':
        record_rejected(config, run_id, None, size=collected['bytes'],
                        sha256=collected['sha256'], via='file', _business=business_id)
        return None
    raw = collected['raw']
    if len(raw) != collected['bytes'] or admission.sha(raw) != collected['sha256']:
        raise ValueError('File delivery integrity mismatch.')
    return receive_document(config, run_id, None, request_key='file:' + collected['sha256'],
                            html=raw, via='file', _business=business_id)
