"""Client transport contracts and real SQLite/WAL checkpoint integrity."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import httpx

from decision_room.engine import checkpoint
from decision_room.engine.client import Client, DeliveryUncertain, Events, ProtocolError


class ClientTests(unittest.TestCase):
    def client(self, handler):
        client = Client('http://engine.internal:4096', 'synthetic-password', transport=httpx.MockTransport(handler))
        self.addCleanup(client.close)
        return client

    def test_mcp_is_reconnected_and_confirmed_before_prompting(self):
        paths = []
        def handler(request):
            paths.append((request.method, request.url.path))
            if request.method == 'POST': return httpx.Response(200, json=True)
            return httpx.Response(200, json={'decision_room': {'status': 'connected' if len(paths) > 1 else 'failed'}})
        self.client(handler).require_mcp()
        self.assertEqual(paths, [('GET', '/mcp'), ('POST', '/mcp/decision_room/connect'), ('GET', '/mcp')])
        with self.assertRaises(ProtocolError):
            self.client(lambda _: httpx.Response(200, json={'decision_room': {'status': 'failed'}})).require_mcp()

    def test_fixed_version_password_and_explicit_title(self):
        seen = []
        def handle(request):
            self.assertEqual(request.headers['authorization'], 'Basic b3BlbmNvZGU6c3ludGhldGljLXBhc3N3b3Jk')
            self.assertEqual(request.url.params['directory'], '/work')
            seen.append(request)
            if request.url.path == '/global/health':
                return httpx.Response(200, json={'healthy': True, 'version': '1.18.34'})
            body = json.loads(request.content)
            self.assertEqual(body['title'], 'Report job')
            self.assertEqual(body['model'], {'id': 'test-model', 'providerID': 'openai', 'variant': 'low'})
            return httpx.Response(200, json={'id': 'ses_fixture', 'title': body['title']})
        client = self.client(handle)
        client.health()
        self.assertEqual(client.create_session(title='Report job', model='test-model')['id'], 'ses_fixture')
        self.assertEqual(len(seen), 2)
        wrong = self.client(lambda _: httpx.Response(200, json={'healthy': True, 'version': 'different'}))
        with self.assertRaises(ProtocolError):
            wrong.health()

    def test_uncertain_prompt_is_not_retried_and_reconciles_by_message_id(self):
        calls = []
        def handle(request):
            calls.append(request.url.path)
            if request.method == 'POST':
                body = json.loads(request.content)
                self.assertEqual(body['messageID'], 'msg_durable')
                self.assertEqual(body['parts'], [{'type': 'text', 'text': 'Compute units'}])
                raise httpx.ReadTimeout('private prompt and synthetic-password', request=request)
            return httpx.Response(200, json={'info': {'id': 'msg_durable'}, 'parts': []})
        client = self.client(handle)
        with self.assertRaises(DeliveryUncertain) as caught:
            client.submit('ses_fixture', message_id='msg_durable', text='Compute units', model='test-model')
        self.assertNotIn('synthetic-password', str(caught.exception))
        self.assertEqual(calls, ['/session/ses_fixture/prompt_async'])
        self.assertEqual(client.message('ses_fixture', 'msg_durable')['info']['id'], 'msg_durable')

    def test_async_ack_missing_message_and_abort_contracts(self):
        def handle(request):
            if request.url.path.endswith('/prompt_async'):
                return httpx.Response(204)
            if '/message/' in request.url.path:
                return httpx.Response(404)
            if request.url.path.endswith('/abort'):
                return httpx.Response(200, json=True)
            self.assertEqual(dict(request.url.params), {'directory': '/work', 'limit': '10', 'before': 'msg_previous'})
            return httpx.Response(200, json=[])
        client = self.client(handle)
        self.assertIsNone(client.submit('ses_fixture', message_id='msg_once', text='Compute', model='test-model'))
        self.assertIsNone(client.message('ses_fixture', 'msg_once'))
        self.assertTrue(client.abort('ses_fixture'))
        self.assertEqual(client.messages('ses_fixture', before='msg_previous', limit=10), [])
        with self.assertRaises(ValueError):
            client.message('ses_fixture/../../secret', 'msg_once')

    def test_redirect_and_error_bodies_are_never_followed_or_exposed(self):
        seen = []
        def handle(request):
            seen.append(request)
            return httpx.Response(302, headers={'location': 'https://foreign.invalid'}, text='private body')
        client = self.client(handle)
        with self.assertRaises(ProtocolError) as caught:
            client.health()
        self.assertEqual(len(seen), 1)
        self.assertNotIn('private body', str(caught.exception))
        with self.assertRaises(ValueError):
            Client('http://user:password@engine.internal', 'another')
        with self.assertRaises(ValueError):
            Client('http://engine.internal', '')

    def test_sse_fragmentation_and_eof_require_reconciliation(self):
        data = 'data: {"type":"message.part.updated","properties":{"text":"á"}}\r\n\r\n'.encode()
        parser = Events(); events = []
        for byte in data:
            events.extend(parser.feed(bytes([byte])))
        self.assertEqual(events[0]['properties']['text'], 'á')
        client = self.client(lambda _: httpx.Response(200, headers={'Content-Type': 'text/event-stream'}, content=data))
        stream = client.events()
        self.assertEqual(next(stream)['type'], 'message.part.updated')
        with self.assertRaises(ProtocolError):
            next(stream)
        with self.assertRaises(ProtocolError):
            Events().feed(b'data: []\n\n')
        with self.assertRaises(ProtocolError):
            Events().feed(b'x' * (1024*1024 + 1))


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(prefix='dr-engine-checkpoint-')
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.source = self.root / 'state.db'
        self.db = sqlite3.connect(self.source)
        self.addCleanup(self.db.close)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA wal_autocheckpoint=0')
        self.db.execute('CREATE TABLE message(id TEXT PRIMARY KEY,body TEXT)')
        self.db.execute("INSERT INTO message VALUES ('msg_1','committed in WAL')")
        self.db.commit()

    def test_backup_includes_wal_and_excludes_uncommitted_rows(self):
        self.db.execute("INSERT INTO message VALUES ('msg_2','not committed')")
        snapshot = self.root / 'snapshot'
        checkpoint.capture(self.source, snapshot)
        self.db.rollback()
        restored = self.root / 'restored.db'
        checkpoint.restore(snapshot, restored)
        with sqlite3.connect(restored) as db:
            self.assertEqual(db.execute('SELECT * FROM message').fetchall(), [('msg_1', 'committed in WAL')])
            db.execute("INSERT INTO message VALUES ('msg_3','resumed')")
        self.assertEqual(self.db.execute('SELECT count(*) FROM message').fetchone()[0], 1)

    def test_inspection_of_wal_mode_backup_never_creates_or_changes_files(self):
        snapshot = self.root / 'snapshot'
        checkpoint.capture(self.source, snapshot)
        before = {p.name: p.read_bytes() for p in snapshot.iterdir()}
        for _ in range(3):
            checkpoint.inspect(snapshot)
        self.assertEqual({p.name: p.read_bytes() for p in snapshot.iterdir()}, before)
        self.assertEqual(set(before), {'manifest.json', 'opencode.db'})

    def test_two_checkpoints_preserve_both_revisions_and_reject_overwrite(self):
        first = self.root / 'first'; second = self.root / 'second'
        a = checkpoint.capture(self.source, first)
        self.db.execute("INSERT INTO message VALUES ('msg_2','later')"); self.db.commit()
        b = checkpoint.capture(self.source, second)
        self.assertNotEqual(a['sha256'], b['sha256'])
        with self.assertRaises(ValueError):
            checkpoint.capture(self.source, first)
        dest = self.root / 'resume.db'
        checkpoint.restore(first, dest)
        with self.assertRaises(ValueError):
            checkpoint.restore(second, dest)
        with sqlite3.connect(dest) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM message').fetchone()[0], 1)

    def test_corrupt_incomplete_or_path_changing_checkpoint_is_rejected(self):
        snap = self.root / 'snapshot'; checkpoint.capture(self.source, snap)
        dest = self.root / 'restore.db'
        manifest = json.loads((snap / 'manifest.json').read_text())
        (snap / 'manifest.json').chmod(0o600)
        (snap / 'manifest.json').write_text('[]')
        with self.assertRaises(ValueError):
            checkpoint.restore(snap, dest)
        (snap / 'manifest.json').write_text(json.dumps({**manifest, 'database': '../state.db'}))
        with self.assertRaises(ValueError):
            checkpoint.restore(snap, dest)
        (snap / 'manifest.json').write_text(json.dumps(manifest))
        (snap / 'opencode.db').chmod(0o600)
        (snap / 'opencode.db').write_bytes(b'corrupt')
        with self.assertRaises(ValueError):
            checkpoint.restore(snap, dest)
        self.assertFalse(dest.exists())
        (snap / 'manifest.json').unlink()
        with self.assertRaises(ValueError):
            checkpoint.restore(snap, dest)

    def test_restore_does_not_follow_destination_symlink(self):
        snap = self.root / 'snapshot'; checkpoint.capture(self.source, snap)
        victim = self.root / 'private.txt'; victim.write_text('keep')
        dest = self.root / 'restore.db'; dest.symlink_to(victim)
        with self.assertRaises(ValueError):
            checkpoint.restore(snap, dest)
        self.assertEqual(victim.read_text(), 'keep')


if __name__ == '__main__':
    unittest.main()
