"""Versioned rendering contract; never inferred from report-controlled HTML."""
from functools import lru_cache
import json
from pathlib import Path
import re

from ..config import ROOT

from .presentation import POLICY_VERSION
RENDERER_VERSION = 'v1-container-raster-2'
DERIVED_VERSION = 1
MAX_TEXT = 1_000_000
MAX_SNAPSHOT_BYTES = 20 * 1024 * 1024
MAX_INVENTORY_BYTES = 16 * 1024 * 1024


@lru_cache(maxsize=1)
def renderer_version():
    """A changed pinned image is a new derivative key; deployment restarts workers.

    Without a configured image the queue remains durable but no rendered content
    can be served. The worker can enqueue a newly configured key later.
    """
    try:
        image = json.loads((ROOT / '.local/report-browser-runtime.json').read_text())['image']
    except (OSError,ValueError,KeyError):
        return RENDERER_VERSION + ':unconfigured'
    if not isinstance(image,str) or not re.fullmatch(r'sha256:[0-9a-f]{64}',image):
        raise ValueError('The report browser requires an immutable image.')
    return RENDERER_VERSION + ':' + image
