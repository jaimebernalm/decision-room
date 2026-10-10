"""HTML-only MCP boundary. Calculations remain local to the isolated agent."""
from . import admission, store

VERSIONS = {'2025-03-26', '2025-06-18'}
TOOLS = [{'name': 'entregar_informe',
          'description': 'Save exact HTML before validation. This is a receipt, not verification or permission to display. Repeat the same request_key and bytes for the same revision; changed bytes need a new key. At most 256 KiB UTF-8. You may instead write /work/informe.html for final collection.',
          'inputSchema': {'type': 'object', 'properties': {
              'request_key': {'type': 'string', 'minLength': 1, 'maxLength': 128},
              'html': {'type': 'string'}}, 'required': ['request_key', 'html'],
              'additionalProperties': False}}]


def dispatch(config, run_id, token, message, *, backend=None):
    admission.authenticate(config, run_id, token)
    if not isinstance(message, dict) or message.get('jsonrpc') != '2.0':
        raise ValueError('Invalid MCP message.')
    if set(message) - {'jsonrpc', 'id', 'method', 'params'}:
        raise ValueError('Unexpected MCP fields.')
    method, params = message.get('method'), message.get('params', {})
    if not isinstance(params, dict):
        raise ValueError('Invalid MCP parameters.')
    if 'id' not in message:
        if method == 'notifications/initialized':
            return None
        raise ValueError('Unsupported MCP notification.')
    response = {'jsonrpc': '2.0', 'id': message['id']}
    if method == 'initialize':
        result = {'protocolVersion': params.get('protocolVersion') if params.get('protocolVersion') in VERSIONS else '2025-06-18',
                  'capabilities': {'tools': {}},
                  'serverInfo': {'name': 'decision-room-engine', 'version': 'html-v1'}}
    elif method == 'ping':
        result = {}
    elif method == 'tools/list':
        result = {'tools': TOOLS}
    elif method == 'tools/call':
        try:
            args = params.get('arguments', {})
            if params.get('name') != 'entregar_informe' or not isinstance(args, dict) or set(args) != {'request_key', 'html'} or not isinstance(args['html'], str):
                raise ValueError('Invalid HTML delivery.')
            value = store.receive_document(config, run_id, token, **args)
            result = {'content': [{'type': 'text', 'text': admission.canonical(value).decode()}]}
        except admission.Denied:
            raise
        except (ValueError, TypeError, UnicodeError):
            result = {'isError': True, 'content': [{'type': 'text', 'text': 'Invalid delivery or receipt limit exceeded. Existing receipts are retained.'}]}
    else:
        return {**response, 'error': {'code': -32601, 'message': 'Method not found.'}}
    return {**response, 'result': result}
