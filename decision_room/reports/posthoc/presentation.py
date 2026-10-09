"""Add an occurrence layer without rewriting the source HTML or its charts."""
import base64
import json
from pathlib import Path
import time

from .browser import Browser
from .inventory import DOM_SCRIPT, canonical, sha, validate

VERSION='posthoc-presentation-v2'
MARK='data-posthoc-owned'
LABELS={'verified':'Verificada','discrepancy':'Discrepancia','not_checkable':'No comprobable','uncertain':'Incierta'}

INSTALL=r'''(() => {
 const p=PAYLOAD, stable=x=>JSON.stringify(x,(_,v)=>v && !Array.isArray(v) && typeof v==='object' ? Object.fromEntries(Object.keys(v).sort().map(k=>[k,v[k]])) : v);
 let tries=0;
 const get=path=>path.reduce((n,i)=>n?.childNodes[i],document.body);
 function install(){
  let snap;try{snap=SNAPSHOT;}catch(e){retry();return;}
  if(stable(snap)!==stable(p.snapshot)){retry();return;}
  const original=document.documentElement.outerHTML;
  const operations=[];
  for(const entry of p.occurrences){
   if(entry.region==='chart')continue;
   for(const part of entry.parts){const node=get(part.path);
    if(!node || node.nodeType!==3)throw new Error('Missing original node');
    operations.push({node,a:part.span[0],b:part.span[1],id:entry.id,status:p.ledger[entry.id].status});}
  }
  // Descending offsets prevent a preceding split from changing later node ranges.
  operations.sort((a,b)=>a.node===b.node?b.a-a.a:0);
  const nodes=new Map();operations.forEach(o=>{if(!nodes.has(o.node))nodes.set(o.node,[]);nodes.get(o.node).push(o);});
  for(const [node,parts] of nodes){
   parts.sort((a,b)=>b.a-a.a);
   for(const o of parts){const end=node.splitText(o.b), target=node.splitText(o.a);
    const mark=document.createElement('span');mark.setAttribute('data-posthoc-owned','mark');
    mark.setAttribute('data-posthoc-occurrence',o.id);mark.setAttribute('data-posthoc-status',o.status);
    mark.title=p.labels[o.status];mark.setAttribute('aria-label',target.nodeValue+' — '+p.labels[o.status]);
    mark.setAttribute('aria-describedby','posthoc-state-'+o.status);
    if(o.status==='verified' || o.status==='discrepancy'){
     mark.style.textDecorationLine='underline';mark.style.textDecorationStyle='dotted';
     mark.style.textDecorationColor=o.status==='discrepancy'?'#a62121':'#226b49';
    }
    if(o.status==='discrepancy'){
     mark.setAttribute('role','link');mark.tabIndex=0;mark.style.cursor='pointer';
     const jump=()=>document.getElementById('posthoc-check-'+o.id)?.scrollIntoView({block:'center'});
     mark.addEventListener('click',jump);mark.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();jump();}});
    }
    target.replaceWith(mark);mark.appendChild(target);
   }
  }
  const appendix=document.createElement('section');appendix.setAttribute('data-posthoc-owned','appendix');
  Object.assign(appendix.style,{boxSizing:'border-box',width:'calc(100% - 48px)',maxWidth:'960px',margin:'32px auto',
   padding:'24px',border:'1px solid #d5dbe3',borderRadius:'8px',background:'#f7f9fc',color:'#182438',
   font:window.getComputedStyle(document.querySelector('main,article')||document.body).font,lineHeight:'1.55'});
  const title=document.createElement('h2');title.textContent='Comprobación de cifras';appendix.appendChild(title);
  const counts={};Object.values(p.ledger).forEach(r=>counts[r.status]=(counts[r.status]||0)+1);
  const summary=document.createElement('p');summary.textContent=Object.entries(p.labels).map(([k,v])=>v+': '+(counts[k]||0)).join(' · ');appendix.appendChild(summary);
  const note=document.createElement('p');note.textContent='Las marcas describen la comprobación de cada cifra. No certifican la recomendación ni la interpretación que la rodea. El informe original se conserva íntegro. Los valores inventariados de los gráficos cuentan en los totales, aunque no llevan marcas sobre el gráfico.';appendix.appendChild(note);
  const meanings={verified:'Coincide con el recálculo del ámbito interpretado.',discrepancy:'No coincide con ese recálculo; abajo se muestran ambos valores.',
   uncertain:'No se ha podido fijar una interpretación suficientemente fundamentada.',not_checkable:'Queda fuera de las comprobaciones disponibles; no significa que sea incorrecta.'};
  const legend=document.createElement('dl');
  for(const [state,label] of Object.entries(p.labels)){const term=document.createElement('dt'),meaning=document.createElement('dd');
   term.id='posthoc-state-'+state;term.textContent=label;term.style.fontWeight='600';meaning.textContent=meanings[state];meaning.style.margin='0 0 8px';legend.append(term,meaning);}
  appendix.appendChild(legend);
  for(const entry of p.occurrences){const state=p.ledger[entry.id];if(state.status!=='discrepancy')continue;
   const row=document.createElement('p');row.id='posthoc-check-'+entry.id;
   row.textContent='Publicado: '+entry.text+'. Recalculado: '+state.recalculated.value+' '+state.recalculated.unit+'. '+p.descriptions[entry.id];appendix.appendChild(row);
  }
  document.body.appendChild(appendix);
  window.__posthoc={status:'applied',source_sha256:p.source_sha256};
 }
 function retry(){if(++tries>80){window.__posthoc={status:'failed',reason:'rendered_document_changed'};return;}setTimeout(install,250);}
 window.addEventListener('load',()=>setTimeout(install,1000),{once:true});
 if(document.readyState==='complete')setTimeout(install,1000);
})()'''


