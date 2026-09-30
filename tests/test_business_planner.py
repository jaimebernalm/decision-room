"""3.7 protocol tests use real persistence/sandbox; scripted roles are not quality evidence."""
from copy import deepcopy
from uuid import uuid4
import unittest
from unittest.mock import patch

import test_research as base
from test_parallel_research import TeamModel, ParallelTests
from test_review import DialogueModel
from decision_room.agent import research, review, service
from decision_room.agent.business_planner import validate, successor_context
from decision_room.database import connect


class PlannerModel(TeamModel):
    impact='context'
    def generate_business_planner(self,context,correction=None):
        result,usage=super().generate_business_planner(context,correction)
        if context['stage']=='checkpoint' and not context['owner_replies']:
            result.update(action='ask_owner',question=dict(key='schedule',text='¿Hubo un cambio de horario?',reason='Interpretar la actividad sin atribuir causas.',impact=self.impact,
                options=[],references=[dict(kind='column',id=context['table_catalog'][0]['id'],column='quantity')]))
        return result,usage


class PlannerTests(unittest.TestCase):
    setUpClass=classmethod(base.ResearchTests.setUpClass.__func__)
    tearDownClass=classmethod(base.ResearchTests.tearDownClass.__func__)
    def setUp(self):
        ParallelTests.setUp(self)
        self.model=PlannerModel()
    def start(self,**kwargs):
        return research.start(self.config,self.business,self.plan['id'],request_key='research',model=self.model,
                              business_planner=True,quality_first=True,**kwargs)
    def test_pause_keeps_completed_branches_context_and_no_duplicate_calls(self):
        result=self.start()
        self.assertEqual(result['status'],'waiting')
        self.assertEqual(len(result['findings']),2)
        self.assertEqual(result['options']['max_model_calls'],128)
        self.assertEqual(result['options']['max_rounds'],8)
        self.assertEqual(len(result['pending_questions']),1)
        again=research.resume(self.config,self.business,result['id'],model=self.model)
        self.assertEqual(len(again['model_calls']),len(result['model_calls']))
        executions=[s['execution_id'] for s in result['steps'] if s['execution_id']]
        q=result['pending_questions'][0]
        reply=dict(question_id=q['id'],text='La tienda cerró por obras.',request_key='context-answer',model=self.model)
        done=research.answer(self.config,self.business,result['id'],**reply)
        self.assertEqual(done['status'],'completed')
        self.assertEqual([s['execution_id'] for s in done['steps'] if s['execution_id']],executions)
        same=research.answer(self.config,self.business,result['id'],**reply)
        self.assertEqual(len(same['model_calls']),len(done['model_calls']))
        with self.assertRaisesRegex(ValueError,'differently'):
            research.answer(self.config,self.business,result['id'],**{**reply,'text':'Changed'})
        with connect(self.config) as db:
            snapshots=db.execute('SELECT r.snapshot,r.options FROM agent_research r JOIN agent_research_branches b ON b.child_id=r.id WHERE b.parent_id=%s',(result['id'],)).fetchall()
            self.assertTrue(all(r['snapshot'].get('business_direction') for r in snapshots))
            self.assertTrue(all(not r['options']['business_planner'] for r in snapshots))
            self.assertGreater(db.execute('SELECT paused_seconds FROM agent_research WHERE id=%s',(result['id'],)).fetchone()['paused_seconds'],0)
        roles=DialogueModel();roles.identity=self.model.identity
        delivery=review.start(self.config,self.business,result['id'],request_key='review',analyst=roles,reviewer=roles)
        self.assertTrue(delivery['publishable'])
        self.assertEqual(roles.contexts[-1]['business_direction']['owner_replies'][0]['text'],reply['text'])
        self.assertEqual(delivery['options']['max_review_rounds'],8)
    def test_unknown_does_not_replan_or_repeat_and_cannot_review_waiting(self):
        result=self.start()
        with self.assertRaisesRegex(ValueError,'Wait for research'):
            review.start(self.config,self.business,result['id'],request_key='too-early',analyst=self.model,reviewer=self.model)
        done=research.answer(self.config,self.business,result['id'],question_id=result['pending_questions'][0]['id'],
            disposition='unknown',request_key='unknown',model=self.model)
        self.assertEqual(done['status'],'completed')
        self.assertEqual(len(done['business_answers']),1)
        self.assertFalse(done['pending_questions'])
    def test_explicit_consultation_and_final_synthesis_reach_planner(self):
        class ConsultingModel(TeamModel):
            consulted=False
            business_contexts=[]
            def generate_research(self,context,correction=None):
                if not context['budgets'].get('worker_assignment') and not self.consulted:
                    self.consulted=True
                    return dict(action='consult_business',investigation_key='',code='',table_ids=[],
                                metric_keys=[],summary='¿Qué decisión necesita el propietario sobre disponibilidad?'),{}
                return super().generate_research(context,correction)
            def generate_business_planner(self,context,correction=None):
                self.business_contexts.append(deepcopy(context))
                return super().generate_business_planner(context,correction)
        self.model=ConsultingModel()
        result=self.start()
        self.assertEqual(result['status'],'completed')
        messages=[c['analyst_message'] for c in self.model.business_contexts if c.get('analyst_message')]
        self.assertTrue(any(m['action']=='consult_business' and 'disponibilidad' in m['summary'] for m in messages))
        self.assertEqual(messages[-1]['synthesis'],result['synthesis'])
    def test_remembering_this_answer_keeps_its_session_current_but_withdrawal_stales_it(self):
        from decision_room.memory import context as memory_context,extraction,service as memory
        from test_memory import MemoryModel,candidate
        result=self.start();text='La tienda cerró por obras.'
        done=research.answer(self.config,self.business,result['id'],question_id=result['pending_questions'][0]['id'],
                             text=text,request_key='context-memory',model=self.model)
        other=service.start(self.config,self.business,self.analysis,owner_context='Different analysis.',request_key='other-plan',model=self.model)
        with connect(self.config) as db:
            source=db.execute('SELECT * FROM memory_sources WHERE business_id=%s AND origin_key=%s',
                              (self.business,'planning_answer:'+done['business_answers'][0]['id'])).fetchone()
        p=source['payload']
        extraction.process(self.config,self.business,source['id'],MemoryModel([
            candidate(text,topic='store_closure',scope=p['default_scope'],scope_id=p['scope_id'])]))
        with connect(self.config) as db:
            self.assertIsNone(memory_context.reason(db,self.plan['id']))
            self.assertTrue(memory_context.reason(db,other['id']))
            fact=memory.current(db,self.business)[0]
        memory.change(self.config,self.business,action='withdraw',request_key='withdraw-business-answer',
                      fact_id=str(fact['fact_id']),expected_revision=fact['revision'])
        with connect(self.config) as db:self.assertTrue(memory_context.reason(db,self.plan['id']))
    def test_definition_reply_requires_successor_and_keeps_previous_calculations(self):
        self.model.impact='definition'
        result=self.start()
        done=research.answer(self.config,self.business,result['id'],question_id=result['pending_questions'][0]['id'],
            text='Amount is a row total.',request_key='definition',model=self.model)
        self.assertEqual(done['status'],'replan_required')
        with self.assertRaisesRegex(ValueError,'Wait for research'):
            review.start(self.config,self.business,result['id'],request_key='wrong',analyst=self.model,reviewer=self.model)
        with connect(self.config) as db:
            run=db.execute('SELECT * FROM agent_research WHERE id=%s',(result['id'],)).fetchone()
            context=successor_context(db,run)
        self.assertIn('Amount is a row total.',context)
        successor=service.replan(self.config,self.business,self.plan['id'],owner_context=context,request_key='successor',model=self.model)
        self.assertNotEqual(successor['id'],self.plan['id'])
        self.assertEqual(research.show(self.config,self.business,result['id'])['status'],'stale')
    def test_cross_business_reply_is_rejected(self):
        result=self.start()
        with self.assertRaisesRegex(ValueError,'belong'):
            research.answer(self.config,uuid4(),result['id'],question_id=result['pending_questions'][0]['id'],text='x',request_key='bad',model=self.model)
    def test_shared_memory_boundary_honors_the_saved_context_allowance(self):
        from decision_room.agent.persistence import session_lock, model_call
        context=dict(stage='initial',plan={'investigations':[]},padding='x'*210000,budgets={'max_context_bytes':512000})
        original=self.model.generate_business_planner
        received=[]
        def capture(payload,correction=None):
            received.append(payload['padding'])
            return original(payload,correction)
        self.model.generate_business_planner=capture
        with session_lock(self.config,self.business,self.plan['id']) as (db,session):
            model_call(db,session['id'],self.model,context,None,False,config=self.config,phase='business_planner',scope='context-profile')
            self.assertEqual(received,[context['padding']])
            context['budgets']={}
            with self.assertRaisesRegex(ValueError,'200 KB'):
                model_call(db,session['id'],self.model,context,None,False,config=self.config,phase='business_planner',scope='legacy-context')
    def test_exhaustion_without_business_readiness_is_partial(self):
        def still_missing(context,correction=None):
            raw,usage=base.ResearchModel.generate_business_planner(self.model,context,correction)
            raw['action']='guide'
            return raw,usage
        self.model.generate_business_planner=still_missing
        result=self.start(max_model_calls=12)
        self.assertEqual(result['status'],'partial')
        self.assertEqual(len(result['findings']),2)
        self.assertFalse(result['publishable'])
    def test_quality_workers_can_recover_after_three_failed_programs(self):
        class RecoveringTeam(TeamModel):
            def generate_research(self,context,correction=None):
                assignment=context['budgets'].get('worker_assignment')
                if assignment:
                    used=context['budgets']['attempts_used'].get(assignment['investigation_key'],0)
                    return base.ResearchModel(always_fail=used<3).generate_research(context,correction)
                return super().generate_research(context,correction)
        self.model=RecoveringTeam()
        done=self.start()
        self.assertEqual(done['status'],'completed')
        self.assertEqual(len(done['findings']),2)
        executions=[s['execution'] for s in done['steps'] if s['action']['action']=='execute']
        self.assertEqual(len(executions),8)
        self.assertEqual(sum(e['status']=='completed' for e in executions),2)
        again=research.resume(self.config,self.business,done['id'],model=self.model)
        self.assertEqual(len(again['model_calls']),len(done['model_calls']))
    def test_review_repairs_invalid_actions_without_relaxing_approval(self):
        from test_review import action,assessed,draft
        self.model=TeamModel()
        work=self.start()
        class RepairingReview(base.ResearchModel):
            def __init__(self,invalid):super().__init__();self.invalid=invalid;self.corrections=[]
            def generate_analyst_review(self,context,correction=None):return action('submit',report=draft(context)),{}
            def generate_reviewer(self,context,correction=None):
                self.corrections.append(correction)
                value=assessed(action('approve'),context)
                if len(self.corrections)<=self.invalid:value['action']='revise'
                return value,{}
        for invalid in (3,4):
            model=RepairingReview(invalid);model.identity=self.model.identity
            if invalid==4:
                with self.assertRaisesRegex(ValueError,'validation 4 times'):
                    review.start(self.config,self.business,work['id'],request_key='invalid',analyst=model,reviewer=model)
            else:
                result=review.start(self.config,self.business,work['id'],request_key='repaired',analyst=model,reviewer=model)
                self.assertTrue(result['publishable'])
                self.assertEqual(sum(e['role']=='reviewer' for e in result['conversation']),1)
            self.assertEqual(len(model.corrections),4)
            self.assertEqual(len(set(model.corrections)),4)
    def test_waiting_time_is_excluded_and_fresh_model_can_resume(self):
        result=self.start()
        with connect(self.config) as db:
            db.execute("UPDATE agent_research SET created_at=created_at-interval '2 days' WHERE id=%s",(result['id'],))
            db.execute("UPDATE business_planner_events SET created_at=created_at-interval '2 days' WHERE id=%s",(result['pending_questions'][0]['id'],))
        done=research.answer(self.config,self.business,result['id'],question_id=result['pending_questions'][0]['id'],
            text='Hubo obras.',request_key='later',model=PlannerModel())
        self.assertEqual(done['status'],'completed')
        self.assertGreater(done['paused_seconds'],172800)
    def test_failed_planner_delivery_replays_saved_branches(self):
        original=self.model.generate_business_planner
        crashed=False
        def fail_once(context,correction=None):
            nonlocal crashed
            if context['stage']=='checkpoint' and not crashed:
                crashed=True;raise ValueError('temporary planner failure')
            return original(context,correction)
        self.model.generate_business_planner=fail_once
        with self.assertRaisesRegex(ValueError,'temporary planner failure'):self.start()
        with connect(self.config) as db:
            run=db.execute("SELECT * FROM agent_research WHERE session_id=%s AND request_key='research'",(self.plan['id'],)).fetchone()
            count=db.execute('SELECT count(*) n FROM executions WHERE business_id=%s',(self.business,)).fetchone()['n']
        resumed=research.resume(self.config,self.business,run['id'],model=self.model)
        self.assertEqual(resumed['status'],'waiting')
        with connect(self.config) as db:self.assertEqual(db.execute('SELECT count(*) n FROM executions WHERE business_id=%s',(self.business,)).fetchone()['n'],count)


