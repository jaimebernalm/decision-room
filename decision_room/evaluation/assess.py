"""Independent rubric and numeric bindings. Model approval is never evaluator approval."""
from decimal import Decimal, InvalidOperation
from html import escape
import json
from pathlib import Path

def tolerance(key):
    return Decimal(0) if key in ('quantity','observed_days','missing_days') or key.endswith(('_days',':quantity')) else Decimal('.01')


RUBRIC=('definitions','scope_and_limitations','narrative_and_charts','usefulness','questions','all_presented_numbers_checked')


def token_accounting(calls, snapshot_complete=True):
    known = {'input': 0, 'output': 0}
    missing = {'input': 0, 'output': 0}
    for call in calls:
        usage = call.get('usage') or {}
        for side, standard, native in [('input', 'prompt_tokens', 'total_input_tokens'),
                                       ('output', 'completion_tokens', 'total_output_tokens')]:
            value = usage.get(standard, usage.get(native))
            if type(value) is int and value >= 0:
                known[side] += value
            else:
                missing[side] += 1
    return {'known_input_tokens': known['input'], 'known_output_tokens': known['output'],
            'missing_input_usage_calls': missing['input'], 'missing_output_usage_calls': missing['output'],
            'token_usage_complete': snapshot_complete and not any(missing.values()),
            'input_tokens': known['input'] if snapshot_complete and not missing['input'] else None,
            'output_tokens': known['output'] if snapshot_complete and not missing['output'] else None}


def assess(state,report,oracle,assessment=None):
    checks=[]
    def add(name,passed,detail):checks.append({'name':name,'passed':bool(passed),'detail':detail})
    add('source_stable',state.get('source_stable'),'Every executed phase must use the declared source version.')
    add('completed',state['status']=='completed','The full pipeline must finish in this run.')
    add('publishable',report.get('publishable') and report.get('status')=='approved','Use actual current approval, not just a generated HTML file.')
    add('resume',state.get('resume_idempotent'),'Completed review must resume without another model call.')
    add('mechanical',bool(report.get('checks')) and all(c['passed'] for c in report.get('checks',[])),'Mechanical review checks.')
    add('reference_present',bool(oracle.get('required')) and bool(oracle.get('metrics')),'Independent reference must be present, including required outcomes.')
    if state.get('supersedes_review_id'):
        add('previous_approval_invalidated',state.get('previous_approval_invalidated'),'Owner correction must invalidate the previous approved report.')
    if not assessment:
        return {'accepted':False,'status':'needs_independent_review' if all(c['passed'] for c in checks) else 'failed', 'checks':checks}
    add('independent_review',assessment.get('reviewer')=='development_review' and bool(assessment.get('notes','').strip()),'Human/development review is explicit; no inferred pass from model agreement.')
    for key in RUBRIC:add(key,assessment.get('rubric',{}).get(key) is True,'Independent semantic judgment.')
    draft=report.get('report') or {'claims':[],'charts':[]}
    cited={(r['execution_id'],r['metric']) for c in draft['claims'] for r in c['evidence']}
    cited.update((p['value']['execution_id'],p['value']['metric']) for c in draft.get('charts',[]) for p in c['points'])
    cited.update((h['value']['execution_id'],h['value']['metric']) for h in draft.get('highlights',[]))
    cited_series={(c['series']['execution_id'],c['series']['series']) for c in draft.get('charts',[]) if c.get('series')}
    observations={o['execution_id']:o for o in report.get('observations',[])}
    def resolve(ref, require_cited):
        obs=observations[ref['execution_id']]
        if not obs.get('current') or obs['status']!='completed' or obs.get('result_omitted'):
            raise ValueError('Unavailable evidence.')
        if 'series' in ref:
            if require_cited and (ref['execution_id'],ref['series']) not in cited_series:
                raise ValueError('Series not cited.')
            points=obs['result']['series'][ref['series']]['points']
            found=[p['value'] for p in points if p['label']==ref['label']]
            if len(found)!=1: raise ValueError('Series label missing or ambiguous.')
            raw=found[0]
        else:
            if require_cited and (ref['execution_id'],ref['metric']) not in cited:
                raise ValueError('Metric not cited.')
            raw=obs['result']['metrics'][ref['metric']]
        if type(raw) not in (str,int,float):raise ValueError('Not numeric.')
        return Decimal(str(raw))
    bindings=assessment.get('bindings',{})
    for expected in oracle['required']:
        ref=bindings.get(expected)
        passed=False
        detail='A required numerical result must be saved, cited and independently matched.'
        if ref:
            try:
                actual=resolve(ref,True);target=Decimal(oracle['metrics'][expected])
                passed=actual.is_finite() and abs(actual-target)<=tolerance(expected)
                detail=f'Actual {actual}; independent reference {target}.'
            except (KeyError,InvalidOperation,TypeError,ValueError):pass
        add('reference:'+expected,passed,detail)
    for expected,ref in bindings.items():
        if expected in oracle['required']:continue
        try:
            actual=resolve(ref,False)
            target=Decimal(oracle['metrics'][expected])
            passed=actual.is_finite() and abs(actual-target)<=tolerance(expected)
        except (KeyError,TypeError,InvalidOperation,ValueError):passed=False
        add('additional:'+expected,passed,'Additional independently recomputed metric.')
    return {'accepted':all(c['passed'] for c in checks),'status':'passed' if all(c['passed'] for c in checks) else 'failed','checks':checks}


