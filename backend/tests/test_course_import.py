"""Universal course importer: platform detection, structure preservation, crawl limits, SSRF protection, and the
Add a course → Import from URL workflow through the real HTTP API and SQLite database.

Websites are simulated in memory (transport and DNS are replaced), so these tests need no internet access. The
fixtures follow the markup of the real platforms; backend/tools/import_smoke.py checks the live sites.
"""
from contextlib import closing, contextmanager
import gzip
import json
import socket
import unittest
import uuid
from unittest import mock

from test_portal import Client, PortalFixture
from database import connect
from importers import fetch, run_import
from importers.dom import parse
from importers.fetch import FetchError, Fetcher, validate_url
from importers.markdown import convert
from importers.platforms import detect

PUBLIC_IP = '93.184.216.34'
WORDS = ' '.join(['Lists keep items in order and let programs add, change or remove values as the data grows.'] * 3)

MS_MODULE = '''<html><head><title>Organize data with collections - Training | Microsoft Learn</title><meta name="description" content="Organize related data with lists."></head>
<body><main><h1>Organize data with collections</h1><ul id="unit-list">
<li><a class="unit-title" href="1-introduction">Introduction</a></li>
<li><a class="unit-title" href="2-store-data-with-lists">Store and manage data with lists</a></li>
<li><a class="unit-title" href="3-knowledge-check">Module assessment</a></li></ul></main></body></html>'''


def ms_unit(title, body):
    return f'''<html><body><div id="unit-inner-section"><h1 id="module-unit-title">{title}</h1><div class="xp-tag"><span class="visually-hidden">Completed</span></div>
<ul id="module-unit-metadata" class="metadata"><li>10 minutes</li></ul><div id="module-unit-content">
<div class="zone has-pivot" data-pivot="video"><iframe src="https://learn-video.azurefd.net/vod/player?id=1"></iframe><div class="TIP"><p>Tip</p><p>See the Text and images tab for more details!</p></div></div>
<div class="zone has-pivot" data-pivot="text">{body}</div></div></div>
<section id="site-user-feedback-footer"><h2>Feedback</h2><p>Was this page helpful?</p></section></body></html>'''


MS_LISTS = ms_unit('Store and manage data with lists', f'''<p>A <strong>list</strong> is an ordered collection of values. {WORDS}</p>
<h2 id="creating-a-list">Creating a list</h2><pre><code class="lang-python">colors = ["red", "green"]
print(colors)</code></pre><h3>Lists of lists</h3><p>Lists can contain other lists.</p>
<h2>Common list operations</h2><table><tr><th>Operation</th><th>What it does</th></tr><tr><td><code>len(list)</code></td><td>Counts items | size</td></tr><tr><td><code>list.pop()</code></td><td>Removes the last item</td></tr></table>''')
MS_PATH = '''<html><body><h1>Get started with Python programming</h1>
<div data-bi-name="module"><a aria-hidden="true" href="../../modules/organize-data/"></a><a href="../../modules/organize-data/">Organize data with collections</a></div>
<div data-bi-name="module"><a href="../../modules/repeat-actions/">Repeat actions with loops</a></div></body></html>'''
MS_LOOPS = '''<html><body><h1>Repeat actions with loops</h1><ul id="unit-list"><li><a class="unit-title" href="1-introduction">Introduction</a></li>
<li><a class="unit-title" href="https://learn.microsoft.com/en-us/training/modules/organize-data/2-store-data-with-lists">Store and manage data with lists</a></li></ul></body></html>'''

OCW_COURSE = '''<html><head><script type="application/ld+json">{"@context":"https://schema.org","@type":"WebPage","name":"Introduction to Computer Science | EECS | MIT OpenCourseWare",
"description":"An introductory course for students with little programming experience.","license":"https://creativecommons.org/licenses/by-nc-sa/4.0/"}</script>
<meta name="description" content="An introductory course for students with little programming experience."></head><body>
<nav class="course-nav" aria-label="Course materials"><ul>
<li class="course-nav-list-item"><div class="course-nav-parent"><a class="nav-link" href="/courses/6-0001-intro/pages/syllabus/">Syllabus</a></div><ul class="course-nav-child-nav"></ul></li>
<li class="course-nav-list-item"><div class="course-nav-parent"><a class="nav-link" href="/courses/6-0001-intro/pages/lecture-notes/">Lecture Notes</a></div>
<ul class="course-nav-child-nav"><li><a href="/courses/6-0001-intro/pages/lecture-notes/lecture-1/">Lecture 1</a></li>
<li><a href="/courses/6-0001-intro/pages/lecture-notes/lecture-2/">Lecture 2</a></li>
<li><a href="/courses/6-0001-intro/pages/syllabus/">Syllabus</a></li>
<li><a href="/courses/another-course/pages/unrelated/">Another course</a></li></ul></li>
<li class="course-nav-list-item"><div class="course-nav-parent"><a href="https://www.youtube.com/watch?v=abc">YouTube playlist</a></div></li>
<li class="course-nav-list-item"><div class="course-nav-parent"><a class="nav-link" href="/courses/6-0001-intro/pages/assignments/">Assignments</a></div></li>
</ul></nav><nav class="course-nav"><ul><li><a href="/courses/6-0001-intro/pages/syllabus/">Syllabus</a></li></ul></nav>
<div id="course-main-content"><p>Course home.</p></div></body></html>'''


