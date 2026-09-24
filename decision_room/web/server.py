"""Same-origin HTTP boundary for a single, authenticated local workspace."""
import hmac
import json
import logging
import secrets
from email import policy
from email.parser import BytesParser
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlsplit

from ..config import ROOT
from .service import MAX_UPLOAD, WebError

STATIC = Path(__file__).with_name('static')
CSP = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'self'"


def access_key(config):
    path = config.storage / '.web-access-key'
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        with path.open('x') as stream:
            stream.write(secrets.token_urlsafe(32))
        path.chmod(0o600)
    except FileExistsError:
        pass
    return path.read_text().strip()


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, workspace, port=8787, token=None):
        self.workspace = workspace
        self.token = token or access_key(workspace.config)
        super().__init__(('127.0.0.1', port), Handler)
        self.origin = f'http://127.0.0.1:{self.server_port}'
        self.cookie_name = f'dr_session_{self.server_port}'


class Handler(BaseHTTPRequestHandler):
    server_version = 'DecisionRoom'

    def log_message(self, format, *args):
        # URLs, answers and access keys must not enter HTTP logs.
        pass

    def setup(self):
        super().setup()
        self.connection.settimeout(30)

    def send(self, status, body, content_type='application/json; charset=utf-8', headers=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False, default=str).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', CSP)
        self.send_header('X-Frame-Options', 'SAMEORIGIN')
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def authenticated(self):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get('Cookie', ''))
            name = self.server.cookie_name
            value = cookie[name].value if name in cookie else ''
            return hmac.compare_digest(value, self.server.token)
        except Exception:
            return False

    def body(self, limit):
        try:
            length = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            raise WebError('La petición no es válida.') from None
        if self.headers.get('Transfer-Encoding') or not 0 < length <= limit:
            self.close_connection = True
            raise WebError('El archivo o la petición superan el tamaño permitido.', 413)
        data = self.rfile.read(length)
        if len(data) != length:
            raise WebError('La subida se ha interrumpido. Vuelve a intentarlo.')
        return data

    def json_body(self):
        if self.headers.get_content_type() != 'application/json':
            raise WebError('Se esperaba una petición JSON.')
        try:
            data = json.loads(self.body(24_000))
        except (ValueError, UnicodeDecodeError):
            raise WebError('La petición no es válida.') from None
        if not isinstance(data, dict):
            raise WebError('La petición no es válida.')
        return data

    def multipart(self):
        if self.headers.get_content_type() != 'multipart/form-data':
            raise WebError('Selecciona un archivo CSV.')
        raw = self.body(MAX_UPLOAD + 50_000)
        message = BytesParser(policy=policy.default).parsebytes(
            ('Content-Type: ' + self.headers['Content-Type'] + '\r\nMIME-Version: 1.0\r\n\r\n').encode() + raw)
        parts = list(message.iter_parts())
        if len(parts) != 2:
            raise WebError('Sube un único CSV junto con los datos de tu negocio.')
        fields = {p.get_param('name', header='content-disposition'): p for p in parts}
        if set(fields) != {'metadata', 'file'}:
            raise WebError('Faltan los datos del negocio o el CSV.')
        metadata = fields['metadata'].get_payload(decode=True)
        if not metadata or len(metadata) > 24_000:
            raise WebError('La descripción es demasiado larga.')
        try:
            data = json.loads(metadata)
        except (ValueError, UnicodeDecodeError):
            raise WebError('Los datos del negocio no son válidos.') from None
        return data, fields['file'].get_filename(), fields['file'].get_payload(decode=True)

    def do_GET(self):
        self.dispatch(False)

    def do_POST(self):
        self.dispatch(True)

    def dispatch(self, mutation):
        try:
            if self.headers.get('Host') != urlsplit(self.server.origin).netloc:
                raise WebError('Accede desde la dirección local de Decision Room.', 403)
            if mutation and (self.headers.get('Origin') != self.server.origin or self.headers.get('X-Decision-Room') != '1'):
                raise WebError('La petición debe enviarse desde Decision Room.', 403)
            path = urlsplit(self.path).path
            if not mutation and path in ('/', '/app.js', '/dossier.js', '/styles.css'):
                name = {'/': 'index.html', '/app.js': 'app.js', '/dossier.js': 'dossier.js', '/styles.css': 'styles.css'}[path]
                mime = {'/': 'text/html', '/app.js': 'text/javascript', '/dossier.js': 'text/javascript', '/styles.css': 'text/css'}[path]
                self.send(200, (STATIC / name).read_bytes(), mime + '; charset=utf-8')
                return
            if mutation and path == '/api/login':
                token = self.json_body().get('token', '')
                if not isinstance(token, str) or not hmac.compare_digest(token, self.server.token):
                    raise WebError('La clave de acceso no es correcta.', 401)
                self.send(200, {'ok': True}, headers={'Set-Cookie': f'{self.server.cookie_name}={self.server.token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=2592000'})
                return
            if not self.authenticated():
                raise WebError('Introduce tu clave de acceso para abrir el espacio local.', 401)
            ws = self.server.workspace
            if not mutation and path == '/api/workspace':
                self.send(200, ws.state())
                return
            if mutation and path == '/api/business':
                self.send(200, {'business': ws.save_business(self.json_body())})
                return
            if mutation and path == '/api/business/select':
                self.send(200, {'business': ws.select_business(self.json_body())})
                return
            if not mutation and path == '/api/sample':
                sample = ROOT / 'data/reference-cases/01-daily-sales/input/sales.csv'
                # Keep the example exact and attributed to the public reference fixture.
                if not sample.exists():
                    sample = next((ROOT / 'data/reference-cases/01-daily-sales/input').glob('*.csv'))
                self.send(200, sample.read_bytes(), 'text/csv; charset=utf-8', {'Content-Disposition': 'attachment; filename="ventas-ejemplo.csv"'})
                return
            # Pin this request. A selection change in another tab must not
            # redirect a pending read/write to a different business halfway through.
            ws = ws.scoped(ws.business_id())
            if path == '/api/chats' or path.startswith('/api/chats/'):
                from ..conversations import Conversations
                chats = Conversations(ws)
                parts = path.strip('/').split('/')
                if len(parts) == 2:
                    self.send(202 if mutation else 200, chats.create(self.json_body()) if mutation else chats.listing())
                    return
                chat_id = parts[2]
                action = parts[3] if len(parts) == 4 else ''
                if len(parts) == 3 and not mutation:
                    self.send(200, chats.detail(chat_id))
                    return
                if mutation and action in ('messages','retry','report','resolve'):
                    data = self.json_body()
                    result = (chats.send(chat_id,data) if action == 'messages' else
                              chats.resolve(chat_id,data) if action == 'resolve' else
                              chats.retry(chat_id,data.get('turn_id'),data) if action == 'retry' else
                              chats.report(chat_id,data.get('turn_id'),data))
                    self.send(202,result)
                    return
                if not mutation and len(parts) == 5 and parts[3] == 'report':
                    self.send(200,chats.report(chat_id,parts[4]),'text/html; charset=utf-8')
                    return
                raise WebError('Operación de conversación no encontrada.',404)
            from . import dossier
            if path == '/api/business/dossier' and not mutation:
                self.send(200, dossier.listing(ws))
                return
            if path == '/api/business/memory' and mutation:
                self.send(200, dossier.change(ws, self.json_body()))
                return
            if path == '/api/datasets' and mutation:
                self.send(200, dossier.upload(ws, *self.multipart()))
                return
            if path.startswith('/api/datasets/file/') and not mutation:
                name, content = dossier.download(ws, path.rsplit('/', 1)[-1])
                self.send(200, content, 'text/csv; charset=utf-8', {'Content-Disposition': "attachment; filename*=UTF-8''" + quote(name)})
                return
            if mutation and path == '/api/memory/retry':
                self.send(202, {'memory': ws.retry_memory(self.json_body())})
                return
            if not mutation and path == '/api/dashboard':
                requested = parse_qs(urlsplit(self.path).query).get('report', [None])
                self.send(200, ws.dashboard(requested[0]))
                return
            if mutation and path == '/api/jobs':
                self.send(202, ws.create(*self.multipart()))
                return
            pieces = path.strip('/').split('/')
            if len(pieces) in (3, 4) and pieces[:2] == ['api', 'jobs']:
                job_id = pieces[2]
                action = pieces[3] if len(pieces) == 4 else ''
                if not mutation and not action:
                    self.send(200, ws.detail(job_id))
                    return
                if mutation and action == 'answers':
                    self.send(202, ws.reply(job_id, self.json_body()))
                    return
                if mutation and action == 'retry':
                    self.json_body()
                    self.send(202, ws.retry(job_id))
                    return
                if not mutation and action == 'report':
                    self.send(200, ws.report(job_id), 'text/html; charset=utf-8')
                    return
                if not mutation and action == 'file':
                    name, content = ws.upload(job_id)
                    self.send(200, content, 'text/csv; charset=utf-8', {'Content-Disposition': "attachment; filename*=UTF-8''" + quote(name)})
                    return
            raise WebError('Esta página no existe.', 404)
        except WebError as error:
            self.send(error.status, {'error': str(error)})
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            self.close_connection = True
        except Exception:
            logging.getLogger(__name__).exception('Local web request failed')
            self.send(503, {'error': 'No hemos podido conectar con el servicio local. Conserva esta página y vuelve a intentarlo.'})