class PlannerContractTests(unittest.TestCase):
    def test_question_scope_and_evidence_are_checked(self):
        context=dict(stage='checkpoint',plan={'investigations':[{'key':'sales'}]},findings=[],owner_replies=[],prior_checkpoints=[],answers=[],table_catalog=[dict(id='t',column_names=['quantity'])])
        raw,_=PlannerModel().generate_business_planner(context)
        self.assertEqual(validate(raw,context)['question']['impact'],'context')
        wrong=deepcopy(raw);wrong['question']['references'][0]['id']='other'
        with self.assertRaisesRegex(ValueError,'available'):validate(wrong,context)
        wrong=deepcopy(raw);wrong['evidence_keys']=['invented']
        with self.assertRaisesRegex(ValueError,'saved candidate'):validate(wrong,context)
        context['prior_checkpoints']=[{'direction':raw}]
        with self.assertRaisesRegex(ValueError,'repeat'):validate(raw,context)
    def test_workers_cannot_consult(self):
        from decision_room.agent.research_contract import validate_research_action
        action=dict(action='consult_business',investigation_key='',table_ids=[],code='',summary='Need context',metric_keys=[])
        with self.assertRaisesRegex(ValueError,'principal'):
            validate_research_action(action,{'proposal':{'investigations':[]}},[],[],{'business_planner':True,'worker_assignment':{'key':'x'}})

    def test_ready_requires_delivery_guidance(self):
        context=dict(stage='delivery',plan={'investigations':[]},findings=[],owner_replies=[],prior_checkpoints=[],answers=[],table_catalog=[])
        raw,_=PlannerModel().generate_business_planner(context)
        raw['instructions']=[]
        with self.assertRaisesRegex(ValueError,'business handoff'):validate(raw,context)

