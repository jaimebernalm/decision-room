"""Small Python client for the pinned OpenCode 1.18.34 HTTP API.

Mutations are never automatically retried. A prompt timeout is ambiguous: the
controller must reconcile its durable message ID before deciding what to do.
SSE is advisory; reconnecting cannot substitute for reading persisted messages.
"""
import json
import re
from urllib.parse import urlsplit

import httpx

VERSION = '1.18.34'
MAX_RESPONSE = 32 * 1024 * 1024
MAX_EVENT = 1024 * 1024


class ProtocolError(RuntimeError):
    pass


class DeliveryUncertain(ProtocolError):
    pass


def _identifier(value, prefix):
    if not isinstance(value, str) or not re.fullmatch(prefix + r'[A-Za-z0-9_]{1,128}', value):
        raise ValueError('Invalid OpenCode identifier.')
    return value


class Events:
    """Bound each event and decode only complete SSE data blocks."""
    def __init__(self):
        self.pending = b''
        self.data = []
        self.size = 0

    def feed(self, chunk):
        self.pending += chunk
        if len(self.pending) + self.size > MAX_EVENT:
            raise ProtocolError('OpenCode event exceeds the byte limit.')
        events = []
        while b'\n' in self.pending:
            line, self.pending = self.pending.split(b'\n', 1)
            line = line.rstrip(b'\r')
            if not line:
                if self.data:
                    try:
                        value = json.loads(b'\n'.join(self.data))
                    except (ValueError, UnicodeError, RecursionError):
                        raise ProtocolError('Malformed OpenCode event.') from None
                    if not isinstance(value, dict):
                        raise ProtocolError('Malformed OpenCode event.')
                    events.append(value)
                self.data, self.size = [], 0
            elif line.startswith(b'data:'):
                part = line[5:].lstrip()
                self.data.append(part)
                self.size += len(part)
        return events


class Client:
    def __init__(self, base_url, password, *, directory='/work', timeout=30, transport=None):
        parsed = urlsplit(base_url)
        if (parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username
                or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('', '/')):
            raise ValueError('Provide a trusted OpenCode server origin.')
        if not isinstance(password, str) or not password:
            raise ValueError('OpenCode server password is required.')
        self.directory = directory
        self.http = httpx.Client(base_url=base_url, auth=('opencode', password),
                                 trust_env=False, follow_redirects=False, timeout=timeout,
                                 transport=transport)

    def close(self):
        self.http.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def _request(self, method, path, *, body=None, missing=False, params=None):
        query = {'directory': self.directory, **(params or {})}
        try:
            with self.http.stream(method, path, params=query, json=body) as response:
                if missing and response.status_code == 404:
                    return None
                if response.status_code not in (200, 204):
                    # Do not include a private server body, password or prompt.
                    raise ProtocolError(f'OpenCode request failed ({response.status_code}).')
                raw = bytearray()
                for chunk in response.iter_bytes():
                    raw.extend(chunk)
                    if len(raw) > MAX_RESPONSE:
                        raise ProtocolError('OpenCode response exceeds the byte limit.')
                if response.status_code == 204:
                    return None
                try:
                    return json.loads(raw)
                except (ValueError, UnicodeError, RecursionError):
                    raise ProtocolError('Malformed OpenCode response.') from None
        except httpx.TransportError:
            error = DeliveryUncertain if method != 'GET' else ProtocolError
            raise error('OpenCode transport failed; reconcile persisted state before retrying.') from None

    def health(self):
        value = self._request('GET', '/global/health')
        if not isinstance(value, dict) or value.get('healthy') is not True or value.get('version') != VERSION:
            raise ProtocolError('Unexpected OpenCode version or health state.')
        return value

    def create_session(self, *, title, model, provider='openai', variant='low'):
        if not isinstance(title, str) or not title.strip():
            raise ValueError('A nonempty session title is required.')
        value = self._request('POST', '/session', body={
            'title': title, 'model': {'id': model, 'providerID': provider, 'variant': variant}})
        if not isinstance(value, dict):
            raise ProtocolError('Malformed created session.')
        _identifier(value.get('id'), 'ses')
        return value

    def session(self, session_id):
        return self._request('GET', '/session/' + _identifier(session_id, 'ses'))

    def submit(self, session_id, *, message_id, text, model, provider='openai', variant='low'):
        # message_id must already be in the controller's outbox before this call.
        session_id = _identifier(session_id, 'ses')
        message_id = _identifier(message_id, 'msg')
        if not isinstance(text, str) or not text.strip():
            raise ValueError('A nonempty prompt is required.')
        self._request('POST', f'/session/{session_id}/prompt_async', body={
            'messageID': message_id, 'model': {'providerID': provider, 'modelID': model},
            'variant': variant, 'parts': [{'type': 'text', 'text': text}]})

    def message(self, session_id, message_id):
        session_id, message_id = _identifier(session_id, 'ses'), _identifier(message_id, 'msg')
        return self._request('GET', f'/session/{session_id}/message/{message_id}', missing=True)

    def messages(self, session_id, *, before=None, limit=100):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('Message pages must contain 1–100 messages.')
        params = {'limit': limit}
        if before is not None:
            params['before'] = _identifier(before, 'msg')
        return self._request('GET', '/session/' + _identifier(session_id, 'ses') + '/message', params=params)

    def children(self, session_id):
        return self._request('GET', '/session/' + _identifier(session_id, 'ses') + '/children')

    def statuses(self):
        return self._request('GET', '/session/status')

    def abort(self, session_id):
        return self._request('POST', '/session/' + _identifier(session_id, 'ses') + '/abort')

    def events(self):
        parser = Events()
        try:
            with self.http.stream('GET', '/event', params={'directory': self.directory},
                                  headers={'Accept': 'text/event-stream'}) as response:
                if response.status_code != 200 or not response.headers.get('content-type', '').startswith('text/event-stream'):
                    raise ProtocolError('OpenCode event stream unavailable.')
                for chunk in response.iter_bytes():
                    yield from parser.feed(chunk)
        except httpx.TransportError:
            raise ProtocolError('OpenCode event stream interrupted; reconcile session state.') from None
        # A disconnected/truncated stream is not proof of successful completion.
        raise ProtocolError('OpenCode event stream ended; reconcile session state.')
