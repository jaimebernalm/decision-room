"""P1b exposes frozen descriptive signals before planning and investigation."""
from copy import deepcopy
from ..panorama_presentation import compact

VERSION = 'panorama-research-v1'
SYSTEM = '''
PANORAMA-GUIDED RESEARCH (sales_panorama_research=true):
Read the compact sales_panorama first, alongside the owner's actual request.
Its signals are descriptive calculations, not a commercial ranking or causes.
For every listed gap and major change, the initial plan must supply panorama_plan:
either investigate linked to an investigation_key and a concrete research question,
or dismissed with a specific reason. One investigation may address several related
signals; never create one task per signal mechanically. Questions should say what
comparison would change the decision, using the available files before asking the
owner. A missing-row span is not zero sales, closure or a known extraction error.
The researcher may deepen a signal with Python: find exact boundary dates, compare
that product across channels or that channel across products, inspect continuity,
coverage and magnitude. Choose the method and useful followups; no fixed business
winner or mandatory causal conclusion. These overview references orient research;
register new evidence through normal executions before claiming a research result.
Business planner: review priorities and justified exclusions against the panorama
and owner goal. Do not override code-imposed coverage or demand an impossible task
per gap. A justified dismissal is allowed. Normal tool and budget rules still apply.
'''


def view(source):
    frozen = source.get('research_panorama')
    return compact(frozen, frozen['observations']) if frozen else None


def context_keys(context):
    return [s['key'] for s in (context.get('sales_panorama') or {}).get('signals', [])]


def constrain(schema, context):
    properties = schema['$defs']['Proposal']['properties']
    keys = context_keys(context) if context.get('sales_panorama_research') else []
    branch = {'anyOf':[{'$ref':'#/$defs/PanoramaInvestigation'}, {'$ref':'#/$defs/PanoramaExclusion'}]}
    properties['panorama_plan'] = dict(type='object',additionalProperties=False,
        properties={key:deepcopy(branch) for key in keys},required=keys)
    proposal = schema['$defs']['Proposal']
    proposal['required'] = list(properties)


def validate(proposal, source):
    panorama = view(source)
    if panorama is None: return
    expected = {s['key']:s for s in panorama['signals']}
    decisions = proposal.get('panorama_plan', {})
    if set(decisions) != set(expected):
        raise ValueError('panorama_plan must address every gap and major change exactly once: ' + ', '.join(expected))
    tasks = {item['key']:item for item in proposal['investigations']}
    for key, decision in decisions.items():
        if decision['disposition'] == 'investigate':
            task = tasks.get(decision['investigation_key'])
            if not task:
                raise ValueError(f'{key}: link to a real investigation_key in this plan: ' + ', '.join(tasks))
            if expected[key]['table_id'] not in task['table_ids']:
                raise ValueError(f'{key}: the linked investigation must have access to the signal source table.')


def expose(context, source):
    panorama = view(source)
    if panorama is not None:
        return {'sales_panorama':panorama, 'sales_panorama_research':True, **context}
    return context


def system(base, context):
    return base + SYSTEM if context.get('sales_panorama_research') else base
