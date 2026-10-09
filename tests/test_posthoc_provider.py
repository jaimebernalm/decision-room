import json
from pathlib import Path
import tempfile
import unittest
import sqlite3
from unittest.mock import patch

import httpx
from decision_room.reports.posthoc.provider import Budget, BudgetStop, ReservedTransport


class BudgetTests(unittest.TestCase):
    def test_unknown_cost_is_durable_and_cannot_be_replayed(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'budget.sqlite';budget=Budget(path)
            budget.reserve('a','r','0.01')
            with self.assertRaises(BudgetStop):budget.settle('a',{'status':'incomplete','cost':None})
            with self.assertRaises(BudgetStop):Budget(path).reserve('b','r','0.01')
            self.assertEqual(Budget(path).inspect()['unresolved'],1)
            with self.assertRaises(BudgetStop):budget.settle('a',{'status':'estimated','cost':'0'})

    def test_global_and_per_report_ceilings(self):
        with tempfile.TemporaryDirectory() as folder:
            budget=Budget(Path(folder)/'b',limit='.10',report_limit='.06')
            budget.reserve('a','r','.05');budget.settle('a',{'status':'estimated','cost':'.05'})
            with self.assertRaises(BudgetStop):budget.reserve('b','r','.02')
            budget.reserve('c','s','.05');budget.settle('c',{'status':'estimated','cost':'.05'})
            with self.assertRaises(BudgetStop):budget.reserve('d','t','.01')

    def test_budget_operations_close_database_handles_without_gc(self):
        real_connect=sqlite3.connect;opened=[]
        def connect(*args,**kwargs):
            db=real_connect(*args,**kwargs);opened.append(db);return db
        with tempfile.TemporaryDirectory() as folder:
            with patch('decision_room.reports.posthoc.provider.sqlite3.connect',side_effect=connect):
                budget=Budget(Path(folder)/'b');budget.reserve('a','r','.01')
                budget.settle('a',{'status':'estimated','cost':'.005'});budget.inspect()
            self.assertEqual(len(opened),4)
            for db in opened:
                with self.assertRaises(sqlite3.ProgrammingError):db.execute('SELECT 1')

    def test_generation_is_not_sent_until_cost_reserved(self):
        requests=[]
        def handler(request):
            requests.append(request.url.path)
            if request.url.path.endswith('input_tokens'):return httpx.Response(200,json={'input_tokens':1000})
            self.assertEqual(budget.inspect()['unresolved'],1)
            return httpx.Response(200,json={'status':'completed'})
        with tempfile.TemporaryDirectory() as folder:
            budget=Budget(Path(folder)/'b')
            transport=ReservedTransport(budget,'a','r',httpx.MockTransport(handler))
            with httpx.Client(transport=transport) as client:
                client.post('https://api.openai.com/v1/responses/input_tokens',json={})
                client.post('https://api.openai.com/v1/responses',json={'model':'gpt-6-luna','max_output_tokens':8000})
            self.assertEqual(requests,['/v1/responses/input_tokens','/v1/responses'])
            self.assertTrue(transport.reserved)
            self.assertEqual(budget.inspect()['calls'][0]['reservation'],'0.004125')

    def test_guard_denial_never_calls_generation_transport(self):
        requests=[]
        def handler(request):
            requests.append(request.url.path);return httpx.Response(200,json={'input_tokens':1000})
        with tempfile.TemporaryDirectory() as folder:
            budget=Budget(Path(folder)/'b',limit='.001',report_limit='.001')
            with httpx.Client(transport=ReservedTransport(budget,'a','r',httpx.MockTransport(handler))) as client:
                client.post('https://api.openai.com/v1/responses/input_tokens',json={})
                with self.assertRaises(BudgetStop):client.post('https://api.openai.com/v1/responses',json={'model':'gpt-6-luna','max_output_tokens':8000})
            self.assertEqual(requests,['/v1/responses/input_tokens'])

if __name__=='__main__':unittest.main()
