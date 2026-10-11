"""F4 view: receipt policy, script-free frame, raw attachment and deferred PDF."""
import unittest

from decision_room.reports import presentation as policy
from tests import test_engine_report_surfaces as surfaces

CLEAN = '<!doctype html><html><head><meta charset="utf-8"><style>h1{color:#123}</style></head><body><h1>Ventas</h1><svg width="10"><rect width="5" height="5"/></svg></body></html>'.encode()


class ReceiptPolicyTests(unittest.TestCase):
    def test_clean_report_is_framed_without_scripts_and_with_its_own_policy_first(self):
        view = policy.view(CLEAN)
        self.assertEqual((view['mode'], view['sandbox']), ('frame', ''))
        self.assertTrue(view['srcdoc'].startswith('<!doctype html><meta http-equiv="Content-Security-Policy"'))
        self.assertIn("default-src 'none'", view['srcdoc'])
        self.assertNotIn('allow-', view['sandbox'])

    def test_forbidden_elements_urls_and_encodings_are_blocked(self):
        cases = {
            b'<base href="/">': 'element:base', b'<meta http-equiv="refresh" content="0;url=/">': 'element:meta',
            b'<iframe src="/"></iframe>': 'element:iframe', b'<object data="x"></object>': 'element:object',
            b'<embed src="x">': 'element:embed', b'<link rel="prefetch" href="/x">': 'element:link',
            b'<a href="https://example.org">x</a>': 'url:href', b'<a href="javascript:alert(1)">x</a>': 'url:href',
            b'<img src="//example.org/p.png">': 'url:src', b'<img src="http://127.0.0.1/p">': 'url:src',
            b'<form action="https://x"><button>x</button></form>': 'url:action',
            b'<div style="background:url(https://x/y)">': 'css:url', b'<style>@import "x.css";</style>': 'css:url',
            b'<style>p{background:url(/x)}</style>': 'css:url', b'<p srcdoc="x">': 'attribute:srcdoc',
            b'\xff\xfe': 'not_utf8', b'': 'empty', b'a\x00b': 'nul_byte',
            b'<p>' + b'x' * (policy.MAX_BYTES + 1): 'too_large',
        }
        for raw, reason in cases.items():
            with self.subTest(raw=raw[:40]):
                self.assertEqual(policy.receive(raw), ('blocked', reason))
                self.assertEqual(policy.view(raw)['mode'], 'blocked')

    def test_inline_images_anchors_and_viewport_are_allowed(self):
        for raw in (b'<img src="data:image/png;base64,AAAA">', b'<a href="#tabla">ir</a>',
                    b'<meta name="viewport" content="width=device-width">', b'<p style="color:red">x</p>'):
            with self.subTest(raw=raw):
                self.assertEqual(policy.receive(raw), ('allowed', None))

    def test_scripted_reports_wait_for_the_isolated_snapshot_or_are_blocked(self):
        for raw in (b'<p>x</p><script>draw()</script>', b'<button onclick="draw()">x</button>'):
            with self.subTest(raw=raw):
                self.assertEqual(policy.view(raw)['mode'], 'pending')
                self.assertEqual(policy.view(raw, {'status': 'pending'})['mode'], 'pending')
                failed = policy.view(raw, {'status': 'failed'})
                self.assertEqual((failed['mode'], failed['reason']), ('blocked', 'render_failed'))
                ready = policy.view(raw, {'status': 'ready', 'canonical_text': 'Ventas 12', 'snapshot_html': '<img src="data:image/png;base64,AA">'})
                self.assertEqual((ready['mode'], ready['canonical_text']), ('snapshot', 'Ventas 12'))
                self.assertNotIn('draw()', ready['srcdoc'])

    def test_snapshot_wins_over_raw_and_blocked_receipts_keep_canonical_text(self):
        ready = {'status': 'ready', 'canonical_text': 'Texto', 'snapshot_html': '<p>captura</p>'}
        self.assertEqual(policy.view(CLEAN, ready)['mode'], 'snapshot')
        blocked = policy.view(b'<base href="/">', ready)
        self.assertEqual((blocked['mode'], blocked['canonical_text']), ('blocked', 'Texto'))


class ViewSurfaceTests(surfaces.HtmlSurfaceTests):
    def delivered_clean(self):
        self.fake_runtime()
        from tests.engine_fakes import FakeRuntime
        FakeRuntime.payload = CLEAN
        job = self.create(engine_kind='opencode', title='Informe limpio')
        self.ws.run_job(job)
        return job

    def test_presentation_frames_the_report_and_the_raw_is_only_an_attachment(self):
        job = self.delivered_clean()
        client, server = self.http(); client.post('/api/login', json={'token': server.token})
        display = client.get(f'/api/jobs/{job}/presentation').json()
        self.assertEqual(display['view']['mode'], 'frame')
        self.assertEqual(display['view']['sandbox'], '')
        self.assertEqual(display['summary'], '')
        self.assertNotIn('Revisado', str(display))
        raw = client.get(f'/api/jobs/{job}/raw')
        self.assertEqual(raw.status_code, 200)
        self.assertEqual(raw.content, CLEAN)
        self.assertTrue(raw.headers['content-type'].startswith('application/octet-stream'))
        self.assertIn('attachment', raw.headers['content-disposition'])
        self.assertIn('sandbox', raw.headers['content-security-policy'])
        pdf = client.get(f'/api/jobs/{job}/pdf')
        self.assertEqual(pdf.status_code, 409)
        self.assertIn('PDF no disponible todavía', pdf.json()['error'])
        self.assertEqual(client.get(f'/api/jobs/{job}/report').status_code, 409)

    def test_scripted_delivery_is_pending_and_never_framed_raw(self):
        job = self.delivered()
        client, server = self.http(); client.post('/api/login', json={'token': server.token})
        display = client.get(f'/api/jobs/{job}/presentation').json()
        self.assertEqual(display['view']['mode'], 'pending')
        self.assertNotIn('srcdoc', display['view'])
        self.assertEqual(client.get(f'/api/jobs/{job}/raw').content, b'<script>PRIVATE_AGENT_ONLY</script>')

    def test_legacy_reports_have_no_raw_download(self):
        job = self.create()
        client, server = self.http(); client.post('/api/login', json={'token': server.token})
        self.assertEqual(client.get(f'/api/jobs/{job}/raw').status_code, 409)
