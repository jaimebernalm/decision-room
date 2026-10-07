"""Real isolated container to loopback HTTP/SSE, with a simulated product service."""
import base64
import json
import io
from types import SimpleNamespace
from unittest.mock import Mock
import os
import subprocess
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from uuid import uuid4

from decision_room.engine.tunnel import JobTunnel
from decision_room.engine.client import ProtocolError
from tests.test_engine_image import isolated_server


class TunnelTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('DECISION_ROOM_ENGINE_IMAGE_ID'), 'Build the pinned image for real relay transport tests.')
    def test_mcp_json_sse_concurrency_and_foreign_routes_without_external_network(self):
        run_id = str(uuid4()); seen = []; lock = threading.Lock()
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass
            def do_POST(self):
                raw = self.rfile.read(int(self.headers['content-length']))
                with lock:
                    seen.append({'path': self.path, 'token': self.headers.get('Authorization'), 'raw': raw})
                if self.headers.get('Authorization') != 'Bearer fixture-job-token':
                    self.send_response(403); self.end_headers(); return
                self.send_response(200)
                streaming = self.path.endswith('/responses')
                self.send_header('Content-Type', 'text/event-stream' if streaming else 'application/json')
                self.end_headers()
                if streaming:
                    for chunk in [b'data: {"text":"', 'á'.encode(), b'"}\n\ndata: [DONE]\n\n']:
                        self.wfile.write(chunk); self.wfile.flush()
                else:
                    self.wfile.write(json.dumps({'echo': json.loads(raw)}, ensure_ascii=False).encode())
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True); worker.start()
        try:
            with isolated_server(os.environ['DECISION_ROOM_ENGINE_IMAGE_ID']) as (_, backend, container_id):
                with JobTunnel(backend, container_id, run_id, f'http://127.0.0.1:{server.server_port}') as tunnel:
                    script = r'''
import concurrent.futures,json,sys,urllib.request,urllib.error
run_id=sys.argv[1]
def request(path,auth=True):
 body=json.dumps({'text':'á & <fixture>','rows':[1,2,3]}).encode()
 headers={'Content-Type':'application/json','Accept':'application/json, text/event-stream'}
 if auth:headers['Authorization']='Bearer fixture-job-token'
 req=urllib.request.Request('http://127.0.0.1:8080'+path,headers=headers,data=body)
 try:
  with urllib.request.urlopen(req,timeout=10) as response:return [response.status,response.read().decode()]
 except urllib.error.HTTPError as error:return [error.code,'']
with concurrent.futures.ThreadPoolExecutor(3) as pool:
 values=list(pool.map(request,['/jobs/'+run_id+'/mcp','/jobs/'+run_id+'/v1/responses','/jobs/'+run_id+'/mcp']))
assert json.loads(values[0][1])['echo']['text']=='á & <fixture>'
assert values[1]==[200,'data: {"text":"á"}\n\ndata: [DONE]\n\n']
assert request('/jobs/'+run_id+'/mcp',False)[0]==403
for path in ['/private','/jobs/00000000-0000-0000-0000-000000000000/mcp','/jobs/'+run_id+'/mcp?override=1']:
 assert request(path)[0]==403
print('JSON, SSE and job route isolation OK')
'''
                    result = subprocess.run([*backend.prefix, 'exec', container_id, 'python', '-I', '-S', '-c', script, run_id],
                        capture_output=True, text=True, timeout=30, env=backend.cli_env)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('isolation OK', result.stdout)
                    tunnel.check()
                    tunnel.process.kill()
                    tunnel.process.wait(timeout=5)
                    with self.assertRaises(ProtocolError):
                        tunnel.check()
                # Only the four permitted paths reached the host, including one
                # unauthorized request rejected by the product's own boundary.
                self.assertEqual(len(seen), 4)
                self.assertTrue(all(r['path'].startswith('/jobs/' + run_id + '/') for r in seen))
                self.assertEqual(sum(r['token'] == 'Bearer fixture-job-token' for r in seen), 3)
        finally:
            server.shutdown(); server.server_close(); worker.join(timeout=2)

    def test_host_boundary_rejects_forged_routes_headers_and_frames(self):
        run_id = str(uuid4())
        valid = {'type': 'request', 'id': 'b' * 32, 'path': f'/jobs/{run_id}/mcp',
                 'headers': {'content-type': 'application/json'}, 'body': base64.b64encode(b'{}').decode()}
        for change in [{'path': '/private'}, {'path': '/jobs/' + str(uuid4()) + '/mcp'},
                       {'headers': {'host': 'foreign.invalid'}}, {'headers': {'authorization': 'x\r\nHost: foreign'}},
                       {'body': '%%%invalid-base64'}, {'type': 'execute'}, {'id': '../unexpected'}]:
            with self.subTest(change=change):
                tunnel = JobTunnel(None, 'a' * 64, run_id, 'http://127.0.0.1:1234')
                try:
                    tunnel.process = SimpleNamespace(stdout=io.BytesIO(
                        b'{"type":"ready"}\n' + json.dumps({**valid, **change}).encode() + b'\n'))
                    tunnel._forward = Mock()
                    tunnel._read()
                    tunnel._forward.assert_not_called()
                    self.assertTrue(tunnel.failed.is_set())
                finally:
                    tunnel.http.close()

    def test_configuration_cannot_select_external_service_or_container_name(self):
        for origin in ['http://example.com:8080', 'http://127.0.0.1:8080/private',
                       'http://user:secret@127.0.0.1:8080', 'https://127.0.0.1:8080']:
            with self.assertRaises(ValueError):
                JobTunnel(None, 'a' * 64, uuid4(), origin)
        with self.assertRaises(ValueError):
            JobTunnel(None, 'mutable-container-name', uuid4(), 'http://127.0.0.1:8080')


if __name__ == '__main__':
    unittest.main()
