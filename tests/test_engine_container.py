"""Real Docker recovery of OpenCode sessions and work files, no model traffic."""
import io
import os
from pathlib import Path
import secrets
import tarfile
import tempfile
import unittest
from uuid import uuid4

from decision_room.docker_backend import DockerBackend
from decision_room.engine.container import Runtime, _unpack, inspect_snapshot


class ArchiveTests(unittest.TestCase):
    def test_links_traversal_duplicates_and_devices_are_rejected(self):
        for name, kind, duplicate in [('../outside', tarfile.REGTYPE, False),
            ('/absolute', tarfile.REGTYPE, False), ('link', tarfile.SYMTYPE, False),
            ('hard', tarfile.LNKTYPE, False), ('pipe', tarfile.FIFOTYPE, False),
            ('x', tarfile.REGTYPE, True)]:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                raw = io.BytesIO()
                with tarfile.open(fileobj=raw, mode='w') as archive:
                    item = tarfile.TarInfo(name); item.type = kind; item.linkname = 'outside'
                    archive.addfile(item)
                    if duplicate:
                        archive.addfile(item)
                with self.assertRaises(ValueError):
                    _unpack(raw.getvalue(), Path(directory))


@unittest.skipUnless(os.environ.get('DECISION_ROOM_ENGINE_IMAGE_ID'), 'Build the pinned engine image.')
class RuntimeTests(unittest.TestCase):
    def test_stop_checkpoint_restore_session_and_work_in_new_container(self):
        backend = DockerBackend(); image = os.environ['DECISION_ROOM_ENGINE_IMAGE_ID']; run = uuid4()
        def runtime():
            result = Runtime(backend, run_id=run, instance_id=uuid4(), image=image,
                             password=secrets.token_urlsafe(32), token=secrets.token_urlsafe(32), model='gpt-6-luna')
            self.addCleanup(result.remove)
            return result
        first = runtime(); first.create()
        first.install_files('inputs', {'fixture.csv': b'units\n2\n3\n'})
        first.install_files('work', {'notes.txt': 'Persistir á'.encode()})
        with first.start() as client:
            session = client.create_session(title='Recovery fixture without model', model='gpt-6-luna')
            self.assertEqual(client.messages(session['id']), [])
            child = client._request('POST', '/session', body={'title': 'Child recovery fixture', 'parentID': session['id']})
            self.assertIn(child['id'], [s['id'] for s in client.children(session['id'])])
        with tempfile.TemporaryDirectory() as folder:
            snapshot = Path(folder) / 'checkpoint'
            manifest = first.capture(snapshot)
            self.assertFalse(first._inspect()['State']['Running'])
            self.assertIn('work/notes.txt', manifest['files'])
            second = runtime(); second.restore(snapshot)
            self.assertNotEqual(first.container_id, second.container_id)
            with second.start() as client:
                self.assertEqual(client.session(session['id'])['title'], session['title'])
                self.assertEqual(client.messages(session['id']), [])
                self.assertIn(child['id'], [s['id'] for s in client.children(session['id'])])
                self.assertEqual(client.session(child['id'])['title'], child['title'])
                probe = "from pathlib import Path; assert Path('/work/notes.txt').read_text() == 'Persistir á'; assert Path('/inputs/fixture.csv').read_text() == 'units\\n2\\n3\\n'"
                second._docker('exec', second.container_id, 'python', '-I', '-S', '-c', probe)
                denied = second._docker('exec', second.container_id, 'python', '-I', '-S', '-c', "from pathlib import Path; Path('/inputs/fixture.csv').write_text('changed')", check=False)
                self.assertNotEqual(denied.returncode, 0)
                with self.assertRaises(ValueError):
                    second.restore(snapshot)
            with self.assertRaises(ValueError):
                first.capture(snapshot)
            (snapshot / 'work/notes.txt').write_text('corrupt')
            with self.assertRaises(ValueError):
                inspect_snapshot(snapshot, run_id=run, image=image)
            third = runtime()
            with self.assertRaises(ValueError):
                third.restore(snapshot)
            self.assertIsNone(third._inspect())


if __name__ == '__main__':
    unittest.main()
