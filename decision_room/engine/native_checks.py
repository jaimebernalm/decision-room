"""Preterminal native check/correction cycle, sharing the writer's provider envelope.

New volumes for each checker; only frozen CSV, priorities and declared semantics
enter them. A delegated token reaches only the parent's model proxy. Uncertain
checker/controller delivery never creates another session, allowance or send.
"""
import json
import secrets
import time
from uuid import UUID, uuid4
from psycopg.types.json import Jsonb
from ..database import connect
from ..memory import service as memory
from ..reports import store as registry
from . import admission, blocks, check_contract as contract, control, store
from .export import folder


def _context(db, config, run, *, deep=True):
    memory.lock(db, run['business_id'])
    locked=control._run(db, run['business_id'],run['id'])
    if locked['status']!='running' or locked['credential_revoked'] or locked['credential_expires_at']<=locked['checked_at']:
        raise admission.Denied('Native cycle is not active.')
    if admission._active(db,locked): raise admission.Aborted('Native cycle time exhausted.')
    problem=registry.reason(db,dict(source_run_id=run['id'],business_id=run['business_id'],analysis_id=run['analysis_id'],stale_reason=None),config=config,deep=deep)
    if problem: raise admission.Denied('Native cycle context revoked.')
    return locked


def _result(row):
    if not row or row['status']!='complete': return None
    if admission.sha(admission.canonical(row['result']))!=row['result_sha256']:
        raise ValueError('Check result integrity failed.')
    return row['result']


def _resolved_usage(db, config, run):
    if db.execute("SELECT 1 FROM engine_model_calls WHERE run_id=%s AND state<>'settled' LIMIT 1", (run['id'],)).fetchone():
        raise admission.Denied('Provider usage is unresolved.')
    from . import provider_budget
    ledger=provider_budget.ledger(config,run)
    if ledger:
        state=ledger.snapshot()
        if state['policy']['stopped'] or state['uncertain']:
            raise admission.Denied('Provider budget stopped or unresolved.')


def read(db,business,run,revision):
    row=db.execute('SELECT * FROM engine_native_checks WHERE business_id=%s AND run_id=%s AND revision_id=%s AND version IN (%s,%s) ORDER BY started_at DESC LIMIT 1',
                   (business,run,revision,contract.VERSION+'-initial',contract.VERSION+'-final')).fetchone()
    result=_result(row)
    if result: return result
    return dict(state='pending' if row and row['status']=='running' else 'incomplete' if row else 'unknown',items=[])


def inputs(config,run,receipt,projection):
    from . import api, brief
    files={k:v for k,v in api._inputs(config,run).items() if k.startswith('datos/') or k=='manifest.json'}
    # Explicit F2 declaration-only projection, frozen at run creation. Direct API
    # calls have only their owner_context, never a split of delivery instructions.
    owner=run['brief'].get('checker_context') or (run['owner_context']+'\n'+brief.DATA+'\n'+brief.UNKNOWN+'\n'+brief.LIMITS)
    files['contexto/definiciones.txt']=owner.encode()
    files['prioridades.json']=admission.canonical(dict(revision_sha256=receipt['raw_sha256'],priorities=blocks.priorities(projection)))
    return files


def _finish_check(config,run,check,*,raw=None,result=None,issue=None,observations=None):
    with connect(config) as db,db.transaction():
        if result is not None:
            _context(db,config,run)
        else:
            control._run(db,run['business_id'],run['id'])
        row=db.execute('SELECT * FROM engine_native_checks WHERE id=%s AND run_id=%s FOR UPDATE',(check,run['id'])).fetchone()
        if row['status']!='running':
            if result is not None and _result(row)!=result: raise ValueError('Check completion differs.')
            return _result(row)
        db.execute('''UPDATE engine_native_checks SET status=%s,raw_result=%s,result=%s,result_sha256=%s,
            issue=%s,observations=%s,finished_at=clock_timestamp() WHERE id=%s''',
            ('complete' if result is not None else 'incomplete',raw,Jsonb(result) if result is not None else None,
             admission.sha(admission.canonical(result)) if result is not None else None,issue,Jsonb(observations) if observations is not None else None,check))
    return result