def ocw_page(title, body):
    return f'''<html><body><header><div class="course-content-parent-title">Course</div><h2 class="pb-1 mb-1">{title}</h2></header>
<article class="content"><main id="course-content-section">{body}</main></article><footer>MIT OpenCourseWare footer</footer></body></html>'''


OCW_LECTURE = ocw_page('Lecture 1', f'''<h4 id="shell-vs-editor">Shell vs. Editor</h4><p>{WORDS}</p><ol>
<li><p>Type the code below into the editor.</p><div class="highlight"><pre><code class="language-plaintext" data-lang="plaintext">type(5)
print(3.0-1)</code></pre></div></li><li>Press run<span class="material-icons">check</span></li></ol>
<div class="multiple_choice_buttons"><button>Check</button></div>''')

GFG = f'''<html><head><title>Python Lists - GeeksforGeeks</title>
<script type="application/ld+json">{{"@context":"https://schema.org","@type":"Article","headline":"Python Lists","description":"Lists store ordered collections of items."}}</script></head>
<body><nav class="header-main">Tutorials DSA Interview</nav><h1>Python Lists</h1><div class="article-meta">Last Updated</div>
<div class="text"><p>List is a built-in data structure used to store an ordered collection of items. {WORDS}</p>
<h2 id="creating-a-list"><span>Creating a List</span></h2><p><b>1. Using Square Brackets:</b> Square brackets <code>[]</code> create a list.</p>
<gfg-tabs><gfg-tab slot="tab">Python</gfg-tab><gfg-panel slot="panel" data-code-lang="python3"><code class="language-python3"><div class="highlight"><pre><span class="n">a</span> = [1, 2, 3]
print(a)</pre></div></code></gfg-panel></gfg-tabs>
<h3>Using list() Constructor</h3><p>A list can be built from an iterable such as a <a href="/python/python-tuples/">tuple</a>.</p>
<img src="https://media.geeksforgeeks.org/list.webp" alt="Elements of different types in one list">
<h2>Accessing Elements</h2><ul><li>Use an index<ul><li>Indexes start at 0</li></ul></li><li>Negative indexes count from the end</li></ul>
<div class="adsbygoogle">ADVERTISEMENT TEXT</div></div><div class="comments">Reader comment</div></body></html>'''

COURSERA = '''<html><head><script type="application/ld+json">{"@context":"https://schema.org/","@type":"Course","name":"Programming for Everybody",
"description":"Learn the basics of programming in Python.","provider":{"@type":"CollegeOrUniversity","name":"University of Michigan"},
"syllabusSections":[{"@type":"Syllabus","name":"Chapter One - Why We Program","description":"Why we write programs."},{"@type":"Syllabus","name":"Installing Python","description":"Set up Python."}]}</script></head>
<body><h1>Programming for Everybody</h1><p>Enroll for free.</p></body></html>'''

GUIDE = '''<html><head><title>Data Guide | Example University</title><meta property="og:site_name" content="Example University"></head><body>
<nav class="site-nav"><ul><li><a href="/blog/news">News</a></li><li><a href="/blog/events">Events</a></li><li><a href="/about">About</a></li></ul></nav>
<main><h1>Data Guide<a class="headerlink" href="#top">¶</a></h1><p>Welcome to the guide.</p><div class="toc"><ul>
<li><a href="/guide/basics/">Basics</a><ul><li><a href="/guide/basics/variables">Variables</a></li><li><a href="/guide/basics/#types">Types</a></li></ul></li>
<li><a href="/guide/advanced">Advanced topics</a></li><li><a href="https://other.example-site.org/guide/x">Partner material</a></li>
<li><a href="/guide/basics/variables">Variables again</a></li></ul></div></main></body></html>'''


def guide_page(title, body):
    return f'''<html><body><aside class="sidebar"><ul><li><a href="/guide/basics/">Basics</a></li><li><a href="/guide/advanced">Advanced</a></li></ul></aside>
<main><h1>{title}<a class="headerlink" href="#x">¶</a></h1>{body}</main><footer>Copyright</footer></body></html>'''


ADVANCED = guide_page('Advanced topics', f'''<p>{WORDS}</p><h2>Indexing<a class="headerlink" href="#i">¶</a></h2><p>Index rules.</p><h4>Negative indexes</h4><p>Count from the end.</p>
<h2>Slicing</h2><ol start="3"><li>Choose a start</li><li>Choose a stop</li></ol><blockquote><p>Slices never raise IndexError.</p></blockquote>
<div hidden>Hidden draft text</div><div class="share-buttons">Share on social</div>''')

MANIFEST = '''<?xml version="1.0" encoding="UTF-8"?>
<manifest identifier="safety" xmlns="http://www.imsglobal.org/xsd/imscp_v1p1"><organizations default="org1"><organization identifier="org1"><title>Workplace Safety</title>
<item identifier="m1"><title>Module A: Hazards</title><item identifier="l1" identifierref="r1"><title>Spotting hazards</title></item><item identifier="l2" identifierref="r2"><title>Reporting hazards</title></item></item>
<item identifier="l3" identifierref="r3"><title>Wrap-up</title></item></organization></organizations>
<resources><resource identifier="r1" href="content/a1.html"/><resource identifier="r2" href="content/a2.html"/><resource identifier="r3" href="content/wrap.html"/></resources></manifest>'''


