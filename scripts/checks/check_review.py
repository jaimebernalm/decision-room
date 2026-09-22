"""Run actual review roles against saved research and export their visible dialogue."""
import argparse
import json
import os
from pathlib import Path
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from decision_room.agent import review
from decision_room.config import Config
from decision_room.database import connect
from decision_room.report import export


def trace(config, business_id, review_id, directory):
    report = review.show(config, business_id, review_id)
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    (directory / 'review.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    lines = ['# Conversación de revisión', '', f"Estado: **{report['status']}**. Publicable: **{report['publishable']}**.", '',
             'Decisiones y explicaciones guardadas; no razonamiento interno.', '']
    for event in report['conversation']:
        lines += [f"## {event['step']}. {event['role']} — {event['action']['action']}", '', event['action']['message'], '']
        if event['action']['question']:
            lines += ['Pregunta: ' + event['action']['question'], '']
        if event.get('owner_answer'):
            lines += ['Respuesta del propietario: ' + json.dumps(event['owner_answer'], ensure_ascii=False), '']
        if event['action']['code']:
            file = directory / f"step-{event['step']:02d}-{event['role']}.py"
            file.write_text(event['action']['code'])
            lines += [f'[Python generado, sin editar](<{file.resolve()}>).', '']
    exported = export(config, business_id, review_id)
    lines += [f"[Informe del cliente](<{exported['path']}>).", f"[Registro interno](<{exported['internal_path']}>).", '']
    (directory / 'trace.md').write_text('\n'.join(lines))
    (directory / 'export.json').write_text(json.dumps(exported, indent=2))
    return report, exported


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--business', required=True)
    parser.add_argument('--research')
    parser.add_argument('--review')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--step', type=int)
    parser.add_argument('--answer')
    parser.add_argument('--disposition', choices=['answered', 'unknown', 'declined'], default='answered')
    args = parser.parse_args()
    if bool(args.research) == bool(args.review):
        parser.error('Choose --research for a new review or --review for an existing one.')
    config, request = Config.load(), 'review-check-' + uuid4().hex
    directory = ROOT / '.local/review-checks' / request
    run_id = args.review
    try:
        if args.research:
            result = review.start(config, args.business, args.research, request_key=request)
            run_id = result['id']
        elif args.step is not None:
            review.answer(config, args.business, args.review, step=args.step, text=args.answer or '',
                          disposition=args.disposition, request_key=request)
        elif args.resume:
            review.resume(config, args.business, args.review)
    finally:
        if not run_id:
            with connect(config) as db:
                row = db.execute('SELECT id FROM agent_reviews WHERE business_id=%s AND request_key=%s', (args.business, request)).fetchone()
            run_id = row['id'] if row else None
        if run_id:
            report, exported = trace(config, args.business, run_id, directory)
            print(json.dumps({'directory': str(directory), 'review_id': str(run_id), 'status': report['status'],
                              'publishable': report['publishable'], 'html': exported['path']}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
