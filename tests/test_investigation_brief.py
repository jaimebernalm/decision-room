"""The chat-written investigation brief: validated, frozen once, guidance only, never checker input."""
import unittest

from decision_room import chat_agent
from decision_room.conversations import Action, Conversations
from decision_room.database import connect
from decision_room.engine import brief, job_profile
from decision_room.web import engine_jobs
from tests import test_report_history

BRIEF = dict(objective='Saber si la recogida en local sigue cayendo.', reason='Lo comentamos tras el último informe.',
             background=[dict(text='El dueño cree que los clientes pasaron al envío a domicilio.', sources=['memory/m1'])])


def decision(action='investigate', **values):
    return chat_agent.Decision.model_validate({**dict(action=action, retrieval=None, sources=[], text='',
                                                      analysis_id='a' if action == 'investigate' else ''), **values})


class ContractTests(unittest.TestCase):
    def test_only_an_investigation_carries_a_bounded_brief(self):
        chat_agent.validate_decision(decision(investigation_brief=BRIEF))
        chat_agent.validate_decision(decision(investigation_brief=None))
        with self.assertRaises(ValueError):
            chat_agent.validate_decision(decision('answer', text='Hola', investigation_brief=BRIEF))
        edit = dict(report_id='r', base_version='v', revision=0, changes=[], restore_revision=1)
        with self.assertRaises(ValueError):
            chat_agent.validate_decision(decision('edit_presentation', analysis_id='', include_report=False,
                                                  presentation_edit=edit, investigation_brief=BRIEF))
        # Every field within its own limit, yet over 4096 bytes once serialised.
        long = dict(objective='ñ' * 600, reason='ñ' * 600, background=[dict(text='ñ' * 300, sources=[]) for _ in range(6)])
        with self.assertRaises(ValueError):
            chat_agent.validate_decision(decision(investigation_brief=long))
        action = Action.model_validate(dict(report_id='', claim_keys=[], question='', message_ids=[],
                                            **decision(investigation_brief=BRIEF).model_dump()))
        self.assertEqual(action.investigation_brief.objective, BRIEF['objective'])

    def test_sources_must_be_delivered_and_memory_declared(self):
        context = {'available_sources': {
            'memory/m1': dict(content=dict(status='declared')),
            'memory/m2': dict(content=dict(status='proposed')),
            'tool/0': dict(content=dict(origin='engine_blocks', id='doc-1')),
            'dataset/t': dict(content=dict(id='t')),
            'selection/0': dict(content=dict(kind='memory', memory_status='proposed', content=dict(statement='Quizá'))),
            'tool/1': dict(content=dict(memories=[dict(status='declared'), dict(status='conflicted')])),
            'tool/2': dict(content=dict(memories=[dict(status='declared')])),
            'selection/1': dict(content=dict(kind='engine_block', authority='engine_report', source_id='doc-9',
                                             status='available'))}}
        parse = lambda **b: chat_agent.InvestigationBrief.model_validate({**BRIEF, **b})
        frozen = Conversations._investigation_brief(context, parse(background=[
            dict(text='x', sources=['memory/m1', 'tool/0', 'dataset/t']), dict(text='y', sources=['tool/2', 'selection/1'])]))
        # Opened reports and selected native blocks are pinned as explicit prior reports.
        self.assertEqual(frozen['reports'], ['doc-1', 'doc-9'])
        for bad in (['memory/m2'], ['memory/unknown'], ['tool/9'], ['selection/0'], ['tool/1']):
            with self.assertRaises(ValueError):
                Conversations._investigation_brief(context, parse(background=[dict(text='x', sources=bad)]))
        self.assertIsNone(Conversations._investigation_brief(context, None))

    def test_frozen_with_its_own_hash(self):
        settings = job_profile.freeze({'model': 'm'}, context='c', goal='g', input_hash='h', investigation_brief=BRIEF)
        self.assertEqual(settings['investigation_brief'], BRIEF)
        self.assertEqual(len(settings['investigation_brief_sha256']), 64)
        self.assertNotIn('investigation_brief', job_profile.freeze({'model': 'm'}, context='c', goal='g', input_hash='h'))


class BriefTextTests(unittest.TestCase):
    def test_literal_goal_stays_and_the_chat_summary_is_labelled_guidance(self):
        kwargs = dict(name='Tienda', description='Una tienda.', goal='¿Sigue cayendo la recogida?', model=None,
                      memory=[], panorama=False, format='blocks')
        text = brief.compose(**kwargs, chat_brief=BRIEF)
        self.assertIn('¿Sigue cayendo la recogida?', text)
        self.assertIn(brief.CHAT_BRIEF, text)
        self.assertIn('- Objetivo: ' + BRIEF['objective'], text)
        self.assertLess(text.index('¿Sigue cayendo'), text.index(brief.CHAT_BRIEF))
        self.assertNotIn(brief.CHAT_BRIEF, brief.compose(**kwargs))


class ChatJobTests(test_report_history.HistoryTests):
    test_summary_keeps_label_cover_priorities_and_proposed_actions = None
    test_stale_report_is_labelled_and_deleted_or_blocked_reports_are_excluded = None
    test_explicit_reference_comes_first_and_at_most_three_are_kept = None
    test_next_brief_freezes_prior_summaries_files_and_checker_context = None
    test_replayed_key_reuses_frozen_inputs_and_a_changed_request_still_fails = None
    test_checker_receives_frozen_prior_texts_and_the_same_summary = None
    test_other_business_reports_never_appear = None
    test_replaced_data_keeps_the_same_logical_dataset_first_and_labels_it_stale = None

    def test_chat_brief_reaches_the_writer_not_the_checker_and_pins_its_reports(self):
        old = self.deliver()
        newer = [self.deliver() for _ in range(3)]
        chat_brief = {**BRIEF, 'reports': [str(old['report_document_id'])]}
        job = dict(business_id=self.business['id'], analysis_id=newer[-1]['analysis_id'], origin='chat',
                   engine_config={'goal': '¿Sigue cayendo la recogida?', 'investigation_brief': chat_brief,
                                  'profile': {'format': 'blocks'}})
        builder, _ = engine_jobs.inputs(self.config, job)
        self.assertEqual(builder.request['investigation_brief'], chat_brief)
        with connect(self.config) as db, db.transaction():
            prompt, provenance, files = builder(db)
        self.assertIn(brief.CHAT_BRIEF, prompt)
        self.assertNotIn(brief.CHAT_BRIEF, provenance['checker_context'])
        self.assertTrue(provenance['chat_brief'])
        self.assertEqual(provenance['prior_reports'][0]['document_id'], str(old['report_document_id']))
        self.assertEqual(provenance['prior_reports'][0]['group'], 0)
        self.assertEqual(len(provenance['prior_reports']), 3)


if __name__ == '__main__':
    unittest.main()
