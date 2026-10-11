"""F0 engine orchestration only; report access and display belong to F1/F4."""
from ..database import connect
from ..engine import admission, api, control
from ..engine.export import snapshot


def reconcile(workspace, job):
    """Recover the stable run link without consulting any legacy agent tables."""
    with connect(workspace.config) as db:
        row = db.execute('SELECT id FROM engine_runs WHERE business_id=%s AND request_key=%s',
                         (job['business_id'], 'web:' + str(job['id']))).fetchone()
    if row:
        if job['engine_run_id'] and job['engine_run_id'] != row['id']:
            raise ValueError('Engine run link differs from its stable job key.')
        if not job['engine_run_id']:
            workspace.update(job['id'], engine_run_id=row['id'])
            job = workspace.row(job['id'])
        from ..reports.store import adopt
        adopt(workspace.config, job['business_id'], row['id'])
        job = workspace.row(job['id'])
    return job


def inputs(config, job):
    """Panorama from the prepared tables plus a brief builder, used once at run creation.

    The panorama depends only on the snapshot tables (their hashes are rechecked at
    creation). The brief reads profile, data model and memory inside create_run, under
    the same memory lock that captures the report's dependency baseline. A resumed
    run reads its stored prompt and context; this is never called again for it.
    """
    from ..engine import brief, panorama_v1
    business, analysis = job['business_id'], job['analysis_id']
    with connect(config) as db:
        tables = db.execute('''SELECT id,parquet_key,parquet_sha256,columns FROM prepared_tables
            WHERE business_id=%s AND analysis_id=%s ORDER BY id''', (business, analysis)).fetchall()
    panorama = panorama_v1.build(config, business, tables)
    available = panorama['status'] == 'available'
    # Upload and dataset jobs froze the profile description in web_jobs.context; chat
    # jobs store the legacy continuation there, which is not owner text for the brief.
    owner = {} if job.get('origin') == 'chat' else dict(name=job['business_name'], description=job['context'],
                                                         profile_revision=job.get('business_revision'))

    def builder(db):
        text, provenance = brief.build(db, business, analysis, goal=job['engine_config']['goal'],
                                       panorama=available, questions=job['engine_config'].get('profile', {}).get('questions', False),
                                       format=job['engine_config'].get('profile', {}).get('format', 'html'), **owner)
        provenance['panorama'] = {k: v for k, v in panorama.items() if k != 'markdown'}
        return text, provenance
    return builder, ({'panorama.md': panorama['markdown']} if available else None)


def creation(config, job):
    """Run-creation arguments; F0/F1 jobs keep the provisional prompt they captured."""
    settings = job['engine_config']
    if settings['input_request_sha256'] != job['request_sha256']:
        raise ValueError('Captured job configuration failed its integrity check.')
    if 'prompt' in settings:
        if admission.sha(settings['prompt'].encode()) != settings['prompt_sha256']:
            raise ValueError('Captured job configuration failed its integrity check.')
        return dict(frozen_prompt=settings['prompt'])
    if admission.sha(admission.canonical([settings['owner_context'], settings['goal']])) != settings['owner_sha256']:
        raise ValueError('Captured job configuration failed its integrity check.')
    builder, context = inputs(config, job)
    return dict(builder=builder, context=context)


def apply_state(workspace, job, state):
    from .engine_wait import acknowledge
    with connect(workspace.config) as db, db.transaction():
        acknowledge(db, job['business_id'], job['engine_run_id'])
    from ..reports.store import adopt
    adopt(workspace.config, job['business_id'], job['engine_run_id'])
    status = state['status']
    mapped = {'running': 'running', 'pausing': 'running', 'waiting': 'waiting',
              'delivered': 'completed', 'failed': 'failed', 'aborted': 'blocked'}[status]
    issue = None
    if status in ('failed', 'aborted'):
        issue = 'El motor se ha detenido. Conservamos los datos y las entregas recibidas; no repetimos llamadas de uso incierto.'
    workspace.update(job['id'], status=mapped, phase='engine', issue=issue, retry_uncertain=False)


def run(workspace, job_id):
    config = workspace.config
    # Covers ingestion, run creation and the link. A second worker leaves the
    # existing job alone; lock release on process death enables reconciliation.
    with connect(config) as db:
        key = 'engine-web-job:' + str(job_id)
        if not db.execute('SELECT pg_try_advisory_lock(hashtextextended(%s,32)) AS locked', (key,)).fetchone()['locked']:
            return
        try:
            job = reconcile(workspace, workspace.row(job_id))
            if job['engine_run_id']:
                state = snapshot(config, job['business_id'], job['engine_run_id'])
                if state['status'] in ('delivered', 'failed', 'aborted') or (state['status']=='waiting' and not job['pending_answer']):
                    # resume_report may clean up a crashed terminal runtime but
                    # never calls a provider for a terminal job.
                    api.resume_report(config, job['business_id'], job['engine_run_id'])
                    apply_state(workspace, job, snapshot(config, job['business_id'], job['engine_run_id']))
                    return
            workspace.update(job_id, status='running', issue=None)
            data = workspace.ingest_job(job)
            if data is None:
                return
            job = workspace.row(job_id)
            settings = job['engine_config']
            if not job['engine_run_id']:
                run_id, _ = api.prepare_report(config, job['business_id'], job['analysis_id'],
                                               owner_context=settings['owner_context'], request_key='web:' + str(job_id),
                                               limits=settings['limits'], engine_config=settings['profile'],
                                               **creation(config, job))
                # Publish identity before driving. A crash before this update
                # is recovered by reconcile's business + web-job key.
                workspace.update(job_id, engine_run_id=run_id, phase='engine')
                job = workspace.row(job_id)
            pending = job['pending_answer']
            answer = None
            if pending:
                if pending.get('phase') != 'engine' or pending.get('run_id') != str(job['engine_run_id']):
                    raise ValueError('Pending answer belongs to another run.')
                answer = dict(question_id=pending['id'], disposition=pending['disposition'], text=pending['text'], request_key=pending['request_key'])
            api.resume_report(config, job['business_id'], job['engine_run_id'], answer=answer)
            apply_state(workspace, job, snapshot(config, job['business_id'], job['engine_run_id']))
        except admission.Denied:
            # A concurrent direct controller owns the run. This is not a failed
            # job, and no uncertainty override or provider replay is introduced.
            job = reconcile(workspace, workspace.row(job_id))
            if job['engine_run_id']:
                apply_state(workspace, job, snapshot(config, job['business_id'], job['engine_run_id']))
            else:
                workspace.update(job_id, status='blocked', phase='engine', retry_uncertain=False,
                                 issue='No se pudo autorizar el motor con esta copia de los datos.')
        except Exception:
            job = reconcile(workspace, workspace.row(job_id))
            if job['engine_run_id']:
                # Abort once: never retry a partially submitted request under a
                # new identity after an unexpected controller failure.
                api._finish(config, job['business_id'], job['engine_run_id'], 'failed', 'web_controller_failure')
            workspace.update(job_id, status='failed', phase='engine', retry_uncertain=False,
                             issue='La ejecución del motor se ha interrumpido. Conservamos sus datos y entregas.')
        finally:
            db.execute('SELECT pg_advisory_unlock(hashtextextended(%s,32))', (key,))
