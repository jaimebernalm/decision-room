"""Follow-up register: verbatim native actions as owner topics; states never copied between actions."""
import json
import unittest
from uuid import uuid4

from psycopg.types.json import Jsonb

from decision_room import follow_ups
from decision_room.database import connect
from decision_room.web.errors import WebError
from tests import test_report_history as reports


def topic(id, block, sha, state='proposed'):
    return dict(id=id, block_id=block, content_sha256=sha, state=state, availability='available')


def action(id, block, sha):
    return dict(id=id, block_id=block, content_sha256=sha)


class MatchTests(unittest.TestCase):
    def test_identical_actions_stay_separate_and_a_closure_never_propagates(self):
        old = [topic('t1', 'b1', 'X', 'closed'), topic('t2', 'b2', 'X')]
        # Same positions and content: each follows its own block.
        pairs = follow_ups._match(old, [action('n1', 'b1', 'X'), action('n2', 'b2', 'X')])
        self.assertEqual({(t['id'], a['id']) for t, a in pairs}, {('t1', 'n1'), ('t2', 'n2')})
        # Reordered duplicates: positions differ and the content is not unique, so nothing is carried.
        self.assertEqual(follow_ups._match(old, [action('n1', 'b3', 'X'), action('n2', 'b4', 'X')]), [])
        # One of the two deleted: the remaining one keeps its own position.
        pairs = follow_ups._match(old, [action('n2', 'b2', 'X')])
        self.assertEqual([(t['id'], a['id']) for t, a in pairs], [('t2', 'n2')])
        # A third identical block inserted elsewhere: the two keep their positions, the new one is new.
        pairs = follow_ups._match(old, [action('n1', 'b1', 'X'), action('n2', 'b2', 'X'), action('n3', 'b3', 'X')])
        self.assertEqual(len(pairs), 2)

    def test_a_unique_moved_action_follows_and_changed_content_does_not(self):
        old = [topic('t1', 'b1', 'A', 'checked'), topic('t2', 'b2', 'B')]
        pairs = follow_ups._match(old, [action('n1', 'b5', 'A'), action('n2', 'b2', 'B2')])
        self.assertEqual([(t['id'], a['id']) for t, a in pairs], [('t1', 'n1')])


class RegisterTests(reports.HistoryTests):
    for name in [n for n in dir(reports.HistoryTests) if n.startswith('test_')]:
        locals()[name] = None
    del name

    def topics(self, include_closed=True):
        with connect(self.config) as db:
            return follow_ups.listing(db, self.business['id'], include_closed=include_closed)

    def state(self, item, state, **extra):
        return follow_ups.set_state(self.config, self.business['id'], item['id'],
                                    dict(request_key=extra.pop('key', str(uuid4())), state=state,
                                         expected_revision=extra.pop('expected', item['revision']), **extra))

    def test_each_action_is_a_verbatim_topic_with_its_report_headline(self):
        job = self.deliver()
        items = self.topics()
        self.assertEqual(len(items), 2)
        first, second = items[0], items[1]
        self.assertEqual(first['headline'], 'Crece la tienda online; la recogida en local pide revisión')
        self.assertEqual(first['priority_title'], 'Revisar la recogida en local')
        self.assertEqual(first['state'], 'proposed')
        self.assertEqual(second['content']['labels']['check'], 'Qué revisar en abril')
        self.assertIsNone(second['content']['if_confirmed'])
        self.assertTrue(all(isinstance(line, str) for line in first['content']['check']))
        follow_ups.reconcile_once(self.config)
        self.assertEqual(len(self.topics()), 2)  # Idempotent.
        self.assertEqual(str(first['document_id']), str(job['report_document_id']))

    def test_owner_states_are_audited_idempotent_and_closed_ones_are_not_open(self):
        self.deliver()
        item = self.topics()[0]
        key = str(uuid4())
        self.state(item, 'checked', note='Lo miré con las ventas de marzo.', key=key)
        self.assertEqual(self.state(item, 'checked', note='Lo miré con las ventas de marzo.', key=key)['state'], 'checked')
        with self.assertRaises(WebError):
            self.state(item, 'closed', key=key)  # Same key, other payload.
        with self.assertRaises(WebError):
            self.state(item, 'closed')  # Stale revision.
        current = next(t for t in self.topics() if t['id'] == item['id'])
        self.state(current, 'closed')
        self.assertNotIn(item['id'], [t['id'] for t in self.topics(include_closed=False)])
        with connect(self.config) as db:
            events = db.execute('SELECT from_state,to_state FROM follow_up_events WHERE follow_up_id=%s ORDER BY created_at',
                                (item['id'],)).fetchall()
            self.assertEqual(follow_ups.counts(db, self.business['id'])['closed'], 1)
        self.assertEqual([(e['from_state'], e['to_state']) for e in events], [('proposed', 'checked'), ('checked', 'closed')])
        with self.assertRaises(WebError):
            self.state(current, 'checked', link=dict(indicator_id=str(uuid4()), metric_key='x'), expected=current['revision'] + 1)
        other = self.ws.save_business(dict(request_key=str(uuid4()), expected_active_id=str(self.business['id']),
                                           name='Otra tienda', description='Otra.'))
        with self.assertRaises(WebError) as foreign:
            follow_ups.set_state(self.config, other['id'], item['id'], dict(request_key=str(uuid4()), state='closed', expected_revision=1))
        self.assertEqual(foreign.exception.status, 404)

    def test_deleting_withdraws_topics_and_restoring_brings_them_back_with_their_state(self):
        job = self.deliver()
        item = self.topics()[0]
        self.state(item, 'closed')
        data = dict(business_id=str(self.business['id']))
        self.ws.delete_report(job['id'], data)
        self.assertEqual(self.topics(), [])
        self.ws.delete_report(job['id'], data, restore=True)
        restored = next(t for t in self.topics() if t['id'] == item['id'])
        self.assertEqual(restored['state'], 'closed')

    def test_reconciliation_covers_every_report_page_by_page(self):
        jobs = [self.deliver() for _ in range(3)]
        with connect(self.config) as db:
            for table in ('follow_up_events', 'follow_up_actions', 'follow_ups', 'follow_up_sync'):
                db.execute('DELETE FROM ' + table)
        while follow_ups.reconcile_once(self.config, limit=1):
            pass
        documents = {str(t['document_id']) for t in self.topics()}
        self.assertEqual(documents, {str(j['report_document_id']) for j in jobs})

    def test_the_revision_only_moves_when_the_owner_visible_register_changes(self):
        self.deliver()
        with connect(self.config) as db, db.transaction():
            before = db.execute('SELECT follow_ups_revision FROM knowledge_heads WHERE business_id=%s', (self.business['id'],)).fetchone()
            self.assertIsNone(follow_ups.bump(db, self.business['id']))
        self.state(self.topics()[0], 'checked')
        with connect(self.config) as db:
            after = db.execute('SELECT follow_ups_revision FROM knowledge_heads WHERE business_id=%s', (self.business['id'],)).fetchone()
        self.assertGreater(after['follow_ups_revision'], before['follow_ups_revision'])
        json.dumps(follow_ups.projection(connect(self.config), self.business['id']), default=str)


