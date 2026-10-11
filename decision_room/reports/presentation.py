"""Presentation policy for engine HTML: receipt checks and the script-free isolated frame.

The agent's HTML is untrusted. It is shown only inside ``<iframe sandbox="">`` (no
scripts, forms, popups or navigation of the parent) with ``srcdoc``, so it inherits the
platform CSP (``frame-src 'self'``) and adds a stricter one of its own. Scripts never run
in the product view: the trial readers judged static renderings, inline SVG charts draw
without them, and a script-drawn chart can be shown from the isolated renderer's static
snapshot instead. The raw bytes are always kept and downloadable as an attachment.
"""
import re
from html.parser import HTMLParser

POLICY_VERSION = 'v1-frame-noscript-1'
MAX_BYTES = 256 * 1024
SANDBOX = ''
CSP = ("default-src 'none'; img-src data:; style-src 'unsafe-inline'; font-src data:; "
       "base-uri 'none'; form-action 'none'")
FORBIDDEN_TAGS = {'base', 'iframe', 'frame', 'frameset', 'object', 'embed', 'applet', 'link', 'portal', 'meta'}
URL_ATTRIBUTES = {'href', 'src', 'action', 'formaction', 'data', 'poster', 'background', 'srcset',
                  'xlink:href', 'ping', 'cite', 'longdesc', 'manifest', 'codebase', 'lowsrc', 'dynsrc'}
REMOTE = re.compile(r'^\s*(?:[a-z][a-z0-9+.-]*:|//|\\\\)', re.I)
ALLOWED_SCHEMES = re.compile(r'^\s*(?:data:image/|#)', re.I)
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
            if not (tag == 'meta' and {k.lower() for k, _ in attrs} <= {'charset'}
                    or tag == 'meta' and dict((k.lower(), (v or '').lower()) for k, v in attrs).get('name') == 'viewport'):
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
            elif name in URL_ATTRIBUTES and REMOTE.match(value) and not ALLOWED_SCHEMES.match(value):
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

    1. A ready static snapshot (platform HTML with images, no agent markup).
    2. Otherwise, a script-free allowed revision without scripts or handlers, provisionally.
    3. Scripted revisions wait for the snapshot, or are blocked if rendering failed.
    The canonical text accompanies every mode when it is ready.
    """
    checked = inspect(raw)
    ready = bool(derived and derived.get('status') == 'ready')
    text = derived.get('canonical_text') if ready else None
    base = dict(policy_version=POLICY_VERSION, receipt=checked['state'], reason=checked['reason'], canonical_text=text)
    if checked['state'] != 'allowed':
        return dict(base, mode='blocked')
    if ready and derived.get('snapshot_html'):
        return dict(base, mode='snapshot', sandbox=SANDBOX, srcdoc=frame_document(derived['snapshot_html'].encode('utf-8')))
    if not checked['scripted']:
        return dict(base, mode='frame', sandbox=SANDBOX, srcdoc=frame_document(raw))
    if derived and derived.get('status') == 'failed':
        return dict(base, mode='blocked', reason='render_failed')
    return dict(base, mode='pending')
