"""Step 3.3 live round evaluation; source references never enter model context.

Run: python -m decision_room.evaluation.research_rounds --output .local/evaluation/rounds-33
Requires the public WWI exports, configured model, PostgreSQL and Docker.
Preserves every attempt in an isolated database and local directory.
"""
import argparse
from dataclasses import asdict, replace
import hashlib
import json
import os
from pathlib import Path
import time
from uuid import uuid4

from psycopg import sql
from psycopg.conninfo import make_conninfo

from ..agent import service, research, review
from ..agent.model import ModelClient, ModelSettings
from ..config import Config, ROOT
from ..database import connect, migrate
from ..local_env import load_env
from ..service import create_business, import_batch
from ..report import export
from .runner import write, collect, source_version
from .substantial_data import TABLES, OWNER, reference
from .substantial import owner_reply
from .assess import token_accounting

GOAL = '''Compara 2014 y 2015 para descubrir qué productos explican los cambios de
ventas sin impuestos y margen bruto. Empieza por comprobar la evolución general
y profundiza en los resultados que merezcan atención. Cuantifica contribuciones,
comprueba la comparabilidad y distingue explicación aritmética de causa comercial.
No fuerces sorpresas. Ventas sin impuestos = ExtendedPrice - TaxAmount; porcentaje
de margen bruto = SUM(LineProfit) / SUM(ExtendedPrice - TaxAmount) * 100.
'''


def run(output, repeats):
    output.mkdir(parents=True, exist_ok=False)
    csv = ROOT / 'data/wide-world-importers/exports/csv'
    oracle = reference(csv)
    write(output / 'reference.json', oracle)
    base = Config.load()
    name = 'dr_rounds_eval_' + uuid4().hex
    with connect(base) as db:
        db.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
    config = replace(base, dsn=make_conninfo(base.dsn, dbname=name), storage=output / 'storage')
    migrate(config)
    model = ModelClient(ModelSettings.load())
    version = source_version()
    write(output / 'manifest.json', dict(database=name, storage=str(config.storage), model=asdict(model.settings),
        source_sha256=version, repeats=repeats, goal=GOAL,
        fixtures={n: hashlib.sha256((csv / (n + '.csv')).read_bytes()).hexdigest() for n in TABLES},
        acceptance='Evidence-linked useful depth; independent numerical assessment; stop/recovery/partial checks in automated tests.'))
    for index in range(1, repeats + 1):
        directory = output / f'run-{index}'
        directory.mkdir()
        started = time.monotonic()
        state = dict(key='rounds-' + uuid4().hex, status='running')
        try:
            if source_version() != version:
                raise ValueError('Source changed; create another evaluation directory.')
            business = create_business(config, 'WWI · investigación por rondas')['id']
            state['business_id'] = str(business)
            batch = import_batch(config, business, [csv / (n + '.csv') for n in TABLES])
            state['analysis_id'] = str(batch['analysis']['id'])
            write(directory / 'state.json', state)
            plan = service.start(config, business, state['analysis_id'], owner_context=OWNER + '\nObjetivo: ' + GOAL,
                                 request_key=state['key'] + '-plan', model=model)
            state['session_id'] = str(plan['id'])
            for _ in range(3):
                if not plan['questions']:
                    break
                for q in plan['questions']:
                    disposition, text = owner_reply(q)
                    plan = service.answer(config, business, plan['id'], question_id=q['id'], disposition=disposition,
                        text=text, request_key='answer-' + q['id'], model=model)
            print(json.dumps(dict(run=index, phase='research')), flush=True)
            work = research.start(config, business, plan['id'], request_key=state['key'] + '-research', model=model)
            state['research_id'] = str(work['id'])
            write(directory / 'research.json', work)
            resumed = research.resume(config, business, work['id'], model=model)
            state['resume_idempotent'] = len(resumed['steps']) == len(work['steps']) and len(resumed['model_calls']) == len(work['model_calls'])
            print(json.dumps(dict(run=index, phase='review', rounds=work['coverage']['rounds_used'], findings=len(work['findings']))), flush=True)
            result = review.start(config, business, work['id'], request_key=state['key'] + '-review', analyst=model, reviewer=model)
            state['review_id'] = str(result['id'])
            for _ in range(3):
                if not result['pending_questions']:
                    break
                for q in result['pending_questions']:
                    disposition, text = owner_reply(q['action']['question'])
                    result = review.answer(config, business, result['id'], step=q['step'], disposition=disposition,
                        text=text, request_key='review-answer-' + str(q['step']), analyst=model, reviewer=model)
            state.update(status=result['status'], publishable=result['publishable'])
            if result['publishable']:
                write(directory / 'export.json', export(config, business, result['id']))
        except Exception as error:
            state.update(status='failed', issue=str(error))
        finally:
            state.update(seconds=round(time.monotonic() - started, 3), source_stable=source_version() == version)
            collect(config, state, directory)
            resources = json.loads((directory / 'resources.json').read_text()) if (directory / 'resources.json').exists() else {}
            state.update(calls=len(resources.get('calls', [])), executions=len(resources.get('executions', [])),
                         monetary_cost=None, **token_accounting(resources.get('calls', []), bool(resources)))
            write(directory / 'state.json', state)
            print(json.dumps(state), flush=True)


def main():
    os.umask(0o077)
    load_env(ROOT / '.env')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--repeats', type=int, choices=(1, 2, 3), default=2)
    args = parser.parse_args()
    run(args.output.resolve(), args.repeats)


if __name__ == '__main__':
    main()