if __name__ == '__main__':
    unittest.main()


class ConsumerTests(RegisterTests):
    for name in [n for n in dir(RegisterTests) if n.startswith('test_')]:
        locals()[name] = None
    del name

    def test_brief_checker_and_chat_receive_the_same_bounded_register(self):
        from decision_room import business_knowledge, chat_agent, conversations
        from decision_room.engine import brief, check_contract
        from decision_room.web import engine_jobs
        job = self.deliver()
        item = self.topics()[0]
        self.state(item, 'checked', note='Comprobado con las ventas de marzo.')
        closed = self.topics()[1]
        self.state(closed, 'closed')
        later = dict(business_id=self.business['id'], analysis_id=job['analysis_id'], origin='upload',
                     engine_config={'goal': 'Qué revisar.', 'profile': {'format': 'blocks'}},
                     business_name='Test shop', context='una tienda de prueba.', business_revision=1)
        builder, _ = engine_jobs.inputs(self.config, later)
        with connect(self.config) as db, db.transaction():
            prompt, provenance, *_ = builder(db)
            core = business_knowledge.build(db, self.business['id'], dict(analysis_id=str(job['analysis_id']), source_ids=[],
                                                                         period={'from': None, 'until': None}))
            saved = conversations.snapshot(db, self.business['id'], job['analysis_id'], 'objetivo')
        self.assertIn(brief.FOLLOW_UPS, prompt)
        self.assertIn('Revisar la recogida en local', prompt)
        self.assertIn('comprobado con datos (declarado por el propietario)', prompt)
        self.assertIn('1 tema(s) cerrado(s) no se incluyen', prompt)
        self.assertNotIn('Qué revisar en abril', prompt.split(brief.FOLLOW_UPS)[1].split('\n\n')[0])
        self.assertIn(brief.FOLLOW_UPS, provenance['checker_context'])
        self.assertEqual(provenance['follow_ups'], [dict(id=str(item['id']), state='checked')])
        self.assertIn('Los indicadores guardados y los temas abiertos', check_contract.PROMPT)
        self.assertEqual([i['id'] for i in core['follow_ups']['items']], [str(item['id'])])
        from decision_room.memory.service import encoded
        self.assertLessEqual(len(encoded(core['follow_ups']).encode()), business_knowledge.FOLLOW_UPS_BYTES)
        sources = chat_agent.sources_for(dict(chat_context=saved, retrievals=[]))
        self.assertEqual(sources['follow_ups']['label'], 'Temas abiertos de informes anteriores')
        # A later owner change makes that snapshot stale.
        with connect(self.config) as db:
            self.assertTrue(conversations.fresh(db, saved))
        self.state(next(t for t in self.topics() if t['id'] == item['id']), 'proposed')
        with connect(self.config) as db:
            self.assertFalse(conversations.fresh(db, saved))

    def test_closed_only_or_omitted_only_registers_are_still_reported(self):
        from decision_room.engine import brief
        args = dict(name='Tienda', description='Una tienda.', goal='Qué revisar.', model=None, memory=[], panorama=False,
                    data_meanings=([], False))
        closed = brief.compose(**args, follow_ups=dict(items=[], omitted=0, counts=dict(open=0, closed=2, withdrawn=0)))
        self.assertIn(brief.FOLLOW_UPS, closed)
        self.assertIn('2 tema(s) cerrado(s) no se incluyen', closed)
        omitted = brief.compose(**args, follow_ups=dict(items=[], omitted=1, counts=dict(open=1, closed=0, withdrawn=0)))
        self.assertIn('1 tema(s) abierto(s) más no caben aquí', omitted)
        self.assertNotIn(brief.FOLLOW_UPS, brief.compose(**args, follow_ups=dict(items=[], omitted=0, counts={})))

    def test_a_link_freezes_the_current_value_the_owner_saw_with_its_meanings_caveat(self):
        from decision_room import business_knowledge, indicators
        from decision_room.engine import brief
        job = self.deliver()
        item = self.topics()[0]
        b, analysis = self.business['id'], job['analysis_id']
        indicator, version, old, new = uuid4(), uuid4(), uuid4(), uuid4()
        inherited = dict(dataset_version=1, current_meanings_confirmed=False, confirmed=[], inherited=['ventas: column:unidades'])
        with connect(self.config) as db:
            db.execute("INSERT INTO saved_indicators(id,business_id,dataset_id,name,status) VALUES (%s,%s,%s,'Unidades','active')",
                       (indicator, b, analysis))
            db.execute('''INSERT INTO indicator_versions(id,business_id,indicator_id,version,state,code,code_sha256,tables,metric_keys,
                definitions,signature,signature_sha256,provenance) VALUES (%s,%s,%s,1,'proposed','x','x','[]','["unidades"]','{}','{}','x','{}')''',
                       (version, b, indicator))
            other = uuid4()  # A second dataset version: a copy of the analysis row under a new id.
            db.execute('''INSERT INTO analyses SELECT (jsonb_populate_record(NULL::analyses, to_jsonb(a) || jsonb_build_object('id', %s::text, 'batch_sha256', md5(random()::text)))).*
                FROM analyses a WHERE id=%s''', (other, analysis))
            db.execute('''INSERT INTO indicator_values(id,business_id,indicator_id,version_id,analysis_id,dataset_version,status,metrics,
                meanings_basis) VALUES (%s,%s,%s,%s,%s,1,'completed','{"unidades": 180}',%s),
                (%s,%s,%s,%s,%s,2,'pending',NULL,NULL)''',
                       (old, b, indicator, version, analysis, Jsonb(inherited), new, b, indicator, version, other))
            # Activated only now so no revalidation of this hand-made version runs in between.
            db.execute("UPDATE indicator_versions SET state='active' WHERE id=%s", (version,))
        self.addCleanup(self._drop_indicator, indicator, other)
        link = dict(indicator_id=str(indicator), metric_key='unidades', value_id=str(old))
        with self.assertRaises(WebError) as stale:  # The latest value is pending: no fallback to the older figure.
            self.state(item, 'checked', link=link)
        self.assertEqual(stale.exception.status, 409)
        with connect(self.config) as db:
            db.execute("UPDATE indicator_values SET status='completed',metrics='{\"unidades\": 200}',meanings_basis=%s WHERE id=%s",
                       (Jsonb(inherited), new))
        with self.assertRaises(WebError):  # The owner saw the older one: refused, not silently replaced.
            self.state(item, 'checked', link=link)
        self.state(item, 'checked', link={**link, 'value_id': str(new)}, note='Visto con el indicador.')
        with connect(self.config) as db, db.transaction():
            core = business_knowledge.follow_ups(db, b)
        [linked] = [t for t in core['items'] if t['id'] == str(item['id'])]
        self.assertEqual((linked['link']['value'], linked['link']['value_id']), (200, str(new)))
        self.assertEqual(linked['link']['meanings'], indicators.INHERITED.format(1))
        self.assertIn(indicators.INHERITED.format(1), '\n'.join(brief.follow_up_lines(core)))
        self.assertIn('check_state', linked['report'])

    def _drop_indicator(self, indicator, analysis):
        with connect(self.config) as db:
            db.execute('UPDATE follow_ups SET link=NULL')
            db.execute('UPDATE follow_up_events SET link=NULL')
            for table in ('indicator_values', 'indicator_versions', 'saved_indicators'):
                db.execute(f"DELETE FROM {table} WHERE {'id' if table == 'saved_indicators' else 'indicator_id'}=%s", (indicator,))
            db.execute('DELETE FROM analyses WHERE id=%s', (analysis,))
