"""Offline presentation experiment. Never imported by the live report exporter.

Render frozen verified documents without recertifying any occurrence. The original
ledger stays authoritative; the separate map locates its occurrences in this HTML.
"""
import argparse
from collections import defaultdict
from copy import deepcopy
from decimal import Decimal
from hashlib import sha256
from html import escape
from html.parser import HTMLParser
import json
from pathlib import Path
import re

from . import contract, charts
from .verification_contract import canonical, validate
from ..web.report_projection import _graphic

VERSION = 'presentation-r0-v1'
TOKEN = re.compile(r'\{\{n:[^{}]+\}\}')
LABELS = {'verified': 'Verificada', 'unverified': 'No verificada',
          'uncertain': 'Incierta', 'corrected': 'Corregida'}


def spanish(value):
    """Format an already displayed decimal, preserving its precision and value."""
    if not re.fullmatch(r'-?\d+(?:\.\d+)?', value):
        return value
    integer, dot, fraction = value.partition('.')
    sign = '-' if integer.startswith('-') else ''
    digits = integer.lstrip('-')
    groups = []
    while digits:
        groups.insert(0, digits[-3:]); digits = digits[:-3]
    return sign + '\u202f'.join(groups) + (',' + fraction if dot else '')


def display_field(source, figures, *, label=False):
    output, cursor, destinations, edits = '', 0, [], []
    for figure in sorted(figures, key=lambda f: f['span']['start']):
        start, end = figure['span']['start'], figure['span']['end']
        output += source[cursor:start]
        original = source[start:end]; shown = original; kind = None
        if figure['value'] is None and TOKEN.fullmatch(original):
            shown, kind = 'No disponible', 'unresolved_reference'
        elif figure['value'] is not None and figure['unit'] and re.fullmatch(r'-?\d+(?:\.\d+)?', original):
            # Do not format a figure whose text and declared value disagree.
            if Decimal(original) == Decimal(figure['value']):
                shown = spanish(original)
                if shown != original: kind = 'decimal_locale'
        destination = {'start': len(output), 'end': len(output)+len(shown)}
        destinations.append({'id': figure['id'], 'source_span': figure['span'],
                             'span': destination, 'text': shown})
        if kind:
            edits.append({'kind': kind, 'source_span': figure['span'],
                          'original': original, 'visible': shown})
        output += shown; cursor = end
    output += source[cursor:]
    if label:
        # Only an explicit complete chart label "CODE — name" is rearranged.
        match = re.fullmatch(r'(P[0-9]{2}|[A-Z]{2})\s*[—–]\s*(.+)', output)
        if match:
            code, name = match.group(1), match.group(2)
            pieces = [(match.start(2), match.end(2), 0), (0, len(code), len(name)+2)]
            moved = []
            for occurrence in destinations:
                start, end = occurrence['span']['start'], occurrence['span']['end']
                part = next((p for p in pieces if p[0] <= start < end <= p[1]), None)
                if part is None: break
                moved.append({**occurrence, 'span': {'start': part[2]+start-part[0], 'end': part[2]+end-part[0]}})
            else:
                output = name+' ('+code+')'
                destinations = sorted(moved, key=lambda o:o['span']['start'])
                edits.append({'kind':'explicit_label_order', 'source_span':{'start':0,'end':len(source)},
                              'original':source, 'visible':output})
    return output, destinations, edits


