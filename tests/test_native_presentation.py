"""Optional native presentation blocks: full text, checker locations, PDF and stored citations."""
import io
import json
import copy
import unittest
from pathlib import Path
from unittest.mock import patch

from pypdf import PdfReader

from decision_room.database import connect
from decision_room.engine import blocks, brief, check_contract, api
from decision_room.reports import blocks_pdf, reading
from tests.test_engine_blocks import doc, raw
from tests.test_native_checks import IndependentClient, IndependentRuntime
from tests import test_engine_jobs as product

FIXTURE = Path(__file__).parent / 'fixtures/native-presentation/informe.json'


def example():
    return json.loads(FIXTURE.read_bytes())


def pdf_text(pdf):
    return '\n'.join(page.extract_text() for page in PdfReader(io.BytesIO(pdf)).pages)


class PresentationFormatTests(unittest.TestCase):
    def test_synthetic_fixture_keeps_all_text_and_path_ids(self):
        p = blocks.parse(FIXTURE.read_bytes())
        self.assertEqual(p['projector'], 'bloques-proyector-6')
        self.assertEqual([b['id'] for b in blocks.walk(p['blocks'])],
                         ['b1', 'b2', 'b3', 'b3-1', 'b3-2', 'b4', 'b5', 'b5-1'])
        self.assertEqual([b['type'] for b in p['blocks']], ['cover', 'cards', 'priority', 'cards', 'priority'])
        self.assertEqual([c['tone'] for c in p['blocks'][1]['cards']], ['positive', 'negative'])
        self.assertEqual([c['tone'] for c in p['blocks'][3]['cards']], [None, 'warning', 'neutral'])
        self.assertIsNone(p['blocks'][4]['blocks'][0]['if_confirmed'])
        self.assertEqual(p['blocks'][2]['blocks'][1]['labels'], dict(check=None, if_confirmed=None, if_not=None))
        self.assertEqual(p['blocks'][4]['blocks'][0]['labels']['check'], 'Qué revisar en abril')
        text = blocks.canonical_text(p)
        for phrase in ('8,2 %', '1.240 pedidos', 'Revisar la atención en el local.', 'Tres.',
                       'Qué comprobar', 'Si se confirma', 'Si no', 'Qué revisar en abril'):
            self.assertIn(phrase, text)
        priorities = blocks.priorities(p)
        self.assertEqual([b['block_id'] for b in priorities], ['b3', 'b5'])
        self.assertNotIn('8,2 %', '\n'.join(b['text'] for b in priorities))
        self.assertNotIn('1.240 pedidos', '\n'.join(b['text'] for b in priorities))

    def test_cover_is_unique_and_only_the_first_root_block(self):
        cover = dict(tipo='portada', titulo='Titular', contenido='Resumen')
        text = dict(tipo='texto', contenido='Texto')
        for invalid in (doc(text, cover), doc(cover, cover),
                        doc(dict(tipo='seccion', titulo='S', bloques=[cover])),
                        doc(dict(tipo='prioridad', titulo='P', bloques=[cover]))):
            with self.subTest(invalid=invalid), self.assertRaisesRegex(blocks.BlocksError, 'primer bloque'):
                blocks.parse(raw(invalid))

    def test_action_requires_a_priority_but_can_live_in_its_section(self):
        action = dict(tipo='accion', comprobar='Comprobar')
        for invalid in (doc(action), doc(dict(tipo='seccion', titulo='S', bloques=[action]))):
            with self.assertRaisesRegex(blocks.BlocksError, 'dentro de una prioridad'):
                blocks.parse(raw(invalid))
        p = blocks.parse(raw(doc(dict(tipo='prioridad', titulo='P', bloques=[
            dict(tipo='seccion', titulo='S', bloques=[action])]))))
        self.assertIn('Qué comprobar\nComprobar', blocks.priorities(p)[0]['text'])
        self.assertNotIn('Si no', blocks.canonical_text(p))

    def test_card_count_content_tones_and_unknown_fields_are_strict(self):
        card = dict(titulo='A', contenido='Texto')
        for value in (None, {}, [], [card], [card] * 4):
            with self.subTest(value=value), self.assertRaises(blocks.BlocksError):
                blocks.parse(raw(doc(dict(tipo='tarjetas', tarjetas=value))))
        for changed in (dict(card, titulo=''), dict(card, contenido=[]), dict(card, contenido=None),
                        dict(card, tono=[]), dict(card, tono='inventado'), dict(card, html='<b>x</b>')):
            with self.subTest(changed=changed), self.assertRaises(blocks.BlocksError):
                blocks.parse(raw(doc(dict(tipo='tarjetas', tarjetas=[card, changed]))))
        for changed in (dict(tipo='accion', comprobar=''), dict(tipo='accion', comprobar='X', si_no=None),
                        dict(tipo='portada', titulo='x' * 201, contenido='X')):
            document = doc(changed) if changed['tipo'] == 'portada' else doc(dict(tipo='prioridad', titulo='P', bloques=[changed]))
            with self.assertRaises(blocks.BlocksError):
                blocks.parse(raw(document))

    def test_new_contents_share_the_existing_string_and_total_text_limits(self):
        with self.assertRaisesRegex(blocks.BlocksError, 'máximo es 4000'):
            blocks.parse(raw(doc(dict(tipo='portada', titulo='T', contenido='x' * 4001))))
        cards = dict(tipo='tarjetas', tarjetas=[dict(titulo='A', contenido='x' * 3900)] * 2)
        with self.assertRaisesRegex(blocks.BlocksError, 'caracteres de texto'):
            blocks.parse(raw(doc(*[cards] * 20)))

    def test_confirmed_number_in_action_uses_the_actual_canonical_offsets(self):
        p = blocks.parse(raw(doc(dict(tipo='prioridad', titulo='P', bloques=[
            dict(tipo='accion', comprobar='Recontar unidades.', si_se_confirma='Mantener las 5 unidades.', si_no='Revisar.')]))))
        priority = blocks.priorities(p)[0]
        self.assertEqual(priority['text'], 'Prioridad: P\nQué comprobar\nRecontar unidades.\nSi se confirma\nMantener las 5 unidades.\nSi no\nRevisar.')
        offset = priority['text'].index('5 unidades')
        output = dict(version=check_contract.VERSION, revision_sha256='a' * 64, coverage_notes='', items=[
            dict(priority_id='b1', quote='5 unidades', start=offset, end=offset + 10, status='confirmed',
                 independent_value='5 unidades', method='Sumar el CSV sintético.', message='')])
        checked = check_contract.parse(raw(output), p, 'a' * 64)
        self.assertEqual(checked['coverage']['confirmed_spans'], 1)
        self.assertEqual(checked['items'][0]['block_id'], 'b1-1')
        self.assertTrue(checked['items'][0]['located'])
        output['items'][0]['start'] -= len('Si se confirma\n')
        with self.assertRaises(check_contract.CheckError):
            check_contract.parse(raw(output), p, 'a' * 64)

    def test_own_action_labels_are_optional_bounded_and_require_their_branch(self):
        action = dict(tipo='accion', comprobar='Contar.', si_se_confirma='Actuar.', si_no='Revisar.',
                      rotulo_comprobar='La comprobación', rotulo_si_se_confirma='Si son pedidos reales',
                      rotulo_si_no='Si son duplicados')
        p = blocks.parse(raw(doc(dict(tipo='prioridad', titulo='P', bloques=[action]))))
        b = p['blocks'][0]['blocks'][0]
        self.assertEqual(b['labels'], dict(check='La comprobación', if_confirmed='Si son pedidos reales', if_not='Si son duplicados'))
        self.assertEqual(blocks.block_lines(b), ['La comprobación', 'Contar.', 'Si son pedidos reales', 'Actuar.', 'Si son duplicados', 'Revisar.'])
        for key in ('rotulo_comprobar', 'rotulo_si_se_confirma', 'rotulo_si_no'):
            valid = dict(action, **{key: 'x' * blocks.MAX_TITLE})
            blocks.parse(raw(doc(dict(tipo='prioridad', titulo='P', bloques=[valid]))))
            for value in ('', '  ', None, False, 12, [], {}, 'x' * (blocks.MAX_TITLE + 1), 'x\x00y'):
                with self.subTest(key=key, value=value), self.assertRaises(blocks.BlocksError):
                    blocks.parse(raw(doc(dict(tipo='prioridad', titulo='P', bloques=[dict(action, **{key: value})]))))
        for branch in ('si_se_confirma', 'si_no'):
            invalid = dict(action)
            del invalid[branch]
            with self.assertRaisesRegex(blocks.BlocksError, 'sin la rama'):
                blocks.parse(raw(doc(dict(tipo='prioridad', titulo='P', bloques=[invalid]))))
        with patch.object(blocks, 'MAX_TEXT', 50), self.assertRaisesRegex(blocks.BlocksError, 'caracteres de texto'):
            blocks.parse(raw(doc(dict(tipo='prioridad', titulo='P', bloques=[dict(action, rotulo_comprobar='x' * 50)]))))

    def test_projector_five_without_labels_preserves_default_text_and_pdf(self):
        current = blocks.parse(raw(doc(dict(tipo='prioridad', titulo='P', bloques=[
            dict(tipo='accion', comprobar='Contar.', si_se_confirma='Actuar.', si_no='Revisar.')]))))
        legacy = copy.deepcopy(current)
        legacy['projector'] = 'bloques-proyector-5'
        del legacy['blocks'][0]['blocks'][0]['labels']
        self.assertEqual(blocks.canonical_text(legacy), blocks.canonical_text(current))
        self.assertEqual(blocks.priorities(legacy), blocks.priorities(current))
        self.assertEqual(pdf_text(blocks_pdf.render(legacy)), pdf_text(blocks_pdf.render(current)))

    def test_custom_labels_and_number_in_branch_use_the_actual_checker_offsets(self):
        p = blocks.parse(raw(doc(dict(tipo='prioridad', titulo='P', bloques=[dict(tipo='accion',
            comprobar='Recontar.', si_se_confirma='Mantener las 5 unidades.', si_no='Revisar.',
            rotulo_comprobar='La comprobación siguiente', rotulo_si_se_confirma='Si son pedidos reales', rotulo_si_no='Si son duplicados')]))))
        text = blocks.priorities(p)[0]['text']
        self.assertEqual(text, 'Prioridad: P\nLa comprobación siguiente\nRecontar.\nSi son pedidos reales\nMantener las 5 unidades.\nSi son duplicados\nRevisar.')
        offset = text.index('5 unidades')
        output = dict(version=check_contract.VERSION, revision_sha256='a' * 64, coverage_notes='', items=[
            dict(priority_id='b1', quote='5 unidades', start=offset, end=offset + 10, status='confirmed',
                 independent_value='5 unidades', method='Sumar.', message='')])
        checked = check_contract.parse(raw(output), p, 'a' * 64)
        self.assertEqual(checked['coverage']['confirmed_spans'], 1)
        self.assertEqual(checked['items'][0]['block_id'], 'b1-1')
        self.assertTrue(checked['items'][0]['located'])
        legacy = copy.deepcopy(p)
        del legacy['blocks'][0]['blocks'][0]['labels']
        wrong_offset = blocks.priorities(legacy)[0]['text'].index('5 unidades')
        self.assertNotEqual(offset, wrong_offset)
        output['items'][0].update(start=wrong_offset, end=wrong_offset + 10)
        with self.assertRaises(check_contract.CheckError):
            check_contract.parse(raw(output), p, 'a' * 64)

    def test_brief_and_guide_offer_presentation_without_a_mandatory_template(self):
        kwargs = dict(name='Fixture', description='Datos', goal='Comparar', model=None, memory=[], panorama=False)
        native = brief.compose(**kwargs, format='blocks')
        self.assertIn(brief.PRESENTATION, native)
        self.assertNotIn(brief.PRESENTATION, brief.compose(**kwargs, format='html'))
        self.assertIn('no lo dupliques', native)
        self.assertIn('Subir no siempre es bueno', native)
        self.assertIn('rótulos propios', native)
        self.assertIn('fuera de prioridades no forman parte de esa cobertura', blocks.FORMAT_GUIDE)


