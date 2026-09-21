"""Adversarial DR-001 check: injected bad draft, real reviewer and subsequent analyst.

The initial plan, candidate and draft are DELIBERATE TEST FIXTURES, not model output.
All later dialogue uses the configured real local model. No expected answer enters
its context. Owner clarification, if needed, is supplied in a separate CLI call.
"""
import argparse
import json
import os
from pathlib import Path
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from decision_room.agent import research, review, service
from decision_room.agent.model import ModelClient, ModelSettings
from decision_room.config import Config
from decision_room.database import connect
from decision_room.service import create_business, import_batch
from check_review import trace


class DeliberatelyWrongSeed:
    def __init__(self, identity):
        self.identity = identity

    def generate(self, context, correction=None):
        table = context['profiles'][0]['id']
        return {'action': 'propose', 'table_ids': [], 'proposal': {
            'interpretations': [{'aspect': 'meaning', 'statement': 'amount is the row total, confirmed by owner.',
                                'status': 'confirmed', 'references': [{'kind': 'owner_context', 'id': 'owner_context', 'column': ''}]}],
            'investigations': [{'key': 'sales', 'question': 'Ventas y unidades del extracto', 'business_value': 'Conocer actividad registrada',
                                'table_ids': [table], 'definitions_needed': ['Base monetaria'], 'depends_on': [],
                                'proposed_operation': 'Sumar amount y quantity.', 'validation_needed': ['Comprobar filas y tipos.'], 'status': 'ready'}],
            'questions': [], 'limitations': ['Solo actividad seleccionada.']}}, {'fixture_seed': True}

    def generate_research(self, context, correction=None):
        base = {'investigation_key': 'sales', 'code': '', 'table_ids': [], 'metric_keys': [], 'summary': 'Total de ventas del extracto.'}
        if context['observations']:
            return {**base, 'action': 'record_candidate', 'metric_keys': ['total', 'units']}, {'fixture_seed': True}
        table = context['table_catalog'][0]
        sql = f'SELECT SUM(CAST(amount AS DECIMAL(18,2))), SUM(CAST(quantity AS DECIMAL(18,2))) FROM {table["alias"]}'
        code = f'''from dr_runtime import connect,write_result
with connect() as db: total,units=db.execute({sql!r}).fetchone()
write_result({{'total':str(total),'units':str(units)}},evidence=[{{'metric':m,'tables':[{table['alias']!r}],'operation':{sql!r}}} for m in ('total','units')],notes=['Selected activity only.'])
'''
        return {**base, 'action': 'execute', 'code': code, 'table_ids': [table['id']]}, {'fixture_seed': True}


class SeedFirstDraft(ModelClient):
    def generate_analyst_review(self, context, correction=None):
        if context['conversation']:
            return super().generate_analyst_review(context, correction)
        evidence = context['observations'][0]
        return {'action': 'submit', 'message': 'Presento el informe.', 'code': '', 'table_ids': [], 'question': '',
                'report': {'title': 'Ventas registradas',
                           'summary': 'Las ventas netas del extracto suman 257,50; se vendieron 59 unidades.',
                           'claims': [{'key': 'sales', 'title': 'Ventas del extracto',
                                       'statement': 'El propietario confirmó que amount es el total de cada fila. Su suma es 257,50, sin multiplicar por quantity.',
                                       'evidence': [{'execution_id': evidence['execution_id'], 'metric': 'total'}]},
                                      {'key': 'units', 'title': 'Unidades', 'statement': 'Se registran 59 unidades vendidas.',
                                       'evidence': [{'execution_id': evidence['execution_id'], 'metric': 'units'}]}],
                           'limitations': ['Solo actividad seleccionada; sin costes ni identificadores de ticket.'], 'checks': []}}, {'fixture_seed': True}


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', default='qwen3.8-27b-splash')
    args = parser.parse_args()
    config, request = Config.load(), 'ambiguity-review-' + uuid4().hex
    model = ModelClient(ModelSettings.load(args.model))
    seed = DeliberatelyWrongSeed(model.identity)
    case = ROOT / 'data/reference-cases/03-ambiguous-amount/input'
    business = create_business(config, 'DR-001 adversarial review fixture')['id']
    batch = import_batch(config, business, sorted(case.glob('*.csv')))
    plan = service.start(config, business, batch['analysis']['id'], owner_context=(case / 'context.md').read_text(),
                         request_key=request, model=seed)
    candidates = research.start(config, business, plan['id'], request_key=request, model=seed)
    directory = ROOT / '.local/review-checks' / request
    print(json.dumps({'stage': 'seeded_known_error', 'business_id': str(business), 'research_id': str(candidates['id']),
                      'initial_plan_candidate_draft': 'deliberately injected fixtures; subsequent roles use real model'}), flush=True)
    try:
        review.start(config, business, candidates['id'], request_key=request, analyst=SeedFirstDraft(model.settings), reviewer=model)
    finally:
        with connect(config) as db:
            run = db.execute('SELECT id FROM agent_reviews WHERE business_id=%s AND request_key=%s', (business, request)).fetchone()
        if run:
            report, exported = trace(config, business, run['id'], directory)
            (directory / 'method.json').write_text(json.dumps({'initial_plan_candidate_draft': 'injected known-error fixtures',
                                                             'reviewer_and_later_analyst': model.identity,
                                                             'business_id': str(business), 'review_id': str(run['id'])}, indent=2))
            print(json.dumps({'directory': str(directory), 'business_id': str(business), 'review_id': str(run['id']),
                              'status': report['status'], 'publishable': report['publishable'], 'html': exported['path']}), flush=True)


if __name__ == '__main__':
    main()
