"""Blind evaluation kits for a finished trial batch.

python -m decision_room.evaluation.trial_kit BATCH OUT

Reports get fresh random codes and are shuffled; the code-to-attempt key is
written to BATCH/kit-key-<OUT name>.json, never into OUT. Every report gets the
same neutral typography and grayscale palette. OUT/lector holds one offline
page for the owner (full reports, plain questions, saved in the browser and
exported as JSON). OUT/tecnica holds de-branded reports, the agents' inputs and
a template for a technical evaluator, without any oracle. Style can still
reveal a system: this reduces bias, it does not remove it.
"""
import argparse
import base64
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
from pathlib import Path
import random
import re
import shutil
from uuid import uuid4

from .runner import write
from .trials import read, text_of

BRANDING = [(re.compile(r'Decision Room\s*·\s*Informe de negocio', re.I), 'Informe'),
            (re.compile(r'\s*[·—-]\s*Decision Room', re.I), ''),
            (re.compile(r'Decision Room', re.I), ''),
            (re.compile(r'Generado:\s*[0-9T:+\-.]+'), '')]
LABELS = {'bruma': 'Bruma Café · 3 meses de datos', 'albor': 'Albor Café · 5 años de datos'}
RUBRIC = ['significado', 'cobertura', 'profundidad', 'prioridad', 'siguientes_comprobaciones',
          'comparabilidad', 'claridad', 'ausencia_de_repeticion', 'cifras_narradas', 'decisiones',
          'integridad_visual', 'incertidumbre_de_fuentes']


NEUTRAL = '''<style id="kit-neutral">
html{filter:grayscale(1)!important;background:#fff!important}
body{background:#fff!important;color:#222!important;font-size:16px!important}
*{font-family:-apple-system,"Helvetica Neue",Arial,sans-serif!important;letter-spacing:normal!important;
  text-transform:none!important;box-shadow:none!important;text-shadow:none!important;border-radius:0!important}
h1{font-size:28px!important;font-weight:700!important;line-height:1.25!important}
h2{font-size:22px!important;font-weight:700!important;line-height:1.3!important}
h3,h4{font-size:18px!important;font-weight:700!important}
p,li,td,th,dd,dt,summary,blockquote{font-size:16px!important;line-height:1.55!important}
/* Text blocks white with dark text; empty elements (bars, swatches) keep their shade. */
body *:not(:empty){background-color:#fff!important;background-image:none!important;
  color:#222!important;border-color:#ddd!important}
</style>'''


def debrand(html):
    for pattern, replacement in BRANDING:
        html = pattern.sub(replacement, html)
    return html


def neutralize(html):
    """Same fonts, sizes, white text blocks and grayscale for every report.

    CSS only: some reports forbid scripts, and both systems must get identical
    treatment. Removes quick visual tells (palette, typography, dark cards).
    Structure and wording can still reveal a system; charts keep their shapes."""
    match = re.search(r'</head\s*>', html, flags=re.I)
    return html[:match.start()] + NEUTRAL + html[match.start():] if match else NEUTRAL + html


def collect(batch):
    manifest = read(batch / 'manifest.json')
    reports = []
    for name in manifest['order']:
        job = batch / 'jobs' / name
        state = read(job / 'state.json')
        if state['status'] == 'completed' and (job / 'informe.html').exists():
            original = debrand((job / 'informe.html').read_text(errors='replace'))
            reports.append((state['dataset'], name, neutralize(original), original))
    return manifest, reports


