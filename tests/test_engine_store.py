"""Draft reception uses real PostgreSQL and process restart, without model calls."""
import json
import subprocess
import sys
import tempfile
import threading
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
from decision_room.engine import admission, gateway, store
from decision_room.reports import contract
from decision_room.reports.verification import build
from decision_room.web.report_projection import project, render
from decision_room.service import create_business, import_batch


class DraftTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = Config.load()
        cls.database = 'dr_engine_draft_' + uuid4().hex
        with connect(cls.base) as db:
            db.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(cls.database)))
        cls.dsn = make_conninfo(cls.base.dsn, dbname=cls.database)
        migrate(replace(cls.base, dsn=cls.dsn))

    @classmethod
    def tearDownClass(cls):
        with connect(cls.base) as db:
            db.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(cls.database)))

    def setUp(self):
        folder = tempfile.TemporaryDirectory(prefix='dr-engine-draft-')
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.config = replace(self.base, dsn=self.dsn, storage=self.root / 'storage')
        self.business = create_business(self.config, 'Draft fixture')['id']
        source = self.root / 'units.csv'
        source.write_text('quantity\n2\n3\n')
        batch = import_batch(self.config, self.business, [source])
        self.analysis = batch['analysis']['id']
        self.table = batch['files'][0]['table_id']
        self.run, self.token = self.create()

    def create(self):
        return admission.create_run(self.config, self.business, self.analysis,
                                    table_ids=[self.table], owner_context='Units only',
                                    request_key=uuid4().hex, model='test-model')

    def deliver(self, raw, key='delivery'):
        return store.receive_document(self.config, self.run, self.token, request_key=key, draft_json=raw)

    def test_malformed_duplicate_keys_empty_and_non_utf8_are_preserved_exactly(self):
        samples = [b'{"title":', b'{"x":1,"x":2}', b'', b'\xff\xfe']
        for i, raw in enumerate(samples):
            receipt = self.deliver(raw, str(i))
            self.assertEqual((receipt['status'], receipt['verification']), ('received', 'pending'))
            row = store.read_document(self.config, self.business, self.run, revision_id=receipt['revision_id'])
            self.assertEqual(row['raw'], raw)
            dest = self.root / f'export-{i}'
            self.assertEqual(store.export_raw(self.config, self.business, self.run, dest, revision_id=receipt['revision_id']), receipt)
            self.assertEqual((dest / 'draft.raw').read_bytes(), raw)
        self.assertEqual(admission.inspect_run(self.config, self.business, self.run)['status'], 'running')

    def test_identical_retry_and_new_revision_never_replace_previous_raw(self):
        first = self.deliver('{ "title": "á" }')
        self.assertEqual(first, self.deliver('{ "title": "á" }'))
        with self.assertRaises(ValueError):
            self.deliver('{"title":"á"}')  # Same JSON meaning is different exact bytes.
        second = self.deliver('{"title":"á"}', 'second')
        self.assertEqual(first['document_id'], second['document_id'])
        self.assertEqual((first['ordinal'], second['ordinal']), (1, 2))
        self.assertEqual(store.read_document(self.config, self.business, self.run)['revision_id'], second['revision_id'])
        self.assertEqual(store.read_document(self.config, self.business, self.run, revision_id=first['revision_id'])['raw'], '{ "title": "á" }'.encode())
        with connect(self.config) as db:
            self.assertEqual(db.execute("SELECT count(*) n FROM engine_events WHERE run_id=%s AND kind='draft_received'", (self.run,)).fetchone()['n'], 2)

    def test_concurrent_delivery_same_key_creates_one_revision(self):
        barrier = threading.Barrier(2)
        def submit(_):
            barrier.wait()
            return self.deliver('partial')
        with ThreadPoolExecutor(2) as pool:
            receipts = list(pool.map(submit, range(2)))
        self.assertEqual(receipts[0], receipts[1])
        self.assertEqual(receipts[0]['ordinal'], 1)

    def test_process_exit_after_commit_does_not_lose_unparsed_draft(self):
        script = '''import json,os,sys
from pathlib import Path
from decision_room.config import Config
from decision_room.engine.store import receive_document
p=json.load(sys.stdin)
receive_document(Config(p['dsn'],Path(p['storage'])),p['run'],p['token'],request_key='crash',draft_json='{"unfinished":')
os._exit(19)
'''
        completed = subprocess.run([sys.executable, '-c', script], input=json.dumps({
            'dsn': self.config.dsn, 'storage': str(self.config.storage),
            'run': str(self.run), 'token': self.token}), text=True, capture_output=True)
        self.assertEqual(completed.returncode, 19, completed.stderr)
        row = store.read_document(self.config, self.business, self.run)
        self.assertEqual(row['raw'], b'{"unfinished":')
        self.assertEqual(self.deliver('{"unfinished":', 'crash')['revision_id'], row['revision_id'])

    def test_aborted_or_waiting_run_retains_raw_but_rejects_late_delivery(self):
        receipt = self.deliver('partial report')
        for status in ['pausing', 'waiting', 'aborted']:
            with self.subTest(status=status):
                with connect(self.config) as db:
                    db.execute('UPDATE engine_runs SET status=%s,active_started_at=NULL WHERE id=%s', (status, self.run))
                with self.assertRaises(admission.Denied):
                    self.deliver('late replacement', status)
                dest = self.root / status
                store.export_raw(self.config, self.business, self.run, dest)
                self.assertEqual((dest / 'draft.raw').read_bytes(), b'partial report')
                self.assertEqual(store.read_document(self.config, self.business, self.run)['revision_id'], receipt['revision_id'])

    def test_foreign_job_business_and_token_cannot_read_or_write(self):
        receipt = self.deliver('private fixture')
        other, token = self.create()
        with self.assertRaises(admission.Denied):
            store.receive_document(self.config, self.run, token, request_key='bad', draft_json='overwrite')
        with self.assertRaises(admission.Denied):
            store.read_document(self.config, self.business, other, revision_id=receipt['revision_id'])
        foreign = create_business(self.config, 'Foreign draft fixture')['id']
        with self.assertRaises(admission.Denied):
            store.export_raw(self.config, foreign, self.run, self.root / 'denied')
        self.assertFalse((self.root / 'denied').exists())

    def test_size_is_utf8_bytes_and_no_draft_is_not_delivery(self):
        self.assertIsNone(store.export_raw(self.config, self.business, self.run, self.root / 'absent'))
        self.assertFalse((self.root / 'absent').exists())
        with self.assertRaises(ValueError):
            self.deliver('á' * (store.MAX_DRAFT_BYTES // 2 + 1))
        self.assertIsNone(store.read_document(self.config, self.business, self.run))
        self.deliver('a' * store.MAX_DRAFT_BYTES)
        self.assertEqual(len(store.read_document(self.config, self.business, self.run)['raw']), store.MAX_DRAFT_BYTES)

    def test_mcp_returns_small_receipt_without_echoing_draft(self):
        text = 'private fixture draft' * 1000
        result = gateway.dispatch(self.config, self.run, self.token, {
            'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
            'params': {'name': 'entregar_informe', 'arguments': {'request_key': 'mcp', 'draft_json': text}}})
        receipt = json.loads(result['result']['content'][0]['text'])
        self.assertEqual(receipt['status'], 'received')
        self.assertNotIn('private fixture draft', json.dumps(result))
        self.assertLess(len(json.dumps(result)), 1024)
        self.assertEqual(store.read_document(self.config, self.business, self.run)['raw'], text.encode())

    def test_mcp_format_feedback_follows_commit_and_correction_keeps_facts_and_chart(self):
        draft = {'schema_version': 1, 'title': 'Fixture', 'summary': 'Compare the observations.',
                 'limitations': ['fixture-private-limitation'],
                 'findings': [{'key': 'first', 'title': 'First', 'facts': ['units']},
                              {'key': 'second', 'title': 'Second', 'facts': ['units']},
                              {'key': 'third', 'title': 'Third', 'facts': ['units']}],
                 'numbers': [{'key': 'units', 'execution_id': str(uuid4()), 'metric': 'quantity', 'decimals': 0}],
                 'charts': [{'key': 'comparison', 'kind': 'bar', 'title': 'Units',
                             'series': [{'key': 'one', 'label': 'Units', 'points': [{'label': 'Period', 'number_key': 'units'}]}]}]}
        def deliver(raw, key):
            return gateway.dispatch(self.config, self.run, self.token, {
                'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                'params': {'name': 'entregar_informe', 'arguments': {'request_key': key, 'draft_json': raw}}})['result']
        invalid = json.dumps(draft)
        original = gateway.format_feedback
        def check_after_commit(raw):
            # Read through another connection while the feedback runs.
            self.assertEqual(store.read_document(self.config, self.business, self.run)['raw'], raw)
            return original(raw)
        with patch.object(gateway, 'format_feedback', side_effect=check_after_commit):
            bad = deliver(invalid, 'bad-shape')
        receipt = json.loads(bad['content'][0]['text'])
        self.assertTrue(bad['isError'])
        self.assertEqual(receipt['status'], 'received')
        self.assertFalse(receipt['format']['valid'])
        self.assertEqual(receipt['format']['errors'][0]['path'], '/limitations')
        self.assertIn('string', receipt['format']['errors'][0]['expected'])
        self.assertNotIn('fixture-private-limitation', json.dumps(bad))
        self.assertEqual(deliver(invalid, 'bad-shape'), bad)
        fallback, _, issues = contract.load(invalid.encode())
        self.assertEqual(fallback['summary'], invalid)
        self.assertIn('report_format_fallback', issues)
        draft['limitations'] = 'Known coverage limitations.'
        corrected = json.dumps(draft)
        self.assertTrue(deliver(corrected, 'bad-shape')['isError'])  # Changed bytes need a new identity.
        good = deliver(corrected, 'corrected-shape')
        self.assertNotIn('isError', good)
        final_receipt = json.loads(good['content'][0]['text'])
        self.assertTrue(final_receipt['format']['valid'])
        self.assertEqual(final_receipt['ordinal'], receipt['ordinal'] + 1)
        self.assertEqual(store.read_document(self.config, self.business, self.run, revision_id=receipt['revision_id'])['raw'], invalid.encode())
        raw = store.read_document(self.config, self.business, self.run)['raw']
        doc, refs, issues = contract.load(raw)
        self.assertEqual((len(doc['findings']), len(refs), len(doc['charts'])), (3, 1, 1))
        self.assertEqual([len(f['facts']) for f in doc['findings']], [1, 1, 1])
        self.assertEqual(issues, [])
        verified, ledger = build(raw)
        self.assertNotIn('report_format_fallback', ledger['issues'])
        self.assertFalse(any(f['verified'] for f in ledger['figures']))  # Valid shape does not certify data.
        self.assertIn('First', render(project(verified), marks=False))
        self.assertIn('Units', render(project(verified), marks=False))

    def test_mcp_feedback_failure_does_not_undo_persisted_raw(self):
        with patch.object(gateway, 'format_feedback', side_effect=RuntimeError('Synthetic validation interruption')):
            with self.assertRaises(RuntimeError):
                gateway.dispatch(self.config, self.run, self.token, {
                    'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                    'params': {'name': 'entregar_informe', 'arguments': {'request_key': 'saved', 'draft_json': '{'}}})
        self.assertEqual(store.read_document(self.config, self.business, self.run)['raw'], b'{')

    def test_export_replaces_file_symlink_and_detects_damaged_stored_bytes(self):
        receipt = self.deliver('kept raw')
        dest = self.root / 'export'; dest.mkdir()
        unrelated = self.root / 'unrelated.txt'; unrelated.write_text('unchanged')
        (dest / 'draft.raw').symlink_to(unrelated)
        store.export_raw(self.config, self.business, self.run, dest)
        self.assertEqual(unrelated.read_text(), 'unchanged')
        self.assertFalse((dest / 'draft.raw').is_symlink())
        with connect(self.config) as db:
            db.execute('UPDATE engine_document_revisions SET raw=%s WHERE id=%s', (b'corrupted', receipt['revision_id']))
        with self.assertRaises(ValueError):
            store.export_raw(self.config, self.business, self.run, self.root / 'corrupt')
        self.assertFalse((self.root / 'corrupt').exists())


if __name__ == '__main__':
    unittest.main()
