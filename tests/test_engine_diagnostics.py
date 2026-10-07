import unittest

from decision_room.engine.client import ProtocolError
from decision_room.engine.diagnostics import describe


class DiagnosticTests(unittest.TestCase):
    def test_known_protocol_errors_are_actionable_without_provider_body(self):
        value = describe(ProtocolError('OpenCode request failed (503).'), 'require_mcp')
        self.assertEqual(value['http_status'], 503)
        self.assertEqual(value['reason'], 'opencode_http_status')
        self.assertEqual(value['exception_type'], 'ProtocolError')

    def test_arbitrary_messages_arguments_paths_and_causes_never_appear(self):
        class HostileError(RuntimeError):
            def __str__(self): raise AssertionError('Do not stringify arbitrary errors')
        for error in (RuntimeError('private-token', {'password':'private-token'}),
                      HostileError('private-token'), FileNotFoundError(2, 'private-token', '/private-fixture/path'),
                      ProtocolError('OpenCode request failed (503). private-token')):
            error.__cause__ = ValueError('private-token')
            value = describe(error, 'require_mcp')
            self.assertNotIn('private-token', str(value))
            self.assertNotIn('/private-fixture', str(value))
            self.assertLess(len(str(value)), 500)
        self.assertEqual(describe(FileNotFoundError(), 'load_prompt')['reason'], 'file_missing')

    def test_malformed_exception_class_name_cannot_leak_arbitrary_text(self):
        error_type = type('private/credential', (Exception,), {})
        self.assertEqual(describe(error_type('private'), 'require_mcp')['exception_type'], 'Exception')
