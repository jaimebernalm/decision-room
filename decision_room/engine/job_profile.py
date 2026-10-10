"""Trusted creation snapshot shared by uploads, folder jobs and chat jobs."""
import re
from dataclasses import asdict

from . import admission, profile


def selection(config, data, old=None):
    explicit = data.get('engine_kind')
    if 'engine_kind' in data and explicit not in ('legacy', 'opencode'):
        raise ValueError('Unknown report engine.')
    if old:
        if explicit is not None and explicit != old['engine_kind']:
            raise ValueError('The job engine is already fixed.')
        return old['engine_kind'], old['engine_config']
    kind = explicit if explicit is not None else config.report_engine
    if kind == 'legacy':
        return kind, {}
    settings = profile.configuration()
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', settings['image_id']):
        raise ValueError('Configure a pinned engine image before creating engine jobs.')
    limits = admission.Limits(input_tokens=config.engine_input_tokens,
                             output_tokens=config.engine_output_tokens,
                             output_per_call=config.engine_output_per_call,
                             calls=config.engine_calls, active_seconds=config.engine_seconds)
    return kind, {'profile': settings, 'limits': asdict(limits)}


def freeze(settings, *, context, goal, input_hash):
    if not settings:
        return {}
    owner = context + '\n\n' + goal
    prompt = profile.prompt(owner)
    return {**settings, 'owner_context': owner, 'prompt': prompt,
            'prompt_sha256': admission.sha(prompt.encode()), 'input_request_sha256': input_hash}
