"""Paired blind comparison for the engine gate (preregistration 2026-10-06, step 3).

python -m decision_room.evaluation.trial_pairs plan BATCH --seed N [--against opencode,product]
python -m decision_room.evaluation.trial_pairs kit BATCH OUT --measure contenido|artefacto
python -m decision_room.evaluation.trial_pairs score BATCH --kit OUT_NAME --reader FILE [--reader FILE]

plan fixes, before any attempt runs, which engine repetition faces which repetition of each
opponent arm, from a recorded seed. kit gives readers one page per measure with both reports of
each pair side by side, left/right at random and fresh codes; the key stays in BATCH. score turns
each reader's vote into a score for the engine (win 1, tie 0.5, loss 0); per pair, the mean of the
votes decides the pair (> 0.5 win 1, = 0.5 tie 0.5, < 0.5 loss 0) and the raw mean is kept; the
gate takes the mean of pair results per dataset and opponent: >= 0.5 against the agent loop and
> 0.5 against the pipeline, in every dataset. A lost report is replaced by its first replacement
attempt; if that is lost too the pair is insufficient, stays planned and the gate cannot pass.
"""
import argparse
import base64
from datetime import datetime, timezone
import json
from pathlib import Path
import random
from uuid import uuid4

from .runner import write
from .trial_kit import LABELS, debrand, neutralize
from .trials import read, text_of

ENGINE = 'engine'
GATE = {'opencode': ('>=', 0.5), 'product': ('>', 0.5)}  # agent loop with panorama; frozen pipeline
MEASURES = {'contenido': 'Presentación igualada: juzga qué ayuda más a decidir.',
            'artefacto': 'Presentación real: juzga qué informe entregarías al dueño.'}
CHOICES = {'A': 1.0, 'empate': 0.5, 'B': 0.0}  # from the point of view of side A


def plan(batch, seed, against=('opencode', 'product')):
    """Seeded pairing of repetitions, written before running so results cannot shape it."""
    batch = Path(batch)
    manifest = read(batch / 'manifest.json')
    if (batch / 'pairs.json').exists():
        raise SystemExit('Pairs already planned for this batch.')
    states = [read(batch / 'jobs' / name / 'state.json') for name in manifest['order']]
    if any(s['status'] != 'not_run' for s in states):
        raise SystemExit('Plan pairs before any attempt runs.')
    missing = {ENGINE, *against} - set(manifest['systems'])
    if missing:
        raise SystemExit(f'Batch lacks arms: {", ".join(sorted(missing))}.')
    rng = random.Random(seed)
    pairs = []
    for dataset in manifest['datasets']:
        reps = lambda system: sorted(s['repetition'] for s in states
                                     if s['dataset'] == dataset and s['system'] == system)
        engine = reps(ENGINE)
        for opponent in against:
            other = reps(opponent)
            if len(other) != len(engine):
                raise SystemExit(f'{dataset}: {opponent} has {len(other)} repetitions, engine {len(engine)}.')
            rng.shuffle(other)
            pairs += [{'id': f'{dataset}-{opponent}-{i + 1}', 'dataset': dataset, 'opponent': opponent,
                       'engine': f'{dataset}-{ENGINE}-{e}', 'other': f'{dataset}-{opponent}-{o}'}
                      for i, (e, o) in enumerate(zip(engine, other))]
    write(batch / 'pairs.json', {'created_at': datetime.now(timezone.utc).isoformat(), 'seed': seed,
                                 'against': list(against), 'pairs': pairs})
    return pairs


def delivered(batch, job):
    """De-branded HTML of a completed attempt with readable text, else None."""
    path = Path(batch) / 'jobs' / job / 'informe.html'
    state = read(Path(batch) / 'jobs' / job / 'state.json')
    if state['status'] != 'completed' or not path.exists():
        return None
    html = path.read_text(errors='replace')
    return debrand(html) if text_of(html).strip() else None


def report(batch, job):
    """The planned attempt's report, or its first replacement's (preregistration: one per slot)."""
    html = delivered(batch, job)
    if html is not None:
        return html, job
    replacement = Path(batch) / 'jobs' / f'{job}r1'
    if replacement.exists() and read(replacement / 'state.json').get('replaces') == job:
        html = delivered(batch, replacement.name)
        if html is not None:
            return html, replacement.name
    return None, None