def render(document, ledger, raw):
    """Return HTML and a complete source/occurrence map; input objects are unchanged."""
    validate(ledger, document, raw)
    by_path = defaultdict(list)
    for f in ledger['figures']: by_path[f['path']].append(f)
    fields = {}; ordered = list(contract.texts(document))
    for i, (path, value, recommendation) in enumerate(ordered):
        shown, occurrences, edits = display_field(value, by_path[path], label=path.startswith('/charts/') and path.endswith('/label'))
        fields[path] = {'source_text': value, 'text': shown, 'recommendation_id': recommendation,
                        'anchor': f'e{i+1:03d}', 'occurrences': occurrences, 'edits': edits,
                        'destinations': []}
    mapping = {'version': VERSION, 'source_document_sha256': sha256(canonical(document)).hexdigest(),
               'source_ledger_sha256': sha256(canonical(ledger)).hexdigest(),
               'source_raw_sha256': sha256(raw).hexdigest(),
               'priority_order': [f['key'] for f in document['findings']],
               'figures': deepcopy(ledger['figures']), 'fields': fields}
    fact_paths = {path+'/text' for path, _, _ in contract.fact_entries(document)}
    def block(path, location, *, marked=True, excerpt=False):
        field = fields[path]; value = field['text']
        if excerpt:
            # A preview only; complete original scope and limitations remain in the appendix.
            stop = value.find('. ')
            value = value[:stop+1] if stop >= 0 else value
        ident = location + '-' + field['anchor']
        content = ''; end = 0; occurrences = []
        for item in field['occurrences']:
            a, b = item['span']['start'], item['span']['end']
            if b > len(value): continue
            occurrences.append({'id': item['id'], 'span': item['span']})
            if marked:
                figure = next(f for f in by_path[path] if f['id'] == item['id'])
                status = figure['status']; label = LABELS[status]
                if status == 'corrected': label += '; ' + ('verificada en su ámbito' if figure['verified'] else 'ámbito no verificado')
                content += escape(value[end:a]) + f'<span class="state {status}" data-figure="{figure['id']}" data-status="{status}" data-verified="{str(figure['verified']).lower()}" tabindex="0" title="{escape(label)}" aria-label="{escape(value[a:b]+": "+label)}">{escape(value[a:b])}</span>'
                end = b
        content += escape(value[end:])
        field['destinations'].append({'id': ident, 'text': value, 'full': not excerpt, 'occurrences': occurrences})
        return f'<span id="{ident}" data-text="true">{content}</span>'
    def ref(path):
        if path not in fact_paths: return ''
        return f'<a class="ref" href="#annex-{fields[path]["anchor"]}" aria-label="Ver evidencia y estado">[{fields[path]["anchor"].upper()}]</a>'
    def p(path, cls=''):
        if not fields[path]['text']: return ''
        return f'<p class="{cls}">'+block(path, 'body')+' '+ref(path)+'</p>'
    projected_charts = charts.project(document.get('charts', []), ledger['figures'])
    def chart(i):
        c = projected_charts[i]; base = f'/charts/{i}'
        graphic, issue = _graphic(c)
        parts = ['<section class="chart"><h3>'+block(base+'/title','body')+' '+ref(base+'/title')+'</h3>', p(base+'/caption')]
        if graphic: parts.append(graphic)
        if issue: parts.append('<p class="note">'+escape(issue)+'</p>')
        parts.append('<div class="table-wrap"><table><thead><tr><th>Serie</th><th>Elemento</th><th>Valor</th></tr></thead><tbody>')
        for j, series in enumerate(c['series']):
            for k, point in enumerate(series['points']):
                # A label used for multiple points has separate destination IDs.
                parts.append('<tr>')
                for path in (f'{base}/series/{j}/label', f'{base}/series/{j}/points/{k}/label', f'{base}/series/{j}/points/{k}/value_text'):
                    parts.append('<td>'+block(path,f'chart-{i}-{j}-{k}')+' '+ref(path)+'</td>')
                parts.append('</tr>')
        parts.append('</tbody></table></div></section>')
        return ''.join(parts)
    parts = ['<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
             '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'">',
             '<title>Informe</title><style>'+CSS+'</style></head><body><main>',
             '<header><div class="eyebrow">Informe · lectura y comprobaciones</div><h1>'+block('/title','body')+'</h1>',
             p('/summary','summary'), p('/scope','scope'), '</header>']
    parts.append('<div class="legend note" aria-label="Estado de las cifras">'+''.join(f'<span class="state {status}">{label}</span>' for status,label in LABELS.items())+'</div>')
    if document['findings']:
        parts.append('<nav aria-label="Contenido"><span class="eyebrow">En este informe</span><ol>')
        for i, f in enumerate(document['findings']):
            parts.append(f'<li><a href="#finding-{i}">'+escape(f['title'] or 'Lectura '+str(i+1))+'</a></li>')
        parts.append('</ol></nav>')
    for i, finding in enumerate(document['findings']):
        base = f'/findings/{i}'
        parts.append(f'<section class="finding" id="finding-{i}"><h2>'+block(base+'/title','body')+'</h2>')
        parts.append(p(base+'/statement','statement'))
        parts.append(p(base+'/scope','scope'))
        parts.append(p(base+'/interpretation'))
        if finding['next_step']:
            parts.append('<div class="action"><h3>Qué comprobar</h3>'+p(base+'/next_step')+'</div>')
        facts = [path+'/text' for path, fact, rec in contract.fact_entries(document) if rec == finding['key']]
        if facts:
            parts.append('<div class="support"><h3>Cifras de soporte</h3><p class="note">El alcance completo y el estado de cada cifra están en el anexo.</p><ul>')
            for path in facts:
                parts.append('<li>'+block(path,'preview',marked=False,excerpt=True)+' '+ref(path)+'</li>')
            parts.append('</ul></div>')
        for j,c in enumerate(projected_charts):
            if c['recommendation_id'] == finding['key']: parts.append(chart(j))
        parts.append('</section>')
    for i,c in enumerate(projected_charts):
        if c['recommendation_id'] is None: parts.append(chart(i))
    if document['limitations']: parts.append('<section class="limits"><h2>Alcance y límites</h2>'+p('/limitations')+'</section>')
    parts.append('<section class="appendix"><h2>Soporte completo</h2><p>El estado se muestra donde aparece cada cifra. Este anexo conserva el soporte completo de cada referencia, incluido su ámbito. Una cifra comprobada no certifica automáticamente la interpretación. Las referencias no disponibles no se han rellenado.</p><div class="legend">')
    for status,label in LABELS.items(): parts.append(f'<span class="state {status}">{label}</span>')
    parts.append('</div><p class="note">Las correcciones conservan su condición de verificación: el detalle de cada marca distingue si su ámbito está verificado.</p>')
    figures_by_id = {f['id']: f for f in ledger['figures']}
    for path,field in fields.items():
        if not field['text'] or path not in fact_paths: continue
        parts.append(f'<article id="evidence-{field["anchor"]}"><h3>{field["anchor"].upper()} · '+escape(field_label(path, document))+'</h3><p>'+block(path,'annex',marked=True)+'</p>')
        # Correction scope is explicit in static screenshots too, not only a tooltip.
        corrections = [figures_by_id[o['id']] for o in field['occurrences'] if figures_by_id[o['id']]['status']=='corrected']
        for f in corrections:
            parts.append('<p class="note">Corrección: '+escape(f['text'])+'; '+('ámbito verificado' if f['verified'] else 'ámbito no verificado')+'. Valor anterior: '+escape(f['corrected_from'])+'.</p>')
        parts.append('</article>')
    for f in ledger['figures']:
        if f['status'] == 'corrected' and f['path'] not in fact_paths:
            parts.append('<p class="note">Corrección en '+escape(field_label(f['path'], document))+': '+escape(f['text'])+'; '+('ámbito verificado' if f['verified'] else 'ámbito no verificado')+'. Valor anterior: '+escape(f['corrected_from'])+'.</p>')
    parts.append('</section></main></body></html>')
    html = ''.join(parts)
    check_invariants(document, ledger, raw, html, mapping)
    return html, mapping


