"""Offline provider receipts and catalogue arithmetic, including missing data."""
import json
import unittest

import httpx

from decision_room.database import connect
from decision_room.engine import admission, costs, proxy
from tests import test_engine_admission as fixtures


class CostTests(unittest.TestCase):
    def receipt(self, **extra):
        return costs.capture({'model': 'gpt-6-luna', 'service_tier': 'default',
            'usage': {'input_tokens': 1000, 'output_tokens': 100,
                      'input_tokens_details': {'cached_tokens': 200, 'cache_write_tokens': 300}}, **extra},
            requested_model='gpt-6-luna', requested_tier='default')

    def test_cache_write_read_and_context_rates_without_double_counting(self):
        receipt = self.receipt()
        self.assertEqual(costs.estimate(receipt)['cost'], '0.0001395')
        receipt.update(input=300000, output=64000, cache_read=0, cache_write=300000)
        self.assertEqual(costs.estimate(receipt)['cost'], '0.123')
        receipt['input'] = 272000; receipt['cache_write'] = 272000
        self.assertFalse(costs.estimate(receipt)['long_context'])

    def test_absence_or_unknown_tier_model_never_becomes_zero_cost(self):
        for changes in ({'effective_tier': None}, {'effective_tier': 'priority'}, {'effective_model': None},
                        {'cache_write': None}, {'cache_read': None}, {'cache_write': 9999}):
            self.assertIsNone(costs.estimate({**self.receipt(), **changes})['cost'])
        missing = self.receipt(usage={'input_tokens': 10, 'output_tokens': 1})
        self.assertIsNone(missing['cache_write'])
        self.assertIsNone(missing['cache_read'])
        summary = costs.aggregate([{'cost_catalog': costs.estimate(self.receipt())}, {'cost_catalog': costs.estimate(missing)}])
        self.assertIsNone(summary['cost']); self.assertEqual(summary['known_cost'], '0.0001395')
        self.assertEqual(summary['unpriced_calls'], 1)


class CostPersistenceTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.EngineTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.EngineTests.tearDownClass.__func__)
    setUp = fixtures.EngineTests.setUp

    def run_request(self, *, stream=False, disconnect=False, omit_write=False):
        run, token = admission.create_run(self.config, self.business, self.analysis, table_ids=[self.table],
            owner_context='Fixture', request_key='billing', model='gpt-6-luna')
        details = {'cached_tokens': 2}
        if not omit_write: details['cache_write_tokens'] = 3
        response = {'status': 'completed', 'model': 'gpt-6-luna', 'service_tier': 'default',
                    'usage': {'input_tokens': 10, 'output_tokens': 5, 'input_tokens_details': details}}
        def provider(request):
            if request.url.path.endswith('input_tokens'):
                return httpx.Response(200, json={'input_tokens': 10})
            if stream:
                data = ('data: ' + json.dumps({'type': 'response.completed', 'response': response}) + '\n\n').encode()
                return httpx.Response(200, headers={'content-type': 'text/event-stream'}, content=data)
            return httpx.Response(200, json=response)
        def write(data):
            if disconnect: raise BrokenPipeError()
        kwargs = dict(api_key='fixture-only', transport=httpx.MockTransport(provider),
                      send_headers=lambda *a: None, write=write)
        raw = admission.canonical({'model': 'gpt-6-luna', 'input': 'Fixture', 'stream': stream})
        if disconnect:
            with self.assertRaises(BrokenPipeError): proxy.forward(self.config, run, token, raw, **kwargs)
        else:
            proxy.forward(self.config, run, token, raw, **kwargs)
        return admission.inspect_run(self.config, self.business, run)

    def test_json_receipt_persists_tier_and_cache_counts(self):
        state = self.run_request(); call = state['model_calls'][0]
        self.assertEqual(call['billing']['effective_tier'], 'default')
        self.assertEqual(call['billing']['cache_write'], 3)
        self.assertEqual(call['billing']['cache_read'], 2)
        self.assertEqual(call['cost_catalog']['status'], 'estimated')
        self.assertNotIn('fixture-only', str(state))

    def test_terminal_sse_receipt_survives_downstream_disconnect(self):
        state = self.run_request(stream=True, disconnect=True); call = state['model_calls'][0]
        self.assertEqual(state['status'], 'aborted')
        self.assertEqual(call['usage']['output'], 5)
        self.assertEqual(call['cost_catalog']['status'], 'estimated')

    def test_missing_cache_write_stays_unpriced(self):
        state = self.run_request(omit_write=True)
        self.assertIsNone(state['model_calls'][0]['billing']['cache_write'])
        self.assertIsNone(state['model_calls'][0]['cost_catalog']['cost'])
