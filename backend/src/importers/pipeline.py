"""Import orchestration shared by every extractor: page retrieval, lesson extraction, table-of-contents trees,
crawl limits, duplicate-lesson detection, and the preview structure returned to administrators.

Structure returned by `run_import` (nothing is stored until an administrator saves it):

    {platform, strategy, kind: 'course'|'article'|'reference', title, description, license, sourceUrl, ...,
     items: [ {type: 'lesson', title, url, status, reason, content, sections, ...}
            | {type: 'module', title, url, lessons: [lesson, ...]} ],
     notes: [...], stats: {...}}

Lesson status is 'imported', 'inaccessible' (with the reason), or 'reference' (title and link only).
"""
import re
from urllib.parse import urljoin, urlsplit, urlunsplit

from .dom import json_ld, ld_types, license_info, metadata, page_title, parse
from .fetch import FetchError, Fetcher, validate_url
from .markdown import convert

MAX_LESSON_PAGES = 40
MIN_WORDS = 25
PERMALINK = re.compile(r'\s*[¶§🔗#]\s*$')
TRACKING = re.compile(r'^(utm_[a-z]+|wt\.mc_id|fbclid|gclid|msclkid|mc_cid|mc_eid|ref_src|_hsenc|_hsmi)$', re.I)


def canonical(url):
    """Comparable form of a URL for duplicate detection: no fragment, tracking parameters or trailing slash."""
    parts = urlsplit(url)
    query = '&'.join(kv for kv in parts.query.split('&') if kv and not TRACKING.match(kv.split('=')[0]))
    path = parts.path.rstrip('/') if len(parts.path) > 1 else parts.path or '/'
    return urlunsplit((parts.scheme.lower(), (parts.hostname or '').lower(), path, query, ''))


def tidy(text, limit):
    text = ' '.join((text or '').split())
    return text if len(text) <= limit else text[:limit - 1].rsplit(' ', 1)[0] + '…'


def selector_match(node, selector):
    """Minimal selectors: tag, #id, .class, [attr=value] and combinations such as div.text or div[data-pivot=video]."""
    match = re.fullmatch(r'([a-z0-9-]+)?((?:[#.][\w-]+)*)(?:\[([\w-]+)(?:=([^\]]*))?\])?', selector)
    if not match:
        return False
    tag, rest, attr, value = match.groups()
    if tag and node.tag != tag:
        return False
    for kind, name in re.findall(r'([#.])([\w-]+)', rest):
        if kind == '#' and node.get('id') != name or kind == '.' and name not in node.classes:
            return False
    if attr and (attr not in node.attrs or value is not None and node.get(attr) != value.strip('"\'')):
        return False
    return True


def select_all(root, selector):
    return [n for n in root.iter() if selector_match(n, selector)]


def select(root, selector):
    return next((n for n in root.iter() if selector_match(n, selector)), None)


def content_score(node):
    return sum(len(n.text()) for n in node.find_all(('p', 'pre', 'li', 'td', 'h2', 'h3')))


def main_content(root, preferred=()):
    """The element holding the page's lesson content: a platform selector, else the richest common container."""
    for selector in preferred:
        nodes = select_all(root, selector)
        if nodes:
            return max(nodes, key=content_score)
    for selector in ('article', 'main', '[role=main]', '#content', '#main-content', '.post-content', '.entry-content', '.article-body',
                     '.article-content', '.markdown-body', '.content'):
        nodes = [n for n in select_all(root, selector) if content_score(n) >= 300]
        if nodes:
            return max(nodes, key=content_score)
    return root.find('body') or root


def base_url(root, url):
    base = root.find('base')
    return urljoin(url, base.get('href').strip()) if base is not None and base.get('href').strip() else url


def heading(root, main=None):
    for scope in (main, root):
        if scope is not None:
            h1 = scope.find('h1')
            if h1 is not None and h1.text():
                return PERMALINK.sub('', h1.text())
    meta = metadata(root)
    title = meta.get('og:title') or page_title(root)
    site = meta.get('og:site_name')
    if site:
        title = re.sub(r'\s*[|\-–—]\s*' + re.escape(site) + r'\s*$', '', title)
    return title


