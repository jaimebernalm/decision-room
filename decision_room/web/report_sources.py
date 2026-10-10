"""Small, read-only report provenance, without samples or machine paths."""
from ..database import connect


def view(ws, job_id):
    job = ws.row(job_id)  # Enforces the active business, including deleted reports.
    with connect(ws.config) as db, db.transaction():
        session = db.execute('''SELECT source_snapshot,created_at FROM agent_sessions
            WHERE id=%s AND business_id=%s''', (job['session_id'], job['business_id'])).fetchone()
        if not session:
            return {'tables': None, 'added_tables': []}
        tables = [{'id': table['id'], 'name': table['names'][0]}
                  for table in session['source_snapshot']['tables']]
        family = db.execute('''SELECT coalesce(v.dataset_id,a.id) AS id
            FROM analyses a LEFT JOIN dataset_versions v ON v.analysis_id=a.id
            WHERE a.id=%s AND a.business_id=%s''', (job['analysis_id'], job['business_id'])).fetchone()
        current = db.execute('''SELECT p.id,s.original_names->>0 AS name,
            coalesce(v.dataset_id,a.id) AS family FROM prepared_tables p
            JOIN sources s ON s.id=p.source_id AND s.business_id=p.business_id
            JOIN analyses a ON a.id=p.analysis_id AND a.business_id=p.business_id
            LEFT JOIN dataset_versions v ON v.analysis_id=a.id
            WHERE p.business_id=%s AND p.created_at>%s AND a.id!=%s
            AND a.status IN ('ready','partial') AND NOT coalesce(v.corrected,false)
            AND v.superseded_by IS NULL
            AND NOT EXISTS (SELECT 1 FROM dataset_uploads u WHERE u.business_id=a.business_id
                AND u.result->>'pending'='true' AND u.result->>'existing_id' IS NULL
                AND u.result->>'batch_sha256'=a.batch_sha256)
            ORDER BY p.created_at,p.id''',
            (job['business_id'], session['created_at'], job['analysis_id'])).fetchall()
        old_names = {table['name'] for table in tables}
        old_ids = {table['id'] for table in tables}
        added = [{'id': str(table['id']), 'name': table['name']} for table in current
                 if str(table['id']) not in old_ids
                 and (table['family'] != family['id'] or table['name'] not in old_names)]
    # The snapshot is the input catalogue, not proof that every table was used in a calculation.
    return {'tables': tables, 'added_tables': added}
