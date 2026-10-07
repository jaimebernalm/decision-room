"""Actionable bounded sandbox diagnostics without leaking host exceptions."""
import unittest

from decision_room.engine import admission, gateway
from tests import test_engine_panorama as fixtures


class DiagnosticTests(unittest.TestCase):
    def test_safe_known_diagnostic_is_identical_on_result_pagination(self):
        record={'id':'fixture','status':'invalid_output','result':None,'issue':'Metrics must contain named scalar values.'}
        page=gateway.page_result(record)
        self.assertEqual(page['diagnostic']['code'],'non_scalar_metric')
        self.assertIn('new request_key',page['diagnostic']['retry'])
        self.assertEqual(gateway.page_result(record,1)['diagnostic'],page['diagnostic'])

    def test_private_exception_and_missing_metric_names_are_not_echoed(self):
        for issue in ['ValueError: private storage location and credential',
                      'Every metric must have evidence. Missing: private customer label',
                      'Metric text too long. private suffix']:
            page=gateway.page_result({'id':'fixture','status':'invalid_output','result':None,'issue':issue})
            self.assertNotIn('private',str(page))
            self.assertLess(len(admission.canonical(page)),2048)
        self.assertNotIn('diagnostic',gateway.page_result({'id':'fixture','status':'completed','result':{'answer':3}}))

    def test_sandbox_exception_type_supplies_advice_without_query_or_traceback(self):
        record={'id':'fixture','status':'failed','result':None,'issue':None,
                'logs':{'stderr':'Traceback private path\n_duckdb.BinderException: private column value and query'}}
        page=gateway.page_result(record)
        self.assertEqual(page['diagnostic']['code'],'python_binderexception')
        self.assertIn('cast explicitly',page['diagnostic']['message'])
        self.assertNotIn('private',str(page))


class CalculationFeedbackTests(unittest.TestCase):
    setUpClass=classmethod(fixtures.PanoramaTests.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.PanoramaTests.tearDownClass.__func__)
    setUp=fixtures.PanoramaTests.setUp
    create=fixtures.PanoramaTests.create
    tool=fixtures.PanoramaTests.tool

    def test_real_invalid_output_can_be_corrected_with_new_key(self):
        programs=[('print("not a result")','missing_result'),
                  ('from dr_runtime import write_result\nwrite_result({"rows":[1,2]},evidence=[{"metric":"rows","tables":["data"],"operation":"fixture"}])','non_scalar_metric'),
                  ('from dr_runtime import write_result\nwrite_result({"rows":"x"*1001},evidence=[{"metric":"rows","tables":["data"],"operation":"fixture"}])','metric_text_too_long')]
        for i,(code,expected) in enumerate(programs):
            result=self.tool('consulta',{'code':code,'tables':{'data':str(self.table)},'request_key':f'invalid-{i}'})
            self.assertEqual(result['status'],'invalid_output')
            self.assertEqual(result['diagnostic']['code'],expected)
            replay=self.tool('resultado',{'execution_id':result['execution_id']})
            self.assertEqual(result['diagnostic'],replay['diagnostic'])
        code='''from dr_runtime import connect, write_result
with connect() as db:
    amount = db.execute('SELECT SUM(CAST(quantity AS DECIMAL(20,8))) FROM data').fetchone()[0]
write_result({'quantity':str(amount)},evidence=[{'metric':'quantity','tables':['data'],'operation':'SUM(quantity) over all rows'}])
'''
        result=self.tool('consulta',{'code':code,'tables':{'data':str(self.table)},'request_key':'corrected'})
        self.assertEqual(result['status'],'completed')
        self.assertNotIn('diagnostic',result)
        value=next(r['value'] for r in result['rows'] if r['path']=='/metrics/quantity')
        self.assertEqual(float(value),15)
