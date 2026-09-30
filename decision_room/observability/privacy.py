"""Explicit projections plus credential/path filtering for diagnostic text."""
import os
import re

HIDDEN = re.compile(r'(?i)(reasoning|chain.of.thought|authorization|cookie|password|secret|api.key|dsn|headers)')


def text(value,limit=500):
    value=str(value or '')
    for key,secret in os.environ.items():
        if re.search(r'(?i)(api.?key|token|secret|password)',key) and len(secret)>=8:
            value=value.replace(secret,'[credencial omitida]')
    value=re.sub(r'sk-[A-Za-z0-9_-]{12,}','[credencial omitida]',value)
    value=re.sub(r'(?i)(Bearer\s+)[A-Za-z0-9._~+/-]+',r'\1[omitido]',value)
    value=re.sub(r'(?i)((?:api[_-]?key|password|token|secret)\s*[:=]\s*)[\"\x27]?[^\s,;\"\x27]+',r'\1[omitido]',value)
    value=re.sub(r'/(?:Users|home|var/folders)/[^\s\"\x27<>]*','[ruta privada]',value)
    value=re.sub(r'(?i)(?:postgres(?:ql)?|https?)://[^\s\"\x27<>]+','[dirección omitida]',value)
    return value if len(value)<=limit else value[:max(0,limit-1)].rstrip()+'…'


def diagnostic(value,depth=0):
    if depth>8: return '[profundidad limitada]'
    if isinstance(value,dict):
        return {text(k,100):diagnostic(v,depth+1) for k,v in list(value.items())[:100] if not HIDDEN.search(str(k))}
    if isinstance(value,list): return [diagnostic(v,depth+1) for v in value[:100]]
    if isinstance(value,str): return text(value,12000)
    return value
