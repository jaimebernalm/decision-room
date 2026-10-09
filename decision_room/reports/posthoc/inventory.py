"""Rendered occurrence inventory: Unicode code-point offsets, plus DOM UTF-16 spans.

Inline tags never insert separators. Block boundaries do. Values are not parsed or
classified as business claims here, so omissions cannot silently shrink an audit.
"""
import hashlib
import json
from pathlib import Path
import re
import time

from .browser import Browser

VERSION = 'posthoc-inventory-v1'
MAX_BYTES = 8 * 1024 * 1024
# Store DOM text rather than HTML source: entities and inline nodes are resolved.
DOM_SCRIPT = r'''(() => {
 const out=[]; let count=0; const headings=[];
 const nodePath=n=>{const p=[]; while(n!==document.body){if(!n.parentNode)return null;
   p.unshift(Array.from(n.parentNode.childNodes).indexOf(n));n=n.parentNode;}return p;};
 function context(n) {
   const cell=n.parentElement.closest('td,th'), table=cell?.closest('table');
   let tab=null;
   if(table){
     const rows=Array.from(table.rows), grid=[]; let target=null;
     rows.forEach((r,y)=>{grid[y]??=[];let x=0;Array.from(r.cells).forEach(c=>{
       while(grid[y][x])x++;if(c===cell)target=[y,x];
       for(let a=0;a<c.rowSpan;a++){grid[y+a]??=[];for(let b=0;b<c.colSpan;b++)grid[y+a][x+b]=c;}
       x+=c.colSpan;});});
     const refs=a=>Array.from(new Set(a.filter(Boolean))).filter(c=>c!==cell).map(nodePath);
     const [y,x]=target||[-1,-1];
     tab={caption:table.caption?[nodePath(table.caption)]:[],
       column_headers:refs(grid.slice(0,Math.max(0,y)).map(r=>r[x]).filter(c=>c?.tagName==='TH'||rows[0]?.contains(c))),
       row_headers:refs((grid[y]||[]).slice(0,Math.max(0,x)).filter((c,i)=>c?.tagName==='TH'||i===0)),
       unresolved:!target};
   }
   return {section:headings.filter(Boolean).map(nodePath),table:tab};
 }
 function walk(n, path) {
  if (++count > 100000) throw new Error('DOM bound');
  if (n.nodeType===3) {
   const r=document.createRange(); r.selectNodeContents(n);
   if (r.getClientRects().length && n.nodeValue) out.push({path,text:n.nodeValue,
     preserve:/^(pre|pre-wrap|break-spaces)$/.test(getComputedStyle(n.parentElement).whiteSpace),
     region:n.parentElement.closest('svg,canvas')?'chart':'text',context:context(n)});
   return;
  }
  if(n.nodeType!==1) return;
  if(/^(SCRIPT|STYLE|NOSCRIPT|TEMPLATE)$/.test(n.tagName) || n.hidden) return;
  const s=getComputedStyle(n);
  if(s.display==='none' || s.visibility==='hidden' || s.visibility==='collapse' || s.opacity==='0') return;
  if(/^H[1-6]$/.test(n.tagName)){const level=Number(n.tagName[1]); headings.length=level;headings[level-1]=n;}
  const block=/^(block|list-item|table|table-row|flex|grid|flow-root)$/.test(s.display);
  if(block || n.tagName==='BR') out.push({separator:'\n'});
  if(n.tagName==='TD' || n.tagName==='TH') out.push({separator:'\t'});
  Array.from(n.childNodes).forEach((c,i)=>walk(c,path.concat(i)));
  if(block) out.push({separator:'\n'});
 }
 if(!document.body) throw new Error('Missing body');
 walk(document.body,[]);
 return {nodes:out, charts:Array.from(document.querySelectorAll('canvas,svg')).map(e=>({
  tag:e.tagName, width:e.getBoundingClientRect().width,height:e.getBoundingClientRect().height}))};
})()'''

TOKEN = re.compile(
    r'\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?)?'
    r'|[+\-−]?\d+(?:[.,]\d+)*(?:[ \u00a0\u202f\u2009]\d{3}(?!\d))*(?:,\d+)?'
    r'(?:[ \t\u00a0\u202f\u2009]*(?:%|millones\b|mil\b|k\b|M\b))?')