def describe(recipe):
    names={'sum':'suma','count':'recuento de filas','mean':'media por registro','min':'mínimo','max':'máximo',
           'daily_mean':'media por día natural','difference':'diferencia A menos B','percent_change':'variación porcentual (A−B)/B',
           'share':'cuota A/B','quotient':'cociente A/B','percentage_points':'diferencia en puntos porcentuales A/B−C/D'}
    parts=[names[recipe['operation']]+'.']
    for letter,operand in zip('ABCD',recipe['operands']):
        filters=[]
        for rule in operand['filters']:
            values=rule['values']
            if rule['operator']=='date_between':filters.append(rule['column']+' entre '+values[0]+' y '+values[1]+' inclusive')
            else:filters.append(rule['column']+' en {'+', '.join(values)+'}')
        parts.append(letter+': '+names[operand['aggregate']]+' de '+str(operand['column'] or 'filas')+
                     ', tabla '+operand['table_id']+', '+('; '.join(filters) or 'todas las filas')+'.')
    return ' '.join(parts)


def render(source,inventory,ledger):
    validate(inventory)
    if sha(source)!=inventory['source_sha256']:raise ValueError('Source bytes changed.')
    if MARK.encode() in source:raise ValueError('Source uses the reserved annotation namespace.')
    if set(ledger)!={o['id'] for o in inventory['occurrences']}:raise ValueError('Ledger must account for every occurrence.')
    if any(v['status'] not in LABELS for v in ledger.values()):raise ValueError('Unknown occurrence state.')
    if 'snapshot' not in inventory:raise ValueError('A rendered snapshot is required.')
    payload={'source_sha256':inventory['source_sha256'],'snapshot':inventory['snapshot'],
             'occurrences':inventory['occurrences'],'ledger':ledger,'labels':LABELS,
             'descriptions':{k:describe(v['recipe']) for k,v in ledger.items() if v['status']=='discrepancy'}}
    # Escaping '<' prevents source/report text from terminating the injected script.
    body=INSTALL.replace('PAYLOAD',canonical(payload).decode().replace('<','\\u003c')).replace('SNAPSHOT',DOM_SCRIPT)
    return source+b'<script data-posthoc-owned="installer">'+body.encode()+b'</script>'


CLEAN=r'''(() => {
 const copy=document.documentElement.cloneNode(true);
 for(const node of copy.querySelectorAll('[data-posthoc-owned="mark"]'))node.replaceWith(...node.childNodes);
 for(const node of copy.querySelectorAll('[data-posthoc-owned]'))node.remove();
 return copy.outerHTML;
})()'''


def chart_images(browser,session):
    shapes=browser.evaluate('Array.from(document.querySelectorAll("svg,canvas")).map(e=>{const r=e.getBoundingClientRect();return {x:r.x+scrollX,y:r.y+scrollY,width:r.width,height:r.height}})',session)
    result=[]
    for shape in shapes:
        if shape['width']<=0 or shape['height']<=0:continue
        image=browser.call('Page.captureScreenshot',{'format':'png','captureBeyondViewport':True,
                'clip':{**shape,'scale':1}},session)
        result.append(sha(base64.b64decode(image['data'])))
    return result


def check(original,derived,inventory,*,browser_factory=Browser):
    """Fail closed on a changed chart, text, DOM structure, or uninstalled layer."""
    expected_source=sha(Path(original).read_bytes())
    if expected_source!=inventory['source_sha256']:raise ValueError('Original changed before QA.')
    with browser_factory() as browser:
        first=browser.open(original);time.sleep(1.25)
        before=browser.evaluate(CLEAN,first);charts_before=chart_images(browser,first)
        second=browser.open(derived);deadline=time.monotonic()+25
        while True:
            state=browser.evaluate('window.__posthoc || {status:"waiting"}',second)
            if state['status']!='waiting':break
            if time.monotonic()>deadline:raise ValueError('Annotation layer did not install.')
            time.sleep(.1)
        if state['status']!='applied':raise ValueError('Annotation layer rejected changed rendered text.')
        after=browser.evaluate(CLEAN,second);charts_after=chart_images(browser,second)
        if before!=after:raise ValueError('Removing annotations did not recover the original DOM.')
        if charts_before!=charts_after:raise ValueError('Rendered charts changed.')
    return {'version':VERSION,'source_sha256':expected_source,'derived_sha256':sha(Path(derived).read_bytes()),
            'invariants_passed':True,'charts_compared':len(charts_before),
            'restored_dom_sha256':sha(before.encode())}
