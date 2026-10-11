"""Trusted creation snapshot shared by uploads, folder jobs and chat jobs."""
import re
from dataclasses import asdict

from . import admission, costs, profile


def selection(config, data, old=None):
    questions = data.get('engine_questions', False)
    if type(questions) is not bool:
        raise ValueError('Questions must be an explicit boolean.')
    explicit = data.get('engine_kind')
    if 'engine_kind' in data and explicit not in ('legacy', 'opencode'):
        raise ValueError('Unknown report engine.')
    if old:
        if explicit is not None and explicit != old['engine_kind']:
            raise ValueError('The job engine is already fixed.')
        if 'engine_questions' in data and questions != bool(old['engine_config'].get('profile', {}).get('questions')):
            raise ValueError('The job question profile is already fixed.')
        return old['engine_kind'], old['engine_config']
    kind = explicit if explicit is not None else config.report_engine
    if kind == 'legacy':
        if questions:
            raise ValueError('Engine questions require an engine job.')
        return kind, {}
    settings = profile.configuration(questions=questions)
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', settings['image_id']):
        raise ValueError('Configure a pinned engine image before creating engine jobs.')
    limits = admission.Limits(input_tokens=config.engine_input_tokens,
                             output_tokens=config.engine_output_tokens,
                             output_per_call=config.engine_output_per_call,
                             calls=config.engine_calls, active_seconds=config.engine_seconds)
    # Hard dollar ceiling (P4): the token limits are fitted so that every token priced at
    # the catalogue's worst rate stays within the cap. Frozen with the job.
    fitted, ceiling = costs.fit(asdict(limits), config.engine_usd_cap, settings['model'])
    return kind, {'profile': settings, 'limits': asdict(admission.Limits(**fitted)), 'usd_ceiling': ceiling}


def freeze(settings, *, context, goal, input_hash):
    """Owner inputs at creation. The brief needs prepared data, so it is built once at run creation."""
    if not settings:
        return {}
    owner = context + '\n\n' + goal
    return {**settings, 'owner_context': owner, 'goal': goal,
            'owner_sha256': admission.sha(admission.canonical([owner, goal])), 'input_request_sha256': input_hash}
