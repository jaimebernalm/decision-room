"""Untrusted-side HTTP relay. Only job HTTP crosses the Docker exec pipe.

The trusted host validates every frame again. This process has no provider key,
Docker socket, database access or host network. Stdout is framed protocol only.
"""
import base64
import json
import queue
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from uuid import UUID, uuid4

RUN = str(UUID(sys.argv[1]))
MAX_BODY = 4 * 1024 * 1024
MAX_FRAME = 6 * 1024 * 1024
LOCK = threading.Lock()
PENDING_LOCK = threading.Lock()
PENDING = {}


def send(value):
    raw = json.dumps(value, separators=(',', ':')).encode() + b'\n'
    if len(raw) > MAX_FRAME:
        raise ValueError('Frame too large.')
    with LOCK:
        sys.stdout.buffer.write(raw)
        sys.stdout.buffer.flush()


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def log_message(self, *_):
        pass

    def do_POST(self):
        if self.path not in (f'/jobs/{RUN}/mcp', f'/jobs/{RUN}/v1/responses'):
            self.send_error(403)
            return
        if self.headers.get('Transfer-Encoding') or len(self.headers.get_all('Content-Length', [])) != 1:
            self.send_error(400)
            return
        try:
            size = int(self.headers['Content-Length'])
            if not 0 < size <= MAX_BODY:
                self.send_error(413)
                return
            raw = self.rfile.read(size)
            if len(raw) != size:
                self.send_error(400)
                return
            headers = {k.lower(): v for k, v in self.headers.items()
                       if k.lower() in ('authorization', 'accept', 'content-type', 'mcp-protocol-version', 'origin')}
            if sum(len(k) + len(v) for k, v in headers.items()) > 4096:
                self.send_error(431)
                return
            request_id, inbox = uuid4().hex, queue.Queue(maxsize=16)
            with PENDING_LOCK:
                if len(PENDING) >= 8:
                    self.send_error(503)
                    return
                PENDING[request_id] = inbox
            started = False
            try:
                send({'type': 'request', 'id': request_id, 'path': self.path,
                      'headers': headers, 'body': base64.b64encode(raw).decode()})
                while True:
                    item = inbox.get(timeout=120)
                    if item['type'] == 'headers' and not started:
                        self.send_response(item['status'])
                        self.send_header('Content-Type', item['content_type'])
                        self.send_header('Cache-Control', 'no-store')
                        self.send_header('Connection', 'close')
                        self.end_headers()
                        started = True
                    elif item['type'] == 'chunk' and started:
                        self.wfile.write(base64.b64decode(item['body'], validate=True))
                        self.wfile.flush()
                    elif item['type'] == 'end':
                        return
                    else:
                        raise ValueError('Relay stream interrupted.')
            except (OSError, ValueError, queue.Empty):
                if not started:
                    self.send_error(502)
            finally:
                with PENDING_LOCK:
                    PENDING.pop(request_id, None)
                self.close_connection = True
        except (OSError, ValueError):
            self.close_connection = True

    def do_GET(self):
        self.send_error(403)

    do_PUT = do_DELETE = do_PATCH = do_OPTIONS = do_GET


server = ThreadingHTTPServer(('127.0.0.1', 8080), Handler)
server.daemon_threads = True
threading.Thread(target=server.serve_forever, daemon=True).start()
send({'type': 'ready'})
try:
    while True:
        raw = sys.stdin.buffer.readline(256 * 1024 + 1)
        if not raw:
            break
        if len(raw) > 256 * 1024 or not raw.endswith(b'\n'):
            break
        value = json.loads(raw)
        with PENDING_LOCK:
            inbox = PENDING.get(value.get('id'))
        if inbox:
            try:
                inbox.put(value, timeout=15)
            except queue.Full:
                break
finally:
    server.shutdown()
    server.server_close()
