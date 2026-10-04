"""Bound provider enum size without broadening the set of valid evidence keys.

https://developers.openai.com/api/docs/guides/structured-outputs
Only overflow string enums are represented as exact literal patterns. This is a
wire representation change, not a relaxation of the domain validator.
"""
from copy import deepcopy
import re

MAX_ENUM_VALUES = 1000


def enum_nodes(schema):
    """Walk serialized definitions once; do not expand references or deduplicate occurrences."""
    if isinstance(schema, dict):
        if isinstance(schema.get('enum'), list):
            yield schema
        for value in schema.values():
            yield from enum_nodes(value)
    elif isinstance(schema, list):
        for value in schema:
            yield from enum_nodes(value)


def enum_count(schema):
    return sum(len(node['enum']) for node in enum_nodes(schema))


def validate_enum_limits(schema):
    count = enum_count(schema)
    if count > MAX_ENUM_VALUES:
        raise ValueError(f'Structured output schema has {count} enum values; limit is {MAX_ENUM_VALUES}. Request not sent.')
    for node in enum_nodes(schema):
        values = node['enum']
        if len(values) > 250 and all(isinstance(v, str) for v in values) and sum(map(len, values)) > 15000:
            raise ValueError('Structured output string enum exceeds 15000 characters. Request not sent.')


def bound_enums(schema):
    """Retain small schemas byte-for-byte; compact overflowing string choices only."""
    schema = deepcopy(schema)
    nodes = list(enum_nodes(schema))
    count = sum(len(n['enum']) for n in nodes)
    # Stable ordering makes the effective schema reproducible, including ties.
    for node in sorted(nodes, key=lambda n: len(n['enum']), reverse=True):
        values = node['enum']
        if not values or node.get('type') != 'string' or 'pattern' in node or not all(isinstance(v, str) for v in values):
            continue
        too_long = len(values) > 250 and sum(map(len, values)) > 15000
        if count <= MAX_ENUM_VALUES and not too_long:
            continue
        # Escape regex syntax only (ECMAScript-compatible), not arbitrary spaces
        # or punctuation. The final negative lookahead excludes the trailing
        # newline that the conventional $ anchor otherwise admits.
        escaped = [re.sub(r'([\\.^$|?*+()\[\]{}])', r'\\\1', value) for value in values]
        node['pattern'] = '^(?:' + '|'.join(escaped) + ')$(?![\\s\\S])'
        node.pop('enum')
        count -= len(values)
    validate_enum_limits(schema)
    return schema