def simple_page(title):
    return f'<html><body><main><h1>{title}</h1><p>{WORDS}</p></main></body></html>'


ML = 'https://learn.microsoft.com/en-us/training/'
OCW = 'https://ocw.mit.edu/courses/6-0001-intro/'
SITE = {
    ML + 'modules/organize-data/': MS_MODULE,
    ML + 'modules/organize-data/1-introduction': ms_unit('Introduction', f'<p>In this module you organize data. {WORDS}</p>'),
    ML + 'modules/organize-data/2-store-data-with-lists': MS_LISTS,
    ML + 'modules/organize-data/3-knowledge-check': ms_unit('Module assessment', '<div id="quiz-root"></div>'),
    ML + 'paths/python-programs/': MS_PATH,
    ML + 'modules/repeat-actions/': MS_LOOPS,
    ML + 'modules/repeat-actions/1-introduction': ms_unit('Introduction', f'<p>Loops repeat work. {WORDS}</p>'),
    OCW: OCW_COURSE,
    OCW + 'pages/syllabus/': ocw_page('Syllabus', f'<h2>Course Meeting Times</h2><p>{WORDS}</p><h2>Grading</h2><table><tr><th>Activity</th><th>Percentage</th></tr><tr><td>Problem sets</td><td>50%</td></tr></table>'),
    OCW + 'pages/lecture-notes/': ocw_page('Lecture Notes', f'<p>Slides and code for each lecture. {WORDS}</p>'),
    OCW + 'pages/lecture-notes/lecture-1/': OCW_LECTURE,
    OCW + 'pages/lecture-notes/lecture-2/': ocw_page('Lecture 2', f'<p>Branching and iteration. {WORDS}</p>'),
    'https://www.geeksforgeeks.org/python/python-lists/': GFG,
    'https://www.coursera.org/learn/python': COURSERA,
    'https://docs.example-university.org/guide/': GUIDE,
    'https://docs.example-university.org/guide/basics/': guide_page('Basics', f'<p>{WORDS}</p><h2 id="types">Types</h2><p>Numbers and text.</p>'),
    'https://docs.example-university.org/guide/basics/variables': guide_page('Variables', f'<p>Names refer to values. {WORDS}</p>'),
    'https://docs.example-university.org/guide/advanced': ADVANCED,
    'https://docs.example-university.org/blog/news': simple_page('News'),
    'https://packages.example-site.org/safety/imsmanifest.xml': (200, {'content-type': 'application/xml'}, MANIFEST),
    'https://packages.example-site.org/safety/content/a1.html': simple_page('Spotting hazards'),
    'https://packages.example-site.org/safety/content/a2.html': simple_page('Reporting hazards'),
    'https://packages.example-site.org/safety/content/wrap.html': simple_page('Wrap-up'),
    'https://blocked.example-site.org/robots.txt': (200, {'content-type': 'text/plain'}, 'User-agent: *\nDisallow: /'),
    'https://blocked.example-site.org/course/': simple_page('Blocked course'),
    'https://secure.example-site.org/course/': (403, {'content-type': 'text/html'}, '<h1>Forbidden</h1>'),
    'https://captcha.example-site.org/course/': '<html><head><title>Just a moment...</title></head><body><div id="cf-browser-verification"></div></body></html>',
    'https://redirect.example-site.org/to-private': (302, {'location': 'https://intranet.example-site.org/admin'}, ''),
    'https://redirect.example-site.org/to-metadata': (302, {'location': 'http://169.254.169.254/latest/meta-data/'}, ''),
    'https://redirect.example-site.org/to-file': (302, {'location': 'file:///etc/passwd'}, ''),
    'https://redirect.example-site.org/loop': (302, {'location': '/loop'}, ''),
    'https://redirect.example-site.org/ok': (301, {'location': 'https://docs.example-university.org/guide/advanced'}, ''),
    'https://files.example-site.org/handbook.pdf': (200, {'content-type': 'application/pdf'}, '%PDF-1.4'),
    'https://huge.example-site.org/declared': (200, {'content-type': 'text/html', 'content-length': str(50 * 1024 * 1024)}, '<p>x</p>'),
    'https://huge.example-site.org/streamed': (200, {'content-type': 'text/html'}, '<p>' + 'x' * (fetch.MAX_PAGE_BYTES + 10) + '</p>'),
    'https://huge.example-site.org/bomb': (200, {'content-type': 'text/html', 'content-encoding': 'gzip'}, gzip.compress(b'<p>' + b'x' * (fetch.MAX_PAGE_BYTES + 10))),
    'https://huge.example-site.org/gzipped': (200, {'content-type': 'text/html', 'content-encoding': 'gzip'}, gzip.compress(simple_page('Compressed page').encode())),
    'https://bad.example-site.org/doctype/imsmanifest.xml': (200, {'content-type': 'text/xml'}, '<?xml version="1.0"?><!DOCTYPE m [<!ENTITY a "aaaa">]><manifest>&a;</manifest>'),
}
DNS = {'intranet.example-site.org': ['10.0.0.7'], 'rebind.example-site.org': [PUBLIC_IP, '127.0.0.1'], 'cgnat.example-site.org': ['100.64.1.1'],
       'mapped.example-site.org': ['::ffff:127.0.0.1'], 'linklocal.example-site.org': ['169.254.169.254']}
