"""Saved indicators: created from a published calculation, recomputed without a model, never adapted."""
import json
import unittest
from datetime import date, timedelta
from unittest.mock import patch
from uuid import uuid4

from decision_room import execution, indicators
from decision_room.database import connect
from decision_room.data_knowledge import service as knowledge
from decision_room.web import dossier
from decision_room.web.errors import WebError
from tests import test_quick_calc as qc

ROWS = 'fecha,producto_id,unidades\n' + ''.join(
    f'{(date(2025, 1, 1) + timedelta(days=i)).isoformat()},P{i % 2},{1 + i % 3}\n' for i in range(90))


class IndicatorTests(qc.ChatCalculationTests):
    for name in [n for n in dir(qc.ChatCalculationTests) if n.startswith('test_')]:
        locals()[name] = None
    del name

    def setUp(self):
        super().setUp()
        self.b = self.business['id']
        with connect(self.config) as db:  # The class shares one database: earlier tests' queues are not this test's.
            db.execute("UPDATE indicator_values SET status='unavailable',reason='test_isolation' WHERE status='pending'")
            db.execute("""UPDATE indicator_versions SET comparison=jsonb_build_object('state','unavailable','reason','test_isolation')
                WHERE state='proposed' AND comparison->>'state'='pending'""")

    def saved(self, metric_keys=('unidades',), key=None):
        turn, shown = self.send()
        calc = shown['response']['calculations'][0]['calculation_id']
        data = dict(request_key=key or str(uuid4()), turn_id=str(turn), calculation_id=calc, name='Unidades vendidas',
                    metric_keys=list(metric_keys))
        return indicators.create(self.config, self.b, data), data

    def update(self, content=ROWS, filename='ventas.csv', mode='update', previous=None):
        self.uploads = getattr(self, 'uploads', 0) + 1  # Distinct content per upload, never a reused file.
        extra = [f'2025-12-{self.uploads:02d}', 'P9', str(self.uploads)] + ['web'] * (content.split('\n', 1)[0].count(',') - 2)
        content = content + ','.join(extra) + '\n'
        result = dossier.upload(self.ws.scoped(self.b), dict(business_id=str(self.b), request_key=str(uuid4()), title='Ventas',
                                                              mode=mode, previous_id=str(previous or self.analysis)),
                                filename, content.encode())
        return result['analysis_id']

    def values(self, indicator):
        with connect(self.config) as db:
            return db.execute('SELECT * FROM indicator_values WHERE indicator_id=%s ORDER BY dataset_version', (indicator,)).fetchall()

    def declare(self, analysis, **column):
        head = knowledge.ensure(self.config, self.b, analysis)
        table = next(t for t in head['body']['tables'] if 'unidades' in [c['name'] for c in t['columns']])
        return knowledge.change(self.config, self.b, analysis, head['revision'], 'table',
                                dict(id=table['id'], columns=[dict(name='unidades', **column)]))

    def test_saved_from_a_published_calculation_with_its_first_value_copied(self):
        created, data = self.saved()
        self.assertEqual(len(self.backend.runs), 1)  # Only the chat calculation ran.
        [value] = self.values(created['indicator_id'])
        self.assertEqual((value['status'], value['metrics'], value['dataset_version']), ('completed', {'unidades': 180}, 1))
        self.assertTrue(value['meanings_basis']['current_meanings_confirmed'])
        self.assertEqual(indicators.create(self.config, self.b, data), created)  # Same key and payload.
        with self.assertRaises(WebError) as changed:
            indicators.create(self.config, self.b, {**data, 'name': 'Otro nombre'})
        self.assertEqual(changed.exception.status, 409)
        for bad in (dict(metric_keys=[]), dict(metric_keys=['otra']), dict(metric_keys=['unidades', 'unidades']),
                    dict(calculation_id=str(uuid4())), dict(turn_id=str(uuid4()))):
            with self.assertRaises(WebError):
                indicators.create(self.config, self.b, {**data, 'request_key': str(uuid4()), **bad})
        other = self.ws.save_business(dict(request_key=str(uuid4()), expected_active_id=str(self.b), name='Otra tienda',
                                           description='Otra.'))
        with self.assertRaises(WebError) as foreign:
            indicators.create(self.config, other['id'], {**data, 'request_key': str(uuid4())})
        self.assertEqual(foreign.exception.status, 404)
        self.ws.select_business(dict(business_id=str(self.b)))

    def test_a_new_version_is_recomputed_without_a_model_and_only_once(self):
        created, _ = self.saved()
        newer = self.update()
        [old, pending] = self.values(created['indicator_id'])
        self.assertEqual((pending['status'], str(pending['analysis_id'])), ('pending', str(newer)))
        self.backend.payload = qc.result({'unidades': 200})
        self.assertTrue(indicators.work_once(self.config))
        [_, done] = self.values(created['indicator_id'])
        self.assertEqual((done['status'], done['metrics']), ('completed', {'unidades': 200}))
        self.assertEqual(len(self.backend.runs), 2)
        self.assertFalse(indicators.work_once(self.config))  # Nothing due: no rerun.
        with connect(self.config) as db:
            attempt = db.execute('SELECT * FROM indicator_attempts WHERE value_id=%s', (done['id'],)).fetchone()
            run = db.execute('SELECT request_key,status FROM executions WHERE id=%s', (attempt['execution_id'],)).fetchone()
        self.assertEqual(run['request_key'], indicators.PREFIX + str(attempt['id']))
        self.assertEqual((attempt['admission'], attempt['outcome']), ('admitted', 'completed'))
        self.assertTrue(attempt['runtime'])
        with connect(self.config) as db:  # A legacy report never treats it as one of its own runs.
            db.execute("UPDATE executions SET status='running' WHERE id=%s", (attempt['execution_id'],))
            self.assertFalse(execution.open_report_runs(db, self.b))

    def test_a_fresh_version_reuses_the_declared_meanings_as_an_explicit_assumption(self):
        self.declare(self.analysis, meaning='unidades vendidas', unit='paquetes')
        self.snapshot = None
        created, _ = self.saved()
        newer = self.update()
        indicators.work_once(self.config)
        done = self.values(created['indicator_id'])[-1]
        self.assertEqual(done['status'], 'completed')
        basis = done['meanings_basis']
        self.assertFalse(basis['current_meanings_confirmed'])
        self.assertEqual(basis['dataset_version'], 1)
        self.assertIn('ventas: column:unidades', basis['inherited'])
        # A second fresh update still attributes version 1, never the intermediate one.
        self.update(previous=newer)
        indicators.work_once(self.config)
        self.assertEqual(self.values(created['indicator_id'])[-1]['meanings_basis']['dataset_version'], 1)

    def test_declared_changes_withdrawals_and_structure_stop_it_with_a_reason(self):
        self.declare(self.analysis, meaning='unidades vendidas', unit='paquetes')
        created, _ = self.saved()
        newer = self.update()
        self.declare(newer, meaning='unidades vendidas', unit='cajas')  # Declared differently.
        indicators.work_once(self.config)
        self.assertEqual(self.values(created['indicator_id'])[-1]['reason'], 'meanings_changed')
        third = self.update(previous=newer)
        self.declare(third, meaning='unidades vendidas', unit='paquetes')
        self.declare(third, meaning='', unit='', conversion='')  # Explicitly withdrawn by the owner.
        indicators.work_once(self.config)
        self.assertEqual(self.values(created['indicator_id'])[-1]['reason'], 'meanings_unknown')
        wider = 'fecha,producto_id,unidades,canal\n' + ''.join(line + ',web\n' for line in ROWS.splitlines()[1:])
        self.update(previous=third, content=wider)
        indicators.work_once(self.config)
        self.assertEqual(self.values(created['indicator_id'])[-1]['reason'], 'schema_changed')
        self.assertEqual(len(self.backend.runs), 1)  # None of these ran the code.

    def test_a_missing_file_leaves_it_unavailable_without_running(self):
        created, _ = self.saved()
        self.update(filename='otro_nombre.csv')
        indicators.work_once(self.config)
        self.assertEqual(self.values(created['indicator_id'])[-1]['reason'], 'missing_table')
        self.assertEqual(len(self.backend.runs), 1)

    def test_a_failing_program_leaves_it_unavailable_with_its_error(self):
        created2, _ = self.saved()
        self.backend.status, self.backend.stderr = 'failed', 'Binder Error: column "unidades" not found'
        self.update()
        while indicators.work_once(self.config):
            pass
        last = [v for v in self.values(created2['indicator_id'])][-1]
        self.assertEqual((last['status'], last['reason']), ('unavailable', 'program_failed'))
        self.assertIn('unidades', last['detail'])

    def test_transient_failures_retry_later_with_a_new_attempt_and_the_same_formula(self):
        created, _ = self.saved()
        self.update()
        with patch.object(execution, 'execute', side_effect=ValueError('Local sandbox is busy. Retry later.')):
            self.assertTrue(indicators.work_once(self.config))
        pending = self.values(created['indicator_id'])[-1]
        self.assertEqual(pending['status'], 'pending')
        self.assertIsNotNone(pending['next_attempt_at'])
        self.assertFalse(indicators.work_once(self.config))  # Not due yet: no busy loop.
        with connect(self.config) as db:
            db.execute('UPDATE indicator_values SET next_attempt_at=now() WHERE id=%s', (pending['id'],))
        self.assertTrue(indicators.work_once(self.config))
        with connect(self.config) as db:
            attempts = db.execute('SELECT attempt_no,admission,outcome,identity FROM indicator_attempts WHERE value_id=%s ORDER BY attempt_no',
                                  (pending['id'],)).fetchall()
        self.assertEqual([(a['attempt_no'], a['admission'], a['outcome']) for a in attempts],
                         [(1, 'refused', 'transient'), (2, 'admitted', 'completed')])
        self.assertEqual(attempts[0]['identity']['code_sha256'], attempts[1]['identity']['code_sha256'])

    def test_a_correction_revokes_values_and_they_are_never_current(self):
        created, _ = self.saved()
        newer = self.update()
        indicators.work_once(self.config)
        self.update(mode='correction', previous=newer)
        values = self.values(created['indicator_id'])
        self.assertEqual([v['status'] for v in values], ['completed', 'revoked', 'pending'])
        with connect(self.config) as db:
            current = indicators.current_values(db, self.b, created['indicator_id'])
        self.assertEqual(current[0]['status'], 'pending')  # The latest eligible version, not an older completed one.
        self.assertNotIn('revoked', [v['status'] for v in current])

    def test_one_to_one_mapping_never_takes_the_first_of_several(self):
        created, _ = self.saved()
        with connect(self.config) as db:
            version = db.execute("SELECT tables FROM indicator_versions WHERE indicator_id=%s", (created['indicator_id'],)).fetchone()
            rows, failure = indicators.mapping(db, self.b, self.analysis, [dict(version['tables'][0], alias='a'),
                                                                          dict(version['tables'][0], alias='b')])
        self.assertIsNone(rows)
        self.assertEqual(failure[0], 'ambiguous_table')

    def test_a_meaning_redeclared_identically_is_confirmed_and_a_changed_basis_stops_it(self):
        self.declare(self.analysis, meaning='unidades vendidas', unit='paquetes')
        created, _ = self.saved()
        newer = self.update()
        self.declare(newer, meaning='unidades vendidas', unit='paquetes')
        indicators.work_once(self.config)
        basis = self.values(created['indicator_id'])[-1]['meanings_basis']
        self.assertTrue(basis['current_meanings_confirmed'])
        self.assertIn('ventas: column:unidades', basis['confirmed'])
        # The owner later changes what the original version declared: it is no longer a valid basis.
        self.declare(self.analysis, meaning='unidades vendidas', unit='cajas')
        self.update(previous=newer)
        indicators.work_once(self.config)
        self.assertEqual(self.values(created['indicator_id'])[-1]['reason'], 'basis_changed')

    def test_a_completed_value_stops_as_soon_as_its_basis_changes_and_is_not_revived(self):
        from decision_room import business_knowledge
        self.declare(self.analysis, meaning='unidades vendidas', unit='paquetes')
        created, _ = self.saved()
        newer = self.update()
        self.backend.payload = qc.result({'unidades': 200})
        indicators.work_once(self.config)
        self.assertEqual(self.values(created['indicator_id'])[-1]['status'], 'completed')
        self.declare(self.analysis, meaning='unidades vendidas', unit='cajas')  # The basis the new value inherited.
        first, second = self.values(created['indicator_id'])
        self.assertEqual((first['status'], first['reason']), ('unavailable', 'meanings_changed'))
        self.assertEqual((second['status'], second['reason'], second['metrics']), ('unavailable', 'basis_changed', None))
        with connect(self.config) as db, db.transaction():
            self.assertEqual(indicators.current_values(db, self.b, created['indicator_id'])[0]['status'], 'unavailable')
            core = business_knowledge.build(db, self.b, dict(analysis_id=str(newer), source_ids=[], period={'from': None, 'until': None}))
            attempt = db.execute('SELECT outcome FROM indicator_attempts WHERE value_id=%s', (second['id'],)).fetchone()
        self.assertEqual(core['indicators']['items'][0]['latest']['status'], 'unavailable')
        self.assertEqual(attempt['outcome'], 'completed')  # The earlier result stays for audit.
        self.declare(self.analysis, meaning='unidades vendidas', unit='paquetes')  # Restored: still the owner's repair.
        self.assertEqual([v['status'] for v in self.values(created['indicator_id'])], ['unavailable', 'unavailable'])

    def test_withdrawing_an_inherited_meaning_in_the_new_version_stops_its_value(self):
        self.declare(self.analysis, meaning='unidades vendidas', unit='paquetes')
        created, _ = self.saved()
        newer = self.update()
        indicators.work_once(self.config)
        self.declare(newer, meaning='unidades vendidas', unit='paquetes')
        self.assertTrue(self.values(created['indicator_id'])[-1]['meanings_basis']['current_meanings_confirmed'])
        self.declare(newer, meaning='', unit='', conversion='')
        self.assertEqual(self.values(created['indicator_id'])[-1]['reason'], 'meanings_unknown')

    def test_a_table_changed_after_the_run_is_not_published_and_is_run_again(self):
        created, _ = self.saved()
        newer = self.update()
        real = execution.execute

        def changing(*args, **kwargs):
            result = real(*args, **kwargs)
            with connect(self.config) as db:
                db.execute('UPDATE prepared_tables SET row_count=row_count+1 WHERE analysis_id=%s', (newer,))
            return result
        with patch.object(execution, 'execute', side_effect=changing):
            self.assertTrue(indicators.work_once(self.config))
        value = self.values(created['indicator_id'])[-1]
        self.assertEqual(value['status'], 'pending')
        self.assertTrue(indicators.work_once(self.config))
        with connect(self.config) as db:
            attempts = db.execute('SELECT attempt_no,outcome,reason FROM indicator_attempts WHERE value_id=%s ORDER BY attempt_no',
                                  (value['id'],)).fetchall()
        self.assertEqual([(a['outcome'], a['reason']) for a in attempts], [('structural', 'identity_changed'), ('completed', None)])
        self.assertEqual(self.values(created['indicator_id'])[-1]['status'], 'completed')

    def test_a_table_changed_before_admission_is_never_run(self):
        created, _ = self.saved()
        newer = self.update()
        real = indicators._freeze

        def freeze(db, *args):
            attempt = real(db, *args)
            db.execute('UPDATE prepared_tables SET row_count=row_count+1 WHERE analysis_id=%s', (newer,))
            return attempt
        with patch.object(indicators, '_freeze', side_effect=freeze):
            indicators.work_once(self.config)
        self.assertEqual(len(self.backend.runs), 1)  # Only the chat calculation.
        with connect(self.config) as db:
            attempt = db.execute('SELECT admission,outcome,reason FROM indicator_attempts WHERE analysis_id=%s', (newer,)).fetchone()
        self.assertEqual((attempt['admission'], attempt['outcome'], attempt['reason']), ('refused', 'structural', 'identity_changed'))
        self.assertEqual(self.values(created['indicator_id'])[-1]['status'], 'pending')