class PresentationPdfTests(unittest.TestCase):
    def test_cover_cards_actions_and_notices_are_complete_and_escaped(self):
        p = blocks.parse(FIXTURE.read_bytes())
        p['blocks'][0]['title'] = '<b>Titular</b> & <script>'
        text = pdf_text(blocks_pdf.render(p, dict(state='complete', items=[
            dict(block_id='b1', quote='8,2 %', status='discrepancy', independent_value='7,9 %'),
            dict(block_id='b2', quote='1.240', status='discrepancy', independent_value='1.180'),
            dict(block_id='b3-2', quote='pedidos', status='discrepancy', independent_value='otro')])) )
        self.assertEqual(text.count('Cómo va el trimestre'), 1)
        self.assertIn('<b>Titular</b> & <script>', text)
        for phrase in ('Qué ha funcionado', 'Qué no', 'Qué comprobar', 'Si se confirma', 'Si no',
                       'Revisar la atención en el local.', 'Tres.', '1.180', '7,9 %', 'otro', 'Qué revisar en abril'):
            self.assertIn(phrase, text)
        self.assertEqual(text.count('Cifra en revisión'), 3)
        self.assertNotIn('Verificado', text)

    def test_custom_action_labels_are_complete_and_escaped_in_pdf(self):
        p = blocks.parse(raw(doc(dict(tipo='prioridad', titulo='P', bloques=[dict(tipo='accion',
            comprobar='Contar.', si_se_confirma='Actuar.', si_no='Revisar.',
            rotulo_comprobar='<b>Mi comprobación</b>', rotulo_si_se_confirma='Si son pedidos reales', rotulo_si_no='Si son duplicados')]))))
        text = pdf_text(blocks_pdf.render(p))
        for phrase in ('<b>Mi comprobación</b>', 'Si son pedidos reales', 'Si son duplicados', 'Contar.', 'Actuar.', 'Revisar.'):
            self.assertEqual(text.count(phrase), 1)
        self.assertNotIn('Qué comprobar', text)
        self.assertNotIn('Si se confirma', text)

    def test_long_cover_cards_and_action_paginate_without_lost_or_repeated_text(self):
        card = lambda title, word: dict(titulo=title, contenido=(word + ' ') * 480)
        document = doc(dict(tipo='portada', titulo='Titular', contenido='portada ' * 480),
                       dict(tipo='tarjetas', tarjetas=[card('A', 'primera'), card('B', 'segunda')]),
                       dict(tipo='prioridad', titulo='P', bloques=[dict(tipo='accion', comprobar='comprobar ' * 380,
                            si_se_confirma='confirmar ' * 380, si_no='descartar ' * 380)]))
        pdf = blocks_pdf.render(blocks.parse(raw(document)))
        pages = PdfReader(io.BytesIO(pdf)).pages
        self.assertGreater(len(pages), 2)
        self.assertTrue(all(page.extract_text().strip() for page in pages), 'No empty panel continuations')
        text = pdf_text(pdf)
        for word in ('portada', 'primera', 'segunda'):
            self.assertEqual(text.count(word), 480)
        for word in ('comprobar', 'confirmar', 'descartar'):
            self.assertEqual(text.count(word), 381 if word == 'comprobar' else 380)

    def test_two_short_cards_share_columns_three_cards_stay_splittable(self):
        cards = blocks.parse(FIXTURE.read_bytes())['blocks'][1]['cards']
        pair = blocks_pdf._cards(cards)
        self.assertEqual(len(pair[0]._colWidths), 3)  # two panels and their gutter
        three = blocks_pdf._cards(cards + [cards[0]])
        self.assertEqual(len(three), 3)
        self.assertTrue(all(p.splitInRow for p in three))

    def test_panel_near_page_bottom_defers_without_empty_pages_or_duplicate_text(self):
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
        for remaining in (8, 14, 22):
            with self.subTest(remaining=remaining):
                buffer = io.BytesIO()
                document = SimpleDocTemplate(buffer, pagesize=A4, topMargin=44, bottomMargin=44)
                before = Paragraph('Contenido previo', blocks_pdf.STYLES['body'])
                height = before.wrap(blocks_pdf.WIDTH, 10000)[1] + before.getSpaceAfter()
                spacer = document.height - 12 - height - remaining
                document.build([before, Spacer(1, spacer), blocks_pdf._panel([
                    Paragraph('Panel completo una sola vez.', blocks_pdf.STYLES['body'])])])
                pages = PdfReader(io.BytesIO(buffer.getvalue())).pages
                self.assertEqual(len(pages), 2)
                self.assertTrue(all(page.extract_text().strip() for page in pages))
                self.assertEqual(pdf_text(buffer.getvalue()).count('Panel completo una sola vez.'), 1)

    def test_card_heading_near_page_bottom_stays_with_its_body(self):
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
        content = blocks.parse(raw(doc(dict(tipo='texto', contenido='Contenido. ' * 80))))['blocks'][0]['content']
        for tone in (None, 'positive'):
            for remaining in (35, 50, 65):
                with self.subTest(tone=tone, remaining=remaining):
                    buffer = io.BytesIO()
                    document = SimpleDocTemplate(buffer, pagesize=A4, topMargin=44, bottomMargin=44)
                    before = Paragraph('Contenido previo', blocks_pdf.STYLES['body'])
                    height = before.wrap(blocks_pdf.WIDTH, 10000)[1] + before.getSpaceAfter()
                    spacer = document.height - 12 - height - remaining
                    card = dict(title='Tarjeta siguiente', content=content, tone=tone)
                    document.build([before, Spacer(1, spacer), *blocks_pdf._cards([card])])
                    pages = PdfReader(io.BytesIO(buffer.getvalue())).pages
                    self.assertEqual(len(pages), 2)
                    self.assertNotIn('Tarjeta siguiente', pages[0].extract_text())
                    self.assertIn('Tarjeta siguiente', pages[1].extract_text())
                    self.assertEqual(pages[1].extract_text().count('Contenido.'), 80)


