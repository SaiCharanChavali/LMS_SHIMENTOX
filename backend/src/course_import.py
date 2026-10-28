"""Add a course by importing it from a URL: preview first, then save the reviewed structure as a draft or published course.

Preview retrieves and extracts the source (see `importers`) and keeps the result on the server for 30 minutes under
a random token; nothing is written to the database. Save turns the previewed structure into an ordinary
lesson-based course through `admin.save_course`, so the same validation, permissions, publishing checks,
notifications and audit records apply as for courses created by hand. Imported courses are then edited in the
regular course builder.
"""
import json
import math
import secrets
import threading
import time
from urllib.parse import urlsplit

from admin import audit, course_view, save_course
from importers import FetchError, canonical, run_import, validate_url
from services import APIError, check, now, require

PREVIEW_SECONDS = 30 * 60
MAX_PREVIEWS = 20
WORDS_PER_MINUTE = 200
_previews = {}
_lock = threading.Lock()
# Imports make outbound requests for up to ~75 seconds; at most two run at once on this server.
_running = threading.BoundedSemaphore(2)


def duplicate(db, *urls):
    """A non-archived course already imported from any of these addresses."""
    for key in {canonical(u) for u in urls if u}:
        row = db.execute("SELECT id,title,status FROM courses WHERE source_url=? AND status<>'archived'", (key,)).fetchone()
        if row:
            return row
    return None


def preview(db, user, data):
    """Retrieve and extract a URL for review. Runs outside a database transaction (see server.py)."""
    require(user, 'courses.manage')
    try:
        url = validate_url(data.get('url'))
    except FetchError as error:
        raise APIError(400, str(error))
    if not _running.acquire(blocking=False):
        raise APIError(429, 'Another course import is in progress. Try again when it finishes.')
    try:
        result = run_import(url)
    except FetchError as error:
        raise APIError(400 if error.kind in ('invalid', 'blocked') else 422, str(error))
    finally:
        _running.release()
    existing = duplicate(db, url, result['sourceUrl'])
    token = secrets.token_urlsafe(24)
    with _lock:
        for key in [k for k, v in _previews.items() if v['expires'] < time.time()]:
            del _previews[key]
        while len(_previews) >= MAX_PREVIEWS:
            del _previews[min(_previews, key=lambda k: _previews[k]['expires'])]
        _previews[token] = {'user': user['id'], 'expires': time.time() + PREVIEW_SECONDS, 'result': result}
    return {'token': token, 'preview': result, 'duplicate': {'id': existing['id'], 'title': existing['title'], 'status': existing['status']} if existing else None}


def placed_lessons(result):
    """(module index or None, module title, lesson) in source order; module indexes count the source's modules."""
    module = -1
    for item in result['items']:
        if item['type'] == 'module':
            module += 1
            for lesson in item['lessons']:
                yield module, item['title'], lesson
        else:
            yield None, '', item


def lesson_payload(lesson, number, full, platform):
    """One lesson in the format admin.save_course accepts. Only retrieved text is used; nothing is written for
    lessons that could not be retrieved apart from a link to the original."""
    title = lesson['title'] if len(lesson['title'].strip()) >= 2 else f'Lesson {number}'
    url = lesson['url'] or ''
    content = lesson['content'] if full and lesson['status'] == 'imported' else ''
    resources = [{'title': f'Original lesson on {platform}'[:150], 'url': url}] if url.startswith('https://') else []
    if not content and not resources and url:
        content = f'This lesson is on the original site: [{title}]({url})'
    description = lesson.get('description') or ''
    if full and lesson['status'] != 'imported':
        description = f'This lesson could not be imported. Open it on {platform} using the link below.'
    minutes = min(1000, math.ceil(lesson.get('words', 0) / WORDS_PER_MINUTE)) if content else 0
    return {'title': title, 'description': description[:2000], 'content': content, 'resources': resources, 'durationMinutes': minutes}


