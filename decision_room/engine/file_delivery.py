"""Bounded raw-file collection; never interpret or execute the delivered HTML."""
import base64
import hashlib
import json

from .store import MAX_DRAFT_BYTES

# Runs in an isolated, read-only helper after the agent has stopped. O_NONBLOCK
# prevents a FIFO from hanging before fstat can reject it; no symlinks are read.
SCRIPT = r'''import os,stat,hashlib,base64,json,time
p='/work/informe.html'
try: fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
except FileNotFoundError:
 print(json.dumps({'status':'missing'})); raise SystemExit
with os.fdopen(fd,'rb') as f:
 before=os.fstat(f.fileno())
 if not stat.S_ISREG(before.st_mode): raise ValueError('Not a regular report file')
 h=hashlib.sha256(); size=0; data=bytearray(); deadline=time.monotonic()+20
 while chunk:=f.read(1048576):
  if time.monotonic()>deadline: raise ValueError('Report hashing timed out')
  h.update(chunk); size+=len(chunk)
  if size<=262144: data.extend(chunk)
  else: data.clear()
 if size!=before.st_size: raise ValueError('Report changed during collection')
 result={'status':'oversized' if size>262144 else 'received','bytes':size,'sha256':h.hexdigest()}
 if size<=262144: result['raw']=base64.b64encode(data).decode('ascii')
 print(json.dumps(result))
'''


def script(filename='informe.html'):
    if filename not in ('informe.html', 'informe.json'):
        raise ValueError('Unsupported report filename.')
    return SCRIPT.replace("p='/work/informe.html'", "p='/work/" + filename + "'")


def decode(value):
    result = json.loads(value)
    if result == {'status': 'missing'}:
        return result
    if not isinstance(result, dict) or result.get('status') not in ('received', 'oversized'):
        raise ValueError('Invalid file collection receipt.')
    size, digest = result.get('bytes'), result.get('sha256')
    if type(size) is not int or size < 0 or not isinstance(digest, str) or len(digest) != 64:
        raise ValueError('Invalid file collection metadata.')
    if any(c not in '0123456789abcdef' for c in digest):
        raise ValueError('Invalid file collection hash.')
    oversized = result['status'] == 'oversized'
    if oversized != (size > MAX_DRAFT_BYTES) or set(result) != ({'status', 'bytes', 'sha256'} if oversized else {'status', 'bytes', 'sha256', 'raw'}):
        raise ValueError('Inconsistent file collection receipt.')
    if not oversized:
        raw = base64.b64decode(result['raw'], validate=True)
        if len(raw) != size or hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError('File collection failed its integrity check.')
        result['raw'] = raw
    return result