def kit(batch, out, measure):
    batch, out = Path(batch).resolve(), Path(out).resolve()
    if measure not in MEASURES:
        raise SystemExit(f'Measure must be one of {", ".join(MEASURES)}.')
    key_path = batch / f'kit-key-{out.name}.json'
    if out.exists() or key_path.exists():
        raise SystemExit('Kit already built; keep its codes so readers stay aligned.')
    if out.is_relative_to(batch):
        raise SystemExit('Build the kit outside the batch, so readers never browse attempts or keys.')
    rng = random.Random(uuid4().int)
    items, key, skipped = [], {}, []
    for pair in read(batch / 'pairs.json')['pairs']:
        (engine, engine_job), (other, other_job) = report(batch, pair['engine']), report(batch, pair['other'])
        if engine is None or other is None:
            skipped.append(pair['id'])
            continue
        engine_left = rng.random() < 0.5
        left, right = (engine, other) if engine_left else (other, engine)
        if measure == 'contenido':
            left, right = neutralize(left), neutralize(right)
        code = uuid4().hex[:6]
        key[code] = {'pair': pair['id'], 'engine_side': 'A' if engine_left else 'B',
                     'jobs': [engine_job, other_job]}
        items.append({'code': code, 'dataset': pair['dataset'],
                      'label': LABELS.get(pair['dataset'].split('-')[0], pair['dataset']),
                      'a': base64.b64encode(left.encode()).decode(),
                      'b': base64.b64encode(right.encode()).decode()})
    rng.shuffle(items)
    items.sort(key=lambda i: i['dataset'])
    write(key_path, {'created_at': datetime.now(timezone.utc).isoformat(), 'measure': measure,
                     'out': str(out), 'codes': key, 'skipped': skipped})
    out.mkdir(parents=True)
    page = PAGE.replace('__DATA__', json.dumps(items)).replace('__KIT__', uuid4().hex[:8]) \
               .replace('__MEASURE__', MEASURES[measure])
    (out / 'comparacion.html').write_text(page, encoding='utf-8')
    return {'pairs': len(items), 'skipped': skipped}


def engine_score(choice, engine_side):
    """Reader choice ('A', 'B' or 'empate') as the engine's score: win 1, tie 0.5, loss 0."""
    value = CHOICES[choice]
    return value if engine_side == 'A' else 1 - value


def pair_result(votes):
    """Mean of the readers' votes decides the pair: win 1, tie 0.5, loss 0 for the engine."""
    mean = sum(votes) / len(votes)
    return (1.0 if mean > 0.5 else 0.5 if mean == 0.5 else 0.0), mean


def score(batch, kit_name, readers):
    """Pair results from readers' votes, their mean per dataset and opponent, and the gate."""
    batch = Path(batch)
    key = read(batch / f'kit-key-{kit_name}.json')
    pairs = {p['id']: p for p in read(batch / 'pairs.json')['pairs']}
    per_pair = {}
    for answers in readers:
        for code, entry in answers['choices'].items():
            if code in key['codes'] and entry.get('choice') in CHOICES:
                info = key['codes'][code]
                per_pair.setdefault(info['pair'], []).append(engine_score(entry['choice'], info['engine_side']))
    groups = {}
    for pair_id, votes in per_pair.items():
        pair = pairs[pair_id]
        groups.setdefault((pair['dataset'], pair['opponent']), []).append(pair_result(votes))
    table = []
    for (dataset, opponent), results in sorted(groups.items()):
        mean = sum(r for r, _ in results) / len(results)
        sign, threshold = GATE[opponent]
        passed = mean >= threshold if sign == '>=' else mean > threshold
        table.append({'dataset': dataset, 'opponent': opponent, 'pairs': len(results), 'mean': round(mean, 4),
                      'raw_vote_mean': round(sum(m for _, m in results) / len(results), 4),
                      'threshold': f'{sign} {threshold}', 'passed': passed})
    unscored = sorted(set(pairs) - set(per_pair))
    result = {'measure': key['measure'], 'readers': len(readers), 'groups': table,
              'insufficient_pairs': key['skipped'], 'unscored_pairs': unscored,
              'passed': not unscored and all(row['passed'] for row in table)}
    write(batch / f'pairs-score-{kit_name}.json', result)
    return result