def description(root, ld=None):
    for item in ld if ld is not None else json_ld(root):
        if ld_types(item) & {'Course', 'Article', 'TechArticle', 'BlogPosting', 'LearningResource', 'NewsArticle'} and isinstance(item.get('description'), str):
            return tidy(item['description'], 2000)
    meta = metadata(root)
    return tidy(meta.get('og:description') or meta.get('description') or '', 2000)


class Context:
    """State for one import: the fetcher, lessons already seen, page budget and notes for the administrator."""

    def __init__(self, fetcher):
        self.fetcher = fetcher
        self.seen = set()
        self.lesson_pages = 0
        self.notes = []
        self.duplicates = 0
        self.limited = False

    def page(self, url):
        page = self.fetcher.get(url)
        try:
            root = parse(page.text)
        except ValueError as error:
            raise FetchError(str(error), 'too-large')
        return page, root

    def first_visit(self, url):
        key = canonical(url)
        if key in self.seen:
            self.duplicates += 1
            return False
        self.seen.add(key)
        return True

    def lesson(self, title, url, extract):
        """Fetch one lesson page and extract it, or record why it could not be retrieved."""
        entry = {'title': tidy(title, 150), 'url': url}
        if self.lesson_pages >= MAX_LESSON_PAGES:
            self.limited = True
            return dict(entry, **unavailable(f'Not retrieved: the import limit of {MAX_LESSON_PAGES} lesson pages was reached.'))
        self.lesson_pages += 1
        try:
            page, root = self.page(url)
        except FetchError as error:
            return dict(entry, **unavailable(str(error)))
        result = extract(page, root, title)
        result['title'] = entry['title'] or result['title']
        result['url'] = page.url
        return result


def unavailable(reason):
    return {'status': 'inaccessible', 'reason': reason, 'content': '', 'description': '', 'sections': [], 'words': 0,
            'codeBlocks': 0, 'tables': 0, 'figures': 0, 'truncated': False}


def article(page, root, title='', preferred=(), cleanup=None):
    """A single page as one lesson, keeping its heading hierarchy."""
    main = main_content(root, preferred)
    if cleanup:
        cleanup(main)
    name = title or heading(root, main)
    result = convert(main, base_url(root, page.url), name)
    lesson = {'title': tidy(name, 150), 'url': page.url, 'description': '', **result}
    if result['words'] >= MIN_WORDS or result['codeBlocks'] or result['tables']:
        lesson.update(status='imported', reason='Content truncated at 100,000 characters; open the original for the rest.' if result['truncated'] else '')
    else:
        lesson.update(unavailable('No readable lesson text was found on this page. It may be built with JavaScript, need sign-in, or contain only media.'))
    return lesson


# ---------------------------------------------------------------- tables of contents

def own_link(item):
    """The link that names a list item, ignoring links inside its nested lists."""
    for a in item.find_all('a'):
        if any(x.tag in ('ul', 'ol') for x in _between(a, item)):
            continue
        if a.get('href').strip() and not a.get('href').startswith(('#', 'javascript:', 'mailto:')):
            return a
    return None


def _between(node, ancestor):
    for parent in node.ancestors():
        if parent is ancestor:
            return
        yield parent


def nested_lists(item):
    """First-level lists inside an item, including lists wrapped in divs."""
    return [n for n in item.find_all(('ul', 'ol')) if not any(x.tag in ('ul', 'ol') for x in _between(n, item))]


def toc_tree(list_node, base, accept):
    """[{title, url|None, children}] from nested ul/ol markup, in source order. Links failing `accept` are dropped."""
    entries = []
    for item in list_node.children:
        if not hasattr(item, 'tag') or item.tag != 'li':
            continue
        link = own_link(item)
        url = urljoin(base, link.get('href').strip()) if link is not None else None
        url = url if url and accept(url) else None
        if link is not None:
            title = link.text()
        else:
            parts = [c if isinstance(c, str) else c.text() for c in item.children if isinstance(c, str) or c.tag not in ('ul', 'ol')]
            title = ' '.join(' '.join(parts).split())
        children = [child for sub in nested_lists(item) for child in toc_tree(sub, base, accept)]
        for child in children:
            # Links to sections of this same page (#anchors) are part of its lesson, not separate lessons.
            if url and child['url'] and canonical(child['url']) == canonical(url):
                child['url'] = None
        children = [c for c in children if c['url'] or c['children']]
        if (url or children) and title:
            entries.append({'title': title, 'url': url, 'children': children})
    return entries


