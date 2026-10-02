"""Persistent owner group layout, revision checks and business isolation."""
import copy
import unittest
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
from unittest.mock import patch

from decision_room.database import connect, migrate
from decision_room.memory import service as memory
from decision_room.web import dossier, dossier_layout
from decision_room.web.errors import WebError
import test_web


class DossierLayoutTests(unittest.TestCase):
    setUpClass = classmethod(test_web.WebTests.setUpClass.__func__)
    tearDownClass = classmethod(test_web.WebTests.tearDownClass.__func__)
    setUp = test_web.WebTests.setUp
    http = test_web.WebTests.http

    def body(self, layout=None, **changes):
        return {'business_id': str(self.ws.business_id()), **(layout or dossier.listing(self.ws)['layout']), **changes}

    def fact(self):
        return memory.change(self.config, self.ws.business_id(), action='declare', request_key=str(uuid4()),
                             content={'kind': 'context', 'statement': 'School supplies.', 'topic': 'shop',
                                      'scope': 'business', 'scope_id': None, 'valid_from': None,
                                      'valid_until': None, 'temporal_scope': 'unspecified', 'result_id': None})

    def declaration(self, group_id='custom', **changes):
        return {'business_id': str(self.ws.business_id()), 'action': 'declare', 'request_key': str(uuid4()),
                'group_id': group_id, 'content': {'kind': 'context', 'statement': 'Families shop every week.',
                'topic': 'weekly_customers_' + uuid4().hex, 'scope': 'business', 'scope_id': None,
                'valid_from': None, 'valid_until': None, 'temporal_scope': 'unspecified', 'result_id': None}, **changes}

    def test_http_addition_persists_group_atomically_and_retries_exactly(self):
        dossier_layout.save(self.ws, self.body(groups=[{'id': 'custom', 'name': 'Clientes', 'description': 'Perfil de clientes'}]))
        client, server = self.http()
        client.post('/api/login', json={'token': 'test-local-access'})
        body = self.declaration()
        first = client.post('/api/business/memory', json=body)
        self.assertEqual(first.status_code, 200, first.text)
        saved = first.json()
        current = client.get('/api/business/dossier').json()
        self.assertEqual(current['layout']['assignments'], {saved['fact_id']: 'custom'})
        self.assertEqual(current['layout']['revision'], 2)
        self.assertEqual(client.post('/api/business/memory', json=body).json(), saved)
        self.assertEqual(dossier.listing(self.ws)['layout']['revision'], 2)
        self.assertEqual(client.post('/api/business/memory', json={**body, 'group_id': 'ungrouped'}).status_code, 409)
        proposal = client.post('/api/business/memory', json=self.declaration('custom', action='propose')).json()
        self.assertEqual(proposal['status'], 'proposed')
        ungrouped = client.post('/api/business/memory', json=self.declaration('ungrouped')).json()
        layout = dossier.listing(self.ws)['layout']
        self.assertEqual(layout['assignments'][ungrouped['fact_id']], 'ungrouped')
        dossier_layout.save(self.ws, self.body(layout))

    def test_unavailable_group_rolls_back_fact_and_source_and_retry_does_not_restore_removed_group(self):
        initial = dossier.listing(self.ws)
        for group in ('foreign-group', 'review', 42, False, []):
            with self.subTest(group=group), self.assertRaises(WebError):
                dossier.change(self.ws, self.declaration(group))
        self.assertEqual(dossier.listing(self.ws)['facts'], initial['facts'])
        with connect(self.config) as db:
            self.assertEqual(db.execute("SELECT count(*) AS n FROM memory_sources WHERE business_id=%s AND origin_key LIKE 'manual:%%'", (self.ws.business_id(),)).fetchone()['n'], 0)
        dossier_layout.save(self.ws, self.body(groups=[{'id': 'custom', 'name': 'Clientes'}]))
        body = self.declaration()
        saved = dossier.change(self.ws, body)
        dossier_layout.save(self.ws, self.body(groups=[], assignments={}))
        self.assertEqual(dossier.change(self.ws, body), saved)
        self.assertEqual(dossier.listing(self.ws)['layout']['groups'], [])
        with self.assertRaises(WebError):
            dossier.change(self.ws, self.declaration())
        self.assertEqual(len(dossier.listing(self.ws)['facts']), len(initial['facts']) + 1)

    def test_sql_failure_in_assignment_rolls_back_entire_new_memory(self):
        dossier_layout.save(self.ws, self.body(groups=[{'id': 'custom', 'name': 'Clientes'}]))
        initial = dossier.listing(self.ws)
        body = self.declaration()
        def fail(db, *args):
            db.execute('SELECT 1/0')
        from psycopg.errors import DivisionByZero
        with patch.object(memory, '_assign_group', side_effect=fail), self.assertRaises(DivisionByZero):
            dossier.change(self.ws, body)
        current = dossier.listing(self.ws)
        self.assertEqual(current['facts'], initial['facts'])
        self.assertEqual(current['layout'], initial['layout'])
        saved = dossier.change(self.ws, body)
        self.assertEqual(dossier.listing(self.ws)['layout']['assignments'], {saved['fact_id']: 'custom'})

    def test_http_save_reload_and_repeat_migration_preserve_layout_without_changing_memory(self):
        fact = self.fact()
        client, server = self.http()
        self.assertEqual(client.get('/api/business/dossier').status_code, 401)
        client.post('/api/login', json={'token': 'test-local-access'})
        initial = client.get('/api/business/dossier').json()
        body = self.body(initial['layout'], groups=[{'id': 'custom', 'name': '  Clientes  '}], assignments={fact['fact_id']: 'custom'})
        response = client.post('/api/business/dossier-layout', json=body)
        self.assertEqual(response.status_code, 200, response.text)
        saved = response.json()
        self.assertEqual(saved['groups'], [{'id': 'custom', 'name': 'Clientes', 'description': ''}])
        self.assertEqual(saved['revision'], 1)
        migrate(self.config)
        migrate(self.config)
        current = client.get('/api/business/dossier').json()
        self.assertEqual(current['layout'], saved)
        self.assertEqual(current['facts'][0]['revision'], initial['facts'][0]['revision'])
        self.assertEqual(current['facts'][0]['content'], initial['facts'][0]['content'])
        self.assertEqual(dossier_layout.save(self.ws, body), saved)

    def test_descriptions_persist_and_legacy_layouts_remain_readable(self):
        saved = dossier_layout.save(self.ws, self.body(groups=[{'id': 'custom', 'name': 'Clientes', 'description': '  Perfil y necesidades de las familias.  '}]))
        self.assertEqual(saved['groups'][0]['description'], 'Perfil y necesidades de las familias.')
        self.assertEqual(dossier.listing(self.ws)['layout'], saved)
        with connect(self.config) as db:
            from psycopg.types.json import Jsonb
            db.execute('UPDATE web_dossier_layouts SET layout=%s WHERE business_id=%s',
                       (Jsonb({'groups': [{'id': 'custom', 'name': 'Legacy'}], 'assignments': {}}), self.ws.business_id()))
        self.assertEqual(dossier.listing(self.ws)['layout']['groups'][0]['description'], '')
        for description in (True, None, 'x' * 501):
            with self.subTest(description=description), self.assertRaises(WebError):
                dossier_layout.save(self.ws, self.body(groups=[{'id': 'custom', 'name': 'Clientes', 'description': description}]))

    def test_invalid_groups_and_unknown_assignments_leave_saved_layout_unchanged(self):
        initial = dossier.listing(self.ws)['layout']
        cases = [
            {'groups': [{'id': 'review', 'name': 'Custom'}]},
            {'groups': [{'id': 'custom', 'name': 'Por revisar'}]},
            {'groups': [{'id': 'a', 'name': 'Customers'}, {'id': 'b', 'name': ' customers '}]},
            {'groups': [{'id': 'a', 'name': 'Customers'}, {'id': 'a', 'name': 'Other'}]},
            {'groups': [{'id': 'a', 'name': ' '}]},
            {'groups': [{'id': str(i), 'name': str(i)} for i in range(21)]},
            {'assignments': {str(uuid4()): 'business'}},
            {'assignments': {str(uuid4()): 'missing'}},
            {'assignments': {'invalid': 'business'}},
            {'revision': True},
            {'revision': -1},
            {'unexpected': 'field'},
        ]
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises(WebError):
                dossier_layout.save(self.ws, self.body(initial, **changes))
        self.assertEqual(dossier.listing(self.ws)['layout'], initial)

    def test_other_business_cannot_assign_foreign_memory_or_replace_layout(self):
        original = self.ws.business_id()
        fact = self.fact()
        dossier_layout.save(self.ws, self.body(groups=[{'id': 'custom', 'name': 'Customers'}], assignments={fact['fact_id']: 'custom'}))
        self.ws.save_business({'request_key': str(uuid4()), 'name': 'Other business', 'description': 'Other context', 'expected_active_id': str(original)})
        other = dossier.listing(self.ws)['layout']
        self.assertEqual(other['revision'], 0)
        with self.assertRaises(WebError):
            dossier_layout.save(self.ws, self.body(other, assignments={fact['fact_id']: 'business'}))
        with self.assertRaises(WebError):
            dossier_layout.save(self.ws, self.body(other, business_id=str(original)))
        with connect(self.config) as db:
            self.assertEqual(dossier_layout.load(db, original)['revision'], 1)

    def test_concurrent_first_writes_allow_only_one_distinct_layout(self):
        first = self.body(groups=[{'id': 'a', 'name': 'First'}])
        second = self.body(groups=[{'id': 'b', 'name': 'Second'}])
        def write(body):
            try:
                return dossier_layout.save(self.ws, body)
            except WebError as error:
                return error.status
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(write, [first, second]))
        self.assertEqual(sum(isinstance(result, dict) for result in results), 1)
        self.assertIn(409, results)
        self.assertEqual(dossier.listing(self.ws)['layout']['revision'], 1)

    def test_deleting_groups_preserves_facts_and_clears_assignments_explicitly(self):
        fact = self.fact()
        saved = dossier_layout.save(self.ws, self.body(groups=[{'id': 'custom', 'name': 'Customers'}], assignments={fact['fact_id']: 'custom'}))
        with self.assertRaises(WebError):
            dossier_layout.save(self.ws, self.body(saved, groups=[]))
        empty = dossier_layout.save(self.ws, self.body(saved, groups=[], assignments={}))
        self.assertEqual(empty['groups'], [])
        self.assertEqual(str(dossier.listing(self.ws)['facts'][0]['fact_id']), fact['fact_id'])
        stale = copy.deepcopy(saved)
        stale['groups'][0]['name'] = 'Stale rename'
        with self.assertRaises(WebError):
            dossier_layout.save(self.ws, self.body(stale))