def save(db, user, data):
    require(user, 'courses.manage')
    token = data.get('token')
    with _lock:
        entry = _previews.get(token) if isinstance(token, str) else None
    check(entry is not None and entry['user'] == user['id'] and entry['expires'] > time.time(), 'This import preview has expired. Import the URL again.', 410)
    result = entry['result']
    mode = data.get('mode')
    check(mode in ('full', 'reference'), 'Choose whether to import the lesson content or save the course as a reference.')
    status = data.get('status', 'draft')
    check(status in ('draft', 'published'), 'Save the imported course as a draft or publish it.')
    full = mode == 'full'
    if full:
        check(result['policy']['fullContent'], result['policy']['note'] or 'This source can only be saved as a reference.', 409)
        check(data.get('rightsConfirmed') is True, 'Confirm that ShimentoX is permitted to reuse this content, or save the course as a reference instead.')
        check(result['stats']['imported'] > 0, 'No lesson content could be retrieved from this source. Save it as a reference instead.', 409)
    existing = duplicate(db, result['requestedUrl'], result['sourceUrl'])
    check(existing is None, f'This source has already been imported as “{existing["title"] if existing else ""}”. Open it from the course catalog.', 409)
    # Attribution names the platform, or the site's own address for pages handled by the generic extractor.
    platform = result['platform']['name'] if result['platform']['id'] != 'website' else urlsplit(result['sourceUrl']).hostname
    placed = list(placed_lessons(result))
    if not placed:
        # Nothing but the course page itself is known (for example a platform that blocks automated access).
        title = result['title'] or (data.get('title') if isinstance(data.get('title'), str) else '') or 'Course'
        placed = [(None, '', {'title': title, 'url': result['sourceUrl'], 'status': 'reference', 'reason': '', 'description': result['description'], 'content': '', 'words': 0})]
    lessons = [lesson_payload(lesson, n, full, platform) for n, (_, _, lesson) in enumerate(placed, 1)]
    payload = {key: data[key] for key in ('title', 'category', 'description', 'difficulty', 'durationMinutes', 'departmentId', 'visibility') if key in data}
    if not str(payload.get('description') or '').strip():
        payload['description'] = result['description'] or f'Imported from {platform}.'
    if 'durationMinutes' not in payload:
        payload['durationMinutes'] = min(100000, sum(l['durationMinutes'] for l in lessons))
    course = save_course(db, user, {**payload, 'format': 'lessons', 'status': status, 'lessons': lessons})
    import_status = 'reference' if not full else 'complete' if result['stats']['inaccessible'] == 0 else 'partial'
    report = {'importedAt': now(), 'mode': mode, 'platform': result['platform'], 'strategy': result['strategy'], 'kind': result['kind'], 'requestedUrl': result['requestedUrl'],
              'sourceUrl': result['sourceUrl'], 'license': result['license'], 'provider': result.get('provider', ''), 'policyNote': result['policy']['note'], 'notes': result['notes'],
              'lessons': [{'title': l['title'], 'module': m, 'url': l['url'], 'status': l['status'] if full else 'reference', 'reason': l.get('reason', ''),
                           'sections': len(l.get('sections', [])), 'words': l.get('words', 0) if full else 0} for m, _, l in placed]}
    db.execute('UPDATE courses SET source_url=?,source_platform=?,import_status=?,import_report_json=? WHERE id=?',
               (canonical(result['sourceUrl']), platform, import_status, json.dumps(report, ensure_ascii=False), course['id']))
    for position, (module, module_title, lesson) in enumerate(placed):
        db.execute('UPDATE course_lessons SET module_index=?,module_title=?,source_url=? WHERE course_id=? AND position=?',
                   (module, module_title, lesson['url'] or '', course['id'], position))
    audit(db, user['id'], 'course_imported', course['id'], f'{mode}: {platform} {result["sourceUrl"]}'[:500])
    with _lock:
        _previews.pop(token, None)
    return {'course': course_view(db.execute('SELECT * FROM courses WHERE id=?', (course['id'],)).fetchone(), True, db)}
