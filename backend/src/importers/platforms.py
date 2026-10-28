"""Source platforms and their extraction strategies.

`extractor_for(url)` picks the most specific extractor: a course manifest, a platform-specific extractor, a
reference-only extractor for enrollment-based platforms, or the generic extractor for other public pages.
Add a platform by subclassing `Extractor` and listing it in `EXTRACTORS`.
"""
import re
import xml.etree.ElementTree as ElementTree
from urllib.parse import urljoin, urlsplit

from .dom import json_ld, ld_types
from .fetch import FetchError
from .pipeline import article, below, canonical, course_result, flatten, heading, nested_lists, select_all, tidy, toc_tree, tree_items


class Extractor:
    id, name, strategy = 'website', 'Website', 'Generic HTML extractor'
    hosts = ()

    def matches(self, url):
        host = urlsplit(url).hostname or ''
        return any(host == h or host.endswith('.' + h) for h in self.hosts)

    def platform(self):
        return {'id': self.id, 'name': self.name}

    def remove(self, root, *selectors):
        for selector in selectors:
            for node in select_all(root, selector):
                node.remove()


# ---------------------------------------------------------------- generic public web pages

class Generic(Extractor):
    """Any public page. Uses, in order: a schema.org Course/ItemList listing lesson pages, a table of contents
    whose links sit below the page's own path, or the page itself as a single article."""

    def matches(self, url):
        return True

    def extract(self, ctx, url):
        page, root = ctx.page(url)
        ctx.first_visit(page.url)
        ld = json_ld(root)
        accept = below(page.url)
        title = heading(root)
        structured = self.structured(ld, page.url, accept)
        if structured:
            items = tree_items(ctx, structured, lambda p, r, t: article(p, r, t))
            return course_result(self.platform(), 'Structured data (schema.org course outline)', 'course', page, root, self.course_title(root, ld) or title, items, ld)
        tree = self.table_of_contents(root, page.url, accept)
        if tree:
            items = tree_items(ctx, tree, lambda p, r, t: article(p, r, t))
            return course_result(self.platform(), 'Table of contents on the course page', 'course', page, root, title, items, ld,
                                 notes=['Lessons were taken from the table of contents on the course page, in its order. Only pages below the course address were retrieved.'])
        lesson = article(page, root)
        return course_result(self.platform(), 'Single article (heading structure preserved)', 'article', page, root, lesson['title'], [{'type': 'lesson', **lesson}], ld)

    @staticmethod
    def course_title(root, ld):
        for item in ld:
            if ld_types(item) & {'Course', 'LearningResource'} and isinstance(item.get('name'), str):
                return item['name']
        return ''

    @staticmethod
    def structured(ld, base, accept):
        """Course parts (hasPart / syllabusSections) or an ItemList that link to lesson pages under this course."""
        for item in ld:
            types = ld_types(item)
            parts = item.get('hasPart') or item.get('syllabusSections') if types & {'Course', 'LearningResource'} else item.get('itemListElement') if 'ItemList' in types else None
            if not isinstance(parts, list):
                continue
            tree = []
            for part in parts:
                part = part.get('item', part) if isinstance(part, dict) else None
                if not isinstance(part, dict):
                    continue
                url = urljoin(base, part.get('url') or part.get('@id') or '')
                name = part.get('name') or part.get('headline') or ''
                if isinstance(name, str) and name.strip() and accept(url):
                    tree.append({'title': name, 'url': url, 'children': []})
            if len(tree) >= 2:
                return tree
        return None

    @staticmethod
    def table_of_contents(root, base, accept):
        hint = re.compile(r'toc|table-of-contents|contents|syllabus|curriculum|course|outline|chapter|lesson|module|unit|sidebar|docs-nav|book|tutorial', re.I)
        best, best_count = None, 0
        for node in root.iter():
            if node.tag not in ('nav', 'aside', 'div', 'section', 'ul', 'ol'):
                continue
            label = ' '.join([node.get('class'), node.get('id'), node.get('aria-label'), node.get('role')])
            if node.tag != 'nav' and not hint.search(label):
                continue
            # Every top-level list in the container, in order (sidebars often have one list per section).
            tree = [entry for top in ([node] if node.tag in ('ul', 'ol') else nested_lists(node)) for entry in toc_tree(top, base, accept)]
            count = len(list(flatten(tree)))
            if count > best_count:
                best, best_count = tree, count
        return best if best_count >= 3 else None


# ---------------------------------------------------------------- Microsoft Learn

