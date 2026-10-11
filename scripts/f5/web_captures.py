"""Full-page captures of the platform's web report view for blind evaluation kits (M4/M5).

Usage: python scripts/f5/web_captures.py BASE_URL KEY_FILE DB_NAME OUT_DIR MODE JOB:BUSINESS:NAME ...

MODE "reader": what the owner sees (check notices visible, details folded, tables initial).
MODE "auditor": the same view without the independent check's notices, so an auditor never
uses them as answers. Both arms get the same treatment: 1440 px wide, scale 1, full page,
sidebar, chat composer and local-copy banners hidden, the HTML arm's sandboxed raster frame
expanded to its pages, then cut into 1500 px slices (OUT_DIR/NAME/page-NN.png).

Headless Chrome with its own profile opens only the platform page; the HTML arm is shown by
the platform as raster images in a sandboxed srcdoc, never the agent's HTML. The view server
must run on a disposable copy of the trial database: the active business is switched in it.
The access key is read from KEY_FILE and never printed.
"""
import asyncio
import base64
import io
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
import psycopg
from psycopg.conninfo import make_conninfo
import websockets
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
WIDTH, SLICE = 1440, 1500
HIDE = '''
[data-slot=sidebar], [data-slot=sidebar-gap], [data-slot=sidebar-container], [data-slot=sidebar-trigger],
form:has([data-slot=input-group]), [data-slot=sidebar-inset] > header button { display: none !important; }
html, body, [data-slot=sidebar-wrapper], main, .assistant-frame, main * { overflow: visible !important; }
html, body, [data-slot=sidebar-wrapper], main, .assistant-frame { height: auto !important; min-height: 0 !important; max-height: none !important; }
'''
# Independent-check output only (auditor mode): per-block notices (role=note), the folded
# "Detalles de la comprobación independiente" disclosure and the incomplete/pending state notices.
# The report's own callouts (aside) are never touched.
HIDE_CHECKS = r'''
(() => {
  const hide = e => e && e.style.setProperty('display','none','important');
  const hidden = {notes: 0, details: 0, state: 0};
  document.querySelectorAll('main [role=note]').forEach(e => { hide(e); hidden.notes++; });
  document.querySelectorAll('main [data-slot=collapsible-trigger]').forEach(t => {
    if (/Detalles de la comprobación independiente/.test(t.textContent)) { hide(t.closest('[data-slot=collapsible]') || t); hidden.details++; }
  });
  document.querySelectorAll('main [role=alert], main [data-slot=alert]').forEach(e => {
    if (/comprobación independiente de cifras/.test(e.textContent)) { hide(e); hidden.state++; }
  });
  return hidden;
})()
'''
EXPAND = r'''
(() => {
  for (const e of [...document.querySelectorAll('main *')].filter(e => e.children.length === 0 &&
      /PDF no disponible todavía/.test(e.textContent)))
    (e.closest('[role=status],[role=alert],div') || e).style.setProperty('display','none','important');
  for (const el of document.querySelectorAll('main *')) {
    const s = getComputedStyle(el);
    if (el.scrollHeight > el.clientHeight + 4 && ['auto','scroll','hidden'].includes(s.overflowY)) {
      el.style.setProperty('height', 'auto', 'important'); el.style.setProperty('max-height', 'none', 'important');
    }
  }
  const frame = document.querySelector('main iframe');
  if (frame) {
    const doc = frame.getAttribute('srcdoc') || '';
    const dims = [...doc.matchAll(/<img[^>]*width="(\d+)"[^>]*height="(\d+)"/g)].map(m => [+m[1], +m[2]]);
    const w = frame.getBoundingClientRect().width;
    frame.style.setProperty('height', Math.ceil(dims.reduce((s, [iw, ih]) => s + ih * Math.min(1, w / iw), 0)) + 'px', 'important');
  }
  window.scrollTo(0, 0);
  return Math.ceil(document.documentElement.scrollHeight);
})()
'''


async def call(ws, method, params=None, *, session=None, _id=[0]):
    _id[0] += 1
    message = {'id': _id[0], 'method': method, 'params': params or {}}
    if session:
        message['sessionId'] = session
    await ws.send(json.dumps(message))
    while True:
        reply = json.loads(await ws.recv())
        if reply.get('id') == _id[0]:
            if 'error' in reply:
                raise RuntimeError(f"{method}: {reply['error']}")
            return reply.get('result', {})


def activate(dsn_db, business):
    # Same server as the product (DECISION_ROOM_DATABASE_URL), switched to the disposable copy.
    from decision_room.config import Config
    with psycopg.connect(make_conninfo(Config.load().dsn, dbname=dsn_db), autocommit=True) as db:
        assert db.execute('SELECT current_database()').fetchone()[0] == dsn_db
        db.execute('UPDATE web_workspace SET active_business_id=%s WHERE singleton', (business,))


