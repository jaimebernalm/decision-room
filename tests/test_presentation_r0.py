"""Offline R0 preserves evidence and rejects altered presentation attestations."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from decision_room.reports.verification import build
from decision_room.reports import presentation_r0 as r0


def index_texts(html):
    index=r0.TextIndex();index.feed(html);return index.texts


class PresentationR0Tests(unittest.TestCase):
    def fixture(self):
        raw=json.dumps({'schema_version':1,'title':'Lectura <script>mal</script>',
            'summary':'🧾 42 % y 42 %. Fecha 2025-01-01; código P01; tamaño 1 kg.',
            'scope':'Periodo observado; no garantiza cobertura.',
            'limitations':'Una ausencia no prueba cero.',
            'findings':[{'key':'one','title':'Primera revisión','statement':'La cifra libre es 1234.50.',
                         'interpretation':'Sin causa demostrada.','next_step':'Contrastar pedidos.', 'facts':['q','missing']},
                        {'key':'two','title':'Segunda revisión','facts':['q']}],
            'numbers':[{'key':'q','execution_id':'public-fixture','metric':'total','decimals':2}],
            'charts':[{'key':'c','kind':'bar','title':'Comparación','recommendation_id':'one',
                'series':[{'key':'s','label':'Unidades','points':[{'label':'Anterior','number_key':'q'},
                                                             {'label':'Actual','number_key':'q'}]}]}]}).encode()
        def resolve(ref):
            return {'status':'verified_in_scope','origin':'deterministic_calculation','value':'1234.5',
                    'display':{'label':'Cantidad','scope':'Canal de referencia; 2025-01-01 a 2025-01-31.',
                               'unit':'unidades','limitation':'No acredita causa.'}}
        doc,ledger=build(raw,resolver=resolve)
        return raw,doc,ledger

    def test_complete_fields_states_offsets_and_inputs_unchanged(self):
        raw,doc,ledger=self.fixture();before=deepcopy((doc,ledger))
        html,mapping=r0.render(doc,ledger,raw)
        self.assertEqual((doc,ledger),before)
        self.assertTrue(r0.check_invariants(doc,ledger,raw,html,mapping)['passed'])
        self.assertEqual(mapping['priority_order'],['one','two'])
        self.assertIn('1\u202f234,50',html)
        self.assertIn('La cifra libre es 1234.50.',' '.join(index_texts(html).values()))
        self.assertIn('Fecha 2025-01-01; código P01; tamaño 1 kg.',' '.join(index_texts(html).values()))
        self.assertNotIn('<script>',html)
        self.assertNotIn('<details',html)
        self.assertNotIn('{{n:missing}}',html)
        self.assertIn('No disponible',html)
        self.assertIn('{{n:missing}}',json.dumps(mapping))
        self.assertEqual(len({f['id'] for f in mapping['figures']}),len(ledger['figures']))
        self.assertLess(html.index('Comparación</span>'),html.index('Segunda revisión</span>'))

    def test_repeated_figures_keep_separate_ids_even_in_identical_facts(self):
        raw,doc,ledger=self.fixture();html,mapping=r0.render(doc,ledger,raw)
        repeated=[f for f in mapping['figures'] if f['path']=='/summary' and f['text'].startswith('42')]
        self.assertEqual(len(repeated),2)
        self.assertNotEqual(repeated[0]['id'],repeated[1]['id'])
        for f in ledger['figures']:
            self.assertEqual(html.count('data-figure="'+f['id']+'"'),1)

    def test_changed_text_status_map_source_or_priority_is_rejected(self):
        raw,doc,ledger=self.fixture();html,mapping=r0.render(doc,ledger,raw)
        changes=[html.replace('Contrastar pedidos.','Comprar ahora.'),
                 html.replace('data-status="unverified"','data-status="verified"',1),
                 html.replace('data-verified="false"','data-verified="true"',1)]
        for changed in changes:
            with self.subTest(changed=sha256(changed.encode()).hexdigest()), self.assertRaises(ValueError):
                r0.check_invariants(doc,ledger,raw,changed,mapping)
        for kind in ('priority','state','field','offset','source'):
            bad=deepcopy(mapping)
            if kind=='priority': bad['priority_order'].reverse()
            elif kind=='state': bad['figures'][0]['verified']=True
            elif kind=='field': del bad['fields']['/scope']
            elif kind=='offset': bad['fields']['/summary']['destinations'][-1]['occurrences'][0]['span']['start']+=1
            else: bad['source_raw_sha256']='wrong'
            with self.subTest(kind=kind),self.assertRaises(ValueError):r0.check_invariants(doc,ledger,raw,html,bad)

    def test_correction_does_not_approve_free_prose(self):
        raw=json.dumps({'schema_version':1,'summary':'{{n:q}}','findings':[],
            'numbers':[{'key':'q','execution_id':'fixture','metric':'n','unit':'units'}]}).encode()
        doc,ledger=build(raw,resolver=lambda _:{'value':'12','original_value':'20',
            'status':'corrected_in_scope','origin':'deterministic_calculation'})
        html,mapping=r0.render(doc,ledger,raw)
        self.assertIn('ámbito no verificado',html)
        self.assertFalse(mapping['figures'][0]['verified'])
        self.assertEqual(mapping['figures'][0]['corrected_from'],'20')

    def test_missing_chart_value_preserves_table_without_invented_geometry(self):
        raw=json.dumps({'schema_version':1,'title':'Sin dato','findings':[],
            'charts':[{'key':'c','kind':'bar','title':'Pendiente','series':[{'key':'s','label':'Serie',
                'points':[{'label':'A','number_key':'x'}]}]}]}).encode()
        doc,ledger=build(raw);html,mapping=r0.render(doc,ledger,raw)
        self.assertNotIn('<svg',html);self.assertIn('No disponible',html)
        self.assertTrue(all(f['value'] is None for f in mapping['figures']))

    def test_incomplete_occurrence_map_is_rejected(self):
        raw,doc,ledger=self.fixture();html,mapping=r0.render(doc,ledger,raw)
        bad=deepcopy(mapping);bad['fields']['/summary']['destinations'][-1]['occurrences']=[]
        with self.assertRaises(ValueError):r0.check_invariants(doc,ledger,raw,html,bad)

    def test_explicit_chart_label_names_move_before_codes_with_offsets(self):
        raw=json.dumps({'schema_version':1,'title':'Etiquetas','findings':[],
            'charts':[{'key':'c','kind':'table','title':'Detalle','series':[{'key':'s','label':'MA — Canal',
                'points':[{'label':'P01 — Producto 1 kg','number_key':'q'}]}]}]}).encode()
        doc,ledger=build(raw);html,mapping=r0.render(doc,ledger,raw)
        field=mapping['fields']['/charts/0/series/0/points/0/label']
        self.assertEqual(field['text'],'Producto 1 kg (P01)')
        for o in field['occurrences']:
            self.assertEqual(field['text'][o['span']['start']:o['span']['end']],o['text'])
        self.assertTrue(r0.check_invariants(doc,ledger,raw,html,mapping)['passed'])

    def test_body_fields_are_not_duplicated_in_appendix(self):
        raw,doc,ledger=self.fixture();html,mapping=r0.render(doc,ledger,raw)
        for path,field in mapping['fields'].items():
            full=[d for d in field['destinations'] if d['full']]
            if '/facts/' in path:
                self.assertEqual(len(full),1)
                self.assertTrue(full[0]['id'].startswith('annex-'))
            else:
                self.assertFalse(any(d['id'].startswith('annex-') for d in full))
        self.assertEqual(html.count('Contrastar pedidos.'),1)

    def test_repeated_chart_labels_keep_state_at_each_visible_destination(self):
        raw=json.dumps({'schema_version':1,'title':'Tabla','findings':[],
            'charts':[{'key':'c','kind':'table','title':'Detalle','series':[{'key':'s','label':'Periodo 2025',
                'points':[{'label':'A','number_key':'q'},{'label':'B','number_key':'q'}]}]}]}).encode()
        doc,ledger=build(raw);html,mapping=r0.render(doc,ledger,raw)
        f=next(f for f in ledger['figures'] if f['path']=='/charts/0/series/0/label')
        self.assertEqual(html.count('data-figure="'+f['id']+'"'),2)
        changed=html.replace('data-figure="'+f['id']+'"','data-other="'+f['id']+'"',1)
        with self.assertRaises(ValueError):r0.check_invariants(doc,ledger,raw,changed,mapping)

    def test_mark_shifted_onto_neighbor_is_rejected(self):
        raw,doc,ledger=self.fixture();html,mapping=r0.render(doc,ledger,raw)
        changed=html.replace('>42 %</span> y', '>42 % y</span>',1)
        self.assertNotEqual(changed,html)
        with self.assertRaises(ValueError):r0.check_invariants(doc,ledger,raw,changed,mapping)

    def test_pilot_audit_copy_has_same_fields_without_state_marks(self):
        from decision_room.reports.presentation_r1 import render
        raw,doc,ledger=self.fixture();marked,plain,mapping=render(doc,ledger,raw)
        self.assertEqual(index_texts(marked),index_texts(plain))
        self.assertNotIn('class="state ',plain)
        self.assertNotIn('data-verified=',plain)
        self.assertNotIn('class="legend',plain)
        self.assertIn('class="state ',marked)
        self.assertEqual(marked,r0.render(doc,ledger,raw)[0])

    def test_export_attests_exact_output_bytes_and_refuses_overwrite(self):
        raw,doc,ledger=self.fixture()
        with TemporaryDirectory() as temp:
            root=Path(temp);source=root/'source';source.mkdir()
            for name,contents in {'draft.raw':raw,'draft.verified.json':json.dumps(doc).encode(),
                                  'verification.json':json.dumps(ledger).encode(),'informe.html':b'<p>frozen</p>'}.items():
                (source/name).write_bytes(contents)
            manifest=r0.export({'sample-1':source},root/'out')
            checks=json.loads((root/'out/sample-1.checks.json').read_text())
            self.assertEqual(checks['id'],'sample-1');self.assertTrue(checks['invariants_passed'])
            for name,digest in manifest['reports']['sample-1']['outputs'].items():
                self.assertEqual(digest,sha256((root/'out'/name).read_bytes()).hexdigest())
            with self.assertRaises(ValueError):r0.export({'sample-1':source},root/'out')
            ledger['draft_sha256']='bad';(source/'verification.json').write_text(json.dumps(ledger))
            with self.assertRaises(ValueError):r0.export({'sample-1':source},root/'invalid')
            self.assertFalse((root/'invalid').exists())


if __name__=='__main__':unittest.main()
