#!/usr/bin/env python3
"""Opt-in integrated daily-workspace evaluation; synthetic data and a private database.

Expected totals/series come from Decimal over input CSVs, never from agent output.
Use --keep only for subsequent local browser inspection. Logs are private artifacts.
"""
import argparse
import csv
import io
import json
import os
import subprocess
import sys
import threading
import time
from collections import defaultdict
from dataclasses import asdict, replace
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from psycopg import sql
from psycopg.conninfo import make_conninfo
from decision_room.config import Config, ROOT
from decision_room.database import connect, migrate
from decision_room.local_env import load_env
from decision_room.agent.model import ModelSettings
from decision_room.agent import review
from decision_room.web.service import Workspace
from decision_room.web.server import Server
from decision_room.web.dashboard import projection
from decision_room.memory import extraction
from decision_room.evaluation.runner import source_version
from decision_room.evaluation.assess import token_accounting
from evaluate_context import check_report


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def oracle(raw, unit):
    days, categories = defaultdict(Decimal), defaultdict(Decimal)
    for row in csv.DictReader(io.StringIO(raw.decode())):
        value = Decimal(row['amount']) * (Decimal(row['quantity']) if unit else 1)
        days[row['date']] += value
        categories[row['category']] += value
    return dict(total=sum(days.values()), days=dict(days), categories=dict(categories))