REAL_GETADDRINFO = socket.getaddrinfo


class FakeInternet:
    def __init__(self, pages=SITE):
        self.pages, self.requests = pages, []

    def transport(self, url, address, timeout):
        assert fetch.public_address(address), f'connected to a non-public address {address}'
        self.requests.append(url)
        page = self.pages.get(url, self.pages.get(url.split('?')[0]))
        if page is None:
            status, headers, body = 404, {'content-type': 'text/html'}, '<h1>Not found</h1>'
        elif isinstance(page, str):
            status, headers, body = 200, {'content-type': 'text/html; charset=utf-8'}, page
        else:
            status, headers, body = page
        data = body.encode('utf-8') if isinstance(body, str) else body
        chunks = [data[i:i + 65536] for i in range(0, len(data), 65536)] + [b'']
        return fetch.RawResponse(status, headers, lambda size=-1: chunks.pop(0) if chunks else b'')

    @staticmethod
    def getaddrinfo(host, port, *args, **kwargs):
        if host in ('127.0.0.1', 'localhost', '::1'):
            return REAL_GETADDRINFO(host, port, *args, **kwargs)
        if host == 'nowhere.example-site.org':
            raise socket.gaierror('not found')
        return [(socket.AF_INET6 if ':' in ip else socket.AF_INET, socket.SOCK_STREAM, 6, '', (ip, port)) for ip in DNS.get(host, [PUBLIC_IP])]


@contextmanager
def internet(pages=SITE):
    site = FakeInternet(pages)
    with mock.patch.object(fetch, 'TRANSPORT', site.transport), mock.patch.object(fetch.socket, 'getaddrinfo', site.getaddrinfo):
        yield site


def lessons_of(result):
    return [l for item in result['items'] for l in (item['lessons'] if item['type'] == 'module' else [item])]


class UrlSafetyTests(unittest.TestCase):
    def test_rejects_unsafe_addresses_without_network_access(self):
        for url in ['ftp://example.org/x', 'file:///etc/passwd', 'javascript:alert(1)', 'http://localhost/admin', 'http://127.0.0.1/', 'http://[::1]/', 'http://10.0.0.5/',
                    'http://169.254.169.254/latest/meta-data/', 'http://metadata.google.internal/computeMetadata/v1/', 'http://2130706433/', 'http://0x7f.1/', 'http://printer.local/',
                    'http://service.internal/', 'https://user:pass@example.org/', 'https://example.org:8443/', 'http://intranet/', 'https://kubernetes.default.svc/', 'not a url']:
            with self.subTest(url=url), self.assertRaises(FetchError):
                validate_url(url)
        self.assertEqual(validate_url(' https://Learn.Microsoft.com/en-us/training/#units '), 'https://learn.microsoft.com/en-us/training/')

    def test_private_resolution_redirects_and_limits_are_blocked(self):
        with internet():
            for url, kind in [('https://intranet.example-site.org/', 'blocked'), ('https://rebind.example-site.org/', 'blocked'), ('https://cgnat.example-site.org/', 'blocked'),
                              ('https://mapped.example-site.org/', 'blocked'), ('https://linklocal.example-site.org/', 'blocked'),
                              ('https://redirect.example-site.org/to-private', 'blocked'), ('https://redirect.example-site.org/to-metadata', 'blocked'),
                              ('https://redirect.example-site.org/to-file', 'invalid'), ('https://redirect.example-site.org/loop', 'unreachable'),
                              ('https://files.example-site.org/handbook.pdf', 'unsupported'), ('https://huge.example-site.org/declared', 'too-large'),
                              ('https://huge.example-site.org/streamed', 'too-large'), ('https://huge.example-site.org/bomb', 'too-large'),
                              ('https://nowhere.example-site.org/', 'unreachable')]:
                with self.subTest(url=url), self.assertRaises(FetchError) as caught:
                    Fetcher().get(url)
                self.assertEqual(caught.exception.kind, kind, str(caught.exception))
            self.assertIn('Compressed page', Fetcher().get('https://huge.example-site.org/gzipped').text)
            self.assertEqual(Fetcher().get('https://redirect.example-site.org/ok').url, 'https://docs.example-university.org/guide/advanced')
            budget = Fetcher(max_requests=2)
            budget.get('https://docs.example-university.org/guide/')  # robots.txt + page
            with self.assertRaises(FetchError) as caught:
                budget.get('https://docs.example-university.org/guide/advanced')
            self.assertEqual(caught.exception.kind, 'limit')

    def test_robots_rules_and_bot_challenges_are_respected(self):
        with internet() as site:
            with self.assertRaises(FetchError) as caught:
                Fetcher().get('https://blocked.example-site.org/course/')
            self.assertEqual(caught.exception.kind, 'robots')
            self.assertNotIn('https://blocked.example-site.org/course/', site.requests)
            with self.assertRaises(FetchError) as caught:
                Fetcher().get('https://captcha.example-site.org/course/')
            self.assertEqual(caught.exception.kind, 'restricted')
            unreachable = dict(SITE, **{'https://down.example-site.org/robots.txt': (503, {'content-type': 'text/plain'}, 'down'), 'https://down.example-site.org/a': simple_page('A')})
        with internet(unreachable), self.assertRaises(FetchError) as caught:
            Fetcher().get('https://down.example-site.org/a')
        self.assertEqual(caught.exception.kind, 'robots')