def field_label(path, document):
    names = {'title':'Título', 'summary':'Conclusión', 'scope':'Ámbito', 'limitations':'Límites',
             'statement':'Hallazgo', 'interpretation':'Lectura', 'next_step':'Comprobación siguiente',
             'text':'Soporte completo', 'caption':'Lectura del gráfico', 'label':'Etiqueta', 'value_text':'Valor'}
    if path.startswith('/findings/'):
        index = int(path.split('/')[2]); prefix = document['findings'][index]['title'] or f'Lectura {index+1}'
    elif path.startswith('/charts/'): prefix = document['charts'][int(path.split('/')[2])]['title']
    else: prefix = 'Informe'
    return prefix+' · '+names.get(path.rsplit('/',1)[-1], 'Evidencia')


class TextIndex(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True); self.depth=0; self.active=None; self.texts={}; self.ids=set(); self.links=[]; self.states={}; self.marked_destinations=defaultdict(list); self.mark_spans=defaultdict(list); self.open_mark=None; self.findings=[]
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if tag=='section' and re.fullmatch(r'finding-\d+',attrs.get('id','')): self.findings.append(attrs['id'])
        if 'data-figure' in attrs:
            key=attrs['data-figure']
            self.states.setdefault(key, []).append((attrs.get('data-status'),attrs.get('data-verified')))
            self.marked_destinations[self.active].append(key)
            self.open_mark=(self.active, key, len(self.texts.get(self.active,'')), self.depth+1)
        if 'id' in attrs:
            if attrs['id'] in self.ids: raise ValueError('Duplicate HTML destination.')
            self.ids.add(attrs['id'])
        if tag=='a' and attrs.get('href','').startswith('#'): self.links.append(attrs['href'][1:])
        if attrs.get('data-text')=='true':
            if self.active: raise ValueError('Nested source destinations.')
            self.active=attrs['id']; self.depth=0; self.texts[self.active]=''
        if self.active: self.depth+=1
    def handle_endtag(self, tag):
        if self.active:
            if self.open_mark and self.depth == self.open_mark[3]:
                dest,key,start,_=self.open_mark
                self.mark_spans[dest].append({'id':key,'span':{'start':start,'end':len(self.texts[dest])}})
                self.open_mark=None
            self.depth-=1
            if self.depth==0: self.active=None
    def handle_data(self, data):
        if self.active: self.texts[self.active]+=data


