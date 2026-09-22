"""Explicit local dotenv loading without shell evaluation or value expansion."""
import os
import re
import shlex
from pathlib import Path


def load_env(path):
    path = Path(path)
    if not path.exists():
        return
    values = {}
    for number, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        match = re.fullmatch(r'\s*(?:export\s+)?([A-Z][A-Z0-9_]*)\s*=\s*(.*)', line)
        if not match:
            raise ValueError(f'Invalid environment assignment on line {number}.')
        name, raw = match.groups()
        if not (name.startswith('DECISION_ROOM_') or name == 'OPENAI_API_KEY'):
            raise ValueError(f'Unsupported environment variable on line {number}.')
        try:
            words = shlex.split(raw, comments=True, posix=True)
        except ValueError:
            raise ValueError(f'Invalid environment value on line {number}.') from None
        if len(words) > 1:
            raise ValueError(f'Quote environment values containing spaces (line {number}).')
        values[name] = words[0] if words else ''
    for name, value in values.items():
        os.environ.setdefault(name, value)
