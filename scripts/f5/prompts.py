"""Fill the fixed evaluator prompts (scripts/f5/prompts/*.md) for every sealed kit.

Usage: python scripts/f5/prompts.py KITS_DIR DATA_DIR OUT_DIR

Writes OUT_DIR/<role>/<id>.md (auditor, grouper, judge, reader_owner, reader_advisor) and
OUT_DIR/<role>/<id>.out.json as each evaluator's required output path. The judge prompt
embeds the oracle of the report's business; no other role sees it. No arm is ever written.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PYTHON = str(Path(__file__).resolve().parents[2].parent.parent / '.venv/bin/python')


def render(name, **values):
    return (HERE / 'prompts' / f'{name}.md').read_text().format(**values)


def main(kits, data, out):
    kits, data, out = Path(kits).resolve(), Path(data).resolve(), Path(out).resolve()
    spec = json.loads((data / 'spec.json').read_text())
    owners = {b['key']: f"{b['name']}. {b['description']}\nPetición: {b['goal']}" for b in spec['businesses']}
    oracle = {o['business']: '\n'.join(f"- {s['id']}: {s['title']}. {s['detail']}" for s in o['signals'])
              for o in json.loads((data / 'oracle.json').read_text())}
    index = json.loads((kits / 'index.json').read_text())
    for role in ('auditor', 'grouper', 'judge', 'reader_owner', 'reader_advisor', 'results'):
        (out / role).mkdir(parents=True, exist_ok=True)
    for code, business in index['reports'].items():
        audit_out = out / 'results' / f'audit-{code}.json'
        (out / 'auditor' / f'{code}.md').write_text(render(
            'auditor', report_dir=kits / 'audit' / code, data_dir=kits / 'audit' / 'data' / business, python=PYTHON,
            owner=owners[business], out_path=audit_out, code=code))
        (out / 'grouper' / f'{code}.md').write_text(render(
            'grouper', audit_path=audit_out, out_path=out / 'results' / f'group-{code}.json', code=code))
        (out / 'judge' / f'{code}.md').write_text(render(
            'judge', report_dir=kits / 'judge' / code, oracle=oracle[business],
            out_path=out / 'results' / f'judge-{code}.json', code=code))
    for pair in index['pairs']:
        business = pair.rsplit('-', 1)[0]
        slots = {s: kits / 'read' / pair / s for s in 'AB'}
        files = {f'{s.lower()}_pages': ', '.join(str(p) for p in sorted(slots[s].glob('page-*.png'))) for s in 'AB'}
        files.update({f'{s.lower()}_text': str(slots[s] / 'report.txt') for s in 'AB'})
        (out / 'reader_owner' / f'{pair}.md').write_text(render(
            'reader_owner', owner=owners[business], pair=pair, out_path=out / 'results' / f'owner-{pair}.json', **files))
        (out / 'reader_advisor' / f'{pair}.md').write_text(render(
            'reader_advisor', pair=pair, out_path=out / 'results' / f'advisor-{pair}.json', **files))
    print(len(index['reports']), 'reports;', len(index['pairs']), 'pairs')


if __name__ == '__main__':
    main(*sys.argv[1:4])
