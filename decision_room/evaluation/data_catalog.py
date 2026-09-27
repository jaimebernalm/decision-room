"""Repeatable 3.2 full-database ER validation; generated data and DB stay local.

python -m decision_room.evaluation.data_catalog --output .local/evaluation/catalog-32
Uses the public WWI CSV exports and source foreign keys only as independent checks.
"""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import time
from uuid import uuid4
import xml.etree.ElementTree as ET
import zipfile

from psycopg import sql
from psycopg.conninfo import make_conninfo

from ..config import Config, ROOT
from ..database import connect, migrate
from ..service import create_business, import_batch
from ..data_knowledge import service, profiling
from ..memory import retrieval
from ..conversations import snapshot


def write(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str)+'\n')


def run(output):
    output.mkdir(parents=True,exist_ok=False)
    base=Config.load()
    name='dr_catalog_eval_'+uuid4().hex
    with connect(base) as db:
        db.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
    config=replace(base,dsn=make_conninfo(base.dsn,dbname=name),storage=(output/'storage').resolve())
    migrate(config)
    business=create_business(config,'WWI · pruebas de relaciones')['id']
    # Also expose this isolated business in the optional local QA server.
    with connect(config) as db:
        db.execute('INSERT INTO web_businesses(business_id,creation_key,creation_sha256) VALUES (%s,%s,%s)',(business,uuid4(),'evaluation'))
        db.execute("UPDATE web_businesses SET onboarding_status='analysis_started' WHERE business_id=%s",(business,))
        db.execute('UPDATE web_workspace SET active_business_id=%s WHERE singleton',(business,))
    csv=ROOT/'data/wide-world-importers/exports/csv'
    started=time.monotonic()
    result=import_batch(config,business,sorted(csv.glob('*.csv')),title='Wide World Importers · 48 tablas')
    analysis=result['analysis']['id']
    write(output/'manifest.json',dict(database=name,business_id=business,analysis_id=analysis,storage=config.storage))
    with connect(config) as db:
        model=service.latest(db,business,analysis)
        if not model:
            raise ValueError('Full catalog build failed: '+str(result.get('data_model_issue')))
        rows=service.records(db,business,analysis)
    elapsed=time.monotonic()-started
    write(output/'model.json',model)
    tables={t['name'].removesuffix('.csv'):t for t in model['body']['tables']}
    bacpac=next((ROOT/'data/wide-world-importers').glob('*.bacpac'))
    with zipfile.ZipFile(bacpac) as archive:
        root=ET.fromstring(archive.read('model.xml'))
    ns={'m':root.tag.split('}')[0][1:]}
    def refs(element,name):
        return [r.get('Name').replace('[','').replace(']','') for r in element.findall(f"m:Relationship[@Name='{name}']/m:Entry/m:References",ns)]
    checks=[]
    with profiling.engine(config,business,rows) as (engine,views):
        for element in root.findall(".//m:Element[@Type='SqlForeignKeyConstraint']",ns):
            source=refs(element,'DefiningTable')[0];target=refs(element,'ForeignTable')[0]
            sc=[v.rsplit('.',1)[1] for v in refs(element,'Columns')]
            tc=[v.rsplit('.',1)[1] for v in refs(element,'ForeignColumns')]
            r=profiling.validate_relation(engine,views,model['body']['tables'],tables[source]['id'],tables[target]['id'],sc,tc)
            assert not r['evidence']['target']['duplicate_keys'], element.get('Name')
            assert not r['evidence']['unmatched_rows'], element.get('Name')
            checks.append(dict(constraint=element.get('Name'),source=source,target=target,evidence=r['evidence']))
    write(output/'source-fk-checks.json',checks)
    # Read from a new connection: no in-process reconstruction or separate graph model.
    with connect(config) as db:
        chat=snapshot(db,business,analysis,'Explain invoice relationships')
        for table in tables.values():
            retrieval.retrieve(config,db,None,dict(tool='inspect_dataset',id=table['id'],query='',limit=1),manifest=chat)
        inspected,deps=retrieval.retrieve(config,db,None,dict(tool='inspect_dataset',id=tables['Sales.InvoiceLines']['id'],query='',limit=1),manifest=chat)
        assert inspected['data_model']['revision']==model['revision']
        assert inspected['data_model']['relations']==[r for r in model['body']['relations'] if tables['Sales.InvoiceLines']['id'] in (r['source'],r['target'])]
    write(output/'chat-retrieval.json',inspected)
    allnames={t['id']:t['name'] for t in model['body']['tables']}
    summary=dict(tables=len(tables),rows=sum(t['row_count'] for t in tables.values()),
        import_and_profile_seconds=round(elapsed,3),source_foreign_keys_checked=len(checks),
        inferred_relations=len(model['body']['relations']),checked=sum(r['verification']=='checked' for r in model['body']['relations']),
        unconfirmed=sum(r['semantic_status']=='proposed' for r in model['body']['relations']),
        invoice_line_links=[dict(source=allnames[r['source']],target=allnames[r['target']],columns=r['source_columns'],cardinality=r['cardinality'],evidence=r['evidence']) for r in inspected['data_model']['relations']],
        shared_revision=model['revision'])
    write(output/'summary.json',summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
