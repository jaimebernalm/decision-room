"""Activity ordering and failure isolation use real PostgreSQL."""
import threading
import unittest
from dataclasses import replace
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch
from psycopg import sql
from psycopg.conninfo import make_conninfo
from decision_room.config import Config
from decision_room.database import connect,migrate
from decision_room.service import create_business
from decision_room.observability import store
from decision_room.observability.privacy import diagnostic,text


class ActivityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base=Config.load();cls.database='dr_activity_test_'+uuid4().hex
        with connect(cls.base) as db: db.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(cls.database)))
        cls.config=replace(cls.base,dsn=make_conninfo(cls.base.dsn,dbname=cls.database))
        migrate(cls.config)
    @classmethod
    def tearDownClass(cls):
        with connect(cls.base) as db: db.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(cls.database)))
    def setUp(self):
        self.business=create_business(self.config,'Activity test')['id']
        with connect(self.config) as db: self.trace=store.root(db,self.business,'job',uuid4())
    def event(self,db,key,**kw):
        return store.append(db,self.business,self.trace,kind='test',source_id=key,status='running',public_text='Comprobando datos',dedupe_key=kw.pop('dedupe_key',key),**kw)
    def test_idempotency_rollback_and_migration(self):
        migrate(self.config)
        with connect(self.config) as db:
            self.event(db,'one');self.event(db,'one')
            try:
                with db.transaction():
                    self.event(db,'rolled-back')
                    raise RuntimeError()
            except RuntimeError: pass
            self.assertEqual(db.execute('SELECT last_sequence FROM activity_traces WHERE id=%s',(self.trace,)).fetchone()['last_sequence'],1)
            self.assertEqual(db.execute('SELECT count(*) n FROM activity_events WHERE trace_id=%s',(self.trace,)).fetchone()['n'],1)
    def test_migration_from_schema_24_preserves_existing_records(self):
        name='dr_activity_legacy_'+uuid4().hex
        with connect(self.base) as db: db.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
        config=replace(self.config,dsn=make_conninfo(self.base.dsn,dbname=name))
        try:
            schema=Path('decision_room/schema.sql').read_text().split('-- 3.8:')[0]
            with connect(config) as db: db.execute(schema)
            existing=create_business(config,'Legacy business')['id']
            migrate(config);migrate(config)
            with connect(config) as db:
                self.assertEqual(db.execute('SELECT max(version) n FROM schema_versions').fetchone()['n'],25)
                self.assertEqual(db.execute('SELECT name FROM businesses WHERE id=%s',(existing,)).fetchone()['name'],'Legacy business')
                self.assertEqual(db.execute('SELECT count(*) n FROM activity_traces').fetchone()['n'],0)
        finally:
            with connect(self.base) as db: db.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
    def test_concurrent_commit_order_has_no_cursor_gap(self):
        entered=threading.Event();release=threading.Event();done=threading.Event();errors=[]
        def first():
            try:
                with connect(self.config) as db,db.transaction():
                    self.event(db,'first');entered.set();release.wait(5)
            except BaseException as e: errors.append(e)
        def second():
            try:
                with connect(self.config) as db: self.event(db,'second')
                done.set()
            except BaseException as e: errors.append(e)
        a=threading.Thread(target=first);a.start();self.assertTrue(entered.wait(5))
        b=threading.Thread(target=second);b.start()
        self.assertFalse(done.wait(.1))
        with connect(self.config) as db:
            self.assertEqual(db.execute('SELECT last_sequence FROM activity_traces WHERE id=%s',(self.trace,)).fetchone()['last_sequence'],0)
        release.set();a.join(5);b.join(5);self.assertEqual(errors,[])
        with connect(self.config) as db:
            rows=db.execute('SELECT sequence,dedupe_key FROM activity_events WHERE trace_id=%s ORDER BY sequence',(self.trace,)).fetchall()
            self.assertEqual([(r['sequence'],r['dedupe_key']) for r in rows],[(1,'first'),(2,'second')])
    def test_failed_observer_savepoint_keeps_domain_transaction(self):
        with connect(self.config) as db,db.transaction():
            def broken(db,*args): db.execute('SELECT * FROM activity_table_does_not_exist')
            self.assertIsNone(store.safe(db,self.business,self.trace,broken))
            db.execute("UPDATE businesses SET description='domain survived' WHERE id=%s",(self.business,))
        with connect(self.config) as db:
            self.assertFalse(db.execute('SELECT history_complete FROM activity_traces WHERE id=%s',(self.trace,)).fetchone()['history_complete'])
            self.assertEqual(db.execute('SELECT description FROM businesses WHERE id=%s',(self.business,)).fetchone()['description'],'domain survived')
    def test_cross_business_links_and_parent_cycles_rejected(self):
        other=create_business(self.config,'Other')['id']
        with connect(self.config) as db:
            with self.assertRaises(ValueError): store.link(db,other,self.trace,'job',uuid4())
            a=self.event(db,'a');b=self.event(db,'b',parent_id=a)
            with self.assertRaisesRegex(ValueError,'cycle'): self.event(db,'a',parent_id=b,dedupe_key='cycle')
    def test_diagnostics_remove_secrets_and_private_reasoning(self):
        with patch.dict('os.environ',{'OPENAI_API_KEY':'canary-private-credential'}):
            result=diagnostic({'reasoning':'hidden','headers':{'x':'hidden'},'output':'canary-private-credential /Users/person/private/file https://host/?token=secret'})
            self.assertNotIn('reasoning',result);self.assertNotIn('headers',result)
            self.assertNotIn('canary',str(result));self.assertNotIn('/Users/',str(result));self.assertNotIn('https://',str(result))

    def test_thousand_events_from_three_producers_are_contiguous(self):
        barrier=threading.Barrier(3);errors=[]
        def producer(number,count):
            try:
                barrier.wait(timeout=5)
                for i in range(count):
                    with connect(self.config) as db: self.event(db,f'producer-{number}-{i}')
            except BaseException as error: errors.append(error)
        threads=[threading.Thread(target=producer,args=(i,334 if i==0 else 333)) for i in range(3)]
        for thread in threads: thread.start()
        for thread in threads: thread.join(30)
        self.assertFalse(any(t.is_alive() for t in threads));self.assertEqual(errors,[])
        with connect(self.config) as db:
            sequences=[r['sequence'] for r in db.execute('SELECT sequence FROM activity_events WHERE trace_id=%s ORDER BY sequence',(self.trace,)).fetchall()]
            self.assertEqual(sequences,list(range(1,1001)))