def flatten(entries):
    for entry in entries:
        if entry['url']:
            yield entry
        yield from flatten(entry['children'])


def tree_items(ctx, tree, extract):
    """Top-level entries with children become modules (their own page, if any, is the module's first lesson);
    deeper levels are kept in order inside their top-level module."""
    items = []
    for entry in tree:
        if entry['children']:
            lessons = [ctx.lesson(e['title'], e['url'], extract) for e in ([entry] if entry['url'] else []) + list(flatten(entry['children'])) if ctx.first_visit(e['url'])]
            if lessons:
                items.append({'type': 'module', 'title': tidy(entry['title'], 150), 'url': entry['url'], 'lessons': lessons})
        elif ctx.first_visit(entry['url']):
            items.append({'type': 'lesson', **ctx.lesson(entry['title'], entry['url'], extract)})
    return items


def below(start_url):
    """URLs on the same site strictly below the start page's own path (unrelated pages are not crawled)."""
    parts = urlsplit(start_url)
    prefix = re.sub(r'/(index|default)\.(html?|php|aspx?)$', '/', parts.path)
    prefix = prefix if prefix.endswith('/') else prefix + '/'
    host = parts.hostname

    def accept(url):
        target = urlsplit(url)
        return target.scheme in ('http', 'https') and target.hostname == host and target.path.startswith(prefix) and target.path.rstrip('/') != prefix.rstrip('/')
    return accept


# ---------------------------------------------------------------- results

def summarize(result):
    lessons = [l for item in result['items'] for l in (item['lessons'] if item['type'] == 'module' else [item])]
    result['stats'] = {'modules': sum(1 for i in result['items'] if i['type'] == 'module'), 'lessons': len(lessons),
                       'imported': sum(1 for l in lessons if l['status'] == 'imported'), 'inaccessible': sum(1 for l in lessons if l['status'] == 'inaccessible'),
                       'reference': sum(1 for l in lessons if l['status'] == 'reference'),
                       'words': sum(l.get('words', 0) for l in lessons), 'codeBlocks': sum(l.get('codeBlocks', 0) for l in lessons), 'tables': sum(l.get('tables', 0) for l in lessons)}
    return result


def course_result(platform, strategy, kind, page, root, title, items, ld=None, policy=None, notes=()):
    ld = json_ld(root) if ld is None else ld
    return {'platform': platform, 'strategy': strategy, 'kind': kind, 'sourceUrl': page.url, 'title': tidy(title, 150), 'description': description(root, ld),
            'license': license_info(root, page.url, ld), 'policy': policy or {'fullContent': True, 'note': ''}, 'items': items, 'notes': list(notes)}


def run_import(url, fetcher=None):
    """Identify the platform, choose its extraction strategy, and return the preview structure."""
    from .platforms import extractor_for  # Platforms build on the helpers above.
    url = validate_url(url)
    ctx = Context(fetcher or Fetcher())
    extractor = extractor_for(url)
    try:
        result = extractor.extract(ctx, url)
    except FetchError as error:
        if error.kind not in ('restricted', 'robots', 'timeout'):
            raise  # Unsafe, missing, unsupported or oversized sources are errors, not references.
        # The site does not let the importer read the start page (sign-in, robots.txt, bot protection, time-out): offer a reference.
        result = {'platform': {'id': extractor.id, 'name': extractor.name}, 'strategy': extractor.strategy, 'kind': 'reference', 'sourceUrl': url, 'title': '',
                  'description': '', 'license': None, 'items': [], 'notes': [],
                  'policy': {'fullContent': False, 'note': f'{error} No content was copied. You can save this course as a reference: enter its title, and employees will open it on the original site.'}}
    result['requestedUrl'] = url
    if ctx.duplicates:
        result['notes'].append(f'{ctx.duplicates} repeated link{"s" if ctx.duplicates != 1 else ""} to the same lesson {"were" if ctx.duplicates != 1 else "was"} imported once.')
    if ctx.limited:
        result['notes'].append(f'Only the first {MAX_LESSON_PAGES} lesson pages are retrieved per import. Later lessons are listed with links to the original.')
    return summarize(result)
