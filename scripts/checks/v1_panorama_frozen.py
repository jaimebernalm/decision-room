"""Compare the product panorama with a frozen trial panorama.md, through the product path.

Usage: .venv/bin/python scripts/checks/v1_panorama_frozen.py <inputs folder with datos/*.csv and contexto/panorama.md>

Imports the CSVs into a disposable database and storage, builds the panorama with
engine.panorama_v1 and prints a unified diff against the frozen file. No model call.
The trial data is not part of the repository.
"""
import difflib
import hashlib
import sys
import tempfile
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

from psycopg import sql
from psycopg.conninfo import make_conninfo

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from decision_room.config import Config  # noqa: E402
from decision_room.database import connect, migrate  # noqa: E402
from decision_room.engine import panorama_v1  # noqa: E402
from decision_room.service import create_business, import_batch  # noqa: E402


def main(folder):
    folder = Path(folder)
    frozen = (folder / 'contexto/panorama.md').read_bytes()
    base, name = Config.load(), 'dr_panorama_check_' + uuid4().hex
    with connect(base) as db:
        db.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
    try:
        with tempfile.TemporaryDirectory() as storage:
            config = replace(base, dsn=make_conninfo(base.dsn, dbname=name), storage=Path(storage))
            migrate(config)
            business = create_business(config, 'Comprobación')['id']
            analysis = import_batch(config, business, sorted((folder / 'datos').glob('*.csv')))['analysis']['id']
            with connect(config) as db:
                tables = db.execute('''SELECT id,parquet_key,parquet_sha256,columns FROM prepared_tables
                    WHERE business_id=%s AND analysis_id=%s ORDER BY id''', (business, analysis)).fetchall()
            result = panorama_v1.build(config, business, tables)
    finally:
        with connect(base) as db:
            db.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
    ours = result.get('markdown', '').encode('utf-8')
    print('frozen ', hashlib.sha256(frozen).hexdigest())
    print('product', hashlib.sha256(ours).hexdigest(), result['status'])
    print('identical' if ours == frozen else 'different')
    # Decoding is only for the readable diff; the verdict above compares raw bytes.
    sys.stdout.writelines(difflib.unified_diff(frozen.decode().splitlines(True), ours.decode().splitlines(True),
                                               'frozen', 'product', n=0))


if __name__ == '__main__':
    main(sys.argv[1])