class MicrosoftLearn(Extractor):
    """Learning paths (path → modules → units), modules (module → units), single units, and documentation articles."""
    id, name, strategy = 'microsoft-learn', 'Microsoft Learn', 'Microsoft Learn extractor'
    hosts = ('learn.microsoft.com',)
    PATH = re.compile(r'^(/[a-z]{2}-[a-z]{2})?/training/paths/[^/]+/?$')
    MODULE = re.compile(r'^(/[a-z]{2}-[a-z]{2})?/training/modules/[^/]+/?$')

    def extract(self, ctx, url):
        page, root = ctx.page(url)
        ctx.first_visit(page.url)
        path = urlsplit(page.url).path
        if self.PATH.match(path):
            items = []
            for box in select_all(root, 'div[data-bi-name=module]'):
                link = next((a for a in box.find_all('a') if '/modules/' in a.get('href') and a.text()), None)
                if link is None:
                    continue
                module_url = urljoin(page.url, link.get('href'))
                if not ctx.first_visit(module_url):
                    continue
                lessons = self.module_units(ctx, module_url)
                items.append({'type': 'module', 'title': tidy(link.text(), 150), 'url': module_url, 'lessons': lessons})
            return course_result(self.platform(), 'Microsoft Learn learning path (modules and units)', 'course', page, root, heading(root), items)
        if self.MODULE.match(path):
            items = [{'type': 'lesson', **lesson} for lesson in self.units(ctx, page, root)]
            return course_result(self.platform(), 'Microsoft Learn module (units)', 'course', page, root, heading(root), items)
        if '/training/modules/' in path:
            lesson = self.unit(page, root)
            return course_result(self.platform(), 'Microsoft Learn unit', 'article', page, root, lesson['title'], [{'type': 'lesson', **lesson}])
        lesson = article(page, root, preferred=('div.content',), cleanup=lambda main: self.remove(main, 'div#article-header', 'ul.metadata', 'div#ms--content-well-notifications'))
        return course_result(self.platform(), 'Microsoft Learn documentation article', 'article', page, root, lesson['title'], [{'type': 'lesson', **lesson}])

    def module_units(self, ctx, url):
        try:
            page, root = ctx.page(url)
        except FetchError as error:
            ctx.notes.append(f'The module page {url} could not be retrieved: {error}')
            return []
        return self.units(ctx, page, root)

    def units(self, ctx, page, root):
        base = page.url if page.url.endswith('/') else page.url + '/'
        links = [a for a in select_all(root, 'a.unit-title') if a.get('href').strip()]
        return [ctx.lesson(a.text(), urljoin(base, a.get('href').strip()), lambda p, r, t: self.unit(p, r, t)) for a in links if ctx.first_visit(urljoin(base, a.get('href').strip()))]

    def unit(self, page, root, title=''):
        # The unit's video tab duplicates its text tab; the text is imported and the video stays on Microsoft Learn.
        cleanup = lambda main: self.remove(main, 'div[data-pivot=video]', 'div.xp-tag', 'ul#module-unit-metadata')
        heading_node = root.find('h1', id='module-unit-title')
        return article(page, root, title or (heading_node.text() if heading_node else ''), ('div#module-unit-content', 'div#unit-inner-section'), cleanup)


# ---------------------------------------------------------------- MIT OpenCourseWare

class MITOpenCourseWare(Extractor):
    """Course home pages: the course navigation (sections and their sub-pages) becomes modules and lessons."""
    id, name, strategy = 'mit-ocw', 'MIT OpenCourseWare', 'MIT OpenCourseWare extractor'
    hosts = ('ocw.mit.edu',)
    COURSE = re.compile(r'^/courses/([^/]+)/?$')

    def extract(self, ctx, url):
        page, root = ctx.page(url)
        ctx.first_visit(page.url)
        match = self.COURSE.match(urlsplit(page.url).path)
        if not match:
            lesson = self.page_lesson(page, root)
            return course_result(self.platform(), 'MIT OpenCourseWare page', 'article', page, root, lesson['title'], [{'type': 'lesson', **lesson}])
        nav = root.find('nav', cls='course-nav')
        top = nav.find(('ul', 'ol')) if nav is not None else None
        accept = lambda u: urlsplit(u).hostname == 'ocw.mit.edu' and urlsplit(u).path.startswith(f'/courses/{match.group(1)}/') and canonical(u) != canonical(page.url)
        tree = toc_tree(top, page.url, accept) if top is not None else []
        items = tree_items(ctx, tree, lambda p, r, t: self.page_lesson(p, r, t))
        notes = ['Lecture videos stay on MIT OpenCourseWare; their pages are imported as text with links to the videos.'] if any('video' in (i['url'] or '') for i in tree) else []
        title = next((i.get('name') for i in json_ld(root) if isinstance(i.get('name'), str)), '') .split(' | ')[0] or heading(root)
        return course_result(self.platform(), 'MIT OpenCourseWare course navigation', 'course', page, root, title, items, notes=notes)

    def page_lesson(self, page, root, title=''):
        header = root.find('h2', cls='pb-1')
        cleanup = lambda main: self.remove(main, 'span.material-icons', 'div.multiple_choice_buttons', 'div.multiple-choice-solution', 'div.video-embed', 'div.course-image-section')
        return article(page, root, title or (header.text() if header else ''), ('main#course-content-section', 'div#course-main-content'), cleanup)


