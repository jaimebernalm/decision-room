"""Private static HTML snapshots. Model prose is always escaped, never executable."""
import json
from datetime import datetime, timezone
from uuid import uuid4

from .agent import review
from .agent.persistence import session_lock
from .storage import Storage
from .internal_report import render  # Backward-compatible internal renderer.
from .client_report import render_client


def export(config, business_id, review_id):
    # Read fresh scoped state, never trust a previously exported approval flag.
    # Prevent an owner reply/replan racing the approval check used for export.
    with session_lock(config, business_id, review._parent(config, business_id, review_id)):
        data = review.show(config, business_id, review_id)
        now = datetime.now(timezone.utc).isoformat(timespec='seconds')
    store = Storage(config.storage)
    directory = store.path(business_id, f'{business_id}/reports/{review_id}/{uuid4().hex}')
    directory.mkdir(parents=True, mode=0o700)
    html = directory / 'report.html'
    html.write_text(render_client(data, now))
    internal = directory / 'internal.html'
    internal.write_text(render(data, now))
    internal.chmod(0o600)
    html.chmod(0o600)
    audit = directory / 'review.json'
    audit.write_text(json.dumps({'exported_at': now, **data}, ensure_ascii=False, indent=2, default=str))
    audit.chmod(0o600)
    return {'path': str(html), 'audit_path': str(audit), 'internal_path': str(internal), 'status': data['status'],
            'publishable': data['publishable'], 'exported_at': now}
