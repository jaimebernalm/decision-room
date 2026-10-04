"""P3 reading/formatting contracts, with synthetic evidence and no model calls."""
from copy import deepcopy
from io import BytesIO
from html.parser import HTMLParser
import unittest
from unittest.mock import patch

from decision_room.agent.model import ModelClient, ModelSettings
from decision_room.agent.owner_presentation import feedback, SYSTEM
from decision_room.agent.review_context import model_context
from decision_room.client_report import render_client
from decision_room.owner_presentation import readable_number
from decision_room.report_pdf import render_pdf
from decision_room.web.dashboard import presentation
from decision_room.web.presentation_editing import relabel
from decision_room.web.presentation_html import render
from test_client_report import sample


def readable():
    data = sample()
    data['options'] = {'owner_presentation': True}
    report = data['report']
    report['owner_coverage'] = [dict(deliverable_index=0, status='partial', claim_keys=['sales'],
        explanation='Faltan costes para comparar el beneficio.')]
    report['highlights'] = [dict(label='Importe del primer día', unit='EUR', decimals=4, claim_key='sales',
                                value={'execution_id': 'calculation-a', 'metric': 'first'})]
    report['claims'][0]['orientation'] = dict(segment='Todos los registros', period='Enero',
        signal=report['claims'][0]['statement'], evidence=report['claims'][0]['evidence'],
        relative_priority='Revisar primero la disponibilidad de datos.', knowledge='calculated',
        next_check='Comparar días con registros.', decision_value='Permite decidir si ampliar la comparación.',
        reactions=[dict(condition='Hay datos completos', reaction='Comparar periodos completos.')],
        limitation=report['limitations'][0])
    report['limitations'].append('  No conocemos costes ni causas.  ')
    report['charts'][0]['caption'] = 'Comparamos el primer y el último día disponible para describir el cambio observado; falta el día intermedio.'
    data['observations'][0]['result']['evidence'][0]['operation'] = 'SUM(TRY_CAST(amount AS DECIMAL))'
    return data