class RepairTests(IndicatorTests):
    for name in [n for n in dir(IndicatorTests) if n.startswith('test_')]:
        locals()[name] = None
    del name

    def proposal(self, created):
        turn, shown = self.send('Arregla el indicador')
        calc = shown['response']['calculations'][0]['calculation_id']
        with connect(self.config) as db:
            active = db.execute("SELECT id FROM indicator_versions WHERE indicator_id=%s AND state='active'",
                                (created['indicator_id'],)).fetchone()['id']
        data = dict(request_key=str(uuid4()), turn_id=str(turn), calculation_id=calc, expected_active_version_id=str(active))
        return indicators.propose(self.config, self.b, created['indicator_id'], data), active

    def version(self, version_id):
        with connect(self.config) as db:
            return db.execute('SELECT * FROM indicator_versions WHERE id=%s', (version_id,)).fetchone()

    def confirm(self, created, proposed, active, sha=None):
        return indicators.confirm(self.config, self.b, created['indicator_id'], proposed['version_id'],
                                  dict(request_key=str(uuid4()), expected_active_version_id=str(active),
                                       comparison_sha=sha if sha is not None else self.version(proposed['version_id'])['comparison'].get('sha256')))

    def test_a_proposal_is_compared_on_earlier_data_and_activated_only_by_the_owner(self):
        created, _ = self.saved()
        proposed, active = self.proposal(created)
        with self.assertRaises(WebError):  # Comparison still pending.
            self.confirm(created, proposed, active)
        self.assertTrue(indicators.work_once(self.config))
        comparison = self.version(proposed['version_id'])['comparison']
        self.assertEqual(comparison['state'], 'match')
        self.assertEqual(comparison['policy'], indicators.POLICY)
        self.assertEqual(self.version(proposed['version_id'])['state'], 'proposed')  # A match never activates by itself.
        with self.assertRaises(WebError):
            self.confirm(created, proposed, active, sha='0' * 64)
        self.confirm(created, proposed, active)
        self.assertEqual(self.version(proposed['version_id'])['state'], 'active')
        self.assertEqual(self.version(active)['state'], 'superseded')

    def test_a_mismatch_can_still_be_confirmed_and_a_stale_proposal_cannot(self):
        created, _ = self.saved()
        first, active = self.proposal(created)
        second, _ = self.proposal(created)
        self.backend.payload = qc.result({'unidades': 999})
        while indicators.work_once(self.config):
            pass
        self.assertEqual(self.version(first['version_id'])['comparison']['state'], 'mismatch')
        rows = self.version(first['version_id'])['comparison']['metrics']
        self.assertEqual((rows[0]['before'], rows[0]['after'], rows[0]['same']), (180, 999, False))
        self.confirm(created, first, active)
        self.assertEqual(self.version(second['version_id'])['state'], 'discarded')
        with self.assertRaises(WebError) as stale:
            self.confirm(created, second, active)
        self.assertEqual(stale.exception.status, 409)

    def test_a_corrected_baseline_revokes_the_receipt_and_compares_again(self):
        created, _ = self.saved()
        proposed, active = self.proposal(created)  # Calculated on the original data.
        with connect(self.config) as db:  # Hold the comparison until the newer value exists.
            db.execute('''UPDATE indicator_versions SET comparison=comparison || '{"next_attempt_at": "2999-01-01T00:00:00+00:00"}'
                WHERE id=%s''', (proposed['version_id'],))
        newer = self.update()
        indicators.work_once(self.config)  # Value on the newer version: the latest eligible baseline.
        with connect(self.config) as db:
            db.execute("UPDATE indicator_versions SET comparison=comparison - 'next_attempt_at' WHERE id=%s", (proposed['version_id'],))
        indicators.work_once(self.config)
        receipt = self.version(proposed['version_id'])['comparison']
        self.assertEqual(receipt['baseline']['analysis_id'], str(newer))
        self.update(mode='correction', previous=newer)
        comparison = self.version(proposed['version_id'])['comparison']
        self.assertEqual(comparison['state'], 'pending')
        self.assertEqual(comparison['history'][-1]['revoked'], 'baseline_corrected')
        with self.assertRaises(WebError):
            self.confirm(created, proposed, active, sha=receipt['sha256'])
        while indicators.work_once(self.config):
            pass
        again = self.version(proposed['version_id'])['comparison']
        self.assertNotEqual(again['baseline']['analysis_id'], str(newer))
        self.confirm(created, proposed, active)

    def test_a_baseline_corrected_while_comparing_is_never_sealed(self):
        created, _ = self.saved()
        proposed, active = self.proposal(created)
        with connect(self.config) as db:
            db.execute('''UPDATE indicator_versions SET comparison=comparison || '{"next_attempt_at": "2999-01-01T00:00:00+00:00"}'
                WHERE id=%s''', (proposed['version_id'],))
        newer = self.update()
        indicators.work_once(self.config)
        with connect(self.config) as db:
            db.execute("UPDATE indicator_versions SET comparison=comparison - 'next_attempt_at' WHERE id=%s", (proposed['version_id'],))
        real = execution.execute

        def correcting(*args, **kwargs):
            result = real(*args, **kwargs)
            self.update(mode='correction', previous=newer)  # Between the run and the seal.
            return result
        with patch.object(execution, 'execute', side_effect=correcting):
            self.assertTrue(indicators._compare_once(self.config))
        comparison = self.version(proposed['version_id'])['comparison']
        self.assertEqual(comparison['state'], 'pending')
        with connect(self.config) as db:
            [attempt] = db.execute("SELECT outcome,reason,identity FROM indicator_attempts WHERE purpose='comparison' AND version_id=%s",
                                   (proposed['version_id'],)).fetchall()
        self.assertEqual((attempt['outcome'], attempt['reason']), ('structural', 'baseline_changed'))
        self.assertEqual(attempt['identity']['baseline']['analysis_id'], str(newer))
        while indicators.work_once(self.config):
            pass
        again = self.version(proposed['version_id'])['comparison']
        self.assertNotEqual(again['baseline']['analysis_id'], str(newer))
        self.confirm(created, proposed, active)

    def test_confirm_with_a_stale_baseline_really_queues_the_comparison_again(self):
        created, _ = self.saved()
        proposed, active = self.proposal(created)
        indicators.work_once(self.config)
        receipt = self.version(proposed['version_id'])['comparison']
        with connect(self.config) as db:  # The baseline stopped being current without passing through a hook.
            db.execute("UPDATE indicator_values SET status='unavailable',reason='program_failed',metrics=NULL WHERE id=%s",
                       (receipt['baseline']['value_id'],))
        with self.assertRaises(WebError) as refused:
            self.confirm(created, proposed, active, sha=receipt['sha256'])
        self.assertEqual(refused.exception.status, 409)
        comparison = self.version(proposed['version_id'])['comparison']
        self.assertEqual(comparison['state'], 'pending')  # Committed, not rolled back with the refusal.
        self.assertEqual(comparison['history'][-1]['revoked'], 'baseline_changed')

    def test_a_comparison_shows_the_meanings_basis_of_its_baseline(self):
        self.declare(self.analysis, meaning='unidades vendidas', unit='paquetes')
        created, _ = self.saved()
        proposed, _ = self.proposal(created)
        with connect(self.config) as db:
            db.execute('''UPDATE indicator_versions SET comparison=comparison || '{"next_attempt_at": "2999-01-01T00:00:00+00:00"}'
                WHERE id=%s''', (proposed['version_id'],))
        self.update()
        indicators.work_once(self.config)  # The inherited value on the newer version becomes the baseline.
        with connect(self.config) as db:
            db.execute("UPDATE indicator_versions SET comparison=comparison - 'next_attempt_at' WHERE id=%s", (proposed['version_id'],))
        indicators.work_once(self.config)
        baseline = self.version(proposed['version_id'])['comparison']['baseline']
        self.assertEqual(baseline['meanings'], indicators.INHERITED.format(1))
        self.assertFalse(baseline['meanings_basis']['current_meanings_confirmed'])

    def test_inspect_fits_with_many_proposals_and_never_offers_an_older_value_instead(self):
        created, _ = self.saved()
        newer = self.update()
        indicators.work_once(self.config)
        with connect(self.config) as db:
            db.execute('''INSERT INTO indicator_versions(id,business_id,indicator_id,version,state,code,code_sha256,tables,metric_keys,
                definitions,signature,signature_sha256,provenance,comparison)
                SELECT gen_random_uuid(),business_id,indicator_id,version+g,'proposed',code,code_sha256,tables,metric_keys,definitions,
                    signature,signature_sha256,provenance,'{"state": "unavailable", "reason": "no_baseline"}'
                FROM indicator_versions, generate_series(1,450) g WHERE indicator_id=%s AND state='active' ''',
                       (created['indicator_id'],))
            seen = indicators.inspect(db, self.b, created['indicator_id'])
            self.assertLessEqual(indicators._size(seen), indicators.INSPECT_BYTES)
            self.assertEqual((len(seen['proposed']), seen['proposed_omitted']), (indicators.INSPECT_PROPOSALS, 450 - indicators.INSPECT_PROPOSALS))
            self.assertEqual([v['dataset_version'] for v in seen['values']], [2, 1])
            db.execute("UPDATE indicator_values SET metrics=%s WHERE indicator_id=%s AND analysis_id=%s",
                       (json.dumps({'unidades': 'ñ' * 9000}), created['indicator_id'], newer))
            seen = indicators.inspect(db, self.b, created['indicator_id'])
        self.assertLessEqual(indicators._size(seen), indicators.INSPECT_BYTES)
        self.assertEqual(seen['values'], [dict(dataset_version=2, status='completed', omitted=True)])
        self.assertEqual(seen['values_omitted'], 1)

    def test_a_proposal_whose_own_data_was_corrected_is_refused(self):
        created, _ = self.saved()
        proposed, active = self.proposal(created)
        indicators.work_once(self.config)
        with connect(self.config) as db:
            db.execute('''INSERT INTO dataset_versions(business_id,analysis_id,dataset_id,version,corrected)
                VALUES (%s,%s,%s,1,true) ON CONFLICT (analysis_id) DO UPDATE SET corrected=true''', (self.b, self.analysis, self.analysis))
        with self.assertRaises(WebError) as refused:
            self.confirm(created, proposed, active)
        self.assertEqual(refused.exception.status, 409)


