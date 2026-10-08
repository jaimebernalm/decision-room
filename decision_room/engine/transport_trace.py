"""Bounded transport milestones, never HTTP request/response or exception data."""
import time


_OPERATIONS = ('connection.connect_tcp', 'connection.start_tls',
               'http11.send_request_headers', 'http11.send_request_body',
               'http11.receive_response_headers', 'http11.receive_response_body')
_EVENTS = frozenset(f'{operation}.{state}' for operation in _OPERATIONS
                    for state in ('started', 'complete', 'failed'))


class TransportTrace:
    """HTTP/1.1 trace callbacks expose completion, not byte counts or admission.

    A missing milestone is unknown, including with transports that do not trace.
    Even send completion only means the local write completed, not that the
    provider accepted or billed the request. Partial header bytes are not exposed.
    """
    def __init__(self):
        self.started = time.monotonic()
        self.events = {}

    def __call__(self, name, info):
        # Never inspect info: it contains credentials, streams and raw exceptions.
        if name in _EVENTS:
            self.events.setdefault(name, round(time.monotonic() - self.started, 6))

    def snapshot(self):
        milestones = {
            'new_connection_observed': 'connection.connect_tcp.complete',
            'request_headers_sent': 'http11.send_request_headers.complete',
            'request_body_sent': 'http11.send_request_body.complete',
            'response_headers_received': 'http11.receive_response_headers.complete',
        }
        return {'events_seconds': dict(self.events),
                **{key: True if event in self.events else None for key, event in milestones.items()}}