def sha(value):
    return hashlib.sha256(value).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def from_snapshot(source, snapshot):
    """Pure inventory from a captured DOM; useful for deterministic adversarial tests."""
    if not isinstance(source, bytes) or len(source) > MAX_BYTES:
        raise ValueError('Report must be bounded bytes.')
    chars, locations = [], []
    def add(char, location):
        if char in ' \t\n' and chars and chars[-1] in ' \t\n':
            if char == '\n': chars[-1] = '\n'; locations[-1] = None
            return
        chars.append(char); locations.append(location)
    for node in snapshot['nodes']:
        if 'separator' in node:
            add(node['separator'], None); continue
        offset = 0
        for char in node['text']:
            end = offset + (2 if ord(char) > 0xffff else 1)
            if char in '\r\n\t ' and not node.get('preserve'):
                add(' ', (node['path'], offset, end))
            else:
                chars.append(char); locations.append((node['path'], offset, end))
            offset = end
    left = 0
    while left < len(chars) and chars[left] in ' \t\n': left += 1
    right = len(chars)
    while right > left and chars[right-1] in ' \t\n': right -= 1
    text = ''.join(chars[left:right]); locations = locations[left:right]
    if len(text) > 1_000_000:
        raise ValueError('Visible report exceeds the text bound.')
    source_hash, text_hash = sha(source), sha(text.encode())
    bounds = {}; metadata = {}
    for node in snapshot['nodes']:
        if 'path' in node: metadata[tuple(node['path'])] = node
    for i, location in enumerate(locations):
        if location is None: continue
        path = tuple(location[0])
        for size in range(len(path)+1):
            key=path[:size]
            if key not in bounds: bounds[key]=[i,i+1]
            else: bounds[key][1]=i+1
    def references(paths):
        result=[]
        for path in paths:
            if tuple(path) not in bounds: continue
            a,b=bounds[tuple(path)]
            while a<b and text[a].isspace(): a+=1
            while b>a and text[b-1].isspace(): b-=1
            if a<b: result.append({'text':text[a:b], 'span':[a,b]})
        return result
    occurrences = []
    for match in TOKEN.finditer(text):
        start, end = match.span()
        if text[start] in '-−+' and start and (text[start-1].isalnum() or text[start-1] in '_'):
            start += 1  # Identifier/range separator is not a numeric sign.
        parts = []
        for location in locations[start:end]:
            if location is None: continue
            path, a, b = location
            if parts and parts[-1]['path'] == path and parts[-1]['span'][1] == a:
                parts[-1]['span'][1] = b
            else:
                parts.append({'path': path, 'span': [a,b]})
        literal = text[start:end]
        meta=metadata.get(tuple(parts[0]['path']),{}) if parts else {}
        raw_context=meta.get('context',{})
        table=raw_context.get('table')
        context={'section':references(raw_context.get('section',[])), 'table':None}
        if table is not None:
            context['table']={k:references(table.get(k,[])) for k in ('caption','column_headers','row_headers')}
            context['table']['unresolved']=table.get('unresolved',False)
        identifier = sha(canonical([VERSION,source_hash,text_hash,start,end,literal]))[:24]
        occurrences.append({'id': identifier, 'span': [start,end], 'text': literal,
                            'kind': 'date' if re.match(r'^\d{4}-\d{2}-\d{2}',literal) else 'number',
                            'parts': parts, 'region':meta.get('region','text'), 'context':context})
    return {'version':VERSION,'source_sha256':source_hash,'text_sha256':text_hash,
            'snapshot_sha256':sha(canonical(snapshot)), 'text':text,
            'occurrences':occurrences, 'charts':snapshot.get('charts',[])}


def build_inventory(html, *, browser_factory=Browser):
    """Capture a stable rendered document. No model calls; source is read only."""
    path = Path(html)
    source = path.read_bytes()
    if len(source) > MAX_BYTES: raise ValueError('HTML exceeds the byte bound.')
    with browser_factory() as browser:
        session = browser.open(path)
        prior = browser.evaluate(DOM_SCRIPT,session)
        deadline = time.monotonic()+10
        while True:
            time.sleep(.25)
            current = browser.evaluate(DOM_SCRIPT,session)
            if current == prior: break
            if time.monotonic() > deadline: raise ValueError('Rendered text does not stabilize.')
            prior = current
    if path.read_bytes() != source: raise ValueError('Report changed during inventory.')
    result = from_snapshot(source,current)
    result['snapshot'] = current
    return result


def validate(inventory):
    if inventory['version'] != VERSION or sha(inventory['text'].encode()) != inventory['text_sha256']:
        raise ValueError('Inventory identity mismatch.')
    ids = set(); last = 0
    for entry in inventory['occurrences']:
        a,b = entry['span']
        expected = sha(canonical([VERSION,inventory['source_sha256'],inventory['text_sha256'],a,b,entry['text']]))[:24]
        if entry['id'] != expected or entry['id'] in ids or not last <= a < b <= len(inventory['text']):
            raise ValueError('Invalid occurrence identity or span.')
        if inventory['text'][a:b] != entry['text']:
            raise ValueError('Occurrence text mismatch.')
        ids.add(entry['id']); last=b
    return inventory
