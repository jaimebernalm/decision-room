"""Convenience API, not the security boundary. Docker enforces isolation."""
import json
from pathlib import Path

import duckdb

REQUEST = json.loads(Path('/inputs/request.json').read_text())
TABLES = REQUEST['tables']
DEFINITIONS = REQUEST['definitions']


def table_path(alias):
    return TABLES[alias]['path']


def connect():
    db = duckdb.connect(config={'threads': 1, 'memory_limit': '384MB',
                                'temp_directory': '/tmp/duckdb', 'max_temp_directory_size': '64MB',
                                'autoinstall_known_extensions': False, 'autoload_known_extensions': False})
    for alias, table in TABLES.items():
        db.read_parquet(table['path']).create_view(alias)
    return db


def write_result(metrics, *, evidence, notes=None):
    """Write a candidate result. The controller validates structure, not truth."""
    result = {'schema_version': 1, 'metrics': metrics, 'evidence': evidence, 'notes': notes or []}
    Path('/output/result.json').write_text(json.dumps(result, ensure_ascii=False, allow_nan=False) + '\n')
