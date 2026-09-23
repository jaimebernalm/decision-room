"""Real pgvector, deterministic embeddings for mechanics; real quality eval is separate."""
import json
import unittest
from dataclasses import replace
from unittest.mock import patch
from uuid import uuid4

import httpx

from decision_room.database import connect, migrate
from decision_room.service import create_business, import_batch
from decision_room.memory import semantic, retrieval, context as ctx, service as memory
import test_context_memory as context_tests
from test_memory import content


def fake_embed(config, texts):
    vectors = []
    for text in texts:
        # Controlled semantic equivalents, not a language-quality claim.
        concept = 0 if any(word in text.lower() for word in ('venta', 'facturación', 'client', 'restaurante')) else 1
        vector = [0.0] * config.embedding_dimensions
        vector[concept] = 1.0
        vectors.append(vector)
    return vectors, {'total_tokens': len(texts)}


class SemanticTests(unittest.TestCase):
    setUpClass = classmethod(context_tests.ContextTests.setUpClass.__func__)
    tearDownClass = classmethod(context_tests.ContextTests.tearDownClass.__func__)
    fact = context_tests.ContextTests.fact
    start = context_tests.ContextTests.start
    complete = context_tests.ContextTests.complete
    correct = context_tests.ContextTests.correct

    def setUp(self):
        context_tests.ContextTests.setUp(self)
        self.config = replace(self.config, semantic_search=True, embedding_dimensions=256)
        self.embedding = patch.object(semantic, 'embed', side_effect=fake_embed).start()
        self.addCleanup(patch.stopall)

    def search(self, plan, tool='search_datasets', query='facturación mercancías', **kwargs):
        with connect(self.config) as db:
            return retrieval.retrieve(self.config, db, plan['id'],
                dict(tool=tool, query=query, id=kwargs.get('id', ''), limit=kwargs.get('limit', 1)))[0]

    def title(self, text):
        with connect(self.config) as db:
            db.execute('UPDATE analyses SET title=%s WHERE id=%s', (text, self.analysis))

    def test_hybrid_synonyms_cache_and_model_dimensions_are_separate(self):
        self.title('Ventas de productos')
        self.fact()
        plan = self.start()
        first = self.search(plan)
        self.assertEqual(first['search']['mode'], 'hybrid')
        self.assertNotIn('lexical_rank', first['search']['matches'][0])
        self.assertEqual(first['items'][0]['analysis_id'], str(self.analysis))
        self.assertEqual(self.embedding.call_count, 2)  # Documents + query.
        self.search(plan)
        self.assertEqual(self.embedding.call_count, 3)  # Only query; cached documents reused.
        self.config = replace(self.config, embedding_model='text-embedding-3-large', embedding_dimensions=512)
        self.search(plan)
        self.assertEqual(self.embedding.call_count, 5)
        with connect(self.config) as db:
            rows = db.execute('SELECT DISTINCT model,vector_dims(embedding) n FROM semantic_chunks WHERE business_id=%s', (self.business,)).fetchall()
        self.assertEqual({(r['model'], r['n']) for r in rows}, {('text-embedding-3-small',256),('text-embedding-3-large',512)})

    def test_correction_and_withdrawal_exclude_cached_old_memory(self):
        self.fact()
        fact = memory.change(self.config, self.business, action='declare', request_key='clients',
                             content=content('Vendemos a restaurantes.', topic='customers'))
        old = self.start()
        self.search(old, 'search_memory', 'clientes')
        self.correct(fact, 'Vendemos exclusivamente a hospitales.')
        fresh = self.start()
        result = self.search(fresh, 'search_memory', 'clientes', limit=10)
        refs = {r['reference'] for r in result['memories']}
        self.assertIn(fact['fact_id'] + '@2', refs)
        self.assertNotIn(fact['fact_id'] + '@1', refs)
        memory.change(self.config, self.business, action='withdraw', request_key='remove', fact_id=fact['fact_id'], expected_revision=2)
        result = self.search(self.start(), 'search_memory', 'clientes', limit=10)
        self.assertNotIn(fact['fact_id'], {r['id'] for r in result['memories']})
        with connect(self.config) as db:
            self.assertGreater(db.execute('SELECT count(*) n FROM semantic_chunks WHERE business_id=%s AND object_key=%s',
                (self.business, fact['fact_id'] + '@1')).fetchone()['n'], 0)  # Stale cache deliberately remains.
        self.assertNotIn('restaurantes', json.dumps(result))

    def test_scope_and_future_period_filter_before_embedding(self):
        self.fact()
        future = memory.change(self.config, self.business, action='declare', request_key='future',
            content=content('SEPTEMBER_SECRET', topic='future', valid_from='2026-09-01'))
        other = create_business(self.config, 'Other')['id']
        file = self.root / 'other.csv'; file.write_text('private\nFOREIGN_SECRET\n')
        import_batch(self.config, other, [file], title='FOREIGN_SECRET')
        another = self.root / 'another.csv'; another.write_text('stock\n1\n')
        analysis = import_batch(self.config, self.business, [another])['analysis']['id']
        memory.change(self.config, self.business, action='declare', request_key='scoped',
            content=content('SOURCE_SECRET', topic='scoped', scope='analysis', scope_id=str(analysis)))
        plan = self.start(period={'from':'2026-06-01','until':'2026-06-30'})
        result = self.search(plan, 'search_memory', 'clientes', limit=10)
        self.search(plan)
        submitted = json.dumps([c.args[1] for c in self.embedding.call_args_list])
        for secret in ('SEPTEMBER_SECRET','FOREIGN_SECRET','SOURCE_SECRET'):
            self.assertNotIn(secret, submitted)
        self.assertNotIn(future['fact_id'], {r['id'] for r in result['memories']})

    def test_historical_revision_remains_searchable_in_its_period(self):
        fact = self.fact(valid_from='2026-01-01')
        old = memory.read(self.config, self.business, fact_id=fact['fact_id'])[0]
        memory.change(self.config, self.business, action='correct', change_kind='future', request_key='future',
            fact_id=fact['fact_id'], expected_revision=1,
            content={**old['content'], 'statement':'Amount is whole row total.', 'valid_from':'2026-09-01'})
        june = self.start(period={'from':'2026-06-01','until':'2026-06-30'})
        september = self.start(period={'from':'2026-09-01','until':'2026-09-30'})
        a = self.search(june, 'search_memory', 'importe')
        b = self.search(september, 'search_memory', 'importe')
        self.assertEqual(a['memories'][0]['revision'], 1)
        self.assertEqual(b['memories'][0]['revision'], 2)

    def test_provider_failure_is_explicit_and_doubts_survive(self):
        self.fact()
        doubt = memory.change(self.config, self.business, action='propose', request_key='doubt',
            content=content('No sabemos si faltan devoluciones.', kind='open_question'))
        plan = self.start()
        self.embedding.side_effect = semantic.EmbeddingUnavailable('Embedding provider HTTP 429.')
        with connect(self.config) as db:
            request = dict(tool='search_memory', query='unrelated', id='', limit=1)
            retrieval.save(self.config, db, plan['id'], 'failure', 1, request)
            event = db.execute('SELECT response FROM context_retrievals WHERE session_id=%s', (plan['id'],)).fetchone()['response']
            self.assertEqual(event['search']['mode'], 'text_fallback')
            self.assertIn(doubt['fact_id'], {r['id'] for r in event['memories']})
            calls = self.embedding.call_count
            retrieval.save(self.config, db, plan['id'], 'failure', 1, request)
            self.assertEqual(self.embedding.call_count, calls)
            self.assertEqual(db.execute('SELECT status FROM semantic_calls WHERE business_id=%s', (self.business,)).fetchone()['status'], 'failed')

    def test_correction_during_embedding_cannot_be_saved(self):
        fact = self.fact()
        plan = self.start()
        def racing(config, texts):
            self.correct(fact)
            return fake_embed(config, texts)
        self.embedding.side_effect = racing
        with connect(self.config) as db:
            with self.assertRaisesRegex(ctx.StaleContext, 'changed'):
                retrieval.save(self.config, db, plan['id'], 'race', 1,
                    dict(tool='search_memory', query='importe', id='', limit=1))
            self.assertEqual(db.execute('SELECT count(*) n FROM context_retrievals WHERE session_id=%s', (plan['id'],)).fetchone()['n'], 0)

    def test_discovered_dataset_change_during_search_is_rejected(self):
        self.fact()
        file = self.root / 'extra.csv'; file.write_text('stock\n2\n')
        extra = import_batch(self.config, self.business, [file], title='Ventas extra')['analysis']['id']
        plan = self.start()
        def racing(config, texts):
            with connect(config) as writer:
                writer.execute("UPDATE analyses SET title=title || ' corrected' WHERE id=%s", (extra,))
            return fake_embed(config, texts)
        self.embedding.side_effect = racing
        with self.assertRaisesRegex(ctx.StaleContext, 'Dataset changed'):
            self.search(plan, limit=10)

    def test_reports_held_and_incompatible_are_excluded_even_with_cached_vectors(self):
        from decision_room.agent import review
        self.fact()
        period = {'from':'2026-06-01','until':'2026-06-30'}
        first = self.start(period=period)
        _, report = self.complete(first)
        plan = self.start(period=period)
        result = self.search(plan, 'search_reports', 'facturación')
        self.assertEqual(result['items'][0]['id'], str(report['id']))
        self.assertEqual(result['search']['mode'], 'hybrid')
        later = self.start(period={'from':'2026-09-01','until':'2026-09-30'})
        self.assertEqual(self.search(later, 'search_reports', 'facturación')['items'], [])
        review.hold(self.config, self.business, report['id'], reason='Test withdrawal')
        self.assertEqual(self.search(plan, 'search_reports', 'facturación')['items'], [])

    def test_chunking_unicode_budgets_and_full_recall_of_late_fragment(self):
        text = 'á😀' * 2000 + ' ventas'
        pieces = semantic.chunks(text)
        self.assertTrue(all(len(p.encode()) <= 4000 for p in pieces))
        self.assertTrue(pieces[-1].endswith('ventas'))
        with connect(self.config) as db:
            keys, info = semantic.rank(self.config, db, self.business, 'memory',
                [dict(key='long', version='1', text=text), dict(key='other', version='1', text='stock')],
                'facturación', 1)
        self.assertEqual(keys, ['long'])
        self.assertIn('ventas', info['matches'][0]['excerpt'] if len(pieces[-1]) <= 500 else pieces[-1])

    def test_corpus_limit_is_explicit_and_no_api_call(self):
        with connect(self.config) as db, self.assertRaisesRegex(ValueError, '1000'):
            semantic.rank(self.config, db, self.business, 'dataset',
                [dict(key=str(n),version='1',text='ventas') for n in range(1001)], 'facturación', 1)
        self.embedding.assert_not_called()

    def test_cached_vectors_are_business_scoped_and_replay_is_provider_free(self):
        self.title('Ventas de productos')
        self.fact()
        plan = self.start()
        with connect(self.config) as db:
            request = dict(tool='search_datasets', query='facturación', id='', limit=1)
            retrieval.save(self.config, db, plan['id'], 'hybrid', 1, request)
            event = db.execute('SELECT response FROM context_retrievals WHERE session_id=%s', (plan['id'],)).fetchone()['response']
            self.assertEqual(event['search']['mode'], 'hybrid')
            calls = self.embedding.call_count
            retrieval.save(self.config, db, plan['id'], 'hybrid', 1, request)
            self.assertEqual(self.embedding.call_count, calls)
            other = create_business(self.config, 'Other cache')['id']
            # Poison an otherwise identical cache identity in another business.
            db.execute('''INSERT INTO semantic_chunks
                (business_id,kind,object_key,content_hash,model,dimensions,ordinal,fragment,embedding)
                SELECT %s,kind,object_key,content_hash,model,dimensions,ordinal,'FOREIGN_SECRET',embedding
                FROM semantic_chunks WHERE business_id=%s''', (other, self.business))
            result, _ = retrieval.retrieve(self.config, db, plan['id'], request)
            self.assertNotIn('FOREIGN_SECRET', json.dumps(result))

    def test_partial_index_failure_recovers_and_budget_falls_back_to_text(self):
        docs = [dict(key=str(n), version='1', text='ventas ' + str(n)) for n in range(33)]
        calls = []
        def fail_second(config, texts):
            calls.append(len(texts))
            if len(calls) == 2:
                raise semantic.EmbeddingUnavailable('Provider temporarily unavailable.')
            return fake_embed(config, texts)
        self.embedding.side_effect = fail_second
        with connect(self.config) as db:
            keys, info = semantic.rank(self.config, db, self.business, 'dataset', docs, 'ventas', 3)
            self.assertTrue(keys)
            self.assertEqual(info['mode'], 'text_fallback')
            self.assertEqual(calls, [32, 1])
            self.embedding.side_effect = fake_embed
            before = self.embedding.call_count
            _, info = semantic.rank(self.config, db, self.business, 'dataset', docs, 'ventas', 3)
            self.assertEqual(info['mode'], 'hybrid')
            self.assertEqual(self.embedding.call_count - before, 2)  # One missing fragment + query.
            before = self.embedding.call_count
            _, info = semantic.rank(self.config, db, self.business, 'dataset',
                [dict(key=str(n), version='1', text='ventas') for n in range(513)], 'ventas', 3)
            self.assertEqual(info['mode'], 'text_fallback')
            self.assertIn('512', info['issue'])
            self.assertEqual(self.embedding.call_count, before)


