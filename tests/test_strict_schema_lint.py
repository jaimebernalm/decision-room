"""Strict wire lint, multiline owner quotes and the complete review option matrix."""
from copy import deepcopy
from itertools import product
import unittest
from unittest.mock import patch
import jsonschema
from decision_room.agent.schema_limits import validate_strict_schema
from decision_room.agent.model import ModelClient,ModelSettings
from decision_room.agent.panorama_contract import validate,gap_keys,owner_sources
import test_model_strict_schemas as strict_tests
from test_panorama_contract_v2 import PanoramaContractTests, frozen_fixture
from test_review_budget import large_context


class LintTests(unittest.TestCase):
    def test_each_forbidden_literal_and_object_rule_in_nested_defs(self):
        root=dict(type='object',additionalProperties=False,properties={},required=[])
        for keyword,character in product(('enum','const','pattern'),('\n','\r','\t')):
            bad=deepcopy(root);bad['$defs']={'hidden':{keyword:['a'+character+'b'] if keyword=='enum' else 'a'+character+'b'}}
            with self.subTest(keyword=keyword,character=repr(character)),self.assertRaisesRegex(ValueError,'control character'):
                validate_strict_schema(bad)
        for node in (dict(type='object',properties={},required=[]),
                     dict(type='object',additionalProperties=False,properties={'a':{'type':'string'}},required=[]),
                     dict(type='object',additionalProperties=False,properties={'a':{'type':'string'}},required=['a','a'])):
            bad=deepcopy(root);bad['$defs']={'hidden':node}
            with self.assertRaises(ValueError):validate_strict_schema(bad)
        bad=deepcopy(root);bad['$defs']={'a':{'enum':list(range(600))},'b':{'enum':list(range(401))}}
        with self.assertRaisesRegex(ValueError,'1001 enum values'):validate_strict_schema(bad)
        validate_strict_schema(root)

    def test_invalid_generated_pattern_stops_before_http(self):
        schema=dict(type='object',additionalProperties=False,properties={'s':dict(type='string',pattern='a\nb')},required=['s'])
        client=ModelClient(ModelSettings('offline',protocol='openai',base_url='https://api.openai.com/v1'))
        with patch('decision_room.agent.model.httpx.AsyncClient') as http,self.assertRaisesRegex(ValueError,'control character'):
            client._generate({},None,'Instructions',schema)
        http.assert_not_called()

    def test_dynamic_multiline_label_enum_is_relaxed_not_corrupted(self):
        schema=dict(type='object',additionalProperties=False,properties={'s':dict(type='string',enum=['a\nb','c\td','e\rf'])},required=['s'])
        wire=ModelClient._wire_schema(schema)
        validate_strict_schema(wire)
        self.assertNotIn('enum',wire['properties']['s'])
        for value in schema['properties']['s']['enum']:jsonschema.validate({'s':value},wire)
        self.assertIn('enum',schema['properties']['s'])


class OwnerQuoteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=PanoramaContractTests();cls.fixture.frozen=frozen_fixture()

    def test_source_id_and_literal_substring_with_normalized_spaces(self):
        context=self.fixture.context()
        message='Resumen del negocio.\nLa tienda cerró\tpor reforma.\r\nAhora está abierta.'
        context['owner_context']=message
        context['owner_answers']=[dict(id='answer-123',disposition='answered',text=message)]
        report=self.fixture.report(context);key=gap_keys(context)[0]
        report['panorama_dispositions'][key]=dict(disposition='dismissed',claim_key=None,
            reason='El dueño confirma el cierre previsto por reforma del local.',
            proof=dict(kind='owner',source='owner_message/answer-123',quote='La tienda cerró por reforma.',
                verified_fact='El dueño declara un cierre planificado por reforma.'))
        validate(report,context)
        schema=self.fixture.schema(context)
        self.assertNotIn(message,str(schema))
        wire=strict_tests.StrictProviderSchemaTests().capture('generate_analyst_review',context)
        validate_strict_schema(wire)
        proof=report['panorama_dispositions'][key]['proof']
        for field,value in (('quote','La tienda no cerró por reforma.'),('quote',' \n\t'),('source','another-message')):
            bad=deepcopy(report);bad['panorama_dispositions'][key]['proof'][field]=value
            with self.subTest(field=field,value=value),self.assertRaises(ValueError):validate(bad,context)
        self.assertEqual(owner_sources(context)['owner_message/answer-123'],message)


class ReviewFlagMatrixTests(unittest.TestCase):
    def test_research_continuity_recovery_and_large_evidence_in_wire(self):
        from test_model_strict_schemas import cases
        base=[(n,c) for n,m,c in cases() if m=='generate_research' and n.endswith(('-success','-expand'))]
        for name,original in base:
            for recovery in (False,True):
                context=deepcopy(original)
                context['budgets']['research_validation_recovery']=recovery
                context['observations'][0]['result']['metrics'].update({f'added_{i}':str(i) for i in range(1100)})
                context['owner_context']='Unidades registradas.\nNo he confirmado los importes.\t'
                with self.subTest(name=name,recovery=recovery):
                    validate_strict_schema(strict_tests.StrictProviderSchemaTests().capture('generate_research',context))

    def test_both_roles_all_option_combinations_and_large_contexts(self):
        frozen=frozen_fixture()
        flags=('owner_presentation','sales_panorama','review_loop_guard','review_context_budget',
               'review_stable_prefix','panorama_obligation_guard')
        captured=0
        for values in product((False,True),repeat=len(flags)):
            context=large_context()
            context['budgets'].update(zip(flags,values))
            context['owner_context']='Soy el dueño.\nLa tienda cerró por reforma.\r\nCompara canales\ty periodos.'
            if context['budgets']['sales_panorama']:
                from decision_room.panorama_presentation import compact
                context['sales_panorama']=compact(frozen,frozen['observations'])
                context['observations']+=deepcopy(frozen['observations'])
            # Over 1000 accumulated keys, and historical text exceeds 70000 tokens.
            context['observations'][0]['result']['metrics'].update({f'added_{i}':str(i) for i in range(1100)})
            for role in ('generate_analyst_review','generate_reviewer'):
                with self.subTest(flags=dict(zip(flags,values)),role=role):
                    validate_strict_schema(strict_tests.StrictProviderSchemaTests().capture(role,context))
                    captured+=1
        self.assertEqual(captured,128)