class ExtractionTests(unittest.TestCase):
    def test_platform_detection(self):
        expected = {ML + 'modules/x/': 'microsoft-learn', OCW: 'mit-ocw', 'https://www.geeksforgeeks.org/python/python-lists/': 'geeksforgeeks',
                    'https://www.freecodecamp.org/news/a/': 'freecodecamp', 'https://www.coursera.org/learn/python': 'coursera', 'https://www.edx.org/learn/x': 'edx',
                    'https://www.udemy.com/course/x/': 'udemy', 'https://cdn.example-site.org/pkg/imsmanifest.xml': 'ims-manifest', 'https://docs.python.org/3/tutorial/': 'website'}
        for url, platform in expected.items():
            self.assertEqual(detect(url)['id'], platform, url)

    def test_markdown_keeps_hierarchy_lists_tables_code_and_figures(self):
        html = '''<article><h1>Title</h1><p>Intro with <a href="/docs">a link</a> and <code>code</code>.</p><h2>Part one</h2><h4>Detail</h4><p>Text</p>
        <h2>Part two</h2><ul><li>Item<ul><li>Child <b>bold</b></li></ul></li><li>Next</li></ul><ol start="4"><li>Four<pre><code class="language-sql">SELECT 1;
SELECT 2;</code></pre></li><li>Five</li></ol><table><thead><tr><th>A</th><th>B</th></tr></thead><tbody><tr><td>1 | 2</td><td>x</td></tr></tbody></table>
        <figure><img src="diagram.png" alt="Flow"><figcaption>Request flow diagram</figcaption></figure><img src="icon.png" width="16"><nav>Menu</nav><div class="related-posts">More</div>
        <p>- looks like a bullet</p><blockquote><p>Quoted text</p></blockquote></article>'''
        result = convert(parse(html).find('article'), 'https://site.example-site.org/a/page', 'Title')
        md = result['content']
        self.assertNotIn('# Title', md)
        self.assertIn('[a link](https://site.example-site.org/docs)', md)
        self.assertLess(md.index('## Part one'), md.index('### Detail'))
        self.assertLess(md.index('### Detail'), md.index('## Part two'))
        self.assertIn('- Item\n  - Child **bold**\n- Next', md)
        self.assertIn('4. Four\n\n```sql\nSELECT 1;\nSELECT 2;\n```\n\n5. Five', md)
        self.assertIn('| A | B |\n|---|---|\n| 1 \\| 2 | x |', md)
        self.assertIn('[Figure: Request flow diagram](https://site.example-site.org/a/diagram.png)', md)
        self.assertNotIn('icon.png', md)
        self.assertNotIn('Menu', md)
        self.assertNotIn('More', md)
        self.assertIn('​- looks like a bullet', md)
        self.assertIn(':::note\nQuoted text\n:::', md)
        self.assertEqual([s['title'] for s in result['sections']], ['Part one', 'Detail', 'Part two'])
        self.assertEqual((result['codeBlocks'], result['tables'], result['figures']), (1, 1, 1))

    def test_microsoft_learn_module_and_path_keep_units_in_order(self):
        with internet():
            module = run_import(ML + 'modules/organize-data/')
            path = run_import(ML + 'paths/python-programs/')
        self.assertEqual((module['platform']['id'], module['kind'], module['title']), ('microsoft-learn', 'course', 'Organize data with collections'))
        self.assertEqual([(l['title'], l['status']) for l in lessons_of(module)],
                         [('Introduction', 'imported'), ('Store and manage data with lists', 'imported'), ('Module assessment', 'inaccessible')])
        lists = lessons_of(module)[1]
        self.assertIn('```python\ncolors = ["red", "green"]\nprint(colors)\n```', lists['content'])
        self.assertIn('| `len(list)` | Counts items \\| size |', lists['content'])
        self.assertEqual([s['title'] for s in lists['sections']], ['Creating a list', 'Lists of lists', 'Common list operations'])
        for chrome in ('Completed', '10 minutes', 'Text and images tab', 'Was this page helpful', 'learn-video'):
            self.assertNotIn(chrome, lists['content'])
        self.assertEqual([(i['type'], i['title'], [l['title'] for l in i['lessons']]) for i in path['items']],
                         [('module', 'Organize data with collections', ['Introduction', 'Store and manage data with lists', 'Module assessment']),
                          ('module', 'Repeat actions with loops', ['Introduction'])])
        self.assertTrue(any('imported once' in n for n in path['notes']))

    def test_ocw_navigation_becomes_modules_and_lessons(self):
        with internet() as site:
            result = run_import(OCW)
        self.assertEqual(result['title'], 'Introduction to Computer Science')
        self.assertEqual(result['license']['name'], 'CC BY-NC-SA 4.0')
        self.assertEqual([(i['type'], i['title']) for i in result['items']], [('lesson', 'Syllabus'), ('module', 'Lecture Notes'), ('lesson', 'Assignments')])
        self.assertEqual([l['title'] for l in result['items'][1]['lessons']], ['Lecture Notes', 'Lecture 1', 'Lecture 2'])
        self.assertEqual(result['items'][2]['status'], 'inaccessible')
        self.assertIn('HTTP 404', result['items'][2]['reason'])
        lecture = result['items'][1]['lessons'][1]['content']
        self.assertIn('1. Type the code below into the editor.\n\n```plaintext\ntype(5)\nprint(3.0-1)\n```\n\n2. Press run', lecture)
        self.assertNotIn('check', lecture.split('Press run')[1])
        self.assertNotIn('footer', lecture)
        self.assertFalse(any('another-course' in u or 'youtube' in u for u in site.requests), 'Unrelated pages must not be crawled')

    def test_geeksforgeeks_article_keeps_sections_code_and_attribution_links(self):
        with internet():
            result = run_import('https://www.geeksforgeeks.org/python/python-lists/')
        self.assertEqual((result['kind'], result['title'], result['description']), ('article', 'Python Lists', 'Lists store ordered collections of items.'))
        lesson = lessons_of(result)[0]
        md = lesson['content']
        self.assertEqual([s['title'] for s in lesson['sections']], ['Creating a List', 'Using list() Constructor', 'Accessing Elements'])
        self.assertIn('```python3\na = [1, 2, 3]\nprint(a)\n```', md)
        self.assertNotIn('\nPython\n', md)
        self.assertIn('[tuple](https://www.geeksforgeeks.org/python/python-tuples/)', md)
        self.assertIn('- Use an index\n  - Indexes start at 0\n- Negative indexes count from the end', md)
        self.assertIn('Figure: Elements of different types in one list', md)
        for noise in ('ADVERTISEMENT', 'Reader comment', 'Tutorials DSA', 'Last Updated'):
            self.assertNotIn(noise, md)

    def test_generic_table_of_contents_and_single_article(self):
        with internet() as site:
            course = run_import('https://docs.example-university.org/guide/')
            single = run_import('https://docs.example-university.org/guide/advanced')
        self.assertEqual((course['kind'], course['title']), ('course', 'Data Guide'))
        self.assertEqual([(i['type'], i['title']) for i in course['items']], [('module', 'Basics'), ('lesson', 'Advanced topics')])
        self.assertEqual([l['title'] for l in course['items'][0]['lessons']], ['Basics', 'Variables'])
        self.assertFalse(any('/blog/' in u or 'other.example-site.org' in u for u in site.requests))
        self.assertEqual(sum(u.endswith('/guide/basics/variables') for u in site.requests), 1)
        self.assertEqual(single['kind'], 'article')
        md = lessons_of(single)[0]['content']
        self.assertEqual(lessons_of(single)[0]['title'], 'Advanced topics')
        self.assertIn('## Indexing\n\nIndex rules.\n\n### Negative indexes', md)
        self.assertIn('3. Choose a start\n4. Choose a stop', md)
        for text in ('¶', 'Hidden draft', 'Share on social', 'Copyright', 'Basics'):
            self.assertNotIn(text, md)

    def test_course_manifest_and_unsafe_manifest(self):
        with internet():
            result = run_import('https://packages.example-site.org/safety/imsmanifest.xml')
            with self.assertRaises(FetchError):
                run_import('https://bad.example-site.org/doctype/imsmanifest.xml')
        self.assertEqual(result['title'], 'Workplace Safety')
        self.assertEqual([(i['type'], i['title']) for i in result['items']], [('module', 'Module A: Hazards'), ('lesson', 'Wrap-up')])
        self.assertEqual([l['title'] for l in result['items'][0]['lessons']], ['Spotting hazards', 'Reporting hazards'])

    def test_enrollment_platforms_and_restricted_sources_are_reference_only(self):
        with internet():
            coursera = run_import('https://www.coursera.org/learn/python')
            restricted = run_import('https://secure.example-site.org/course/')
            robots = run_import('https://blocked.example-site.org/course/')
            with self.assertRaises(FetchError):
                run_import('https://docs.example-university.org/missing')
        self.assertEqual((coursera['kind'], coursera['policy']['fullContent'], coursera.get('provider')), ('reference', False, 'University of Michigan'))
        self.assertEqual([(l['title'], l['status'], l['content']) for l in lessons_of(coursera)],
                         [('Chapter One - Why We Program', 'reference', ''), ('Installing Python', 'reference', '')])
        self.assertIn('does not sign in', coursera['policy']['note'])
        for result, reason in ((restricted, 'HTTP 403'), (robots, 'robots.txt')):
            self.assertEqual((result['kind'], result['items'], result['policy']['fullContent']), ('reference', [], False))
            self.assertIn(reason, result['policy']['note'])

    def test_page_limit_lists_remaining_lessons_without_retrieving_them(self):
        pages = dict(SITE)
        links = ''.join(f'<li><a href="/many/lesson-{n}">Lesson {n}</a></li>' for n in range(1, 46))
        pages['https://docs.example-university.org/many/'] = f'<html><body><main><h1>Many</h1><nav class="toc"><ol>{links}</ol></nav></main></body></html>'
        for n in range(1, 46):
            pages[f'https://docs.example-university.org/many/lesson-{n}'] = simple_page(f'Lesson {n}')
        with internet(pages) as site:
            result = run_import('https://docs.example-university.org/many/')
        lessons = lessons_of(result)
        self.assertEqual([l['title'] for l in lessons], [f'Lesson {n}' for n in range(1, 46)])
        self.assertEqual(result['stats']['imported'], 40)
        self.assertTrue(all(l['status'] == 'inaccessible' and 'limit' in l['reason'] for l in lessons[40:]))
        self.assertNotIn('https://docs.example-university.org/many/lesson-41', site.requests)
        self.assertTrue(any('first 40 lesson pages' in n for n in result['notes']))


