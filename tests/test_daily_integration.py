"""Cross-feature regressions found while closing delivery 2.5."""
import unittest
from uuid import uuid4

from psycopg.types.json import Jsonb
import test_conversations as fixture
from test_memory import content, candidate, MemoryModel
from decision_room.database import connect
from decision_room.memory import service as memory, extraction


class DailyIntegrationTests(unittest.TestCase):
    setUpClass = classmethod(fixture.ConversationTests.setUpClass.__func__)
    tearDownClass = classmethod(fixture.ConversationTests.tearDownClass.__func__)
    setUp = fixture.ConversationTests.setUp
    batch = fixture.ConversationTests.batch
    chat = fixture.ConversationTests.chat
    send = fixture.ConversationTests.send
    complete = fixture.ConversationTests.complete

    def test_source_conflict_can_be_seen_and_resolved_in_its_chat(self):
        analysis = self.batch()
        with connect(self.config) as db:
            source = str(db.execute('SELECT id FROM sources WHERE analysis_id=%s', (analysis,)).fetchone()['id'])
        original = content('amount es precio unitario.', topic='amount_basis', kind='definition', scope='source', scope_id=source)
        fact = memory.change(self.config, self.b, action='declare', request_key=str(uuid4()), content=original)
        text = 'amount es el total de fila.'
        with connect(self.config) as db:
            captured = memory.capture(db, self.b, str(uuid4()), text=text, kind='manual', default_scope='source', scope_id=source)
        extraction.process(self.config, self.b, captured['id'], MemoryModel([candidate(text, topic='amount_basis', kind='definition', scope='source', scope_id=source, conflicts=[fact['fact_id']])]))
        chat = self.chat(analysis)
        items = self.chats.detail(chat)['memory_items']
        conflict = next((f for f in items if f['id'] == fact['fact_id']), None)
        self.assertIsNotNone(conflict, 'The agent sees the source conflict but the chat hides its resolution controls.')
        self.assertEqual(conflict['status'], 'conflicted')
        chosen = next(i for i,a in enumerate(conflict['alternatives']) if a['content']['statement'] == text)
        self.chats.resolve(chat,dict(business_id=str(self.b),request_key=str(uuid4()),fact_id=fact['fact_id'],revision=conflict['revision'],alternative=chosen))
        self.assertEqual(self.chats.detail(chat)['memory_items'][0]['content']['statement'], text)
        self.assertFalse(self.chats.detail(self.chat())['memory_items'])

    def test_running_chat_is_not_hidden_by_more_recent_published_reports(self):
        active = self.chat()
        self.chats.send(active,dict(business_id=str(self.b),request_key=str(uuid4()),text='Pending work'))
        _, done = self.complete()
        # A busy workday with many completed/published chats must not hide queued work.
        with connect(self.config) as db:
            row = db.execute('SELECT * FROM chat_turns WHERE id=%s',(done['id'],)).fetchone()
            for _ in range(14):
                chat = self.chat()
                db.execute('''INSERT INTO chat_turns(id,business_id,conversation_id,ordinal,request_key,payload,status,model_settings,response,snapshot,report_requested)
                    VALUES (%s,%s,%s,1,%s,%s,'completed',%s,%s,%s,true)''',
                    (uuid4(),self.b,chat,uuid4(),Jsonb(row['payload']),Jsonb(row['model_settings']),Jsonb(row['response']),Jsonb(row['snapshot'])))
        activity = self.ws.dashboard()['activity']
        self.assertTrue(any(x['href']=='#chat/'+str(active) and x['status']=='queued' for x in activity),activity)
