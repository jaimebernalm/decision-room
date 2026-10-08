"""Read-only exploration output remains bounded, scoped and uncertified."""
import unittest
from uuid import uuid4

from decision_room.engine import exploration, admission, gateway
from tests import test_engine_panorama as fixtures


class TextPageTests(unittest.TestCase):
    def test_escaped_unicode_pages_reconstruct_retained_text(self):
        text=('🧾\\\"\n'*5000)+'END'
        cursor=0;parts=[]
        while True:
            p=exploration.text_page(text,cursor,tool='salida',arguments={'execution_id':'fixture'},identity={})
            self.assertLess(len(admission.canonical(p)),24000)
            parts.append(p['text'])
            if p['next_cursor'] is None:break
            self.assertGreater(p['next_cursor'],cursor);cursor=p['next_cursor']
        self.assertEqual(''.join(parts),text)
        for cursor in (-1,True,len(text)+1):
            with self.assertRaises(ValueError):exploration.text_page(text,cursor,tool='x',arguments={},identity={})

    def test_retention_loss_is_distinct_from_more_pages_and_never_certified(self):
        p=exploration.stdout_page({'id':'x','status':'invalid_output','logs':{'stdout':'candidate','stdout_truncated':True}})
        self.assertTrue(p['retention_truncated']);self.assertFalse(p['truncated'])
        self.assertIsNone(p['next_call']);self.assertEqual(p['verification'],'unverified')


class ExplorationTests(unittest.TestCase):
    setUpClass=classmethod(fixtures.PanoramaTests.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.PanoramaTests.tearDownClass.__func__)
    setUp=fixtures.PanoramaTests.setUp
    create=fixtures.PanoramaTests.create
    tool=fixtures.PanoramaTests.tool

    def test_printed_table_reads_scoped_input_and_is_replayable_not_certified(self):
        args={'code':"from dr_runtime import connect\nwith connect() as db:\n print(db.execute('SELECT channel, SUM(CAST(quantity AS INTEGER)) FROM data GROUP BY channel').fetchall())",'tables':{'data':str(self.table)},'request_key':'printed'}
        first=self.tool('explorar',args)
        self.assertIn('Local',first['text']);self.assertIn('15',first['text'])
        self.assertEqual(first['verification'],'unverified')
        self.assertEqual(first['status'],'completed')
        self.assertEqual(first,self.tool('explorar',args))
        self.assertEqual(first,self.tool('salida',{'execution_id':first['execution_id']}))
        other,token=self.create()
        with self.assertRaises(admission.Denied):
            gateway.dispatch(self.config,other,token,{'jsonrpc':'2.0','id':1,'method':'tools/call',
                'params':{'name':'salida','arguments':{'execution_id':first['execution_id']}}})
        conflict=gateway.dispatch(self.config,self.run,self.token,{'jsonrpc':'2.0','id':1,'method':'tools/call',
            'params':{'name':'consulta','arguments':args}})
        self.assertTrue(conflict['result']['isError'])

    def test_readable_panorama_retains_signals_and_exact_reference_ids(self):
        args={'table_id':str(self.table),'request_key':'readable'}
        page=self.tool('panorama_lectura',args);parts=[page['text']]
        while page['next_call']:
            call=page['next_call'];page=self.tool(call['name'],call['arguments']);parts.append(page['text'])
        text=''.join(parts)
        self.assertIn('Tabla y periodos',text);self.assertIn('Local',text)
        self.assertIn('Referencias para numbers / facts',text)
        original=self.tool('panorama',args)
        for ident in original['observation_ids']:self.assertIn(ident,text)
        self.assertIn('Cambio entre periodos',text)
