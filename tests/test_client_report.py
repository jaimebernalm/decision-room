"""Publication, chart provenance and client/internal separation regressions."""
from copy import deepcopy
from html.parser import HTMLParser
import re
import unittest

from decision_room.agent.review_contract import ReportDraft, checks, validate
from decision_room.agent.review_context import approval_digest
from decision_room.client_report import render_client, formatted


def sample():
    ref = lambda key: {'execution_id': 'calculation-a', 'metric': key}
    report = {
        'title': 'Ventas registradas', 'summary': 'Comparación del extracto recibido.',
        'scope': {'business': 'Tienda de ejemplo', 'question': '¿Cómo cambia la actividad registrada?',
                  'period': '2026-01-01 a 2026-01-03', 'coverage': 'Falta el día intermedio; no se considera cero.'},
        'claims': [{'key': 'sales', 'title': 'Comparación de ventas', 'statement': 'El último registro es mayor.',
                    'interpretation': 'No demuestra un cambio de demanda.', 'next_step': 'Comprobar la cobertura del extracto.',
                    'method': 'Sumar los importes de cada fecha; no rellenar días ausentes.', 'evidence': [ref('first'), ref('last')]}],
        'charts': [{'key': 'trend', 'claim_key': 'sales', 'kind': 'line', 'title': 'Importe por fecha',
                    'unit': 'Importe; moneda no informada', 'decimals': 2, 'caption': 'El hueco corresponde a una fecha sin registros.',
                    'points': [{'label': '2026-01-01', 'value': ref('first')}, {'label': '2026-01-03', 'value': ref('last')}]}],
        'no_chart_reason': '', 'limitations': ['No conocemos costes ni causas.'], 'checks': []}
    observation = {'execution_id': 'calculation-a', 'status': 'completed', 'current': True,
                   'result': {'metrics': {'first': '10.00', 'last': '20.005'},
                              'evidence': [{'metric': k, 'tables': ['sales'], 'operation': 'SUM by date'} for k in ('first','last')]},
                   'inputs': {'sales': {'original_names': ['ventas.csv'], 'row_count': 2}},
                   'code': 'PRIVATE PYTHON', 'issue': None}
    return {'status': 'approved', 'publishable': True, 'report': report, 'observations': [observation],
            'checks': checks(report, [observation]), 'conversation': [{'secret': 'PRIVATE DISCUSSION'}],
            'owner_context': 'PRIVATE OWNER TEXT', 'pending_questions': []}