import test_web

class BusinessWebModel(test_web.WebModel):
    impact='context'
    def generate_business_planner(self,context,correction=None):
        result,usage=super().generate_business_planner(context,correction)
        if context['stage']=='checkpoint' and not context['owner_replies'] and 'Aclaraciones posteriores' not in context['owner_context']:
            result.update(action='ask_owner',question=dict(key='opening',text='¿Cambió el horario de apertura?',
                reason='Interpretar la actividad observada.',impact=self.impact,options=[],
                references=[dict(kind='column',id=context['table_catalog'][0]['id'],column='quantity')]))
        return result,usage

class PlannerWebTests(unittest.TestCase):
    setUpClass=classmethod(test_web.WebTests.setUpClass.__func__)
    tearDownClass=classmethod(test_web.WebTests.tearDownClass.__func__)
    setUp=test_web.WebTests.setUp
    create=test_web.WebTests.create
    answer=test_web.WebTests.answer
    def test_question_delivery_response_and_resume_through_web_boundary(self):
        self.ws.model_factory=BusinessWebModel
        job=self.create();self.ws.run_job(job)
        self.answer(job);self.ws.run_job(job)
        detail=self.ws.detail(job)
        self.assertEqual(detail['status'],'waiting')
        self.assertEqual(detail['questions'][0]['phase'],'research')
        self.assertEqual(detail['questions'][0]['references'][0]['column'],'quantity')
        research_id=self.ws.row(job)['research_id']
        self.answer(job,text='Cerramos dos días por obras.');self.ws.run_job(job)
        self.assertEqual(self.ws.row(job)['research_id'],research_id)
        detail=self.ws.detail(job)
        self.assertEqual(detail['questions'][0]['phase'],'review')
        self.assertTrue(any(a['text']=='Cerramos dos días por obras.' for a in detail['answers']))
        self.answer(job,text='Amount is row total.');self.ws.run_job(job)
        self.assertTrue(self.ws.detail(job)['publishable'])
    def test_definition_answer_replans_the_same_web_job(self):
        class DefinitionModel(BusinessWebModel):impact='definition'
        self.ws.model_factory=DefinitionModel
        job=self.create();self.ws.run_job(job);self.answer(job);self.ws.run_job(job)
        old=self.ws.row(job)
        self.answer(job,text='Amount is row total.');self.ws.run_job(job)
        new=self.ws.row(job)
        self.assertNotEqual(new['session_id'],old['session_id'])
        self.assertEqual(new['status'],'queued')
        self.assertIsNone(new['research_id'])
        self.ws.run_job(job)
        self.assertNotEqual(self.ws.row(job)['research_id'],old['research_id'])
        self.assertEqual(research.show(self.config,self.business['id'],old['research_id'])['status'],'stale')


