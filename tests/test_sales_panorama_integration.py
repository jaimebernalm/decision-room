"""Real private PostgreSQL/storage/Docker, scripted roles; no real model requests."""
import csv
import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from uuid import uuid4

from decision_room.agent import service as agent_service, research, review
from decision_room.agent.context import snapshot, fingerprint
from decision_room.config import Config
from decision_room.database import connect
from decision_room.service import create_business, import_batch
from decision_room.sales_panorama_store import prepare, review_snapshot, materialize
from decision_room.sales_panorama import VERSION
from decision_room.series import evidence_value
from decision_room.report import export
from test_research import ResearchModel
import test_research as research_tests
from test_review import DialogueModel, draft, action
from test_sales_panorama import fixture


class PanoramaDialogue(DialogueModel):
    def generate_analyst_review(self, context, correction=None):
        self.contexts.append(deepcopy(context))
        report = draft(context)
        if context.get('sales_panorama'):
            report['claims'][0]['evidence'] = [context['sales_panorama']['tables'][0]['total']['reference']]
            report['claims'][0]['method'] = 'Suma de cantidades registradas en el archivo completo.'
        opening=deepcopy(report['claims'][0])
        opening.update(key='overview',title='Panorama del extracto')
        report['claims'].insert(0,opening)
        if context.get('budgets', {}).get('sales_panorama_contract') == 2:
            from test_panorama_contract_v2 import add_decisions
            add_decisions(report, context)
        return action('submit',report=report), {}


