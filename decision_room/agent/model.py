"""A replaceable model boundary. No model access from the Python sandbox."""
import json
import os
import time
import math
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from contextvars import ContextVar
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict, dataclass
from urllib.parse import urlsplit

import httpx

from .contracts import Action
from .context import encoded
from .prompts import SYSTEM
from ..execution_contract import strict_json
from .research_contract import ResearchAction
from .research_prompts import RESEARCH_SYSTEM
from .review_contract import ReviewAction
from .review_prompts import ANALYST_SYSTEM, REVIEWER_SYSTEM


_TRANSPORT_RECORDER = ContextVar('model_transport_recorder', default=None)


@contextmanager
def record_transport(callback):
    token = _TRANSPORT_RECORDER.set(callback)
    try:
        yield
    finally:
        _TRANSPORT_RECORDER.reset(token)


def retry_delay(response, attempt):
    """Honor bounded 429 Retry-After; never retry early when its wait is too long."""
    raw = response.headers.get('Retry-After')
    delay = 2 ** (attempt + (response.status_code == 429))
    if raw:
        try:
            delay = float(raw)
        except ValueError:
            try:
                delay = (parsedate_to_datetime(raw) - datetime.now(timezone.utc)).total_seconds()
            except (ValueError, TypeError, OverflowError):
                pass
    if not math.isfinite(delay):
        return None
    if response.status_code == 429:
        return max(1, delay) if delay <= 30 else None
    return min(5, max(1, delay))


class ModelRequestUncertain(ValueError):
    """The server may have processed a request whose response was not received."""


class ModelAPIError(ValueError):
    """An HTTP rejection with no untrusted response body in the diagnostic."""

    def __init__(self, status_code):
        self.status_code = status_code
        super().__init__(f'Model API returned HTTP {status_code}; check its server logs.')


class ModelNotReady(ValueError):
    """Safe owner-facing explanation from a read-only local readiness check."""


@dataclass(frozen=True)
class ModelSettings:
    model: str
    base_url: str = 'http://127.0.0.1:1234/api/v1'
    protocol: str = 'lmstudio'
    reasoning: str = 'off'
    timeout_seconds: int = 180
    max_output_tokens: int = 8192
    response_language: str | None = None

    def __post_init__(self):
        if self.response_language not in (None, 'en', 'es'):
            raise ValueError('Unsupported response language.')
        url = urlsplit(self.base_url)
        if not self.model or len(self.model) > 200:
            raise ValueError('Set DECISION_ROOM_AGENT_MODEL or --model to an installed model ID.')
        if self.protocol not in ('lmstudio', 'lmstudio_structured', 'chat_completions', 'openai') or self.reasoning not in ('off', 'on', 'low', 'medium', 'high'):
            raise ValueError('Unsupported model protocol or reasoning setting.')
        if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError('Invalid model API base URL. Credentials belong in the environment.')
        if url.scheme == 'http' and url.hostname not in ('127.0.0.1', 'localhost', '::1'):
            raise ValueError('Remote model endpoints require HTTPS.')
        if self.protocol == 'openai' and (url.scheme, url.netloc, url.path.rstrip('/')) != ('https', 'api.openai.com', '/v1'):
            raise ValueError('The openai protocol requires https://api.openai.com/v1.')
        if not 1 <= self.timeout_seconds <= 300 or not 256 <= self.max_output_tokens <= 16384:
            raise ValueError('Model timeout or output budget outside allowed limits.')

    @classmethod
    def load(cls, model=None):
        protocol = os.environ.get('DECISION_ROOM_AGENT_PROTOCOL', 'lmstudio_structured')
        default_url = ('https://api.openai.com/v1' if protocol == 'openai' else
                       'http://127.0.0.1:1234/api/v1' if protocol == 'lmstudio' else 'http://127.0.0.1:1234/v1')
        return cls(model=model or os.environ.get('DECISION_ROOM_AGENT_MODEL', ''), protocol=protocol,
                   reasoning=os.environ.get('DECISION_ROOM_AGENT_REASONING', 'off'),
                   timeout_seconds=int(os.environ.get('DECISION_ROOM_AGENT_TIMEOUT', '180')),
                   max_output_tokens=int(os.environ.get('DECISION_ROOM_AGENT_MAX_OUTPUT_TOKENS', '8192')),
                   base_url=os.environ.get('DECISION_ROOM_AGENT_BASE_URL', default_url))