def build(batch, out):
    batch, out = Path(batch).resolve(), Path(out).resolve()
    key_path = batch / f'kit-key-{out.name}.json'
    if key_path.exists() or out.exists():
        raise SystemExit('Kit already built; keep its codes so evaluators stay aligned.')
    if out.is_relative_to(batch):
        raise SystemExit('Build the kit outside the batch, so evaluators never browse attempts or keys.')
    manifest, reports = collect(batch)
    rng = random.Random(uuid4().int)
    rng.shuffle(reports)
    order = sorted(set(r[0] for r in reports), key=lambda d: (d != 'bruma', d))
    reports.sort(key=lambda r: order.index(r[0]))
    key, items = {}, []
    for dataset, name, html, original in reports:
        code = uuid4().hex[:6]
        key[code] = name
        items.append({'code': code, 'dataset': dataset, 'html': html, 'original': original})
    write(key_path, {'created_at': datetime.now(timezone.utc).isoformat(), 'out': str(out), 'codes': key})
    reader(out / 'lector', items)
    technical(batch, out / 'tecnica', items, manifest)
    signals(out / 'senales', items)
    return {'reports': len(items), 'by_dataset': {d: sum(i['dataset'] == d for i in items) for d in order}}


class _ReadingText(HTMLParser):
    BLOCKS = {'p', 'div', 'section', 'article', 'header', 'footer', 'main', 'figure', 'figcaption',
              'table', 'tr', 'ul', 'ol', 'dl', 'dt', 'dd', 'blockquote', 'br', 'caption'}
    INLINE = {'b', 'i', 'strong', 'em', 'a', 'code', 'sup', 'sub', 'small', 'abbr', 'mark', 'u', 's'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.skip, self.folded = [], 0, []

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'svg', 'canvas'):
            self.skip += 1
        elif tag == 'details':
            folded = 'open' not in dict(attrs)
            self.folded.append(folded)
            self.out.append('\n[Sección plegada; solo se ve si se pulsa: ' if folded else '\n')
        elif tag == 'summary':
            pass
        elif tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            self.out.append('\n\n' + '#' * int(tag[1]) + ' ')
        elif tag == 'li':
            self.out.append('\n- ')
        elif tag in ('td', 'th'):
            self.out.append(' | ')
        elif tag in self.BLOCKS:
            self.out.append('\n')
        elif tag not in self.INLINE:
            self.out.append(' ')

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'svg', 'canvas'):
            self.skip = max(0, self.skip - 1)
        elif tag == 'summary' and self.folded and self.folded[-1]:
            self.out.append(']\n')
        elif tag == 'details' and self.folded:
            if self.folded.pop():
                self.out.append('\n[Fin de la sección plegada]\n')
        elif tag in self.BLOCKS or tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            self.out.append('\n')
        elif tag not in self.INLINE:
            self.out.append(' ')

    def handle_data(self, data):
        if not self.skip:
            self.out.append(re.sub(r'\s+', ' ', data))


def reading_text(html):
    """Text as an owner sees the page: headings, lists and table rows kept, folded sections marked."""
    parser = _ReadingText()
    parser.feed(html)
    lines = (' '.join(line.split()) for line in ''.join(parser.out).splitlines())
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(lines)).strip()


def reader(folder, items):
    folder.mkdir(parents=True)
    payload = [{'code': i['code'], 'dataset': i['dataset'], 'label': LABELS.get(i['dataset'], i['dataset']),
                'html': base64.b64encode(i['html'].encode()).decode()} for i in items]
    page = READER.replace('__DATA__', json.dumps(payload)).replace('__KIT__', uuid4().hex[:8])
    (folder / 'evaluacion.html').write_text(page, encoding='utf-8')


def technical(batch, folder, items, manifest):
    (folder / 'informes').mkdir(parents=True)
    (folder / 'render').mkdir()
    for item in items:
        stem = f"{item['dataset']}-{item['code']}"
        (folder / 'informes' / f'{stem}.html').write_text(item['html'], encoding='utf-8')
        (folder / 'render' / f'{stem}.html').write_text(item['original'], encoding='utf-8')
        (folder / 'informes' / f'{stem}.txt').write_text(text_of(item['html']) + '\n', encoding='utf-8')
    for dataset in sorted({i['dataset'] for i in items}):
        target = folder / 'entradas' / dataset
        shutil.copytree(batch / 'inputs' / dataset, target)
    template = {'evaluador': 'Astra', 'informes': {
        f"{i['dataset']}-{i['code']}": {
            'cifras': {'comprobadas': None, 'erroneas': []},
            'prioridad_principal': '', 'prioridad_justificada_frente_alternativa': None,
            'alternativa_material_omitida': '', 'siguiente_comprobacion_util': None,
            'tareas_calculables_trasladadas_al_dueno': [], 'falsas_alarmas': [],
            'fidelidad_calculo_relato': None,
            'rubrica_39': {c: None for c in RUBRIC},
            'render': {'errores_js': None, 'tablas_vacias': None, 'etiquetas_indistinguibles': None, 'movil': None},
            'notas': ''} for i in items}}
    write(folder / 'plantilla.json', template)
    (folder / 'INSTRUCCIONES.md').write_text(TECHNICAL.format(count=len(items)), encoding='utf-8')


