"""Native gate with synthetic HTML only; no agent report is executed on the host."""
import html
import http.server
import threading
import time
import unittest

from decision_room.web.server import CSP as PRODUCT_CSP
from tests.synthetic_browser import SyntheticBrowser, chrome_binary


def available():
    try:
        chrome_binary()
        return True
    except RuntimeError:
        return False


@unittest.skipUnless(available(), 'Chrome required for the synthetic native frame gate.')
class NativeFrameGate(unittest.TestCase):
    def setUp(self):
        self.requests = []
        self.page = b''
        owner = self
        class Parent(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                owner.requests.append(self.path)
                body = owner.page if self.path == '/' else b'escaped'
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Security-Policy', PRODUCT_CSP)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            def log_message(self, *args): pass
        self.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Parent)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.origin = f'http://127.0.0.1:{self.server.server_port}'

    def parent(self, srcdoc):
        self.page = ('<!doctype html><title>parent-intact</title><iframe '
                     'style="position:absolute;left:0;top:0;width:800px;height:600px" '
                     'sandbox="" srcdoc="' + html.escape(srcdoc, quote=True) + '"></iframe>').encode()
        self.requests.clear()

    def click(self, browser, session):
        time.sleep(.25)
        for kind in ('mousePressed', 'mouseReleased'):
            browser.call('Input.dispatchMouseEvent', dict(type=kind, x=50, y=50, button='left', clickCount=1), session)
        time.sleep(.3)

    def test_smil_bypasses_old_raw_candidate_but_snapshot_only_never_frames_it(self):
        from decision_room.reports import presentation
        from tests.test_report_derive import snapshot
        raw = (f'<svg width="600" height="120"><a href="#"><animate attributeName="href" '
               f'values="{self.origin}/escape-smil" begin="0s" fill="freeze"/>'
               '<rect width="500" height="100" fill="blue"/></a></svg>').encode()
        # Intentional reproduction of the rejected candidate, not a product path.
        self.assertEqual(presentation.inspect(raw)['state'], 'allowed')
        self.parent(presentation.frame_document(raw))
        with SyntheticBrowser(timeout=8) as browser:
            session = browser.open_origin(self.origin)
            self.click(browser, session)
            self.assertIn('/escape-smil', self.requests)
            self.assertEqual(browser.evaluate('document.title', session), 'parent-intact')
            self.assertNotIn('srcdoc', presentation.view(raw))
            safe = presentation.view(raw, dict(status='ready', canonical_text='Units 5', snapshot_html=snapshot()))
            self.assertEqual((safe['mode'], safe['sandbox']), ('snapshot', ''))
            self.assertNotIn('<svg', safe['srcdoc'])
            self.assertNotIn('/escape-smil', safe['srcdoc'])
            self.parent(safe['srcdoc'])
            session = browser.open_origin(self.origin)
            self.click(browser, session)
            self.assertEqual(set(self.requests) - {'/', '/favicon.ico'}, set())
            self.assertEqual(browser.evaluate('document.title', session), 'parent-intact')

    def test_hostile_fixtures_never_reach_the_frame_or_the_product_sink(self):
        from decision_room.reports import presentation
        from tests.test_report_derive import snapshot
        fixtures = [
            '<script>parent.document.title="escaped"</script>',
            f'<script>fetch("{self.origin}/escape-fetch")</script>',
            f'<script>location.href="http:"+"//127.0.0.1:{self.server.server_port}/escape-built"</script>',
            f'<base href="{self.origin}/escape-base">',
            f'<meta http-equiv="refresh" content="0;url={self.origin}/escape-refresh">',
            '<a href="javascript:parent.document.title=\'escaped\'">click</a>',
            '<a href="/escape-relative">click</a>',
            f'<form action="{self.origin}/escape-form"><input type="submit"></form>',
            '<svg><a href="#"><animate attributeName="href" values="/escape-animate"/><rect width="500" height="100"/></a></svg>',
            '<p>' + 'x' * (256 * 1024),
        ]
        with SyntheticBrowser(timeout=8) as browser:
            for fixture in fixtures:
                with self.subTest(fixture=fixture[:50]):
                    raw = fixture.encode()
                    view = presentation.view(raw, dict(status='ready', canonical_text='Units 5', snapshot_html=snapshot()))
                    # Blocked intake is represented by product text, without a frame.
                    self.parent(view.get('srcdoc', '<p>Presentación bloqueada</p>'))
                    self.assertNotIn(fixture, self.page.decode())
                    session = browser.open_origin(self.origin)
                    self.click(browser, session)
                    self.assertEqual(set(self.requests) - {'/', '/favicon.ico'}, set())
                    self.assertEqual(browser.evaluate('document.title', session), 'parent-intact')
