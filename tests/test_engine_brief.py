"""Generated v1 brief and panorama: deterministic, no model, nothing business-specific."""
import hashlib
import unittest
from datetime import date, timedelta
from decimal import Decimal, localcontext
from pathlib import Path
from uuid import uuid4

from decision_room import sales_panorama
from decision_room.database import connect
from decision_room.engine import brief, panorama_v1
from decision_room.service import import_batch
from decision_room.web import engine_jobs
from tests import test_web as fixtures

# Paragraphs 3-5 of both trial briefs, byte for byte (charts, depth, verification).
FIXED_SHA256 = 'c91844485cfe856f2273bdfb8abd7a2452e578505c5c00670eddbf90e321a6ba'
MAPPING = {'date': 'fecha', 'product': 'producto_id', 'channel': 'canal_id', 'quantity': 'unidades'}


def fact(statement, *, kind='context', status='declared', temporal='unspecified'):
    return dict(reference=uuid4().hex, status=status,
                content=dict(kind=kind, statement=statement, temporal_scope=temporal))


def column(name, meaning='', status='unknown', unit=''):
    return dict(name=name, meaning=meaning, unit=unit, conversion='', semantic_status=status)


def summary(rows):
    with localcontext() as ctx:
        ctx.prec = 80
        out = sales_panorama.summarize(sorted(rows), MAPPING, len(rows))
    return out['summary'], out['result']['metrics']


def daily(start, days, groups, skip=lambda d, g: False):
    return [(start + timedelta(days=i), p, c, Decimal(q), 1)
            for i in range(days) for (p, c, q) in groups if not skip(start + timedelta(days=i), (p, c))]


class BriefTextTests(unittest.TestCase):
    def compose(self, **changes):
        values = dict(name='Tienda Ejemplo', description='una tienda de barrio. Vendemos en tienda y web.',
                      goal='Quiero saber qué productos revisar primero.', model=None, memory=[], panorama=False)
        return brief.compose(**{**values, **changes})

    def test_fixed_paragraphs_are_the_unchanged_trial_text(self):
        self.assertEqual(hashlib.sha256(brief.FIXED.read_bytes()).hexdigest(), FIXED_SHA256)
        self.assertTrue(self.compose().endswith(brief.FIXED.read_text()))

    def test_owner_paragraphs_follow_the_trial_order(self):
        model = dict(tables=[dict(name='ventas', description='', semantic_status='unknown', columns=[
            column('unidades', 'la cantidad registrada por fecha, producto y canal', 'owner_declared'),
            column('importe')])])
        text = self.compose(model=model, panorama=True)
        first, second = text.split('\n\n')[:2]
        self.assertEqual(first, ' '.join([
            'Mi negocio es Tienda Ejemplo, una tienda de barrio. Vendemos en tienda y web.',
            brief.DATA, brief.PANORAMA,
            '«unidades» es la cantidad registrada por fecha, producto y canal.',
            brief.UNKNOWN, brief.LIMITS]))
        self.assertEqual(second, 'Quiero saber qué productos revisar primero. ' + brief.REQUEST)

    def test_without_panorama_the_brief_never_mentions_it(self):
        text = self.compose(panorama=False)
        self.assertNotIn('panorama', text.casefold())
        self.assertNotIn('/inputs/contexto', text)

    def test_no_invented_meanings_trial_specifics_or_tool_names(self):
        model = dict(tables=[dict(name='t', description='descripción técnica', semantic_status='inferred',
                                  columns=[column('importe', 'importe por fila', 'inferred')])])
        text = self.compose(model=model)
        self.assertNotIn('«importe»', text)
        self.assertNotIn('descripción técnica', text)
        self.assertIn(brief.UNKNOWN, text)
        for absent in ('sintétic', 'entregar_informe', 'márgenes', 'retorno de marketing', 'Albor', 'Bruma'):
            self.assertNotIn(absent, text)

    def test_grain_metrics_and_same_named_columns_keep_their_table(self):
        model = dict(tables=[
            dict(id='t1', name='ventas', description='', grain='un día y un producto', semantic_status='owner_declared',
                 columns=[column('importe', 'el total de la fila', 'owner_declared')]),
            dict(id='t2', name='tarifas', description='', grain='', semantic_status='unknown',
                 columns=[column('importe', 'el precio por unidad', 'owner_declared')])],
            metrics=[dict(key='m', name='Ventas netas', unit='EUR', table_ids=['t1'], definition='importe menos descuento, por fila',
                          period={'from': '2025-01-01', 'until': None})])
        text = self.compose(model=model)
        self.assertIn('En «ventas», cada fila es un día y un producto.', text)
        self.assertIn('«importe» en «ventas» es el total de la fila.', text)
        self.assertIn('«importe» en «tarifas» es el precio por unidad.', text)
        self.assertIn('Métrica «Ventas netas» (unidad: EUR), con «ventas» (desde 2025-01-01): importe menos descuento, por fila.', text)

    def test_memory_keeps_each_declarations_effective_period(self):
        old = {**fact('Abrimos de lunes a sábado'), 'period': {'from': None, 'until': '2025-02-28'}}
        new = {**fact('Abrimos todos los días'), 'period': {'from': '2025-03-01', 'until': None}}
        text = self.compose(memory=[old, new])
        self.assertIn('- Abrimos de lunes a sábado (hasta 2025-02-28).\n- Abrimos todos los días (desde 2025-03-01).', text)

    def test_only_declared_memory_is_quoted_as_the_owners_statement(self):
        memory = [fact('Abrimos los domingos desde marzo'), fact('Prioridad: café en grano', kind='priority'),
                  fact('¿Abrimos en agosto?', kind='open_question'), fact('Propuesta', status='proposed'),
                  fact('Fecha dudosa', temporal='unresolved'), fact('Ver informe', kind='result_reference')]
        text = self.compose(memory=memory)
        self.assertIn(brief.MEMORY + '\n- Abrimos los domingos desde marzo.\n- Prioridad: café en grano.', text)
        for absent in ('¿Abrimos en agosto?', 'Propuesta', 'Fecha dudosa', 'Ver informe'):
            self.assertNotIn(absent, text)

    def test_identity_and_goal_defaults(self):
        self.assertTrue(self.compose(description='Tostadores en Lugo').startswith('Mi negocio es Tienda Ejemplo. Tostadores en Lugo.'))
        self.assertTrue(self.compose(description='').startswith('Mi negocio es Tienda Ejemplo. Los CSV'))
        self.assertIn(brief.DEFAULT_GOAL + ' ' + brief.REQUEST, self.compose(goal='  '))


