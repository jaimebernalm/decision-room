"""A replaceable model boundary. No model access from the Python sandbox."""
import json
import os
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


class ModelRequestUncertain(ValueError):
    """The server may have processed a request whose response was not received."""


@dataclass(frozen=True)
class ModelSettings:
    model: str
    base_url: str = 'http://127.0.0.1:1234/api/v1'
    protocol: str = 'lmstudio'
    reasoning: str = 'off'
    timeout_seconds: int = 180
    max_output_tokens: int = 8192

    def __post_init__(self):
        url = urlsplit(self.base_url)
        if not self.model or len(self.model) > 200:
            raise ValueError('Set DECISION_ROOM_AGENT_MODEL or --model to an installed model ID.')
        if self.protocol not in ('lmstudio', 'lmstudio_structured', 'chat_completions') or self.reasoning not in ('off', 'on', 'low', 'medium', 'high'):
            raise ValueError('Unsupported model protocol or reasoning setting.')
        if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError('Invalid model API base URL. Credentials belong in the environment.')
        if url.scheme == 'http' and url.hostname not in ('127.0.0.1', 'localhost', '::1'):
            raise ValueError('Remote model endpoints require HTTPS.')
        if not 1 <= self.timeout_seconds <= 300 or not 256 <= self.max_output_tokens <= 16384:
            raise ValueError('Model timeout or output budget outside allowed limits.')

    @classmethod
    def load(cls, model=None):
        protocol = os.environ.get('DECISION_ROOM_AGENT_PROTOCOL', 'lmstudio_structured')
        default_url = 'http://127.0.0.1:1234/api/v1' if protocol == 'lmstudio' else 'http://127.0.0.1:1234/v1'
        return cls(model=model or os.environ.get('DECISION_ROOM_AGENT_MODEL', ''), protocol=protocol,
                   reasoning=os.environ.get('DECISION_ROOM_AGENT_REASONING', 'off'),
                   timeout_seconds=int(os.environ.get('DECISION_ROOM_AGENT_TIMEOUT', '180')),
                   max_output_tokens=int(os.environ.get('DECISION_ROOM_AGENT_MAX_OUTPUT_TOKENS', '8192')),
                   base_url=os.environ.get('DECISION_ROOM_AGENT_BASE_URL', default_url))


