"""Untrusted report input, contained Chromium, bounded inventory + PNG snapshot.

Only this dedicated image starts Chrome. No product configuration, credentials or
business files are copied into it. stdout is a bounded receipt, not diagnostic HTML.
"""
import base64
import json
import math
from pathlib import Path
import struct
import sys
import traceback

# -I intentionally excludes the script directory; only this image-owned path is
# admitted, never /tmp (which contains report-controlled bytes).
sys.path.insert(0, '/opt/report')
from chrome import Browser
from inventory import DOM_SCRIPT, build_inventory, validate

MAX_INPUT = 262144
MAX_HEIGHT = 24000
MAX_OUTPUT = 36 * 1024 * 1024
PREFIX = '<!doctype html><html lang="es"><meta charset="utf-8"><meta name="referrer" content="no-referrer"><body style="margin:0;background:white">'
SUFFIX = '</body></html>'


def capture(browser, session, expected):
    # Stop page scripts/animations after stable text and fonts; no source content or
    # CSS is injected into the product snapshot. Canvas/SVG appear as pixels.
    browser.call('Emulation.setScriptExecutionDisabled', {'value':True},session)
    browser.call('Animation.enable', {},session)
    browser.call('Animation.setPlaybackRate', {'playbackRate':0},session)
    metrics = browser.call('Page.getLayoutMetrics', {},session)['cssContentSize']
    width, height = math.ceil(metrics['width']), math.ceil(metrics['height'])
    if width>1280 or not 1<=height<=MAX_HEIGHT:
        raise ValueError('Report dimensions exceed the snapshot bounds.')
    parts=[]
    for top in range(0,height,2000):
        h=min(2000,height-top)
        args={'format':'png','captureBeyondViewport':True,
              'clip':{'x':0,'y':top,'width':1280,'height':h,'scale':1}}
        first=browser.call('Page.captureScreenshot',args,session)['data']
        second=browser.call('Page.captureScreenshot',args,session)['data']
        if first!=second: raise ValueError('Rendered pixels do not stabilize.')
        png=base64.b64decode(first,validate=True)
        if png[:8]!=b'\x89PNG\r\n\x1a\n' or struct.unpack('>II',png[16:24])!=(1280,h):
            raise ValueError('Unexpected snapshot dimensions.')
        parts.append(f'<img alt="Página del informe" width="1280" height="{h}" style="display:block;max-width:100%;height:auto" src="data:image/png;base64,{first}">')
    if browser.evaluate(DOM_SCRIPT,session)!=expected:
        raise ValueError('Report changed between text and pixels.')
    state=browser.evaluate('document.URL',session)
    if state!='about:blank': raise ValueError('Report navigated during capture.')
    capture.snapshot=PREFIX+''.join(parts)+SUFFIX
    if len(capture.snapshot.encode())>20*1024*1024:
        raise ValueError('Snapshot exceeds the output bound.')


def main():
    source=sys.stdin.buffer.read(MAX_INPUT+1)
    if not source or len(source)>MAX_INPUT: raise ValueError('Input bound')
    source.decode('utf-8',errors='strict')
    path=Path('/tmp/report.html');path.write_bytes(source)
    inventory=validate(build_inventory(path,browser_factory=lambda:Browser(timeout=8),capture=capture))
    if not inventory['text'].strip(): raise ValueError('No visible canonical text.')
    inventory.pop('snapshot',None)  # DOM spans are kept in occurrences; no extra large DOM copy.
    output=json.dumps({'inventory':inventory,'snapshot_html':capture.snapshot},ensure_ascii=False,separators=(',', ':'),allow_nan=False).encode()
    if len(output)>MAX_OUTPUT: raise ValueError('Output bound')
    sys.stdout.buffer.write(output)


if __name__=='__main__':
    try: main()
    except BaseException:
        traceback.print_exc(file=sys.stderr)
        sys.stderr.write('Report rendering unavailable.\n');sys.exit(1)