class PresentationProductTests(unittest.TestCase):
    setUpClass = classmethod(product.EngineJobTests.setUpClass.__func__)
    tearDownClass = classmethod(product.EngineJobTests.tearDownClass.__func__)
    setUp = product.EngineJobTests.setUp
    create = product.EngineJobTests.create
    pinned = product.EngineJobTests.pinned
    fake_runtime = product.EngineJobTests.fake_runtime

    def deliver(self):
        self.fake_runtime()
        IndependentRuntime.payloads = [FIXTURE.read_bytes()]
        IndependentClient.checker_results = []
        runtime = patch.object(api, 'Runtime', IndependentRuntime)
        runtime.start(); self.addCleanup(runtime.stop)
        job = self.create(engine_kind='opencode', engine_format='blocks')
        self.ws.run_job(job)
        row = self.ws.row(job)
        self.assertEqual(row['status'], 'completed', row['issue'])
        return next(x for x in self.ws.listing() if str(x['id']) == str(job))

    def resolve(self, entry, key):
        from decision_room import context_references
        reference = dict(source_id=entry['report_document_id'], source_version=entry['engine_report']['revision_id'],
                         kind='engine_block', element_key=key)
        with connect(self.config) as db:
            return context_references.resolve_source(context_references.normalize([reference])[0], db, self.business['id'])

    def test_new_blocks_can_be_cited_from_the_stored_revision_without_reprojection(self):
        entry = self.deliver()
        expected = {'b1': '8,2 %', 'b2': '1.240 pedidos', 'b3-2': 'Revisar la atención en el local.'}
        before = {key: self.resolve(entry, key) for key in expected}
        for key, phrase in expected.items():
            self.assertEqual(before[key]['content']['key'], key)
            self.assertEqual(before[key]['authority'], 'engine_report')
            self.assertIn(phrase, before[key]['content']['statement'])
            self.assertTrue(before[key]['href'])
        with patch.object(blocks, 'parse', side_effect=AssertionError('stored projection must not be recomputed')), \
                patch.object(blocks, 'PROJECTOR_VERSION', 'future-projector'):
            for key in expected:
                self.assertEqual(self.resolve(entry, key), before[key])
            with reading.read(self.config, self.business['id'], entry['report_document_id']) as (db, document, revision):
                self.assertEqual(reading.view(db, document, revision)['blocks']['projector'], 'bloques-proyector-6')
        with connect(self.config) as db:
            db.execute("UPDATE report_documents SET stale_reason='data_changed' WHERE id=%s", (entry['report_document_id'],))
        from decision_room.web.errors import WebError
        with self.assertRaises(WebError):
            self.resolve(entry, 'b1')
