"""Reports start only from the owner's explicit acceptance of an offer, never from model output."""
import unittest
from unittest.mock import patch
from uuid import uuid4

from decision_room import chat_agent
from decision_room.agent.model import ModelClient, ModelSettings
from decision_room.conversations import Conversations, LEGACY_OFFER
from decision_room.database import connect
from decision_room.memory import service as memory
from decision_room.web.errors import WebError
import test_conversations
from test_memory import content

BRIEF = dict(objective='Ventas por mes y por qué cambian.', reason='Lo pidió el propietario.', background=[])


class OfferTests(unittest.TestCase):
    # The conversation fixtures only; their scenarios already run in test_conversations.
    setUpClass = classmethod(test_conversations.ConversationTests.setUpClass.__func__)
    tearDownClass = classmethod(test_conversations.ConversationTests.tearDownClass.__func__)
    setUp, chat, send, accept, batch = (test_conversations.ConversationTests.setUp, test_conversations.ConversationTests.chat, test_conversations.ConversationTests.send,
                                        test_conversations.ConversationTests.accept, test_conversations.ConversationTests.batch)

    def offered(self):
        chat = self.chat(self.batch())
        turn = self.send(chat, 'Calculate sales', accept=False)
        return chat, turn, turn['response']['report_offer']

    def jobs(self):
        with connect(self.config) as db:
            return db.execute('SELECT * FROM web_jobs WHERE business_id=%s', (self.b,)).fetchall()

    def payload(self, offer, key=None, objective=None):
        return dict(business_id=str(self.b), request_key=key or str(uuid4()), offer_id=offer['id'],
                    objective=objective or offer['objective'])

    def test_an_offer_creates_no_job_until_the_owner_confirms_it(self):
        chat, turn, offer = self.offered()
        self.assertEqual(turn['status'], 'completed')
        self.assertIsNone(turn['job_id'])
        self.assertEqual(turn['response']['text'], LEGACY_OFFER)  # A stored investigate decision only offers.
        self.assertEqual((offer['status'], offer['job_id']), ('open', None))
        self.assertEqual(self.jobs(), [])
        accepted = self.accept(chat, offer, objective='Ventas por mes, sin extrapolar.')
        self.assertEqual(accepted['payload']['text'], 'Preparar informe: Ventas por mes, sin extrapolar.')
        self.assertEqual(accepted['payload']['report_acceptance']['offer_id'], offer['id'])
        self.assertTrue(accepted['job_id'])
        [job] = self.jobs()
        self.assertEqual(str(job['id']), str(accepted['job_id']))
        self.assertEqual(job['goal'], 'Ventas por mes, sin extrapolar.')
        self.assertEqual(job['origin'], 'chat')
        shown = self.chats.detail(chat)['turns'][0]['response']['report_offer']
        self.assertEqual((shown['status'], shown['job_id']), ('accepted', str(accepted['job_id'])))

    def test_acceptance_is_idempotent_and_single_use(self):
        chat, _, offer = self.offered()
        key = str(uuid4())
        first = self.chats.accept_offer(chat, self.payload(offer, key))
        self.assertEqual(self.chats.accept_offer(chat, self.payload(offer, key)), first)  # A double click.
        with self.assertRaises(WebError) as changed:
            self.chats.accept_offer(chat, self.payload(offer, key, objective='Otra cosa.'))
        self.assertEqual(changed.exception.status, 409)
        with self.assertRaises(WebError) as again:
            self.chats.accept_offer(chat, self.payload(offer))
        self.assertEqual(again.exception.status, 409)
        self.assertEqual(len(self.jobs()), 1)

    def test_foreign_stale_or_superseded_offers_are_refused_without_side_effects(self):
        chat, turn, offer = self.offered()
        other = self.chat()
        with self.assertRaises(WebError) as foreign:
            self.chats.accept_offer(other, self.payload(offer))
        self.assertEqual(foreign.exception.status, 404)
        business = self.ws.save_business(dict(request_key=str(uuid4()), expected_active_id=str(self.b),
                                              name='Other shop', description='Other context'))
        with self.assertRaises(WebError):
            Conversations(self.ws.scoped(business['id'])).accept_offer(
                chat, {**self.payload(offer), 'business_id': str(business['id'])})
        self.ws.select_business(dict(business_id=str(self.b)))
        memory.change(self.config, self.b, action='declare', request_key=str(uuid4()),
                      content=content('Amount is the row total.'))
        with self.assertRaises(WebError) as stale:
            self.chats.accept_offer(chat, self.payload(offer))
        self.assertEqual(stale.exception.status, 409)
        self.assertEqual(self.jobs(), [])
        self.assertEqual(len(self.chats.detail(chat)['turns']), 1)
        with connect(self.config) as db:
            self.assertEqual(db.execute('SELECT status FROM chat_report_offers WHERE id=%s', (offer['id'],)).fetchone()['status'], 'open')
            db.execute('UPDATE chat_turns SET attempt=attempt+1 WHERE id=%s', (turn['id'],))
        with self.assertRaises(WebError) as superseded:
            self.chats.accept_offer(chat, self.payload(offer))
        self.assertEqual(superseded.exception.status, 409)

    def test_a_job_needs_an_offer_accepted_by_the_same_turn(self):
        chat, turn, offer = self.offered()
        with connect(self.config) as db, db.transaction():
            row = db.execute('SELECT * FROM chat_report_offers WHERE id=%s', (offer['id'],)).fetchone()
            conversation = db.execute('SELECT * FROM chat_conversations WHERE id=%s', (chat,)).fetchone()
            origin = db.execute('SELECT * FROM chat_turns WHERE id=%s', (turn['id'],)).fetchone()
            with self.assertRaises(ValueError):
                self.chats._job(db, conversation, origin, row, origin)
            with self.assertRaises(ValueError):
                self.chats._job(db, conversation, origin, {**row, 'status': 'accepted', 'accepted_turn_id': uuid4(),
                                                           'accepted_objective': 'x'}, origin)
        self.assertEqual(self.jobs(), [])

    def test_a_model_offer_passes_review_and_freezes_its_brief(self):
        analysis = self.batch()
        reviewed = []

        class Model(test_conversations.ChatModel):
            def generate_chat(model, context, correction=None):
                return dict(action='offer_report', retrieval=None, analysis_id=str(analysis), sources=[],
                            text='Es un cálculo grande: un informe tarda unos cinco minutos y comprueba sus cifras.',
                            investigation_brief=BRIEF, calculation=None, include_report=False, onboarding=None,
                            presentation_edit=None), {}

            def review_chat_answer(model, context):
                reviewed.append(context)
                return dict(approved=True, issues=[]), {}

        self.ws.model_factory = Model
        self.chats = Conversations(self.ws.scoped(self.b))
        chat = self.chat(analysis)
        turn = self.send(chat, '¿Por qué cambian las ventas cada mes?', accept=False)
        self.assertEqual(turn['status'], 'completed', turn)
        self.assertIn('report_offer', turn['response'], turn)
        offer = turn['response']['report_offer']
        self.assertEqual(offer['objective'], BRIEF['objective'])
        self.assertEqual(reviewed[0]['report_offer']['brief']['objective'], BRIEF['objective'])
        self.assertIsNone(turn['job_id'])
        with connect(self.config) as db:
            row = db.execute('SELECT * FROM chat_report_offers WHERE id=%s', (offer['id'],)).fetchone()
        self.assertEqual(row['brief']['objective'], BRIEF['objective'])
        from decision_room.engine import job_profile
        with patch.object(job_profile, 'selection', lambda config, data: ('opencode', {'model': 'm'})):
            accepted = self.accept(chat, offer, objective='Ventas por mes, explicadas.')
        [job] = self.jobs()
        self.assertEqual(str(job['id']), str(accepted['job_id']))
        self.assertEqual(job['goal'], 'Ventas por mes, explicadas.')  # The owner-confirmed objective.
        self.assertEqual(job['engine_config']['goal'], 'Ventas por mes, explicadas.')
        self.assertEqual(job['engine_config']['investigation_brief']['objective'], BRIEF['objective'])  # Guidance only.


class ContractTests(unittest.TestCase):
    def decision(self, **values):
        return chat_agent.Decision.model_validate({**dict(action='offer_report', retrieval=None, analysis_id='a',
                                                           text='Te propongo un informe.', sources=[],
                                                           investigation_brief=BRIEF), **values})

    def test_an_offer_needs_an_analysis_a_brief_and_text(self):
        chat_agent.validate_decision(self.decision())
        for bad in (dict(analysis_id=''), dict(investigation_brief=None), dict(text=' ')):
            with self.assertRaises(ValueError):
                chat_agent.validate_decision(self.decision(**bad))
        with self.assertRaises(ValueError):
            chat_agent.validate_decision(self.decision(action='answer', analysis_id=''))

    def test_the_model_can_no_longer_choose_investigate(self):
        captured = []
        client = ModelClient(ModelSettings(model='schema-test-only'))
        with patch.object(ModelClient, '_generate', lambda self, context, correction, system, schema: captured.append(schema)):
            client.generate_chat({'message': {}})
        enum = captured[0]['properties']['action']['enum']
        self.assertNotIn('investigate', enum)
        self.assertIn('offer_report', enum)
        self.assertIn('calculate', enum)


if __name__ == '__main__':
    unittest.main()