class PanoramaPersistenceTests(unittest.TestCase):
    setUpClass = classmethod(research_tests.ResearchTests.setUpClass.__func__)
    tearDownClass = classmethod(research_tests.ResearchTests.tearDownClass.__func__)

    def setUp(self):
        self.temp = TemporaryDirectory(prefix='dr-panorama-')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.config=replace(self.base,dsn=self.dsn,storage=self.root/'storage')
        self.business=create_business(self.config,'Synthetic shop')['id']
        self.path=self.root/'sales.csv'
        with self.path.open('w',newline='') as f:
            writer=csv.writer(f); writer.writerow(['date','product','channel','quantity','amount'])
            writer.writerows([*r,'1'] for r in fixture())
        self.analysis=import_batch(self.config,self.business,[self.path])['analysis']['id']
        with connect(self.config) as db:
            self.table=str(db.execute('SELECT id FROM prepared_tables WHERE analysis_id=%s',(self.analysis,)).fetchone()['id'])

    def cache_count(self):
        with connect(self.config) as db:
            return db.execute('SELECT count(*) n FROM sales_panoramas WHERE business_id=%s',(self.business,)).fetchone()['n']

    def test_import_flag_idempotency_mapping_scope_and_integrity(self):
        before=snapshot(self.config,self.business,self.analysis,'Quantities are units.')
        self.assertEqual(self.cache_count(),0)
        enabled=replace(self.config,sales_panorama=True)
        import_batch(enabled,self.business,[self.path])
        self.assertEqual(self.cache_count(),1)
        import_batch(enabled,self.business,[self.path])
        self.assertEqual(self.cache_count(),1)
        self.assertEqual(snapshot(self.config,self.business,self.analysis,'Quantities are units.'),before)
        prepared=prepare(self.config,self.business,self.analysis)
        frozen=review_snapshot(prepared,'initial')
        current=materialize(self.config,self.business,frozen,'initial')
        self.assertTrue(all(o['current'] for o in current['observations']))
        old=materialize(self.config,self.business,frozen,'new knowledge')
        with self.assertRaisesRegex(ValueError,'obsolete'):
            evidence_value(old['observations'],old['tables'][0]['total'])
        other=create_business(self.config,'Other')['id']
        with self.assertRaisesRegex(ValueError,'business'):
            prepare(self.config,other,self.analysis)
        with self.assertRaisesRegex(ValueError,'another business'):
            materialize(self.config,other,frozen,'initial')
        with self.assertRaisesRegex(ValueError,'unauthorized'):
            prepare(self.config,self.business,self.analysis,{str(uuid4()):{}})
        changed=deepcopy(frozen); changed['observations'][0]['result']['metrics']['total']='999'
        with self.assertRaisesRegex(ValueError,'integrity'):
            materialize(self.config,self.business,changed,'initial')
        with connect(self.config) as db:
            db.execute("UPDATE sales_panoramas SET body=jsonb_set(body,'{status}','\"broken\"') WHERE business_id=%s",(self.business,))
        with self.assertRaisesRegex(ValueError,'cache integrity'):
            prepare(self.config,self.business,self.analysis)

    def test_quoted_timestamp_csv_through_real_import_and_frozen_evidence(self):
        from decimal import Decimal
        from decision_room.storage import Storage
        import duckdb
        path=Path(__file__).parent/'fixtures'/'sales_panorama_timestamps.csv'
        self.assertIn('"2021-09-01 00:00:00"',path.read_text())
        enabled=replace(self.config,sales_panorama=True)
        with patch('decision_room.agent.model.ModelClient._generate',side_effect=AssertionError('No model calls')):
            analysis=import_batch(enabled,self.business,[path])['analysis']['id']
            with connect(self.config) as db:
                cached=db.execute('SELECT body FROM sales_panoramas WHERE business_id=%s',(self.business,)).fetchall()
                table=db.execute('SELECT * FROM prepared_tables WHERE analysis_id=%s',(analysis,)).fetchone()
            self.assertEqual(len(cached),1)  # generated by import, not a test-only calculator path
            body=cached[0]['body']
            self.assertEqual(body['status'],'available')
            self.assertEqual(body['summary']['mapping'],dict(date='fecha',channel='canal_id',product='producto_id',quantity='unidades'))
            self.assertEqual(body['diagnostics']['invalid_rows'],0)
            self.assertEqual(body['diagnostics']['row_count'],5)
            self.assertEqual(Decimal(body['result']['metrics']['total']),28)
            self.assertEqual(Decimal(body['result']['metrics']['period_before']),10)
            self.assertEqual(Decimal(body['result']['metrics']['period_current']),18)
            self.assertEqual(Decimal(body['result']['metrics']['period_change']),8)
            with duckdb.connect() as db:
                rows=db.read_parquet(str(Storage(enabled.storage).path(self.business,table['parquet_key'])))
                self.assertEqual(rows.project('fecha').fetchone()[0],'2021-09-01 00:00:00')
                self.assertEqual(str(rows.types[1]),'VARCHAR')
            prepared=prepare(enabled,self.business,analysis)
            self.assertEqual(prepared[0]['body'],body)
            frozen=review_snapshot(prepared,'unchanged knowledge')
            view=materialize(enabled,self.business,frozen,'unchanged knowledge')
            overview=view['tables'][0]
            self.assertEqual(overview['status'],'available')
            self.assertEqual(overview['period'],['2021-09-01','2021-10-31'])
            self.assertEqual(Decimal(evidence_value(view['observations'],overview['total'])),28)
            self.assertEqual(Decimal(evidence_value(view['observations'],overview['comparison']['change'])),8)
            self.assertTrue(all(o['origin']==VERSION for o in view['observations']))

    def test_old_import_reuses_frozen_research_only_writer_reviewer_receive_panorama(self):
        model=ResearchModel()
        parent=agent_service.start(self.config,self.business,self.analysis,owner_context='Amount is unit price. Quantity is units.',request_key='plan',model=model)
        run=research.start(self.config,self.business,parent['id'],request_key='research',model=model,delegation=False)
        with connect(self.config) as db:
            original=db.execute('SELECT snapshot FROM agent_research WHERE id=%s',(run['id'],)).fetchone()['snapshot']
            original_calls=db.execute("SELECT context_payload FROM agent_calls WHERE session_id=%s AND phase IN ('planning','research') ORDER BY created_at",(parent['id'],)).fetchall()
            count=db.execute('SELECT count(*) n FROM executions WHERE business_id=%s',(self.business,)).fetchone()['n']
        control_model=PanoramaDialogue('simple')
        config=replace(self.config,sales_panorama=True)
        with patch('decision_room.agent.parallel_research.synthesis',return_value={'priorities':[{'investigation_key':'sales'}]}):
            control=review.start(config,self.business,run['id'],request_key='control',sales_panorama=False,analyst=control_model,reviewer=control_model)
        self.assertEqual(control['report']['claims'][0]['key'],'sales')
        self.assertTrue(control['publishable'])
        self.assertEqual(self.cache_count(),0)
        self.assertTrue(all('sales_panorama' not in c for c in control_model.contexts))
        candidate_model=PanoramaDialogue('simple')
        with patch('decision_room.agent.parallel_research.synthesis',return_value={'priorities':[{'investigation_key':'sales'}]}):
            candidate=review.start(config,self.business,run['id'],request_key='p1a',analyst=candidate_model,reviewer=candidate_model)
        self.assertEqual(candidate['report']['claims'][0]['key'],'overview')
        self.assertTrue(candidate['publishable'])
        self.assertTrue(candidate['options']['sales_panorama'])
        self.assertNotIn('owner_presentation',candidate['options'])
        self.assertEqual(self.cache_count(),1)
        self.assertEqual({c['role'] for c in candidate_model.contexts},{'analyst','reviewer'})
        for context in candidate_model.contexts:
            self.assertIn('sales_panorama',context)
            self.assertEqual(context['budgets']['python_used'],{'analyst':0,'reviewer':0})
        ref=candidate['report']['claims'][0]['evidence'][0]
        self.assertEqual(ref,candidate['sales_panorama']['tables'][0]['total'])
        self.assertIsNotNone(evidence_value(candidate['observations'],ref))
        resumed=review.resume(self.config,self.business,candidate['id'],analyst=candidate_model,reviewer=candidate_model)
        self.assertEqual(resumed['approved_sha256'],candidate['approved_sha256'])
        with self.assertRaisesRegex(ValueError,'different inputs'):
            review.start(config,self.business,run['id'],request_key='p1a',sales_panorama=False,analyst=candidate_model,reviewer=candidate_model)
        with connect(self.config) as db:
            self.assertEqual(db.execute('SELECT count(*) n FROM executions WHERE business_id=%s',(self.business,)).fetchone()['n'],count)
            self.assertEqual(db.execute('SELECT snapshot FROM agent_research WHERE id=%s',(run['id'],)).fetchone()['snapshot'],original)
            self.assertEqual(db.execute("SELECT context_payload FROM agent_calls WHERE session_id=%s AND phase IN ('planning','research') ORDER BY created_at",(parent['id'],)).fetchall(),original_calls)
            versions=db.execute('SELECT DISTINCT prompt_version FROM agent_calls WHERE scope=%s',(str(candidate['id']),)).fetchall()
        self.assertTrue(all('sales-panorama-v2' in v['prompt_version'] for v in versions))
        self.assertNotIn('sales_panorama',json.dumps(original_calls,default=str))
        combined_model=PanoramaDialogue('simple')
        combined=review.start(config,self.business,run['id'],request_key='p1a-p3',owner_presentation=True,
                              analyst=combined_model,reviewer=combined_model)
        self.assertTrue(combined['publishable'])
        self.assertTrue(combined['options']['owner_presentation'])
        self.assertEqual(combined['sales_panorama'],candidate['sales_panorama'])
        combined_export=export(self.config,self.business,combined['id'])
        self.assertNotIn('SUM(',Path(combined_export['path']).read_text())
        exported=export(self.config,self.business,candidate['id'])
        audit=json.loads(Path(exported['audit_path']).read_text())
        self.assertEqual(audit['sales_panorama'],candidate['sales_panorama'])
        self.assertEqual(audit['report']['claims'][0]['evidence'][0],ref)
        self.assertIn(VERSION,Path(exported['internal_path']).read_text())

    def test_actual_quoted_csv_timestamp_gap_import_with_verified_catalog(self):
        from decision_room.data_knowledge.discovery import discover
        from decision_room.web.presentation_editing import catalog_labels
        from decision_room.panorama_presentation import owner_sections, render_html
        sales = self.root/'recorded.csv'
        with sales.open('w', newline='') as file:
            writer = csv.writer(file, quoting=csv.QUOTE_ALL)
            writer.writerow(['fecha','canal_id','producto_id','unidades'])
            writer.writerows([r[0]+' 00:00:00', 'LO' if r[2]=='Local' else 'WE', r[1], r[3]] for r in fixture())
        catalog = self.root/'channels.csv'
        catalog.write_text('canal_id,nombre\nLO,Tienda de barrio\nWE,Web propia\n')
        analysis = import_batch(replace(self.config,sales_panorama=True), self.business, [sales,catalog])['analysis']['id']
        class Proposer:
            identity={'model':'scripted-catalog'}
            def generate_data_discovery(inner, context, correction=None):
                by={t['name']:t['id'] for t in context['profiles']}
                return dict(tables=[],limitations=[],relations=[dict(source=by['recorded.csv'],target=by['channels.csv'],source_columns=['canal_id'],target_columns=['canal_id'],description='Catálogo de canales')]), {}
        discover(self.config,self.business,analysis,Proposer())
        with connect(self.config) as db:
            labels=catalog_labels(self.config,self.business,analysis,db)
        self.assertEqual({r['code'] for r in labels},{'LO','WE'})
        frozen=review_snapshot(prepare(self.config,self.business,analysis),'knowledge',labels)
        materialized=materialize(self.config,self.business,frozen,'knowledge')
        html=render_html(owner_sections(materialized,materialized['observations']))
        self.assertIn('Tienda de barrio: sin registros del 5 de mayo de 2025 al 18 de mayo de 2025',html)
        self.assertIn('Web propia:',html)
        self.assertNotIn('LO:',html)
        self.assertNotIn('WE:',html)
