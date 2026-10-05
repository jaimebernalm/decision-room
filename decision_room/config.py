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
    max_files: int = 10_000  # Internal manifest guard, not a product file quota.
    max_file_bytes: int = 2_000_000_000
    max_batch_bytes: int = 2_000_000_000
    max_columns: int = 256
    max_rows: int = 10_000_000
    owner_presentation: bool = False
    research_continuity: bool = False
    research_validation_recovery: bool = False
    semantic_search: bool = False
    embedding_model: str = 'text-embedding-3-small'
    embedding_dimensions: int = 1536
    sales_panorama: bool = False
    panorama_obligation_guard: bool = False
    review_loop_guard: bool = False
    review_stable_prefix: bool = False
    review_context_budget: bool = False
    review_context_tokens: int = 110000

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
                   panorama_obligation_guard=os.environ.get('DECISION_ROOM_PANORAMA_OBLIGATION_GUARD', 'false').lower() == 'true',
                   review_stable_prefix=os.environ.get('DECISION_ROOM_REVIEW_STABLE_PREFIX', 'false').lower() == 'true',
                   review_context_budget=os.environ.get('DECISION_ROOM_REVIEW_CONTEXT_BUDGET', 'false').lower() == 'true',
                   review_context_tokens=int(os.environ.get('DECISION_ROOM_REVIEW_CONTEXT_TOKENS', '110000')),
                   review_loop_guard=os.environ.get('DECISION_ROOM_REVIEW_LOOP_GUARD', 'false').lower() == 'true',
                   sales_panorama=os.environ.get('DECISION_ROOM_SALES_PANORAMA', 'false').lower() == 'true',
                   owner_presentation=os.environ.get('DECISION_ROOM_OWNER_PRESENTATION', 'false').lower() == 'true',
                   research_continuity=os.environ.get('DECISION_ROOM_RESEARCH_CONTINUITY', 'false').lower() == 'true',
                   research_validation_recovery=os.environ.get('DECISION_ROOM_RESEARCH_VALIDATION_RECOVERY', 'false').lower() == 'true',
                   semantic_search=os.environ.get('DECISION_ROOM_SEMANTIC_SEARCH', 'false').lower() == 'true',
                   embedding_model=os.environ.get('DECISION_ROOM_EMBEDDING_MODEL', 'text-embedding-3-small'),
                   embedding_dimensions=int(os.environ.get('DECISION_ROOM_EMBEDDING_DIMENSIONS', '1536')))