# ---------------------------------------------------------------- article sites

class GeeksforGeeks(Extractor):
    id, name, strategy = 'geeksforgeeks', 'GeeksforGeeks', 'GeeksforGeeks article extractor'
    hosts = ('geeksforgeeks.org',)

    def extract(self, ctx, url):
        page, root = ctx.page(url)
        ctx.first_visit(page.url)
        # Code tabs repeat the language name as a tab label; the language is kept on the code block itself.
        lesson = article(page, root, preferred=('div.text', 'article'), cleanup=lambda main: self.remove(main, 'gfg-tab', 'div.article-meta', 'div.article-bottom-text', 'div.improved'))
        return course_result(self.platform(), self.strategy, 'article', page, root, lesson['title'], [{'type': 'lesson', **lesson}])


class FreeCodeCamp(Generic):
    id, name, strategy = 'freecodecamp', 'freeCodeCamp', 'freeCodeCamp article extractor'
    hosts = ('freecodecamp.org',)
    matches = Extractor.matches

    def extract(self, ctx, url):
        if '/news/' not in urlsplit(url).path:
            return super().extract(ctx, url)  # Curriculum pages are scripted; the generic strategy reports what is readable.
        page, root = ctx.page(url)
        ctx.first_visit(page.url)
        lesson = article(page, root, preferred=('section.post-content', 'div.post-full-content', 'article'))
        return course_result(self.platform(), self.strategy, 'article', page, root, lesson['title'], [{'type': 'lesson', **lesson}])


# ---------------------------------------------------------------- enrollment-based platforms

class ReferenceOnly(Extractor):
    """Platforms whose course materials are available only to enrolled or subscribed learners. Only the public
    catalogue information (title, description, syllabus outline) is read; lessons link back to the platform."""
    strategy = 'Public course listing (reference only)'
    PLATFORMS = {'coursera.org': 'Coursera', 'edx.org': 'edX', 'udemy.com': 'Udemy', 'linkedin.com': 'LinkedIn Learning', 'pluralsight.com': 'Pluralsight',
                 'udacity.com': 'Udacity', 'skillshare.com': 'Skillshare', 'datacamp.com': 'DataCamp', 'futurelearn.com': 'FutureLearn', 'oreilly.com': "O'Reilly"}

    def __init__(self):
        self.hosts = tuple(self.PLATFORMS)
        self.id, self.name = 'reference', 'Enrollment-based platform'

    def for_url(self, url):
        host = urlsplit(url).hostname or ''
        key = next(h for h in self.hosts if host == h or host.endswith('.' + h))
        clone = ReferenceOnly()
        clone.id, clone.name = key.split('.')[0], self.PLATFORMS[key]
        return clone

    def extract(self, ctx, url):
        page, root = ctx.page(url)
        ld = json_ld(root)
        course = next((i for i in ld if 'Course' in ld_types(i)), {})
        provider = course.get('provider')
        provider = provider.get('name') if isinstance(provider, dict) else provider if isinstance(provider, str) else ''
        title = course.get('name') if isinstance(course.get('name'), str) else heading(root)
        items = []
        for section in course.get('syllabusSections') or []:
            if isinstance(section, dict) and isinstance(section.get('name'), str) and section['name'].strip():
                items.append({'type': 'lesson', 'title': tidy(section['name'], 150), 'url': page.url, 'status': 'reference', 'reason': f'Available to enrolled learners on {self.name}.',
                              'description': tidy(section.get('description') if isinstance(section.get('description'), str) else '', 2000),
                              'content': '', 'sections': [], 'words': 0, 'codeBlocks': 0, 'tables': 0, 'figures': 0, 'truncated': False})
        note = (f'{self.name} course materials are available only to learners enrolled on {self.name}, under its own terms. The importer does not sign in or copy enrolled '
                f'content. This course can be saved as a reference: the public title, description{" and syllabus outline" if items else ""} with links to {self.name}.')
        result = course_result(self.platform(), self.strategy, 'reference', page, root, title, items, ld, policy={'fullContent': False, 'note': note},
                               notes=[] if items else [f'{self.name} does not publish a syllabus outline on this page, so the reference has one lesson that links to the course.'])
        if provider:
            result['provider'] = tidy(provider, 150)
        return result