class OwnerPresentationTests(unittest.TestCase):
    def test_values_are_legible_without_zeroing_small_signals(self):
        for raw, expected in [('188.0000','188'), ('51.366666666','51,37'), ('1234.565','1.234,57'),
                              ('-0.004','-0,004'), ('0.00003','0,00003'), ('0','0'), ('-0.0000','0'), ('1e-10','1,0E-10')]:
            with self.subTest(raw=raw): self.assertEqual(readable_number(raw), expected)

    def test_projection_preserves_source_evidence_and_one_visible_limit(self):
        data = readable(); original = deepcopy(data)
        view = presentation(data)
        self.assertTrue(view['owner_presentation'])
        self.assertTrue(view['partial']) # audited status remains truthful
        self.assertEqual(view['highlights'][0]['value'], '10')
        self.assertEqual(view['highlights'][0]['raw_value'], '10.00')
        self.assertEqual(view['charts'][0]['points'][-1]['formatted'], '20,01')
        self.assertEqual(view['charts'][0]['points'][-1]['value'], '20.005')
        self.assertEqual(view['limitations'], ['No conocemos costes ni causas.', 'Faltan costes para comparar el beneficio.'])
        self.assertEqual(view['claims'][0]['orientation']['limitation'], '')
        self.assertEqual(view['claims'][0]['orientation']['reactions'], original['report']['claims'][0]['orientation']['reactions'])
        row = view['claims'][0]['evidence_details']['metrics'][0]
        self.assertEqual(row['label'], 'Importe del primer día')
        self.assertEqual(row['original_label'], 'first')
        self.assertEqual(row['reference'], data['report']['claims'][0]['evidence'][0])
        self.assertEqual(data, original)

    def test_off_view_and_prompt_keep_baseline(self):
        data = readable(); data['options'] = {}
        view = presentation(data)
        self.assertNotIn('owner_presentation', view)
        self.assertEqual(view['highlights'][0]['value'], '10,0000')
        self.assertEqual(view['claims'][0]['evidence_details']['metrics'][0]['label'], 'first')
        self.assertIn('Entrega parcial', render_client(data, 'today'))
        client = ModelClient(ModelSettings('test'))
        for method in ('generate_analyst_review','generate_reviewer'):
            with patch.object(client, '_generate', return_value=({},{})) as generate:
                getattr(client, method)({})
                original = generate.call_args.args
                getattr(client, method)({'budgets': {'owner_presentation': True}})
                updated = generate.call_args.args
            self.assertTrue(updated[2].endswith(SYSTEM))
            self.assertNotIn('The client sees a partial-delivery marker', updated[2])
            self.assertNotIn('Controller caveats and counts remain intact.', updated[2])
            self.assertNotIn(SYSTEM, original[2])
            self.assertEqual(updated[3], original[3])

    def test_editorial_feedback_is_opt_in_and_never_rewrites_prose(self):
        data = readable()
        data['report']['claims'][0]['statement'] = 'TRY_CAST dio earlier_units de 51.36666.'
        ctx = dict(report=data['report'], observations=[], conversation=[], budgets={})
        self.assertNotIn('owner_reading_feedback', model_context(ctx, 'analyst'))
        ctx['budgets']['owner_presentation'] = True; original = deepcopy(ctx)
        value = model_context(ctx, 'analyst')
        issues = {entry['issue'] for entry in value['owner_reading_feedback']['locations']}
        self.assertEqual(issues, {'technical_language','internal_identifier','excess_decimal_precision'})
        self.assertEqual(value['report'], ctx['report'])
        self.assertEqual(ctx, original)
        self.assertEqual(feedback(data['report'])['review_period_rationale'], ['trend'])

    def test_html_and_cli_exclude_raw_evidence_even_inside_optional_details(self):
        class Reading(HTMLParser):
            def __init__(self):
                super().__init__(); self.depth = 0; self.primary = []; self.all = []; self.raw_depths = []
            def handle_starttag(self, tag, attrs):
                if tag == 'details': self.depth += 1
            def handle_endtag(self, tag):
                if tag == 'details': self.depth -= 1
            def handle_data(self, text):
                self.all.append(text)
                if not self.depth: self.primary.append(text)
                if 'SUM(TRY_CAST' in text: self.raw_depths.append(self.depth)
        data = readable()
        for html in (render(presentation(data), 'today'), render_client(data, 'today')):
            parser = Reading(); parser.feed(html)
            primary, all_text = '\n'.join(parser.primary), '\n'.join(parser.all)
            self.assertNotIn('Entrega parcial', all_text)
            self.assertEqual(all_text.count('No conocemos costes ni causas.'), 1)
            self.assertEqual(parser.raw_depths, [])
            self.assertNotIn('20.005', all_text)
            self.assertNotIn('TRY_CAST', all_text)
            self.assertIn('Datos utilizados: ventas.csv.', all_text)
            self.assertNotIn('20.005', primary)
            self.assertNotIn('TRY_CAST', primary)
            self.assertIn(data['report']['charts'][0]['caption'], primary)
            self.assertIn('Faltan costes para comparar el beneficio.', primary)

    def test_pdf_moves_technical_evidence_to_appendix_after_limits(self):
        from pypdf import PdfReader
        view = presentation(readable())
        pdf = PdfReader(BytesIO(render_pdf(view)))
        text = '\n'.join(page.extract_text() for page in pdf.pages)
        self.assertNotIn('Entrega parcial', text)
        self.assertEqual(text.count('No conocemos costes ni causas.'), 1)
        appendix = text.index('Fuentes, cálculos y valores originales')
        self.assertLess(text.index('Faltan costes'), appendix)
        self.assertGreater(text.index('TRY_CAST'), appendix)
        self.assertGreater(text.index('20.005'), appendix)
        self.assertIn('10\nEUR', text[:appendix])

    def test_catalog_labels_cover_all_reading_surfaces_without_rewriting_references(self):
        view = presentation(readable()); original = deepcopy(view)
        view['charts'][0].update(caption='U17 en D2', points=[dict(label='U17×D2', value='20.005', formatted='20,01')],
            panels=[dict(title='U17', category_title='Producto', series_title='D2', series_order=['D2'],
                         colors={'D2':'blue'}, styles={'D2':{'description':'U17 en D2'}},
                         coordinates=[dict(label='U17×D2', category='U17', series='D2')])],
            details=[dict(point_label='U17×D2', values=[dict(label='U17', formatted='20,01',unit='EUR')])])
        view['claims'][0]['orientation']['next_check'] = 'Revisar U17 en D2'
        view['limitations'] = ['Faltan costes de U17']
        result = relabel(view, [dict(code='U17', name='Cuaderno'), dict(code='D2', name='Web'), dict(code='calculated', name='Producto llamado calculated')])
        chart = result['charts'][0]
        self.assertEqual(chart['points'][0]['label'], 'Cuaderno×Web')
        self.assertEqual(chart['points'][0]['original_label'], 'U17×D2')
        self.assertEqual(chart['points'][0]['value'], '20.005')
        self.assertEqual(chart['panels'][0]['coordinates'][0]['label'], chart['points'][0]['label'])
        self.assertEqual(chart['panels'][0]['styles']['Web']['description'], 'Cuaderno en Web')
        self.assertEqual(chart['details'][0]['point_label'], 'Cuaderno×Web')
        self.assertEqual(chart['caption'], 'Cuaderno en Web')
        self.assertEqual(result['claims'][0]['orientation']['knowledge'], 'calculated')
        self.assertEqual(result['claims'][0]['orientation']['next_check'], 'Revisar Cuaderno en Web')
        self.assertEqual(result['limitations'], ['Faltan costes de Cuaderno'])
        self.assertEqual(result['claims'][0]['evidence_details']['metrics'][0]['reference'],
                         original['claims'][0]['evidence_details']['metrics'][0]['reference'])


