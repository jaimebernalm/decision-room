"""Immutable, business-scoped catalog revisions and explicit owner corrections."""
from copy import deepcopy

from psycopg.types.json import Jsonb

from ..database import connect
from ..memory import context
from ..memory.service import digest, lock
from . import profiling


def records(db, business, analysis):
    rows = db.execute('''SELECT p.*,s.original_names FROM prepared_tables p
        JOIN sources s ON s.id=p.source_id JOIN analyses a ON a.id=p.analysis_id
        LEFT JOIN dataset_versions v ON v.analysis_id=a.id
        WHERE p.business_id=%s AND p.analysis_id=%s AND s.status='ready'
        AND a.status IN ('ready','partial') AND NOT coalesce(v.corrected,false)
        ORDER BY s.original_names->>0,p.id''', (business,analysis)).fetchall()
    if not rows:
        raise ValueError('No hay tablas vigentes disponibles para este negocio y versión.')
    return rows


def fingerprint(rows):
    return digest([[str(r['id']),r['parquet_sha256'],r['columns'],r['original_names']] for r in rows])


def latest(db, business, analysis, revision=None):
    return db.execute('''SELECT * FROM data_model_revisions WHERE business_id=%s AND analysis_id=%s
        AND (%s::int IS NULL OR revision=%s) ORDER BY revision DESC LIMIT 1''',
        (business,analysis,revision,revision)).fetchone()


def heads(db, business, analysis=None):
    return [dict(analysis_id=str(r['analysis_id']), revision=r['revision']) for r in db.execute('''
        SELECT DISTINCT ON (m.analysis_id) m.analysis_id,m.revision FROM data_model_revisions m
        LEFT JOIN dataset_versions v ON v.analysis_id=m.analysis_id
        WHERE m.business_id=%s AND (%s::uuid IS NULL OR m.analysis_id=%s)
        AND NOT coalesce(v.corrected,false)
        AND (v.superseded_by IS NULL OR m.analysis_id=%s)
        ORDER BY m.analysis_id,m.revision DESC''', (business,analysis,analysis,analysis)).fetchall()]


def current(db, business, reference):
    row = latest(db,business,reference['analysis_id'])
    valid = db.execute('SELECT 1 FROM dataset_versions WHERE business_id=%s AND analysis_id=%s AND corrected',
                       (business,reference['analysis_id'])).fetchone()
    if not row or valid or row['revision'] != reference['revision']:
        return False
    try:
        return row['fingerprint'] == fingerprint(records(db,business,reference['analysis_id']))
    except ValueError:
        return False


def summary(db, business, analysis):
    row = latest(db,business,analysis)
    if not row or not current(db,business,{'analysis_id':str(analysis),'revision':row['revision']}):
        return None
    body = row['body']
    return dict(analysis_id=str(analysis),revision=row['revision'],
        tables=len(body['tables']),relations=len(body['relations']),
        confirmed_relations=sum(r['semantic_status']=='confirmed' for r in body['relations']),
        relationships=[{k:r[k] for k in ('id','source','target','source_columns','target_columns','description','semantic_status','verification','cardinality','evidence')} for r in body['relations']],
        discovery_limits=body.get('discovery',{}).get('limitations',[]),
        definitions=[{k:m[k] for k in ('key','name','unit','table_ids','period')} for m in body['metrics']],
        instruction='Use inspect_dataset(table id) for full column knowledge and adjacent ER edges. Technical checks are not confirmed business meaning. No automatic joins or implicit numeric conversions.')


def inspect(db, business, table_id):
    table = db.execute('SELECT analysis_id FROM prepared_tables WHERE business_id=%s AND id=%s',
                       (business,table_id)).fetchone()
    row = latest(db,business,table['analysis_id']) if table else None
    if not row or not current(db,business,{'analysis_id':str(row['analysis_id']),'revision':row['revision']}):
        return None
    return dict(analysis_id=str(row['analysis_id']),revision=row['revision'],
        table=next(t for t in row['body']['tables'] if t['id']==str(table_id)),
        relations=[r for r in row['body']['relations'] if str(table_id) in (r['source'],r['target'])],
        related_tables=[dict(id=t['id'],name=t['name']) for t in row['body']['tables']
            if t['id'] in {x for r in row['body']['relations'] if str(table_id) in (r['source'],r['target']) for x in (r['source'],r['target'])}],
        metrics=[m for m in row['body']['metrics'] if str(table_id) in m['table_ids']],
        references=references(row, str(table_id)))


