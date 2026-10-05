"""P1a v2: obligatory gap decisions, priorities, frozen owner view and wire order."""
from copy import deepcopy
import json
from uuid import uuid4
import unittest
from unittest.mock import patch
import jsonschema

from decision_room.agent.context import fingerprint
from decision_room.agent.model import ModelClient, ModelSettings
from decision_room.agent.panorama_contract import gap_keys, metric_choices, validate
from decision_room.agent.review_contract import ReportDraft, ReviewAction
from decision_room.panorama_presentation import compact, owner_sections, render_html
from decision_room.sales_panorama_store import review_snapshot
from test_sales_panorama import PanoramaTests, fixture
from test_model_strict_schemas import assert_strict_objects


def frozen_fixture():
    # Exact date format from real imports, all synthetic content.
    rows = [[r[0] + ' 00:00:00', *r[1:]] for r in fixture()]
    body = PanoramaTests().compute(rows)
    body['specification'] = dict(code_sha256='hash', parquet_sha256='source')
    return review_snapshot([dict(table_id=str(uuid4()), names=['synthetic.csv'], body=body,
        body_sha256=fingerprint(body), code='calculator')], 'knowledge', [])


def add_decisions(report, context):
    report['panorama_dispositions'] = {key:dict(disposition='dismissed', claim_key=None,
        reason='Comprobar primero la continuidad de los registros antes de recomendar cambios de oferta.') for key in gap_keys(context)}
    for claim in report['claims']:
        claim['panorama_priority'] = dict(alternative='El hueco en los registros requiere comprobar cobertura antes de interpretar la caída.',
            why_first='Primero describimos la cantidad disponible para evitar decidir con cobertura incompleta.',
            evidence=[metric_choices(context)[0]])


class PanoramaContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.frozen = frozen_fixture()

    def context(self):
        return dict(sales_panorama=compact(self.frozen, self.frozen['observations']),
            observations=deepcopy(self.frozen['observations']), budgets={'sales_panorama':True,'sales_panorama_contract':2},
            tables=[], conversation=[])

    def report(self, context):
        report = dict(contract_version=2, title='Informe', summary='Resumen', scope=dict(business='Tienda',question='Evolución',period='2025',coverage='Registros disponibles'),
            charts=[],no_chart_reason='El panorama permite leer la comparación.',claims=[dict(key='finding',title='Una comparación',statement='Las cantidades cambian.',evidence=[metric_choices(context)[0]],
                interpretation='Comprobar la cobertura.',next_step='',method='Suma de cantidades.')],limitations=['No confirma causas.'],checks=[])
        add_decisions(report,context)
        return ReportDraft.model_validate(report).model_dump()

    def schema(self, context):
        captured = []
        client = ModelClient(ModelSettings('offline'))
        with patch.object(client, '_generate', side_effect=lambda c,r,s,sc: captured.append(sc)):
            client.generate_analyst_review({'review_policy':5, **context})
        return captured[0]

    def test_exact_gap_contract_and_current_panorama_evidence(self):
        context=self.context(); report=self.report(context); schema=self.schema(context)
        self.assertGreater(len(gap_keys(context)),0)
        assert_strict_objects(self,schema)
        action=ReviewAction(action='submit',message='Informe listo',report=report,code='',table_ids=[],question='',assessment=None).model_dump()
        jsonschema.validate(action,schema)
        validate(report,context)
        key=gap_keys(context)[0]
        for mutation in ('missing','unknown','empty_reason','wrong_evidence','no_comparison'):
            bad=deepcopy(action)
            if mutation=='missing': del bad['report']['panorama_dispositions'][key]
            elif mutation=='unknown': bad['report']['panorama_dispositions']['invented']=bad['report']['panorama_dispositions'][key]
            elif mutation=='empty_reason': bad['report']['panorama_dispositions'][key]['reason']=' '
            elif mutation=='wrong_evidence': bad['report']['claims'][0]['panorama_priority']['evidence'][0]['metric']='invented'
            else: bad['report']['claims'][0]['panorama_priority']=None
            with self.subTest(mutation=mutation), self.assertRaises(jsonschema.ValidationError): jsonschema.validate(bad,schema)
        report['panorama_dispositions'][key]=dict(disposition='priority',claim_key='finding',reason='El hueco requiere verificar los registros del canal antes de decidir.')
        validate(report,context)
        report['panorama_dispositions'][key]['claim_key']='missing'
        with self.assertRaisesRegex(ValueError,'finding in this report'): validate(report,context)

    def test_flag_off_and_unavailable_do_not_require_invented_decisions(self):
        for context in (dict(budgets={}, observations=[]), dict(budgets={'sales_panorama_contract':2},sales_panorama={'tables':[]}, observations=[])):
            schema=self.schema(context)
            self.assertEqual(schema['$defs']['ReportDraft']['properties']['panorama_dispositions']['required'],[])
            self.assertEqual(schema['$defs']['Claim']['properties']['panorama_priority'],{'type':'null'})
            assert_strict_objects(self,schema)

    def test_prompt_starts_with_compact_panorama_without_duplicated_sql(self):
        context=self.context()
        prompt=ModelClient._prompt_context(context)
        self.assertTrue(prompt.startswith('{"sales_panorama":'))
        self.assertNotIn('SUM(',json.dumps(context['sales_panorama']))
        self.assertNotIn('result', context['sales_panorama'])
        self.assertLess(len(json.dumps(context['sales_panorama'])),len(json.dumps(self.frozen)))
        self.assertEqual(json.loads(prompt),context)

    def test_frozen_opening_is_present_without_any_model_citation(self):
        sections=owner_sections(self.frozen,self.frozen['observations'])
        html=render_html(sections)
        self.assertIn('Panorama',html)
        self.assertIn('Local: sin registros del 5 de mayo de 2025 al 18 de mayo de 2025',html)
        self.assertIn('últimos tres meses completos',html)
        self.assertNotIn('SUM(',html)
        self.assertNotIn('channel_gap',html)
        self.assertIn('no ventas cero',html)
        self.assertEqual(self.frozen,self.__class__.frozen)

    def test_frozen_catalog_names_and_escaped_owner_html(self):
        frozen=deepcopy(self.frozen)
        for table in frozen['tables']:
            for item in table.get('totals',{}).get('channel',[]): item['channel']='HO'
        frozen['catalog_labels']=[dict(code='HO',name='Hostelería <b>verificada</b>')]
        html=render_html(owner_sections(frozen,frozen['observations']))
        self.assertIn('Hostelería &lt;b&gt;verificada&lt;/b&gt;',html)
        self.assertNotIn('HO:',html)

    def test_html_and_pdf_open_before_summary_and_keep_audit_out(self):
        from test_owner_presentation import readable
        from decision_room.web.dashboard import presentation
        from decision_room.web.presentation_html import render
        from decision_room.report_pdf import render_pdf
        from io import BytesIO
        from pypdf import PdfReader
        data = readable()
        data['options'].update(sales_panorama=True, sales_panorama_contract=2)
        data['sales_panorama'] = self.frozen
        data['observations'] += self.frozen['observations']
        view = presentation(data)
        self.assertTrue(view['panorama'])
        html = render(view, '2026-10-05')
        text = '\n'.join(p.extract_text() for p in PdfReader(BytesIO(render_pdf(view))).pages)
        for body in (html, text):
            self.assertLess(body.index('Panorama'), body.index(view['summary']))
            self.assertIn('Local: sin registros del 5 de mayo', body)
        self.assertNotIn('channel_gap', html)

    def test_approval_binds_uncited_panorama_values(self):
        from decision_room.agent.review_context import approval_digest
        from test_client_report import sample
        data = sample()
        data.update(budgets={'sales_panorama_contract':2},sales_panorama={k:v for k,v in self.frozen.items() if k!='observations'})
        data['observations'] += deepcopy(self.frozen['observations'])
        before = approval_digest(data, 'knowledge')
        target = next(o for o in data['observations'] if 'total' in o['result']['metrics'])
        target['result']['metrics']['total'] = '999999'
        self.assertNotEqual(before, approval_digest(data, 'knowledge'))
