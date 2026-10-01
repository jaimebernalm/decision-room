"""Chat uses the direct editor's scope, intent review and atomic publication."""
import unittest
from unittest.mock import patch
from uuid import uuid4

import test_web
from test_presentation_editing import RevisionTests
from decision_room.conversations import Conversations
from decision_room.web import presentation_editing as editing, home
from decision_room.database import connect


class ChatEditingTests(unittest.TestCase):
    setUpClass = classmethod(test_web.WebTests.setUpClass.__func__)
    tearDownClass = classmethod(test_web.WebTests.tearDownClass.__func__)
    setUp = test_web.WebTests.setUp
    create, answer, complete = test_web.WebTests.create, test_web.WebTests.answer, test_web.WebTests.complete
    fixture = RevisionTests.fixture

    def setup_chat(self, *, changes=None, race=False, deny=False, restore=None):
        job, report, body = self.fixture()
        owner = self
        class EditorModel(test_web.WebModel):
            def generate_chat(self, context, correction=None):
                if context['validation_feedback']:
                    return dict(action='answer', retrieval=None, analysis_id='', text='Puedo explicar las opciones de edición.', sources=[], include_report=False), {}
                target = context['presentation_targets'][0]
                return dict(action='edit_presentation',retrieval=None,analysis_id='',text='',sources=[],include_report=False,
                            presentation_edit=dict(report_id=target['report_id'],base_version=target['base_version'],revision=target['revision'],
                            changes=changes or [],restore_revision=restore)), {}
            def review_chat_answer(self, context):
                if context.get('presentation_change'):
                    owner.assertIn('Cambios solicitados',context['draft'])
                    if race:
                        editing.save(owner.ws, report['report_id'], {**body,'changes':[dict(kind='report',key='title',field='title',value='Edición simultánea del propietario')]})
                    if deny:
                        return dict(approved=False,issues=['The current message asks a question, not to save.']), {}
                return dict(approved=True,issues=[]), {}
        self.ws.model_factory=EditorModel
        chats=Conversations(self.ws.scoped(self.business['id']))
        chat=chats.create(dict(business_id=str(self.business['id']),request_key=str(uuid4())))['id']
        return job,report,chats,chat

    def send(self,chats,chat,text='Aplica el cambio de presentación.'):
        body=dict(business_id=str(self.business['id']),request_key=str(uuid4()),text=text)
        result=chats.send(chat,body)
        chats.run(result['id'])
        return chats.detail(chat)['turns'][-1],body

    def test_chat_saves_shared_names_and_titles_once_then_restores(self):
        labels=[dict(id='catalog:P01',code='P01',name='Café original',table_id='catalog',key_column='producto_id',name_column='nombre',source_sha256='fixture')]
        changes=[dict(kind='entity',key='catalog:P01',field='name',value='Café Bruma'),dict(kind='report',key='title',field='title',value='Ventas de Bruma')]
        with patch.object(editing,'catalog_labels',return_value=labels):
            job,report,chats,chat=self.setup_chat(changes=changes)
            turn,body=self.send(chats,chat)
            self.assertEqual(turn['status'],'completed',turn.get('issue'))
            receipt=turn['response']['presentation_receipt']
            self.assertEqual(receipt['revision'],1)
            self.assertEqual(receipt['previous_revision'],0)
            self.assertEqual(editing.view(self.ws,report['report_id'])['presentation']['labels'][0]['name'],'Café Bruma')
            self.assertEqual(home.view(self.ws)['sources'][0]['title'],'Ventas de Bruma')
            self.assertEqual(self.ws.report(job,structured=True)['report_version'],report['report_version'])
            self.assertEqual(chats.send(chat,body)['id'],turn['id'])
            chats.run(turn['id'])
            self.assertEqual(editing.view(self.ws,report['report_id'])['presentation']['revision'],1)
            restored=editing.save(self.ws,report['report_id'],dict(business_id=str(self.business['id']),base_version=receipt['base_version'],revision=1,request_key=str(uuid4()),restore_revision=0))
            self.assertEqual(restored['report']['title'],report['title'])
            self.assertEqual(restored['report']['presentation']['labels'][0]['name'],'Café original')

    def test_question_is_not_authorization(self):
        job,report,chats,chat=self.setup_chat(changes=[dict(kind='report',key='title',field='title',value='No autorizado')],deny=True)
        turn,_=self.send(chats,chat,'¿Se puede cambiar el título?')
        self.assertEqual(turn['status'],'completed',turn.get('issue'))
        self.assertNotIn('presentation_receipt',turn['response'])
        self.assertEqual(editing.view(self.ws,report['report_id'])['presentation']['revision'],0)

    def test_owner_edit_during_review_wins(self):
        job,report,chats,chat=self.setup_chat(changes=[dict(kind='report',key='title',field='title',value='Cambio del chat')],race=True)
        turn,_=self.send(chats,chat)
        self.assertIn('No he cambiado',turn['response']['text'])
        self.assertNotIn('presentation_receipt',turn['response'])
        self.assertEqual(self.ws.report(job,structured=True)['title'],'Edición simultánea del propietario')

    def test_incompatible_unit_is_rejected_without_receipt(self):
        # A saved metric has a stable server-owned key; unit edits cannot change dimensions.
        job,report,chats,chat=self.setup_chat(changes=[dict(kind='report',key='title',field='unit',value='kg')])
        turn,_=self.send(chats,chat)
        self.assertIn('No he cambiado',turn['response']['text'])
        self.assertEqual(editing.view(self.ws,report['report_id'])['presentation']['revision'],0)

    def test_edit_rolls_back_if_receipt_cannot_be_published(self):
        job,report,chats,chat=self.setup_chat(changes=[dict(kind='report',key='title',field='title',value='Rollback')])
        save=chats._save
        def interrupted(db,turn,status,response=None,issue=None):
            if response and response['kind']=='presentation_edit':
                raise RuntimeError('Controlled publication interruption')
            return save(db,turn,status,response,issue)
        with patch.object(chats,'_save',side_effect=interrupted):
            turn,_=self.send(chats,chat)
        self.assertEqual(turn['status'],'failed')
        self.assertEqual(editing.view(self.ws,report['report_id'])['presentation']['revision'],0)
        with connect(self.config) as db:
            self.assertIsNone(db.execute('SELECT 1 FROM report_presentation_revisions WHERE report_id=%s',(report['report_id'],)).fetchone())