class ModelClient:
    def __init__(self, settings):
        self.settings = settings
        self.identity = asdict(settings)

    def check_ready(self):
        """Check local LM Studio loading state without triggering model loading.

        This is a necessary condition, not an inference health guarantee. Other
        providers retain their existing request path and error handling.
        """
        url = urlsplit(self.settings.base_url)
        if self.settings.protocol not in ('lmstudio', 'lmstudio_structured') or url.hostname not in ('127.0.0.1', 'localhost', '::1'):
            return
        headers = {}
        if key := os.environ.get('DECISION_ROOM_AGENT_API_KEY'):
            headers['Authorization'] = 'Bearer ' + key
        try:
            with httpx.Client(timeout=5, trust_env=False) as client:
                with client.stream('GET', f'{url.scheme}://{url.netloc}/api/v1/models', headers=headers) as response:
                    if response.status_code != 200:
                        raise ModelNotReady('No se pudo comprobar el modelo local. Revisa que el servidor de LM Studio esté activo y permita el acceso.')
                    body = bytearray()
                    for chunk in response.iter_bytes():
                        body.extend(chunk)
                        if len(body) > 1024**2:
                            raise ValueError('Model listing too large.')
            models = strict_json(body)['models']
            if not isinstance(models, list):
                raise ValueError('Invalid model listing.')
            for model in models:
                instances = model.get('loaded_instances', [])
                if not isinstance(instances, list) or any(not isinstance(i, dict) or not isinstance(i.get('id'), str) for i in instances):
                    raise ValueError('Invalid loaded instances.')
                if instances and (model.get('key') == self.settings.model or any(i.get('id') == self.settings.model for i in instances)):
                    return
        except ModelNotReady:
            raise
        except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError):
            raise ModelNotReady('No se pudo comprobar el modelo local. Abre LM Studio y comprueba que su servidor esté activo antes de reintentar.') from None
        raise ModelNotReady(
            'El modelo de este análisis no está cargado en LM Studio. Cárgalo antes de reintentar. '
            'Si LM Studio indica falta de memoria, cierra aplicaciones que no necesites y vuelve a cargarlo. '
            'El análisis sigue pausado y tus datos y respuestas están guardados.'
        )

    def generate_chat(self, context, correction=None):
        from ..chat_agent import Decision, SYSTEM, ONBOARDING_SYSTEM
        schema = Decision.model_json_schema()
        # Optional Python fields preserve historical stored decisions; the provider's
        # strict schema requires every property, using null for unused guide fields.
        for node in [schema, *schema.get('$defs', {}).values()]:
            if node.get('type') == 'object':
                node['required'] = list(node.get('properties', {}))
                for prop in node.get('properties', {}).values():
                    prop.pop('default', None)
        if context.get('onboarding'):
            schema['properties']['action']['enum'] = ['retrieve', 'answer']
        return self._generate(context, correction, SYSTEM + (ONBOARDING_SYSTEM if context.get("onboarding") else ""), schema)

    def review_chat_answer(self, context):
        from ..chat_agent import AnswerReview, REVIEW_SYSTEM
        return self._generate(context, None, REVIEW_SYSTEM, AnswerReview.model_json_schema())

    def generate_data_discovery(self, context, correction=None):
        from ..data_knowledge.discovery import Discovery, SYSTEM as DISCOVERY_SYSTEM
        schema = Discovery.model_json_schema()
        if 'tables' in context:
            ids = [t['id'] for t in context['tables']]
            if ids:
                schema['$defs']['TableMeaning']['properties']['id']['enum'] = ids
                for field in ('source', 'target'):
                    schema['$defs']['RelationProposal']['properties'][field]['enum'] = ids
            else:
                for field in ('tables', 'relations'):
                    schema['properties'][field]['maxItems'] = 0
        return self._generate(context, correction, DISCOVERY_SYSTEM, schema)

    def generate_dashboard(self, context):
        from ..web.home import Proposal, SYSTEM as DASHBOARD_SYSTEM
        return self._generate(context, None, DASHBOARD_SYSTEM, Proposal.model_json_schema())

    def generate_memory(self, context, correction=None):
        from ..memory.contracts import Extraction, SYSTEM as MEMORY_SYSTEM
        schema = Extraction.model_json_schema()
        schema['required'] = list(schema['properties'])
        schema['properties']['presentation_only'].pop('default', None)
        candidate = schema['$defs']['Candidate']
        candidate['required'] = list(candidate['properties'])
        candidate['properties']['correction_of'].pop('default', None)
        candidate['properties']['profile_replacement'].pop('default', None)
        candidate['properties']['group_id'] = {'type': ['string', 'null'],
                                               'enum': [g['id'] for g in context.get('groups', [])] + [None]}
        source = context['source']
        content = schema['$defs']['Content']['properties']
        scope = source['default_scope']
        content['scope']['enum'] = [scope, 'business'] if source['allow_business'] and scope != 'business' else [scope]
        content['scope_id'] = ({'type': ['string', 'null'], 'enum': [source['scope_id'], None]}
                               if len(content['scope']['enum']) > 1 else
                               {'type': 'null'} if source['scope_id'] is None else
                               {'type': 'string', 'enum': [source['scope_id']]})
        content['kind']['enum'] = [kind for kind in content['kind']['enum']
                                   if kind != 'result_reference' and not (scope == 'business' and kind == 'definition')]
        content['result_id'] = {'type': 'null'}
        return self._generate(context, correction, MEMORY_SYSTEM, schema)

    def generate(self, context, correction=None):
        schema = Action.model_json_schema()
        schema['$defs']['Investigation']['required'] = list(schema['$defs']['Investigation']['properties'])
        for prop in schema['$defs']['Investigation']['properties'].values():
            prop.pop('default', None)
        if 'uninspected_table_ids' in context:
            self._table_choices(schema['properties']['table_ids'], context['uninspected_table_ids'])
        if 'catalog' in context:
            self._table_choices(schema['$defs']['Investigation']['properties']['table_ids'],
                                [t['id'] for t in context.get('profiles', context['catalog'])])
        if 'profiles' in context:
            self._planning_references(schema, context)
            if not context['profiles'] and context.get('uninspected_table_ids'):
                schema['properties']['action']['enum'] = ['inspect']
                schema['properties']['proposal'] = {'type': 'null'}
                schema['properties']['table_ids']['minItems'] = 1
        if context.get('uninspected_table_ids') == []:
            # Small uploads are already profiled before the first model turn.
            # Do not offer an impossible inspect action to constrained decoding.
            schema['properties']['action']['enum'] = ['propose']
            schema['properties']['table_ids']['maxItems'] = 0
            if not context.get('business_context'):
                schema['properties']['proposal'] = {'$ref': '#/$defs/Proposal'}
        return self._generate(context, correction, SYSTEM, schema)

    @staticmethod
    def _planning_references(schema, context):
        from copy import deepcopy
        original = schema['$defs']['Reference']
        choices = []
        def branch(kind, ids, columns):
            if not ids or not columns:
                return
            item = deepcopy(original)
            item['properties']['kind']['enum'] = [kind]
            item['properties']['id']['enum'] = ids
            item['properties']['column']['enum'] = columns
            choices.append(item)
        branch('owner_context', ['owner_context'], [''])
        branch('answer', [str(a['id']) for a in context.get('answers', [])], [''])
        for table in context['profiles']:
            branch('table', [table['id']], [''])
            branch('column', [table['id']], table['column_names'])
        # Memory references retain their separate retrieved-evidence validator.
        if context.get('business_context'):
            shared = deepcopy(original)
            shared['properties']['kind']['enum'] = ['memory', 'data_model']
            choices.append(shared)
        schema['$defs']['Reference'] = {'anyOf': choices}

    def generate_business_planner(self, context, correction=None):
        from .business_planner import Direction, SYSTEM
        schema = Direction.model_json_schema()
        self._planning_references(schema, {'profiles': context['table_catalog']})
        self._table_choices(schema['properties']['priority_keys'], [i['key'] for i in context['plan']['investigations']])
        self._table_choices(schema['properties']['evidence_keys'], [f['investigation_key'] for f in context['findings'] if f['status']=='candidate'])
        if context['stage'] != 'delivery':
            schema['properties']['action']['enum'] = ['guide', 'ask_owner', 'replan']
        if not any(r['disposition']=='answered' for r in context['owner_replies']):
            schema['properties']['action']['enum'].remove('replan')
        return self._generate(context, correction, SYSTEM, schema)

    def generate_research(self, context, correction=None):
        schema = ResearchAction.model_json_schema()
        followup = schema['$defs']['Followup']
        followup['required'] = list(followup['properties'])
        for prop in followup['properties'].values():
            prop.pop('default', None)
        if 'plan' in context:
            finished = {f['investigation_key'] for f in context['findings']} | set(context.get('budgets', {}).get('discarded_keys', []))
            unfinished = [i['key'] for i in context['plan']['investigations']
                          if i['status'] == 'ready' and i['key'] not in finished]
            latest = {o['investigation_key']: o for o in context['observations']}
            allowed = ['execute', 'block', 'discard'] if unfinished else []
            if any(latest.get(key, {}).get('status') == 'completed' for key in unfinished):
                allowed.append('record_candidate')
            if not (latest.keys() - finished):
                allowed.append('finish')
            if context.get('budgets', {}).get('delegation') and any(key not in latest for key in unfinished):
                allowed.append('delegate')
                # The principal may make one broad exploration when only one
                # question is initially ready. Independent later work is handed
                # to workers, rather than advertising two interchangeable roles.
                if (latest or len(unfinished) > 1) and not (latest.keys() - finished):
                    allowed.remove('execute')
                    allowed.remove('block')
            expandable = [f['investigation_key'] for f in context['findings'] if f.get('status') == 'candidate'] if context.get('budgets', {}).get('delegation') else []
            if expandable:
                allowed.append('expand')
            if context.get('budgets', {}).get('delegation') and any(
                i['key'] in unfinished and i.get('round', 1) <= context['budgets'].get('max_rounds', 3)
                for i in context['plan']['investigations']):
                if 'finish' in allowed:
                    allowed.remove('finish')
            unrecorded_success = [key for key in unfinished if latest.get(key, {}).get('status') == 'completed'
                                  and not latest[key].get('result_omitted')]
            if unrecorded_success:
                # Preserve a usable result before another program can hide it.
                # A candidate is still unverified; a concrete unusable result may be blocked.
                allowed = ['record_candidate', 'block']
                unfinished, expandable = unrecorded_success, []
            if context.get('budgets', {}).get('business_planner') and not unrecorded_success:
                allowed.append('consult_business')
            if allowed:
                schema['properties']['action']['enum'] = allowed
                schema['properties']['investigation_key']['enum'] = list(dict.fromkeys(unfinished + expandable)) + ([''] if any(a in allowed for a in ('finish','delegate','consult_business')) else [])
                if allowed == ['finish']:
                    for key in ('code', 'investigation_key'):
                        schema['properties'][key]['enum'] = ['']
                    for key in ('table_ids', 'metric_keys'):
                        schema['properties'][key]['maxItems'] = 0
            assignable = [key for key in unfinished if key not in latest]
            if 'delegate' in allowed and assignable:
                schema['$defs']['Assignment']['properties']['investigation_key']['enum'] = assignable
            else:
                schema['properties']['assignments']['maxItems'] = 0
            if 'table_catalog' in context:
                authorized = {t['id'] for t in context['table_catalog']}
                pending_tables = {table_id for item in context['plan']['investigations']
                                  if item['key'] in unfinished for table_id in item['table_ids']}
                self._table_choices(schema['properties']['table_ids'], authorized & pending_tables)
        # Restrict evidence references to actual latest metrics. The validator
        # still checks the chosen investigation; a typo must never become evidence.
        latest_results = {o['investigation_key']: o for o in context.get('observations', [])}
        metric_names = {key for o in latest_results.values() if o.get('status') == 'completed'
                        for key in o.get('result', {}).get('metrics', {})}
        self._table_choices(schema['properties']['metric_keys'], metric_names)
        candidates = [f['investigation_key'] for f in context.get('findings', []) if f.get('status') == 'candidate']
        if candidates:
            schema['$defs']['RankedFinding']['properties']['investigation_key']['enum'] = candidates
            schema['$defs']['Disagreement']['properties']['investigation_keys']['items']['enum'] = candidates
        else:
            for name in ('priorities', 'excluded', 'disagreements'):
                schema['$defs']['Synthesis']['properties'][name]['maxItems'] = 0
        schema['required'] = list(schema['properties'])
        if 'table_catalog' in context:
            self._table_choices(schema['$defs']['Followup']['properties']['table_ids'], [t['id'] for t in context['table_catalog']])
        role = 'You are the subanalyst for budgets.worker_assignment; complete only that assignment.' if context.get('budgets', {}).get('worker_assignment') else (
            'You are the PRINCIPAL COORDINATOR. Your available calculation tool is action=delegate: workers execute Python. When execute is absent from your action schema, delegate IS available; never claim Python is unavailable. After expand, delegate the ready tasks. Retain synthesis and prioritization. Explicitly discard a ready task only with a concrete reason of low value or insufficient evidence.' if context.get('budgets', {}).get('delegation') else 'You are the sole analyst.')
        return self._generate(context, correction, role + '\n' + RESEARCH_SYSTEM, schema)

    def generate_analyst_review(self, context, correction=None):
        schema = ReviewAction.model_json_schema()
        schema['required'] = list(schema['properties'])
        schema['properties']['action']['enum'] = self._review_actions(context, 'analyst', ['submit', 'execute', 'ask_owner', 'withdraw'])
        self._review_references(schema, context)
        return self._generate(context, correction, ANALYST_SYSTEM, schema)

    def generate_reviewer(self, context, correction=None):
        schema = ReviewAction.model_json_schema()
        allowed = ['revise', 'reject', 'ask_owner', 'execute']
        new_execution = any(e['step'] > context.get('report_step', 0) and e['action']['action'] == 'execute'
                            for e in context.get('conversation', []))
        if context.get('report') and all(c['passed'] for c in context.get('checks', [])) and not new_execution:
            allowed.append('approve')
        schema['required'] = list(schema['properties'])
        schema['properties']['action']['enum'] = self._review_actions(context, 'reviewer', allowed)
        self._review_references(schema, context)
        return self._generate(context, correction, REVIEWER_SYSTEM, schema)

    @staticmethod
    def _table_choices(field, identifiers):
        if identifiers:
            field['items']['enum'] = sorted(set(identifiers))
        else:
            field['maxItems'] = 0
            if 'minItems' in field:
                field['minItems'] = 0

    @classmethod
    def _review_references(cls, schema, context):
        assessment = schema['$defs']['ReviewAssessment']
        assessment['required'] = list(assessment['properties'])
        assessment['properties']['usefulness'].pop('default', None)
        # Runtime defaults retain old reports; model output supplies all fields.
        for name in ('ReportDraft', 'Chart'):
            definition = schema['$defs'][name]
            definition['required'] = list(definition['properties'])
            for field in definition['properties'].values():
                field.pop('default', None)
        point_choices = []
        for item in context.get('observations', []):
            if item.get('current') and item['status'] == 'completed' and item.get('result') and not item.get('result_omitted'):
                for key, series in item['result'].get('series', {}).items():
                    if not series.get('points') or any('label' not in p for p in series['points']):
                        continue
                    branch = deepcopy(schema['$defs']['SeriesPointRef'])
                    branch['properties']['execution_id']['enum'] = [item['execution_id']]
                    branch['properties']['series']['enum'] = [key]
                    branch['properties']['label']['enum'] = [p['label'] for p in series['points']]
                    point_choices.append(branch)
        if point_choices:
            schema['$defs']['SeriesPointRef'] = {'anyOf': point_choices}
        else:
            schema['$defs']['Claim']['properties']['evidence']['items'] = {'$ref': '#/$defs/MetricRef'}
            for name, field in (('Highlight','value'),('ChartPoint','value'),('NumericCheck','actual')):
                schema['$defs'][name]['properties'][field] = {'$ref': '#/$defs/MetricRef'}
            schema['$defs']['NumericCheck']['properties']['operands']['items'] = {'$ref': '#/$defs/MetricRef'}
        series_choices = []
        series_by_chart = {}
        for item in context.get('observations', []):
            if item.get('current') and item['status'] == 'completed' and item.get('result') and not item.get('result_omitted'):
                units = {}
                display = {}
                for key, value in item['result'].get('series', {}).items():
                    count = len(value.get('points', []))
                    kinds = (['bar', 'table'] if 2 <= count <= 36 else [])
                    if value.get('grain') == 'day' and 2 <= count <= 366:
                        kinds.append('line')
                    if kinds:
                        units.setdefault(value['unit'], []).append(key)
                        display[key] = kinds
                for unit, keys in sorted(units.items()):
                    branch = deepcopy(schema['$defs']['SeriesRef'])
                    branch['properties']['execution_id']['enum'] = [item['execution_id']]
                    branch['properties']['series']['enum'] = sorted(keys)
                    series_choices.append(branch)
                    for kind in ('bar', 'table', 'line'):
                        eligible = [key for key in keys if kind in display[key]]
                        if eligible:
                            reference = deepcopy(branch)
                            reference['properties']['series']['enum'] = sorted(eligible)
                            series_by_chart.setdefault((unit, kind), []).append(reference)
        original_chart = schema['$defs']['Chart']
        # Select evidence before its display unit. With unit first, constrained
        # decoding can lock an edited chart into the old source's unit branch
        # and force a wrong series even while the analyst intends to replace it.
        properties = original_chart['properties']
        original_chart['properties'] = {key: properties[key] for key in
            ['series', 'points', *[key for key in properties if key not in ('series', 'points')]]}
        scalar_chart = deepcopy(original_chart)
        scalar_chart['properties']['series'] = {'type': 'null'}
        scalar_chart['properties']['points']['minItems'] = 2
        if series_choices:
            schema['$defs']['SeriesRef'] = {'anyOf': series_choices}
            charts = [scalar_chart]
            for (unit, kind), references in sorted(series_by_chart.items()):
                branch = deepcopy(original_chart)
                branch['properties']['unit']['enum'] = [unit]
                branch['properties']['kind']['enum'] = [kind]
                branch['properties']['series'] = {'anyOf': references}
                branch['properties']['points']['maxItems'] = 0
                charts.append(branch)
            # Keep the source unit paired with its evidence, rather than offering
            # invalid combinations and relying on a later correction turn.
            schema['$defs']['Chart'] = {'anyOf': charts}
        else:
            schema['$defs']['Chart'] = scalar_chart
        investigations = context.get('plan', {}).get('investigations', [])
        if investigations:
            ready = sorted(i['key'] for i in investigations if i['status'] == 'ready')
            blocked = sorted(i['key'] for i in investigations if i['status'] != 'ready')
            coverage = schema['$defs']['ReportDraft']['properties']['question_coverage']
            coverage.update(minItems=len(ready), maxItems=len(investigations))
            branches = []
            deferred = sorted(i['key'] for i in investigations if i['status'] == 'ready' and i.get('parent_key')) if context.get('review_policy', 0) >= 3 else []
            standard = [key for key in ready if key not in deferred]
            for keys, statuses in ((standard, ['answered', 'unavailable']), (deferred, ['answered', 'unavailable', 'deferred']), (blocked, ['unavailable'])):
                if not keys:
                    continue
                branch = deepcopy(schema['$defs']['QuestionCoverage'])
                branch['properties']['investigation_key']['enum'] = keys
                branch['properties']['status']['enum'] = statuses
                if statuses == ['unavailable']:
                    branch['properties']['claim_keys']['maxItems'] = 0
                branches.append(branch)
            schema['$defs']['QuestionCoverage'] = {'anyOf': branches}
        delivered = (context.get('report') or {}).get('question_coverage', [])
        if delivered:
            branches = []
            for entry in delivered:
                branch = deepcopy(schema['$defs']['QuestionUtility'])
                branch['properties']['investigation_key']['enum'] = [entry['investigation_key']]
                branch['properties']['verdict']['enum'] = {
                    'answered': ['pass', 'fail'], 'unavailable': ['unavailable', 'fail'],
                    'deferred': ['deferred', 'fail'],
                }[entry['status']]
                cls._table_choices(branch['properties']['claim_keys'], entry['claim_keys'])
                branches.append(branch)
            schema['$defs']['QuestionUtility'] = {'anyOf': branches}
        # Offer only the arity that each supported numerical operation accepts.
        # A combined numerator must be a saved metric, not an extra ratio operand.
        original_check = schema['$defs']['NumericCheck']
        shapes = []
        for operations, minimum, maximum in [(['zero', 'nonnegative'], 0, 0),
                                              (['equal'], 1, 1), (['sum'], 1, 16),
                                              (['percent_change', 'ratio_percent'], 2, 2)]:
            branch = deepcopy(original_check)
            branch['properties']['operation']['enum'] = operations
            branch['properties']['operands'].update(minItems=minimum, maxItems=maximum)
            shapes.append(branch)
        schema['$defs']['NumericCheck'] = {'anyOf': shapes}
        if 'tables' in context:
            cls._table_choices(schema['properties']['table_ids'], [t['id'] for t in context['tables']])
        if 'observations' not in context:
            return
        choices = []
        original = schema['$defs']['MetricRef']
        for item in context['observations']:
            result = item.get('result')
            if not item.get('current') or item['status'] != 'completed' or not result or item.get('result_omitted'):
                continue
            evidenced = {e['metric'] for e in result.get('evidence', [])}
            keys = sorted(set(result.get('metrics', {})) & evidenced)
            if not keys:
                continue
            branch = deepcopy(original)
            branch['properties']['execution_id']['enum'] = [item['execution_id']]
            branch['properties']['metric']['enum'] = keys
            choices.append(branch)
        if choices:
            # Keep each execution paired with its own saved metrics. This prevents
            # invented references, not wrong labels or business interpretations.
            schema['$defs']['MetricRef'] = {'anyOf': choices}
        elif point_choices:
            # Saved series points are evidence too; no redundant scalar required.
            # Some numeric-check definitions have already become anyOf branches.
            def point_only(node):
                if isinstance(node, dict):
                    if node.get('$ref') == '#/$defs/MetricRef':
                        node['$ref'] = '#/$defs/SeriesPointRef'
                    for value in node.values(): point_only(value)
                elif isinstance(node, list):
                    for value in node: point_only(value)
            point_only(schema)
        else:
            # A draft needs evidence. Keep execute/question/withdraw available,
            # without constructing an invalid empty union or inventing a sentinel ID.
            schema['properties']['report'] = {'type': 'null'}
            schema['properties']['action']['enum'] = [action for action in schema['properties']['action']['enum']
                                                     if action not in ('submit', 'approve')]

    @staticmethod
    def _review_actions(context, role, allowed):
        budgets = context.get('budgets', {})
        if budgets.get('python_used', {}).get(role, 0) >= budgets.get('max_python_per_role', 3):
            allowed.remove('execute')
        if budgets.get('questions_used', 0) >= budgets.get('max_questions', 3):
            allowed.remove('ask_owner')
        return allowed

    @staticmethod
    def _action(content):
        if not isinstance(content, str):
            return {'invalid_model_output': 'Expected a JSON message string.'}
        # Some local models wrap valid JSON in a Markdown fence. Unwrap only the
        # complete outer fence; never patch or execute the generated program.
        text = content.strip()
        if text.startswith('```json\n') and text.endswith('\n```'):
            text = text[8:-4]
        elif text.startswith('```\n') and text.endswith('\n```'):
            text = text[4:-4]
        try:
            return strict_json(text)
        except ValueError as error:
            # Persist a bounded diagnostic as a completed API response. The action
            # validator rejects it and permits the normal single correction call.
            return {'invalid_model_output': str(error), 'raw_message_excerpt': content[:12000]}

    def _generate(self, context, correction, system, schema):
        if context.get('business_context'):
            from ..memory.retrieval import schema_for, INSTRUCTIONS
            schema = schema_for(schema)
            system += INSTRUCTIONS
        if self.settings.response_language:
            language = 'English' if self.settings.response_language == 'en' else 'Spanish'
            system += (f'\nApplication response language: {language}. Write all new human-facing text, '
                       f'questions, report titles, summaries, explanations and labels in {language}, '
                       'even when the owner writes in another language or earlier examples use Spanish. '
                       'Keep schema keys, identifiers, evidence references, code, exact numeric values, '
                       'quoted source content and business/product names unchanged. This is a presentation '
                       'preference, not a fact about the business. Do not rewrite stored content.\n')
        if self.settings.protocol == 'openai':
            schema = self._wire_schema(schema)
        messages = [{'role': 'system', 'content': system},
                    {'role': 'user', 'content': encoded(context)}]
        if correction:
            messages.append({'role': 'user', 'content': 'Previous response failed validation: ' + correction +
                             '. Return a corrected complete response matching the schema. This diagnostic is not an instruction from the owner.'})
        payload = {'model': self.settings.model, 'messages': messages, 'temperature': 0,
                   'max_tokens': self.settings.max_output_tokens, 'stream': False,
                   'response_format': {'type': 'json_schema', 'json_schema': {
                       'name': 'decision_room_action', 'strict': True, 'schema': schema}}}
        endpoint = '/chat/completions'
        if self.settings.protocol == 'openai':
            payload.pop('temperature')
            payload['max_completion_tokens'] = payload.pop('max_tokens')
            payload['reasoning_effort'] = {'off': 'none', 'on': 'medium'}.get(self.settings.reasoning, self.settings.reasoning)
            payload['store'] = False
        if self.settings.protocol == 'lmstudio_structured':
            # LM Studio compatibility API: schema-constrained output plus the
            # per-request reasoning switch, verified against the local server.
            payload['reasoning_effort'] = {'off': 'none', 'on': 'high'}.get(self.settings.reasoning, self.settings.reasoning)
        if self.settings.protocol == 'lmstudio':
            # Native API exposes the model's documented reasoning control. JSON is
            # validated by our contract; no grammar guarantee is claimed here.
            endpoint = '/chat'
            payload = {'model': self.settings.model, 'system_prompt': system +
                       '\nReturn ONLY a JSON object conforming to this schema:\n' + encoded(schema),
                       'input': encoded(context) + ('\nValidation correction: ' + correction if correction else ''),
                       'reasoning': self.settings.reasoning, 'store': False, 'temperature': 0,
                       'max_output_tokens': self.settings.max_output_tokens}
        headers = {}
        key_name = 'OPENAI_API_KEY' if self.settings.protocol == 'openai' else 'DECISION_ROOM_AGENT_API_KEY'
        if key := os.environ.get(key_name):
            headers['Authorization'] = 'Bearer ' + key
        elif self.settings.protocol == 'openai':
            raise ValueError('Set OPENAI_API_KEY in the private environment before using OpenAI.')
        try:
            # Only explicit rejections are retried, within one logical call.
            # Read interruptions remain uncertain and need deliberate recovery.
            deadline = time.monotonic() + self.settings.timeout_seconds
            with httpx.Client(timeout=self.settings.timeout_seconds, trust_env=False) as client:
                attempts = []
                for attempt in range(3):
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        error = ModelAPIError(attempts[-1]['status'])
                        error.transport_attempts = attempts
                        raise error
                    with client.stream('POST', self.settings.base_url.rstrip('/') + endpoint,
                                       json=payload, headers=headers, timeout=remaining) as response:
                        attempts.append({'status': response.status_code})
                        delay = retry_delay(response, attempt) if response.status_code in (429, 503) and attempt < 2 else None
                        if delay is not None and delay >= deadline - time.monotonic():
                            delay = None
                        if response.status_code != 200:
                            attempts[-1]['usage_unknown'] = True
                        if delay is not None:
                            attempts[-1]['retry_delay_seconds'] = delay
                        if recorder := _TRANSPORT_RECORDER.get():
                            recorder(attempts)
                        if response.status_code != 200 and delay is None:
                            error = ModelAPIError(response.status_code)
                            error.transport_attempts = attempts
                            raise error
                        if response.status_code == 200:
                            body = bytearray()
                            for chunk in response.iter_bytes():
                                body.extend(chunk)
                                if len(body) > 2 * 1024**2:
                                    raise ValueError('Model response exceeds 2 MiB.')
                            break
                    time.sleep(delay)
            result = strict_json(body)
            if self.settings.protocol == 'lmstudio':
                usage = result['stats']
                if len(attempts) > 1:
                    usage = {**usage, 'transport_attempts': attempts, 'rejected_attempt_usage_unknown': True}
                if usage['total_output_tokens'] >= self.settings.max_output_tokens:
                    return {'invalid_model_output': 'Output token budget exhausted. Return a shorter complete JSON action.'}, usage
                messages = [item['content'] for item in result['output'] if item['type'] == 'message']
                if len(messages) != 1:
                    return {'invalid_model_output': 'Expected exactly one JSON model message.'}, usage
                return self._action(messages[0]), usage
            usage = result.get('usage', {})
            if len(attempts) > 1:
                usage = {**usage, 'transport_attempts': attempts, 'rejected_attempt_usage_unknown': True}
            choice = result['choices'][0]
            if choice.get('finish_reason') != 'stop':
                return {'invalid_model_output': 'Output did not finish normally. Return a shorter complete JSON action.'}, usage
            content = choice['message']['content']
            return self._action(content), usage
        except httpx.HTTPError as error:
            if isinstance(error, (httpx.ConnectError, httpx.ConnectTimeout)):
                raise ValueError(f'Model connection failed ({type(error).__name__}); check the configured server.') from None
            raise ModelRequestUncertain(f'Model response unavailable ({type(error).__name__}); processing is uncertain. '
                                        'Use agent-resume --retry-model to retry deliberately.') from None
        except (KeyError, IndexError, TypeError, json.JSONDecodeError):
            raise ValueError('Model API returned an invalid JSON completion.') from None

    @staticmethod
    def _wire_schema(schema):
        """Preserve source labels when provider strict enums reject quote literals.

        Exact source/column/label/unit validation still runs after generation.
        Relax only the affected string enum, never change the underlying data or
        silently remove a legitimate label from the selectable source evidence.
        """
        schema = deepcopy(schema)
        def visit(node):
            if isinstance(node, dict):
                values = node.get('enum', [])
                if values and all(isinstance(v, str) for v in values) and any('"' in v for v in values):
                    node.pop('enum')
                    node.setdefault('type', 'string')
                for value in node.values():
                    visit(value)
            elif isinstance(node, list):
                for value in node:
                    visit(value)
        visit(schema)
        return schema
