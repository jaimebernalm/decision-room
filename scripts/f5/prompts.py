"""Fill the fixed evaluator prompts (scripts/f5/prompts/*.md) for every sealed kit.

Usage: python scripts/f5/prompts.py KITS_DIR DATA_DIR OUT_DIR [--quotes] [--web[=MAX_IMAGES]]

--quotes (N4 onward) asks the auditor for an exact quote per claim, for the auditor-checker cross-match.
--web (M5): readers get only the web view captures of A and B (no text), with the image limit
fixed in the preregistration (default 20).

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


def main(kits, data, out, quotes=False, web=None):
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
            owner=owners[business], out_path=audit_out, code=code) + (render('auditor_quotes') if quotes else ''))
        (out / 'grouper' / f'{code}.md').write_text(render(
            'grouper', audit_path=audit_out, out_path=out / 'results' / f'group-{code}.json', code=code))
        (out / 'judge' / f'{code}.md').write_text(render(
            'judge', report_dir=kits / 'judge' / code, oracle=oracle[business],
            out_path=out / 'results' / f'judge-{code}.json', code=code))
    for pair in index['pairs']:
        business = pair.rsplit('-', 1)[0]
        slots = {s: kits / 'read' / pair / s for s in 'AB'}
        files = {f'{s.lower()}_pages': ', '.join(str(p) for p in sorted(slots[s].glob('page-*.png'))) for s in 'AB'}
        limit = web or 16
        if sum(len(list(slots[s].glob('page-*.png'))) for s in 'AB') > limit:
            raise SystemExit(f'{pair} exceeds the {limit}-image reading limit; it must be marked incomplete, never truncated.')
        if not web:
            files.update({f'{s.lower()}_text': str(slots[s] / 'report.txt') for s in 'AB'})
        suffix = '_web' if web else ''
        (out / 'reader_owner' / f'{pair}.md').write_text(render(
            'reader_owner' + suffix, owner=owners[business], pair=pair, out_path=out / 'results' / f'owner-{pair}.json', **files))
        (out / 'reader_advisor' / f'{pair}.md').write_text(render(
            'reader_advisor' + suffix, pair=pair, out_path=out / 'results' / f'advisor-{pair}.json', **files))
    print(len(index['reports']), 'reports;', len(index['pairs']), 'pairs')


if __name__ == '__main__':
    web = next((int(a.split('=', 1)[1]) if '=' in a else 20 for a in sys.argv[4:] if a.startswith('--web')), None)
    main(*sys.argv[1:4], quotes='--quotes' in sys.argv[4:], web=web)
