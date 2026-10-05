"""Generic synthetic scope/materiality contracts; no customer datasets or model calls."""
from copy import deepcopy
import unittest
import jsonschema
import test_panorama_contract_v2 as base
from decision_room.agent.panorama_contract import gap_keys, metric_choices, validate
from decision_room.agent.review_contract import ReviewAction
from decision_room.panorama_presentation import material_gaps, compact, owner_sections, comparison_statement
from test_model_strict_schemas import assert_strict_objects


class MaterialityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=base.PanoramaContractTests()
        cls.fixture.frozen=base.frozen_fixture()

    def pair(self):
        context=self.fixture.context()
        return context,self.fixture.report(context)

    def action(self,report):
        return dict(action='submit',message='Informe',report=report,code='',table_ids=[],question='',assessment=None)

    def test_selection_is_recent_open_significant_stable_and_calendar_relative(self):
        def gap(key,start,end,days,product='Paper'):
            item=dict(start=start,end=end,channel='Shop',absent_expected_days=days,rows_in_gap={'metric':key})
            if product is not None:item['product']=product
            return item
        view=dict(tables=[dict(table_id='t',status='available',period=['2020-01-01','2026-08-31'],gaps=[
            gap('old','2021-01-01','2021-01-09',9,None),
            gap('short','2026-02-01','2026-02-03',3),
            gap('open','2026-08-30','2026-08-31',2),
            gap('large','2026-03-01','2026-03-12',10),
            gap('channel','2026-06-01','2026-06-04',4,None)])])
        selected=material_gaps(view)
        self.assertEqual([g['rows_in_gap']['metric'] for g in selected],['large','channel','open'])
        view['tables'][0]['gaps'].reverse()
        self.assertEqual(selected,material_gaps(view))

    def test_only_five_visible_but_all_material_require_disposition(self):
        frozen=deepcopy(self.fixture.frozen)
        table=frozen['tables'][0]; template=table['gaps'][0]
        table['gaps']=[dict(deepcopy(template),channel=f'Canal {i}',rows_in_gap=dict(execution_id='synthetic',metric=str(i))) for i in range(8)]
        frozen['observations'].append(dict(execution_id='synthetic',current=True,status='completed',result=dict(metrics={str(i):'0' for i in range(8)},evidence=[{'metric':str(i)} for i in range(8)])))
        sections=owner_sections(frozen,frozen['observations'])
        self.assertEqual(sum(len(s['alerts']) for s in sections),5)
        self.assertIn('Otros 3 huecos registrados, en la auditoría.',' '.join(sections[0]['lines']))
        self.assertEqual(len(gap_keys(dict(sales_panorama=compact(frozen,frozen['observations']),observations=frozen['observations']))),8)

    def test_flag_alone_enforces_priority_and_rejects_empty_saved_payload(self):
        context,report=self.pair();context['budgets'].pop('sales_panorama_contract')
        schema=self.fixture.schema(context);assert_strict_objects(self,schema)
        for field,value in [('panorama_priority',None),('alternative',' ' * 30),('why_first',''),('evidence',[])]:
            bad=deepcopy(report)
            if field=='panorama_priority':bad['claims'][0][field]=value
            else:bad['claims'][0]['panorama_priority'][field]=value
            with self.subTest(field=field):
                with self.assertRaises(ValueError):validate(bad,context)
                with self.assertRaises(jsonschema.ValidationError):jsonschema.validate(self.action(bad),schema)

    def test_generic_dismissal_needs_verifiable_proof_in_schema_and_validator(self):
        context,report=self.pair();key=gap_keys(context)[0]
        report['panorama_dispositions'][key]=dict(disposition='dismissed',claim_key=None,
            reason='No demuestra ventas perdidas ni una causa confirmada.')
        with self.assertRaisesRegex(ValueError,'verifiable proof'):validate(report,context)
        with self.assertRaises(jsonschema.ValidationError):jsonschema.validate(self.action(report),self.fixture.schema(context))

    def test_verified_owner_dismissal_and_mandatory_link_to_existing_scope(self):
        context,report=self.pair()
        key=next(g['key'] for g in material_gaps(context['sales_panorama']) if 'product' not in g)
        context['owner_context']='La tienda permaneció cerrada del 5 al 18 de mayo por reforma planificada.'
        decision=dict(disposition='dismissed',claim_key=None,reason='La ausencia coincide con el cierre planificado confirmado por el dueño.',
            proof=dict(kind='owner',verified_fact='El dueño confirma el cierre de la tienda durante este tramo.',source='owner_context',quote=context['owner_context']))
        report['panorama_dispositions'][key]=decision
        validate(report,context);jsonschema.validate(self.action(report),self.fixture.schema(context))
        bad=deepcopy(report);bad['panorama_dispositions'][key]['proof']['quote']='Inventado'
        with self.assertRaises(ValueError):validate(bad,context)
        with self.assertRaises(jsonschema.ValidationError):jsonschema.validate(self.action(bad),self.fixture.schema(context))
        gap=next(g for g in material_gaps(context['sales_panorama']) if g['key']==key)
        report['claims'][0]['focal_combinations']=[dict(table_id=gap['table_id'],product=gap.get('product'),channel=gap['channel'])]
        with self.assertRaisesRegex(ValueError,'existing focal finding'):validate(report,context)
        report['panorama_dispositions'][key]=dict(disposition='priority',claim_key='finding',reason=decision['reason'])
        validate(report,context)

    def test_gap_itself_cannot_be_used_to_dismiss_it(self):
        context,report=self.pair();key=gap_keys(context)[0]
        proof=dict(kind='evidence',verified_fact='La cobertura del archivo coincide con los días de cierre registrados.',evidence=[metric_choices(context)[0]])
        report['panorama_dispositions'][key]=dict(disposition='dismissed',claim_key=None,reason=proof['verified_fact'],proof=proof)
        with self.assertRaisesRegex(ValueError,'separate calculation'):validate(report,context)
        context['observations'].append(dict(execution_id='verified',status='completed',current=True,result=dict(metrics={'closure_days':'14'},evidence=[{'metric':'closure_days'}])))
        proof['evidence']=[dict(execution_id='verified',metric='closure_days')]
        validate(report,context);jsonschema.validate(self.action(report),self.fixture.schema(context))
        context['observations'][-1]['current']=False
        with self.assertRaises(ValueError):validate(report,context)

    def test_unavailable_evidence_does_not_silently_disable_contract(self):
        context,report=self.pair()
        for o in context['observations']:o['current']=False
        with self.assertRaisesRegex(ValueError,'no current evidence'):validate(report,context)
        with self.assertRaisesRegex(ValueError,'no current evidence'):self.fixture.schema(context)

    def test_custom_comparison_requires_visible_reason_once(self):
        context,report=self.pair();claim=report['claims'][0]
        claim['panorama_priority']['comparison']=dict(basis='custom',periods='Junio frente a mayo',reason='Comparamos estos meses para comprobar el cambio tras la reapertura.')
        validate(report,context);jsonschema.validate(self.action(report),self.fixture.schema(context))
        statement=comparison_statement(claim)
        self.assertEqual(statement.count('Comparamos estos meses'),1)
        claim['statement']=statement
        self.assertEqual(comparison_statement(claim),statement)
        claim['panorama_priority']['comparison']['reason']=''
        with self.assertRaises(ValueError):validate(report,context)
        with self.assertRaises(jsonschema.ValidationError):jsonschema.validate(self.action(report),self.fixture.schema(context))

    def test_owner_language_distinguishes_change_dimensions(self):
        lines=' '.join(line for s in owner_sections(self.fixture.frozen,self.fixture.frozen['observations']) for line in s['lines'])
        self.assertIn('unidades registradas',lines)
        self.assertNotIn('de cantidad registrada',lines)
        self.assertIn('por canal:',lines)
        self.assertIn('por producto y canal:',lines)

    def test_full_and_compact_contexts_enforce_identical_gaps(self):
        context,report=self.pair()
        full={**context,'sales_panorama':self.fixture.frozen}
        self.assertEqual(gap_keys(context),gap_keys(full))
        validate(report,full)
        self.assertEqual(self.fixture.schema(context)['$defs']['ReportDraft']['properties']['panorama_dispositions'],
                         self.fixture.schema(full)['$defs']['ReportDraft']['properties']['panorama_dispositions'])


    def test_mixed_focal_combinations_rejected_by_schema_and_validator(self):
        context,report=self.pair();schema=self.fixture.schema(context)
        report['claims'][0]['focal_combinations'][0]['channel']='Local + Web'
        with self.assertRaises(ValueError):validate(report,context)
        with self.assertRaises(jsonschema.ValidationError):jsonschema.validate(self.action(report),schema)
        report['claims'][0]['focal_combinations'][0]['channel']='Local'
        report['claims'][0]['focal_combinations']*=2
        with self.assertRaises(ValueError):validate(report,context)
        with self.assertRaises(jsonschema.ValidationError):jsonschema.validate(self.action(report),schema)

    def test_large_proof_schema_stays_strict_and_bounded(self):
        from decision_room.agent.model import ModelClient
        from decision_room.agent.schema_limits import bound_enums, validate_enum_limits
        context,report=self.pair()
        context['observations'].append(dict(execution_id='separate',current=True,status='completed',result=dict(
            metrics={f'calculation_{i}':str(i) for i in range(1200)},
            evidence=[dict(metric=f'calculation_{i}') for i in range(1200)])))
        schema=bound_enums(ModelClient._wire_schema(self.fixture.schema(context)))
        assert_strict_objects(self,schema);validate_enum_limits(schema)
        key=gap_keys(context)[0]
        report['panorama_dispositions'][key]=dict(disposition='dismissed',claim_key=None,
            reason='La comprobación separada confirma el calendario de cierre.',proof=dict(kind='evidence',
            verified_fact='El calendario revisado registra catorce días de cierre.',
            evidence=[dict(execution_id='separate',metric='calculation_1199')]))
        jsonschema.validate(self.action(report),schema);validate(report,context)
        report['panorama_dispositions'][key]['proof']['evidence'][0]['metric']='invented'
        with self.assertRaises(jsonschema.ValidationError):jsonschema.validate(self.action(report),schema)
        with self.assertRaises(ValueError):validate(report,context)

    def test_custom_reason_in_owner_html_pdf_and_support_bound_to_digest(self):
        from decision_room.agent.review_context import approval_digest
        from test_owner_presentation import readable
        from decision_room.web.dashboard import presentation
        from decision_room.web.presentation_html import render
        from decision_room.report_pdf import render_pdf
        from io import BytesIO
        from pypdf import PdfReader
        context,report=self.pair()
        data=readable();reason='Elegimos estos meses para observar la evolución después de la reapertura.'
        data['report']['claims'][0]['panorama_priority']=dict(report['claims'][0]['panorama_priority'],
            comparison=dict(basis='custom',periods='Junio frente a mayo',reason=reason))
        data['observations']+=deepcopy(self.fixture.frozen['observations'])
        view=presentation(data)
        html=render(view,'2026-10-05')
        pdf=' '.join(p.extract_text() for p in PdfReader(BytesIO(render_pdf(view))).pages)
        self.assertIn(reason,html);self.assertIn(reason,' '.join(pdf.split()))
        data['report']['panorama_dispositions']={'gap':dict(disposition='dismissed',claim_key=None,
            reason=reason,proof=dict(kind='evidence',verified_fact=reason,evidence=[dict(execution_id='separate',metric='closure_days')]))}
        data['observations'].append(dict(execution_id='separate',current=True,status='completed',result=dict(metrics={'closure_days':'14'},evidence=[dict(metric='closure_days')])))
        original=approval_digest(data,'knowledge')
        data['observations'][-1]['result']['metrics']['closure_days']='15'
        self.assertNotEqual(original,approval_digest(data,'knowledge'))


    def test_owner_quote_is_provenance_not_a_recomputed_percentage(self):
        from decision_room.agent.review_contract import checks
        context,report=self.pair()
        context['owner_context']='Buscamos un margen del 10%. La tienda cerró del 5 al 18 de mayo por reforma.'
        key=gap_keys(context)[0]
        report['panorama_dispositions'][key]=dict(disposition='dismissed',claim_key=None,
            reason='El dueño confirma una reforma planificada durante el tramo sin registros.',
            proof=dict(kind='owner',source='owner_context',quote=context['owner_context'],
                verified_fact='El dueño confirma un cierre planificado por obras en la tienda.'))
        validate(report,context)
        self.assertTrue(all(c['passed'] for c in checks(report,context['observations'])))
        report['claims'][0]['statement']='Las unidades crecieron un 10%.'
        self.assertFalse(all(c['passed'] for c in checks(report,context['observations'])))