def signals(folder, items):
    folder.mkdir(parents=True)
    write(folder / 'plantilla.json', {'evaluador': 'Opus', 'nota': 'Detección frente al oráculo; se rellena sin abrir kit-key.json.',
                                      'informes': {f"{i['dataset']}-{i['code']}": {} for i in items}})


TECHNICAL = '''# Evaluación técnica a ciegas

Hay {count} informes en `informes/`, con códigos aleatorios, en HTML y en texto.
Se ha quitado la marca y todos usan la misma tipografía y escala de grises; la
estructura y la redacción aún pueden delatar el sistema: no intentes deducirlo.
Puntúa primero el contenido con `informes/`. Solo después, para la parte de
render, abre `render/`, que conserva el diseño original de cada informe.

## Reglas de ceguera

- No abras nada fuera de esta carpeta `tecnica/`: ni los lotes de ensayo, ni
  las claves `kit-key-*.json`, ni registros, resúmenes ni puntuaciones automáticas.
- No abras oráculos ni el generador de datos. No uses lo que veas aquí sobre las
  señales de Albor para ajustar implementaciones: Albor es de desarrollo y el
  acuerdo es no adaptar el producto a sus señales.
- Calcula cualquier cifra desde `entradas/<conjunto>/datos/*.csv`. El encargo
  exacto del propietario está en `entradas/<conjunto>/prompt.txt`.

## Qué puntuar (en `plantilla.json`, guardado como `evaluacion-astra.json`)

- **cifras:** cuántas cifras comprobaste y cuáles son erróneas (cita, valor
  correcto y cálculo).
- **prioridad_principal:** qué pide revisar primero el informe.
- **prioridad_justificada_frente_alternativa:** 0/1/2. ¿Justifica la prioridad
  frente a una alternativa material de esos datos? No premies reproducir un
  ranking por volumen.
- **alternativa_material_omitida:** la que tú consideres material y no se discute.
- **siguiente_comprobacion_util:** 0/1/2. ¿El dueño podría hacerla y distinguir
  resultados que cambien su siguiente paso?
- **tareas_calculables_trasladadas_al_dueno:** pendientes que ya eran calculables.
- **falsas_alarmas:** afirmaciones o prioridades que los datos no sostienen.
- **fidelidad_calculo_relato:** 0/1/2. ¿Coinciden rankings y cifras narradas con
  lo calculado?
- **rubrica_39:** los doce criterios 0/1/2 de la evaluación 3.9.
- **render:** errores de JavaScript, tablas vacías, etiquetas indistinguibles y
  lectura en móvil (390 px), si puedes comprobarlo en navegador.
'''

