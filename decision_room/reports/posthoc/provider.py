"""Existing engine proxy plus a shared durable USD guard for the exploratory pilot.

The count endpoint runs first. A reservation at the catalogue's worst applicable
cache-write rate is persisted before forwarding generation. Unknown cost blocks
all later calls. Credentials are constructor-only and never written to artifacts.
"""
from decimal import Decimal
import json
from pathlib import Path
import sqlite3

import httpx

from ...engine import admission, costs, proxy
from .inventory import canonical
from .interpretation import save_new


class BudgetStop(RuntimeError):
    pass


class Budget:
    def __init__(self,path,*,limit='3',report_limit='0.50'):
        self.path=Path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.limit,self.report_limit=Decimal(limit),Decimal(report_limit)
        if not 0<self.report_limit<=self.limit<=3:raise ValueError('Budget outside approved ceiling.')
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS policy (id INTEGER PRIMARY KEY, total TEXT, per_report TEXT)')
            db.execute('INSERT OR IGNORE INTO policy VALUES(1,?,?)',(str(self.limit),str(self.report_limit)))
            if db.execute('SELECT total,per_report FROM policy').fetchone()!=(str(self.limit),str(self.report_limit)):
                raise BudgetStop('Existing budget policy differs; no reset permitted.')
            db.execute('CREATE TABLE IF NOT EXISTS calls (id TEXT PRIMARY KEY, report TEXT, state TEXT, reservation TEXT, cost TEXT)')

    def reserve(self,key,report,upper):
        upper=Decimal(upper)
        if not upper.is_finite() or upper<0:raise ValueError('Invalid cost reservation.')
        with sqlite3.connect(self.path) as db:
            db.execute('BEGIN IMMEDIATE')
            rows=db.execute('SELECT id,report,state,reservation,cost FROM calls').fetchall()
            if any(row[0]==key for row in rows):raise BudgetStop('Call already recorded; never replay.')
            if any(row[2]!='settled' for row in rows):raise BudgetStop('An unresolved call blocks the budget.')
            total=sum((Decimal(r[4]) for r in rows),Decimal(0))
            own=sum((Decimal(r[4]) for r in rows if r[1]==report),Decimal(0))
            if total+upper>self.limit or own+upper>self.report_limit:
                raise BudgetStop('Call reservation would exceed the global or report budget.')
            db.execute('INSERT INTO calls VALUES(?,?,?,?,NULL)',(key,report,'pending',str(upper)))

    def settle(self,key,catalog):
        cost=catalog.get('cost') if catalog and catalog.get('status')=='estimated' else None
        if cost is not None and (not Decimal(cost).is_finite() or Decimal(cost)<0):cost=None
        with sqlite3.connect(self.path) as db:
            db.execute('BEGIN IMMEDIATE')
            prior=db.execute('SELECT state,reservation,cost FROM calls WHERE id=?',(key,)).fetchone()
            if prior is None:raise BudgetStop('Missing budget reservation.')
            if prior[0]!='pending':raise BudgetStop('A settled or uncertain call cannot be rewritten.')
            state='settled' if cost is not None and Decimal(cost)<=Decimal(prior[1]) else 'uncertain'
            db.execute('UPDATE calls SET state=?,cost=? WHERE id=?',(state,cost,key))
        if state!='settled':raise BudgetStop('Unknown or out-of-reservation cost; stop and consult.')

    def inspect(self):
        with sqlite3.connect(self.path) as db:
            rows=db.execute('SELECT id,report,state,reservation,cost FROM calls ORDER BY rowid').fetchall()
        return {'limit':str(self.limit),'per_report':str(self.report_limit),
                'known_cost':str(sum((Decimal(r[4]) for r in rows if r[4] is not None),Decimal(0))),
                'unresolved':sum(r[2]!='settled' for r in rows),
                'calls':[dict(zip(('id','report','state','reservation','cost'),r)) for r in rows]}


