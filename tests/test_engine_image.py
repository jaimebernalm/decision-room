"""Opt-in real OpenCode smoke. No live provider credentials or model charges."""
from contextlib import contextmanager
import json
import os
import re
import secrets
import subprocess
import time
import unittest
from uuid import uuid4

from decision_room.docker_backend import DockerBackend
from decision_room.engine.client import Client, ProtocolError
from decision_room.engine.transport import DockerHTTPTransport


@contextmanager
def isolated_server(image_id, *, provider_unavailable=False):
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', image_id):
        raise ValueError('Use an immutable local engine image ID.')
    backend = DockerBackend()
    ident = uuid4().hex
    name, network = 'dr-engine-smoke-' + ident, 'dr-engine-smoke-net-' + ident
    password = secrets.token_urlsafe(32)
    config = {'autoupdate': False, 'share': 'disabled', 'snapshot': False,
              'model': 'openai/gpt-6-luna', 'permission': {'*': 'deny'}}
    if provider_unavailable:
        config['provider'] = {'openai': {'options': {
            'baseURL': 'http://127.0.0.1:1/v1', 'apiKey': 'unavailable-test-provider'}}}
    env = {**backend.cli_env, 'OPENCODE_SERVER_PASSWORD': password,
           'OPENCODE_CONFIG_CONTENT': json.dumps(config)}

    def docker(*args, check=True, **kwargs):
        return subprocess.run([*backend.prefix, *args], env=env, capture_output=True,
                              text=True, timeout=60, check=check, **kwargs)
    try:
        docker('network', 'create', '--internal', '--label', 'decision-room.engine-smoke=' + ident, network)
        container_id = docker('run', '-d', '--pull=never', '--name', name,
            '--label', 'decision-room.engine-smoke=' + ident, '--network', network,
            '--dns', '127.0.0.1', '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
            '--pids-limit', '512', '--memory', '2g', '--memory-swap', '2g', '--cpus', '2',
            '--user', '10001:10001', '--log-driver', 'none',
            '--tmpfs', '/tmp:rw,nosuid,nodev,size=268435456',
            '--tmpfs', '/home/agent:rw,nosuid,nodev,uid=10001,gid=10001',
            '--tmpfs', '/work:rw,nosuid,nodev,uid=10001,gid=10001',
            '--tmpfs', '/state:rw,nosuid,nodev,uid=10001,gid=10001',
            '-e', 'OPENCODE_SERVER_PASSWORD', '-e', 'OPENCODE_CONFIG_CONTENT', image_id,
            'serve', '--hostname', '0.0.0.0', '--port', '4096').stdout.strip()
        client = Client('http://127.0.0.1:4096', password,
                        transport=DockerHTTPTransport(backend, container_id, timeout=3))
        with client:
            for _ in range(25):
                try:
                    client.health()
                    break
                except ProtocolError:
                    time.sleep(1)
            else:
                raise AssertionError('Real server did not become healthy.')
            yield client, backend, container_id
    finally:
        docker('rm', '-f', name, check=False)
        docker('network', 'rm', network, check=False)


class ImageTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('DECISION_ROOM_ENGINE_IMAGE_ID'), 'Build the pinned engine image to run this smoke test.')
    def test_real_serve_auth_session_and_isolation_without_model(self):
        with isolated_server(os.environ['DECISION_ROOM_ENGINE_IMAGE_ID']) as (client, backend, container_id):
            with Client('http://127.0.0.1:4096', 'incorrect-password',
                        transport=DockerHTTPTransport(backend, container_id, timeout=3)) as wrong:
                with self.assertRaisesRegex(ProtocolError, '401'):
                    wrong.health()
            session = client.create_session(title='Engine smoke without model calls', model='gpt-6-luna')
            self.assertEqual(client.session(session['id'])['title'], 'Engine smoke without model calls')
            self.assertEqual(client.messages(session['id']), [])
            self.assertEqual(client.children(session['id']), [])
            self.assertTrue(client.abort(session['id']))
            probe = """import os,socket
assert 'OPENAI_API_KEY' not in os.environ
assert not os.path.exists('/Users')
socket.setdefaulttimeout(2)
try: socket.getaddrinfo('example.com',443)
except OSError: print('isolated')
else: raise RuntimeError('External DNS unexpectedly available')
"""
            result = subprocess.run([*backend.prefix, 'exec', container_id, 'python', '-I', '-S', '-c', probe],
                                    env=backend.cli_env, text=True, capture_output=True, timeout=10, check=True)
            self.assertEqual(result.stdout.strip(), 'isolated')


if __name__ == '__main__':
    unittest.main()