class ImportWorkflowTests(PortalFixture):
    def employee(self):
        client = Client(self.base)
        client.email = f'{uuid.uuid4().hex}@shimentox.com'
        self.assertEqual(self.admin.request('admin/candidates', {'name': 'Import Learner', 'email': client.email, 'password': 'Temporary123!', 'role': 'employee'})[0], 200)
        client.request('auth/login', {'email': client.email, 'password': 'Temporary123!'})
        client.request('auth/password', {'currentPassword': 'Temporary123!', 'password': 'Learning123!'})
        return client

    def preview(self, url, client=None):
        with internet():
            return (client or self.admin).request('manage/import/preview', {'url': url})

    def save(self, token, **fields):
        body = {'token': token, 'mode': 'full', 'rightsConfirmed': True, 'status': 'draft', 'title': f'Imported {uuid.uuid4().hex[:6]}', 'category': 'Technical Skills',
                'difficulty': 'beginner', 'visibility': 'everyone', 'departmentId': None}
        body.update(fields)
        return self.admin.request('manage/import/save', body)

    def test_preview_save_draft_then_edit_keeps_structure_and_attribution(self):
        before = self.course_count()
        status, data, _ = self.preview(ML + 'paths/python-programs/')
        self.assertEqual(status, 200, data)
        self.assertEqual((data['preview']['platform']['name'], data['preview']['stats']['modules'], data['preview']['stats']['lessons']), ('Microsoft Learn', 2, 4))
        self.assertEqual(self.course_count(), before, 'Preview must not write to the database')
        status, saved, _ = self.save(data['token'], durationMinutes=45)
        self.assertEqual(status, 200, saved)
        course = saved['course']
        self.assertEqual((course['status'], course['format'], course['source']['platform'], course['source']['importStatus']), ('draft', 'lessons', 'Microsoft Learn', 'partial'))
        builder = self.admin.request(f'manage/courses/{course["id"]}/builder')[1]
        self.assertEqual([(l['moduleIndex'], l['moduleTitle'], l['title']) for l in builder['lessons']],
                         [(0, 'Organize data with collections', 'Introduction'), (0, 'Organize data with collections', 'Store and manage data with lists'),
                          (0, 'Organize data with collections', 'Module assessment'), (1, 'Repeat actions with loops', 'Introduction')])
        lists = builder['lessons'][1]
        self.assertIn('## Creating a list', lists['content'])
        self.assertEqual(lists['resources'], [{'title': 'Original lesson on Microsoft Learn', 'url': ML + 'modules/organize-data/2-store-data-with-lists'}])
        self.assertEqual(lists['sourceUrl'], ML + 'modules/organize-data/2-store-data-with-lists')
        self.assertEqual(builder['lessons'][2]['content'], '')
        self.assertIn('could not be imported', builder['lessons'][2]['description'])
        report = builder['course']['importReport']
        self.assertEqual([l['status'] for l in report['lessons']], ['imported', 'imported', 'inaccessible', 'imported'])
        self.assertEqual(self.employee_catalog_ids().count(course['id']), 0, 'Imports are never published automatically')
        # Editing in the course builder keeps each lesson's module.
        lessons = [dict(l, title=l['title'] + ' (edited)') if i == 0 else l for i, l in enumerate(builder['lessons'])]
        body = {'id': course['id'], 'format': 'lessons', 'title': course['title'], 'category': course['category'], 'description': course['description'], 'status': 'published', 'lessons': lessons}
        self.assertEqual(self.admin.request('admin/courses', body)[0], 200)
        again = self.admin.request(f'manage/courses/{course["id"]}/builder')[1]['lessons']
        self.assertEqual([l['moduleIndex'] for l in again], [0, 0, 0, 1])
        self.assertIn(course['id'], self.employee_catalog_ids())
        with closing(connect(self.db_path)) as db:
            row = db.execute('SELECT source_url,source_platform,import_status,duration_minutes FROM courses WHERE id=?', (course['id'],)).fetchone()
            self.assertEqual(tuple(row), (ML + 'paths/python-programs', 'Microsoft Learn', 'partial', 45))
            self.assertEqual(db.execute("SELECT action FROM admin_events WHERE target_id=? ORDER BY id LIMIT 1", (course['id'],)).fetchone()[0], 'course_saved')
            self.assertTrue(db.execute("SELECT 1 FROM admin_events WHERE target_id=? AND action='course_imported'", (course['id'],)).fetchone())

    def course_count(self):
        with closing(connect(self.db_path)) as db:
            return db.execute('SELECT COUNT(*) FROM courses').fetchone()[0]

    def employee_catalog_ids(self):
        if not hasattr(self, '_learner'):
            self._learner = self.employee()
        return [c['id'] for c in self._learner.request('courses')[1]['courses']]

    def test_publish_import_shows_modules_and_source_to_employees(self):
        data = self.preview(OCW)[1]
        status, saved, _ = self.save(data['token'], status='published')
        self.assertEqual(status, 200, saved)
        learner = self.employee()
        self.assertEqual(learner.request('learning/enroll', {'courseId': saved['course']['id']})[0], 200)
        page = learner.request(f'learning?courseId={saved["course"]["id"]}')[1]
        self.assertEqual(page['courseInfo']['source'], {'url': 'https://ocw.mit.edu/courses/6-0001-intro', 'platform': 'MIT OpenCourseWare', 'importStatus': 'partial'})
        self.assertNotIn('importReport', page['courseInfo'])
        self.assertEqual([(l['moduleTitle'], l['title']) for l in page['courseLessons']],
                         [('', 'Syllabus'), ('Lecture Notes', 'Lecture Notes'), ('Lecture Notes', 'Lecture 1'), ('Lecture Notes', 'Lecture 2'), ('', 'Assignments')])
        self.assertIn('| Problem sets | 50% |', page['courseLessons'][0]['content'])

    def test_duplicate_imports_are_prevented(self):
        url = 'https://www.geeksforgeeks.org/python/python-lists/'
        first = self.preview(url)[1]
        self.assertIsNone(first['duplicate'])
        self.assertEqual(self.save(first['token'])[0], 200)
        second = self.preview(url + '?utm_source=newsletter#creating-a-list')[1]
        self.assertEqual(second['duplicate']['status'], 'draft')
        status, error, _ = self.save(second['token'])
        self.assertEqual(status, 409)
        self.assertIn('already been imported', error['error'])

    def test_reference_only_rights_confirmation_and_restricted_sources(self):
        coursera = self.preview('https://www.coursera.org/learn/python')[1]
        self.assertEqual(self.save(coursera['token'])[0], 409, 'Enrollment-based content cannot be imported in full')
        status, saved, _ = self.save(coursera['token'], mode='reference', rightsConfirmed=False)
        self.assertEqual(status, 200, saved)
        builder = self.admin.request(f'manage/courses/{saved["course"]["id"]}/builder')[1]
        self.assertEqual([(l['title'], l['content'], l['resources'][0]['url']) for l in builder['lessons']],
                         [('Chapter One - Why We Program', '', 'https://www.coursera.org/learn/python'), ('Installing Python', '', 'https://www.coursera.org/learn/python')])
        self.assertEqual(builder['course']['source']['importStatus'], 'reference')
        guide = self.preview('https://docs.example-university.org/guide/advanced')[1]
        status, error, _ = self.save(guide['token'], rightsConfirmed=False)
        self.assertEqual(status, 400)
        self.assertIn('permitted to reuse', error['error'])
        restricted = self.preview('https://secure.example-site.org/course/')[1]
        self.assertEqual(restricted['preview']['kind'], 'reference')
        status, saved, _ = self.save(restricted['token'], mode='reference', title='Partner security course')
        self.assertEqual(status, 200, saved)
        lessons = self.admin.request(f'manage/courses/{saved["course"]["id"]}/builder')[1]['lessons']
        self.assertEqual([(l['title'], l['resources'][0]['url']) for l in lessons], [('Partner security course', 'https://secure.example-site.org/course/')])

    def test_permissions_validation_and_preview_ownership(self):
        learner = self.employee()
        self.assertEqual(self.preview('https://www.geeksforgeeks.org/python/python-lists/', learner)[0], 403)
        for url in ('http://localhost:5173/api/session', 'http://169.254.169.254/latest/meta-data/', 'https://intranet.example-site.org/', 'https://redirect.example-site.org/to-private', 'gopher://example.org/'):
            status, error, _ = self.preview(url)
            self.assertEqual(status, 400, (url, error))
        self.assertEqual(self.preview('https://docs.example-university.org/missing')[0], 422)
        token = self.preview('https://docs.example-university.org/guide/advanced')[1]['token']
        hr = Client(self.base)
        email = f'{uuid.uuid4().hex}@shimentox.com'
        self.admin.request('admin/candidates', {'name': 'HR Person', 'email': email, 'password': 'Temporary123!', 'role': 'hr'})
        hr.request('auth/login', {'email': email, 'password': 'Temporary123!'})
        hr.request('auth/password', {'currentPassword': 'Temporary123!', 'password': 'Learning123!'})
        status, error, _ = hr.request('manage/import/save', {'token': token, 'mode': 'full', 'rightsConfirmed': True, 'title': 'Taken', 'category': 'Technical Skills'})
        self.assertEqual(status, 410, error)
        self.assertEqual(self.save('not-a-token')[0], 410)
        self.assertEqual(self.save(token, status='archived')[0], 400)


if __name__ == '__main__':
    unittest.main()
