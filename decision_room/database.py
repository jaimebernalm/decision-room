from pathlib import Path

import psycopg
from psycopg.rows import dict_row


def connect(config):
    return psycopg.connect(config.dsn, autocommit=True, row_factory=dict_row)


def migrate(config):
    with connect(config) as db, db.transaction():
        db.execute('SELECT pg_advisory_xact_lock(87120931)')
        db.execute(Path(__file__).with_name('schema.sql').read_text())