class ReservedTransport(httpx.BaseTransport):
    def __init__(self,budget,key,report,transport=None):
        self.budget,self.key,self.report=budget,key,report
        self.inner=transport or httpx.HTTPTransport(retries=0,trust_env=False,http2=False,
                        limits=httpx.Limits(max_keepalive_connections=0))
        self.count=None;self.reserved=False;self.sent=False

    def handle_request(self,request):
        if request.url.path.endswith('/responses/input_tokens'):
            response=self.inner.handle_request(request)
            response.read()
            if response.status_code==200:
                self.count=response.json().get('input_tokens')
            return response
        if request.url.path.endswith('/responses'):
            if type(self.count) is not int or self.count<0:raise BudgetStop('Missing counted input.')
            body=json.loads(request.content)
            estimate=costs.estimate({'requested_model':body['model'],'effective_model':body['model'],
                'effective_tier':'default','input':self.count,'output':body['max_output_tokens'],
                'cache_read':0,'cache_write':self.count})
            if estimate['status']!='estimated':raise BudgetStop('No applicable conservative catalogue.')
            self.budget.reserve(self.key,self.report,estimate['cost']);self.reserved=True
            self.sent=True
            return self.inner.handle_request(request)
        raise ValueError('Unexpected provider endpoint.')

    def close(self):self.inner.close()


class ProxyInterpreter:
    def __init__(self,config,business_id,run_id,token,*,api_key,budget,report,dest,transport=None,output_tokens=16000):
        self.config,self.business_id,self.run_id,self.token=config,business_id,run_id,token
        self.api_key,self.budget,self.report=api_key,budget,report
        self.dest=Path(dest);self.dest.mkdir(parents=True,exist_ok=False)
        self.transport=transport;self.output_tokens=output_tokens

    def __call__(self,prompt,request,key):
        folder=self.dest/key;folder.mkdir(exist_ok=False)
        credential=admission.authenticate(self.config,self.run_id,self.token)
        if credential['model']!='gpt-6-luna':raise ValueError('Pilot model must match the frozen configuration.')
        payload={'model':credential['model'],'instructions':prompt,'input':canonical({'response_format':'json',**request}).decode(),
                 'max_output_tokens':self.output_tokens,'reasoning':{'effort':'low'},
                 'text':{'format':{'type':'json_object'}},'service_tier':'default','stream':False}
        save_new(folder/'request.json',payload)
        transport=ReservedTransport(self.budget,str(self.run_id)+':'+key,self.report,self.transport)
        before={str(c['id']) for c in admission.inspect_run(self.config,self.business_id,self.run_id)['model_calls']}
        chunks=[];failure=None
        try:
            proxy.forward(self.config,self.run_id,self.token,canonical(payload),api_key=self.api_key,
                          transport=transport,send_headers=lambda *args:None,write=chunks.append)
        except BaseException as error:failure=error
        finally:
            transport.close()
            with (folder/'response.raw').open('xb') as handle:handle.write(b''.join(chunks))
            calls=[c for c in admission.inspect_run(self.config,self.business_id,self.run_id)['model_calls'] if str(c['id']) not in before]
            # Database timestamps/UUIDs are encoded explicitly, never credentials.
            safe=json.loads(json.dumps(calls,default=str))
            save_new(folder/'proxy-calls.json',safe)
            if transport.reserved:
                catalog=calls[0].get('cost_catalog') if len(calls)==1 else None
                self.budget.settle(transport.key,catalog)
            save_new(folder/'budget.json',self.budget.inspect())
        if failure is not None:raise failure
        response=json.loads(b''.join(chunks))
        save_new(folder/'response.json',response)
        if response.get('status')!='completed':raise ValueError('Incomplete model response.')
        texts=[part['text'] for item in response.get('output',[]) if item.get('type')=='message'
               for part in item.get('content',[]) if part.get('type')=='output_text']
        if len(texts)!=1:raise ValueError('Expected one explicit interpretation result.')
        with (folder/'interpretation.txt').open('x') as handle:handle.write(texts[0])
        return json.loads(texts[0])
