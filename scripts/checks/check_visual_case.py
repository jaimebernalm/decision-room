"""Check this larger WWI report against independent SQLite references.

Usage: python scripts/checks/check_visual_case.py --audit /private/review.json
Run prepare_visual_case.py first. Does not call an LLM or alter the report.
"""
import argparse
from decimal import Decimal
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit', type=Path, required=True)
    parser.add_argument('--reference', type=Path, default=ROOT / '.local/visual-case/expected.json')
    args = parser.parse_args()
    report = json.loads(args.audit.read_text())
    reference = json.loads(args.reference.read_text())
    observations = {o['execution_id']:o for o in report['observations']}
    assert report['publishable'] and all(c['passed'] for c in report['checks'])
    checked = 0
    grains = []
    for chart in report['report']['charts']:
        ref = chart['series']
        observation = observations[ref['execution_id']]
        assert observation['current'] and observation['status'] == 'completed'
        series = observation['result']['series'][ref['series']]
        grains.append(series['grain'])
        points = series['points']
        if series['grain'] == 'month':
            assert {p['label']:Decimal(p['value']) for p in points} == {k:Decimal(v) for k,v in reference['monthly'].items()}
        elif series['grain'] == 'category':
            assert len(points) == 10
            for point, expected in zip(points, reference['products_by_sales'][:10], strict=True):
                assert point['label'] == expected['id'] + ' — ' + expected['name']
                assert Decimal(point['value']) == Decimal(expected['sales_ex_tax'])
        else:
            raise AssertionError('This case expects monthly and product comparisons.')
        checked += len(points)
    assert sorted(grains) == ['category', 'month']
    assert sum(Decimal(v) for v in reference['monthly'].values()) == Decimal(reference['sales_ex_tax'])
    highlights = report['report']['highlights']
    assert len(highlights) == 3
    expected_highlights = [max(map(Decimal,reference['monthly'].values())), min(map(Decimal,reference['monthly'].values())), Decimal(reference['products_by_sales'][0]['sales_ex_tax'])]
    actual_highlights = [Decimal(observations[h['value']['execution_id']]['result']['metrics'][h['value']['metric']]) for h in highlights]
    assert sorted(actual_highlights) == sorted(expected_highlights)
    print(json.dumps({'chart_values_verified':checked,'highlights_verified':3,'source_rows':reference['rows'],
                      'source_total':reference['sales_ex_tax'],'status':'passed'},indent=2))


if __name__ == '__main__':
    main()