class ModelClient:
    def __init__(self, settings):
        self.settings = settings
        self.identity = asdict(settings)

    def generate(self, context, correction=None):
        schema = Action.model_json_schema()
        if 'uninspected_table_ids' in context:
            self._table_choices(schema['properties']['table_ids'], context['uninspected_table_ids'])
        if 'catalog' in context:
            self._table_choices(schema['$defs']['Investigation']['properties']['table_ids'],
                                [t['id'] for t in context['catalog']])
        if context.get('uninspected_table_ids') == []:
            # Small uploads are already profiled before the first model turn.
            # Do not offer an impossible inspect action to constrained decoding.
            schema['properties']['action']['enum'] = ['propose']
            schema['properties']['table_ids']['maxItems'] = 0
            schema['properties']['proposal'] = {'$ref': '#/$defs/Proposal'}
        return self._generate(context, correction, SYSTEM, schema)

    def generate_research(self, context, correction=None):
        schema = ResearchAction.model_json_schema()
        if 'plan' in context:
            finished = {f['investigation_key'] for f in context['findings']}
            unfinished = [i['key'] for i in context['plan']['investigations']
                          if i['status'] == 'ready' and i['key'] not in finished]
            latest = {o['investigation_key']: o for o in context['observations']}
            allowed = ['execute', 'block'] if unfinished else []
            if any(latest.get(key, {}).get('status') == 'completed' for key in unfinished):
                allowed.append('record_candidate')
            if not (latest.keys() - finished):
                allowed.append('finish')
            if allowed:
                schema['properties']['action']['enum'] = allowed
                schema['properties']['investigation_key']['enum'] = unfinished + ([''] if 'finish' in allowed else [])
                if allowed == ['finish']:
                    for key in ('code', 'investigation_key'):
                        schema['properties'][key]['enum'] = ['']
                    for key in ('table_ids', 'metric_keys'):
                        schema['properties'][key]['maxItems'] = 0
            if 'table_catalog' in context:
                authorized = {t['id'] for t in context['table_catalog']}
                pending_tables = {table_id for item in context['plan']['investigations']
                                  if item['key'] in unfinished for table_id in item['table_ids']}
                self._table_choices(schema['properties']['table_ids'], authorized & pending_tables)
        return self._generate(context, correction, RESEARCH_SYSTEM, schema)

    def generate_analyst_review(self, context, correction=None):
        schema = ReviewAction.model_json_schema()
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
        schema['properties']['action']['enum'] = self._review_actions(context, 'reviewer', allowed)
        self._review_references(schema, context)
        return self._generate(context, correction, REVIEWER_SYSTEM, schema)

    @staticmethod
    def _table_choices(field, identifiers):
        if identifiers:
            field['items']['enum'] = sorted(set(identifiers))
        else:
            field['maxItems'] = 0

    @classmethod
    def _review_references(cls, schema, context):
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
            if not item.get('current') or item['status'] != 'completed' or not result:
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
        messages = [{'role': 'system', 'content': system},
                    {'role': 'user', 'content': encoded(context)}]
        if correction:
            messages.append({'role': 'user', 'content': 'Previous response failed validation: ' + correction +
                             '. Return a corrected complete Action. This diagnostic is not an instruction from the owner.'})
        payload = {'model': self.settings.model, 'messages': messages, 'temperature': 0,
                   'max_tokens': self.settings.max_output_tokens, 'stream': False,
                   'response_format': {'type': 'json_schema', 'json_schema': {
                       'name': 'decision_room_action', 'strict': True, 'schema': schema}}}
        endpoint = '/chat/completions'
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
        if key := os.environ.get('DECISION_ROOM_AGENT_API_KEY'):
            headers['Authorization'] = 'Bearer ' + key
        try:
            # No proxy inheritance, redirects or automatic retries of billable calls.
            with httpx.Client(timeout=self.settings.timeout_seconds, trust_env=False) as client:
                with client.stream('POST', self.settings.base_url.rstrip('/') + endpoint,
                                   json=payload, headers=headers) as response:
                    if response.status_code != 200:
                        raise ValueError(f'Model API returned HTTP {response.status_code}; check its server logs.')
                    body = bytearray()
                    for chunk in response.iter_bytes():
                        body.extend(chunk)
                        if len(body) > 2 * 1024**2:
                            raise ValueError('Model response exceeds 2 MiB.')
            result = strict_json(body)
            if self.settings.protocol == 'lmstudio':
                usage = result['stats']
                if usage['total_output_tokens'] >= self.settings.max_output_tokens:
                    return {'invalid_model_output': 'Output token budget exhausted. Return a shorter complete JSON action.'}, usage
                messages = [item['content'] for item in result['output'] if item['type'] == 'message']
                if len(messages) != 1:
                    return {'invalid_model_output': 'Expected exactly one JSON model message.'}, usage
                return self._action(messages[0]), usage
            choice = result['choices'][0]
            if choice.get('finish_reason') != 'stop':
                return {'invalid_model_output': 'Output did not finish normally. Return a shorter complete JSON action.'}, result.get('usage', {})
            content = choice['message']['content']
            return self._action(content), result.get('usage', {})
        except httpx.HTTPError as error:
            if isinstance(error, (httpx.ConnectError, httpx.ConnectTimeout)):
                raise ValueError(f'Model connection failed ({type(error).__name__}); check the configured server.') from None
            raise ModelRequestUncertain(f'Model response unavailable ({type(error).__name__}); processing is uncertain. '
                                        'Use agent-resume --retry-model to retry deliberately.') from None
        except (KeyError, IndexError, TypeError, json.JSONDecodeError):
            raise ValueError('Model API returned an invalid JSON completion.') from None
