"""Literal interpretation is fixed before any recalculation; no numeric matching search."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
import re

VERSION = 'posthoc-precision-v1'
SPACES = ' \u00a0\u202f\u2009'


class Uncertain(ValueError):
    pass


@dataclass(frozen=True)
class Literal:
    displayed: Decimal
    scale: Decimal
    decimals: int
    percent: bool
    explicit_sign: bool

    def public(self):
        return {'scale': str(self.scale), 'decimals': self.decimals,
                'percent': self.percent, 'explicit_sign': self.explicit_sign}


def spanish_convention(literals):
    """Requires positive decimal-comma evidence and no conflicting decimal-dot form."""
    evidence = False
    for literal in literals:
        raw = re.sub(r'[+−\-%]|mil(?:lones)?|[kM]', '', literal).strip()
        if re.search(r'\d,\d{1,2}(?!\d)|\d(?:\.\d{3})+,\d+', raw):
            evidence = True
        if re.search(r'\d,\d+\.\d|\d\.\d{1,2}(?!\d)|\d\.\d{4,}',raw):
            return False
    return evidence


def parse_literal(text, *, spanish=False):
    raw = text.strip().replace('−','-')
    if len(raw) > 100 or not re.fullmatch(r'[+\-]?\d[\d., \u00a0\u202f\u2009]*(?:%|mil|millones|k|M)?', raw):
        raise Uncertain('Unsupported or ambiguous numeric literal.')
    suffix = re.search(r'(millones|mil|k|M|%)$', raw)
    unit = suffix.group() if suffix else ''
    if suffix: raw = raw[:suffix.start()].strip()
    scale = Decimal({'mil':'1000','k':'1000','millones':'1000000','M':'1000000'}.get(unit,'1'))
    explicit = raw.startswith(('+','-'))
    sign = '-' if raw.startswith('-') else ''
    unsigned = raw.lstrip('+-')
    # A dot with three digits or a comma with three digits has two plausible conventions.
    if not spanish and ('.' in unsigned or ',' in unsigned):
        raise Uncertain('No accredited decimal convention.')
    if unsigned.count(',') > 1: raise Uncertain('Multiple decimal separators.')
    integer, comma, fraction = unsigned.partition(',')
    if comma and (not fraction.isdigit()): raise Uncertain('Invalid decimal fraction.')
    if '.' in integer and any(s in integer for s in SPACES):
        raise Uncertain('Mixed grouping separators.')
    groups = re.split(r'[. \u00a0\u202f\u2009]', integer)
    if len(groups)>1 and (not 1<=len(groups[0])<=3 or any(len(g)!=3 for g in groups[1:])):
        raise Uncertain('Invalid grouping.')
    if any(not g.isdigit() for g in groups): raise Uncertain('Invalid digits.')
    try:
        number = Decimal(sign + ''.join(groups) + ('.'+fraction if comma else ''))
    except InvalidOperation:
        raise Uncertain('Invalid decimal.') from None
    return Literal(number,scale,len(fraction),unit=='%',explicit)


def compare(literal, recalculated, *, integer_quantity=False, direction=None):
    """direction is grounded separately: -1 falls, +1 rises; never guessed from the value."""
    number = Decimal(str(recalculated))
    if not number.is_finite() or abs(number.adjusted()) > 60:
        raise Uncertain('Recalculated value outside precision bound.')
    if direction not in (None,-1,1): raise ValueError('Invalid direction.')
    if direction is not None:
        actual_direction = (number>0)-(number<0)
        if actual_direction != direction: return False
        if literal.explicit_sign and (literal.displayed>0)-(literal.displayed<0) != direction:
            return False
        if not literal.explicit_sign: number = abs(number)
    with localcontext() as ctx:
        ctx.prec=100
        displayed = number/literal.scale
        if integer_quantity and literal.scale==1:
            return displayed == literal.displayed and displayed == displayed.to_integral_value()
        return displayed.quantize(Decimal(1).scaleb(-literal.decimals), rounding=ROUND_HALF_UP) == literal.displayed
