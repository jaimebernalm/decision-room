"""Selected chat originals: real DB isolation, snapshots, bounded long-history access."""
import unittest
from unittest.mock import patch
from uuid import uuid4
from psycopg.types.json import Jsonb

from decision_room import conversation_context as selected
from decision_room.context_references import normalize
from decision_room.database import connect
from decision_room.memory import retrieval
from decision_room.web.errors import WebError
import test_conversations as chats_tests
from test_conversations import ChatModel, action


class SelectedConversationTests(unittest.TestCase):
    setUpClass = classmethod(chats_tests.ConversationTests.setUpClass.__func__)
    tearDownClass = classmethod(chats_tests.ConversationTests.tearDownClass.__func__)
    setUp = chats_tests.ConversationTests.setUp
    chat = chats_tests.ConversationTests.chat
    send = chats_tests.ConversationTests.send

    def seed(self, chat, texts):
        with connect(self.config) as db:
            start = db.execute('SELECT COALESCE(MAX(ordinal),0) AS n FROM chat_turns WHERE conversation_id=%s', (chat,)).fetchone()['n']
            with db.cursor() as cursor:
                cursor.executemany('''INSERT INTO chat_turns(id,business_id,conversation_id,ordinal,request_key,payload,status,model_settings,response)
                    VALUES(%s,%s,%s,%s,%s,%s,'completed','{}',%s)''', [
                    (uuid4(), self.b, chat, start+i, uuid4(), Jsonb(dict(text=text)),
                     Jsonb(dict(kind='grounded_answer',text='Respuesta anterior: '+text))) for i,text in enumerate(texts,1)])

    def ref(self, chat):
        item = next(c for c in self.chats.listing()['conversations'] if c['id'] == chat)['context_reference']
        return normalize([{k:item[k] for k in ('source_id','source_version','kind','element_key')}])[0]

    def read(self, ref, query='', limit=10, business=None):
        with connect(self.config) as db:
            return retrieval.retrieve(self.config, db, None, dict(tool='open_chat',query=query,id=ref['source_id'],limit=limit),
                manifest=dict(business_id=business or self.b,context_references=[ref]))[0]

    def test_small_chat_reads_both_sides_and_appended_messages_are_excluded(self):
        chat=self.chat(); self.seed(chat,['Plan original','Decisión final'])
        ref=self.ref(chat)
        result=self.read(ref)
        self.assertFalse(result['more']); self.assertFalse(result['partial'])
        self.assertEqual([r['role'] for r in result['items']],['user','assistant','user','assistant'])
        self.seed(chat,['Mensaje posterior'])
        self.assertEqual(self.read(ref),result)
        self.assertNotEqual(self.ref(chat),ref)
        with self.assertRaises(WebError): normalize([ref,self.ref(chat)])

    def test_long_chat_can_find_middle_and_paginate_long_messages_without_recursion(self):
        chat=self.chat(); self.seed(chat,[f'Mensaje sintético {i}' for i in range(600)])
        self.seed(chat,['inicio '+('文'*5000)+' detalle central '+('文'*5000)+' final'])
        ref=self.ref(chat)
        result=self.read(ref,'sintético 312')
        self.assertTrue(result['partial']); self.assertIn('312',result['items'][0]['text'])
        result=self.read(ref,'detalle central')
        self.assertTrue(any('detalle central' in r['text'] for r in result['items']))
        result=self.read(ref, 'page:1200:', limit=10)
        seen=[]
        while True:
            self.assertLess(len(__import__('json').dumps(result,ensure_ascii=False).encode()),12000)
            seen+=result['items']
            if not result['more']: break
            result=self.read(ref,result['next_query'])
        self.assertTrue(any(r['role']=='assistant' and r['text'].endswith(' final') for r in seen))
        self.assertTrue(any('detalle central' in r['text'] for r in seen))

    def test_tampering_other_business_deletion_and_changed_history_are_rejected(self):
        chat=self.chat(); self.seed(chat,['Original']); ref=self.ref(chat)
        for bad in (ref|{'source_version':'1:fake'},ref|{'element_key':'other'},ref|{'source_id':str(uuid4())}):
            with self.assertRaises(ValueError): self.read(bad)
        with self.assertRaises(ValueError): self.read(ref,business=uuid4())
        with connect(self.config) as db:
            with self.assertRaises(ValueError):
                selected.read(db,dict(business_id=self.b,context_references=[]),retrieval.Request(tool='open_chat',query='',id=str(chat),limit=2))
            db.execute("UPDATE chat_turns SET response=%s WHERE conversation_id=%s",(Jsonb(dict(kind='answer',text='Changed')),chat))
        with self.assertRaises(ValueError): self.read(ref)
        ref=self.ref(chat)
        self.chats.delete(chat,dict(business_id=str(self.b)))
        with self.assertRaises(ValueError): self.read(ref)

    def test_pipeline_requires_original_read_and_preserves_attachment_in_full_chat(self):
        chat=self.chat(); self.seed(chat,['Consideramos abrir los sábados.'])
        ref=self.ref(chat); seen=[]
        def respond(model, context, correction=None):
            seen.append(context)
            if not context['retrievals']:
                if not context['validation_feedback']:
                    return action('answer',text='Respuesta basada solo en la vista previa.',sources=['selection/0']),{}
                return action('retrieve',retrieval=dict(tool='open_chat',query='',id=str(chat),limit=5)),{}
            return action('answer',text='En la conversación se planteó abrir los sábados; no confirma el horario actual.',sources=['tool/1']),{}
        with patch.object(ChatModel,'generate_chat',respond):
            target=self.chat()
            turn=self.send(target,'¿Qué hablamos en el chat adjunto?',context_references=[ref])
        self.assertEqual(turn['status'],'completed',turn)
        self.assertEqual(turn['attachments'][0]['kind'],'conversation')
        self.assertEqual(turn['attachments'][0]['href'],'#chat/'+str(chat))
        self.assertEqual(seen[-1]['retrievals'][0]['request']['tool'],'open_chat')
        self.assertTrue(seen[-1]['validation_feedback'])
        def followup(model, context, correction=None):
            if not context['retrievals']:
                self.assertEqual(context['chat_context']['conversation_references'],[ref])
                return action('retrieve',retrieval=dict(tool='open_chat',query='sábados',id=str(chat),limit=5)),{}
            return action('answer',text='Se planteó como posibilidad, no como horario confirmado.',sources=['tool/0']),{}
        with patch.object(ChatModel,'generate_chat',followup):
            follow=self.send(target,'¿Y eso era una propuesta o una confirmación?')
        self.assertEqual(follow['status'],'completed',follow)
        self.chats.delete(chat,dict(business_id=str(self.b)))
        detail=self.chats.detail(target)['turns'][0]
        self.assertEqual(detail['attachments'][0]['status'],'withdrawn')
        with self.assertRaises(WebError): self.send(self.chat(),'Reutiliza esto',context_references=[ref])
