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
    max_file_bytes: int = 2 * 1024**3
    max_batch_bytes: int = 8 * 1024**3
    max_columns: int = 256
    max_rows: int = 10_000_000
    semantic_search: bool = False
    embedding_model: str = 'text-embedding-3-small'
    embedding_dimensions: int = 1536

    def __post_init__(self):
        maximum = {'text-embedding-3-small': 1536, 'text-embedding-3-large': 3072}
        if self.embedding_model not in maximum or not 256 <= self.embedding_dimensions <= maximum[self.embedding_model]:
            raise ValueError('Unsupported embedding model or dimensions.')

    @classmethod
    def load(cls):
        default = make_conninfo(host=str(ROOT / '.local/pgsocket'), port=55432,
                                dbname='decision_room', user=getpass.getuser(), connect_timeout=5)
        return cls(os.environ.get('DECISION_ROOM_DATABASE_URL', default),
                   Path(os.environ.get('DECISION_ROOM_STORAGE', ROOT / '.local/storage')).resolve(),
                   semantic_search=os.environ.get('DECISION_ROOM_SEMANTIC_SEARCH', 'false').lower() == 'true',
                   embedding_model=os.environ.get('DECISION_ROOM_EMBEDDING_MODEL', 'text-embedding-3-small'),
                   embedding_dimensions=int(os.environ.get('DECISION_ROOM_EMBEDDING_DIMENSIONS', '1536')))