PAGE = r'''<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Comparación de informes</title>
<style>
:root{--bg:#f7f6f2;--panel:#fff;--ink:#1d2a26;--muted:#5f6d68;--line:#e2e4dd;--accent:#2f6f57;--warn:#9a5b16}
@media (prefers-color-scheme:dark){:root{--bg:#141816;--panel:#1d2320;--ink:#e8ece9;--muted:#9aa6a1;--line:#2f3833;--accent:#7cc4a3;--warn:#e0a35a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
header{padding:18px 24px;border-bottom:1px solid var(--line)}h1{margin:0 0 4px;font-size:22px}header p{margin:0;color:var(--muted);max-width:900px}
nav{display:flex;flex-wrap:wrap;gap:6px;padding:12px 24px;border-bottom:1px solid var(--line)}
nav button{border:1px solid var(--line);background:var(--panel);color:var(--ink);border-radius:8px;padding:6px 10px;cursor:pointer;font:inherit}
nav button[aria-current=true]{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent)}nav .done{color:var(--accent)}
main{padding:16px 24px 48px}.pair{display:grid;grid-template-columns:1fr 1fr;gap:12px}.pair h3{margin:0 0 6px}
iframe{width:100%;height:70vh;border:1px solid var(--line);border-radius:10px;background:#fff}
form{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:16px 18px;margin-top:16px}
.choices{display:flex;gap:16px;flex-wrap:wrap}.choices label{display:flex;gap:6px;align-items:center}
label.q{display:block;font-weight:600;margin:12px 0 6px}textarea{width:100%;min-height:70px;font:inherit;padding:8px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--ink)}
.row{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-top:14px}
.primary{background:var(--accent);color:#fff;border:0;border-radius:8px;padding:10px 16px;font:inherit;cursor:pointer}
.secondary{background:transparent;color:var(--ink);border:1px solid var(--line);border-radius:8px;padding:10px 16px;font:inherit;cursor:pointer}
.saved{color:var(--accent)}.warn{color:var(--warn)}
@media (max-width:900px){.pair{grid-template-columns:1fr}iframe{height:60vh}}
</style></head><body>
<header><h1>Comparación de informes</h1>
<p>__MEASURE__ Lee los dos informes de cada pareja como si fueras el dueño del negocio. No sabes qué sistema escribió cada uno ni hace falta adivinarlo. Elige el más útil o «empate», y explica por qué. Las respuestas se guardan en este navegador; al terminar, pulsa «Descargar respuestas».</p>
<div class="row"><button class="secondary" type="button" onclick="download()">Descargar respuestas</button></div></header>
<nav id="nav"></nav><main id="main"></main>
<script>
const DATA=__DATA__, KIT="__KIT__", KEY="comparacion-informes-"+KIT;
const decode=b=>new TextDecoder().decode(Uint8Array.from(atob(b),c=>c.charCodeAt(0)));
let state={choices:{}};
try{const s=localStorage.getItem(KEY);if(s)state=JSON.parse(s)}catch(e){}
const save=()=>{try{localStorage.setItem(KEY,JSON.stringify(state))}catch(e){}};
const esc=t=>String(t||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
let current=null;
function nav(){const n=document.getElementById('nav');n.innerHTML='';
 DATA.forEach((d,i)=>{const b=document.createElement('button');const c=state.choices[d.code];
  b.setAttribute('aria-current',current===d.code);b.innerHTML=`${esc(d.label)} · Pareja ${i+1} <span class="done">${c&&c.choice?'✓':''}</span>`;
  b.onclick=()=>show(d.code);n.appendChild(b)})}
function show(code){current=code;nav();const d=DATA.find(x=>x.code===code);const c=state.choices[code]||{};
 const m=document.getElementById('main');
 m.innerHTML=`<div class="pair"><div><h3>Informe A</h3><iframe sandbox="allow-scripts" title="Informe A"></iframe></div>
 <div><h3>Informe B</h3><iframe sandbox="allow-scripts" title="Informe B"></iframe></div></div>
 <form id="f"><label class="q">¿Cuál te ayuda más a decidir qué hacer en tu negocio?</label>
 <div class="choices">${[['A','A es mejor'],['empate','Empate'],['B','B es mejor']].map(([v,t])=>`<label><input type="radio" name="choice" value="${v}" ${c.choice===v?'checked':''}>${t}</label>`).join('')}</div>
 <label class="q">¿Por qué?</label><textarea name="motivo">${esc(c.motivo)}</textarea>
 <div class="row"><button class="primary" type="submit">Guardar</button><span id="msg"></span></div></form>`;
 const frames=m.querySelectorAll('iframe');frames[0].srcdoc=decode(d.a);frames[1].srcdoc=decode(d.b);
 m.querySelector('#f').onsubmit=e=>{e.preventDefault();const f=new FormData(e.target);
  state.choices[code]={choice:f.get('choice'),motivo:f.get('motivo'),saved_at:new Date().toISOString()};save();nav();
  document.getElementById('msg').innerHTML=f.get('choice')?'<span class="saved">Guardado.</span>':'<span class="warn">Falta elegir.</span>'};
 window.scrollTo(0,0)}
function download(){const blob=new Blob([JSON.stringify({kit:KIT,exportado:new Date().toISOString(),...state},null,2)],{type:'application/json'});
 const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='comparacion-'+KIT+'.json';a.click()}
nav();if(DATA.length)show(DATA[0].code);
</script></body></html>
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('plan')
    p.add_argument('batch', type=Path)
    p.add_argument('--seed', type=int, required=True)
    p.add_argument('--against', default='opencode,product')
    k = commands.add_parser('kit')
    k.add_argument('batch', type=Path)
    k.add_argument('out', type=Path)
    k.add_argument('--measure', required=True, choices=list(MEASURES))
    s = commands.add_parser('score')
    s.add_argument('batch', type=Path)
    s.add_argument('--kit', required=True, help='Name of the kit folder, as in kit-key-<name>.json')
    s.add_argument('--reader', action='append', required=True, type=Path)
    args = parser.parse_args()
    if args.command == 'plan':
        print(json.dumps(plan(args.batch, args.seed, tuple(a for a in args.against.split(',') if a)), indent=2))
    elif args.command == 'kit':
        print(json.dumps(kit(args.batch, args.out, args.measure)))
    else:
        print(json.dumps(score(args.batch, args.kit, [read(p) for p in args.reader]), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