class OwnerPresentationPersistenceTests(unittest.TestCase):
    from test_review import ReviewTests as _Base
    setUpClass = classmethod(_Base.setUpClass.__func__)
    tearDownClass = classmethod(_Base.tearDownClass.__func__)
    setUp = _Base.setUp

    def test_saved_option_is_independent_freezes_on_resume_and_reaches_both_roles(self):
        from dataclasses import replace
        from pathlib import Path
        from decision_room.agent import review
        from decision_room.database import connect
        from decision_room.report import export
        from test_review import DialogueModel
        config = replace(self.config, owner_presentation=True)
        roles = DialogueModel('defense')
        control = review.start(config, self.business, self.research['id'], request_key='control',
                               owner_presentation=False, analyst=roles, reviewer=roles)
        self.assertNotIn('owner_presentation', control['options'])
        roles = DialogueModel('defense')
        result = review.start(config, self.business, self.research['id'], request_key='p3', analyst=roles, reviewer=roles)
        self.assertTrue(result['publishable'])
        self.assertTrue(result['options']['owner_presentation'])
        self.assertEqual({c['role'] for c in roles.contexts}, {'analyst', 'reviewer'})
        self.assertTrue(all(c['budgets']['owner_presentation'] for c in roles.contexts))
        self.assertTrue(any('owner_reading_feedback' in c for c in roles.contexts))
        self.assertTrue(presentation(result)['owner_presentation'])
        with connect(config) as db:
            versions = db.execute('SELECT DISTINCT prompt_version FROM agent_calls WHERE scope=%s', (str(result['id']),)).fetchall()
        self.assertEqual([r['prompt_version'] for r in versions], ['owner-presentation-v2'])
        resumed = review.resume(self.config, self.business, result['id'], analyst=roles, reviewer=roles)
        self.assertTrue(resumed['options']['owner_presentation'])
        self.assertEqual(resumed['approved_sha256'], result['approved_sha256'])
        with self.assertRaisesRegex(ValueError, 'different inputs or settings'):
            review.start(config, self.business, self.research['id'], request_key='p3', owner_presentation=False,
                         analyst=roles, reviewer=roles)
        exported = export(self.config, self.business, result['id'])
        self.assertIn('Anexo técnico', Path(exported['path']).read_text())
        self.assertTrue(Path(exported['audit_path']).is_file())


class OwnerPresentationRecoveryTests(unittest.TestCase):
    from test_research import ResearchTests as _Base
    setUpClass = classmethod(_Base.setUpClass.__func__)
    tearDownClass = classmethod(_Base.tearDownClass.__func__)
    setUp = _Base.setUp
    start = _Base.start

    def test_presentation_switch_preserves_recovered_evidence_and_partial_coverage(self):
        from decision_room.agent import review
        from test_research_validation_recovery import InvalidAfterEvidence
        model = InvalidAfterEvidence()
        run = self.start(model=model, research_continuity=True, research_validation_recovery=True)
        self.assertEqual(run['status'], 'partial')
        snapshots = []
        calls = model.calls
        for enabled in (False, True):
            with patch('decision_room.agent.review._drive') as drive:
                review.start(self.config, self.business, run['id'], request_key=f'owner-{enabled}',
                             owner_presentation=enabled, analyst=model, reviewer=model)
            saved = drive.call_args.args[3]
            self.assertEqual(bool(saved['options'].get('owner_presentation')), enabled)
            snapshot = saved['snapshot']
            self.assertFalse(snapshot['research_coverage']['complete'])
            self.assertTrue(snapshot['research_coverage']['validation_recovery'])
            self.assertEqual(len(snapshot['executions']), 2)
            snapshots.append(snapshot)
        self.assertEqual(snapshots[0], snapshots[1])
        self.assertEqual(model.calls, calls)