def summary(directory):
    manifest=json.loads((directory/'manifest.json').read_text())
    rows=[]
    for name in manifest['jobs']:
        job=directory/name
        if not (job/'state.json').exists():
            rows.append({'job':name,'status':'not_run','accepted':False});continue
        state=json.loads((job/'state.json').read_text())
        read=lambda file,default:json.loads((job/file).read_text()) if (job/file).exists() else default
        report=read('review.json',{})
        result=assess(state,report,read('reference.json',{'required':[]}),read('assessment.json',None))
        resources=read('resources.json',{'calls':[]})
        result.update(job=name,scenario=state['scenario'],pipeline_status=state['status'],review_status=report.get('status'),
                      seconds=round(sum(state.get('timings',{}).values()),2),
                      seconds_is_lower_bound=bool(state.get('timings_lower_bound')),
                      model_calls=len(resources['calls']),issue=state.get('issue'))
        result.update(token_accounting(resources['calls'],
                      (job/'resources.json').exists() and not state.get('collection_issue')
                      and state['status'] in ('completed', 'failed', 'interrupted')))
        rows.append(result)
    result={'accepted':len(rows)==len(manifest['jobs']) and all(r['accepted'] for r in rows),
            'passed':sum(r['accepted'] for r in rows),'total':len(rows),'runs':rows}
    (directory/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    html=['<!doctype html><html lang="es"><meta charset="utf-8"><title>Evaluación 1.7</title><style>body{font:16px/1.6 system-ui;margin:3rem;max-width:1200px}table{border-collapse:collapse;width:100%}th,td{padding:12px;border-bottom:1px solid #ddd;text-align:left}a{color:#176358}</style>',
          f'<h1>Evaluación del paso 1.7</h1><p>{result["passed"]} de {result["total"]} ejecuciones aceptadas. Una aprobación del modelo no sustituye la revisión independiente.</p>',
          '<table><tr><th>Caso</th><th>Evaluación</th><th>Segundos</th><th>Llamadas</th><th>Detalle</th></tr>']
    for r in rows:
        name=r['job'];job=directory/name
        links=[]
        for filename,label in [('state.json','Registro'),('plan.json','Plan'),('research.json','Investigación'),
                               ('review.json','Revisión'),('resources.json','Recursos')]:
            if (job/filename).exists():
                links.append(f'<a href="{escape(name)}/{filename}">{label}</a>')
        if (job/'assessment.json').exists():links.append(f'<a href="{escape(name)}/assessment.json">Evaluación independiente</a>')
        if (job/'export.json').exists():
            exported=json.loads((job/'export.json').read_text())
            for key,label in [('path','Informe'),('internal_path','Informe interno')]:
                if exported.get(key):links.append(f'<a href="{escape(Path(exported[key]).as_uri())}">{label}</a>')
        links=' · '.join(links) or 'Sin ejecución registrada'
        html.append(f'<tr><td>{escape(name)}</td><td>{escape(r["status"])}</td><td>{'≥' if r.get('seconds_is_lower_bound') else ''}{r.get("seconds","—")}</td><td>{r.get("model_calls","—")}</td><td>{links}</td></tr>')
    html.append('</table></html>');(directory/'summary.html').write_text(''.join(html))
    return result


if __name__=='__main__':
    import sys
    result=summary(Path(sys.argv[1]))
    print(json.dumps({k:v for k,v in result.items() if k!='runs'}))
