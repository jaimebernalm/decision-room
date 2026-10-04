"""Non-numeric saved evidence remains exportable without a new investigation."""
from contextlib import nullcontext
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import MagicMock, patch

from pypdf import PdfReader
from decision_room.config import Config
from decision_room.owner_presentation import readable_number
from decision_room.report import export
from decision_room.report_pdf import render_pdf
from decision_room.client_report import render_client
from decision_room.web.dashboard import presentation
from decision_room.web.presentation_html import render
from test_owner_presentation import readable


TEXT = 'Café de la casa 250 g | Marketplace'


def with_dimensions():
    data = readable()
    data.update(owner_answers=[], conversation=[])
    values = {'dimension': TEXT, 'date': '2026-01-03', 'flag': True, 'missing': None,
              'markup': '<b>Nombre & canal</b>'}
    observation = data['observations'][0]
    observation['inputs']['sales']['parquet_sha256'] = '0' * 64
    observation['result']['metrics'].update(values)
    for key in values:
        observation['result']['evidence'].append(dict(metric=key, tables=['sales'], operation='Saved dimension'))
        data['report']['claims'][0]['evidence'].append(dict(execution_id=observation['execution_id'], metric=key))
    return data, values


class OwnerEvidenceValueTests(unittest.TestCase):
    def test_non_numeric_values_are_returned_unchanged(self):
        for raw in (TEXT, '', '2026-01-03', date(2026, 1, 3), datetime(2026, 1, 3, 12),
                    True, False, None, 'NaN', 'sNaN', 'Infinity', Decimal('NaN')):
            with self.subTest(value=repr(raw)):
                self.assertIs(readable_number(raw), raw)
        self.assertEqual(readable_number('188.0000'), '188')
        self.assertEqual(readable_number('51.366666'), '51,37')

    def test_real_text_evidence_survives_projection_html_and_pdf(self):
        data, values = with_dimensions()
        before = deepcopy(data)
        view = presentation(data)
        rows = {r['reference']['metric']: r for r in view['claims'][0]['evidence_details']['metrics']}
        for key, value in values.items():
            self.assertEqual(rows[key]['value'], str(value))
            self.assertEqual(rows[key]['raw_value'], str(value))
        for language in ('es', 'en'):
            localized = deepcopy(view)
            localized['response_language'] = language
            html = render(localized, 'today')
            pdf = '\n'.join(p.extract_text() for p in PdfReader(BytesIO(render_pdf(localized))).pages)
            for value in (TEXT, '2026-01-03', 'True', 'None'):
                self.assertIn(value, pdf)
            self.assertNotIn('&lt;b&gt;Nombre &amp; canal&lt;/b&gt;', html)
            self.assertNotIn(TEXT, html)
            self.assertIn('<b>Nombre & canal</b>', pdf)
        self.assertNotIn(TEXT, render_client(data, 'today'))
        self.assertEqual(data, before)

    def test_text_evidence_does_not_relax_numeric_chart_validation(self):
        from decision_room.web.errors import WebError
        data, _ = with_dimensions()
        data['report']['charts'][0]['points'][0]['value']['metric'] = 'dimension'
        with self.assertRaises(WebError):
            presentation(data)

    def test_export_existing_approval_keeps_audit_unchanged(self):
        data, _ = with_dimensions()
        before = deepcopy(data)
        db = MagicMock()
        db.transaction.side_effect = lambda: nullcontext()
        # Only persistence/decoration lookup is stubbed; export, projection,
        # HTML serialization and audit materialization run normally.
        with TemporaryDirectory() as folder, \
                patch('decision_room.report.review._parent', return_value='parent'), \
                patch('decision_room.report.session_lock', side_effect=lambda *a: nullcontext((db, None))), \
                patch('decision_room.report.memory_lock'), \
                patch('decision_room.report.review.show', return_value=data), \
                patch('decision_room.web.presentation_editing.decorate', side_effect=lambda ws, data, view, **kw: view):
            result = export(Config('', Path(folder)), 'business', 'review')
            self.assertTrue(result['publishable'])
            self.assertNotIn(TEXT, Path(result['path']).read_text())
            self.assertIn(TEXT, Path(result['internal_path']).read_text())
            self.assertIn('href="internal.html"', Path(result['path']).read_text())
            audit = json.loads(Path(result['audit_path']).read_text())
            self.assertEqual(audit['report'], before['report'])
            self.assertEqual(audit['observations'], before['observations'])
        self.assertEqual(data, before)