def references(row, table_id):
    """Explicit citation handles; only delivered, owner-declared meanings can confirm a plan."""
    result=[]
    def add(kind, key, value, table_ids, confirmed, period=None):
        result.append(dict(reference=f"dm:{row['analysis_id']}@{row['revision']}:{digest([kind,key])[:20]}",
            analysis_id=str(row['analysis_id']), revision=row['revision'], kind=kind,
            content=value, table_ids=table_ids, confirmed=confirmed,
            period=period or {'from':None,'until':None}))
    table=next(t for t in row['body']['tables'] if t['id']==table_id)
    add('table',table_id,dict(description=table['description'],grain=table['grain']),[table_id],table['semantic_status']=='owner_declared')
    for c in table['columns']:
        if any(c[k] for k in ('meaning','unit','conversion')):
            add('column',[table_id,c['name']],{k:c[k] for k in ('name','meaning','unit','conversion')},[table_id],c['semantic_status']=='owner_declared')
    for rel in row['body']['relations']:
        if table_id in (rel['source'],rel['target']):
            add('relationship',rel['id'],{k:rel[k] for k in ('source','target','source_columns','target_columns','description','semantic_status')},[rel['source'],rel['target']],rel['semantic_status']=='confirmed')
    for metric in row['body']['metrics']:
        if table_id in metric['table_ids']:
            add('metric',metric['key'],metric,metric['table_ids'],True,metric['period'])
    return result


def persist(db,business,analysis,previous,source_hash,body,reason):
    lock(db,business)
    now = latest(db,business,analysis)
    if (now['revision'] if now else 0) != previous:
        raise ValueError('El modelo de datos ha cambiado. Recarga antes de guardar.')
    if now and now['body'] == body and now['fingerprint'] == source_hash:
        return now
    result = db.execute('''INSERT INTO data_model_revisions(business_id,analysis_id,revision,fingerprint,body,reason)
        VALUES (%s,%s,%s,%s,%s,%s) RETURNING *''',
        (business,analysis,previous+1,source_hash,Jsonb(body),reason)).fetchone()
    context.invalidate(db,business)
    return result


def ensure(config,business,analysis):
    with connect(config) as db:
        db.execute('SELECT pg_advisory_lock(hashtextextended(%s,32))',(str(analysis),))
        rows=records(db,business,analysis)
        source_hash=fingerprint(rows)
        old=latest(db,business,analysis)
        if old and old['fingerprint']==source_hash and old['body']['version']==profiling.VERSION:
            return old
        with profiling.engine(config,business,rows) as (engine,views):
            tables=[profiling.profile(engine,views[str(r['id'])],r) for r in rows]
            relations=[]
            if old and old['fingerprint']==source_hash:
                for previous in old['body']['relations']:
                    checked=profiling.validate_relation(engine,views,tables,previous['source'],previous['target'],
                        previous['source_columns'],previous['target_columns'])
                    checked.update({k:v for k,v in previous.items() if k in ('origin','semantic_status','description','provenance')})
                    relations.append(checked)
        body=dict(version=profiling.VERSION,tables=tables,relations=relations,metrics=[],
                  scope='This dataset version only. New files are profiled afresh; definitions and semantic confirmations are never copied by matching names.',
                  inference='Relationships are proposed by the analyst and checked on full files. No proposal is proof of business meaning; absence of an edge does not establish absence of a relationship.')
        if old and old['fingerprint']==source_hash:
            # A profiler upgrade must preserve owner meanings and prior discoveries.
            body.update({k:v for k,v in old['body'].items() if k not in ('version','tables','relations','inference')})
            previous={t['id']:t for t in old['body']['tables']}
            for table in tables:
                before=previous[table['id']]
                for key in ('description','grain','semantic_status','declared_keys'):
                    table[key]=before[key]
                columns={c['name']:c for c in before['columns']}
                for column in table['columns']:
                    for key in ('meaning','unit','conversion','semantic_status'):
                        column[key]=columns[column['name']][key]
        with db.transaction():
            if fingerprint(records(db,business,analysis))!=source_hash:
                raise ValueError('Los archivos han cambiado durante la comprobación. Reintenta.')
            return persist(db,business,analysis,old['revision'] if old else 0,source_hash,body,'Full-file profiling and relationship checks')


