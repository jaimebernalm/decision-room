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
        # Group by exact string length so $ cannot admit a trailing newline.
        # Use only literal alternatives and anchors, without regex lookaround.
        # Preserve existing constraints in every branch of the intersection.
        groups = {}
        for value in values:
            groups.setdefault(len(value), []).append(value)
        choices = []
        for length, group in groups.items():
            choice = {k: deepcopy(v) for k, v in node.items() if k != 'enum'}
            if length < choice.get('minLength', 0) or length > choice.get('maxLength', length):
                continue
            escaped = [re.sub(r'([\\.^$|?*+()\[\]{}])', r'\\\1', value) for value in group]
            choice.update(minLength=length, maxLength=length, pattern='^(?:' + '|'.join(escaped) + ')$')
            choices.append(choice)
        if not choices:
            continue  # Leave an already-unsatisfiable schema for the guard.
        node.clear()
        node.update(choices[0] if len(choices) == 1 else {'anyOf': choices})
        count -= len(values)
    validate_enum_limits(schema)
    return schema


def validate_strict_schema(schema):
    """Offline gate for the strict-provider invariants we can verify locally.

    Walk serialized nodes once (including unused $defs), not expanded $refs.
    This is a concrete compatibility lint, not a claim to emulate the whole API.
    """
    validate_enum_limits(schema)
    if schema.get('type') != 'object' or 'anyOf' in schema:
        raise ValueError('Strict schema root must be an object, not anyOf. Request not sent.')
    def visit(node,path='$'):
        if isinstance(node,dict):
            types=node.get('type',[])
            if types=='object' or 'object' in types or 'properties' in node:
                properties=node.get('properties',{})
                required=node.get('required')
                if node.get('additionalProperties') is not False:
                    raise ValueError(f'{path}: strict object needs additionalProperties: false. Request not sent.')
                if not isinstance(required,list) or len(required)!=len(properties) or set(required)!=set(properties):
                    raise ValueError(f'{path}: required must equal all properties. Request not sent.')
            for keyword in ('enum','const','pattern'):
                literals=node.get(keyword,[])
                if keyword!='enum':literals=[literals]
                for literal in literals:
                    if isinstance(literal,str) and any(c in literal for c in ('\n','\r','\t')):
                        raise ValueError(f'{path}.{keyword}: control character in strict literal. Request not sent.')
            for key,value in node.items():visit(value,path+'/'+key)
        elif isinstance(node,list):
            for i,value in enumerate(node):visit(value,path+'/'+str(i))
    visit(schema)
