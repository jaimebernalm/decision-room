"""The launcher's engine arm against the real engine (OpenCode, Docker, PostgreSQL, MCP) with a
mocked Responses provider: no billed calls. Needs the pinned engine image."""
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from uuid import uuid4

import httpx
from psycopg import sql
from psycopg.conninfo import make_conninfo

from decision_room.config import Config
from decision_room.database import connect, migrate
from decision_room.engine import api
from decision_room.evaluation import trial_accuracy, trial_worker
from decision_room.reports.verification_contract import validate


def provider(calls, actions):
    """Responses stream: first ask the owner, then deliver a small report, then say 'Guardado.'"""
    def respond(request):
        assert request.url.host == 'api.openai.com'
        body = json.loads(request.content)
        if request.url.path.endswith('input_tokens'):
            return httpx.Response(200, json={'input_tokens': 10})
        calls.append(body)
        action = 'preguntar_propietario' if not actions else 'entregar_informe'
        tools = [t for t in body.get('tools', []) if t['name'].endswith(action)]
        events = []
        event = lambda kind, **fields: events.append({'type': kind, **fields})
        n = str(len(calls))
        response = {'id': 'resp_arm_' + n, 'object': 'response', 'created_at': 1, 'model': 'gpt-6-luna',
                    'service_tier': 'default', 'status': 'in_progress', 'output': []}
        event('response.created', response=response.copy())
        if tools and action not in actions:
            arguments = ({'request_key': 'arm-question', 'text': '¿Qué unidad?', 'reason': 'No consta', 'options': []}
                         if action == 'preguntar_propietario' else
                         {'request_key': 'arm-final', 'draft_json': json.dumps({
                             'schema_version': 1, 'title': 'Informe', 'summary': 'Total 5 unidades.', 'findings': []})})
            actions.append(action)
            args = json.dumps(arguments)
            item = {'type': 'function_call', 'id': 'fc_arm_' + n, 'call_id': 'call_arm_' + n,
                    'name': tools[0]['name'], 'arguments': ''}
            event('response.output_item.added', output_index=0, item=item.copy())
            event('response.function_call_arguments.delta', item_id=item['id'], output_index=0, delta=args)
            item.update(arguments=args, status='completed')
            event('response.function_call_arguments.done', item_id=item['id'], output_index=0, arguments=args)
        else:
            item = {'type': 'message', 'id': 'msg_arm_' + n, 'role': 'assistant', 'content': [], 'status': 'in_progress'}
            event('response.output_item.added', output_index=0, item=item.copy())
            part = {'type': 'output_text', 'text': '', 'annotations': []}
            event('response.content_part.added', item_id=item['id'], output_index=0, content_index=0, part=part.copy())
            event('response.output_text.delta', item_id=item['id'], output_index=0, content_index=0, delta='Guardado.')
            part['text'] = 'Guardado.'
            item.update(content=[part], status='completed')
            event('response.output_text.done', item_id=item['id'], output_index=0, content_index=0, text='Guardado.')
            event('response.content_part.done', item_id=item['id'], output_index=0, content_index=0, part=part)
        event('response.output_item.done', output_index=0, item=item)
        response.update(status='completed', output=[item], usage={
            'input_tokens': 10, 'output_tokens': 5, 'input_tokens_details': {'cached_tokens': 2, 'cache_write_tokens': 3}})
        event('response.completed', response=response)
        return httpx.Response(200, headers={'content-type': 'text/event-stream'},
                              content=b''.join(('data: ' + json.dumps(e) + '\n\n').encode() for e in events))
    return respond


@unittest.skipUnless(os.environ.get('DECISION_ROOM_ENGINE_IMAGE_ID'), 'Build the pinned engine image.')
class EngineArmLiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = Config.load()
        cls.database = 'dr_engine_arm_' + uuid4().hex
        with connect(cls.base) as db:
            db.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(cls.database)))
        cls.dsn = make_conninfo(cls.base.dsn, dbname=cls.database)
        migrate(replace(cls.base, dsn=cls.dsn))

    @classmethod
    def tearDownClass(cls):
        with connect(cls.base) as db:
            db.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(cls.database)))

    def test_engine_arm_answers_the_owner_question_and_keeps_a_contract_export(self):
        folder = tempfile.TemporaryDirectory(prefix='dr-engine-arm-')
        self.addCleanup(folder.cleanup)
        root = Path(folder.name)
        config = replace(self.base, dsn=self.dsn, storage=root / 'storage')
        batch = root / 'batch'
        data = batch / 'inputs/demo/datos'
        data.mkdir(parents=True)
        (data / 'units.csv').write_text('quantity\n2\n3\n')
        prompt = 'Mi negocio es Prueba. ¿Cuántas unidades vendo?'
        (batch / 'inputs/demo/prompt.txt').write_text(prompt)
        dataset = {'inputs': {'units.csv': hashlib.sha256((data / 'units.csv').read_bytes()).hexdigest()},
                   'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest(), 'business': 'Prueba'}
        job = batch / 'jobs/demo-engine-1'
        job.mkdir(parents=True)
        state = {'job': job.name, 'dataset': 'demo', 'system': 'engine', 'key': 'trial-' + uuid4().hex}
        calls, actions = [], []
        server = api.Server(config, api_key='offline-fixture', backend=api.DockerBackend(),
                            transport=httpx.MockTransport(provider(calls, actions)))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        with patch.object(api, '_service', return_value=server):
            trial_worker.engine_new(config, state, job, lambda name: state.update(phase=name), batch, dataset)
        meta = json.loads((api.folder(config, state['business_id'], state['engine_run_id']) / 'control.json').read_text())
        self.addCleanup(api.Runtime(api.DockerBackend(), **{k: meta[k] for k in
                        ('run_id', 'instance_id', 'image', 'password', 'token', 'model')}).remove)

        self.assertEqual((state['status'], state['engine_status'], state['engine_questions']), ('completed', 'delivered', 1))
        self.assertEqual(actions, ['preguntar_propietario', 'entregar_informe'])
        self.assertEqual(state['engine_usage']['cost_catalog']['status'], 'estimated')
        export = job / 'engine'
        for name in ('draft.raw', 'draft.verified.json', 'verification.json', 'informe.html',
                     'informe.contenido.html', 'run.json', 'session-export.json', 'proxy-calls.jsonl'):
            self.assertTrue((export / name).exists(), name)
        document = json.loads((export / 'draft.verified.json').read_text())
        ledger = json.loads((export / 'verification.json').read_text())
        validate(ledger, document, (export / 'draft.raw').read_bytes())
        self.assertIn('5', (job / 'informe.html').read_text())
        register = {job.name: {'registro_cifras': [
            {'cita': 'Total 5 unidades', 'valor_informe': '5', 'clase': 'correcta', 'sostiene_prioridad_v3': True}]}}
        (root / 'registro.json').write_text(json.dumps(register))
        result = trial_accuracy.arm(trial_accuracy.load(root / 'registro.json', batch))
        # A1's minimal verifier labels every figure unverified: the join must not count it as verified.
        self.assertEqual(result['totals']['priority_verified_correct'], 0)
        self.assertFalse(result['passed'])


if __name__ == '__main__':
    unittest.main()
