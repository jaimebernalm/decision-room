"""Pure neutral report projection and offline HTML; no legacy approval implied."""
from copy import deepcopy
from html import escape

from ..reports import contract
from ..reports.verification import VERSION


def project(draft_verified):
    annotations = draft_verified.get('verification_annotations', [])
    blocks = []
    for path, text, recommendation_id in contract.texts(draft_verified):
        if text:
            blocks.append({'path': path, 'text': text, 'recommendation_id': recommendation_id,
                           'figures': [deepcopy(f) for f in annotations if f['path'] == path]})
    return {'renderer_version': VERSION, 'blocks': blocks}


def render(projection, *, marks=True):
    if projection['renderer_version'] != VERSION:
        raise ValueError('Unsupported report renderer version.')
    blocks = []
    labels = {'verified': 'Verificada', 'unverified': 'No verificada',
              'uncertain': 'Incierta', 'corrected': 'Corregida; alcance semántico no verificado'}
    for block in projection['blocks']:
        text = block['text']; content = ''; end = 0
        if marks:
            for figure in sorted(block['figures'], key=lambda f: f['span']['start']):
                start, stop = figure['span']['start'], figure['span']['end']
                if not end <= start < stop <= len(text) or text[start:stop] != figure['text']:
                    raise ValueError('Verification annotation does not match visible text.')
                label = labels[figure['status']]
                content += escape(text[end:start]) + '<mark title="' + label + '">' + escape(text[start:stop]) + '</mark>'
                end = stop
        content += escape(text[end:])
        tag = 'h1' if block['path'] == '/title' else 'h2' if block['path'].endswith('/title') else 'p'
        blocks.append(f'<{tag}>{content}</{tag}>')
    note = '<footer>Las marcas indican el estado de comprobación. Una corrección numérica no certifica su interpretación.</footer>' if marks else ''
    return '''<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">
<title>Informe</title><style>body{max-width:850px;margin:48px auto;padding:0 24px;color:#18252c;font:17px/1.6 system-ui,sans-serif}h1{font-size:32px;line-height:1.2}h2{font-size:23px;margin-top:2em}p{white-space:pre-wrap;overflow-wrap:anywhere}mark{background:#fff0c2;color:inherit}footer{border-top:1px solid #ccd5da;margin-top:40px;padding-top:16px;font-size:13px;color:#52616a}@media print{body{margin:0;max-width:none}h2{break-after:avoid}}</style></head><body><main>''' + '\n'.join(blocks) + '</main>' + note + '</body></html>'
