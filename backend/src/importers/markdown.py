"""Convert a page's main content into ShimentoX lesson Markdown without rewording, reordering or summarising it.

Kept: headings (relative hierarchy), paragraphs, bullet and numbered lists (nested), tables, code blocks with their
language, quotes, definition lists and links. Images and diagrams are kept as links to the original file, because
the importer does not copy media. Navigation, ads, forms, scripts and similar page furniture are left out.
"""
import re
from urllib.parse import urljoin, urlsplit

from .dom import Node

SKIP = {'script', 'style', 'noscript', 'template', 'svg', 'canvas', 'form', 'button', 'input', 'select', 'textarea', 'nav', 'footer',
        'aside', 'dialog', 'object', 'embed', 'audio', 'video', 'picture', 'source', 'track', 'map', 'head', 'meta', 'link'}
INLINE = {'a', 'abbr', 'b', 'bdi', 'bdo', 'cite', 'code', 'data', 'del', 'dfn', 'em', 'font', 'i', 'ins', 'kbd', 'mark', 'q', 's', 'samp',
          'small', 'span', 'strong', 'sub', 'sup', 'time', 'tt', 'u', 'var', 'wbr', 'br', 'img', 'math', 'nobr'}
HEADINGS = {'h1': 1, 'h2': 2, 'h3': 3, 'h4': 4, 'h5': 5, 'h6': 6}
NOISE = re.compile(r'(^|[\s_-])(nav|navbar|navigation|menu|breadcrumbs?|sidebar|share|sharing|social|comments?|related|recommended|newsletter|subscribe|'
                   r'advert|advertisement|ads?|adsbygoogle|sponsor|promo|cookie|consent|banner|popup|modal|toolbar|feedback|rating|author-bio|'
                   r'pagination|pager|print-only|sr-only|visually-hidden|skip-link|edit-link|table-of-contents|toc)($|[\s_-])', re.I)
BLOCK_START = re.compile(r'^(```|#{2,4} |:::|\||[-*•]\s|\d+[.)]\s)')
MAX_CONTENT = 100000


def hidden(node):
    style = node.get('style').replace(' ', '').lower()
    return 'hidden' in node.attrs or node.get('aria-hidden') == 'true' or 'display:none' in style or 'visibility:hidden' in style


def noise(node):
    if node.tag in ('main', 'article', 'body'):
        return False
    if node.get('role') in ('navigation', 'banner', 'contentinfo', 'search', 'complementary', 'dialog'):
        return True
    return NOISE.search(' '.join([node.get('class'), node.get('id')])) is not None


def language(node):
    for candidate in [node, *node.find_all('code'), *list(node.ancestors())[:3]]:
        for value in candidate.get('class').split() + [candidate.get('data-lang'), candidate.get('data-code-lang'), candidate.get('data-language')]:
            match = re.match(r'(?:language-|lang-|brush:)?([A-Za-z][\w+#.-]{0,20})$', value or '')
            if match and (value.startswith(('language-', 'lang-')) or candidate.get('data-lang') == value or candidate.get('data-code-lang') == value or candidate.get('data-language') == value):
                return match.group(1).lower()
    return ''


def neutral(text):
    """Text that would otherwise be read as a Markdown block marker gets an invisible prefix."""
    return '​' + text if BLOCK_START.match(text) else text


