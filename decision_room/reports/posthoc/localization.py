"""Traceable label exclusions; never remove occurrences from the inventory/ledger.

Only eligibility for interpretation changes. A mistaken label remains unverified
in evaluation. No rule observes recalculated data, audit labels or model output.
"""
import re
import unicodedata
from .recipes import normalized

VERSION='posthoc-localization-v1'
MONTH=r'(?:enero|ene|febrero|feb|marzo|mar|abril|abr|mayo|may|junio|jun|julio|jul|agosto|ago|septiembre|sept|sep|octubre|oct|noviembre|nov|diciembre|dic)'


def normalized_locations(text):
    chars=[];locations=[]
    for i,char in enumerate(text):
        for c in unicodedata.normalize('NFKC',char).casefold():
            if c.isspace():
                if chars and chars[-1]!=' ':chars.append(' ');locations.append(i)
            else:chars.append(c);locations.append(i)
    return ''.join(chars),locations


def classify(inventory,sources):
    text=inventory['text'];shadow,positions=normalized_locations(text)
    aliases={a['name'] for source in sources.values() for col in source['columns'] for a in col.get('aliases',[])}
    alias_spans=[]
    for alias in sorted(aliases):
        value=normalized(alias)
        if not value:continue
        for match in re.finditer(r'(?<!\w)'+re.escape(value)+r'(?!\w)',shadow):
            alias_spans.append([positions[match.start()],positions[match.end()-1]+1])
    quantities={'unidades','unidad','filas','fila','registros','registro','pedidos','pedido','ventas','euros','puntos'}
    quantities.update(normalized(col.get('unit') or col['name']) for source in sources.values() for col in source['columns'] if col.get('numeric'))
    quantity=re.compile(r'^\s*(?:'+ '|'.join(re.escape(q) for q in sorted(quantities) if q)+r')(?!\w)',re.I)
    result={}
    for item in inventory['occurrences']:
        a,b=item['span'];literal=text[a:b];before=text[max(0,a-80):a];after=text[b:b+80]
        rule=None;foundation=None
        if item['region']=='chart':rule='chart_outside_catalogue'
        elif item['kind']=='date':rule='iso_date_label'
        elif quantity.match(after) or '%' in literal:pass
        else:
            alias=next((s for s in alias_spans if s[0]<=a<b<=s[1]),None)
            if alias is not None:rule='dimension_alias';foundation=alias
            elif a and text[a-1].isalpha() or b<len(text) and text[b].isalpha():rule='identifier_adjacent_letter'
            else:
                word_start=a
                while word_start>0 and not text[word_start-1].isspace():word_start-=1
                word_end=b
                while word_end<len(text) and not text[word_end].isspace():word_end+=1
                if re.search(r'\.(?:csv|parquet|xlsx|json|html|pdf)(?:[.,;:)]|$)',text[word_start:word_end],re.I):
                    rule='filename';foundation=[word_start,word_end]
                elif literal.isdigit():
                    value=int(literal)
                    sections=item.get('context',{}).get('section',[])
                    if any(ref['span'][0]==a and re.match(r'^\d+[.)](?:\s|$)',ref['text']) for ref in sections):
                        rule='heading_ordinal'
                    elif 1<=value<=31 and re.match(r'\s*(?:de\s+)?'+MONTH+r'\b',after,re.I):rule='calendar_day'
                    elif 1<=value<=31 and re.match(r'\s*(?:al|a|–|-)\s*\d{1,2}\s*(?:de\s+)?'+MONTH+r'\b',after,re.I):rule='calendar_day_range'
                    elif len(literal)==4 and 1900<=value<=2100:
                        if ((item.get('context',{}).get('table') or {}).get('cell_is_header')
                            or re.search(r'\b(?:en|año|años|desde|hasta|vs|frente a)\s*$',before,re.I)
                            or re.search(r'\b(?:meses|periodo|período|año|temporada)\s+de\s*$',before,re.I)
                            or re.search(r'\b'+MONTH+r'(?:\s*[–-]\s*'+MONTH+r')?\s*(?:de\s+)?$',before,re.I)
                            or re.match(r'\s*(?:vs|frente a|–|-)\s*(?:19|20|21)\d{2}\b',after,re.I)):
                            rule='calendar_year'
        result[item['id']]={'eligible':rule is None,'rule':rule or 'numeric_target','span':item['span']}
        if foundation is not None:result[item['id']]['foundation_span']=foundation
    return result
