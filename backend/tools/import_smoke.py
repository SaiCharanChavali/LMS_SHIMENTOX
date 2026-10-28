"""Live check of the course importer against real websites (needs internet access; not part of npm test).

    python backend/tools/import_smoke.py                 # the default sample of platforms
    python backend/tools/import_smoke.py URL [URL ...]   # specific pages
    python backend/tools/import_smoke.py --show URL      # also print the first lesson's Markdown

Nothing is written to the database. Use it to confirm a platform still works before relying on it.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from importers import FetchError, run_import  # noqa: E402

SAMPLES = [
    'https://learn.microsoft.com/en-us/training/modules/organize-data-with-collections-python/',
    'https://learn.microsoft.com/en-us/training/paths/get-started-with-python-programs/',
    'https://ocw.mit.edu/courses/6-0001-introduction-to-computer-science-and-programming-in-python-fall-2016/',
    'https://www.geeksforgeeks.org/python/python-lists/',
    'https://www.freecodecamp.org/news/how-to-build-a-simple-data-analyzer-in-python-with-pandas/',
    'https://www.coursera.org/learn/python',
    'https://www.edx.org/learn/python/harvard-university-cs50-s-introduction-to-programming-with-python',
    'https://docs.python.org/3/tutorial/',
]


def main(args):
    show = '--show' in args
    urls = [a for a in args if not a.startswith('--')] or SAMPLES
    for url in urls:
        started = time.monotonic()
        try:
            result = run_import(url)
        except FetchError as error:
            print(f'\n{url}\n  ERROR ({error.kind}): {error}')
            continue
        s = result['stats']
        print(f"\n{url}\n  {result['platform']['name']} · {result['strategy']} · {result['kind']} · {time.monotonic() - started:.1f}s")
        print(f"  Title: {result['title']!r}  Licence: {(result['license'] or {}).get('name')}  Full content allowed: {result['policy']['fullContent']}")
        print(f"  {s['modules']} modules, {s['lessons']} lessons: {s['imported']} imported, {s['inaccessible']} inaccessible, {s['reference']} reference; "
              f"{s['words']} words, {s['codeBlocks']} code blocks, {s['tables']} tables")
        for item in result['items']:
            lessons = item['lessons'] if item['type'] == 'module' else [item]
            if item['type'] == 'module':
                print(f"  ▸ {item['title']}")
            for lesson in lessons:
                indent = '      ' if item['type'] == 'module' else '    '
                print(f"{indent}{lesson['status'][:4]:4} {lesson['title'][:70]!r} {lesson['words']}w {len(lesson['sections'])}§ {lesson['reason'][:90]}")
        for note in result['notes']:
            print(f'  note: {note}')
        if result['policy']['note']:
            print(f"  policy: {result['policy']['note'][:200]}")
        if show:
            first = next((l for i in result['items'] for l in (i['lessons'] if i['type'] == 'module' else [i]) if l['content']), None)
            print('\n' + (first['content'][:4000] if first else '(no content)'))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main(sys.argv[1:])
