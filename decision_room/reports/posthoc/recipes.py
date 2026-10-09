"""Validate grounded occurrence recipes and recalculate against pinned prepared data.

Matching two interpretations is a semantic hypothesis, never proof that their
shared reading is correct. This module checks their mechanical boundary and never
searches for a filter which reproduces the published value.
"""
from datetime import date
from decimal import Decimal, localcontext
from pathlib import Path
import re
import unicodedata

from ...engine import calculations
from .inventory import canonical, sha

VERSION='posthoc-recipes-v1'
AGGREGATES={'count','sum','mean','min','max'}
ARITY={**{op:1 for op in AGGREGATES}, 'daily_mean':1, 'difference':2,
       'percent_change':2,'share':2,'quotient':2,'percentage_points':4}


class Unsupported(ValueError):
    pass


def normalized(text):
    return ' '.join(unicodedata.normalize('NFKC',text).casefold().split())


def public_catalog(sources):
    """An explicit allowlist; paths and numeric data never reach the interpreter."""
    return [{k:s[k] for k in ('table_id','snapshot_sha256','columns')}
            for s in sources.values()]


def citation(ref, text):
    if not isinstance(ref,dict) or set(ref)!={'span','text'}:
        raise ValueError('Citation requires span and exact visible text.')
    span=ref['span']
    if (not isinstance(span,list) or len(span)!=2 or any(type(v) is not int for v in span)
            or not 0<=span[0]<span[1]<=len(text) or text[slice(*span)]!=ref['text']):
        raise ValueError('Citation is not anchored in the masked visible text.')
    if not any(char.isalnum() for char in ref['text']):
        raise ValueError('Citation has no semantic context.')


def validate(recipe, text, sources):
    if not isinstance(recipe,dict) or set(recipe)!={'operation','operands','unit','direction','evidence'}:
        raise ValueError('Recipe fields do not match the contract.')
    operation=recipe['operation']
    if operation not in ARITY: raise Unsupported('Operation outside the frozen catalogue.')
    operands=recipe['operands']
    if not isinstance(operands,list) or len(operands)!=ARITY[operation]:
        raise ValueError('Incorrect operand count.')
    if recipe['direction'] not in (None,-1,1) or isinstance(recipe['direction'],bool):
        raise ValueError('Invalid direction.')
    evidence=recipe['evidence']
    if not isinstance(evidence,dict) or set(evidence)!={'operation','unit','direction'}:
        raise ValueError('Recipe evidence fields do not match.')
    for key in evidence:
        refs=evidence[key]
        if not isinstance(refs,list) or len(refs)>8 or (not refs and (key!='direction' or recipe['direction'] is not None)):
            raise ValueError('Missing recipe evidence.')
        for ref in refs: citation(ref,text)
    units=[]
    for operand in operands:
        if not isinstance(operand,dict) or set(operand)!={'table_id','snapshot_sha256','aggregate','column','filters','evidence'}:
            raise ValueError('Operand fields do not match the contract.')
        if operand['table_id'] not in sources: raise Unsupported('Unknown table.')
        source=sources[operand['table_id']]
        if operand['snapshot_sha256']!=source['snapshot_sha256']:
            raise ValueError('Snapshot mismatch.')
        aggregate=operand['aggregate']
        if aggregate not in AGGREGATES: raise Unsupported('Unsupported primitive aggregate.')
        if operation in AGGREGATES and aggregate!=operation:
            raise ValueError('Primitive aggregate differs from the operation.')
        if operation=='daily_mean' and aggregate!='sum':
            raise ValueError('Daily mean requires sum, not a mean of observed records.')
        columns={c['name']:c for c in source['columns']}
        rules={'key':'value','operation':aggregate,'column':operand['column'],'filters':operand['filters']}
        calculations.validate([rules],list(columns))
        refs=operand['evidence']
        if not isinstance(refs,dict) or set(refs)!={'column','population','period'}:
            raise ValueError('Operand evidence fields do not match.')
        for key,items in refs.items():
            if not isinstance(items,list) or not 1<=len(items)<=8:
                raise ValueError('Missing operand context; no implicit all-time or all-population.')
            for ref in items: citation(ref,text)
        if aggregate=='count':
            units.append('filas')
        else:
            column=columns[operand['column']]
            if not column.get('numeric'): raise Unsupported('Column is not a trusted numeric quantity.')
            units.append(column.get('unit') or column['name'])
        for condition in operand['filters']:
            if condition['operator']=='in':
                allowed=columns[condition['column']].get('categories')
                if allowed is None or any(v not in allowed for v in condition['values']):
                    raise Unsupported('Filter values absent from the categorical catalogue.')
                population=' '.join(normalized(ref['text']) for ref in operand['evidence']['population'])
                for value in condition['values']:
                    names=[value]+[a['name'] for a in columns[condition['column']].get('aliases',[]) if a['code']==value]
                    if not any(re.search(r'(?<!\w)'+re.escape(normalized(name))+r'(?!\w)',population) for name in names):
                        raise ValueError('Categorical filter lacks a cited code or unambiguous label.')
    if len({normalized(unit) for unit in units})!=1:
        raise Unsupported('Operand units differ.')
    if operation in ('percent_change','share','percentage_points'):
        expected='puntos porcentuales' if operation=='percentage_points' else '%'
    elif operation=='quotient': expected='cociente'
    elif operation=='daily_mean': expected=units[0]+'/día'
    else: expected=units[0]
    if not isinstance(recipe['unit'],str) or normalized(recipe['unit'])!=normalized(expected):
        raise Unsupported('Unit is not declared by the selected column and operation.')
    if operation in ('share','percentage_points'):
        for a,b in [(operands[0],operands[1])]+([(operands[2],operands[3])] if operation=='percentage_points' else []):
            if a['aggregate'] not in ('sum','count') or not subset(a,b): raise Unsupported('Numerator population is not a proven subset of denominator.')
    if operation=='daily_mean':
        dates=[f for f in operands[0]['filters'] if f['operator']=='date_between']
        if len(dates)!=1: raise Unsupported('Daily mean requires one explicit calendar interval.')
    return recipe


