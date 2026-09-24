"""Real PostgreSQL: durable knowledge, scope, history and recovery boundaries."""
import json
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from psycopg import sql
from psycopg.conninfo import make_conninfo

from decision_room.config import Config
from decision_room.database import connect, migrate
from decision_room.service import create_business, import_batch
from decision_room.memory import service as memory, extraction
from decision_room.agent.model import ModelRequestUncertain, ModelClient, ModelSettings
from decision_room.web.service import Workspace


def content(statement='Cerramos los domingos.', **changes):
    if changes.get('valid_from') or changes.get('valid_until'):
        changes.setdefault('temporal_scope', 'dated')
    return {**dict(topic='sunday_opening', kind='context', statement=statement, scope='business',
                   scope_id=None, temporal_scope='unspecified', valid_from=None, valid_until=None, result_id=None), **changes}


def candidate(statement='Cerramos los domingos.', *, evidence='explicit', quote=None, conflicts=None, **changes):
    return {'content': content(statement, **changes), 'evidence': evidence,
            'quote': statement if quote is None else quote, 'conflicts_with': conflicts or []}


class MemoryModel:
    identity = {'model': 'memory-test-only'}

    def __init__(self, candidates=None, error=None):
        self.candidates = candidates or []
        self.error = error
        self.calls = 0

    def generate_memory(self, context, correction=None):
        self.calls += 1
        if self.error:
            raise self.error
        return {'candidates': self.candidates}, {'input_tokens': 10, 'output_tokens': 20}


class MemoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = Config.load()
        cls.name = 'dr_memory_test_' + uuid4().hex
        with connect(cls.base) as db:
            db.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(cls.name)))
        cls.dsn = make_conninfo(cls.base.dsn, dbname=cls.name)
        migrate(replace(cls.base, dsn=cls.dsn))

    @classmethod
    def tearDownClass(cls):
        with connect(cls.base) as db:
            db.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(cls.name)))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='dr-memory-test-')
        self.addCleanup(self.temp.cleanup)
        self.config = replace(self.base, dsn=self.dsn, storage=Path(self.temp.name))
        self.b = create_business(self.config, 'Fictional memory shop')['id']
        self.other = create_business(self.config, 'Separate shop')['id']

    def change(self, **values):
        return memory.change(self.config, self.b, request_key=str(uuid4()), **values)

    def capture(self, text='Cerramos los domingos.', **values):
        with connect(self.config) as db, db.transaction():
            return memory.capture(db, self.b, str(uuid4()), kind='manual', text=text, **values)

    def source(self, source):
        with connect(self.config) as db:
            return db.execute('SELECT * FROM memory_sources WHERE id=%s', (source['id'],)).fetchone()

    def process(self, source, *candidates, error=None):
        model = MemoryModel(list(candidates), error=error)
        extraction.process(self.config, self.b, source['id'], model)
        return model

    def batch(self):
        path = Path(self.temp.name) / 'sales.csv'
        path.write_text('date,amount\n2026-09-01,10\n')
        return import_batch(self.config, self.b, [path])

    def test_declare_correct_withdraw_history_and_another_process(self):
        first = self.change(action='declare', content=content())
        second = self.change(action='correct', fact_id=first['fact_id'], expected_revision=1,
                             content=content('Abrimos los domingos.'))
        self.change(action='withdraw', fact_id=first['fact_id'], expected_revision=second['revision'], reason='Retirar este dato')
        history = memory.read(self.config, self.b, history=True)
        self.assertEqual([r['status'] for r in history], ['declared', 'declared', 'withdrawn'])
        self.assertEqual(history[0]['content']['statement'], 'Cerramos los domingos.')
        self.assertEqual([r['effective_status'] for r in history], ['superseded', 'superseded', 'withdrawn'])
        self.assertEqual(memory.read(self.config, self.b, applicable_on='2026-09-23'), [])
        code = """import json,sys
from dataclasses import replace
from decision_room.config import Config
from decision_room.memory.service import read
args=json.load(sys.stdin)
print(read(replace(Config.load(),dsn=args['dsn']),args['business'])[0]['status'])
"""
        result = subprocess.run([sys.executable, '-c', code], input=json.dumps({'dsn': self.dsn, 'business': str(self.b)}),
                                text=True, capture_output=True, check=True)
        self.assertEqual(result.stdout.strip(), 'withdrawn')
        with self.assertRaises(memory.MemoryError):
            memory.read(self.config, self.b, history=True, applicable_on='2026-09-23')

    def test_idempotence_and_concurrent_revision_checks(self):
        key = str(uuid4())
        first = memory.change(self.config, self.b, action='declare', request_key=key, content=content())
        self.assertEqual(first, memory.change(self.config, self.b, action='declare', request_key=key, content=content()))
        with self.assertRaises(memory.MemoryError):
            memory.change(self.config, self.b, action='declare', request_key=key, content=content('Otro contenido'))
        def edit(value):
            try:
                return self.change(action='correct', fact_id=first['fact_id'], expected_revision=1, content=content(value))
            except memory.MemoryError as error:
                return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(edit, ['Abrimos.', 'Cerramos.']))
        self.assertEqual(sum(isinstance(r, dict) for r in results), 1)
        self.assertIn(409, results)
        self.assertEqual(len(memory.read(self.config, self.b, history=True)), 2)

    def test_proposal_confirmation_and_invalid_restore(self):
        first = self.change(action='propose', content=content('Estamos pensando en abrir.'))
        self.assertEqual(memory.read(self.config, self.b, applicable_on='2026-09-23'), [])
        self.change(action='confirm', fact_id=first['fact_id'], expected_revision=1)
        self.assertEqual(len(memory.read(self.config, self.b, applicable_on='2026-09-23')), 1)
        self.change(action='withdraw', fact_id=first['fact_id'], expected_revision=2)
        with self.assertRaises(memory.MemoryError):
            self.change(action='confirm', fact_id=first['fact_id'], expected_revision=3)

    def test_scope_and_dates_do_not_leak_to_another_file_or_period(self):
        batch = self.batch()
        with connect(self.config) as db:
            source = db.execute('SELECT id FROM sources WHERE analysis_id=%s', (batch['analysis']['id'],)).fetchone()['id']
        self.change(action='declare', content=content('Este CSV incluye IVA.', kind='definition',
                    scope='source', scope_id=str(source), valid_from='2026-09-01', valid_until='2026-09-30'))
        self.assertEqual(memory.read(self.config, self.b, applicable_on='2026-08-31', source_id=source), [])
        self.assertEqual(memory.read(self.config, self.b, applicable_on='2026-09-23'), [])
        self.assertEqual(len(memory.read(self.config, self.b, applicable_on='2026-09-23', source_id=source)), 1)
        with self.assertRaises(memory.MemoryError):
            memory.change(self.config, self.other, action='declare', request_key='other', content=content(scope='source', scope_id=str(source)))
        with self.assertRaises(ValueError):
            self.change(action='declare', content=content(valid_from='2026-10-01', valid_until='2026-09-30'))

    def test_foreign_fact_and_source_cannot_be_read_changed_or_retried(self):
        fact = self.change(action='declare', content=content())
        source = self.capture()
        for operation in (
            lambda: memory.read(self.config, self.other, fact_id=fact['fact_id']),
            lambda: memory.change(self.config, self.other, action='withdraw', request_key='x', fact_id=fact['fact_id'], expected_revision=1),
            lambda: extraction.process(self.config, self.other, source['id'], MemoryModel()),
            lambda: extraction.retry(self.config, self.other, source['id'])):
            with self.assertRaises(memory.MemoryError) as caught:
                operation()
            self.assertEqual(caught.exception.status, 404)

    def test_explicit_and_hypothetical_extraction_preserve_original_and_future_date(self):
        text = 'Desde el 1 de octubre de 2026 abrimos los domingos. Estamos pensando en vender online.'
        source = self.capture(text)
        self.process(source,
                     candidate('Abrimos los domingos.', quote='Desde el 1 de octubre de 2026 abrimos los domingos.', valid_from='2026-10-01'),
                     candidate('Estamos pensando en vender online.', evidence='hypothetical', topic='online_channel'))
        rows = memory.read(self.config, self.b)
        self.assertEqual({r['status'] for r in rows}, {'declared', 'proposed'})
        self.assertEqual(self.source(source)['payload']['text'], text)
        self.assertEqual(memory.read(self.config, self.b, applicable_on='2026-09-23'), [])
        self.assertEqual(len(memory.read(self.config, self.b, applicable_on='2026-10-01')), 1)

    def test_contradiction_stays_unresolved_until_explicit_correction(self):
        first = self.change(action='declare', content=content())
        source = self.capture('Abrimos todos los domingos.')
        self.process(source, candidate('Abrimos todos los domingos.', topic='opening_schedule', conflicts=[first['fact_id']]))
        row = memory.read(self.config, self.b)[0]
        self.assertEqual(row['status'], 'conflicted')
        self.assertEqual(len(row['alternatives']), 2)
        self.assertEqual(memory.read(self.config, self.b, applicable_on='2026-09-23'), [])
        with self.assertRaises(memory.MemoryError):
            self.change(action='confirm', fact_id=first['fact_id'], expected_revision=2)
        self.change(action='correct', fact_id=first['fact_id'], expected_revision=2, content=content('Abrimos todos los domingos.'))
        self.assertEqual(memory.read(self.config, self.b)[0]['status'], 'declared')

    def test_withdrawn_origin_and_rephrased_replay_do_not_restore_memory(self):
        source = self.capture()
        model = self.process(source, candidate())
        fact = memory.read(self.config, self.b)[0]
        self.change(action='withdraw', fact_id=fact['fact_id'], expected_revision=1)
        self.assertFalse(extraction.process(self.config, self.b, source['id'], model))
        another = self.capture('Los domingos no abrimos.')
        self.process(another, candidate('Los domingos no abrimos.'))
        self.assertEqual(memory.read(self.config, self.b)[0]['status'], 'withdrawn')
        self.assertEqual(len(memory.read(self.config, self.b, history=True)), 2)

    def test_unknown_and_declined_preserve_question_without_model_or_definition(self):
        batch = self.batch()
        for disposition in ('unknown', 'declined'):
            source = self.capture('', question='¿Incluye IVA el importe?', disposition=disposition,
                                  default_scope='analysis', scope_id=batch['analysis']['id'])
            model = self.process(source)
            self.assertEqual(model.calls, 0)
            self.assertEqual(self.source(source)['status'], 'applied')
        rows = memory.read(self.config, self.b)
        self.assertTrue(all(r['content']['kind'] == 'open_question' for r in rows))
        self.assertFalse(any(r['status'] == 'declared' for r in rows))

    def test_invalid_quote_scope_and_result_roll_back_all_candidates(self):
        batch = self.batch()
        cases = [candidate(quote='Texto inventado'), candidate(scope='analysis', scope_id=str(batch['analysis']['id'])),
                 candidate(kind='result_reference', result_id=str(uuid4())), candidate(kind='definition')]
        for bad in cases:
            source = self.capture()
            self.process(source, candidate(topic='valid_topic'), bad)
            self.assertEqual(self.source(source)['status'], 'failed')
            self.assertEqual(memory.read(self.config, self.b), [])

    def test_model_failure_and_uncertain_call_require_explicit_retry(self):
        for error, expected in ((RuntimeError('private error'), 'failed'), (ModelRequestUncertain('timeout'), 'uncertain')):
            source = self.capture()
            failed = self.process(source, error=error)
            self.assertEqual(self.source(source)['status'], expected)
            self.assertFalse(extraction.process(self.config, self.b, source['id'], failed))
            self.assertEqual(failed.calls, 1)
            extraction.retry(self.config, self.b, source['id'])
            self.process(source, candidate())
            self.assertEqual(self.source(source)['status'], 'applied')
        self.assertEqual(len(memory.read(self.config, self.b)), 1)

    def test_crash_after_response_is_recovered_without_another_model_call(self):
        source = self.capture()
        model = MemoryModel([candidate()])
        with patch.object(extraction, '_apply', side_effect=KeyboardInterrupt), self.assertRaises(KeyboardInterrupt):
            extraction.process(self.config, self.b, source['id'], model)
        self.assertEqual(self.source(source)['status'], 'extracted')
        extraction.process(self.config, self.b, source['id'], model)
        self.assertEqual(model.calls, 1)
        self.assertEqual(len(memory.read(self.config, self.b)), 1)

    def test_crash_during_model_call_is_uncertain_and_not_automatically_repeated(self):
        source = self.capture()
        model = MemoryModel(error=KeyboardInterrupt())
        with self.assertRaises(KeyboardInterrupt):
            extraction.process(self.config, self.b, source['id'], model)
        extraction.process(self.config, self.b, source['id'], model)
        self.assertEqual(self.source(source)['status'], 'uncertain')
        self.assertEqual(model.calls, 1)
        with connect(self.config) as db:
            self.assertEqual(db.execute('SELECT status FROM memory_calls WHERE source_id=%s', (source['id'],)).fetchone()['status'], 'uncertain')

    def test_persistence_failure_after_response_reuses_saved_output(self):
        source = self.capture()
        model = MemoryModel([candidate()])
        with patch.object(extraction, 'append', side_effect=RuntimeError('database unavailable')):
            extraction.process(self.config, self.b, source['id'], model)
        self.assertEqual(self.source(source)['status'], 'failed')
        self.assertEqual(memory.read(self.config, self.b), [])
        extraction.retry(self.config, self.b, source['id'])
        extraction.process(self.config, self.b, source['id'], model)
        self.assertEqual(model.calls, 1)
        self.assertEqual(len(memory.read(self.config, self.b)), 1)

    def test_concurrent_memory_change_requires_fresh_extraction(self):
        source = self.capture()
        model = MemoryModel([candidate()])
        def changed(context):
            self.change(action='declare', content=content('Vendemos libros.', topic='products'))
            return {'candidates': [candidate()]}, {}
        with patch.object(model, 'generate_memory', side_effect=changed):
            extraction.process(self.config, self.b, source['id'], model)
        self.assertEqual(self.source(source)['status'], 'failed')
        extraction.retry(self.config, self.b, source['id'])
        self.assertEqual(self.source(source)['status'], 'pending')
        extraction.process(self.config, self.b, source['id'], model)
        self.assertEqual(len(memory.read(self.config, self.b)), 2)

    def test_profile_and_queue_are_atomic_and_obsolete_profile_is_not_applied(self):
        ws = Workspace(self.config)
        body = {'request_key': str(uuid4()), 'name': 'Test profile', 'description': 'Cerramos los domingos.'}
        with patch('decision_room.web.business.capture', side_effect=RuntimeError), self.assertRaises(RuntimeError):
            ws.save_business(body)
        self.assertIsNone(ws.state()['business'])
        profile = ws.save_business(body)
        with connect(self.config) as db:
            source = db.execute('SELECT * FROM memory_sources WHERE business_id=%s', (profile['id'],)).fetchone()
        ws.save_business({'business_id': str(profile['id']), 'profile_revision': 1, 'name': profile['name'],
                          'description': 'Abrimos los domingos.'})
        extraction.process(self.config, profile['id'], source['id'], MemoryModel([candidate()]))
        self.assertEqual(self.source(source)['status'], 'superseded')
        self.assertEqual(memory.read(self.config, profile['id']), [])

    def test_source_idempotence_rejects_rewritten_original(self):
        with connect(self.config) as db, db.transaction():
            first = memory.capture(db, self.b, 'source', kind='manual', text='Original')
            again = memory.capture(db, self.b, 'source', kind='manual', text='Original')
        self.assertEqual(first['id'], again['id'])
        with connect(self.config) as db, db.transaction(), self.assertRaises(memory.MemoryError):
            memory.capture(db, self.b, 'source', kind='manual', text='Changed')
        self.assertEqual(self.source(first)['payload']['text'], 'Original')

    def test_model_contract_uses_existing_provider_boundary(self):
        model = ModelClient(ModelSettings(model='test-only'))
        with patch.object(model, '_generate', return_value=({'candidates': []}, {})) as generate:
            model.generate_memory({'source': {'default_scope': 'business', 'scope_id': None,
                                              'allow_business': True}})
        schema = generate.call_args.args[-1]
        self.assertFalse(schema['additionalProperties'])
        self.assertEqual(schema['required'], ['candidates'])
        self.assertIn('untrusted', generate.call_args.args[2])
        fields = schema['$defs']['Content']['properties']
        self.assertEqual(fields['scope']['enum'], ['business'])
        self.assertEqual(fields['scope_id'], {'type': 'null'})
        self.assertNotIn('definition', fields['kind']['enum'])
        self.assertNotIn('result_reference', fields['kind']['enum'])

    def test_invalid_business_scope_is_corrected_automatically(self):
        source = self.capture('Cerramos los domingos.', allow_business=True)
        invalid = candidate(scope='source', scope_id=None)
        valid = candidate()

        class CorrectingModel:
            identity = {'model': 'correction-test-only'}
            calls = []

            def generate_memory(self, context, correction=None):
                self.calls.append((context, correction))
                return {'candidates': [valid if correction else invalid]}, {}

        model = CorrectingModel()
        extraction.process(self.config, self.b, source['id'], model)
        self.assertEqual(self.source(source)['status'], 'applied')
        self.assertEqual(len(memory.read(self.config, self.b)), 1)
        self.assertEqual(len(model.calls), 2)
        self.assertIn('scope', model.calls[1][1])
        self.assertIn('previous_response', model.calls[1][0])
        with connect(self.config) as db:
            calls = db.execute('SELECT status FROM memory_calls WHERE source_id=%s ORDER BY created_at',
                               (source['id'],)).fetchall()
        self.assertEqual([row['status'] for row in calls], ['completed', 'completed'])

    def test_greeting_is_applied_without_model_or_new_fact(self):
        with connect(self.config) as db, db.transaction():
            source = memory.capture(db, self.b, 'chat_message:' + str(uuid4()),
                                    kind='manual', text='¡Hola!')
        model = MemoryModel([candidate()])
        extraction.process(self.config, self.b, source['id'], model)
        self.assertEqual(self.source(source)['status'], 'applied')
        self.assertEqual(model.calls, 0)
        self.assertEqual(memory.read(self.config, self.b), [])
        with connect(self.config) as db:
            self.assertFalse(db.execute('SELECT 1 FROM memory_calls WHERE source_id=%s',
                                        (source['id'],)).fetchone())

    def test_hypothesis_does_not_displace_current_declared_schedule(self):
        self.change(action='declare', content=content())
        source = self.capture('Estamos pensando en abrir los domingos.')
        self.process(source, candidate('Estamos pensando en abrir los domingos.', evidence='hypothetical'))
        rows = memory.read(self.config, self.b)
        self.assertEqual({r['status'] for r in rows}, {'declared', 'proposed'})
        active = memory.read(self.config, self.b, applicable_on='2026-09-23')
        self.assertEqual([r['content']['statement'] for r in active], ['Cerramos los domingos.'])

    def test_two_extractors_cannot_duplicate_one_provider_call(self):
        import threading
        entered, release = threading.Event(), threading.Event()
        source = self.capture()
        model = MemoryModel([candidate()])
        original = model.generate_memory
        def generate(context):
            entered.set()
            release.wait(10)
            return original(context)
        with patch.object(model, 'generate_memory', side_effect=generate), ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(extraction.process, self.config, self.b, source['id'], model)
            self.assertTrue(entered.wait(5))
            try:
                self.assertFalse(extraction.process(self.config, self.b, source['id'], model))
            finally:
                release.set()
            self.assertTrue(first.result())
        self.assertEqual(model.calls, 1)
        self.assertEqual(len(memory.read(self.config, self.b)), 1)

    def test_stale_output_is_cleared_before_a_new_uncertain_call(self):
        source = self.capture()
        model = MemoryModel([candidate()])
        with patch.object(extraction, '_apply', side_effect=KeyboardInterrupt), self.assertRaises(KeyboardInterrupt):
            extraction.process(self.config, self.b, source['id'], model)
        self.change(action='declare', content=content('Vendemos libros.', topic='products'))
        extraction.process(self.config, self.b, source['id'], model)
        self.assertEqual(self.source(source)['status'], 'failed')
        extraction.retry(self.config, self.b, source['id'])
        self.process(source, error=ModelRequestUncertain('timeout'))
        saved = self.source(source)
        self.assertEqual(saved['status'], 'uncertain')
        self.assertIsNone(saved['response'])
        extraction.retry(self.config, self.b, source['id'])
        self.assertEqual(self.source(source)['status'], 'pending')
        self.assertEqual(len(memory.read(self.config, self.b)), 1)

    def test_unresolved_temporal_scope_cannot_be_confirmed_as_current(self):
        source = self.capture('Desde septiembre abrimos los domingos.')
        self.process(source, candidate('Desde septiembre abrimos los domingos.', temporal_scope='unresolved'))
        fact = memory.read(self.config, self.b)[0]
        self.assertEqual(fact['status'], 'proposed')
        self.assertEqual(memory.read(self.config, self.b, applicable_on='2026-09-23'), [])
        with self.assertRaises(memory.MemoryError):
            self.change(action='confirm', fact_id=fact['fact_id'], expected_revision=1)
        self.change(action='correct', fact_id=fact['fact_id'], expected_revision=1,
                    content=content('Abrimos los domingos desde septiembre de 2026.', valid_from='2026-09-01'))
        self.assertEqual(len(memory.read(self.config, self.b, applicable_on='2026-09-23')), 1)