class ClientReportTests(unittest.TestCase):
    def test_client_contains_business_context_chart_and_evidence_but_no_internal_log(self):
        data = sample()
        ReportDraft.model_validate(data['report'])
        html = render_client(data, '2026-09-21')
        for text in ('La pregunta de negocio', 'Qué significa para el negocio', 'Siguiente comprobación',
                     'Ver cómo se ha calculado', 'ventas.csv', '20,01', '<svg', 'Ver los valores del gráfico'):
            self.assertIn(text, html)
        for text in ('PRIVATE', 'calculation-a', 'Conversación entre', 'Python guardado'):
            self.assertNotIn(text, html)
        self.assertEqual(formatted('16.135643', 2), '16,14')
        self.assertEqual(formatted('-1234.565', 2), '-1.234,57')

    def test_missing_dates_are_not_connected_or_added_as_zero(self):
        html = render_client(sample(), 'today')
        self.assertEqual(html.count('<circle '), 2)
        self.assertNotIn('class="trend"', html)
        self.assertNotIn('2026-01-02', html)
        data = sample()
        data['report']['charts'][0]['points'][1]['label'] = '2026-01-02'
        self.assertIn('class="trend"', render_client(data, 'today'))

    def test_chart_only_evidence_is_checked_and_in_approval_hash(self):
        data = sample()
        data['report']['claims'][0]['evidence'] = [data['report']['claims'][0]['evidence'][0]]
        extra = deepcopy(data['observations'][0])
        extra['execution_id'] = 'chart-only-execution'
        data['observations'].append(extra)
        data['report']['charts'][0]['points'][1]['value']['execution_id'] = extra['execution_id']
        before = approval_digest(data, 'knowledge')
        extra['result']['metrics']['last'] = '999'
        self.assertNotEqual(before, approval_digest(data, 'knowledge'))
        extra['current'] = False
        result = checks(data['report'], data['observations'])
        self.assertFalse(next(c for c in result if c['check'] == 'chart:trend')['passed'])
        self.assertNotIn('<svg', render_client(data, 'today'))

    def test_invalid_chart_values_dates_labels_and_claim_links_block_publication(self):
        for change in ('unknown', 'nan', 'bool', 'no_evidence', 'reversed', 'duplicate', 'wrong_claim'):
            with self.subTest(change=change):
                data = sample()
                chart, obs = data['report']['charts'][0], data['observations'][0]
                if change == 'unknown':
                    chart['points'][1]['value']['metric'] = 'invented'
                elif change in ('nan', 'bool'):
                    obs['result']['metrics']['last'] = 'NaN' if change == 'nan' else True
                elif change == 'no_evidence':
                    obs['result']['evidence'].pop()
                elif change == 'reversed':
                    chart['points'].reverse()
                elif change == 'duplicate':
                    chart['points'][1]['label'] = chart['points'][0]['label']
                else:
                    chart['claim_key'] = 'invented'
                self.assertTrue(any(not c['passed'] for c in checks(data['report'], data['observations'])))
                self.assertNotIn('<svg', render_client(data, 'today'))

    def test_blocked_stale_waiting_and_legacy_reports_never_expose_draft(self):
        for status in ('held', 'stale', 'waiting', 'rejected', 'failed', 'limited'):
            data = sample()
            data.update(status=status, publishable=False, issue='PRIVATE TECHNICAL DIAGNOSTIC')
            html = render_client(data, 'today')
            self.assertNotIn('El último registro', html)
            self.assertNotIn('PRIVATE', html)
            self.assertNotIn('<svg', html)
        data = sample()
        del data['report']['scope']
        self.assertIn('pendiente', render_client(data, 'today'))
        self.assertNotIn('El último registro', render_client(data, 'today'))

    def test_escape_all_chart_text_and_accessible_svg_references(self):
        data = sample()
        chart = data['report']['charts'][0]
        chart.update(kind='bar', title='<script>bad</script>', unit='<img onerror=bad>', caption='<iframe>')
        chart['points'][0]['label'] = '<svg onload=bad>'
        class Parser(HTMLParser):
            def __init__(self):
                super().__init__(); self.ids = set(); self.refs = []; self.unsafe = []
            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if 'id' in attrs: self.ids.add(attrs['id'])
                if 'aria-labelledby' in attrs: self.refs.extend(attrs['aria-labelledby'].split())
                if tag in ('script', 'iframe', 'img') or any(k.startswith('on') for k in attrs): self.unsafe.append(tag)
        html = render_client(data, 'today')
        parser = Parser(); parser.feed(html)
        self.assertFalse(parser.unsafe)
        self.assertTrue(set(parser.refs) <= parser.ids)
        self.assertIn('&lt;script&gt;', html)

    def test_signed_zero_bars_and_table_chart(self):
        for values in (('-10', '20'), ('0', '0'), ('-10', '-20')):
            data = sample()
            data['report']['charts'][0]['kind'] = 'bar'
            data['observations'][0]['result']['metrics'] = dict(zip(('first','last'), values))
            html = render_client(data, 'today')
            widths = re.findall(r'<rect[^>]+width="([^"]+)"', html)
            self.assertEqual(len(widths), 2)
            self.assertTrue(all(float(w) >= 0 for w in widths))
        data['report']['charts'][0]['kind'] = 'table'
        html = render_client(data, 'today')
        self.assertNotIn('<svg', html)
        self.assertIn('-20,00', html)

    def test_no_chart_requires_reason_and_does_not_force_decoration(self):
        data = sample()
        data['report'].update(charts=[], no_chart_reason='No hay una comparación útil.')
        context = {'observations': data['observations']}
        raw = {'action': 'submit', 'message': 'Borrador', 'report': data['report']}
        validate(raw, 'analyst', context)
        self.assertNotIn('<svg', render_client(data, 'today'))
        data['report']['no_chart_reason'] = ''
        with self.assertRaisesRegex(ValueError, 'why no chart'):
            validate(raw, 'analyst', context)


if __name__ == '__main__':
    unittest.main()
