"""Shared business knowledge: one declared-only core for the chat and the report brief."""
import unittest
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

from decision_room import business_knowledge, conversations
from decision_room.database import connect
from decision_room.memory import service as memory
from decision_room.service import import_batch
from decision_room.web import engine_jobs
from tests import test_web as fixtures
from test_memory import content


def row(status, temporal='unspecified', **extra):
    return dict(id=uuid4().hex, reference=uuid4().hex, revision=1, status=status, origin_id='o', origin_key='k',
                alternatives=['otra'], period={'from': None, 'until': None},
                content=dict(kind='context', statement='x', temporal_scope=temporal, scope='business'), **extra)


class DeclaredTests(unittest.TestCase):
    def test_only_declared_with_a_resolved_period_and_without_alternatives(self):
        kept = row('declared')
        rows = [kept, row('proposed'), row('conflicted'), row('declared', temporal='unresolved')]
        result = business_knowledge.declared(rows)
        self.assertEqual([r['id'] for r in result], [kept['id']])
        self.assertNotIn('alternatives', result[0])
        self.assertNotIn('origin_key', result[0])


class SharedCoreTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.WebTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.WebTests.tearDownClass.__func__)
    setUp = fixtures.WebTests.setUp

    def analysis(self):
        path = Path(self.temp.name) / 'ventas.csv'
        path.write_text('fecha,producto_id,unidades\n' + ''.join(
            f'{(date(2025, 1, 1) + timedelta(days=i)).isoformat()},P{i % 2},{1 + i % 3}\n' for i in range(90)))
        return import_batch(self.config, self.business['id'], [path])['analysis']['id']

    def remember(self):
        business = self.business['id']
        memory.change(self.config, business, action='declare', request_key=str(uuid4()),
                      content=content('Abrimos también los sábados por la tarde.', topic='saturday'))
        memory.change(self.config, business, action='propose', request_key=str(uuid4()),
                      content=content('Quizá cerremos en agosto.', topic='august', kind='open_question'))
        withdrawn = memory.change(self.config, business, action='declare', request_key=str(uuid4()),
                                  content=content('Vendemos a domicilio.', topic='delivery'))
        memory.change(self.config, business, action='withdraw', request_key=str(uuid4()),
                      fact_id=str(withdrawn['fact_id']), expected_revision=withdrawn['revision'])

    def test_chat_and_brief_receive_the_same_declared_core(self):
        analysis = self.analysis()
        self.remember()
        business = self.business['id']
        with connect(self.config) as db, db.transaction():
            saved = conversations.snapshot(db, business, analysis, 'objetivo')
            core = business_knowledge.build(db, business, saved['selection'], profile=saved['profile'])
        self.assertEqual(saved['knowledge'], core)
        statements = [m['content']['statement'] for m in core['memory']]
        self.assertEqual(statements, ['Abrimos también los sábados por la tarde.'])
        # The chat still manages proposed items, labelled, outside the shared core.
        self.assertIn('proposed', {m['status'] for m in saved['memories']})
        self.assertEqual(core['data_model']['analysis_id'], str(analysis))
        self.assertTrue(core['catalog']['use'].startswith('Discovery only'))

        job = dict(business_id=business, analysis_id=analysis, engine_config={'goal': 'Qué revisar.'},
                   origin='upload', business_name='Test shop', context='una tienda de prueba.', business_revision=1)
        builder, _ = engine_jobs.inputs(self.config, job)
        with connect(self.config) as db, db.transaction():
            prompt, provenance, *_ = builder(db)
        self.assertIn('Abrimos también los sábados por la tarde', prompt)
        self.assertNotIn('agosto', prompt)
        self.assertNotIn('domicilio', prompt)
        self.assertEqual(provenance['memory'], sorted(m['reference'] for m in core['memory']))


class CatalogTests(SharedCoreTests):
    test_chat_and_brief_receive_the_same_declared_core = None

    def test_other_datasets_are_listed_as_discovery_for_writer_and_checker(self):
        analysis = self.analysis()
        other = Path(self.temp.name) / 'visitas.csv'
        other.write_text('mes,visitas\n2025-01-01,10\n2025-02-01,12\n')
        second = import_batch(self.config, self.business['id'], [other])['analysis']['id']
        business = self.business['id']
        job = dict(business_id=business, analysis_id=analysis, engine_config={'goal': 'Qué revisar.', 'profile': {'format': 'blocks'}},
                   origin='upload', business_name='Test shop', context='una tienda de prueba.', business_revision=1)
        builder, _ = engine_jobs.inputs(self.config, job)
        with connect(self.config) as db, db.transaction():
            prompt, provenance, *_ = builder(db)
            saved = conversations.snapshot(db, business, analysis, 'objetivo')
        from decision_room.engine import brief
        listed = [i for i in saved['knowledge']['catalog']['items'] if i['analysis_id'] == str(second)]
        self.assertEqual(len(listed), 1)
        for text in (prompt, provenance['checker_context']):
            self.assertIn(brief.CATALOG, text)
            self.assertIn(listed[0]['description'], text)
        # Only the other dataset is listed; the mounted one is not repeated as discovery.
        self.assertEqual(len(saved['knowledge']['catalog']['items']), 2)
        self.assertEqual(prompt.split(brief.CATALOG)[1].split('\n\n')[0].count('\n- '), 1)


if __name__ == '__main__':
    unittest.main()
