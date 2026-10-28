"""A small, forgiving HTML tree built on the standard library parser, with page-metadata helpers."""
import json
import re
from html.parser import HTMLParser
from urllib.parse import urljoin

VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'source', 'track', 'wbr', 'param'}
# Starting one of these closes an open element of the listed kinds (HTML's implied end tags).
IMPLIED = {'li': {'li'}, 'dt': {'dt', 'dd'}, 'dd': {'dt', 'dd'}, 'tr': {'tr', 'td', 'th'}, 'td': {'td', 'th'}, 'th': {'td', 'th'},
           'option': {'option'}, 'thead': {'tbody', 'tfoot', 'tr', 'td', 'th'}, 'tbody': {'thead', 'tbody', 'tr', 'td', 'th'}, 'tfoot': {'tbody', 'tr', 'td', 'th'}}
BLOCK_CLOSES_P = {'address', 'article', 'aside', 'blockquote', 'details', 'div', 'dl', 'fieldset', 'figure', 'footer', 'form', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                  'header', 'hr', 'main', 'nav', 'ol', 'p', 'pre', 'section', 'table', 'ul'}
SCOPE = {'ul', 'ol', 'table', 'dl', 'div', 'section', 'article', 'main', 'body', 'html', 'td', 'th', 'blockquote'}
MAX_NODES = 250000
MAX_DEPTH = 300


class Node:
    __slots__ = ('tag', 'attrs', 'children', 'parent')

    def __init__(self, tag, attrs=None, parent=None):
        self.tag, self.attrs, self.children, self.parent = tag, attrs or {}, [], parent

    def get(self, name, default=''):
        value = self.attrs.get(name)
        return default if value is None else value

    @property
    def classes(self):
        return set(self.get('class').split())

    def iter(self):
        """Descendant elements in document order (iterative, so deep pages cannot exhaust the stack)."""
        stack = list(reversed([c for c in self.children if isinstance(c, Node)]))
        while stack:
            node = stack.pop()
            yield node
            stack.extend(reversed([c for c in node.children if isinstance(c, Node)]))

    def find_all(self, tag=None, cls=None, id=None, **attrs):
        tags = {tag} if isinstance(tag, str) else set(tag) if tag else None
        for node in self.iter():
            if tags and node.tag not in tags:
                continue
            if cls and cls not in node.classes:
                continue
            if id and node.get('id') != id:
                continue
            if any(node.get(k.replace('_', '-')) != v for k, v in attrs.items()):
                continue
            yield node

    def find(self, tag=None, cls=None, id=None, **attrs):
        return next(self.find_all(tag, cls, id, **attrs), None)

    def ancestors(self):
        node = self.parent
        while node is not None:
            yield node
            node = node.parent

    def text(self, skip=('script', 'style', 'noscript', 'template')):
        parts, stack = [], [self]
        while stack:
            item = stack.pop()
            if isinstance(item, str):
                parts.append(item)
            elif item.tag not in skip:
                stack.extend(reversed(item.children))
        return ' '.join(' '.join(parts).split())

    def raw_text(self):
        """Text with whitespace kept (for code blocks and JSON-LD); <br> becomes a newline. Nested scripts are skipped."""
        parts, stack = [], list(reversed(self.children))
        while stack:
            item = stack.pop()
            if isinstance(item, str):
                parts.append(item)
            elif item.tag == 'br':
                parts.append('\n')
            elif item.tag not in ('script', 'style', 'template'):
                stack.extend(reversed(item.children))
        return ''.join(parts)

    def remove(self):
        if self.parent is not None and self in self.parent.children:
            self.parent.children.remove(self)
        self.parent = None


class TreeBuilder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node('#document')
        self.stack = [self.root]
        self.count = 0

    def handle_starttag(self, tag, attrs):
        self.count += 1
        if self.count > MAX_NODES:
            raise ValueError('The page is too complex to import.')
        attributes = {k.lower(): (v if v is not None else '') for k, v in attrs}
        if tag in BLOCK_CLOSES_P:
            self.close_implied({'p'}, stop=SCOPE | {'button'})
        if tag in IMPLIED:
            self.close_implied(IMPLIED[tag], stop=SCOPE - {'div', 'section', 'article', 'main', 'blockquote', 'td', 'th'} if tag in ('li', 'dt', 'dd') else {'table'})
        node = Node(tag, attributes, self.stack[-1])
        self.stack[-1].children.append(node)
        if tag not in VOID and len(self.stack) < MAX_DEPTH:
            self.stack.append(node)

    def close_implied(self, kinds, stop):
        for i in range(len(self.stack) - 1, 0, -1):
            tag = self.stack[i].tag
            if tag in kinds:
                del self.stack[i:]
                return
            if tag in stop:
                return

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID and self.stack[-1].tag == tag:
            self.stack.pop()

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        if data:
            self.stack[-1].children.append(data)


def parse(text):
    builder = TreeBuilder()
    builder.feed(text)
    builder.close()
    return builder.root


def page_title(root):
    title = root.find('title')
    return title.text() if title else ''


def metadata(root):
    """<meta name|property=...> values (first wins), lower-cased keys."""
    values = {}
    for meta in root.find_all('meta'):
        key = (meta.get('property') or meta.get('name') or meta.get('itemprop')).lower()
        if key and key not in values and meta.get('content').strip():
            values[key] = ' '.join(meta.get('content').split())
    return values


def json_ld(root):
    """Every schema.org object found in JSON-LD blocks, with @graph and lists flattened."""
    items = []

    def collect(value):
        if isinstance(value, list):
            for v in value:
                collect(v)
        elif isinstance(value, dict):
            items.append(value)
            if '@graph' in value:
                collect(value['@graph'])
    for script in root.find_all('script'):
        if script.get('type').lower().strip() == 'application/ld+json':
            try:
                collect(json.loads(script.raw_text().strip()))
            except (ValueError, RecursionError):
                continue
    return items


def ld_types(item):
    kind = item.get('@type', [])
    return set(kind if isinstance(kind, list) else [kind])


def link_href(root, rel, base):
    for node in root.find_all(('link', 'a')):
        if rel in node.get('rel').lower().split() and node.get('href').strip():
            return urljoin(base, node.get('href').strip())
    return ''


CC_NAMES = {'by': 'CC BY', 'by-sa': 'CC BY-SA', 'by-nd': 'CC BY-ND', 'by-nc': 'CC BY-NC', 'by-nc-sa': 'CC BY-NC-SA', 'by-nc-nd': 'CC BY-NC-ND'}


def license_info(root, base, ld):
    """The licence the page declares about itself, if any: rel=license links, JSON-LD, or licence meta tags."""
    url = link_href(root, 'license', base)
    if not url:
        for item in ld:
            value = item.get('license')
            if isinstance(value, dict):
                value = value.get('url') or value.get('@id') or value.get('name')
            if isinstance(value, str) and value.strip():
                url = value.strip()
                break
    meta = metadata(root)
    name = meta.get('license') or meta.get('dc.rights') or meta.get('dcterms.license') or ''
    if not url and not name:
        return None
    match = re.search(r'creativecommons\.org/licenses/([a-z-]+)/([\d.]+)', url or '')
    if match and match.group(1) in CC_NAMES:
        name = f'{CC_NAMES[match.group(1)]} {match.group(2)}'
    elif re.search(r'creativecommons\.org/publicdomain/zero', url or ''):
        name = 'CC0 1.0 (public domain dedication)'
    return {'name': name or 'Licence stated by the source', 'url': url if re.match(r'https?://', url or '') else ''}