class Evaluation:
    def __init__(self, config, settings, output):
        self.config, self.settings, self.output = config, settings, output
        self.checks, self.turns, self.reports = [], [], []
        self.open_server()

    def open_server(self):
        self.ws = Workspace(self.config, self.settings)
        self.server = Server(self.ws, 0, token='synthetic-evaluation-access')
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.client = httpx.Client(base_url=self.server.origin, timeout=60,
            headers={'Origin': self.server.origin, 'X-Decision-Room': '1'})
        self.post('/api/login', {'token': 'synthetic-evaluation-access'})

    def close_server(self):
        self.client.close()
        self.server.shutdown()
        self.server.server_close()

    def get(self, path):
        r = self.client.get(path)
        r.raise_for_status()
        return r.json()

    def post(self, path, body):
        r = self.client.post(path, json=body)
        r.raise_for_status()
        return r.json()

    def check(self, name, passed, **details):
        result = dict(name=name, passed=bool(passed), **details)
        self.checks.append(result)
        write(self.output/'checks.json', self.checks)
        print(json.dumps(result, ensure_ascii=False, default=str), flush=True)
        if not passed:
            raise AssertionError(name)

    def drain(self, chat):
        start = time.monotonic()
        for _ in range(24):
            while extraction.work_once(self.config, self.ws.model_factory, self.settings):
                pass
            self.ws.work_once()
            detail = self.get('/api/chats/'+chat)
            turn = detail['turns'][-1]
            if turn['status'] not in ('queued', 'routing', 'processing'):
                break
        elapsed = round(time.monotonic()-start, 2)
        write(self.output/(turn['id']+'.json'), detail)
        self.turns.append(dict(id=turn['id'], seconds=elapsed, status=turn['status'], text=turn['payload']['text']))
        return turn

    def create(self, analysis=None):
        return self.post('/api/chats', dict(business_id=self.business, request_key=str(uuid4()),
            title='Evaluación integrada', analysis_id=analysis))['id']

    def send(self, chat, text, **extra):
        self.post('/api/chats/'+chat+'/messages', dict(business_id=self.business,
            request_key=str(uuid4()), text=text, **extra))
        return self.drain(chat)

    def upload(self, raw, title, **extra):
        metadata = dict(business_id=self.business, request_key=str(uuid4()), title=title,
            mode='separate', period_from='2026-08-01', period_until='2026-08-02')
        metadata.update(extra)
        r = self.client.post('/api/datasets', data={'metadata':json.dumps(metadata)},
                             files={'file':('synthetic.csv', raw, 'text/csv')})
        r.raise_for_status()
        return r.json()['analysis_id']

    def define(self, analysis, unit=True, **extra):
        content = dict(topic='amount_basis', kind='definition',
            statement='En este conjunto cada fila es una venta de una categoría en una fecha. quantity son unidades. amount es '+
            ('el precio por unidad' if unit else 'el total de la fila')+
            ' en euros sin IVA, con descuentos aplicados. date es fecha y category la categoría. Todas las filas son válidas, independientes y están dentro del periodo indicado. No hay costes para calcular beneficio.',
            scope='analysis', scope_id=analysis, temporal_scope='unspecified', valid_from=None, valid_until=None, result_id=None)
        return self.post('/api/business/memory',dict(business_id=self.business, request_key=str(uuid4()),
            action=extra.pop('action','declare'), content=content, **extra))

    def verify_report(self, turn, expected, analysis, label, charts=True):
        self.check(label+': response', turn['status']=='completed' and (turn['response'] or {}).get('kind')=='evidence', issue=turn.get('issue'))
        r = review.show(self.config, self.business, turn['response']['report_id'])
        write(self.output/(label+'-report.json'), r)
        self.reports.append(r['id'])
        check_report(r, str(expected['total']))
        self.check(label+': exact dataset and total', str(r['analysis_id'])==analysis, expected=expected['total'])
        if charts:
            display = projection(r)
            actual = [{p['label']:Decimal(p['value']) for p in c['points']} for c in display['charts']]
            self.check(label+': daily and category values', expected['days'] in actual and expected['categories'] in actual,
                       expected=expected, actual=actual)
        return r

    def run(self):
        self.business = self.post('/api/business', dict(request_key=str(uuid4()), name='Taller Aurora · evaluación ficticia',
            description='Negocio ficticio con ventas y existencias. Los archivos y los periodos se analizan por separado.'))['business']['id']
        memory_chat = self.create()
        self.send(memory_chat, 'Nuestro local cierra todos los domingos.')
        recalled = self.send(self.create(), '¿Qué sabes sobre cuándo cerramos los domingos?')
        self.check('Memory reused between conversations', any(x['status']=='declared' and 'domingo' in x['content']['statement'].lower() for x in (recalled.get('response') or {}).get('items',[])))
        hypothesis = self.send(self.create(), 'Como hipótesis, quizá convendría agrupar los cobros semanalmente. No hemos decidido hacerlo.')
        remembered = self.send(self.create(), '¿Qué idea comenté sobre consolidar los ingresos por semanas? Recupera el mensaje original como antecedente, no como decisión.')
        self.check('Natural-language historical retrieval', (remembered.get('response') or {}).get('kind')=='history' and
            hypothesis['id'] in [x['message_id'] for x in remembered['response']['items']])
        raw=b'date,category,quantity,amount\n2026-08-01,A,2,12.50\n2026-08-01,B,1,40\n2026-08-02,A,3,15\n2026-08-02,B,2,20\n'
        analysis=self.upload(raw,'Ventas de agosto de 2026')
        definition=self.define(analysis)
        july=self.upload(raw.replace(b'2026-08',b'2026-07').replace(b'12.50',b'900'),'Ventas de julio de 2026',period_from='2026-07-01',period_until='2026-07-02')
        self.define(july,unit=False)
        self.upload(b'product,stock\nA,900\nB,600\n','Existencias de almacén')
        goal='Calcula el total registrado en las ventas de agosto de 2026. Usa las definiciones guardadas, sin extrapolar al negocio. Incluye un gráfico por fecha (etiquetas YYYY-MM-DD) y otro por categoría, con todos sus valores. No calcules beneficio.'
        analytical=self.create()
        result=self.send(analytical,goal)
        report=self.verify_report(result,oracle(raw,True),analysis,'initial')
        self.post('/api/chats/'+analytical+'/report',dict(business_id=self.business,turn_id=result['id']))
        dashboard=self.get('/api/dashboard')
        self.check('Published report reaches home',dashboard['report_id']==str(report['id']))
        chosen=report['report']['claims'][0]
        reference=dict(report_id=str(report['id']),report_version=report['approved_sha256'],claim_key=chosen['key'])
        explanation=self.send(self.create(analysis),'Explícame este hallazgo sin volver a calcular.',finding_reference=reference)
        self.check('Exact finding reused',explanation['status']=='completed' and explanation['response']['report_id']==str(report['id']) and
            {c['key'] for c in explanation['response']['claims']}=={chosen['key']})
        self.define(analysis,unit=False,action='correct',fact_id=definition['fact_id'],expected_revision=definition['revision'])
        self.check('Dossier correction withdraws dependent report',self.get('/api/dashboard')['report'] is None and self.client.get('/api/chats/'+analytical+'/report/'+result['id']).status_code==409)
        self.post('/api/chats/'+analytical+'/retry',dict(business_id=self.business,turn_id=result['id']))
        recalculated=self.drain(analytical)
        revised=self.verify_report(recalculated,oracle(raw,False),analysis,'memory-correction')
        self.post('/api/chats/'+analytical+'/report',dict(business_id=self.business,turn_id=result['id']))
        updated_raw=raw.replace(b'B,2,20',b'B,2,25')
        updated=self.upload(updated_raw,'Ventas de agosto actualizadas',mode='update',previous_id=analysis)
        self.define(updated,unit=False)
        self.check('New data preserves historical report',review.show(self.config,self.business,revised['id'])['publishable'] and bool(self.get('/api/dashboard')['data_version']['superseded_by']))
        updated_chat=self.create(updated)
        next_result=self.send(updated_chat,goal)
        newer=self.verify_report(next_result,oracle(updated_raw,False),updated,'updated-data')
        self.post('/api/chats/'+updated_chat+'/report',dict(business_id=self.business,turn_id=next_result['id']))
        corrected_raw=updated_raw.replace(b'B,2,25',b'B,2,35')
        corrected=self.upload(corrected_raw,'Ventas de agosto corregidas',mode='correction',previous_id=updated)
        self.define(corrected,unit=False)
        self.check('Data correction has targeted invalidation',not review.show(self.config,self.business,newer['id'])['publishable'] and review.show(self.config,self.business,revised['id'])['publishable'])
        corrected_chat=self.create(corrected)
        last=self.send(corrected_chat,goal)
        final=self.verify_report(last,oracle(corrected_raw,False),corrected,'corrected-data')
        self.post('/api/chats/'+corrected_chat+'/report',dict(business_id=self.business,turn_id=last['id']))
        final_dashboard=self.get('/api/dashboard')
        foreign=self.post('/api/business',dict(request_key=str(uuid4()),expected_active_id=self.business,
            name='Otro negocio ficticio',description='Espacio independiente sin ventas compartidas.'))['business']['id']
        self.check('Business isolation at HTTP boundary',not self.get('/api/chats')['conversations'] and not self.get('/api/dashboard')['report'] and self.client.get('/api/chats/'+analytical).status_code==404)
        foreign_chat=self.post('/api/chats',dict(business_id=foreign,request_key=str(uuid4())))['id']
        denied=self.client.post('/api/chats/'+foreign_chat+'/messages',json=dict(business_id=foreign,request_key=str(uuid4()),text='Explica',finding_reference=reference))
        self.check('Foreign finding rejected',denied.status_code in (404,409))
        self.post('/api/business/select',dict(business_id=self.business))
        # A separate interpreter must recover durable state without any server cache.
        self.close_server()
        recovered = json.loads(subprocess.check_output([sys.executable, '-c', '''
import json
from decision_room.config import Config
from decision_room.web.service import Workspace
from decision_room.conversations import Conversations
w = Workspace(Config.load())
print(json.dumps(dict(business=str(w.business_id()), dashboard=w.dashboard()['report_id'],
    conversations=[str(c['id']) for c in Conversations(w).listing()['conversations']])))
'''], cwd=ROOT, env={**os.environ, 'DECISION_ROOM_DATABASE_URL':self.config.dsn,
                     'DECISION_ROOM_STORAGE':str(self.config.storage)}, text=True))
        self.check('Separate process recovers durable state', recovered['business']==self.business and
            recovered['dashboard']==final_dashboard['report_id'] and corrected_chat in recovered['conversations'])
        self.open_server()
        self.check('Restart preserves active business, chats and selected report',self.get('/api/workspace')['business']['id']==self.business and
            self.get('/api/chats/'+corrected_chat)['turns'][-1]['response']['report_id']==str(final['id']) and self.get('/api/dashboard')['report_id']==final_dashboard['report_id'])
        return dict(business_id=self.business,chat_id=corrected_chat,report_id=str(final['id']),analysis_id=corrected)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--keep',action='store_true')
    args=p.parse_args();output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    load_env(ROOT/'.env');base=Config.load();settings=ModelSettings.load()
    name='dr_daily_eval_'+uuid4().hex
    with connect(base) as db:db.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
    config=replace(base,dsn=make_conninfo(base.dsn,dbname=name),storage=output/'storage')
    migrate(config);start=time.monotonic();ev=Evaluation(config,settings,output)
    summary=dict(passed=False,source_sha256=source_version(),model=asdict(settings))
    write(output/'state.json',dict(database=name,storage=str(config.storage)))
    try:
        state=ev.run();summary.update(state,passed=True)
    except Exception as error:
        summary['error']=str(error)
        raise
    finally:
        summary.update(seconds=round(time.monotonic()-start,2),checks=ev.checks,turns=ev.turns)
        summary['source_stable']=source_version()==summary['source_sha256']
        summary['passed']=summary['passed'] and summary['source_stable']
        with connect(config) as db:
            summary['resources']={}
            for table in ('agent_calls','chat_calls','memory_calls','semantic_calls','chat_retrievals','context_retrievals'):
                rows=db.execute(sql.SQL('SELECT * FROM {}').format(sql.Identifier(table))).fetchall()
                write(output/(table+'.json'),rows)
                if table.endswith('_calls'):
                    # Embeddings consume input tokens but do not generate completion tokens.
                    accounting = [dict(r, usage={**(r.get('usage') or {}), 'completion_tokens':0}) for r in rows] if table=='semantic_calls' else rows
                    summary['resources'][table]=dict(calls=len(rows),**token_accounting(accounting))
            for r in db.execute('SELECT id,business_id FROM agent_reviews').fetchall():
                write(output/('review-'+str(r['id'])+'.json'),review.show(config,r['business_id'],r['id']))
            write(output/'jobs.json',db.execute('SELECT * FROM web_jobs').fetchall())
            write(output/'questions.json',db.execute('SELECT * FROM agent_questions').fetchall())
        write(output/'summary.json',summary)
        ev.close_server()
        if not args.keep:
            with connect(base) as db:db.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
        print(json.dumps({k:v for k,v in summary.items() if k not in ('turns','checks','model')},default=str),flush=True)


if __name__=='__main__':main()
