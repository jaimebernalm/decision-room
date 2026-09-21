"""Run real-model investigations and export a readable local trace, without editing generated code."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from decision_room.config import Config
from decision_room.database import connect
from decision_room.service import create_business, import_batch
from decision_room.storage import Storage, digest
from decision_room.agent import research, service
from decision_room.agent.model import ModelClient, ModelSettings


def export_trace(config, business_id, report, directory):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'research.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    lines = ['# Investigación con Python generado', '',
             f"Estado: **{report['status']}**. Verificación: **{report['verification']}**. No publicable todavía.", '',
             f"Sesión de planificación: `{report['session_id']}`. Investigación: `{report['id']}`.", '',
             '## Trabajo y resultados', '']
    for work in report['investigations']:
        lines.extend([f"- **{work['key']}** — {work['research_status']}: {work['question']}"])
    lines.extend(['', '## Recorrido guardado', ''])
    store = Storage(config.storage)
    for step in report['steps']:
        action, execution = step['action'], step.get('execution')
        lines.extend([f"### Paso {step['step']}: {action['action']}", '', action['summary'], ''])
        if action['action'] == 'execute':
            path = directory / f"step-{step['step']:02d}.py"
            path.write_text(action['code'])
            lines.extend([f'[Código generado, sin editar](<{path.resolve()}>).', ''])
        if execution:
            lines.extend([f"Ejecución `{execution['id']}`: **{execution['status']}**.", ''])
            if execution['issue']:
                lines.extend([f"Diagnóstico: {execution['issue']}", ''])
            if execution['result']:
                lines.extend(['```json', json.dumps(execution['result'], ensure_ascii=False, indent=2), '```', ''])
            if action['action'] == 'execute':
                target = directory / f"step-{step['step']:02d}-artifacts"
                for artifact in execution['artifacts']:
                    source = store.path(business_id, artifact['storage_key'])
                    if digest(source) != artifact['sha256']:
                        raise ValueError('Artifact failed its integrity check.')
                    target.mkdir(exist_ok=True)
                    destination = target / artifact['name']
                    shutil.copyfile(source, destination)
                    lines.append(f"- [{artifact['name']}](<{destination.resolve()}>)")
                lines.append('')
    lines.extend(['## Límites', '', 'Estas son acciones y explicaciones del agente, no su razonamiento interno. '
                  'Un programa ejecutado correctamente y un resultado estructuralmente válido pueden contener '
                  'supuestos equivocados. La revisión independiente corresponde al paso 1.6.', ''])
    (directory / 'trace.md').write_text('\n'.join(lines))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', default=None)
    parser.add_argument('--case', choices=['01-daily-sales', '02-product-sales', '03-ambiguous-amount'], default='01-daily-sales')
    parser.add_argument('--basis', choices=['unspecified', 'unit_price', 'line_total'], default='unspecified')
    parser.add_argument('--variant', action='store_true')
    parser.add_argument('--business')
    parser.add_argument('--session', help='Use an existing provisional plan, without another planning call.')
    parser.add_argument('--replace-session', help='Replan from this session using the selected reference owner context.')
    parser.add_argument('--research', help='Export an existing research run without model calls.')
    parser.add_argument('--max-investigations', type=int, default=2)
    parser.add_argument('--investigation', action='append', default=[])
    args = parser.parse_args()
    if sum(bool(x) for x in (args.session, args.replace_session, args.research)) > 1:
        parser.error('Choose only one existing session, replacement or research run.')
    if (args.session or args.replace_session or args.research) and not args.business:
        parser.error('Existing records require --business.')
    config, key = Config.load(), uuid4().hex
    directory = ROOT / '.local/research-checks' / key
    directory.mkdir(parents=True)
    case = ROOT / 'data/reference-cases' / args.case
    metadata = {'case': args.case, 'basis': args.basis, 'variant': args.variant, 'status': 'running'}
    started = time.monotonic()
    business, plan = None, None
    try:
        if args.research:
            report = research.show(config, args.business, args.research)
            business = args.business
        else:
            if args.session:
                business, plan = args.business, service.show(config, args.business, args.session)
            else:
                context = (case / 'input/context.md').read_text()
                if args.basis != 'unspecified':
                    if args.case != '03-ambiguous-amount':
                        parser.error('--basis is only for the ambiguous amount reference.')
                    responses = json.loads((case / 'evaluation/owner-responses.json').read_text())
                    context += '\nOwner clarification: ' + responses[args.basis] + '\n'
                model = ModelClient(ModelSettings.load(args.model))
                if args.replace_session:
                    business = args.business
                    plan = service.replan(config, business, args.replace_session, owner_context=context,
                                          request_key='research-check-plan-' + key, model=model)
                else:
                    business = create_business(config, 'Real-model research reference')['id']
                    folder = case / ('variants/renamed-columns' if args.variant else 'input')
                    batch = import_batch(config, business, sorted(folder.glob('*.csv')))
                    plan = service.start(config, business, batch['analysis']['id'], owner_context=context,
                                         request_key='research-check-plan-' + key, model=model)
            metadata.update(business_id=str(business), session_id=str(plan['id']))
            (directory / 'plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2, default=str))
            print(json.dumps({'stage': 'plan', 'business': str(business), 'session': str(plan['id']), 'status': plan['status']}, default=str), flush=True)
            report = research.start(config, business, plan['id'], request_key='research-check-' + key,
                                    max_investigations=args.max_investigations, investigation_keys=args.investigation)
        export_trace(config, business, report, directory)
        metadata.update(status=report['status'], research_id=str(report['id']), verification='requires_independent_review')
        # Read references ONLY AFTER all model calls. They never enter the agent context.
        if not args.research:
            expected = json.loads((case / 'evaluation/expected.json').read_text())
            (directory / 'evaluator-reference.json').write_text(json.dumps(expected, ensure_ascii=False, indent=2))
    except Exception as error:
        metadata.update(status='failed', issue=str(error))
        if business is not None and plan is not None:
            with connect(config) as db:
                saved = db.execute('''SELECT id FROM agent_research WHERE business_id=%s
                    AND session_id=%s AND request_key=%s''', (business, plan['id'], 'research-check-' + key)).fetchone()
            if saved:
                report = research.show(config, business, saved['id'])
                export_trace(config, business, report, directory)
                metadata['research_id'] = str(saved['id'])
        raise
    finally:
        metadata['elapsed_seconds'] = round(time.monotonic() - started, 2)
        (directory / 'check.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
        print(json.dumps({'directory': str(directory), **metadata}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