class PanoramaRenderTests(unittest.TestCase):
    groups = [('A1', 'TI', 3), ('A2', 'WE', 2), ('A1', 'WE', 1)]
    names = {'product': {'A1': 'Café', 'A2': 'Té'}, 'channel': {'TI': 'Tienda', 'WE': 'Web'}}

    def test_shifted_dates_choose_rules_from_the_data_not_a_fixed_year(self):
        rows = daily(date(2018, 1, 1), 821, self.groups)
        text = panorama_v1.render(*summary(rows), self.names)
        self.assertTrue(text.startswith(panorama_v1.HEADER + '\n\nDel 1 de enero de 2018 al 31 de marzo de 2020: '))
        self.assertIn(panorama_v1.COMPARISON['year_to_date_same_months'], text)
        self.assertIn('Por canal: Tienda: ', text)
        self.assertNotIn('2026', text)
        self.assertIn('No se detectan huecos de registros relevantes.', text)
        self.assertNotIn(panorama_v1.NOTE, text)

    def test_short_history_uses_month_rule_and_opaque_codes_are_not_names(self):
        rows = daily(date(2030, 6, 1), 92, self.groups)
        text = panorama_v1.render(*summary(rows), {})
        self.assertIn(panorama_v1.COMPARISON['month_previous_month'], text)
        self.assertIn('TI (código sin nombre verificado)', text)
        self.assertIn('WE (código sin nombre verificado)', text)
        self.assertNotIn('Tienda', text)

    def test_material_gap_is_listed_and_the_rest_are_counted(self):
        start = date(2024, 1, 1)
        stop = date(2024, 12, 20)
        old = lambda d, g: g == ('A2', 'WE') and date(2024, 3, 4) <= d <= date(2024, 3, 6)
        recent = lambda d, g: g[1] == 'WE' and d >= stop
        rows = daily(start, 366, self.groups, skip=lambda d, g: old(d, g) or recent(d, g))
        text = panorama_v1.render(*summary(rows), self.names)
        self.assertIn('Huecos de registros relevantes:\n\n- Web: sin registros del 20 de diciembre de 2024 al 31 de diciembre de 2024.', text)
        self.assertRegex(text, r'Hay otros [0-9.]+ huecos de registros no incluidos aquí\.')
        self.assertTrue(text.endswith(panorama_v1.NOTE + '\n'))
        self.assertNotIn('anteriores a', text)

    def test_numbers_use_spanish_grouping(self):
        self.assertEqual(panorama_v1.number('482439'), '482.439')
        self.assertEqual(panorama_v1.number('-762'), '-762')
        self.assertEqual(panorama_v1.number('1234.50'), '1.234,5')
        self.assertEqual(panorama_v1.number('5.00000000'), '5')
        big = '12345678901234567890123456789.12345678'
        self.assertEqual(panorama_v1.number(big), '12.345.678.901.234.567.890.123.456.789,12345678')
        self.assertEqual(panorama_v1.number('-0.00000000'), '0')


class PanoramaInputsTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.WebTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.WebTests.tearDownClass.__func__)
    setUp = fixtures.WebTests.setUp

    def write(self, name, text):
        path = Path(self.temp.name) / name
        path.write_text(text)
        return path

    def sales(self, start=date(2025, 1, 1), days=200):
        lines = ['fecha,producto_id,canal_id,unidades,importe']
        for i in range(days):
            day = (start + timedelta(days=i)).isoformat()
            lines += [f'{day},P1,TI,{2 + i % 3},10', f'{day},P2,WE,1,4']
        return self.write('ventas.csv', '\n'.join(lines) + '\n')

    def job(self, paths, goal='Quiero saber qué revisar primero.', **changes):
        imported = import_batch(self.config, self.business['id'], paths)
        return {**dict(business_id=self.business['id'], analysis_id=imported['analysis']['id'], engine_config={'goal': goal},
                       origin='upload', business_name='Test shop', context='una tienda de prueba.', business_revision=1), **changes}

    def inputs(self, job):
        builder, context = engine_jobs.inputs(self.config, job)
        with connect(self.config) as db, db.transaction():
            prompt, provenance = builder(db)
        return prompt, context, provenance

    def test_sales_with_catalogs_produce_named_panorama_and_matching_brief(self):
        products = self.write('productos.csv', 'producto_id,nombre\nP1,Café de la casa\nP2,Tetera\n')
        channels = self.write('canales.csv', 'canal_id,nombre\nTI,Tienda física\nWE,Web propia\n')
        prompt, context, provenance = self.inputs(self.job([self.sales(), products, channels]))
        self.assertIn('Café de la casa / Tienda física', context['panorama.md'])
        self.assertIn(brief.PANORAMA, prompt)
        self.assertEqual(provenance['panorama']['status'], 'available')
        self.assertEqual(set(provenance['panorama']['catalogs']), {'product', 'channel'})
        self.assertEqual(provenance['version'], brief.VERSION)
        self.assertTrue(prompt.startswith('Mi negocio es Test shop'))

    def test_ambiguous_or_duplicate_catalogs_name_nothing(self):
        first = self.write('productos.csv', 'producto_id,nombre\nP1,Uno\nP2,Dos\n')
        second = self.write('catalogo.csv', 'producto_id,name\nP1,One\nP2,Two\n')
        channels = self.write('canales.csv', 'canal_id,nombre\nTI,Tienda\nTI,Otra\nWE,Web\n')
        _, context, provenance = self.inputs(self.job([self.sales(), first, second, channels]))
        self.assertEqual(provenance['panorama']['catalogs'], {})
        self.assertIn('P1 (código sin nombre verificado)', context['panorama.md'])

    def test_non_sales_data_is_closed_unavailable_without_diagnostics(self):
        other = self.write('visitas.csv', 'mes,visitas\n2025-01-01,10\n2025-02-01,12\n')
        prompt, context, provenance = self.inputs(self.job([other]))
        self.assertIsNone(context)
        self.assertNotIn('panorama', prompt.casefold())
        self.assertEqual(provenance['panorama']['status'], 'unavailable')
        self.assertNotIn(provenance['panorama']['reason'], prompt)

    def test_two_sales_tables_are_not_merged(self):
        first = self.sales()
        second = self.write('ventas2.csv', first.read_text().replace(',10\n', ',11\n'))
        _, context, provenance = self.inputs(self.job([first, second]))
        self.assertIsNone(context)
        self.assertEqual(provenance['panorama']['status'], 'unavailable')

    def test_english_headers_and_declared_meanings_reach_the_brief(self):
        path = self.write('sales.csv', 'date,product,channel,units\n' + ''.join(
            f'{(date(2025, 1, 1) + timedelta(days=i)).isoformat()},X,Y,{1 + i % 2}\n' for i in range(120)))
        job = self.job([path])
        from decision_room.data_knowledge import service as knowledge
        model = knowledge.ensure(self.config, self.business['id'], job['analysis_id'])
        table = model['body']['tables'][0]['id']
        knowledge.change(self.config, self.business['id'], job['analysis_id'], model['revision'], 'table',
                         {'id': table, 'grain': 'un día, un producto y un canal',
                          'columns': [{'name': 'units', 'meaning': 'las unidades vendidas por día'}]})
        prompt, context, _ = self.inputs(job)
        self.assertIn('«units» es las unidades vendidas por día.', prompt)
        self.assertIsNotNone(context)

    def test_job_frozen_description_wins_and_chat_reads_the_current_profile(self):
        path = self.sales()
        prompt, _, provenance = self.inputs(self.job([path], context='una tostadora congelada al crear el trabajo.'))
        self.assertTrue(prompt.startswith('Mi negocio es Test shop, una tostadora congelada al crear el trabajo.'))
        self.assertEqual((provenance['profile'], provenance['profile_revision']), ('job', 1))
        chat = self.job([path], origin='chat', context='{"context": {"historical_owner_quotes": []}}')
        prompt, _, provenance = self.inputs(chat)
        self.assertNotIn('historical_owner_quotes', prompt)
        self.assertTrue(prompt.startswith('Mi negocio es Test shop, unit price, selected sales only.'))
        self.assertEqual(provenance['profile'], 'current')

    def test_brief_and_dependency_baseline_share_one_data_model_revision(self):
        from decision_room.data_knowledge import service as knowledge
        from decision_room.engine import api
        job = self.job([self.sales()])
        model = knowledge.ensure(self.config, self.business['id'], job['analysis_id'])
        builder, context = engine_jobs.inputs(self.config, job)
        table = model['body']['tables'][0]['id']
        # A definition saved after the panorama but before run creation reaches both records.
        knowledge.change(self.config, self.business['id'], job['analysis_id'], model['revision'], 'table',
                         {'id': table, 'columns': [{'name': 'unidades', 'meaning': 'las unidades vendidas'}]})
        run, _ = api.prepare_report(self.config, job['business_id'], job['analysis_id'], owner_context='x',
                                    request_key=uuid4().hex, engine_config=self.engine_config(), builder=builder, context=context)
        with connect(self.config) as db:
            row = db.execute('SELECT prompt,brief FROM engine_runs WHERE id=%s', (run,)).fetchone()
            baseline = db.execute('SELECT data_models FROM engine_report_contexts WHERE run_id=%s', (run,)).fetchone()
        self.assertIn('«unidades» es las unidades vendidas.', row['prompt'])
        self.assertEqual([row['brief']['data_model']], baseline['data_models'])

    def test_f0_and_f1_jobs_keep_their_captured_prompt(self):
        from decision_room.engine import admission
        settings = dict(prompt='Encargo provisional', prompt_sha256=admission.sha(b'Encargo provisional'),
                        input_request_sha256='r', owner_context='x')
        self.assertEqual(engine_jobs.creation(self.config, dict(engine_config=settings, request_sha256='r')),
                         {'frozen_prompt': 'Encargo provisional'})
        with self.assertRaises(ValueError):
            engine_jobs.creation(self.config, dict(engine_config={**settings, 'prompt': 'cambiado'}, request_sha256='r'))

    def engine_config(self):
        from unittest.mock import patch
        from decision_room.engine import profile
        with patch.dict('os.environ', {'DECISION_ROOM_ENGINE_IMAGE_ID': 'sha256:' + 'a' * 64}):
            return profile.configuration()

    def test_sections_over_the_group_limit_make_the_panorama_unavailable(self):
        lines = ['fecha,producto_id,canal_id,unidades']
        for i in range(120):
            day = (date(2025, 1, 1) + timedelta(days=i)).isoformat()
            lines += [f'{day},P1,C{c},1' for c in range(501) if i < 100 or c % 2]
        _, context, provenance = self.inputs(self.job([self.write('muchos.csv', '\n'.join(lines) + '\n')]))
        self.assertIsNone(context)
        self.assertEqual(provenance['panorama']['status'], 'unavailable')
        self.assertIn('superan el límite', provenance['panorama']['reason'])

    def test_oversized_panorama_is_unavailable_instead_of_failing_the_job(self):
        channels = self.write('canales.csv', 'canal_id,nombre\nTI,' + 'T' * 140000 + '\nWE,' + 'W' * 140000 + '\n')
        prompt, context, provenance = self.inputs(self.job([self.sales(), channels]))
        self.assertIsNone(context)
        self.assertEqual(provenance['panorama']['status'], 'unavailable')
        self.assertNotIn('panorama', prompt.casefold())
