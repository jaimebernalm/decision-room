"""Read-only structural checks of blinded product-trial kits and evaluations.

This checks identities, hashes and arithmetic, not whether an auditor's judgment
is correct. It never opens the arm key, executes HTML or repairs an evaluation.
Usage: python scripts/checks/product_trial_verify.py KITS RESULTS
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re


def require(condition, issue):
    if not condition:
        raise ValueError(issue)


def load(path):
    def pairs(items):
        value = {}
        for key, item in items:
            require(key not in value, 'Duplicate JSON field: ' + key)
            value[key] = item
        return value
    def constant(value):
        raise ValueError('Non-finite JSON number: ' + value)
    return json.loads(path.read_text(), object_pairs_hook=pairs, parse_constant=constant)


def integer(value, low=0, high=None):
    return type(value) is int and value >= low and (high is None or value <= high)


def seal(kits):
    """Reject missing, changed, duplicate, extra or escaping files in the kit."""
    listed = set()
    for row in (kits / 'SEALED.sha256').read_text().splitlines():
        digest, name = row.split('  ', 1)
        relative = Path(name)
        require(not relative.is_absolute() and '..' not in relative.parts, 'Seal path escapes kit')
        require(name not in listed, 'Duplicate seal path')
        path = kits / relative
        require(path.resolve().is_relative_to(kits.resolve()), 'Seal path resolves outside kit')
        require(path.is_file() and not path.is_symlink(), 'Sealed file missing or symlink: ' + name)
        require(hashlib.sha256(path.read_bytes()).hexdigest() == digest, 'Sealed bytes changed: ' + name)
        listed.add(name)
    actual = {str(p.relative_to(kits)) for p in kits.rglob('*') if p.is_file() and p != kits / 'SEALED.sha256'}
    require(actual == listed, 'Seal does not cover the exact kit file set')
    return hashlib.sha256((kits / 'SEALED.sha256').read_bytes()).hexdigest()


def audit(value, code):
    require(value.get('report') == code, 'Audit report identity differs')
    claims = value.get('claims')
    require(isinstance(claims, list) and bool(claims), 'Audit has no claims')
    counts = Counter()
    for claim in claims:
        require(isinstance(claim, dict), 'Audit claim is not an object')
        require(isinstance(claim.get('texto'), str) and bool(claim['texto'].strip()), 'Audit claim has no text')
        require(claim.get('seccion') in ('prioridad', 'resto'), 'Invalid audit section')
        require(claim.get('tipo') in ('cifra', 'comparacion', 'causa', 'recomendacion'), 'Invalid audit claim type')
        require(claim.get('veredicto') in ('correcta', 'menor', 'material', 'critico', 'no_comprobable'), 'Invalid audit verdict')
        require(type(claim.get('calculable')) is bool, 'calculable must be a boolean')
        require(not claim['calculable'] or claim['tipo'] in ('cifra', 'comparacion'), 'Non-numeric claim marked calculable')
        if claim['calculable']:
            counts[claim['seccion'] + '_calculables'] += 1
            if claim['veredicto'] == 'correcta':
                counts[claim['seccion'] + '_correctas'] += 1
    expected = {section + suffix: counts[section + suffix]
                for section in ('prioridad', 'resto') for suffix in ('_calculables', '_correctas')}
    require(value.get('denominadores') == expected and all(integer(v) for v in value['denominadores'].values()),
            'Audit denominators differ from claims')
    return claims


def group(value, code, claims):
    require(value.get('report') == code, 'Group report identity differs')
    groups = value.get('grupos')
    require(isinstance(groups, list), 'Missing material groups')
    wanted = {i for i, c in enumerate(claims) if c['veredicto'] in ('material', 'critico')}
    seen = []
    critical = 0
    for item in groups:
        indices = item.get('afirmaciones')
        require(isinstance(indices, list) and bool(indices), 'Empty material group')
        require(all(integer(i, high=len(claims)-1) and i in wanted for i in indices), 'Group has non-material or invalid index')
        level = 'critico' if any(claims[i]['veredicto'] == 'critico' for i in indices) else 'material'
        require(item.get('nivel') == level, 'Group does not preserve maximum severity')
        seen.extend(indices)
        critical += level == 'critico'
    require(set(seen) == wanted and len(seen) == len(set(seen)), 'Material claims are omitted or grouped more than once')
    require(integer(value.get('material_distintos')) and value['material_distintos'] == len(groups),
            'Material count must include critical groups')
    require(integer(value.get('criticos_distintos')) and value['criticos_distintos'] == critical, 'Critical group count differs')


def judge(value, code):
    require(value.get('report') == code, 'Judge report identity differs')
    for number in range(1, 7):
        require(integer(value.get('S' + str(number)), high=1 if number == 6 else 2), 'Judge signal outside rubric')


def reader(value, pair):
    require(value.get('pair') == pair, 'Reader pair identity differs')
    require(value.get('eleccion') in ('A', 'B', 'empate'), 'Reader did not give a valid choice')
    require(isinstance(value.get('motivo'), str) and bool(value['motivo'].strip()), 'Reader has no reason')


def verify(kits, results):
    kits, results = Path(kits), Path(results)
    issues = []
    try:
        digest = seal(kits)
        index = load(kits / 'index.json')
        require(isinstance(index, dict) and isinstance(index.get('reports'), dict)
                and isinstance(index.get('pairs'), list), 'Invalid kit index')
        require(all(re.fullmatch(r'R[0-9]{3}', code) for code in index['reports']), 'Invalid report code')
        require(all(isinstance(pair, str) and re.fullmatch(r'[a-z][a-z0-9-]*-[1-9][0-9]*', pair)
                    for pair in index['pairs']), 'Invalid pair code')
        require(len(index['pairs']) == len(set(index['pairs'])), 'Duplicate reader pair')
    except (ValueError, OSError, TypeError) as error:
        return {'valid': False, 'issues': ['kit: ' + str(error)]}
    if index.get('incomplete_pairs'):
        issues.append('Reader pairs marked incomplete in the frozen kit index')
    def check(filename, function):
        try:
            return function(load(results / filename))
        except (ValueError, OSError, TypeError, KeyError, AttributeError) as error:
            issues.append(filename + ': ' + str(error))
    for code in index['reports']:
        claims = check('audit-' + code + '.json', lambda v: audit(v, code))
        if claims is not None:
            check('group-' + code + '.json', lambda v: group(v, code, claims))
        check('judge-' + code + '.json', lambda v: judge(v, code))
    for pair in index['pairs']:
        for role in ('owner', 'advisor'):
            check(role + '-' + pair + '.json', lambda v: reader(v, pair))
    return {'valid': not issues, 'reports': len(index['reports']), 'pairs': len(index['pairs']),
            'kit_sha256': digest, 'issues': issues}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kits'); parser.add_argument('results')
    args = parser.parse_args()
    result = verify(args.kits, args.results)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['valid'] else 1)