class Converter:
    def __init__(self, base_url, title=''):
        self.base = base_url
        self.title = ' '.join(title.split()).lower()
        self.blocks = []   # ('heading', level, text) | ('text', markdown) | ('code', lang, code) | ('list'|'table', markdown)
        self.inline = []
        self.stats = {'codeBlocks': 0, 'tables': 0, 'figures': 0, 'lists': 0}
        self.skipped_title = False
        self.pending = []

    # ---------------------------------------------------------------- inline content
    def flush(self):
        text = ' '.join(''.join(self.inline).split())
        self.inline = []
        if text:
            self.blocks.append(('text', neutral(text)))

    def inline_text(self, node):
        """Markdown for an inline run: links, code, bold and italic. Nested lists/tables are excluded by the caller."""
        if isinstance(node, str):
            return node
        if node.tag in SKIP or hidden(node):
            return ''
        if node.tag == 'br':
            return ' '
        if node.tag == 'img':
            return self.figure_link(node, inline=True)
        inner = ''.join(self.inline_text(c) for c in node.children)
        compact = ' '.join(inner.split())
        if not compact:
            return inner if inner and not inner.strip() else ''
        pad = lambda s: (' ' if inner[:1].isspace() else '') + s + (' ' if inner[-1:].isspace() else '')
        if node.tag == 'a':
            if compact in ('¶', '§', '#', '🔗') or 'headerlink' in node.classes:
                return ''  # Heading permalink glyphs.
            href = urljoin(self.base, node.get('href').strip())
            if re.match(r'https?://', href) and '](' not in compact and '[' not in compact and not compact.startswith('Figure:'):
                return pad(f'[{compact}]({href.replace(" ", "%20").replace(")", "%29")})')
            return inner
        if node.tag in ('code', 'kbd', 'samp', 'tt') and '`' not in compact:
            return pad(f'`{compact}`')
        if node.tag in ('strong', 'b') and '*' not in compact:
            return pad(f'**{compact}**')
        if node.tag in ('em', 'i', 'cite', 'dfn') and '*' not in compact:
            return pad(f'*{compact}*')
        return inner

    def figure_link(self, node, inline=False, caption=''):
        src = node.get('src') or node.get('data-src') or node.get('data-original') or ''
        if not src and node.get('srcset'):
            src = node.get('srcset').split(',')[0].split()[0]
        src = urljoin(self.base, src.strip()) if src.strip() else ''
        alt = ' '.join((caption or node.get('alt') or node.get('title')).split())
        if not re.match(r'https?://', src) or src.lower().endswith('.svg') and not alt:
            return ''
        try:
            width = int(re.sub(r'\D', '', node.get('width')) or 0)
        except ValueError:
            width = 0
        # Decorative images (icons, spacers, tracking pixels) carry no lesson content.
        if not alt and (inline or 0 < width < 120):
            return ''
        self.stats['figures'] += 1
        label = f'Figure: {alt}' if alt else 'Figure'
        return f'[{label.replace("[", "(").replace("]", ")")}]({src.replace(" ", "%20").replace(")", "%29")})'

    # ---------------------------------------------------------------- blocks
    def walk(self, node):
        for child in node.children:
            if isinstance(child, str):
                self.inline.append(child)
                continue
            if child.tag in SKIP or hidden(child) or noise(child):
                continue
            tag = child.tag
            if tag in HEADINGS:
                self.flush()
                text = ' '.join(''.join(self.inline_text(c) for c in child.children).split())
                plain = re.sub(r'\s*[¶§🔗#]\s*$', '', child.text()).lower()
                if text and not (not self.skipped_title and plain == self.title):
                    self.blocks.append(('heading', HEADINGS[tag], text))
                elif text:
                    self.skipped_title = True  # The page's own title is the lesson title, not a section.
            elif tag == 'pre':
                self.flush()
                self.code(child)
            elif tag in ('ul', 'ol'):
                self.flush()
                self.list_block(child)
            elif tag == 'table':
                self.flush()
                self.table(child)
            elif tag == 'blockquote':
                self.flush()
                inner = Converter(self.base)
                inner.walk(child)
                inner.flush()
                body = inner.render(heading_map={})
                if body.strip():
                    self.blocks.append(('text', ':::note\n' + body.replace('\n:::', '\n​:::') + '\n:::'))
            elif tag == 'dl':
                self.flush()
                for item in child.find_all(('dt', 'dd')):
                    text = ' '.join(''.join(self.inline_text(c) for c in item.children).split())
                    if text:
                        self.blocks.append(('text', neutral(f'**{text}**' if item.tag == 'dt' and '*' not in text else text)))
            elif tag == 'figure':
                self.flush()
                caption = child.find('figcaption')
                image = child.find('img')
                if child.find('pre'):
                    self.walk(child)
                elif image:
                    link = self.figure_link(image, caption=caption.text() if caption else '')
                    if link:
                        self.blocks.append(('text', link))
                elif child.find('table'):
                    self.walk(child)
                elif caption:
                    self.blocks.append(('text', neutral(caption.text())))
            elif tag == 'img':
                link = self.figure_link(child)
                if link:
                    self.flush()
                    self.blocks.append(('text', link))
            elif tag == 'iframe':
                src = urljoin(self.base, child.get('src').strip())
                if re.match(r'https://', src):
                    self.flush()
                    self.blocks.append(('text', f'[Embedded media on the original page: {child.get("title") or urlsplit(src).hostname}]({src})'))
            elif tag == 'details':
                self.flush()
                summary = child.find('summary')
                if summary:
                    self.blocks.append(('text', neutral(f'**{summary.text()}**')))
                    summary_index = child.children.index(summary) if summary in child.children else -1
                    rest = Node('div', parent=child)
                    rest.children = [c for i, c in enumerate(child.children) if i != summary_index]
                    self.walk(rest)
                else:
                    self.walk(child)
            elif tag in ('hr',):
                self.flush()
            elif tag in ('code', 'tt') and child.find('pre') is not None:
                self.walk(child)
            elif tag in INLINE:
                self.inline.append(self.inline_text(child))
            elif tag == 'p':
                self.flush()
                self.inline.append(''.join(self.inline_text(c) for c in child.children))
                self.flush()
            else:
                # Other containers (div, section, custom elements) are structural: keep walking in order.
                if tag in ('div', 'section', 'article', 'main', 'header', 'li', 'figcaption', 'center'):
                    self.flush()
                self.walk(child)
                if tag in ('div', 'section', 'article', 'main', 'header', 'center'):
                    self.flush()

    def code(self, node):
        text = node.raw_text().replace('\r\n', '\n').replace('\r', '\n').replace('\t', '    ')
        lines = [l.rstrip() for l in text.split('\n')]
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        if not lines:
            return
        # A line starting with ``` inside the code would end the fence early.
        lines = ['​' + l if l.lstrip().startswith('```') else l for l in lines]
        self.stats['codeBlocks'] += 1
        self.blocks.append(('code', language(node), '\n'.join(lines)))

    def list_block(self, node):
        self.pending = []
        self.list_items(node, 0)
        self.end_list()

    def end_list(self):
        if self.pending:
            self.stats['lists'] += 1
            self.blocks.append(('list', '\n'.join(self.pending)))
            self.pending = []

    def list_items(self, node, depth):
        """Items as indented '-'/'N.' lines. A code block or table inside an item ends the current list block,
        is emitted in place, and the list continues afterwards with its original numbering."""
        ordered = node.tag == 'ol'
        try:
            number = int(node.get('start') or 1)
        except ValueError:
            number = 1
        for item in node.children:
            if not isinstance(item, Node) or item.tag != 'li' or hidden(item) or noise(item):
                continue
            state = {'parts': [], 'emitted': False, 'line': '  ' * depth + (f'{number}.' if ordered else '-')}
            self.item_children(item.children, depth, state)
            self.emit_item(state)
            if state['emitted']:
                number += 1

    def emit_item(self, state):
        text = ' '.join(''.join(state['parts']).split())
        state['parts'] = []
        if not text:
            return
        if state['emitted']:
            # Text that follows a nested code block or list inside the same item.
            self.end_list()
            self.blocks.append(('text', neutral(text)))
        else:
            self.pending.append(f"{state['line']} {text}")
            state['emitted'] = True

    def item_children(self, children, depth, state):
        for child in children:
            if isinstance(child, str):
                state['parts'].append(child)
            elif child.tag in SKIP or hidden(child):
                continue
            elif child.tag in ('ul', 'ol'):
                self.emit_item(state)
                self.list_items(child, depth + 1 if state['emitted'] else depth)
            elif child.tag in ('pre', 'table'):
                self.emit_item(state)
                self.end_list()
                self.code(child) if child.tag == 'pre' else self.table(child)
            elif child.tag in INLINE and child.find(('pre', 'ul', 'ol', 'table')) is None:
                state['parts'].append(self.inline_text(child))
            else:
                # Wrappers inside an item (p, div, section...) contribute their text and nested structure in order.
                state['parts'].append(' ')
                self.item_children(child.children, depth, state)
                state['parts'].append(' ')

    def table(self, node):
        rows = []
        for row in node.find_all('tr'):
            # Rows of nested tables belong to those tables.
            if next((a for a in row.ancestors() if a.tag == 'table'), None) is not node:
                continue
            cells = [c for c in row.children if isinstance(c, Node) and c.tag in ('td', 'th')]
            if cells:
                rows.append((cells, all(c.tag == 'th' for c in cells) or any(a.tag == 'thead' for a in row.ancestors() if a is not node)))
        if not rows:
            return
        width = max(len(cells) for cells, _ in rows)
        if width == 1 or len(rows) == 1 and width <= 2:
            # Layout tables (one column, or a single short row) hold ordinary content rather than tabular data.
            for cells, _ in rows:
                for cell in cells:
                    self.walk(cell)
                    self.flush()
            return
        render = lambda cell: ' '.join(''.join(self.inline_text(c) for c in cell.children).split()).replace('|', '\\|') or ' '
        lines = []
        for index, (cells, _) in enumerate(rows):
            values = [render(c) for c in cells] + [' '] * (width - len(cells))
            lines.append('| ' + ' | '.join(values) + ' |')
            if index == 0:
                lines.append('|' + '|'.join(['---'] * width) + '|')
        self.stats['tables'] += 1
        self.blocks.append(('table', '\n'.join(lines)))

    # ---------------------------------------------------------------- output
    def heading_map(self):
        """Map the levels used in the content to ##, ### and ####, keeping their relative order."""
        levels = sorted({b[1] for b in self.blocks if b[0] == 'heading'})
        return {level: min(index, 2) + 2 for index, level in enumerate(levels)}

    def render(self, heading_map=None):
        mapping = self.heading_map() if heading_map is None else heading_map
        out = []
        for block in self.blocks:
            if block[0] == 'heading':
                out.append('#' * mapping.get(block[1], 4) + ' ' + block[2])
            elif block[0] == 'code':
                out.append(f'```{block[1]}\n{block[2]}\n```')
            else:
                out.append(block[1])
        return '\n\n'.join(out)


def convert(node, base_url, title=''):
    """Lesson Markdown for a content element, plus the section outline and content statistics."""
    converter = Converter(base_url, title)
    converter.walk(node)
    converter.flush()
    mapping = converter.heading_map()
    sections = [{'level': mapping[b[1]] - 1, 'title': re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', b[2]).replace('**', '').replace('`', '')}
                for b in converter.blocks if b[0] == 'heading']
    markdown = converter.render(mapping)
    truncated = len(markdown) > MAX_CONTENT
    if truncated:
        cut = markdown.rfind('\n\n', 0, MAX_CONTENT - 200)
        markdown = markdown[:cut if cut > 0 else MAX_CONTENT - 200]
        if markdown.count('```') % 2:
            markdown += '\n```'
    plain = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', markdown)
    words = len(re.findall(r'[\w’\'-]+', plain))
    return {'content': markdown, 'sections': sections, 'words': words, 'truncated': truncated, **converter.stats}
