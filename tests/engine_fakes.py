"""Deterministic agent/runtime: no provider or Docker traffic."""
import sqlite3
from pathlib import Path
from uuid import uuid4
from decision_room.engine import checkpoint, questions

class FakeRuntime:
    sessions = {}
    mode = 'deliver'
    payload = b'<!doctype html><h1>Resultado</h1><p>5 unidades.</p>'
    def __init__(self, backend, **kwargs):
        self.__dict__.update(kwargs); self.container_id = '0' * 64
        self.state = self.sessions.setdefault(self.run_id, {'session': None, 'messages': []})
    def create(self): return self.container_id
    def install_files(self, part, files):
        assert part == 'inputs' and 'manifest.json' in files
        self.state['files'] = files
    def stop(self): pass
    def collect_report(self, *, filename='informe.html'):
        from decision_room.engine import file_delivery
        import base64, hashlib
        raw = self.state.get('raw')
        if raw is None: return {'status': 'missing'}
        return {'status': 'received', 'raw': raw, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    def remove(self): pass
    def restore(self, snapshot): checkpoint.inspect(snapshot)
    def capture(self, destination):
        destination = Path(destination); destination.parent.mkdir(parents=True, exist_ok=True)
        source = destination.parent / (uuid4().hex + '.db')
        with sqlite3.connect(source) as db:
            db.execute('CREATE TABLE fixture(value TEXT)')
        result = checkpoint.capture(source, destination); source.unlink(); return result
    def start(self): return FakeClient(self)


class FakeClient:
    def __init__(self, runtime): self.runtime = runtime; self.state = runtime.state
    def close(self): pass
    def require_mcp(self): pass
    def _request(self, method, path): return [self.state['session']] if self.state['session'] else []
    def create_session(self, **kwargs):
        self.state['session'] = {'id': 'ses_' + uuid4().hex, 'title': kwargs['title']}
        return self.state['session']
    def submit(self, session, *, message_id, text, model):
        def message(ident, role, content, **kwargs):
            return {'info': {'id': ident, 'sessionID': session, 'role': role, **kwargs},
                    'parts': [{'messageID': ident, 'sessionID': session, 'type': 'text', 'text': content}]}
        self.state['messages'].append(message(message_id, 'user', text))
        if self.runtime.mode == 'wait' and not any(m['info']['role'] == 'assistant' for m in self.state['messages']):
            questions.request(self.config, self.runtime.run_id, self.runtime.token,
                              request_key='need-unit', text='What unit?', reason='Missing from source')
        else:
            self.state['raw'] = self.runtime.payload
        self.state['messages'].append(message('msg_' + uuid4().hex, 'assistant', 'Trabajo guardado.',
                                            parentID=message_id, time={'completed': 1}, finish='stop'))
    def message(self, session, message_id):
        return next((m for m in self.state['messages'] if m['info']['id'] == message_id), None)
    def messages(self, session, **kwargs): return list(self.state['messages'])
    def children(self, session): return []
    def statuses(self): return {}
    def abort(self, session): return True


class FakeTunnel:
    def __init__(self, *args): pass
    def start(self): return self
    def close(self): pass
    def check(self): pass
