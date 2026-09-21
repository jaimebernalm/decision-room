import getpass
import os
from dataclasses import dataclass
from pathlib import Path

from psycopg.conninfo import make_conninfo

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Config:
    dsn: str
    storage: Path
    max_files: int = 100
    max_file_bytes: int = 2 * 1024**3
    max_batch_bytes: int = 8 * 1024**3
    max_columns: int = 256
    max_rows: int = 10_000_000

    @classmethod
    def load(cls):
        default = make_conninfo(host=str(ROOT / '.local/pgsocket'), port=55432,
                                dbname='decision_room', user=getpass.getuser(), connect_timeout=5)
        return cls(os.environ.get('DECISION_ROOM_DATABASE_URL', default),
                   Path(os.environ.get('DECISION_ROOM_STORAGE', ROOT / '.local/storage')).resolve())