READER = r'''<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Evaluación de informes</title>
<style>
:root{--bg:#f7f6f2;--panel:#fff;--ink:#1d2a26;--muted:#5f6d68;--line:#e2e4dd;--accent:#2f6f57;--warn:#9a5b16}
@media (prefers-color-scheme:dark){:root{--bg:#141816;--panel:#1d2320;--ink:#e8ece9;--muted:#9aa6a1;--line:#2f3833;--accent:#7cc4a3;--warn:#e0a35a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
header{padding:20px 24px;border-bottom:1px solid var(--line)}h1{margin:0 0 4px;font-size:22px}header p{margin:0;color:var(--muted);max-width:900px}
.layout{display:grid;grid-template-columns:260px 1fr;min-height:calc(100vh - 90px)}
nav{border-right:1px solid var(--line);padding:16px;overflow:auto}nav h2{font-size:13px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:18px 0 8px}
nav button{display:flex;justify-content:space-between;width:100%;text-align:left;border:1px solid var(--line);background:var(--panel);color:var(--ink);border-radius:8px;padding:8px 10px;margin:0 0 6px;cursor:pointer;font:inherit}
nav button[aria-current=true]{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent)}nav .done{color:var(--accent)}
main{padding:16px 24px 48px;min-width:0}iframe{width:100%;height:72vh;border:1px solid var(--line);border-radius:10px;background:#fff}
form{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:16px 18px;margin-top:16px}
label{display:block;font-weight:600;margin:14px 0 6px}textarea{width:100%;min-height:70px;font:inherit;padding:8px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--ink)}
.scale{display:flex;gap:8px;flex-wrap:wrap}.scale label{font-weight:400;margin:0;display:flex;gap:4px;align-items:center}
.hint{color:var(--muted);font-size:14px;margin:2px 0 0}.row{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-top:16px}
.primary{background:var(--accent);color:#fff;border:0;border-radius:8px;padding:10px 16px;font:inherit;cursor:pointer}
.secondary{background:transparent;color:var(--ink);border:1px solid var(--line);border-radius:8px;padding:10px 16px;font:inherit;cursor:pointer}
.saved{color:var(--accent)}.warn{color:var(--warn)}select{font:inherit;padding:6px;border-radius:6px}
@media (max-width:760px){.layout{grid-template-columns:1fr}nav{border-right:0;border-bottom:1px solid var(--line)}iframe{height:65vh}}
</style></head><body>
<header><h1>Evaluación de informes</h1>
<p>Lee cada informe como si fueras el dueño del negocio y responde con tus palabras. No sabes qué sistema escribió cada uno, y no hace falta que lo adivines. Tus respuestas se guardan en este navegador; cuando termines, pulsa «Descargar respuestas».</p>
<div class="row"><button class="secondary" type="button" onclick="download()">Descargar respuestas</button></div></header>
<div class="layout"><nav id="nav"></nav><main id="main"></main></div>
<script>
const DATA=__DATA__, KIT="__KIT__", KEY="evaluacion-informes-"+KIT;
const decode=b=>new TextDecoder().decode(Uint8Array.from(atob(b),c=>c.charCodeAt(0)));
let state={answers:{},rankings:{},started:{}};
try{const saved=localStorage.getItem(KEY);if(saved)state=JSON.parse(saved)}catch(e){}
const esc=t=>String(t||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const save=()=>{try{localStorage.setItem(KEY,JSON.stringify(state))}catch(e){}};
const datasets=[...new Set(DATA.map(d=>d.dataset))];
let current=null;
const done=c=>{const a=state.answers[c];return a&&a.primero&&a.comprobar&&a.entendido&&a.confianza};
function nav(){const n=document.getElementById('nav');n.innerHTML='';
 datasets.forEach(ds=>{const items=DATA.filter(d=>d.dataset===ds);const h=document.createElement('h2');h.textContent=items[0].label;n.appendChild(h);
  items.forEach((d,i)=>{const b=document.createElement('button');b.setAttribute('aria-current',current===d.code);
   b.innerHTML=`<span>Informe ${i+1}</span><span class="${done(d.code)?'done':''}">${done(d.code)?'✓':''}</span>`;b.onclick=()=>show(d.code);n.appendChild(b)});
  const r=document.createElement('button');r.setAttribute('aria-current',current==='rank-'+ds);r.innerHTML='<span>Comparar y ordenar</span>';r.onclick=()=>rank(ds);n.appendChild(r)});}
function scale(name,value,low,high){return `<div class="scale">${[1,2,3,4,5].map(v=>`<label><input type="radio" name="${name}" value="${v}" ${value==v?'checked':''}>${v}</label>`).join('')}</div><p class="hint">1 = ${low} · 5 = ${high}</p>`}
function show(code){current=code;nav();const d=DATA.find(x=>x.code===code);const a=state.answers[code]||{};
 if(!state.started[code]){state.started[code]=new Date().toISOString();save()}
 const idx=DATA.filter(x=>x.dataset===d.dataset).indexOf(d)+1;
 const m=document.getElementById('main');m.innerHTML=`<h2>${d.label} · Informe ${idx}</h2><iframe sandbox="allow-scripts" title="Informe ${idx}"></iframe>
 <form id="f"><label>1. Después de leerlo, ¿qué harías primero en tu negocio?</label><textarea name="primero">${esc(a.primero)}</textarea>
 <label>2. ¿Qué comprobarías y dónde? (qué registro, con quién, qué fechas)</label><textarea name="comprobar">${esc(a.comprobar)}</textarea>
 <label>3. ¿Lo has entendido sin ayuda?</label>${scale('entendido',a.entendido,'nada','perfectamente')}
 <label>4. ¿Te fiarías de él para tomar esa decisión?</label>${scale('confianza',a.confianza,'nada','totalmente')}
 <label>5. ¿Qué te ha sobrado, confundido o parecido demasiado técnico?</label><textarea name="confuso">${esc(a.confuso)}</textarea>
 <div class="row"><button class="primary" type="submit">Guardar</button><span id="msg"></span></div></form>`;
 m.querySelector('iframe').srcdoc=decode(d.html);
 m.querySelector('#f').onsubmit=e=>{e.preventDefault();const f=new FormData(e.target);
  state.answers[code]={primero:f.get('primero'),comprobar:f.get('comprobar'),entendido:f.get('entendido'),confianza:f.get('confianza'),confuso:f.get('confuso'),saved_at:new Date().toISOString()};
  save();nav();const ok=done(code);document.getElementById('msg').innerHTML=ok?'<span class="saved">Guardado.</span>':'<span class="warn">Guardado, pero faltan respuestas 1–4.</span>'};
 window.scrollTo(0,0)}
function rank(ds){current='rank-'+ds;nav();const items=DATA.filter(d=>d.dataset===ds);const saved=state.rankings[ds]||{};const n=items.length;
 const m=document.getElementById('main');m.innerHTML=`<h2>${items[0].label} · Comparar</h2><p>Ordena los informes del más útil (1) al menos útil (${n}) para decidir qué hacer en el negocio.</p>
 <form id="r">${items.map((d,i)=>`<label>Informe ${i+1}</label><select name="${d.code}"><option value=""></option>${items.map((_,j)=>`<option ${saved.order&&saved.order[d.code]==j+1?'selected':''}>${j+1}</option>`).join('')}</select>`).join('')}
 <label>¿Por qué el primero es el más útil?</label><textarea name="motivo">${esc(saved.motivo)}</textarea>
 <div class="row"><button class="primary" type="submit">Guardar orden</button><span id="msg"></span></div></form>`;
 m.querySelector('#r').onsubmit=e=>{e.preventDefault();const f=new FormData(e.target);const order={};items.forEach(d=>order[d.code]=Number(f.get(d.code))||null);
  const vals=Object.values(order).filter(Boolean);const unique=new Set(vals).size===vals.length;
  state.rankings[ds]={order,motivo:f.get('motivo'),saved_at:new Date().toISOString()};save();
  document.getElementById('msg').innerHTML=unique?'<span class="saved">Guardado.</span>':'<span class="warn">Hay posiciones repetidas.</span>'};
}
function download(){const blob=new Blob([JSON.stringify({evaluador:'propietario',kit:KIT,exportado:new Date().toISOString(),...state},null,2)],{type:'application/json'});
 const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='evaluacion-lector.json';a.click()}
nav();show(DATA[0].code);
</script></body></html>
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('batch', type=Path)
    parser.add_argument('out', type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.batch, args.out)))


if __name__ == '__main__':
    main()
