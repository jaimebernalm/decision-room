"""Shared context: real PostgreSQL, checkpoints and sandbox, scripted decisions."""
import json
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from decision_room.agent import service, research, review
from decision_room.agent.persistence import model_call
from decision_room.database import connect, migrate
from decision_room.execution import execute
from decision_room.memory import service as memory, context as contexts, retrieval, extraction
from decision_room.service import create_business, import_batch
import test_agent
from test_agent import ScriptedModel
from test_memory import content, candidate, MemoryModel
from test_research import ResearchModel
from test_review import DialogueModel


class MemoryAwareModel(DialogueModel):
    identity = {'model': 'context-test-only'}

    def __init__(self):
        super().__init__('plain')
        self.seen = []

    def generate(self, context, correction=None):
        self.seen.append(deepcopy(context))
        rows = context['business_context']['memories']
        declared = [r for r in rows if r['content']['kind'] == 'definition' and r['status'] == 'declared']
        if not declared:
            return ScriptedModel.generate(self, context, correction)
        result, usage = ResearchModel.generate(self, context, correction)
        result['proposal']['interpretations'] = [dict(aspect='meaning', statement=declared[0]['content']['statement'],
            status='confirmed', references=[dict(kind='memory', id=declared[0]['id'], column='')])]
        return result, usage

    def generate_research(self, context, correction=None):
        self.seen.append(deepcopy(context))
        facts = context['business_context']['memories']
        # This deterministic model chooses a formula using only delivered definitions.
        context = {**context, 'owner_context': ' '.join(f['content']['statement'] for f in facts if f['status'] == 'declared')}
        return ResearchModel.generate_research(self, context, correction)


