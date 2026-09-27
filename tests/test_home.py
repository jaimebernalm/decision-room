"""Dashboard persistence, evidence withdrawal and bounded model proposals."""
import copy
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

from decision_room.web import home
from decision_room.web.errors import WebError
import test_web


class HomeTests(unittest.TestCase):
    setUpClass = classmethod(test_web.WebTests.setUpClass.__func__)
    tearDownClass = classmethod(test_web.WebTests.tearDownClass.__func__)
    setUp = test_web.WebTests.setUp
    create, answer, complete, http = test_web.WebTests.create, test_web.WebTests.answer, test_web.WebTests.complete, test_web.WebTests.http

    def catalogue(self):
        items = [dict(id=str(i), kind='metric', title=f'Metric {i}', content={'unit': 'EUR'}, source={'period': '2025', 'coverage': 'Sample'}) for i in range(11)]
        return dict(items=items, sources=[], context={'name': 'Test shop'}, fingerprint='v1', activity=[], limited=False)

    def body(self, view, **changes):
        return dict(business_id=view['business_id'], revision=view['revision'], fingerprint=view['fingerprint'],
                    selected=view['selected'], pinned=view['pinned'], **changes)

    def test_only_current_reviewed_evidence_is_available(self):
        job = self.complete()
        data = home.view(self.ws)
        self.assertTrue(data['items'])
        self.assertEqual(data['sources'][0]['job_id'], str(job))
        self.assertEqual(home.view(self.ws)['fingerprint'], data['fingerprint'])
        saved = home.save(self.ws, self.body(data) | {'pinned': [data['selected'][0]]})
        listing, original_row = self.ws.listing(), self.ws.row
        fake_ids = [uuid4() for _ in range(20)]
        def row(identifier):
            return {'review_id': None, 'session_id': None} if identifier in fake_ids else original_row(identifier)
        with patch.object(self.ws, 'listing', return_value=[{'id': id, 'status': 'completed'} for id in fake_ids] + listing), \
                patch.object(self.ws, 'row', side_effect=row), patch.object(self.ws, 'daily_activity', return_value=[]):
            retained = home.view(self.ws)
            self.assertEqual(retained['pinned'], saved['pinned'])
            self.assertEqual(retained['sources'][0]['job_id'], str(job))
        with patch.object(self.ws, 'review_state', return_value={'publishable': False}):
            withdrawn = home.view(self.ws)
            self.assertEqual(withdrawn['items'], [])
            self.assertEqual(withdrawn['selected'], [])
            self.assertEqual(withdrawn['unavailable'], len(saved['selected']))

    def test_preferences_are_persistent_scoped_and_reject_stale_or_invalid_values(self):
        with patch.object(home, 'collect', return_value=self.catalogue()):
            data = home.view(self.ws)
            body = self.body(data)
            body.update(selected=['0', '1'], pinned=['0'])
            saved = home.save(self.ws, body)
            self.assertEqual(home.load(self.ws)['layout']['selected'], ['0', '1'])
            self.assertEqual(saved['hidden'], ['2', '3'])
            self.assertEqual(saved['pinned'], ['0'])
            for invalid in [body, self.body(saved, invalid=True) | {'selected': ['alien']},
                            self.body(saved) | {'selected': ['1']},
                            self.body(saved) | {'selected': [str(i) for i in range(11)]},
                            self.body(saved) | {'business_id': str(uuid4())},
                            self.body(saved) | {'fingerprint': 'old'},
                            self.body(saved) | {'selected': [{}]}]:
                with self.assertRaises(WebError):
                    home.save(self.ws, invalid)
            self.assertEqual(home.load(self.ws)['revision'], saved['revision'])
            expanded = home.save(self.ws, self.body(saved) | {'selected': [str(i) for i in range(10)]})
            self.assertEqual(len(expanded['selected']), 10)
            self.assertEqual(expanded['pinned'], ['0'])
            other = self.ws.save_business({'request_key': str(uuid4()), 'name': 'Other shop', 'description': 'Other context', 'expected_active_id': data['business_id']})
            self.assertNotEqual(str(other['id']), saved['business_id'])
            self.assertEqual(home.load(self.ws)['layout'], {})

    def test_proposal_requires_explicit_apply_and_preserves_pins_and_hidden(self):
        with patch.object(home, 'collect', return_value=self.catalogue()):
            data = home.view(self.ws)
            body = self.body(data) | {'selected': ['0', '1'], 'pinned': ['0']}
            data = home.save(self.ws, body)
            model = Mock()
            model.generate_dashboard.return_value = ({'picks': [{'id': '0', 'reason': 'Fijado por ti.'}, {'id': '4', 'reason': 'Útil para tu objetivo.'}]}, {})
            self.ws.model_factory = Mock(return_value=model)
            proposed = home.suggest(self.ws, {'business_id': data['business_id']})
            self.assertEqual(proposed['selected'], data['selected'])
            self.assertEqual(home.suggest(self.ws, {'business_id': data['business_id']}), proposed)
            self.assertEqual(model.generate_dashboard.call_count, 1)
            context = model.generate_dashboard.call_args.args[0]
            self.assertEqual(context['pinned'], ['0'])
            self.assertIn('2', context['hidden'])
            applied = home.save(self.ws, self.body(proposed, apply_proposal=True))
            self.assertEqual(applied['selected'], ['0', '4'])
            self.assertEqual(applied['pinned'], ['0'])
            self.assertEqual(applied['selection_origin'], 'agent')
            self.assertIsNone(applied['proposal'])

    def test_bad_model_selection_cannot_replace_dashboard(self):
        with patch.object(home, 'collect', return_value=self.catalogue()):
            data = home.view(self.ws)
            data = home.save(self.ws, self.body(data) | {'selected': ['0'], 'pinned': ['0']})
            for ids in [['unknown'], ['4'], ['0', '1'], ['0', '0'], [str(i) for i in range(11)]]:
                model = Mock()
                model.generate_dashboard.return_value = ({'picks': [{'id': id, 'reason': 'Reason'} for id in ids]}, {})
                self.ws.model_factory = lambda _: model
                with self.assertRaises(WebError):
                    home.suggest(self.ws, {'business_id': data['business_id']})
                self.assertEqual(home.view(self.ws)['selected'], ['0'])
                self.assertIsNone(home.load(self.ws)['proposal'])

    def test_data_change_during_inference_or_before_apply_rejects_proposal(self):
        initial = self.catalogue()
        changed = copy.deepcopy(initial) | {'fingerprint': 'v2'}
        model = Mock()
        model.generate_dashboard.return_value = ({'picks': [{'id': '0', 'reason': 'Relevant'}]}, {})
        self.ws.model_factory = lambda _: model
        with patch.object(home, 'collect', side_effect=[initial, changed]):
            with self.assertRaises(WebError):
                home.suggest(self.ws, {'business_id': str(self.business['id'])})
        self.assertIsNone(home.load(self.ws)['proposal'])
        with patch.object(home, 'collect', return_value=initial):
            proposed = home.suggest(self.ws, {'business_id': str(self.business['id'])})
        with patch.object(home, 'collect', return_value=changed):
            self.assertIsNone(home.view(self.ws)['proposal'])
            with self.assertRaises(WebError):
                home.save(self.ws, self.body(proposed, apply_proposal=True))

    def test_owner_edit_during_inference_wins(self):
        with patch.object(home, 'collect', return_value=self.catalogue()):
            data = home.view(self.ws)
            def generate(_context):
                home.save(self.ws, self.body(data) | {'selected': ['1'], 'pinned': ['1']})
                return {'picks': [{'id': '0', 'reason': 'Relevant'}]}, {}
            model = Mock()
            model.generate_dashboard.side_effect = generate
            self.ws.model_factory = lambda _: model
            with self.assertRaises(WebError):
                home.suggest(self.ws, {'business_id': data['business_id']})
            self.assertEqual(home.view(self.ws)['selected'], ['1'])
            self.assertIsNone(home.load(self.ws)['proposal'])

    def test_http_auth_and_valid_preferences_roundtrip(self):
        client, _ = self.http()
        self.assertEqual(client.get('/api/home').status_code, 401)
        client.post('/api/login', json={'token': 'test-local-access'})
        data = client.get('/api/home').json()
        self.assertEqual(data['items'], [])
        response = client.post('/api/home/preferences', json=self.body(data))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['revision'], 1)
        self.assertEqual(client.post('/api/home/suggest', json={'business_id': data['business_id']}).status_code, 409)
