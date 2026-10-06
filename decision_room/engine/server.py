"""Internal service HTTP boundary. Opt-in only; not mounted on the web app."""
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import admission, gateway, proxy


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, config, address=('127.0.0.1', 0), *, api_key='', transport=None, backend=None):
        self.config, self.api_key, self.transport, self.backend = config, api_key, transport, backend
        super().__init__(address, Handler)
        self.origin = f'http://{address[0]}:{self.server_port}'

    def handle_error(self, request, client_address):
        # Never dump a request, token, provider response or customer data.
        pass


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(30)
        self.headers_sent = False

    def log_message(self, *args):
        pass

    def send(self, status, body=None):
        raw = b'' if body is None else admission.canonical(body)
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Connection', 'close')
        self.end_headers()
        self.headers_sent = True
        self.close_connection = True
        self.wfile.write(raw)

    def stream_headers(self, status, content_type):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Connection', 'close')
        self.end_headers()
        self.headers_sent = True
        self.close_connection = True

    def write_chunk(self, chunk):
        self.wfile.write(chunk)
        self.wfile.flush()

    def handle_job(self):
        if self.headers.get('Origin') not in (None, self.server.origin):
            raise admission.Denied('Origin is not allowed.')
        match = re.fullmatch(r'/jobs/([0-9a-f-]{36})/(mcp|v1/responses)', self.path)
        auth = self.headers.get('Authorization', '')
        if not match or not auth.startswith('Bearer '):
            raise admission.Denied('Invalid job endpoint or credential.')
        run_id, endpoint = match.groups()
        token = auth[7:]
        admission.authenticate(self.server.config, run_id, token)
        if self.command != 'POST':
            self.send(405)
            return
        if self.headers.get('Transfer-Encoding') or len(self.headers.get_all('Content-Length', [])) != 1:
            raise ValueError('A single Content-Length is required.')
        length = int(self.headers['Content-Length'])
        maximum = proxy.MAX_REQUEST_BYTES if endpoint == 'v1/responses' else 256 * 1024
        if not 0 < length <= maximum:
            self.send(413)
            return
        if self.headers.get('Content-Type', '').split(';')[0].lower() != 'application/json':
            self.send(415)
            return
        raw = self.rfile.read(length)
        if len(raw) != length:
            raise ValueError('Incomplete request body.')
        if endpoint == 'mcp':
            if self.headers.get('MCP-Protocol-Version', '2025-03-26') not in gateway.VERSIONS:
                raise ValueError('Unsupported MCP protocol version.')
            accepted = self.headers.get('Accept', '')
            if 'application/json' not in accepted or 'text/event-stream' not in accepted:
                self.send(406)
                return
            result = gateway.dispatch(self.server.config, run_id, token, json.loads(raw), backend=self.server.backend)
            self.send(202 if result is None else 200, result)
        else:
            proxy.forward(self.server.config, run_id, token, raw, api_key=self.server.api_key,
                          send_headers=self.stream_headers, write=self.write_chunk, transport=self.server.transport)

    def do_POST(self):
        try:
            self.handle_job()
        except admission.Aborted:
            if not self.headers_sent:
                self.send(429, {'error': 'Job stopped; persisted state retained.'})
        except admission.Denied:
            if not self.headers_sent:
                self.send(403, {'error': 'Job access denied.'})
        except (ValueError, UnicodeError, RecursionError):
            if not self.headers_sent:
                self.send(400, {'error': 'Invalid request.'})
        except Exception:
            if not self.headers_sent:
                self.send(502, {'error': 'Service request failed; persisted state retained.'})
        finally:
            self.close_connection = True

    do_GET = do_POST
    do_DELETE = do_POST
