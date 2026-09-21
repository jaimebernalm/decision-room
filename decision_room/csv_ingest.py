"""Strict CSV preparation. Preserve lexical values; no business interpretation."""
import csv
import os
import re
from collections import Counter

import duckdb

from .storage import digest

FORMAT_VERSION = 'csv-text-v1'
MAX_LINE_BYTES = 16 * 1024 * 1024


def identifier(name):
    return '"' + name.replace('"', '""') + '"'


def inspect_csv(path, config, delimiter=None):
    csv.field_size_limit(MAX_LINE_BYTES)
    with path.open(encoding='utf-8-sig', errors='strict', newline='') as stream:
        sample = stream.read(65536)
        if not sample:
            raise ValueError('Empty file: a CSV header is required.')
        if '\x00' in sample:
            raise ValueError('NUL byte found; expected a UTF-8 CSV, not a binary file.')
        if delimiter is None:
            try:
                delimiter = csv.Sniffer().sniff(sample, delimiters=',;\t|').delimiter
            except csv.Error:
                # A long quoted field can cut the sample midway. A simple header
                # still provides a useful delimiter; full rows are validated below.
                first = sample.splitlines()[0]
                counts = {d: len(next(csv.reader([first], delimiter=d))) for d in ',;\t|'}
                delimiter = max(counts, key=counts.get)
        stream.seek(0)
        reader = csv.reader(stream, delimiter=delimiter, quotechar='"', doublequote=True, strict=True)
        header = next(reader)
        if not header or any(not name.strip() for name in header):
            raise ValueError('Every column needs a nonempty header; none are renamed automatically.')
        if len(header) > config.max_columns:
            raise ValueError('Too many columns for the configured import limit.')
        if len({name.casefold() for name in header}) != len(header):
            raise ValueError('Duplicate column headers (case-insensitive). Provide unique names.')
        if any('\x00' in name for name in header):
            raise ValueError('NUL byte found in a column header.')
        count, blank = 0, 0
        for row in reader:
            if not row:
                blank += 1
                continue
            count += 1
            if count > config.max_rows:
                raise ValueError('Too many rows for the configured import limit.')
            if len(row) != len(header):
                raise ValueError(f'CSV record {count} has {len(row)} fields; expected {len(header)}.')
            if any('\x00' in value for value in row):
                raise ValueError(f'NUL byte found in CSV record {count}.')
        return header, delimiter, count, blank


def lexical_hint(values):
    """Hints from a bounded sample, never confirmed types or business meanings."""
    def kind(value):
        if re.fullmatch(r'[+-]?\d+', value):
            return 'integer-like'
        if re.fullmatch(r'[+-]?\d+\.\d+', value):
            return 'decimal-like'
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
            return 'date-like'
        if re.match(r'^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}', value):
            return 'timestamp-like'
        return 'text'
    return dict(Counter(kind(v) for v in values if v not in (None, '')))


def prepare(path, destination, config, delimiter=None):
    header, delimiter, expected_rows, blank_lines = inspect_csv(path, config, delimiter)
    lineage = '__dr_source_record'
    while lineage.casefold() in {name.casefold() for name in header}:
        lineage = '_' + lineage
    destination.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    temporary = destination.with_suffix('.parquet.tmp')
    temporary.unlink(missing_ok=True)
    try:
        with duckdb.connect(config={'threads': 2, 'memory_limit': '512MB',
                                    'max_temp_directory_size': '2GB',
                                    'temp_directory': str(destination.parent / 'scratch'),
                                    'enable_external_access': True}) as db:
            relation = db.read_csv(str(path), header=True, delimiter=delimiter,
                                   columns={name: 'VARCHAR' for name in header},
                                   auto_detect=False, quotechar='"', escapechar='"',
                                   allow_quoted_nulls=False, strict_mode=True,
                                   parallel=False, null_padding=False, ignore_errors=False,
                                   max_line_size=MAX_LINE_BYTES, buffer_size=64 * 1024 * 1024)
            if relation.columns != header:
                raise ValueError('Reader changed column names; import requires explicit correction.')
            relation.project(f'row_number() OVER () AS {identifier(lineage)}, *').write_parquet(
                str(temporary), compression='zstd')
            db.read_parquet(str(temporary)).create_view('prepared')
            actual_rows = db.sql('SELECT count(*) FROM prepared').fetchone()[0]
            if actual_rows != expected_rows:
                raise ValueError(f'CSV/Parquet row count mismatch: {expected_rows} vs {actual_rows}.')
            expressions = []
            for name in header:
                col = identifier(name)
                expressions.extend([f'count(*) FILTER (WHERE {col} IS NULL)',
                                    f'count(*) FILTER (WHERE {col} = \'\')',
                                    f'coalesce(max(length({col})),0)'])
            stats = db.sql('SELECT ' + ','.join(expressions) + ' FROM prepared').fetchone()
            samples = db.sql('SELECT ' + ','.join(f'left({identifier(c)},200)' for c in header) +
                             ' FROM prepared ORDER BY ' + identifier(lineage) + ' LIMIT 5').fetchall()
            columns = [{'name': name, 'storage_type': 'VARCHAR', 'null_count': stats[i*3],
                        'empty_string_count': stats[i*3+1], 'max_characters': stats[i*3+2],
                        'sample_hints': lexical_hint([r[i] for r in samples])}
                       for i, name in enumerate(header)]
        with temporary.open('rb') as stream:
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o400)
        os.replace(temporary, destination)
        return {'row_count': actual_rows, 'columns': columns, 'lineage_column': lineage,
                'parquet_sha256': digest(destination), 'engine_version': duckdb.__version__,
                'profile': {'encoding': 'utf-8-sig', 'delimiter': delimiter,
                            'quote': '"', 'blank_separator_records': blank_lines,
                            'sample_rows': samples, 'sample_values_truncated_at': 200,
                            'format_version': FORMAT_VERSION,
                            'null_rule': 'unquoted empty field = NULL; quoted empty field = empty text',
                            'row_reference': '1-based logical data record, excluding header and blank separators',
                            'transformations': ['Strip UTF-8 BOM for parsing.',
                                                'Decode CSV quoting and escaping.',
                                                'Keep all source columns as text; preserve values, row order and duplicates.',
                                                'Add logical source record ordinal.'],
                            'interpretation_status': 'not_interpreted'}}
    finally:
        temporary.unlink(missing_ok=True)
