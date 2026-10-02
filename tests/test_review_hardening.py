"""Adversarial contract tests plus durable HTTP recovery against PostgreSQL/Docker."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

import httpx

from decision_room.agent import review
from decision_room.agent.model import ModelClient, ModelSettings, ModelAPIError
from decision_room.agent.review_contract import validate
from decision_room.agent.review_policy import ledger, delivery_manifest
from decision_room.database import connect
from decision_room.report import export
import test_review as review_tests
from test_review import DialogueModel, action, assessed


class HardeningTests(unittest.TestCase):
    setUpClass = classmethod(review_tests.ReviewTests.setUpClass.__func__)
    tearDownClass = classmethod(review_tests.ReviewTests.tearDownClass.__func__)
    setUp = review_tests.ReviewTests.setUp
    run_review = review_tests.ReviewTests.run_review

    def test_saved_selection_notes_replace_stale_counts_and_survive_resume(self):
        class SelectedDialogue(DialogueModel):
            def generate_analyst_review(self, context, correction=None):
                response, usage = super().generate_analyst_review(context, correction)
                if response['action'] == 'submit':
                    report=response['report']; ref=report['claims'][0]['evidence'][0]
                    report['charts']=[dict(key='values',claim_key='sales',kind='table',title='Protocol values',
                        unit='importe',decimals=2,caption='Scripted comparison for persistence verification.',
                        points=[dict(label=label,value=ref) for label in ('A','B')])]
                    report['delivery_selections']=[dict(key='selection',title='Valores de prueba',
                        chart_keys=['values'],axis='points',shown_group_count=2,population=None,coverage='selected')]
                    report['limitations'].append('Selección entregada: stale 18 elements.')
                return response,usage
        self.roles=SelectedDialogue('correct')
        result=review.start(self.config,self.business,self.research['id'],request_key='selected',
                            analyst=self.roles,reviewer=self.roles)
        self.assertTrue(result['publishable'])
        notes=[n for n in result['report']['limitations'] if n.startswith('Selección entregada:')]
        self.assertEqual(notes,['Selección entregada: Valores de prueba: 2 elementos mostrados.'])
        resumed=review.resume(self.config,self.business,result['id'],analyst=self.roles,reviewer=self.roles)
        self.assertEqual(result['approved_sha256'],resumed['approved_sha256'])
        self.assertEqual(result['report'],resumed['report'])

    def test_usefulness_failure_missing_questions_and_false_coverage_block_approval(self):
        self.run_review()
        ctx=self.roles.contexts[-1]
        self.assertEqual(ctx['review_policy'],5)
        good=assessed(action('approve'),ctx)
        for mutation in ('missing','goal','question','coverage'):
            bad=deepcopy(good)
            audit=bad['assessment']['usefulness']
            if mutation=='missing': bad['assessment']['usefulness']=None
            if mutation=='goal': audit['goal_alignment']='fail'
            if mutation=='question': audit['questions'][0]['verdict']='fail'
            if mutation=='coverage': audit['questions']=[]
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                validate(bad,'reviewer',ctx)
        legacy={**ctx,'review_policy':1}
        good['assessment']['usefulness']=None
        validate(good,'reviewer',legacy)

    def test_owner_coverage_and_conditional_reaction_audit_are_independent(self):
        self.run_review()
        ctx = deepcopy(self.roles.contexts[-1])
        ref = ctx['report']['claims'][0]['evidence'][0]
        ctx['report']['claims'][0]['orientation'] = dict(segment='Extracto', period='Periodo disponible',
            signal='Actividad calculada', evidence=[ref], relative_priority='Responde a la pregunta factual.',
            knowledge='calculated', next_check='Confirmar registros del extracto si se requiere el total del negocio.',
            decision_value='Determinar si hace falta completar fuentes.',
            reactions=[dict(condition='Se acredita una omisión.', reaction='Completar registros y recalcular.')],
            limitation='No constan fuentes adicionales.')
        good = assessed(action('approve'), ctx)
        validate(good, 'reviewer', ctx)
        # A reviewer identifies an invented causal reaction; structure alone cannot approve it.
        bad = deepcopy(good)
        bad['assessment']['usefulness']['decision_support'] = 'fail'
        with self.assertRaisesRegex(ValueError, 'unsupported reactions'): validate(bad, 'reviewer', ctx)
        bad = deepcopy(good); bad['assessment']['usefulness']['owner_deliverables'] = []
        with self.assertRaisesRegex(ValueError, 'each owner deliverable'): validate(bad, 'reviewer', ctx)
        # A computable owner component omitted is a semantic failure, even with valid internal branches.
        bad = deepcopy(good); bad['assessment']['usefulness']['owner_deliverables'][0]['verdict'] = 'fail'
        with self.assertRaisesRegex(ValueError, 'failed owner deliverables'): validate(bad, 'reviewer', ctx)
        ctx['report']['owner_coverage'][0]['status'] = 'partial'
        ctx['report']['owner_coverage'][0]['explanation'] = 'Faltan fuentes para el negocio completo.'
        validate(assessed(action('approve'), ctx), 'reviewer', ctx)
        # A limited answer cannot receive complete approval by changing only the audit label.
        bad = assessed(action('approve'), ctx); bad['assessment']['usefulness']['owner_deliverables'][0]['verdict'] = 'pass'
        with self.assertRaisesRegex(ValueError, 'partial/unavailable'): validate(bad, 'reviewer', ctx)

    def test_unresolved_parallel_disagreement_cannot_be_published_as_answered(self):
        self.run_review()
        ctx = deepcopy(self.roles.contexts[-1])
        key = ctx['report']['question_coverage'][0]['investigation_key']
        ctx['research_synthesis'] = {'disagreements': [dict(investigation_keys=[key, 'other'],
            explanation='Las ramas aplicaron alcances incompatibles.', resolution='unresolved')]}
        with self.assertRaisesRegex(ValueError, 'Unresolved research disagreements'):
            validate(assessed(action('approve'), ctx), 'reviewer', ctx)

    def test_priority_order_uses_declared_links_and_preserves_claim_evidence(self):
        from decision_room.agent.review_policy import prioritize_claims
        report = {'claims': [dict(key='context', evidence=['a']), dict(key='secondary', evidence=['b']), dict(key='focus', evidence=['c'])],
                  'question_coverage': [dict(investigation_key='deep',claim_keys=['focus']),dict(investigation_key='overview',claim_keys=['secondary'])]}
        before = deepcopy(report['claims'])
        prioritize_claims(report, {'priorities': [dict(investigation_key='deep'),dict(investigation_key='overview')]})
        self.assertEqual([c['key'] for c in report['claims']], ['focus','secondary','context'])
        self.assertEqual({c['key']:c['evidence'] for c in report['claims']}, {c['key']:c['evidence'] for c in before})

    def test_issues_cannot_disappear_and_suggestions_do_not_block(self):
        result = self.run_review()
        context = self.roles.contexts[-1]
        self.assertTrue(result['publishable'])
        self.assertEqual(result['review_issues'][0]['status'], 'resolved')
        approved = assessed(action('approve'), context)
        missing = deepcopy(approved)
        missing['assessment']['issues'] = []
        with self.assertRaisesRegex(ValueError, 'Retain every'):
            validate(missing, 'reviewer', context)
        open_issue = deepcopy(approved)
        open_issue['assessment']['issues'][0]['status'] = 'open'
        with self.assertRaisesRegex(ValueError, 'open material'):
            validate(open_issue, 'reviewer', context)
        optional = deepcopy(approved)
        optional['assessment']['issues'].append(dict(key='wording',severity='suggestion',status='open',
            target='summary',detail='Optional shorter wording.',resolution='',introduced_because='Editorial observation.',
            basis='optional_improvement',owner_quote='',owner_deliverable_index=None,claim_keys=[],chart_keys=[]))
        validate(optional, 'reviewer', context)
        optional['action'] = 'revise'
        with self.assertRaisesRegex(ValueError, 'optional suggestions'):
            validate(optional, 'reviewer', context)
        optional['assessment']['issues'][-1]['introduced_because'] = ''
        with self.assertRaisesRegex(ValueError, 'later new issue'):
            validate(optional, 'reviewer', context)
        self.assertEqual(ledger(context['conversation'])[0]['key'], 'definition')

    def test_delivery_audit_is_bound_to_exact_draft_and_cannot_fail_on_approval(self):
        result = self.run_review()
        context = self.roles.contexts[-1]
        for field in ('numbers', 'meaning', 'charts', 'coverage', 'files'):
            bad = assessed(action('approve'), context)
            bad['assessment']['delivery'][field] = 'fail'
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'failed delivery audit'):
                validate(bad, 'reviewer', context)
        bad = assessed(action('approve'), context)
        bad['assessment']['report_step'] -= 1
        with self.assertRaisesRegex(ValueError, 'exact current'):
            validate(bad, 'reviewer', context)
        with self.assertRaisesRegex(ValueError, 'requires assessment'):
            validate(action('approve'), 'reviewer', context)
        manifest = result['delivery_manifest']
        self.assertEqual(manifest['downloadable_execution_files'], [])
        self.assertEqual(manifest['claim_keys'], ['sales'])
        self.assertEqual(manifest['question_coverage'][0]['status'], 'answered')
        # Export uses the approved source, with the evidence-resolved total.
        from pathlib import Path
        page = Path(export(self.config, self.business, result['id'])['path']).read_text()
        self.assertIn('80', page)
        self.assertEqual(result['observations'][0]['result']['metrics']['total'], '80.0000')

    def test_existing_successful_calculation_reused_but_independent_check_allowed(self):
        self.run_review()
        context = self.roles.contexts[-1]
        observed = context['observations'][0]
        duplicate = action('execute', code=observed['code'], table_ids=[t['id'] for t in observed['inputs'].values()])
        with self.assertRaisesRegex(ValueError, 'already exists'):
            validate(duplicate, 'analyst', context)
        validate(duplicate, 'reviewer', context)
        stale = deepcopy(context)
        stale['observations'][0]['current'] = False
        validate(duplicate, 'analyst', stale)

    def test_rejected_http_call_recovery_preserves_draft_and_budget(self):
        class HttpReviewer(DialogueModel):
            fail = True
            requests = 0
            def generate_reviewer(inner, context, correction=None):
                response = assessed(action('approve'), context)
                def handler(request):
                    inner.requests += 1
                    if inner.fail:
                        return httpx.Response(429)
                    return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(response)}}],
                                                    'usage':{'prompt_tokens':1,'completion_tokens':1}})
                client = httpx.Client(transport=httpx.MockTransport(handler))
                with patch('decision_room.agent.model.httpx.Client',return_value=client), patch('decision_room.agent.model.time.sleep'):
                    return ModelClient(ModelSettings('test',protocol='chat_completions')).generate_reviewer(context,correction)
        roles = HttpReviewer('plain')
        with self.assertRaisesRegex(ValueError, '429'):
            review.start(self.config,self.business,self.research['id'],request_key='429-recovery',analyst=roles,reviewer=roles)
        with connect(self.config) as db:
            run = db.execute('SELECT * FROM agent_reviews WHERE business_id=%s',(self.business,)).fetchone()
        before = review.show(self.config,self.business,run['id'])
        self.assertFalse(before['publishable'])
        self.assertEqual([e['action']['action'] for e in before['conversation']],['submit'])
        failed = next(c for c in before['model_calls'] if c['status']=='failed')
        self.assertEqual([a['status'] for a in failed['usage']['transport_attempts']],[429,429,429])
        roles.fail=False
        after = review.resume(self.config,self.business,run['id'],analyst=roles,reviewer=roles)
        self.assertTrue(after['publishable'])
        self.assertEqual(len(after['model_calls']),3)  # draft, failed review, resumed review
        self.assertEqual(len(after['observations']),len(before['observations']))
        self.assertEqual(after['report'],before['report'])
        self.assertEqual(roles.requests,4)
        repeated = review.resume(self.config,self.business,run['id'],analyst=roles,reviewer=roles)
        self.assertEqual(len(repeated['model_calls']),3)
        self.assertEqual(roles.requests,4)

    def test_delivery_manifest_reports_resolved_series_point_count(self):
        observations=[dict(execution_id='e',current=True,status='completed',inputs={'sales':{}},result={
            'series':{'annual':dict(grain='category',unit='units',points=[{'label':'2014','value':'2'},{'label':'2015','value':'3'}],
                                    evidence=dict(tables=['sales'],operation='Group by year.'))}})]
        report=dict(claims=[{'key':'sales'}],charts=[dict(key='years',kind='bar',unit='units',points=[],series={'execution_id':'e','series':'annual'})])
        self.assertEqual(delivery_manifest(report,observations)['charts'][0]['points'],2)

    def test_exhausted_call_budget_stops_resume_without_another_request(self):
        class FailingReviewer(DialogueModel):
            def generate_reviewer(inner, context, correction=None):
                raise ModelAPIError(429)
        roles = FailingReviewer('plain')
        with self.assertRaisesRegex(ValueError,'429'):
            review.start(self.config,self.business,self.research['id'],request_key='budget',analyst=roles,reviewer=roles)
        with connect(self.config) as db:
            run=db.execute("UPDATE agent_reviews SET options=jsonb_set(options,'{max_calls_per_role}','1') WHERE business_id=%s RETURNING id",(self.business,)).fetchone()
        result=review.resume(self.config,self.business,run['id'],analyst=roles,reviewer=roles)
        self.assertEqual(result['status'],'limited')
        self.assertFalse(result['publishable'])
        self.assertEqual(len(result['model_calls']),2)
        self.assertIsNotNone(result['report'])

    def test_interruption_during_backoff_preserves_attempt_before_sleep(self):
        class InterruptedReviewer(DialogueModel):
            def generate_reviewer(inner, context, correction=None):
                client=httpx.Client(transport=httpx.MockTransport(lambda request:httpx.Response(429,
                    headers={'Retry-After':'2','x-ratelimit-limit-tokens':'200000',
                             'x-ratelimit-remaining-tokens':'0','x-ratelimit-reset-tokens':'20s'},
                    json={'error':{'code':'rate_limit_exceeded','type':'tokens','message':'private provider message'}})))
                with patch('decision_room.agent.model.httpx.Client',return_value=client), patch('decision_room.agent.model.time.sleep',side_effect=SystemExit(17)):
                    return ModelClient(ModelSettings('test',protocol='chat_completions')).generate_reviewer(context,correction)
        roles=InterruptedReviewer('plain')
        with self.assertRaises(SystemExit):
            review.start(self.config,self.business,self.research['id'],request_key='backoff-crash',analyst=roles,reviewer=roles)
        with connect(self.config) as db:
            run=db.execute('SELECT id FROM agent_reviews WHERE business_id=%s',(self.business,)).fetchone()
            call=db.execute("SELECT * FROM agent_calls WHERE scope=%s AND status='running'",(str(run['id']),)).fetchone()
        self.assertEqual(call['usage']['transport_attempts'],[{'status':429,'usage_unknown':True,
            'retry_delay_seconds':20,'retry_after_seconds':2,'error_code':'rate_limit_exceeded',
            'error_type':'tokens','error_category':'rate_limit',
            'rate_limits':{'limit_tokens':200000,'remaining_tokens':0,'reset_tokens_seconds':20}}])
        self.assertNotIn('private provider',str(call['usage']))
        with self.assertRaisesRegex(ValueError,'retry-model'):
            review.resume(self.config,self.business,run['id'],analyst=roles,reviewer=roles)
        result=review.resume(self.config,self.business,run['id'],analyst=DialogueModel('plain'),reviewer=DialogueModel('plain'),retry_uncertain=True)
        self.assertTrue(result['publishable'])
        self.assertEqual(len(result['observations']),1)
        self.assertEqual(len(result['model_calls']),3)
        self.assertEqual([c['status'] for c in result['model_calls']],['completed','interrupted','completed'])
