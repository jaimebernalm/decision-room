"""Trusted relay from a job's isolated HTTP loopback to the host product service.

No host port is exposed to the container. The agent has only a Docker-exec pipe,
not the Docker socket. The destination is an operator-supplied loopback origin;
frames cannot select a host, method, business, job or other service route. Both
MCP JSON and Responses SSE retain their normal HTTP authentication and framing.
"""
import base64
import json
from pathlib import Path
import re
import subprocess
import threading
from urllib.parse import urlsplit
from uuid import UUID

import httpx

from .client import ProtocolError

MAX_FRAME = 6 * 1024 * 1024
HEADERS = {'authorization', 'accept', 'content-type', 'mcp-protocol-version', 'origin'}


class JobTunnel:
    def __init__(self, backend, container_id, run_id, service_origin):
        parsed = urlsplit(service_origin)
        if (parsed.scheme != 'http' or parsed.hostname != '127.0.0.1' or not parsed.port
                or parsed.path not in ('', '/') or parsed.query or parsed.fragment or parsed.username):
            raise ValueError('The tunnel requires a trusted loopback product service.')
        if not re.fullmatch(r'[0-9a-f]{64}', container_id):
            raise ValueError('Use an immutable engine container ID.')
        self.run_id = str(UUID(str(run_id)))
        self.backend, self.container_id = backend, container_id
        self.origin = service_origin.rstrip('/')
        self.process = None
        self.ready = threading.Event()
        self.stopped = threading.Event()
        self.failed = threading.Event()
        self.write_lock = threading.Lock()
        self.pending_lock = threading.Lock()
        self.pending = set()
        self.http = httpx.Client(trust_env=False, follow_redirects=False,
                                 timeout=httpx.Timeout(120, connect=3), limits=httpx.Limits(max_connections=8))

    def start(self):
        if self.process is not None:
            raise ValueError('Tunnel already started.')
        script = Path(__file__).resolve().parents[2] / 'engine/opencode/relay.py'
        self.process = subprocess.Popen([*self.backend.prefix, 'exec', '-i', self.container_id,
            'python', '-I', '-S', '-c', script.read_text(), self.run_id],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=self.backend.cli_env)
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()
        if not self.ready.wait(10) or self.failed.is_set():
            self.close()
            raise ProtocolError('Job HTTP tunnel failed to start.')
        return self

    def __enter__(self):
        return self.start()

    def __exit__(self, *_):
        self.close()

    def check(self):
        if self.failed.is_set() or self.process is None or self.process.poll() is not None:
            raise ProtocolError('Job HTTP tunnel stopped; preserve state and reconcile.')

    def _send(self, value):
        raw = json.dumps(value, separators=(',', ':')).encode() + b'\n'
        if len(raw) > 256 * 1024:
            raise ProtocolError('Tunnel response frame exceeds its limit.')
        with self.write_lock:
            if self.stopped.is_set():
                raise ProtocolError('Tunnel is stopping.')
            self.process.stdin.write(raw)
            self.process.stdin.flush()

    def _read(self):
        try:
            while not self.stopped.is_set():
                raw = self.process.stdout.readline(MAX_FRAME + 1)
                if not raw or len(raw) > MAX_FRAME or not raw.endswith(b'\n'):
                    raise ProtocolError('Tunnel request stream ended or exceeded its limit.')
                value = json.loads(raw)
                if value == {'type': 'ready'} and not self.ready.is_set():
                    self.ready.set()
                    continue
                if not self.ready.is_set() or not isinstance(value, dict) or set(value) != {'type', 'id', 'path', 'headers', 'body'}:
                    raise ProtocolError('Invalid tunnel request frame.')
                request_id = value['id']
                if value['type'] != 'request' or not isinstance(request_id, str) or not re.fullmatch('[a-f0-9]{32}', request_id):
                    raise ProtocolError('Invalid tunnel request identity.')
                if value['path'] not in (f'/jobs/{self.run_id}/mcp', f'/jobs/{self.run_id}/v1/responses'):
                    raise ProtocolError('Tunnel route is outside this job.')
                headers = value['headers']
                if (not isinstance(headers, dict) or set(headers) - HEADERS
                        or any(not isinstance(v, str) or '\r' in v or '\n' in v for v in headers.values())
                        or sum(len(k) + len(v) for k, v in headers.items()) > 4096):
                    raise ProtocolError('Invalid tunnel request headers.')
                body = base64.b64decode(value['body'], validate=True)
                if not 0 < len(body) <= 4 * 1024 * 1024:
                    raise ProtocolError('Tunnel request body exceeds its limit.')
                with self.pending_lock:
                    if request_id in self.pending or len(self.pending) >= 8:
                        raise ProtocolError('Tunnel request identity reused or capacity exceeded.')
                    self.pending.add(request_id)
                worker = threading.Thread(target=self._forward, args=(request_id, value['path'], headers, body), daemon=True)
                worker.start()
        except Exception:
            if not self.stopped.is_set():
                self.failed.set()
            self.ready.set()

    def _forward(self, request_id, path, headers, body):
        try:
            with self.http.stream('POST', self.origin + path, headers=headers, content=body) as response:
                content_type = response.headers.get('content-type', 'application/octet-stream')
                if len(content_type) > 256 or '\r' in content_type or '\n' in content_type:
                    raise ProtocolError('Invalid product service content type.')
                self._send({'type': 'headers', 'id': request_id, 'status': response.status_code, 'content_type': content_type})
                for chunk in response.iter_raw(chunk_size=None):
                    for offset in range(0, len(chunk), 65536):
                        self._send({'type': 'chunk', 'id': request_id,
                                    'body': base64.b64encode(chunk[offset:offset+65536]).decode()})
            self._send({'type': 'end', 'id': request_id})
        except Exception:
            # No retry: a provider call or MCP mutation may already be admitted.
            self.failed.set()
            try:
                self._send({'type': 'error', 'id': request_id})
            except Exception:
                pass
        finally:
            with self.pending_lock:
                self.pending.discard(request_id)

    def close(self):
        if self.stopped.is_set():
            return
        self.stopped.set()
        if self.process:
            # Closing stdin makes the relay exit. Kill the local CLI if its pipe
            # is stuck; the container owner remains responsible for termination.
            if self.process.poll() is None:
                self.process.kill()
            self.process.wait(timeout=5)
            self.process.stdin.close()
            self.process.stdout.close()
            if hasattr(self, 'reader'):
                self.reader.join(timeout=2)
        self.http.close()
