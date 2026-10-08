"""Occurrence evidence never lends its verification to an adjacent assertion."""
from copy import deepcopy
import hashlib
import json
import unittest
from unittest.mock import patch

from decision_room.reports import presentation_r0, presentation_r1
from decision_room.reports.verification_occurrences import build
from decision_room.reports.verification_contract import validate


class OccurrenceTests(unittest.TestCase):
    def raw(self, **extra):
        return json.dumps({'schema_version':1,'title':'Revisión',
            'summary':'Una hipótesis sobre Norte: {{e:q}}; repetición libre 15.0.',
            'numbers':[{'key':'q','execution_id':'fixture','metric':'total','decimals':1,'unit':'euros'}],
            'findings':[{'key':'revisar','statement':'Antes: 7. Después: {{e:q}}. Aun así, 15.0.'}], **extra},ensure_ascii=False).encode()

    def resolve(self, ref):
        return {'origin':'deterministic_calculation','status':'verified_in_scope','value':'15','original_value':'15',
                'display':{'label':'Suma registrada','unit':'unidades','scope':'Canal «Sur»; periodo 2025-01-01 a 2025-01-31.',
                           'limitation':'No certifica causas ni cobertura.',
                           'operands':[{'label':'Base de comparación','value':'10','unit':'unidades'}]}}

    def test_scoped_segments_keep_context_caution_in_support_and_prose_unverified(self):
        raw=self.raw(); doc,ledger=build(raw,resolver=self.resolve)
        self.assertIn('Suma registrada: 15.0 unidades. Canal «Sur»; periodo 2025-01-01 a 2025-01-31.',doc['summary'])
        self.assertNotIn('No certifica',doc['summary'])
        self.assertNotIn('Base de comparación',doc['summary'])
        self.assertIn('No certifica',doc['facts'][0]['text'])
        self.assertIn('Base de comparación: 10 unidades.',doc['facts'][0]['text'])
        self.assertEqual(len(doc['facts']),1);self.assertEqual(len(doc['findings'][0]['facts']),1)
        for path in ['/summary','/findings/0/statement']:
            same=[f for f in ledger['figures'] if f['path']==path and f['text']=='15.0']
            self.assertEqual([f['verified'] for f in same],[True,False])
            self.assertEqual(same[0]['unit'],'unidades')
            self.assertTrue(all(not f['verified'] for f in ledger['figures'] if f['path']==path and f['text'].startswith('2025')))
        self.assertEqual(ledger['draft_sha256'],hashlib.sha256(raw).hexdigest())
        validate(ledger,doc,raw)

    def test_repeated_tokens_unicode_and_old_n_references_have_separate_occurrences(self):
        doc,ledger=build(self.raw(summary='Á 🐦 {{e:q}} + {{e:q}}; valor suelto {{n:q}}'),resolver=self.resolve)
        figures=[f for f in ledger['figures'] if f['path']=='/summary' and f['text']=='15.0']
        self.assertEqual([f['verified'] for f in figures],[True,True,False])
        self.assertEqual(len({f['id'] for f in figures}),3)
        self.assertEqual(len(doc['facts']),1)

    def test_corrected_occurrence_preserves_before_value_and_recipe_unit(self):
        def resolve(ref):return {**self.resolve(ref),'status':'corrected_in_scope','original_value':'999'}
        doc,ledger=build(self.raw(),resolver=resolve)
        checked=[f for f in ledger['figures'] if f['path']=='/summary' and f['verified']]
        self.assertEqual([(f['status'],f['corrected_from']) for f in checked],[('corrected','999')])
        self.assertIn('15.0 unidades',doc['summary'])

    def test_unknown_failed_and_duplicate_references_cannot_certify(self):
        for resolve in [lambda _:None,lambda r:{**self.resolve(r),'origin':'agent_calculation'}]:
            doc,ledger=build(self.raw(),resolver=resolve)
            self.assertFalse(any(f['verified'] for f in ledger['figures']))
            self.assertIn('sin ámbito comprobado',doc['summary'])
            self.assertNotIn('{{e:',doc['summary'])
        refs=[{'key':'q','execution_id':str(i),'metric':'total'} for i in range(2)]
        doc,ledger=build(self.raw(numbers=refs),resolver=self.resolve)
        self.assertFalse(any(f['verified'] for f in ledger['figures']))

    def test_source_template_text_is_never_recursively_expanded(self):
        def resolve(ref):
            value=self.resolve(ref);value['display']['scope']='Canal «{{e:q}}» y columna «{{n:q}}».';return value
        doc,ledger=build(self.raw(),resolver=resolve)
        self.assertIn('Canal «{{e:q}}» y columna «{{n:q}}»',doc['summary'])
        self.assertEqual(sum(f['verified'] for f in ledger['figures'] if f['path']=='/summary'),1)

    def test_both_presentations_share_fields_and_maps_include_inline_offsets(self):
        raw=self.raw();doc,ledger=build(raw,resolver=self.resolve)
        before=deepcopy((doc,ledger))
        marked,plain,mapping=presentation_r1.render(doc,ledger,raw)
        self.assertEqual((doc,ledger),before)
        presentation_r0.check_invariants(doc,ledger,raw,marked,mapping)
        text=mapping['fields']['/summary']['text']
        figures={f['id']:f for f in ledger['figures']}
        checked=[o for o in mapping['fields']['/summary']['occurrences'] if figures[o['id']]['verified']]
        self.assertEqual(len(checked),1)
        self.assertEqual(text[checked[0]['span']['start']:checked[0]['span']['end']],'15,0')
        self.assertIn('No certifica causas ni cobertura.',plain)
        self.assertNotIn('data-verified=',plain)

    def test_support_limit_and_expansion_limit_are_reported_without_fake_certification(self):
        raw=self.raw(facts=[f'other{i}' for i in range(32)],findings=[])
        doc,ledger=build(raw,resolver=self.resolve)
        self.assertIn('referencia sin soporte comprobado',doc['summary'])
        self.assertIn('occurrence_support_limit',ledger['issues'])
        self.assertFalse(any(f['verified'] for f in ledger['figures'] if f['path']=='/summary'))
        with patch('decision_room.reports.verification_occurrences.MAX_SEGMENTS',0):
            doc,ledger=build(self.raw(),resolver=self.resolve)
        self.assertIn('occurrence_expansion_limit',ledger['issues'])
        self.assertFalse(any(f['verified'] for f in ledger['figures'] if f['path']=='/summary'))

    def test_bad_shape_and_plain_documents_keep_existing_behavior(self):
        from decision_room.reports import verification
        for raw in [b'{{e:q}} not JSON',self.raw(summary='Total {{n:q}}',findings=[])]:
            self.assertEqual(build(raw,resolver=self.resolve),verification.build(raw,resolver=self.resolve))

    def test_existing_facts_and_generated_scopes_keep_order_and_values(self):
        raw=self.raw(facts=['q'],findings=[{'key':'revisar','statement':'{{e:q}}','facts':['q']}])
        doc,ledger=build(raw,resolver=self.resolve)
        self.assertEqual([f['number_key'] for f in doc['facts']],['q'])
        self.assertEqual([f['number_key'] for f in doc['findings'][0]['facts']],['q'])
        self.assertEqual([f['key'] for f in doc['findings']],['revisar'])

    def test_nonfinite_reference_does_not_lose_the_report(self):
        raw=self.raw(numbers=[{'key':'q','execution_id':'fixture','metric':'total','decimals':1}])
        raw=raw.replace(b'"decimals": 1',b'"decimals": 1e999')
        doc,ledger=build(raw,resolver=self.resolve)
        validate(ledger,doc,raw)
        self.assertEqual(doc['title'],'Revisión')
        self.assertFalse(any(f['verified'] for f in ledger['figures']))
