"""Fixed html-v1 runtime profile. The generated brief and panorama live in engine.brief and engine.panorama_v1."""
import os
from pathlib import Path

VERSION = 'html-v1'
MODEL = 'gpt-6-luna'
IMAGE_TAG = 'decision-room-opencode:1.18.34'
RUNTIME_ENV = {'XDG_DATA_HOME': '/state', 'OPENCODE_DISABLE_AUTOUPDATE': '1',
               'OPENCODE_DISABLE_SHARE': '1', 'OPENCODE_DISABLE_CLAUDE_CODE': '1',
               'OPENCODE_DISABLE_EXTERNAL_SKILLS': '1', 'OPENCODE_DISABLE_MODELS_FETCH': '1',
               'OPENCODE_DISABLE_PROJECT_CONFIG': '1', 'OPENCODE_DISABLE_DEFAULT_PLUGINS': '1'}


def configuration(*, model=None, image=None, questions=False):
    if type(questions) is not bool:
        raise ValueError("Questions must be an explicit boolean.")
    return {'version': 'html-v1-questions-1' if questions else VERSION, 'model': model or MODEL, 'variant': 'low',
            'image_tag': IMAGE_TAG,
            'image_id': image if image is not None else os.environ.get('DECISION_ROOM_ENGINE_IMAGE_ID', ''),
            'opencode_version': '1.18.34', 'autoupdate': False, 'share': False,
            'snapshot': False, 'questions': questions,
            'runtime_environment': RUNTIME_ENV.copy(),
            'permissions': {'*': 'allow', 'external_directory': {'*': 'deny', '/inputs/*': 'allow'},
                            'webfetch': 'deny', 'websearch': 'deny', 'question': 'deny'}}


def prompt(owner_context):
    """Direct API fallback. Web jobs build the generated v1 brief in engine.brief instead."""
    fixed = (Path(__file__).resolve().parents[2] / 'engine/opencode/prompts/informe.md').read_text()
    return owner_context.strip() + '\n\n' + fixed


def context_files(value=None):
    """Only the optional F2 panorama, with no diagnostics or arbitrary host paths."""
    value = {} if value is None else value
    if not isinstance(value, dict) or set(value) - {'panorama.md'}:
        raise ValueError('Only panorama.md is accepted as optional context.')
    if any(not isinstance(v, str) or len(v.encode('utf-8')) > 256 * 1024 for v in value.values()):
        raise ValueError('Context must be bounded UTF-8 text.')
    return value.copy()
