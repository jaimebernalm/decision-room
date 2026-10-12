"""Trusted creation snapshot shared by uploads, folder jobs and chat jobs."""
import re
from dataclasses import asdict

from . import admission, profile


def selection(config, data, old=None):
    explicit = data.get('engine_kind')
    kind = explicit if explicit is not None else config.report_engine
    if explicit is None and kind != 'legacy' and not old and not profile.configured():
        kind = 'legacy'  # The configured default needs the pinned engine image; see web startup notice.
    format = data.get('engine_format', config.report_format if kind != 'legacy' else 'html')
    if format not in ('html', 'blocks'):
        raise ValueError('Unknown report format.')
    questions = data.get('engine_questions', False)
    if type(questions) is not bool:
        raise ValueError('Questions must be an explicit boolean.')
    if 'engine_kind' in data and explicit not in ('legacy', 'opencode'):
        raise ValueError('Unknown report engine.')
    if old:
        if 'engine_format' in data and format != old['engine_config'].get('profile', {}).get('format', 'html'):
            raise ValueError('The job format is already fixed.')
        if explicit is not None and explicit != old['engine_kind']:
            raise ValueError('The job engine is already fixed.')
        if 'engine_questions' in data and questions != bool(old['engine_config'].get('profile', {}).get('questions')):
            raise ValueError('The job question profile is already fixed.')
        return old['engine_kind'], old['engine_config']
    if kind == 'legacy':
        if format != 'html':
            raise ValueError('Native reports require an engine job.')
        if questions:
            raise ValueError('Engine questions require an engine job.')
        return kind, {}
    settings = profile.configuration(questions=questions, usd_cap_micro=config.engine_usd_cap_micro, format=format)
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', settings['image_id']):
        raise ValueError('Configure a pinned engine image before creating engine jobs.')
    limits = admission.Limits(input_tokens=config.engine_input_tokens,
                             output_tokens=config.engine_output_tokens,
                             output_per_call=config.engine_output_per_call,
                             calls=config.engine_calls, active_seconds=config.engine_seconds)
    from ..agent import api_budget
    if config.engine_usd_cap_micro * 1000 < api_budget.MAX_INPUT * api_budget.INPUT_RATE + api_budget.MAX_OUTPUT * api_budget.OUTPUT_RATE:
        raise ValueError('The engine USD ceiling cannot reserve one bounded provider call.')
    return kind, {'profile': settings, 'limits': asdict(limits)}


def freeze(settings, *, context, goal, input_hash, investigation_brief=None):
    """Owner inputs at creation. The brief needs prepared data, so it is built once at run creation.

    A chat-written investigation brief is frozen once, with its own hash; it is guidance,
    never a source of facts, and recovery reuses this frozen copy.
    """
    if not settings:
        return {}
    owner = context + '\n\n' + goal
    frozen = {**settings, 'owner_context': owner, 'goal': goal,
              'owner_sha256': admission.sha(admission.canonical([owner, goal])), 'input_request_sha256': input_hash}
    if investigation_brief is not None:
        frozen['investigation_brief'] = investigation_brief
        frozen['investigation_brief_sha256'] = admission.sha(admission.canonical(investigation_brief))
    return frozen
