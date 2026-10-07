"""Finite HTTP requests to an isolated OpenCode server through Docker exec.

The host does not publish the agent port or give the agent another network.
Only the trusted controller can use its existing Docker socket; the container
never receives that socket. SSE stays on the ordinary HTTP transport. Drivers
using this local transport reconcile by polling persisted messages/status.
"""
import base64
import json
import re
import subprocess

import httpx

from .client import MAX_RESPONSE

# Isolated Python ignores /work, user site packages and injected Python env.
# No shell, redirects, external origin or arbitrary executable is accepted.
_EXCHANGE = r'''
import base64,http.client,json,sys
p=json.load(sys.stdin)
c=http.client.HTTPConnection('127.0.0.1',4096,timeout=p['timeout'])
try:
 c.request(p['method'],p['target'],body=base64.b64decode(p['body']),headers=p['headers'])
 r=c.getresponse()
 body=r.read(33554433)
 if len(body)>33554432:raise ValueError('response limit')
 print(json.dumps({'status':r.status,'headers':r.getheaders(),'body':base64.b64encode(body).decode()}))
finally:c.close()
'''


class DockerHTTPTransport(httpx.BaseTransport):
    """Use an immutable container ID resolved and ownership-checked by the driver."""
    def __init__(self, backend, container_id, *, timeout=30):
        if not re.fullmatch(r'[0-9a-f]{64}', container_id):
            raise ValueError('Use the immutable engine container ID.')
        if not 0 < timeout <= 120:
            raise ValueError('Invalid engine transport timeout.')
        self.backend, self.container_id, self.timeout = backend, container_id, timeout

    def handle_request(self, request):
        if (str(request.url.copy_with(path='/', query=None)) != 'http://127.0.0.1:4096/'
                or request.method not in ('GET', 'POST') or request.url.path == '/event'):
            raise httpx.TransportError('Local engine transport only supports finite loopback requests.')
        body = request.read()
        if len(body) > 4 * 1024 * 1024:
            raise httpx.TransportError('Engine request exceeds the byte limit.')
        payload = {'method': request.method, 'target': request.url.raw_path.decode('ascii'),
                   'headers': {k: v for k, v in request.headers.items()
                               if k in {'authorization', 'content-type', 'accept'}},
                   'body': base64.b64encode(body).decode(), 'timeout': self.timeout}
        try:
            result = subprocess.run([*self.backend.prefix, 'exec', '-i', self.container_id,
                                     'python', '-I', '-S', '-c', _EXCHANGE],
                                    input=json.dumps(payload).encode(), capture_output=True,
                                    env=self.backend.cli_env, timeout=self.timeout + 10)
            if result.returncode or len(result.stdout) > MAX_RESPONSE * 2:
                raise ValueError('Failed or oversized transport response.')
            value = json.loads(result.stdout)
            if type(value['status']) is not int or not 100 <= value['status'] <= 599:
                raise ValueError('Invalid HTTP status.')
            content = base64.b64decode(value['body'], validate=True)
            if len(content) > MAX_RESPONSE:
                raise ValueError('Oversized HTTP response.')
            # HTTPConnection has already removed transfer framing. The finite
            # response we return must not advertise chunking or stale lengths.
            headers = [(k, v) for k, v in value['headers']
                       if k.lower() not in ('transfer-encoding', 'content-length', 'connection')]
            return httpx.Response(value['status'], headers=headers, content=content, request=request)
        except (OSError, subprocess.SubprocessError, ValueError, TypeError, KeyError):
            raise httpx.TransportError('Isolated OpenCode transport failed; reconcile persisted state.') from None
