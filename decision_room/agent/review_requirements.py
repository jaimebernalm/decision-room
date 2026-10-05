"""Complete review-scoped inventories, shared by the schema and visible context."""
from copy import deepcopy
from .panorama_contract import enabled as panorama_enabled, metric_choices, reference_schema


def inventories(context):
    tasks=context.get('plan',{}).get('investigations',[])
    return dict(required_coverage_keys=sorted(t['key'] for t in tasks if t['status']=='ready'),
        allowed_coverage_keys=sorted(t['key'] for t in tasks),
        citable_panorama_metrics=sorted(metric_choices(context),key=lambda r:(r['execution_id'],r['metric'])) if panorama_enabled(context) else [])


def expose(context):
    return {**context,**inventories(context)}


def constrain_coverage(schema,context):
    tasks=context.get('plan',{}).get('investigations',[])
    if not tasks:return
    branches=[]
    for task in sorted(tasks,key=lambda t:t['key']):
        branch=deepcopy(schema['$defs']['QuestionCoverage'])
        branch['properties']['investigation_key']['enum']=[task['key']]
        statuses=['unavailable']
        if task['status']=='ready':
            statuses=['answered','unavailable']
            if context.get('review_policy',0)>=3 and (task.get('parent_key') or context.get('review_policy',0)>=5):
                statuses.append('deferred')
        branch['properties']['status']['enum']=statuses
        if task['status']!='ready':branch['properties']['claim_keys']['maxItems']=0
        branches.append(branch)
    schema['$defs']['QuestionCoverage']={'anyOf':branches}
    field=schema['$defs']['ReportDraft']['properties']['question_coverage']
    field.update(minItems=sum(t['status']=='ready' for t in tasks),maxItems=len(tasks))
    schema['$defs']['QuestionUtility']['properties']['investigation_key']['enum']=sorted(t['key'] for t in tasks)


def constrain_panorama(schema,context):
    choices=inventories(context)['citable_panorama_metrics']
    if choices:
        schema['$defs']['FrozenPanoramaMetric']=reference_schema(choices)
        schema['$defs']['PanoramaPriority']['properties']['evidence']['items']={'$ref':'#/$defs/FrozenPanoramaMetric'}