class IndicatorConsumerTests(IndicatorTests):
    for name in [n for n in dir(IndicatorTests) if n.startswith('test_')]:
        locals()[name] = None
    del name

    def test_core_brief_and_chat_show_latest_values_with_their_meanings_basis(self):
        from decision_room import business_knowledge, chat_agent, conversations
        from decision_room.engine import brief
        from decision_room.memory import retrieval
        self.declare(self.analysis, meaning='unidades vendidas', unit='paquetes')
        created, _ = self.saved()
        newer = self.update()
        self.backend.payload = qc.result({'unidades': 200})
        indicators.work_once(self.config)
        with connect(self.config) as db, db.transaction():
            core = business_knowledge.build(db, self.b, dict(analysis_id=str(newer), source_ids=[], period={'from': None, 'until': None}))
        [item] = core['indicators']['items']
        self.assertEqual(item['latest']['metrics'], {'unidades': 200})
        self.assertEqual(item['latest']['meanings'], indicators.INHERITED.format(1))
        lines = brief.indicator_lines(core['indicators'])
        self.assertIn('unidades = 200', lines[0])
        self.assertIn('no están confirmados en esta versión', lines[0])
        # The chat reads one indicator through its own tool; the research retriever refuses it.
        def script(context):
            done = [e for e in context['retrievals'] if e['request']['tool'] == 'inspect_indicator']
            if not done:
                return dict(action='retrieve', retrieval=dict(tool='inspect_indicator', query='', id=created['indicator_id'], limit=1),
                            analysis_id='', text='', sources=[], calculation=None, include_report=False, onboarding=None,
                            presentation_edit=None, investigation_brief=None)
            self.assertNotIn('error', done[0]['response'])
            self.assertIn('write_result', done[0]['response']['version']['code'])
            self.assertLessEqual(len(json.dumps(done[0]['response'], ensure_ascii=False).encode()), indicators.INSPECT_BYTES)
            return qc.answer('El indicador vale 200 con los últimos datos.', [f"tool/{done[0]['ordinal']}", 'indicators'])
        self.script = script
        turn, shown = self.send('¿Cuánto vale el indicador?')
        self.assertEqual(shown['status'], 'completed', shown)
        labels = {s['label'] for s in shown['response']['sources']}
        self.assertEqual(labels, {'Indicador guardado', 'Indicadores guardados'})
        with connect(self.config) as db, self.assertRaises(ValueError):
            retrieval.retrieve(self.config, db, None, dict(tool='inspect_indicator', query='', id=created['indicator_id'], limit=1),
                               manifest=dict(business_id=str(self.b)))
        # A new value makes earlier chat context stale.
        with connect(self.config) as db:
            saved = db.execute('SELECT snapshot FROM chat_turns WHERE id=%s', (turn,)).fetchone()['snapshot']
            self.assertTrue(conversations.fresh(db, saved))
            db.execute("UPDATE indicator_values SET status='unavailable',reason='program_failed',metrics=NULL WHERE indicator_id=%s AND analysis_id=%s",
                       (created['indicator_id'], newer))
            with db.transaction():
                indicators.bump(db, self.b)
            self.assertFalse(conversations.fresh(db, saved))
        del chat_agent