def run_check(config,run,receipt,projection, *, final=False):
    from . import api
    expected=dict(version=contract.VERSION,prompt_sha256=admission.sha(contract.PROMPT.encode()),
                  correction_sha256=admission.sha(contract.CORRECTION.encode()),calls=20,seconds=300)
    if run['profile'].get('checks')!=expected:
        raise ValueError('Frozen checker policy is unavailable.')
    files=inputs(config,run,receipt,projection)
    fingerprint=admission.sha(admission.canonical({k:admission.sha(v) for k,v in files.items()}))
    version=contract.VERSION+('-final' if final else '-initial')
    ident,instance,token,password=uuid4(),uuid4(),secrets.token_urlsafe(32),secrets.token_urlsafe(32)
    message='msg_'+uuid4().hex
    with connect(config) as db,db.transaction():
        _context(db,config,run)
        prior=db.execute('SELECT * FROM engine_native_checks WHERE run_id=%s AND revision_id=%s AND version=%s FOR UPDATE',
                         (run['id'],receipt['revision_id'],version)).fetchone()
        if prior:
            if prior['input_sha256']!=fingerprint or prior['raw_sha256']!=receipt['raw_sha256']:
                raise ValueError('Check input identity changed.')
            result=_result(prior)
            if result: return result
            # Driver death is not proof a prompt was not accepted. Fail closed;
            # preserve its exact runtime identity for an explicit investigation.
            if prior['status']=='running':
                db.execute("UPDATE engine_native_checks SET status='incomplete',issue='checker_recovery_uncertain',finished_at=clock_timestamp() WHERE id=%s",(prior['id'],))
            return None
        db.execute('''INSERT INTO engine_native_checks(id,run_id,business_id,revision_id,raw_sha256,version,
            credential_sha256,instance_id,message_id,input_sha256) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
            (ident,run['id'],run['business_id'],receipt['revision_id'],receipt['raw_sha256'],version,
             admission.sha(token.encode()),instance,message,fingerprint))
    runtime=client=tunnel=None;raw=None;messages=[]
    try:
        backend=api.DockerBackend()
        runtime=api.Runtime(backend,run_id=str(run['id']),instance_id=str(instance),image=run['profile']['image_id'],
                            password=password,token=token,model=run['model'],checker=True)
        # Store private identity before Docker/network mutation. This is runtime
        # state, outside public exports; no writer files/checkpoint are mounted.
        api._save(folder(config,run['business_id'],run['id'])/('check-'+str(ident)+'.json'),
                  dict(run_id=str(run['id']),instance_id=str(instance),image=run['profile']['image_id'],
                       password=password,token=token,model=run['model'],checker=True))
        runtime.create();runtime.install_files('inputs',files);client=runtime.start()
        tunnel=api.JobTunnel(backend,runtime.container_id,run['id'],api._service(config,backend).origin).start()
        session=client.create_session(title='Comprobación independiente',model=run['model'])['id']
        with connect(config) as db,db.transaction():
            _context(db,config,run)
            db.execute('UPDATE engine_native_checks SET session_id=%s,dispatched=true WHERE id=%s AND NOT dispatched',(session,ident))
        client.submit(session,message_id=message,text=contract.PROMPT,model=run['model'])
        deadline=time.monotonic()+300
        while time.monotonic()<deadline:
            tunnel.check()
            with connect(config) as db,db.transaction():_context(db,config,run,deep=False)
            seen=client.message(session,message)
            if seen:
                control._validate_message(seen,session)
                parts=[p.get('text') for p in seen['parts'] if p.get('type')=='text' and not p.get('synthetic')]
                if seen['info']['id']!=message or seen['info']['role']!='user' or parts!=[contract.PROMPT]:
                    raise ValueError('Checker prompt acknowledgement differs.')
                messages=client.messages(session,limit=100)
                if not isinstance(messages,list) or len(admission.canonical(messages))>control.MAX_PAGE_BYTES:
                    raise ValueError('Checker observations exceed limits.')
                if api._completed_turn(messages,message) and client.statuses().get(session,{}).get('type','idle')=='idle':
                    collected=runtime.collect_report(filename='comprobacion.json')
                    if collected['status']!='received':raise ValueError('No bounded checker result.')
                    raw=collected['raw']
                    # Retain exact received bytes before interpreting them, even
                    # if parsing or controller recovery subsequently fails.
                    with connect(config) as db,db.transaction():
                        _context(db,config,run)
                        db.execute("UPDATE engine_native_checks SET raw_result=%s,observations=%s WHERE id=%s AND status='running'",
                                   (raw,Jsonb(messages),ident))
                    result=contract.parse(raw,projection,receipt['raw_sha256'])
                    return _finish_check(config,run,ident,raw=raw,result=result,observations=messages)
            time.sleep(.1)
        raise ValueError('Checker time limit.')
    except Exception:
        # Parent provider handling retains uncertain usage/global budget stops;
        # check errors never silently become an empty successful verification.
        try:_finish_check(config,run,ident,raw=raw,issue='checker_incomplete',observations=messages)
        except (admission.Denied,admission.Aborted):pass
        return None
    finally:
        for resource,method in ((tunnel,'close'),(client,'close'),(runtime,'stop')):
            if resource is not None:getattr(resource,method)()


def incomplete(config,run,issue):
    with connect(config) as db,db.transaction():
        control._run(db,run['business_id'],run['id'])
        db.execute("UPDATE engine_native_cycles SET stage='incomplete',issue=%s WHERE run_id=%s AND stage NOT IN ('complete','incomplete')",(issue,run['id']))


def draft(config,run,receipt):
    """Return correct/delivered/failed; never reopen a terminal engine run."""
    try:
        projection=blocks.parse(receipt['raw'])
    except blocks.BlocksError:
        return 'failed'
    with connect(config) as db,db.transaction():
        _context(db,config,run)
        cycle=db.execute('SELECT * FROM engine_native_cycles WHERE run_id=%s FOR UPDATE',(run['id'],)).fetchone()
        if not cycle:
            db.execute("INSERT INTO engine_native_cycles(run_id,business_id,stage,draft_revision_id) VALUES (%s,%s,'checking',%s)",
                       (run['id'],run['business_id'],receipt['revision_id']))
        elif cycle['stage']=='complete':
            return 'delivered' if str(cycle['selected_revision_id'])==receipt['revision_id'] else 'failed'
        elif cycle['stage']=='incomplete':return 'failed'
        elif cycle['stage']=='correcting':
            db.execute("UPDATE engine_native_cycles SET stage='final_checking',draft_revision_id=%s WHERE run_id=%s",(receipt['revision_id'],run['id']))
    result=run_check(config,run,receipt,projection,final=bool(cycle and cycle['correction_used']))
    if not result:
        # Only a live, current parent with confirmed usage may publish a valid
        # draft with a visible incomplete check. Abort/global budget stops stand.
        try:
            with connect(config) as db,db.transaction():
                locked=_context(db,config,run)
                _resolved_usage(db,config,locked)
                db.execute("UPDATE engine_native_cycles SET stage='incomplete',selected_revision_id=%s,issue='checker_incomplete' WHERE run_id=%s",(receipt['revision_id'],run['id']))
            return 'delivered'
        except (admission.Denied,admission.Aborted):
            incomplete(config,run,'checker_incomplete');return 'failed'
    with connect(config) as db,db.transaction():
        locked=_context(db,config,run)
        _resolved_usage(db,config,locked)
        cycle=db.execute('SELECT * FROM engine_native_cycles WHERE run_id=%s FOR UPDATE',(run['id'],)).fetchone()
        if any(i['status']=='discrepancy' for i in result['items']) and not cycle['correction_used']:
            text=contract.correction(result)
            control._enqueue_prompt(db,locked,request_key='native-correction',text=text,fingerprint=admission.sha(admission.canonical(text)))
            db.execute("UPDATE engine_native_cycles SET stage='correcting',correction_used=true WHERE run_id=%s",(run['id'],))
            return 'correct'
        db.execute("UPDATE engine_native_cycles SET stage='complete',selected_revision_id=%s WHERE run_id=%s",(receipt['revision_id'],run['id']))
    return 'delivered'


def recover(config,run):
    """After a dead controller, stop every retained checker identity before reuse."""
    from . import api
    with connect(config) as db:
        rows=db.execute('SELECT * FROM engine_native_checks WHERE run_id=%s AND business_id=%s',
                        (run['id'],run['business_id'])).fetchall()
    interrupted=False
    for check in rows:
        path=folder(config,run['business_id'],run['id'])/('check-'+str(check['id'])+'.json')
        if path.exists():
            meta=json.loads(path.read_text())
            if (meta['run_id']!=str(run['id']) or meta['instance_id']!=str(check['instance_id'])
                or admission.sha(meta['token'].encode())!=check['credential_sha256']):
                raise ValueError('Checker runtime identity changed.')
            api.Runtime(api.DockerBackend(),**meta).stop()
        if check['status']=='running':
            _finish_check(config,run,check['id'],issue='checker_recovery_uncertain')
            interrupted=True
    if interrupted:
        # A controller death can leave the delegated proxy in flight. Retain
        # its reservations and stop the existing dollar ledger before cleanup;
        # no fresh allowance or automatic send is created.
        pending=[c for c in admission.inspect_run(config,run['business_id'],run['id'])['model_calls']
                 if c['state'] in ('counting','admitted')]
        for call in pending:
            admission.settle(config,run['id'],call['id'],reason='checker_recovery_usage_unknown')
        from . import provider_budget
        ledger=provider_budget.ledger(config,run)
        if ledger and ledger.snapshot()['uncertain']:ledger.stop()
        incomplete(config,run,'checker_recovery_uncertain')
    return interrupted


def run_standalone(config,business,run_id,token,raw):
    """Retained checker trial on a dedicated, already budgeted run.

    The trial runner prepares this separate run and routes its proxy through
    the batch ledger. This entry creates no allowance, writer, correction,
    cycle or owner-facing publication. Never pass a product job's run here.
    """
    from . import api
    projection=blocks.parse(raw)
    with control.controller_lock(config,business,run_id):
        run=api._row(config,business,run_id)
        if run['profile'].get('format')!='blocks' or not run['profile'].get('usd_ceiling'):
            raise admission.Denied('A budgeted native trial run is required.')
        with connect(config) as db,db.transaction():
            if (db.execute('SELECT 1 FROM web_jobs WHERE engine_run_id=%s',(run_id,)).fetchone() or
                db.execute('SELECT 1 FROM engine_sessions WHERE run_id=%s',(run_id,)).fetchone() or
                db.execute('SELECT 1 FROM engine_native_cycles WHERE run_id=%s',(run_id,)).fetchone()):
                raise admission.Denied('Standalone checks require a separate run.')
            previous=db.execute('SELECT * FROM engine_native_checks WHERE business_id=%s AND run_id=%s',(business,run_id)).fetchall()
        if previous:
            if len(previous)!=1 or previous[0]['raw_sha256']!=admission.sha(raw):
                raise ValueError('Standalone check input changed.')
            if previous[0]['status']=='running':
                recover(config,run)
                api._finish(config,business,run_id,'failed','standalone_check_interrupted')
                return dict(state='incomplete',items=[])
            return _result(previous[0]) or dict(state='incomplete',items=[])
        admission.authenticate(config,run_id,token)
        store.receive_document(config,run_id,token,request_key='standalone-check-input',html=raw,via='file')
        receipt=store.read_document(config,business,run_id)
        try:
            return run_check(config,run,receipt,projection) or dict(state='incomplete',items=[])
        finally:
            # A check-only trial must never become an owner report, even if its
            # checker completed. Audit status lives in engine_native_checks.
            api._finish(config,business,run_id,'failed','standalone_check_only')