def text(value,limit=2000):
    if not isinstance(value,str) or len(value)>limit:
        raise ValueError('El texto supera el límite permitido.')
    return value.strip()


def change(config,business,analysis,expected,action,payload):
    if not isinstance(payload,dict) or type(expected) is not int:
        raise ValueError('Revisión o contenido no válido.')
    with connect(config) as db:
        rows=records(db,business,analysis)
        row=latest(db,business,analysis)
        if not row or row['revision']!=expected or row['fingerprint']!=fingerprint(rows):
            raise ValueError('El modelo de datos ha cambiado. Recarga antes de guardar.')
        body=deepcopy(row['body'])
        tables={t['id']:t for t in body['tables']}
        if action=='table':
            if set(payload)-{'id','description','grain','columns','declared_keys'} or payload.get('id') not in tables:
                raise ValueError('Tabla no disponible.')
            table=tables[payload['id']]
            for key in ('description','grain'):
                if key in payload:
                    table[key]=text(payload[key])
            for definition in payload.get('columns',[]):
                if set(definition)-{'name','meaning','unit','conversion'}:
                    raise ValueError('Definición de columna no válida.')
                column=next((c for c in table['columns'] if c['name']==definition.get('name')),None)
                if not column:
                    raise ValueError('Columna no disponible.')
                for key in ('meaning','unit','conversion'):
                    if key in definition:
                        column[key]=text(definition[key])
                column['semantic_status']='owner_declared' if any(column[k] for k in ('meaning','unit','conversion')) else 'unknown'
            if 'declared_keys' in payload:
                keys=payload['declared_keys']
                if not isinstance(keys,list) or len(keys)>10:
                    raise ValueError('Indica hasta diez claves.')
                with profiling.engine(config,business,rows) as (engine,views):
                    checked=[]
                    for names in keys:
                        relation=profiling.validate_relation(engine,views,body['tables'],table['id'],table['id'],names,names)
                        checked.append(dict(columns=names,evidence=relation['evidence']['source'],
                            valid=not relation['evidence']['source']['missing_rows'] and not relation['evidence']['source']['duplicate_keys']))
                table['declared_keys']=checked
            table['semantic_status']='owner_declared' if table['description'] or table['grain'] else 'unknown'
        elif action=='relation':
            if set(payload)-{'source','target','source_columns','target_columns','description','semantic_status'}:
                raise ValueError('Relación no válida.')
            with profiling.engine(config,business,rows) as (engine,views):
                rel=profiling.validate_relation(engine,views,body['tables'],payload.get('source'),payload.get('target'),
                                               payload.get('source_columns',[]),payload.get('target_columns',[]))
            status=payload.get('semantic_status','proposed')
            if status not in ('proposed','confirmed','rejected'):
                raise ValueError('Estado de relación no válido.')
            rel.update(origin='owner',semantic_status=status,description=text(payload.get('description','')))
            body['relations']=[r for r in body['relations'] if r['id']!=rel['id']]+[rel]
        elif action=='metric':
            if set(payload)-{'key','name','definition','unit','table_ids','period_from','period_until'}:
                raise ValueError('Definición de métrica no válida.')
            key=text(payload.get('key',''),80)
            if not key or not payload.get('table_ids') or not set(payload['table_ids'])<=set(tables):
                raise ValueError('Indica una clave y tablas de esta versión.')
            span=context.period({'from':payload.get('period_from'),'until':payload.get('period_until')})
            metric=dict(key=key,name=text(payload.get('name',''),180),definition=text(payload.get('definition',''),4000),
                        unit=text(payload.get('unit',''),180),table_ids=payload['table_ids'],period=span,status='owner_declared')
            if not metric['definition']:
                raise ValueError('Describe cómo se interpreta la métrica.')
            body['metrics']=[m for m in body['metrics'] if m['key']!=key]+[metric]
            if len(body['metrics'])>40:
                raise ValueError('Límite de cuarenta definiciones por conjunto.')
        else:
            raise ValueError('Operación no válida.')
        with db.transaction():
            lock(db,business)
            if fingerprint(records(db,business,analysis))!=row['fingerprint']:
                raise ValueError('Los archivos han cambiado. Recarga antes de guardar.')
            return persist(db,business,analysis,expected,row['fingerprint'],body,'Owner correction: '+action)