import test_conversations as chat_tests


class PlannerConversationTests(unittest.TestCase):
    setUpClass=classmethod(chat_tests.ConversationTests.setUpClass.__func__)
    tearDownClass=classmethod(chat_tests.ConversationTests.tearDownClass.__func__)
    setUp=chat_tests.ConversationTests.setUp
    chat=chat_tests.ConversationTests.chat
    batch=chat_tests.ConversationTests.batch
    send=chat_tests.ConversationTests.send

    def test_research_question_and_unknown_reply_stay_in_original_conversation(self):
        from decision_room.conversations import Conversations
        class ConversationalPlanner(BusinessWebModel,chat_tests.ChatModel):pass
        self.ws.model_factory=ConversationalPlanner
        self.chats=Conversations(self.ws.scoped(self.b))
        chat=self.chat(self.batch())
        turn=self.send(chat,'Calculate sales')
        job=turn['job_id']
        for phase,text,disposition in [('planning','unit price','answered'),('research','No lo sé.','unknown'),('review','Amount is row total.','answered')]:
            self.ws.run_job(job);self.chats.run(turn['id'])
            current=self.chats.detail(chat)['turns'][-1]
            self.assertEqual(current['status'],'waiting')
            question=current['questions'][0]
            self.assertEqual(question['phase'],phase)
            turn=self.send(chat,text,question_id=question['id'],disposition=disposition)
            self.assertEqual(turn['job_id'],job)
        self.ws.run_job(job);self.chats.run(turn['id'])
        final=self.chats.detail(chat)['turns'][-1]
        self.assertEqual(final['status'],'completed')
        self.assertEqual(final['response']['kind'],'evidence')
        self.assertTrue(any(a['disposition']=='unknown' for a in self.ws.detail(job)['answers']))


if __name__=='__main__':unittest.main()