# ---------------------------------------------------------------- course packages (IMS Content Packaging / SCORM)

class CourseManifest(Extractor):
    """An imsmanifest.xml published on the web: its organisation tree gives the module and lesson structure."""
    id, name, strategy = 'ims-manifest', 'Course package manifest', 'IMS/SCORM manifest (organisation tree)'

    def matches(self, url):
        return urlsplit(url).path.lower().endswith('imsmanifest.xml')

    def extract(self, ctx, url):
        page = ctx.fetcher.get(url, accept=('application/xml', 'text/xml'), max_bytes=2 * 1024 * 1024)
        ctx.first_visit(page.url)
        if re.search(r'<!DOCTYPE|<!ENTITY', page.text, re.I):
            raise FetchError('The manifest declares a DOCTYPE or entities, which are not accepted.', 'unsupported')
        try:
            # The text is already decoded, so its XML declaration (which may name another encoding) is dropped.
            manifest = ElementTree.fromstring(re.sub(r'^\s*<\?xml[^>]*\?>', '', page.text))
        except ElementTree.ParseError:
            raise FetchError('The course manifest is not valid XML.', 'unsupported')
        local = lambda el: el.tag.rsplit('}', 1)[-1]
        children = lambda el, name: [c for c in el if local(c) == name]
        base = page.url
        resources = {}
        for group in children(manifest, 'resources'):
            group_base = urljoin(base, next((v for k, v in group.attrib.items() if k.endswith('base')), ''))
            for res in children(group, 'resource'):
                resource_base = urljoin(group_base, next((v for k, v in res.attrib.items() if k.endswith('base')), ''))
                if res.get('href'):
                    resources[res.get('identifier')] = urljoin(resource_base, res.get('href'))
        organizations = next(iter(children(manifest, 'organizations')), None)
        if organizations is None or not children(organizations, 'organization'):
            raise FetchError('The manifest has no course organisation to import.', 'unsupported')
        default = organizations.get('default')
        organization = next((o for o in children(organizations, 'organization') if o.get('identifier') == default), children(organizations, 'organization')[0])
        site = urlsplit(base).hostname

        def tree(element):
            entries = []
            for item in children(element, 'item'):
                if item.get('isvisible', 'true').lower() == 'false':
                    continue
                title = next((t.text for t in children(item, 'title') if t.text), '') or ''
                href = resources.get(item.get('identifierref'))
                url = (href + item.get('parameters', '')) if href else None
                url = url if url and urlsplit(url).hostname == site else None
                kids = tree(item)
                if title.strip() and (url or kids):
                    entries.append({'title': title.strip(), 'url': url, 'children': kids})
            return entries
        items = tree_items(ctx, tree(organization), lambda p, r, t: article(p, r, t))
        title = next((t.text for t in children(organization, 'title') if t.text), '') or 'Imported course'
        result = {'platform': self.platform(), 'strategy': self.strategy, 'kind': 'course', 'sourceUrl': page.url, 'title': tidy(title, 150), 'description': '',
                  'license': None, 'policy': {'fullContent': True, 'note': ''}, 'items': items, 'notes': []}
        return result


EXTRACTORS = [CourseManifest(), MicrosoftLearn(), MITOpenCourseWare(), GeeksforGeeks(), FreeCodeCamp(), ReferenceOnly()]
GENERIC = Generic()


def extractor_for(url):
    for extractor in EXTRACTORS:
        if extractor.matches(url):
            return extractor.for_url(url) if isinstance(extractor, ReferenceOnly) else extractor
    return GENERIC


def detect(url):
    """Platform name and strategy for a URL, without network access."""
    extractor = extractor_for(url)
    return {'id': extractor.id, 'name': extractor.name, 'strategy': extractor.strategy}
