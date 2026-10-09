"""Explicit pilot entry points. No automatic test-set discovery or model invocation."""
from dataclasses import asdict
from pathlib import Path
import json
from uuid import uuid4

from ...engine import admission, costs
from ...service import create_business,import_batch
from . import sources,interpretation,presentation,localization
from .inventory import build_inventory,sha,canonical
from .provider import Budget,ProxyInterpreter


def prepare(report,csv_files,dest):
    dest=Path(dest);dest.mkdir(parents=True,exist_ok=False)
    report=Path(report).resolve()
    inventory=build_inventory(report)
    (dest/'original.html').write_bytes(report.read_bytes())
    prepared=sources.prepare(csv_files,dest/'sources')
    manifest={'version':'posthoc-run-v1','report':str(report),'csv_files':[str(Path(p).resolve()) for p in csv_files],
              'source_sha256':inventory['source_sha256'],'inventory_sha256':sha(canonical(inventory)),
              'sources_sha256':sha(canonical(prepared))}
    interpretation.save_new(dest/'inventory.json',inventory)
    interpretation.save_new(dest/'manifest.json',manifest)
    return manifest


def estimate_preflight(dest,*,batch_size=4,output_per_call=16000):
    """Measured local token estimate, not a bill or a provider count. No model calls."""
    import tiktoken
    dest=Path(dest);inventory=json.loads((dest/'inventory.json').read_text())
    catalog=json.loads((dest/'sources/sources.json').read_text())
    encoder=tiktoken.get_encoding('o200k_base')
    located=localization.classify(inventory,catalog)
    targets=[o for o in inventory['occurrences'] if located[o['id']]['eligible']]
    from decimal import Decimal
    input_tokens=0;scenario=Decimal(0);upper=Decimal(0);calls=0
    for offset in range(0,len(targets),batch_size):
        group=targets[offset:offset+batch_size]
        prompt,request=interpretation.batch_input(inventory,group,catalog)
        encoded=prompt+canonical({'response_format':'json',**request}).decode()
        measured=len(encoder.encode(encoded,disallowed_special=()))
        input_tokens+=measured*2;calls+=2
        base={'requested_model':'gpt-6-luna','effective_model':'gpt-6-luna','effective_tier':'default',
              'input':measured,'cache_read':0}
        scenario+=2*Decimal(costs.estimate({**base,'output':600*len(group),'cache_write':0})['cost'])
        upper+=2*Decimal(costs.estimate({**base,'output':output_per_call,'cache_write':measured})['cost'])
    return {'occurrences':len(inventory['occurrences']),'targets':len(targets),'batch_size':batch_size,
            'calls':calls,'estimated_input_tokens':input_tokens,
            'output_scenario_tokens':len(targets)*1200,'scenario_usd':str(scenario),
            'full_output_scenario_usd':str(upper),'output_per_call':output_per_call,
            'assumptions':['Approximate local tokenizer including masks, segments and excerpts; no cached tokens assumed.',
                '600 output tokens per occurrence; full-output scenario uses all allowed output and cache writes.',
                'Neither local scenario is an invoice or an exact provider count.']}


def sources_public(catalog):
    from .recipes import public_catalog
    return public_catalog(catalog)


def run(config,dest,budget_path,*,api_key,batch_size=4,report_limit='0.50',spend_ceiling='1.80',transport=None):
    """One report, one durable job; caller must explicitly choose the next report."""
    dest=Path(dest)
    with (dest/'started.json').open('x') as handle:
        handle.write(json.dumps({'batch_size':batch_size,'report_limit':report_limit,'spend_ceiling':spend_ceiling,
          'code_sha256':{p.name:sha(p.read_bytes()) for p in sorted(Path(__file__).parent.glob('*.py'))}}))
    inventory=json.loads((dest/'inventory.json').read_text())
    prepared=json.loads((dest/'sources/sources.json').read_text())
    manifest=json.loads((dest/'manifest.json').read_text())
    if sha(canonical(inventory))!=manifest['inventory_sha256'] or sha(canonical(prepared))!=manifest['sources_sha256']:
        raise ValueError('Prepared metadata changed.')
    original=Path(manifest['report'])
    if sha(original.read_bytes())!=manifest['source_sha256']:raise ValueError('Original changed.')
    if sorted(sha(Path(p).read_bytes()) for p in manifest['csv_files'])!=sorted(s['snapshot_sha256'] for s in prepared.values()):
        raise ValueError('CSV snapshot changed.')
    budget=Budget(budget_path,report_limit=report_limit,spend_ceiling=spend_ceiling)
    if budget.inspect()['unresolved']:raise ValueError('Unresolved prior provider cost; consult before continuing.')
    business=create_business(config,'Posthoc verification pilot')['id']
    batch=import_batch(config,business,[Path(p) for p in manifest['csv_files']])
    limits=admission.Limits(input_tokens=6_000_000,output_tokens=512_000,output_per_call=16000,calls=512,active_seconds=3600)
    run_id,token=admission.create_run(config,business,batch['analysis']['id'],
        table_ids=[f['table_id'] for f in batch['files']],owner_context='Verify an immutable report using grounded recipes.',
        request_key='posthoc-'+uuid4().hex,model='gpt-6-luna',limits=limits)
    interpretation.save_new(dest/'engine-job.json',{'business_id':str(business),'run_id':str(run_id),'limits':asdict(limits)})
    ask=ProxyInterpreter(config,business,run_id,token,api_key=api_key,budget=budget,
        report=inventory['source_sha256'],dest=dest/'provider',transport=transport)
    stage='interpretation'
    try:
        ledger=interpretation.verify(inventory,prepared,ask,dest/'verification',batch_size=batch_size)
        stage='render'
        derived=dest/'derived.html';derived.write_bytes(presentation.render(original.read_bytes(),inventory,ledger))
        stage='presentation_check'
        checks=presentation.check(original,derived,inventory)
        interpretation.save_new(dest/'checks.json',checks)
        interpretation.save_new(dest/'run.json',{'status':'completed','budget':budget.inspect()})
    except BaseException as error:
        # Do not promote an incomplete ledger to a successful report.
        interpretation.save_new(dest/'run.json',{'status':'failed','exception_type':type(error).__name__,
            'stage':stage,'errno':error.errno if isinstance(error,OSError) else None,'budget':budget.inspect()})
        raise
    finally:
        admission.revoke(config,business,run_id)
    return {'status':'completed','checks':checks,'budget':budget.inspect()}