def subset(a,b):
    """Structural implication only: no aggregate-value matching and no search."""
    if any(a[k]!=b[k] for k in ('table_id','snapshot_sha256','aggregate','column')):
        return False
    for outer in b['filters']:
        candidates=[f for f in a['filters'] if f['column']==outer['column'] and f['operator']==outer['operator']]
        if outer['operator']=='in':
            if not any(set(f['values'])<=set(outer['values']) for f in candidates): return False
        elif not any(outer['values'][0]<=f['values'][0]<=f['values'][1]<=outer['values'][1] for f in candidates):
            return False
    return True


def semantic(recipe):
    """Compare the entire calculation tuple; independently grounded quotes may differ."""
    return {k:([{n:v for n,v in operand.items() if n!='evidence'} for operand in value]
               if k=='operands' else value) for k,value in recipe.items() if k!='evidence'}


def recalculate(recipe,sources):
    values=[]; receipts=[]; all_integer=True
    with localcontext() as ctx:
        ctx.prec=80
        for n,operand in enumerate(recipe['operands']):
            source=sources[operand['table_id']]; path=Path(source['path'])
            if sha(path.read_bytes())!=source['parquet_sha256']:
                raise ValueError('Prepared data changed before recalculation.')
            columns={c['name']:c for c in source['columns']}
            rule={'key':'value','operation':operand['aggregate'], 'column':operand['column'],'filters':operand['filters']}
            # Empty count is unavailable in V1 even though the engine can return zero.
            count={**rule,'key':'rows','operation':'count','column':None}
            result=calculations.evaluate(path,list(columns),[rule,count],source['table_id'])
            if sha(path.read_bytes())!=source['parquet_sha256']:
                raise ValueError('Prepared data changed during recalculation.')
            if result['metrics']['value'] is None or result['metrics']['rows'] in (None,'0'):
                raise Unsupported('Empty, all-null or invalid selection; no result certified.')
            value=Decimal(result['metrics']['value'])
            if operand['aggregate']=='mean':
                parts=result['displays']['value']['operands']
                # Reconstruct the ratio before the engine's display-only 12-digit formatting.
                value=Decimal(parts[2]['value'])/Decimal(parts[1]['value'])
            values.append(value)
            all_integer=all_integer and (operand['aggregate']=='count' or
                operand['aggregate'] in ('sum','min','max') and columns[operand['column']].get('integer') is True)
            receipts.append({'operand':n,'value':str(value),'result':result,
                             'parquet_sha256':source['parquet_sha256']})
        op=recipe['operation']; a=values[0]
        if op in AGGREGATES: result=a
        elif op=='daily_mean':
            interval=next(f['values'] for f in recipe['operands'][0]['filters'] if f['operator']=='date_between')
            days=(date.fromisoformat(interval[1])-date.fromisoformat(interval[0])).days+1
            result=a/Decimal(days);all_integer=False
        elif op=='difference': result=a-values[1]
        else:
            b=values[1]
            if b<=0 or op=='percentage_points' and values[3]<=0:
                raise Unsupported('Non-positive base is outside the catalogue.')
            if op=='percent_change': result=100*(a-b)/b
            elif op=='share': result=100*a/b
            elif op=='quotient': result=a/b
            else: result=100*a/b-100*values[2]/values[3]
            all_integer=False
    return {'value':str(result),'unit':recipe['unit'],'integer_quantity':bool(all_integer),
            'operands':receipts,'recipe_sha256':sha(canonical(semantic(recipe))),'version':VERSION}