async def capture(base_url, key_file, db_name, out_dir, mode, targets, port=9333):
    assert mode in ('reader', 'auditor')
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    profile = tempfile.mkdtemp(prefix='chrome-')
    chrome = subprocess.Popen([CHROME, '--headless=new', f'--remote-debugging-port={port}', f'--user-data-dir={profile}',
                               '--no-first-run', '--no-default-browser-check', '--hide-scrollbars', 'about:blank'],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    manifest = []
    try:
        for _ in range(50):
            try:
                version = httpx.get(f'http://127.0.0.1:{port}/json/version').json()
                break
            except httpx.HTTPError:
                time.sleep(.2)
        async with websockets.connect(version['webSocketDebuggerUrl'], max_size=400_000_000) as ws:
            target = (await call(ws, 'Target.createTarget', {'url': 'about:blank'}))['targetId']
            session = (await call(ws, 'Target.attachToTarget', {'targetId': target, 'flatten': True}))['sessionId']
            run = lambda expr, **kw: call(ws, 'Runtime.evaluate', {'expression': expr, **kw}, session=session)
            metrics = lambda h: call(ws, 'Emulation.setDeviceMetricsOverride',
                                     {'width': WIDTH, 'height': h, 'deviceScaleFactor': 1, 'mobile': False}, session=session)
            for domain in ('Page', 'Runtime'):
                await call(ws, f'{domain}.enable', session=session)
            await metrics(1000)
            await call(ws, 'Page.navigate', {'url': base_url + '/'}, session=session)
            await asyncio.sleep(2)
            token = Path(key_file).read_text().strip()
            status = await run(f"""fetch('/api/login',{{method:'POST',headers:{{'Content-Type':'application/json',
                'X-Decision-Room':'1'}},body:JSON.stringify({{token:{json.dumps(token)}}})}}).then(r=>r.status)""", awaitPromise=True)
            if status['result']['value'] != 200:
                raise RuntimeError('Login to the view server failed.')
            await run("localStorage.setItem('dr-language','es')")
            for spec in targets:
                job, business, name = spec.split(':')
                activate(db_name, business)
                await call(ws, 'Page.navigate', {'url': f'{base_url}/'}, session=session)
                await asyncio.sleep(3)
                for _ in range(10):
                    await run(f"location.hash='#report/{job}'")
                    await asyncio.sleep(3)
                    ready = (await run("location.hash.includes('report/') && /Análisis completado/.test(document.querySelector('main')?.innerText||'')"
                                       " && !!document.querySelector('main iframe, main section')"))['result']['value']
                    if ready:
                        break
                else:
                    raise RuntimeError(f'{name}: report view did not load')
                await asyncio.sleep(3)
                await run(f"(()=>{{const s=document.createElement('style');s.textContent={json.dumps(HIDE)};document.head.appendChild(s)}})()")
                hidden = None
                if mode == 'auditor':
                    hidden = (await run(HIDE_CHECKS, returnByValue=True))['result']['value']
                visible = (await run("""JSON.stringify({notes: [...document.querySelectorAll('main [role=note]')].filter(e => e.offsetParent).length,
                    details: [...document.querySelectorAll('main [data-slot=collapsible-trigger]')].filter(t => t.offsetParent &&
                      /Detalles de la comprobación independiente/.test(t.textContent)).length})"""))['result']['value']
                await asyncio.sleep(1)
                await run(EXPAND)
                await asyncio.sleep(2)
                height = (await run('Math.ceil(document.documentElement.scrollHeight)'))['result']['value']
                await metrics(height)
                await asyncio.sleep(2)
                shot = await call(ws, 'Page.captureScreenshot', {'format': 'png', 'captureBeyondViewport': True,
                                  'clip': {'x': 0, 'y': 0, 'width': WIDTH, 'height': height, 'scale': 1}}, session=session)
                full = Image.open(io.BytesIO(base64.b64decode(shot['data'])))
                folder = out / name
                folder.mkdir(parents=True, exist_ok=True)
                pages = []
                for i, top in enumerate(range(0, full.height, SLICE), 1):
                    path = folder / f'page-{i:02d}.png'
                    full.crop((0, top, WIDTH, min(full.height, top + SLICE))).save(path)
                    pages.append(path.name)
                manifest.append({'name': name, 'job': job, 'mode': mode, 'height': full.height, 'pages': pages,
                                 'check_elements_hidden': hidden, 'check_elements_visible': json.loads(visible)})
                await metrics(1000)
    finally:
        chrome.terminate()
    (out / f'captures-{mode}.json').write_text(json.dumps(manifest, indent=1))
    return manifest


if __name__ == '__main__':
    base_url, key_file, db_name, out_dir, mode, *targets = sys.argv[1:]
    print(json.dumps(asyncio.run(capture(base_url, key_file, db_name, out_dir, mode, targets))))
