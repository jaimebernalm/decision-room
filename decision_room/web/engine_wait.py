"""Owner-facing run-scoped questions. Receipt, wake-up and model delivery are separate."""
from psycopg.types.json import Jsonb

from ..database import connect
from ..engine import admission, control, questions
from ..memory import service as memory
from .dossier import guard
from .errors import WebError, identifier


def reply(workspace, job_id, data, answer):
    business = guard(workspace, data)
    run_id = identifier(data.get('run_id'))
    question_id = identifier(answer['id'])
    answer = {**answer, 'run_id': str(run_id), 'id': str(question_id)}
    if answer['phase'] != 'engine':
        raise WebError('Esta respuesta no corresponde al motor.', 409)
    try:
        with connect(workspace.config) as db, db.transaction():
            selected = db.execute('SELECT active_business_id FROM web_workspace WHERE singleton FOR SHARE').fetchone()
            if selected['active_business_id'] != business:
                raise WebError('El negocio activo ha cambiado.', 409)
            memory.lock(db, business)
            run = control._run(db, business, run_id)
            job = db.execute('SELECT * FROM web_jobs WHERE business_id=%s AND id=%s FOR UPDATE',
                             (business, identifier(job_id))).fetchone()
            if not job or job['deleted_at'] or job['engine_kind'] != 'opencode' or job['engine_run_id'] != run_id:
                raise WebError('La pregunta no pertenece a este análisis.', 404)
            q = questions._question(db, run_id, question_id)
            prior = db.execute('SELECT answer FROM web_replies WHERE job_id=%s AND request_key=%s',
                               (job_id, answer['request_key'])).fetchone()
            if prior:
                if prior['answer'] != answer:
                    raise WebError('Este envío ya contiene otra respuesta.', 409)
                return {'saved': True}
            if job['status'] != 'waiting' or questions.context_reason(db, workspace.config, run, q):
                raise WebError('La espera ha vencido o su contexto ha cambiado. Conservamos el trabajo; inicia otro análisis.', 409)
            questions._answer(db, run, question_id=question_id, disposition=answer['disposition'],
                              text=answer['text'], request_key=answer['request_key'])
            db.execute('INSERT INTO web_replies(job_id,request_key,answer) VALUES (%s,%s,%s)',
                       (job_id, answer['request_key'], Jsonb(answer)))
            db.execute("UPDATE web_jobs SET pending_answer=%s,status='queued',issue=NULL,updated_at=now() WHERE id=%s",
                       (Jsonb(answer), job_id))
    except admission.Denied as error:
        raise WebError('Esta pregunta ya no admite una respuesta para reanudar.', 409) from error
    except ValueError as error:
        raise WebError('La respuesta no coincide con el recibo guardado.', 409) from error
    workspace.wake.set()
    return {'saved': True}


def detail(config, job):
    """Cheap, non-mutating metadata. No deep hashes while loading a page."""
    if not job['engine_run_id']:
        return {}
    with connect(config) as db:
        run = db.execute('SELECT *,clock_timestamp() AS checked_at FROM engine_runs WHERE business_id=%s AND id=%s',
                         (job['business_id'], job['engine_run_id'])).fetchone()
        if not run:
            raise WebError('El run no pertenece a este análisis.', 404)
        rows = db.execute('SELECT * FROM engine_owner_questions WHERE run_id=%s ORDER BY created_at', (run['id'],)).fetchall()
        answers = db.execute('SELECT * FROM engine_owner_answers WHERE run_id=%s ORDER BY created_at', (run['id'],)).fetchall()
        from ..reports.store import reason
        problem = reason(db, dict(source_run_id=run['id'], business_id=run['business_id'],
                                 analysis_id=run['analysis_id'], stale_reason=None), config=config)
    result = dict(engine_run_id=str(run['id']), engine_state=run['status'],
                  answer_pending=bool(job['pending_answer']), answers=[{
                      **r['body'], 'question': next(q['body']['text'] for q in rows if q['id'] == r['question_id'])
                  } for r in answers])
    q = next((r for r in rows if r['state'] != 'resumed'), None)
    expired = bool(q and q['expires_at'] and q['expires_at'] <= run['checked_at'])
    if run['status'] == 'waiting' and (expired or problem or run['credential_revoked']):
        result.update(status='blocked', context_stale=bool(problem), questions=[],
                      issue='La espera ha vencido o su contexto ya no está vigente. Conservamos lo guardado; inicia otro análisis.')
    elif q and run['status'] == 'waiting' and not answers:
        result['questions'] = [dict(id=str(q['id']), run_id=str(run['id']), phase='engine', **q['body'])]
    return result


def acknowledge(db, business, run_id):
    """Only exact persisted prompt acknowledgement clears a web pending answer."""
    db.execute('''UPDATE web_jobs w SET pending_answer=NULL,updated_at=now()
        FROM engine_owner_answers a JOIN engine_prompt_outbox p
        ON p.run_id=a.run_id AND p.message_id=a.message_id
        WHERE w.business_id=%s AND w.engine_run_id=%s AND w.engine_kind='opencode'
        AND a.run_id=w.engine_run_id AND p.state='confirmed'
        AND w.pending_answer->>'phase'='engine'
        AND w.pending_answer->>'run_id'=a.run_id::text
        AND w.pending_answer->>'id'=a.question_id::text
        AND w.pending_answer->>'request_key'=a.request_key
        AND w.pending_answer->>'disposition'=a.body->>'disposition'
        AND w.pending_answer->>'text'=a.body->>'text' ''', (business, run_id))
