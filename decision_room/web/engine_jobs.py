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


def apply_state(workspace, job, state):
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
                if state['status'] in ('delivered', 'failed', 'aborted', 'waiting'):
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
            if admission.sha(settings['prompt'].encode()) != settings['prompt_sha256'] or settings['input_request_sha256'] != job['request_sha256']:
                raise ValueError('Captured job configuration failed its integrity check.')
            if not job['engine_run_id']:
                run_id, _ = api.prepare_report(config, job['business_id'], job['analysis_id'],
                                               owner_context=settings['owner_context'], request_key='web:' + str(job_id),
                                               limits=settings['limits'], engine_config=settings['profile'],
                                               frozen_prompt=settings['prompt'])
                # Publish identity before driving. A crash before this update
                # is recovered by reconcile's business + web-job key.
                workspace.update(job_id, engine_run_id=run_id, phase='engine')
                job = workspace.row(job_id)
            api.resume_report(config, job['business_id'], job['engine_run_id'])
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
