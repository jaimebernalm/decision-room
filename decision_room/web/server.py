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
from .service import MAX_UPLOAD, MAX_BATCH_UPLOAD, WebError

STATIC = Path(__file__).with_name('dist')
CSP = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'self'"


def access_key(config, name='.web-access-key'):
    path = config.storage / name
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

    def __init__(self, workspace, port=8787, token=None, *, internal_monitor=False, internal_token=None):
        self.workspace = workspace
        self.token = token or access_key(workspace.config)
        super().__init__(('127.0.0.1', port), Handler)
        self.origin = f'http://127.0.0.1:{self.server_port}'
        self.cookie_name = f'dr_session_{self.server_port}'
        self.internal_cookie_name = f'dr_internal_{self.server_port}'
        self.internal_token = (internal_token or access_key(workspace.config, '.internal-access-key')) if internal_monitor else None
        if self.internal_token and hmac.compare_digest(self.internal_token, self.token):
            self.server_close()
            raise ValueError('Internal access key must differ from customer access key.')


class Handler(BaseHTTPRequestHandler):
    server_version = 'DecisionRoom'

    def log_message(self, format, *args):
        # URLs, answers and access keys must not enter HTTP logs.
        pass

    def setup(self):
        super().setup()
        self.connection.settimeout(30)

    def send(self, status, body, content_type='application/json; charset=utf-8', headers=None):
        if body is None or isinstance(body, (dict, list)):
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

    def send_pdf(self, report):
        from ..report_pdf import render_pdf
        self.send(200, render_pdf(report), 'application/pdf',
                  headers={'Content-Disposition': 'attachment; filename="decision-room-informe.pdf"'})

    def send_file(self, path, name):
        self.send_response(200)
        self.send_header('Content-Type', 'application/octet-stream')
        self.send_header('Content-Length', str(path.stat().st_size))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Disposition', "attachment; filename*=UTF-8''" + quote(name))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        with path.open('rb') as stream:
            while chunk := stream.read(1024 * 1024):
                self.wfile.write(chunk)

    def authenticated(self, internal=False):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get('Cookie', ''))
            name = self.server.internal_cookie_name if internal else self.server.cookie_name
            value = cookie[name].value if name in cookie else ''
            return hmac.compare_digest(value, (self.server.internal_token if internal else self.server.token) or '') and bool(value)
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

    def json_body(self, limit=24_000):
        if self.headers.get_content_type() != 'application/json':
            raise WebError('Se esperaba una petición JSON.')
        try:
            data = json.loads(self.body(limit))
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
            if not mutation and (path == '/' or path.startswith('/assets/')):
                name = 'index.html' if path == '/' else path.lstrip('/')
                target = (STATIC / name).resolve()
                if not target.is_relative_to(STATIC.resolve()) or not target.is_file():
                    raise WebError('Compila la interfaz con npm --prefix frontend run build.' if path == '/' else 'Archivo no encontrado.', 503 if path == '/' else 404)
                mime = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
                        '.css': 'text/css; charset=utf-8', '.woff2': 'font/woff2', '.svg': 'image/svg+xml'}.get(target.suffix)
                if not mime:
                    raise WebError('Archivo no encontrado.', 404)
                self.send(200, target.read_bytes(), mime)
                return
            if mutation and path == '/api/login':
                token = self.json_body().get('token', '')
                if not isinstance(token, str) or not hmac.compare_digest(token, self.server.token):
                    raise WebError('La clave de acceso no es correcta.', 401)
                self.send(200, {'ok': True}, headers={'Set-Cookie': f'{self.server.cookie_name}={self.server.token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=2592000'})
                return
            if path.startswith('/api/internal/'):
                if not self.server.internal_token:
                    raise WebError('Monitor interno no disponible.', 404)
                if mutation and path == '/api/internal/login':
                    token = self.json_body().get('token', '')
                    if not isinstance(token, str) or not hmac.compare_digest(token, self.server.internal_token):
                        raise WebError('La clave interna no es correcta.', 401)
                    self.send(200, {'ok': True}, headers={'Set-Cookie': f'{self.server.internal_cookie_name}={self.server.internal_token}; HttpOnly; SameSite=Strict; Path=/api/internal; Max-Age=28800'})
                    return
                if not self.authenticated(internal=True):
                    raise WebError('Introduce la clave interna para abrir el monitor.', 401)
                if path == '/api/internal/logout' and mutation:
                    self.json_body()
                    self.send(200, {'ok': True}, headers={'Set-Cookie': f'{self.server.internal_cookie_name}=; HttpOnly; SameSite=Strict; Path=/api/internal; Max-Age=0'})
                    return
                if mutation:
                    raise WebError('El monitor es de consulta.', 405)
                if path == '/api/internal/session':
                    self.send(200, {'authorized': True})
                    return
                from . import internal_monitor
                parts = path.strip('/').split('/')
                query = parse_qs(urlsplit(self.path).query)
                ws = self.server.workspace
                if parts == ['api','internal','investigations']:
                    self.send(200, internal_monitor.listing(ws, query))
                    return
                if len(parts) == 4 and parts[:3] == ['api','internal','investigations']:
                    self.send(200, internal_monitor.read(ws, parts[3], query))
                    return
                if len(parts) == 5 and parts[:3] == ['api','internal','investigations'] and parts[4] == 'events':
                    self.send(200, internal_monitor.read(ws, parts[3], query))
                    return
                if len(parts) == 6 and parts[:3] == ['api','internal','investigations']:
                    self.send(200, internal_monitor.detail(ws, parts[3], parts[4], parts[5], event_id=query.get('event_id', [None])[0]))
                    return
                raise WebError('Operación interna no encontrada.', 404)
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
            if mutation and path == '/api/onboarding/complete':
                self.json_body()
                self.send(200, ws.complete_onboarding())
                return
            if mutation and path == '/api/onboarding/restart':
                self.json_body()
                self.send(200, ws.restart_onboarding())
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
            if path in ('/api/onboarding/session', '/api/onboarding/start', '/api/onboarding/change', '/api/onboarding/data'):
                from . import onboarding
                if path.endswith('/data') and not mutation:
                    from .preview import dataset_page
                    state = onboarding.read(ws)
                    if not state or not state['analysis_id']:
                        raise WebError('Todavía no has compartido datos.', 409)
                    self.send(200, dataset_page(ws, state['analysis_id'], parse_qs(urlsplit(self.path).query)))
                elif path.endswith('/session') and not mutation:
                    self.send(200, onboarding.read(ws))
                elif mutation and path.endswith('/start'):
                    self.send(200, onboarding.start(ws, self.json_body()))
                elif mutation and path.endswith('/change'):
                    self.send(200, onboarding.change(ws, self.json_body()))
                else:
                    raise WebError('Operación no disponible.', 404)
                return
            if path == '/api/chats' or path.startswith('/api/chats/'):
                from ..conversations import Conversations
                chats = Conversations(ws)
                parts = path.strip('/').split('/')
                if len(parts) == 2:
                    self.send(202 if mutation else 200, chats.create(self.json_body()) if mutation else chats.listing())
                    return
                chat_id = parts[2]
                if not mutation and len(parts) == 6 and parts[3] == 'turns' and parts[5] == 'activity':
                    from . import activity
                    self.send(200, activity.read(ws, 'turn', parts[4], parse_qs(urlsplit(self.path).query), chat_id=chat_id))
                    return
                action = parts[3] if len(parts) == 4 else ''
                if len(parts) == 3 and not mutation:
                    self.send(200, chats.detail(chat_id))
                    return
                if mutation and action in ('messages','retry','report','resolve','delete'):
                    data = self.json_body()
                    result = (chats.delete(chat_id,data) if action == 'delete' else
                              chats.send(chat_id,data) if action == 'messages' else
                              chats.resolve(chat_id,data) if action == 'resolve' else
                              chats.retry(chat_id,data.get('turn_id'),data) if action == 'retry' else
                              chats.report(chat_id,data.get('turn_id'),data))
                    self.send(202,result)
                    return
                if not mutation and len(parts) == 5 and parts[3] == 'presentation':
                    self.send(200, chats.report(chat_id, parts[4], structured=True))
                    return
                if not mutation and len(parts) == 5 and parts[3] == 'pdf':
                    self.send_pdf(chats.report(chat_id, parts[4], structured=True))
                    return
                if not mutation and len(parts) == 5 and parts[3] == 'report':
                    self.send(200,chats.report(chat_id,parts[4]),'text/html; charset=utf-8')
                    return
                raise WebError('Operación de conversación no encontrada.',404)
            if path == '/api/business/data-model':
                from . import data_model
                if mutation:
                    self.send(200, data_model.change(ws, self.json_body()))
                else:
                    query = parse_qs(urlsplit(self.path).query)
                    revision = query.get('revision', [None])[0]
                    if revision is not None and (not revision.isdigit() or int(revision) < 1):
                        raise WebError('Revisión no válida.')
                    self.send(200, data_model.read(ws, query.get('analysis_id', [''])[0], int(revision) if revision else None))
                return
            from . import dossier, bundles
            if path == '/api/business/dossier' and not mutation:
                self.send(200, dossier.listing(ws))
                return
            if path == '/api/business/memory' and mutation:
                self.send(200, dossier.change(ws, self.json_body()))
                return
            if path == '/api/datasets' and mutation:
                self.send(200, dossier.upload(ws, *self.multipart()))
                return
            if path == '/api/datasets/bundles' and mutation:
                self.send(200, bundles.start(ws, self.json_body(bundles.MANIFEST_BYTES)))
                return
            bundle_parts = path.strip('/').split('/')
            if len(bundle_parts) >= 4 and bundle_parts[:3] == ['api', 'datasets', 'bundles']:
                upload_id = bundle_parts[3]
                if len(bundle_parts) == 4 and not mutation:
                    self.send(200, bundles.status(ws, upload_id))
                    return
                if len(bundle_parts) == 5 and bundle_parts[4] == 'finish' and mutation:
                    self.json_body()
                    self.send(200, bundles.finish(ws, upload_id))
                    return
                if len(bundle_parts) == 6 and bundle_parts[4] == 'files' and mutation:
                    if self.headers.get_content_type() != 'application/octet-stream':
                        raise WebError('Se esperaba un fragmento de archivo.')
                    try:
                        index = int(bundle_parts[5])
                        offset = int(self.headers.get('X-Upload-Offset', ''))
                    except ValueError:
                        raise WebError('Indica el archivo y la posición de la carga.') from None
                    self.send(200, bundles.chunk(ws, upload_id, index, offset, self.body(bundles.CHUNK_BYTES)))
                    return
            if path.startswith('/api/datasets/file/') and not mutation:
                name, location = dossier.download_location(ws, path.rsplit('/', 1)[-1])
                self.send_file(location, name)
                return
            if path.startswith('/api/datasets/original/') and not mutation:
                requested = parse_qs(urlsplit(self.path).query).get('path', [''])[0]
                name, location = bundles.original_location(ws, path.rsplit('/', 1)[-1], requested)
                self.send_file(location, name)
                return
            if mutation and path == '/api/memory/retry':
                self.send(202, {'memory': ws.retry_memory(self.json_body())})
                return
            if path in ('/api/home', '/api/home/preferences', '/api/home/suggest'):
                from . import home
                if not mutation and path == '/api/home':
                    self.send(200, home.view(ws))
                    return
                if mutation and path in ('/api/home/preferences', '/api/home/suggest'):
                    operation = home.save if path.endswith('/preferences') else home.suggest
                    self.send(200, operation(ws, self.json_body()))
                    return
            if not mutation and path == '/api/dashboard':
                requested = parse_qs(urlsplit(self.path).query).get('report', [None])
                self.send(200, ws.dashboard(requested[0]))
                return
            if not mutation and path == '/api/reports/deleted':
                self.send(200, {'items': ws.listing(deleted=True)})
                return
            if mutation and path == '/api/jobs/stage':
                self.close_connection = True
                requested = parse_qs(urlsplit(self.path).query).get('filename', [''])[0]
                try:
                    length = int(self.headers.get('Content-Length', '0'))
                except ValueError:
                    raise WebError('La petición no es válida.') from None
                if self.headers.get('Transfer-Encoding') or not 0 < length <= MAX_BATCH_UPLOAD:
                    raise WebError('El CSV debe tener datos y el lote no puede superar 2 GB.', 413)
                self.send(201, ws.stage_upload(requested, self.rfile, length))
                return
            if mutation and path == '/api/jobs/batch':
                self.send(202, ws.create_batch(self.json_body(2 * 1024 * 1024)))
                return
            if mutation and path == '/api/jobs':
                self.send(202, ws.create(*self.multipart()))
                return
            if mutation and path == '/api/jobs/from-dataset':
                self.send(202, ws.create_from_dataset(self.json_body()))
                return
            pieces = path.strip('/').split('/')
            if len(pieces) in (3, 4) and pieces[:2] == ['api', 'jobs']:
                job_id = pieces[2]
                action = pieces[3] if len(pieces) == 4 else ''
                if not mutation and not action:
                    self.send(200, ws.detail(job_id))
                    return
                if not mutation and action == 'activity':
                    from . import activity
                    self.send(200, activity.read(ws, 'job', job_id, parse_qs(urlsplit(self.path).query)))
                    return
                if not mutation and action == 'data':
                    from .preview import page
                    self.send(200, page(ws, job_id, parse_qs(urlsplit(self.path).query)))
                    return
                if mutation and action in ('delete', 'restore'):
                    self.send(200, ws.delete_report(job_id, self.json_body(), restore=action == 'restore'))
                    return
                if not mutation and action == 'preview':
                    params = parse_qs(urlsplit(self.path).query)
                    requested = params.get('offset', ['0'])[0]
                    try:
                        offset = int(requested)
                        file_index = int(params.get('file', ['0'])[0])
                    except ValueError:
                        raise WebError('La página de datos no es válida.') from None
                    self.send(200, ws.preview(job_id, offset, file_index))
                    return
                if mutation and action == 'answers':
                    self.send(202, ws.reply(job_id, self.json_body()))
                    return
                if mutation and action == 'retry':
                    self.json_body()
                    self.send(202, ws.retry(job_id))
                    return
                if not mutation and action == 'presentation':
                    self.send(200, ws.report(job_id, structured=True))
                    return
                if not mutation and action == 'pdf':
                    self.send_pdf(ws.report(job_id, structured=True))
                    return
                if not mutation and action == 'report':
                    self.send(200, ws.report(job_id), 'text/html; charset=utf-8')
                    return
                if not mutation and action == 'file':
                    try:
                        file_index = int(parse_qs(urlsplit(self.path).query).get('file', ['0'])[0])
                    except ValueError:
                        raise WebError('El CSV solicitado no existe.', 404) from None
                    name, path, _ = ws.download_path(job_id, file_index)
                    self.send_file(path, name)
                    return
            raise WebError('Esta página no existe.', 404)
        except WebError as error:
            self.send(error.status, {'error': str(error)})
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            self.close_connection = True
        except Exception:
            logging.getLogger(__name__).exception('Local web request failed')
            self.send(503, {'error': 'No hemos podido conectar con el servicio local. Conserva esta página y vuelve a intentarlo.'})
