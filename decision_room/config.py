import getpass
import os
from decimal import Decimal, localcontext
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
    semantic_search: bool = False
    embedding_model: str = 'text-embedding-3-small'
    embedding_dimensions: int = 1536
    report_engine: str = 'legacy'
    engine_input_tokens: int = 6_000_000
    engine_output_tokens: int = 128_000
    engine_output_per_call: int = 16_000
    engine_calls: int = 60
    engine_seconds: int = 1_200
    engine_usd_cap_micro: int = 1_000_000

    def __post_init__(self):
        if self.report_engine not in ('legacy', 'opencode'):
            raise ValueError('Unsupported report engine.')
        if any(type(v) is not int or v <= 0 for v in (self.engine_input_tokens, self.engine_output_tokens, self.engine_output_per_call, self.engine_calls, self.engine_seconds)) or self.engine_output_per_call > self.engine_output_tokens:
            raise ValueError('Invalid report engine limits.')
        if type(self.engine_usd_cap_micro) is not int or not 0 < self.engine_usd_cap_micro <= (2**63-1)//1000:
            raise ValueError('Invalid engine USD ceiling.')
        maximum = {'text-embedding-3-small': 1536, 'text-embedding-3-large': 3072}
        if self.embedding_model not in maximum or not 256 <= self.embedding_dimensions <= maximum[self.embedding_model]:
            raise ValueError('Unsupported embedding model or dimensions.')

    @classmethod
    def load(cls):
        try:
            value = Decimal(os.environ.get('DECISION_ROOM_ENGINE_USD_CAP', '1.00'))
            if not value.is_finite() or not 0 < value <= Decimal((2**63-1)//1000) / 1_000_000:
                raise ValueError('Invalid engine USD ceiling.')
            with localcontext() as context:
                context.prec = max(28, len(value.as_tuple().digits) + 6)
                amount = value * 1_000_000
            if amount != amount.to_integral_value():
                raise ValueError('Invalid engine USD ceiling.')
            usd_cap = int(amount)
        except (ArithmeticError, ValueError):
            raise ValueError('Engine USD ceiling must be positive with at most six decimals.') from None
        default = make_conninfo(host=str(ROOT / '.local/pgsocket'), port=55432,
                                dbname='decision_room', user=getpass.getuser(), connect_timeout=5)
        return cls(os.environ.get('DECISION_ROOM_DATABASE_URL', default),
                   Path(os.environ.get('DECISION_ROOM_STORAGE', ROOT / '.local/storage')).resolve(),
                   semantic_search=os.environ.get('DECISION_ROOM_SEMANTIC_SEARCH', 'false').lower() == 'true',
                   embedding_model=os.environ.get('DECISION_ROOM_EMBEDDING_MODEL', 'text-embedding-3-small'),
                   embedding_dimensions=int(os.environ.get('DECISION_ROOM_EMBEDDING_DIMENSIONS', '1536')),
                   report_engine=os.environ.get('DECISION_ROOM_REPORT_ENGINE', 'legacy'),
                   engine_input_tokens=int(os.environ.get('DECISION_ROOM_ENGINE_INPUT_TOKENS', '6000000')),
                   engine_output_tokens=int(os.environ.get('DECISION_ROOM_ENGINE_OUTPUT_TOKENS', '128000')),
                   engine_output_per_call=int(os.environ.get('DECISION_ROOM_ENGINE_OUTPUT_PER_CALL', '16000')),
                   engine_calls=int(os.environ.get('DECISION_ROOM_ENGINE_CALLS', '60')),
                   engine_seconds=int(os.environ.get('DECISION_ROOM_ENGINE_SECONDS', '1200')),
                   engine_usd_cap_micro=usd_cap)
