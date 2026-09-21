"""Exercise the real configured model; keep reports and IDs in ignored .local/."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from decision_room.config import Config
from decision_room.service import create_business, import_batch


def cli(*args):
    process = subprocess.run([sys.executable, '-m', 'decision_room', *map(str, args)],
                             cwd=ROOT, capture_output=True, text=True, timeout=1200)
    if process.returncode:
        raise ValueError(process.stderr.strip() or process.stdout)
    return json.loads(process.stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True)
    parser.add_argument('--case', choices=['01-daily-sales', '02-product-sales', '03-ambiguous-amount'], default='03-ambiguous-amount')
    parser.add_argument('--variant', action='store_true')
    parser.add_argument('--answer', choices=['unit_price', 'line_total', 'unknown', 'declined'], default='unit_price')
    parser.add_argument('--wwi-business')
    parser.add_argument('--wwi-analysis')
    args = parser.parse_args()
    key = 'agent-check-' + uuid4().hex
    directory = ROOT / '.local/agent-checks' / key
    directory.mkdir(parents=True)
    config = Config.load()
    case = ROOT / 'data/reference-cases' / args.case
    if args.wwi_business or args.wwi_analysis:
        if not (args.wwi_business and args.wwi_analysis):
            parser.error('Provide both WWI IDs.')
        business, analysis = args.wwi_business, args.wwi_analysis
        context = directory / 'context.md'
        context.write_text('Somos un mayorista de productos. Estos archivos son un lote de la misma empresa. '
                           'Quiero investigar las ventas por producto y cliente y su relación con existencias. '
                           'Inspecciona las tablas relevantes, plantea comprobaciones de sus relaciones y '
                           'pregunta solo por definiciones que cambien lo que se puede investigar.\n')
    else:
        business = create_business(config, 'Reference agent check')['id']
        input_dir = case / ('variants/renamed-columns' if args.variant else 'input')
        analysis = import_batch(config, business, sorted(input_dir.glob('*.csv')))['analysis']['id']
        context = case / 'input/context.md'
    report = {'model': args.model, 'case': 'WWI' if args.wwi_business else args.case,
              'variant': args.variant, 'owner_answer': args.answer,
              'business_id': str(business), 'analysis_id': str(analysis), 'runs': []}
    started = time.monotonic()
    try:
        # Each command exits fully. The answer loads checkpoints in a NEW process.
        first = cli('agent-start', '--business', business, '--analysis', analysis,
                    '--context-file', context, '--request-key', key, '--model', args.model)
        report['runs'].append(first)
        (directory / 'initial.json').write_text(json.dumps(first, ensure_ascii=False, indent=2))
        print(json.dumps({'stage': 'initial', 'session': first['id'], 'status': first['status'],
                          'questions': first['questions']}, ensure_ascii=False), flush=True)
        if not args.wwi_business and args.case == '03-ambiguous-amount':
            if len(first['questions']) != 1:
                raise ValueError('Ambiguity reference expects one material question; inspect the saved proposal.')
            disposition = args.answer if args.answer in ('unknown', 'declined') else 'answered'
            # Evaluator sends ONE explicit owner reply. No answer-key file is fed to the model.
            response = ''
            if disposition == 'answered':
                responses = json.loads((case / 'evaluation/owner-responses.json').read_text())
                response = responses[args.answer]
                if isinstance(response, dict):
                    response = response['response']
            second = cli('agent-answer', '--business', business, '--session', first['id'],
                         '--question', first['questions'][0]['id'], '--request-key', key + '-answer',
                         '--disposition', disposition, '--text', response)
            report['runs'].append(second)
            (directory / 'answered.json').write_text(json.dumps(second, ensure_ascii=False, indent=2))
            if second['questions']:
                raise ValueError('Agent asked again after the owner reply; inspect the revision.')
            if len(second['answers']) != 1 or len(second['revisions']) < 2:
                raise ValueError('Owner reply did not produce a durable revised proposal.')
        report['status'] = 'completed_requires_semantic_review'
    except Exception as error:
        report.update(status='failed', issue=str(error))
        raise
    finally:
        report['elapsed_seconds'] = round(time.monotonic() - started, 2)
        (directory / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        print(json.dumps({'report': str(directory / 'report.json'), 'status': report['status'],
                          'elapsed_seconds': report['elapsed_seconds']}), flush=True)


if __name__ == '__main__':
    main()
