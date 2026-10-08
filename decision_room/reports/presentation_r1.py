"""Use frozen R0 composition for both pilot arms, with a text-identical audit copy."""
from html import escape
from html.parser import HTMLParser

from . import presentation_r0

VERSION = presentation_r0.VERSION


class WithoutMarks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.parts=[]; self.hidden=0
    def handle_starttag(self, tag, attrs):
        values=dict(attrs)
        if self.hidden:
            self.hidden+=1;return
        if tag=='div' and 'legend' in values.get('class','').split():
            self.hidden=1;return
        if 'state' in values.get('class','').split():
            attrs=[(k,v) for k,v in attrs if k not in {'class','data-status','data-verified','title','aria-label','tabindex'}]
        self.parts.append('<'+tag+''.join(' '+k+('="'+escape(v,quote=True)+'"' if v is not None else '') for k,v in attrs)+'>')
    def handle_endtag(self,tag):
        if self.hidden:self.hidden-=1;return
        self.parts.append('</'+tag+'>')
    def handle_data(self,data):
        if not self.hidden:self.parts.append(data)
    def handle_entityref(self,name):
        if not self.hidden:self.parts.append('&'+name+';')
    def handle_charref(self,name):
        if not self.hidden:self.parts.append('&#'+name+';')
    def handle_decl(self,decl):self.parts.append('<!'+decl+'>')


def render(document, ledger, raw):
    marked,mapping=presentation_r0.render(document,ledger,raw)
    parser=WithoutMarks();parser.feed(marked)
    plain=''.join(parser.parts)
    source=presentation_r0.TextIndex();source.feed(marked)
    target=presentation_r0.TextIndex();target.feed(plain)
    if source.texts!=target.texts:raise ValueError('Audit copy changed report text.')
    return marked,plain,mapping