def check_invariants(document, ledger, raw, html, mapping):
    validate(ledger, document, raw)
    if mapping['source_document_sha256'] != sha256(canonical(document)).hexdigest() or mapping['source_ledger_sha256'] != sha256(canonical(ledger)).hexdigest() or mapping['source_raw_sha256'] != sha256(raw).hexdigest():
        raise ValueError('Source identity changed.')
    if mapping['figures'] != ledger['figures'] or mapping['priority_order'] != [f['key'] for f in document['findings']]:
        raise ValueError('Figure states, scopes or priorities changed.')
    index=TextIndex(); index.feed(html)
    if index.findings != [f'finding-{i}' for i in range(len(document['findings']))]:
        raise ValueError('Visible finding order changed.')
    if any(link not in index.ids for link in index.links): raise ValueError('Broken evidence link.')
    by_path=defaultdict(list)
    for figure in ledger['figures']: by_path[figure['path']].append(figure)
    expected_states = {f['id']:(f['status'],str(f['verified']).lower()) for f in ledger['figures']}
    if set(index.states) != set(expected_states) or any(any(state != expected_states[key] for state in states) for key, states in index.states.items()):
        raise ValueError('Missing or changed visible figure state.')
    fact_paths = {path+'/text' for path, _, _ in contract.fact_entries(document)}
    expected={path:value for path,value,_ in contract.texts(document)}
    if set(expected)!=set(mapping['fields']): raise ValueError('Missing source field.')
    for path,source in expected.items():
        field=mapping['fields'][path]; shown,occurrences,edits=display_field(source,by_path[path], label=path.startswith('/charts/') and path.endswith('/label'))
        if (field['source_text'],field['text'],field['occurrences'],field['edits']) != (source,shown,occurrences,edits):
            raise ValueError('Unsupported text or scope transformation.')
        if shown and not any(d['full'] and (d['id'].startswith('annex-') == (path in fact_paths)) for d in field['destinations']):
            raise ValueError('Full evidence is not accessible.')
        for d in field['destinations']:
            if d['full'] and (index.marked_destinations[d['id']] != [o['id'] for o in d['occurrences']] or index.mark_spans[d['id']] != d['occurrences']):
                raise ValueError('State is not attached to its visible occurrence.')
            expected_occurrences = [{'id':o['id'],'span':o['span']} for o in occurrences if o['span']['end'] <= len(d['text'])]
            if d['occurrences'] != expected_occurrences:
                raise ValueError('Incomplete occurrence map.')
            if index.texts.get(d['id']) != d['text'] or (d['full'] and d['text']!=shown) or not shown.startswith(d['text']):
                raise ValueError('Visible text differs from the mapped source.')
            for o in d['occurrences']:
                original=next(x for x in occurrences if x['id']==o['id'])
                if o['span']!=original['span'] or d['text'][o['span']['start']:o['span']['end']]!=original['text']:
                    raise ValueError('Visible occurrence mismatch.')
    return {'passed':True,'fields':len(expected),'figures':len(ledger['figures']),
            'source_identity':True,'states_and_evidence':True,'full_text_and_scopes':True,
            'priority_order':True,'destinations_and_offsets':True}