class EmbeddingTransportTests(unittest.TestCase):
    def test_transport_success_failure_and_malformed_vectors(self):
        from decision_room.config import Config
        from pathlib import Path
        config = Config('', Path('.'), embedding_dimensions=256)
        actual_client = httpx.Client
        captured = []
        response = [httpx.Response(200, json=dict(model=config.embedding_model,
            data=[dict(index=0, embedding=[1.0] + [0.0]*255)], usage={'total_tokens':2}))]
        def handler(request):
            captured.append(request)
            return response[0]
        with patch.dict('os.environ', {'OPENAI_API_KEY':'fixture-key'}), patch.object(semantic.httpx, 'Client',
            side_effect=lambda **kw: actual_client(transport=httpx.MockTransport(handler), **kw)):
            vector, usage = semantic.embed(config, ['ventas'])
            self.assertEqual(len(vector[0]), 256)
            self.assertEqual(str(captured[0].url), 'https://api.openai.com/v1/embeddings')
            self.assertEqual(usage['total_tokens'], 2)
            for body in [httpx.Response(401, text='private-provider-body'),
                         httpx.Response(200, json=dict(model='wrong', data=[])),
                         httpx.Response(200, json=dict(model=config.embedding_model, data=[dict(index=0, embedding=[0]*256)]))]:
                response[0] = body
                with self.assertRaises(semantic.EmbeddingUnavailable) as error:
                    semantic.embed(config, ['ventas'])
                self.assertNotIn('private-provider-body', str(error.exception))
                self.assertNotIn('fixture-key', str(error.exception))


if __name__ == '__main__':
    unittest.main()