class ContextTests(unittest.TestCase):
    setUpClass = classmethod(test_agent.AgentTests.setUpClass.__func__)
    tearDownClass = classmethod(test_agent.AgentTests.tearDownClass.__func__)
    setUp = test_agent.AgentTests.setUp

    def fact(self, statement='Amount is unit price. Quantity is units.', **kwargs):
        with connect(self.config) as db:
            source = db.execute('SELECT id FROM sources WHERE analysis_id=%s', (self.analysis,)).fetchone()['id']
        return memory.change(self.config, self.business, action='declare', request_key=uuid4().hex,
            content=content(statement, topic='amount_basis', kind='definition', scope='source', scope_id=str(source), **kwargs))

    def start(self, key=None, period=None, model=None):
        return service.start(self.config, self.business, self.analysis, owner_context='Total vendido',
                             request_key=key or uuid4().hex, request_period=period, model=model or MemoryAwareModel())

    def complete(self, plan, model=None):
        model = model or MemoryAwareModel()
        work = research.start(self.config, self.business, plan['id'], request_key=uuid4().hex, model=model)
        report = review.start(self.config, self.business, work['id'], request_key=uuid4().hex, analyst=model, reviewer=model)
        self.assertTrue(report['publishable'])
        return work, report

    def correct(self, fact, statement='Amount is whole row total. Quantity is units.', **kwargs):
        current = memory.read(self.config, self.business, fact_id=fact['fact_id'])[0]
        return memory.change(self.config, self.business, action='correct', request_key=uuid4().hex,
            fact_id=fact['fact_id'], expected_revision=current['revision'],
            content={**current['content'], 'statement': statement, **kwargs})

    def test_two_sessions_reuse_then_correction_revokes_and_recalculates(self):
        fact = self.fact()
        model = MemoryAwareModel()
        a, b = self.start(model=model), self.start()
        self.assertFalse(a['questions'])
        self.assertFalse(b['questions'])
        wa, ra = self.complete(a, model)
        wb, rb = self.complete(b)
        self.assertEqual(wa['steps'][0]['execution']['result']['metrics']['total'], '80.0000')
        self.correct(fact)
        for p, w, r in ((a, wa, ra), (b, wb, rb)):
            self.assertTrue(service.show(self.config, self.business, p['id'])['context_stale'])
            self.assertEqual(research.show(self.config, self.business, w['id'])['status'], 'stale')
            self.assertFalse(review.show(self.config, self.business, r['id'])['publishable'])
            with self.assertRaisesRegex(ValueError, 'memory changed'):
                service.resume(self.config, self.business, p['id'], model=model)
        successor = service.replan(self.config, self.business, a['id'], owner_context='Total vendido',
                                   request_key='corrected', model=model)
        work, report = self.complete(successor, model)
        self.assertEqual(work['steps'][0]['execution']['result']['metrics']['total'], '30.00')
        self.assertNotEqual(report['id'], ra['id'])
        with connect(self.config) as db:
            calls = db.execute('SELECT context_payload,phase FROM agent_calls WHERE session_id=%s', (successor['id'],)).fetchall()
        self.assertEqual({c['phase'] for c in calls}, {'planning','research','analyst_review','reviewer'})
        self.assertEqual({c['context_payload']['business_context']['memories'][0]['revision'] for c in calls}, {2})

    def test_future_change_preserves_june_but_invalidates_september(self):
        fact = self.fact()
        june = self.start(period={'from':'2026-06-01','until':'2026-06-30'})
        september = self.start(period={'from':'2026-09-01','until':'2026-09-30'})
        _, historical = self.complete(june)
        old = memory.read(self.config, self.business, fact_id=fact['fact_id'])[0]
        memory.change(self.config, self.business, action='correct', change_kind='future', request_key='future',
            fact_id=fact['fact_id'], expected_revision=1, content={**old['content'], 'statement':'Amount is row total from September.',
                'temporal_scope':'dated','valid_from':'2026-09-01'})
        self.assertFalse(service.show(self.config, self.business, june['id'])['context_stale'])
        self.assertTrue(review.show(self.config, self.business, historical['id'])['publishable'])
        self.assertTrue(service.show(self.config, self.business, september['id'])['context_stale'])
        new_june = self.start(period={'from':'2026-06-01','until':'2026-06-30'})
        self.assertEqual(new_june['context_manifest']['initial_context']['memories'][0]['revision'], 1)

    def test_irrelevant_scope_priority_future_and_other_business_do_not_invalidate(self):
        self.fact()
        plan = self.start(period={'from':'2026-06-01','until':'2026-06-30'})
        other = create_business(self.config, 'Separate')['id']
        memory.change(self.config, other, action='declare', request_key='other', content=content())
        memory.change(self.config, self.business, action='declare', request_key='priority', content=content(kind='priority'))
        memory.change(self.config, self.business, action='declare', request_key='future', content=content(topic='new_hours', valid_from='2026-09-01'))
        path = self.root / 'unrelated.csv'
        path.write_text('dates,stock\n2026-01-01,1\n')
        new = import_batch(self.config, self.business, [path])['analysis']['id']
        memory.change(self.config, self.business, action='declare', request_key='unrelated',
                      content=content(scope='analysis', scope_id=str(new)))
        self.assertFalse(service.show(self.config, self.business, plan['id'])['context_stale'])

    def test_new_relevant_doubt_invalidates_even_if_not_previously_selected(self):
        self.fact()
        plan = self.start()
        memory.change(self.config, self.business, action='propose', request_key='doubt',
                      content=content(topic='uncertain_dates', kind='open_question'))
        self.assertTrue(service.show(self.config, self.business, plan['id'])['context_stale'])

    def test_withdrawn_fact_is_absent_and_old_source_cannot_restore_it(self):
        fact = self.fact()
        plan = self.start()
        memory.change(self.config, self.business, action='withdraw', request_key='withdraw', fact_id=fact['fact_id'], expected_revision=1)
        other = self.start()
        self.assertEqual(other['context_manifest']['initial_context']['memories'], [])
        self.assertTrue(other['questions'])
        self.assertTrue(service.show(self.config, self.business, plan['id'])['context_stale'])
        with connect(self.config) as db:
            response, _ = retrieval.retrieve(self.config, db, other['id'], dict(tool='search_memory',query='',id='',limit=10))
            self.assertEqual(response['memories'], [])

    def test_correction_during_python_cannot_complete_or_publish(self):
        fact = self.fact()
        plan = self.start()
        def racing(*args, **kwargs):
            result = execute(*args, **kwargs)
            self.correct(fact)
            return result
        with self.assertRaisesRegex(ValueError, 'stale'):
            research.start(self.config, self.business, plan['id'], request_key='race', model=MemoryAwareModel(), executor=racing)
        with connect(self.config) as db:
            self.assertEqual(db.execute('SELECT status FROM agent_research WHERE session_id=%s', (plan['id'],)).fetchone()['status'], 'stale')
            self.assertEqual(db.execute('SELECT count(*) n FROM executions WHERE business_id=%s', (self.business,)).fetchone()['n'], 1)

    def test_correction_inside_approval_is_rejected(self):
        fact = self.fact()
        model = MemoryAwareModel()
        plan = self.start(model=model)
        work = research.start(self.config, self.business, plan['id'], request_key='work', model=model)
        original = model.generate_reviewer
        def race(context, correction=None):
            response = original(context, correction)
            self.correct(fact)
            return response
        with patch.object(model,'generate_reviewer',side_effect=race), self.assertRaisesRegex(ValueError,'memory changed'):
            review.start(self.config,self.business,work['id'],request_key='race',analyst=model,reviewer=model)
        with connect(self.config) as db:
            row = db.execute('SELECT * FROM agent_reviews WHERE session_id=%s',(plan['id'],)).fetchone()
        self.assertFalse(review.show(self.config,self.business,row['id'])['publishable'])
        self.assertIsNone(row['approved_sha256'])

    def test_agent_can_discover_inspect_reports_and_open_evidence_with_replay(self):
        self.fact()
        first = self.start()
        _, report = self.complete(first)
        class Explorer(MemoryAwareModel):
            def generate(self, context, correction=None):
                history = context['business_context']['retrievals']
                tools = [e['request']['tool'] for e in history]
                request = dict(query='',id='',limit=5)
                if not tools:
                    request.update(tool='search_datasets',query='CSV')
                elif 'inspect_dataset' not in tools:
                    request.update(tool='inspect_dataset',id=history[-1]['response']['items'][0]['id'])
                elif 'search_reports' not in tools:
                    request.update(tool='search_reports',id=history[-1]['response']['dataset']['id'])
                elif 'open_report' not in tools:
                    request.update(tool='open_report',id=history[-1]['response']['items'][0]['id'])
                elif 'open_evidence' not in tools:
                    request.update(tool='open_evidence',id=history[-1]['response']['evidence_ids'][0])
                else:
                    return super().generate(context, correction)
                return dict(action='retrieve',table_ids=[],proposal=None,retrieval=request), {}
        model = Explorer()
        plan = self.start('explore',model=model)
        again = self.start('explore',model=model)
        self.assertEqual(plan['id'],again['id'])
        self.assertEqual(len(plan['model_calls']),6)
        with connect(self.config) as db:
            events=db.execute('SELECT * FROM context_retrievals WHERE session_id=%s ORDER BY created_at',(plan['id'],)).fetchall()
        self.assertEqual(len(events),5)
        self.assertEqual(events[-1]['response']['result']['metrics']['total'],'80.0000')
        self.assertTrue(events[-1]['dependencies'])
        review.hold(self.config,self.business,report['id'],reason='Fixture hold')
        self.assertTrue(service.show(self.config,self.business,plan['id'])['context_stale'])

    def test_retrieval_is_scoped_and_large_doubts_pause_instead_of_truncating(self):
        self.fact()
        plan=self.start()
        other=create_business(self.config,'Other')['id']
        path=self.root/'other.csv'; path.write_text('secret\nprivate\n')
        data=import_batch(self.config,other,[path])
        with connect(self.config) as db:
            table=db.execute('SELECT id FROM prepared_tables WHERE business_id=%s',(other,)).fetchone()['id']
            with self.assertRaisesRegex(ValueError,'does not belong'):
                retrieval.retrieve(self.config,db,plan['id'],dict(tool='inspect_dataset',id=str(table),query='',limit=2))
        for n in range(35):
            memory.change(self.config,self.business,action='propose',request_key=f'large{n}',
                          content=content('Material doubt ' + 'x'*1400,topic=f'doubt_{n}',kind='open_question'))
        with self.assertRaisesRegex(ValueError,'48 KB'):
            self.start()
        with connect(self.config) as db:
            self.assertEqual(db.execute('SELECT count(*) n FROM context_manifests WHERE business_id=%s',(self.business,)).fetchone()['n'],1)

    def test_extraction_of_own_answer_does_not_revoke_its_session(self):
        model=ScriptedModel()
        plan=service.start(self.config,self.business,self.analysis,owner_context='Units.',request_key='ask',model=model)
        done=service.answer(self.config,self.business,plan['id'],question_id=plan['questions'][0]['id'],text='Amount is row total.',request_key='answer',model=model)
        with connect(self.config) as db:
            source=db.execute('SELECT * FROM memory_sources WHERE business_id=%s',(self.business,)).fetchone()
        extraction.process(self.config,self.business,source['id'],MemoryModel([candidate('Amount is row total.',kind='definition',topic='amount_basis',scope='source',scope_id=source['payload']['scope_id'])]))
        self.assertFalse(service.show(self.config,self.business,done['id'])['context_stale'])
        second=self.start()
        self.assertFalse(second['questions'])
        fact=memory.read(self.config,self.business)[0]
        memory.change(self.config,self.business,action='withdraw',request_key='withdraw-own-answer',fact_id=fact['fact_id'],expected_revision=fact['revision'])
        self.assertTrue(service.show(self.config,self.business,done['id'])['context_stale'])
        with self.assertRaisesRegex(ValueError,'Withdrawn owner answer'):
            service.resume(self.config,self.business,done['id'],model=model)

    def test_migration_repeated_and_legacy_checkpoint_requires_replan(self):
        self.fact()
        plan=self.start('legacy-key')
        migrate(self.config); migrate(self.config)
        with connect(self.config) as db:
            self.assertEqual(db.execute('SELECT count(*) n FROM schema_versions WHERE version=10').fetchone()['n'],1)
            db.execute('DELETE FROM context_manifests WHERE session_id=%s',(plan['id'],))
        with self.assertRaisesRegex(ValueError,'Legacy checkpoint'):
            self.start('legacy-key')
        with self.assertRaisesRegex(ValueError,'Legacy checkpoint'):
            service.resume(self.config,self.business,plan['id'],model=MemoryAwareModel())
        replanned=service.replan(self.config,self.business,plan['id'],owner_context='Total vendido',request_key='legacy-replan',model=MemoryAwareModel())
        self.assertFalse(replanned['questions'])

    def test_retrieval_replays_after_interruption_without_duplicate_calls(self):
        self.fact()
        class Explorer(MemoryAwareModel):
            def generate(self, context, correction=None):
                if not context['business_context']['retrievals']:
                    return dict(action='retrieve',table_ids=[],proposal=None,
                                retrieval=dict(tool='search_memory',query='',id='',limit=5)), {}
                return super().generate(context, correction)
        model=Explorer()
        from decision_room.agent import persistence
        original=persistence._model_call
        def interrupt_after_tool(*args, **kwargs):
            if args[3]['business_context']['retrievals']:
                raise KeyboardInterrupt
            return original(*args, **kwargs)
        with patch.object(persistence,'_model_call',side_effect=interrupt_after_tool), self.assertRaises(KeyboardInterrupt):
            self.start('interrupted',model=model)
        with connect(self.config) as db:
            sid=db.execute("SELECT id FROM agent_sessions WHERE business_id=%s AND request_key='interrupted'",(self.business,)).fetchone()['id']
        resumed=service.resume(self.config,self.business,sid,model=Explorer())
        self.assertEqual(len(resumed['model_calls']),2)
        with connect(self.config) as db:
            self.assertEqual(db.execute('SELECT count(*) n FROM context_retrievals WHERE session_id=%s',(sid,)).fetchone()['n'],1)

    def test_all_roles_can_retrieve_and_context_preserves_doubts_with_unrelated_query(self):
        self.fact()
        doubt=memory.change(self.config,self.business,action='propose',request_key='question',
            content=content('No sabemos si faltan devoluciones.',topic='returns',kind='open_question'))
        class ResearchExplorer(MemoryAwareModel):
            def generate_research(self, context, correction=None):
                if not context['business_context']['retrievals']:
                    return dict(action='retrieve',table_ids=[],investigation_key='',code='',summary='Leer definiciones.',metric_keys=[],
                                retrieval=dict(tool='search_memory',query='unrelated',id='',limit=1)), {}
                return super().generate_research(context, correction)
        model=ResearchExplorer()
        plan=self.start(model=model)
        work, report=self.complete(plan,model)
        events=report['context_retrievals']
        self.assertEqual(len(events),1)
        ids={r['id'] for r in events[0]['response']['memories']}
        self.assertIn(doubt['fact_id'],ids)
        self.assertEqual(len(events[0]['response']['memories']),2)  # limit never drops a material definition/doubt.

    def test_text_discovery_rephrasing_evaluation_and_period_exclusion(self):
        self.fact()
        with connect(self.config) as db:
            db.execute("UPDATE analyses SET title='Ventas de productos en junio' WHERE id=%s",(self.analysis,))
        plan=self.start(period={'from':'2026-06-01','until':'2026-06-30'})
        with connect(self.config) as db:
            # Spanish stemming finds inflections, not arbitrary semantic equivalents.
            for query in ('venta','productos','ventas junio'):
                result,_=retrieval.retrieve(self.config,db,plan['id'],dict(tool='search_datasets',query=query,id='',limit=5))
                self.assertEqual(len(result['items']),1)
            missed,_=retrieval.retrieve(self.config,db,plan['id'],dict(tool='search_datasets',query='facturación mercancías',id='',limit=5))
            self.assertEqual(missed['items'],[])
            fallback,_=retrieval.retrieve(self.config,db,plan['id'],dict(tool='search_datasets',query='',id='',limit=5))
            self.assertEqual(len(fallback['items']),1)
        _, report=self.complete(plan)
        later=self.start(period={'from':'2026-09-01','until':'2026-09-30'})
        with connect(self.config) as db:
            result,_=retrieval.retrieve(self.config,db,later['id'],dict(tool='search_reports',query='',id='',limit=5))
            self.assertEqual(result['items'],[])
            with self.assertRaisesRegex(ValueError,'outside'):
                retrieval.retrieve(self.config,db,later['id'],dict(tool='open_report',query='',id=str(report['id']),limit=5))

    def test_publication_read_refreshes_after_waiting_for_memory_writer(self):
        fact=self.fact()
        plan=self.start()
        _, report=self.complete(plan)
        original_lock=review.memory_lock
        def racing_lock(db,business_id):
            self.correct(fact)
            return original_lock(db,business_id)
        with patch.object(review,'memory_lock',side_effect=racing_lock):
            state=review.show(self.config,self.business,report['id'])
        self.assertFalse(state['publishable'])
        self.assertEqual(state['model_decision_status'],'stale')

    def test_withdrawn_priority_never_reenters_context_despite_orientation_exemption(self):
        self.fact()
        priority=memory.change(self.config,self.business,action='declare',request_key='priority',content=content(kind='priority'))
        plan=self.start()
        memory.change(self.config,self.business,action='withdraw',request_key='retire-priority',fact_id=priority['fact_id'],expected_revision=1)
        self.assertTrue(service.show(self.config,self.business,plan['id'])['context_stale'])
        with self.assertRaisesRegex(ValueError,'Withdrawn memory'):
            service.resume(self.config,self.business,plan['id'],model=MemoryAwareModel())
        fresh=self.start()
        self.assertNotIn(priority['fact_id'],{r['id'] for r in fresh['context_manifest']['initial_context']['memories']})