CSS = '''
:root{color-scheme:light}*{box-sizing:border-box}body{margin:0;background:#f6f5f1;color:#203338;font:17px/1.6 system-ui,sans-serif}main{max-width:1080px;margin:auto;padding:56px 64px;background:#fff}header{border-bottom:2px solid #235b5a;padding-bottom:24px}h1{font:600 38px/1.16 Georgia,serif;max-width:880px;letter-spacing:-.6px}h2{font:600 29px/1.25 Georgia,serif;margin:0 0 18px}h3{font-size:17px;margin:0 0 8px}p{white-space:pre-wrap;overflow-wrap:anywhere;margin:12px 0}.eyebrow{font-size:12px;text-transform:uppercase;letter-spacing:2px;color:#526967}.summary{font-size:21px;line-height:1.55}.scope,.note{font-size:14px;color:#53676d}.ref{font:11px system-ui;color:#426a70;text-decoration:none;white-space:nowrap}a{color:#235b5a}nav{padding:24px 0;border-bottom:1px solid #dce3e1}nav ol{padding-left:22px;columns:2;column-gap:32px}nav li{break-inside:avoid;margin:8px 0}nav a{text-decoration:none}.finding{padding:36px 0;border-bottom:1px solid #dce3e1}.statement{font-size:19px}.action{border-left:3px solid #235b5a;padding:12px 22px;margin:22px 0;background:#f1f6f4}.support{margin-top:24px}.support ul{list-style:none;padding:0;display:grid;grid-template-columns:1fr 1fr;gap:0 24px}.support li{font-size:14px;padding:10px 0;border-bottom:1px solid #e5e9e6;overflow-wrap:anywhere}.chart{margin:30px 0}.chart svg{width:100%;height:auto;display:block}.table-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:14px;font-variant-numeric:tabular-nums}th,td{padding:10px;border-bottom:1px solid #dce3e1;text-align:left;overflow-wrap:anywhere}td:last-child{text-align:right}th{background:#f1f6f4}.limits{padding:32px 0}.appendix{border-top:3px solid #235b5a;margin-top:32px;padding-top:32px}.appendix article{padding:14px 0;border-bottom:1px solid #e5e9e6;font-size:14px}.appendix h3{font-size:13px;color:#526967}.legend{display:flex;gap:22px;flex-wrap:wrap;margin:16px 0}.state.verified{background:#e0f1e9;border-bottom:2px solid #1f6b50}.state.unverified{border-bottom:1px dotted #52676e}.state.uncertain{background:#fff0cf;border-bottom:2px dashed #9b620d}.state.corrected{background:#eee5f7;border-bottom:2px double #70528c}.state:focus{outline:2px solid #235b5a}@media(max-width:700px){main{padding:28px 22px}h1{font-size:30px}nav ol{columns:1}.support ul{grid-template-columns:1fr}}@media print{body{background:white}main{padding:0;max-width:none}h2,h3{break-after:avoid}table,svg{break-inside:avoid}}
'''


def export(sources, out):
    """Sources map opaque job IDs to frozen engine export directories."""
    out=Path(out)
    if out.exists(): raise ValueError('Use a new output directory.')
    if not sources or any(not re.fullmatch(r'[A-Za-z0-9_-]+',name) for name in sources): raise ValueError('Invalid report IDs.')
    prepared=[]
    for name,folder in sources.items():
        folder=Path(folder)
        files={n:(folder/n).read_bytes() for n in ('draft.verified.json','verification.json','draft.raw','informe.html')}
        doc=json.loads(files['draft.verified.json']); ledger=json.loads(files['verification.json'])
        html,mapping=render(doc,ledger,files['draft.raw'])
        checks={**check_invariants(doc,ledger,files['draft.raw'],html,mapping), 'id':name, 'invariants_passed':True, 'map':name+'.map.json'}
        prepared.append((name,files,html,mapping,checks))
    out.mkdir(parents=True)
    manifest={'version':VERSION,'reports':{}}
    for name,files,html,mapping,checks in prepared:
        outputs={name+'.html':html.encode(),name+'.map.json':canonical(mapping),name+'.checks.json':canonical(checks)}
        for filename,data in outputs.items(): (out/filename).write_bytes(data)
        manifest['reports'][name]={'inputs':{n:sha256(b).hexdigest() for n,b in files.items()},
                                  'outputs':{n:sha256(b).hexdigest() for n,b in outputs.items()},'invariants':checks}
    (out/'manifest.json').write_bytes(canonical(manifest))
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sources',type=Path,help='Private JSON mapping report IDs to engine export directories')
    parser.add_argument('out',type=Path)
    args=parser.parse_args();export(json.loads(args.sources.read_text()),args.out)

if __name__=='__main__':main()
