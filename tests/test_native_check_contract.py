"""Adversarial checker results cannot claim another revision, quote or coverage."""
import json
import unittest
from decision_room.engine import blocks, check_contract as checks


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.projection=blocks.parse(json.dumps(dict(version=blocks.VERSION,titulo='T',bloques=[
            dict(tipo='prioridad',titulo='P',bloques=[dict(tipo='texto',contenido='Hay 5 unidades y 2 ventas.')])])).encode())
        self.priority=blocks.priorities(self.projection)[0]
        self.text=self.priority['text'];self.sha='a'*64

    def output(self, **changes):
        offset=self.text.index('5 unidades')
        item=dict(priority_id=self.priority['block_id'],quote='5 unidades',start=offset,end=offset+10,
                  status='confirmed',independent_value='5 unidades',method='Suma CSV de unidades.',message='')
        item.update(changes)
        return json.dumps(dict(version=checks.VERSION,revision_sha256=self.sha,items=[item],coverage_notes='')).encode()

    def test_missing_numbers_never_become_confirmed_and_leaf_location_is_exact(self):
        result=checks.parse(self.output(),self.projection,self.sha)
        self.assertEqual(result['coverage']['numeric_spans'],2)
        self.assertEqual(result['coverage']['addressed_spans'],1)
        self.assertEqual(result['items'][0]['block_id'],'b1-1')
        visible=checks.visible(result)
        self.assertEqual(len(visible['items']),1)
        self.assertEqual(visible['items'][0]['status'],'unverifiable')

    def test_foreign_hash_offset_duplicate_and_unlocated_confirmation_refused(self):
        for raw in [self.output(start=0),self.output(priority_id='b99'),self.output(start=None,end=None),self.output(method='')]:
            with self.subTest(raw=raw),self.assertRaises(checks.CheckError):checks.parse(raw,self.projection,self.sha)
        with self.assertRaises(checks.CheckError):checks.parse(self.output(),self.projection,'b'*64)
        value=json.loads(self.output());value['items']*=2
        with self.assertRaises(checks.CheckError):checks.parse(json.dumps(value).encode(),self.projection,self.sha)

    def test_unlocated_discrepancy_is_visible_on_priority_and_corrector_recalculates(self):
        result=checks.parse(self.output(status='discrepancy',quote='Cita imposible',start=None,end=None),self.projection,self.sha)
        self.assertEqual(result['items'][0]['block_id'],'b1')
        text=checks.correction(result)
        self.assertIn('Si tu cifra\nestaba mal, cámbiala',text)
        self.assertIn('si mantienes tu cifra, explica por qué',text)
        self.assertIn('Suma CSV',text)

    def test_hostile_text_and_oversized_json_refused(self):
        for raw in [self.output(message='\x00'),b'a'*(blocks.MAX_BYTES+1),self.output(independent_value=5),self.output(end=True)]:
            with self.subTest(raw=raw[:80]),self.assertRaises(checks.CheckError):checks.parse(raw,self.projection,self.sha)