class IndicatorApiTests(IndicatorTests):
    for name in [n for n in dir(IndicatorTests) if n.startswith('test_')]:
        locals()[name] = None
    del name
    http = qc.fixtures.WebTests.http

    def test_http_routes_and_home_cards_are_scoped_and_typed(self):
        from decision_room.web import home
        turn, shown = self.send()
        calc = shown['response']['calculations'][0]['calculation_id']
        client, server = self.http()
        client.post('/api/login', json={'token': server.token})
        self.ws.select_business(dict(business_id=str(self.b)))
        body = dict(business_id=str(self.b), request_key=str(uuid4()), turn_id=str(turn), calculation_id=calc,
                    name='Unidades vendidas', metric_keys=['unidades'])
        created = client.post('/api/indicators', json=body)
        self.assertEqual(created.status_code, 200, created.text)
        self.assertEqual(client.post('/api/indicators', json={**body, 'business_id': str(uuid4())}).status_code, 409)
        overview = client.get('/api/indicators').json()
        [item] = overview['indicators']
        self.assertEqual(item['values'][0]['display'], {'unidades': '180'})
        self.assertEqual(overview['label'], indicators.LABEL)
        cards = [i for i in home.collect(self.ws.scoped(self.b))['items'] if i['source'].get('origin') == 'indicator']
        self.assertEqual([c['id'] for c in cards], [f"indicator:{item['id']}:unidades"])
        self.assertIsNone(cards[0]['source']['report_id'])
        missing = client.post(f'/api/follow-ups/{uuid4()}/state', json=dict(business_id=str(self.b), request_key=str(uuid4()),
                                                                              state='closed', expected_revision=1))
        self.assertEqual(missing.status_code, 404)
        retired = client.post(f"/api/indicators/{item['id']}/retire", json=dict(business_id=str(self.b), request_key=str(uuid4()),
                                                                                 expected_revision=item['revision']))
        self.assertEqual(retired.status_code, 200, retired.text)
        self.assertEqual([i for i in home.collect(self.ws.scoped(self.b))['items'] if i['source'].get('origin') == 'indicator'], [])


class BoundTests(unittest.TestCase):
    def test_the_whole_projection_fits_its_budget_with_its_counters(self):
        from decision_room import business_knowledge
        from decision_room.memory.service import encoded
        for count in (1, 7, 40):
            items = [dict(text='ñandú ' * (8 + i % 5)) for i in range(count)]
            for limit in (200, 1000, business_knowledge.INDICATORS_BYTES):
                out = business_knowledge._bounded(items, limit, lambda kept, omitted: dict(items=kept, omitted=omitted, use='x' * 60))
                self.assertLessEqual(len(encoded(out).encode()), limit)
                self.assertEqual(len(out['items']) + out['omitted'], count)
