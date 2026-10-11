"""Presentation policy for engine HTML: receipt checks and what the owner is shown.

The agent's HTML is untrusted and is never rendered in the product origin, not even in
a sandboxed frame: without scripts, markup alone (SVG animation of a link target, relative
URLs under ``frame-src 'self'``) can still navigate a frame. The owner sees the isolated
renderer's static snapshot (platform HTML with images, no agent markup) in a script-free
sandboxed frame, plus the canonical text. Until the snapshot exists the view is pending.
The trial readers judged static renderings too. The raw bytes are always kept and
downloadable as an attachment.
"""
import re
from html.parser import HTMLParser

POLICY_VERSION = 'v1-snapshot-only-1'
MAX_BYTES = 256 * 1024
SANDBOX = ''
CSP = ("default-src 'none'; img-src data:; style-src 'unsafe-inline'; font-src data:; "
       "base-uri 'none'; form-action 'none'")
FORBIDDEN_TAGS = {'base', 'iframe', 'frame', 'frameset', 'object', 'embed', 'applet', 'link', 'portal', 'meta'}
URL_ATTRIBUTES = {'href', 'src', 'action', 'formaction', 'data', 'poster', 'background', 'srcset',
                  'xlink:href', 'ping', 'cite', 'longdesc', 'manifest', 'codebase', 'lowsrc', 'dynsrc'}
# Browsers drop ASCII tab/newline and trim C0 controls/space before parsing a URL.
URL_NOISE = re.compile(r'[\x00-\x20\x7f]')
# Only an in-document fragment or an inline raster/vector image. Relative paths would
# let the framed document navigate itself to product routes (frame-src 'self').
LOCAL_URL = re.compile(r'^(?:#[^#]*|data:image/(?:png|jpeg|gif|webp|svg\+xml)(?:;[a-z0-9=._-]+)*,.*)$', re.I | re.S)
LIST_URL_ATTRIBUTES = {'srcset', 'ping'}
CSS_REMOTE = re.compile(r'(?:@import|url\(\s*[\'"]?\s*(?![\'"]?\s*(?:data:|#)))', re.I)
CHARSET = re.compile(r'^\s*(?:<!--.*?-->\s*)*', re.S)
DOCTYPE = re.compile(r'^\s*<!doctype[^>]*>', re.I)


class _Scan(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.problems, self.style, self.scripted = [], False, False

    def handle_starttag(self, tag, attrs):
        self.inspect(tag, attrs)

    def handle_startendtag(self, tag, attrs):
        self.inspect(tag, attrs)

    def inspect(self, tag, attrs):
        tag = tag.lower()
        if tag in FORBIDDEN_TAGS:
            # Charset declarations are harmless but meta also carries refresh and CSP.
            names = {k.lower() for k, _ in attrs}
            viewport = names == {'name', 'content'} and dict((k.lower(), (v or '').lower()) for k, v in attrs)['name'] == 'viewport'
            if not (tag == 'meta' and (names == {'charset'} or viewport)):
                self.problems.append(f'element:{tag}')
        self.style = tag == 'style'
        if tag == 'script':
            self.scripted = True
        for name, value in attrs:
            name, value = name.lower(), value or ''
            if name.startswith('on'):
                self.scripted = True
            if name == 'srcdoc':
                self.problems.append('attribute:srcdoc')
            elif name in LIST_URL_ATTRIBUTES:
                self.problems.append(f'url:{name}')
            elif name in URL_ATTRIBUTES and not LOCAL_URL.match(URL_NOISE.sub('', value)):
                self.problems.append(f'url:{name}')
            elif name == 'style' and CSS_REMOTE.search(value):
                self.problems.append('css:url')
            elif name.startswith('on') and re.search(r'(?:https?:|javascript:|//)', value, re.I):
                self.problems.append(f'handler:{name}')

    def handle_endtag(self, tag):
        if tag.lower() == 'style':
            self.style = False

    def handle_data(self, data):
        if self.style and CSS_REMOTE.search(data):
            self.problems.append('css:url')


def inspect(raw):
    """Pure receipt check: {'state': 'allowed'|'blocked', 'reason', 'scripted'}. Never raises."""
    def blocked(reason):
        return dict(state='blocked', reason=reason, scripted=False)
    if not isinstance(raw, (bytes, bytearray)) or not raw:
        return blocked('empty')
    if len(raw) > MAX_BYTES:
        return blocked('too_large')
    try:
        text = bytes(raw).decode('utf-8')
    except UnicodeDecodeError:
        return blocked('not_utf8')
    if '\x00' in text:
        return blocked('nul_byte')
    scan = _Scan()
    try:
        scan.feed(text)
        scan.close()
    except Exception:  # noqa: BLE001 - malformed markup is blocked, not an error
        return blocked('unparseable')
    if scan.problems:
        return blocked(sorted(set(scan.problems))[0])
    return dict(state='allowed', reason=None, scripted=scan.scripted)


def receive(raw):
    """Return ('allowed', None) or ('blocked', reason)."""
    checked = inspect(raw)
    return checked['state'], checked['reason']


def frame_document(raw):
    """The srcdoc for an allowed revision: the frame's own CSP goes before any content."""
    text = bytes(raw).decode('utf-8')
    meta = f'<meta http-equiv="Content-Security-Policy" content="{CSP}">'
    doctype = DOCTYPE.match(text)
    if doctype:
        return text[:doctype.end()] + meta + text[doctype.end():]
    return meta + text


def view(raw, derived=None):
    """Choose what the owner sees. ``derived`` is the isolated renderer's result or None.

    1. Receipt blocked: blocked (with canonical text if the renderer produced it).
    2. A ready static snapshot: shown in the script-free frame, with the canonical text.
    3. Rendering failed or produced no snapshot: blocked. Otherwise pending.
    The agent's own markup is never returned as frame content.
    """
    checked = inspect(raw)
    ready = bool(derived and derived.get('status') == 'ready')
    text = derived.get('canonical_text') if ready else None
    base = dict(policy_version=POLICY_VERSION, receipt=checked['state'], reason=checked['reason'], canonical_text=text)
    if checked['state'] != 'allowed':
        return dict(base, mode='blocked')
    if ready and derived.get('snapshot_html'):
        return dict(base, mode='snapshot', sandbox=SANDBOX, srcdoc=frame_document(derived['snapshot_html'].encode('utf-8')))
    if ready or (derived and derived.get('status') == 'failed'):
        return dict(base, mode='blocked', reason='render_failed')
    return dict(base, mode='pending')
