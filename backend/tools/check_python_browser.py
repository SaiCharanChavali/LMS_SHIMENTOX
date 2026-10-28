"""Verify the original Python workshop in an actual browser using an isolated test database.

Requires playwright and an installed Edge browser. Never changes the live LMS database.
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend/tests'))
from test_python_path import PythonPathTests, COURSE
from playwright.sync_api import sync_playwright


def wait(page, expression, arg=None, timeout=60000):
    # Poll via the browser protocol; wait_for_function's string eval conflicts with the portal CSP.
    deadline = time.monotonic() + timeout / 1000
    while time.monotonic() < deadline:
        if page.evaluate(expression, arg):
            return
        page.wait_for_timeout(100)
    raise AssertionError('Browser condition timed out: ' + expression + '\n' + page.locator('body').inner_text()[-4000:])


def main():
    output = ROOT / '.openai/python-interactive'
    output.mkdir(parents=True, exist_ok=True)
    PythonPathTests.setUpClass()
    try:
        fixture = PythonPathTests()
        learner = fixture.employee('Browser Workshop Learner')
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path='C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless=True)
            page = browser.new_page(viewport={'width': 1440, 'height': 1050})
            errors = []
            console = []
            page.on('console', lambda message: console.append(message.text) if message.type == 'error' else None)
            page.on('response', lambda response: console.append(str(response.status) + ' ' + response.url) if response.status >= 400 else None)
            page.on('requestfailed', lambda request: console.append('FAILED ' + request.url + ' ' + str(request.failure)))
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(PythonPathTests.base + '/#login')
            wait(page, 'portalReady')
            page.evaluate('''async ({email,course})=>{
                const result=await api('auth/login',{email,password:'Learning123!'});
                currentUser=result.user;csrfToken=result.csrfToken;
                await loadCandidate();await loadCourse(course);render();
            }''', {'email': learner.email, 'course': COURSE})
            page.wait_for_selector('#python-editor')
            assert page.locator('video').count() == 0
            assert page.locator('.structured-lesson h2').count() >= 5
            route = page.evaluate('location.hash')
            page.locator('.lesson-outline summary').click()
            section = page.locator('[data-act="lesson-section"]').last
            target = section.get_attribute('data-id')
            section.click()
            assert page.evaluate('location.hash') == route
            assert page.evaluate('(id)=>document.activeElement.id===id', target)
            print('PASS: detailed sections render and outline navigation preserves the course route.', flush=True)

            code = 'def discounted_price(price, percent):\n    return price * (1 - percent / 100)\n\nprint(discounted_price(80, 25))'
            page.fill('#python-editor', code)
            page.click('#python-run')
            wait(page, "document.querySelectorAll('#python-results .passed').length===3 || document.querySelector('#python-status')?.textContent.includes('Execution ended')")
            if page.locator('#python-results .passed').count() != 3:
                page.evaluate("() => {const f=document.createElement('iframe');f.sandbox='allow-scripts';f.src='python-sandbox.html';document.body.appendChild(f);}")
                page.wait_for_timeout(500)
                probe = page.frames[-1].evaluate('''async()=>{
                    const results=[];
                    for(const kind of ['classic','module'])for(const credentials of ['same-origin','omit']){
                        results.push(await new Promise(resolve=>{
                            const url=URL.createObjectURL(new Blob(['postMessage("started")'],{type:'text/javascript'}));
                            const w=new Worker(url,{type:kind,credentials});
                            const done=value=>{w.terminate();URL.revokeObjectURL(url);resolve({kind,credentials,value});};
                            w.onmessage=()=>done('started');w.onerror=e=>done('error '+e.message);setTimeout(()=>done('timeout'),1000);
                        }));
                    }return results;
                }''')
                print('Worker boundary diagnostic:',probe,flush=True)
                raise AssertionError(page.locator('#python-output').inner_text() + '\n' + '\n'.join(console))
            assert '60' in page.locator('#python-output').inner_text()
            print('PASS: real browser runs Python and passes all three coding checks.', flush=True)
            first_id = COURSE + '-lesson-01'
            for number, choice in enumerate((1, 2, 0)):
                page.check(f'input[name="lesson-quiz-{number}"][value="{choice}"]')
            page.click('#lesson-quiz-form button[type="submit"]')
            wait(page, '(id)=>Boolean(learning.run.lessons[id])', first_id)
            page.evaluate('(id)=>loadCourse(id)', COURSE)
            page.click(f'[data-act="lesson-select"][data-id="{first_id}"]')
            assert page.input_value('#python-editor') == code
            assert page.locator('.python-knowledge .success').count() == 1
            page.screenshot(path=str(output / 'workshop-desktop.png'), full_page=True)
            print('PASS: the server records the quiz result; saved code survives reopening the course.', flush=True)
            # A loop must not freeze the portal. The worker is killed after five seconds.
            page.fill('#python-editor', 'while True:\n    pass')
            page.click('#python-run')
            wait(page, "document.querySelector('#python-output')?.textContent.includes('5 seconds')", timeout=20000)
            assert page.locator('#python-run').is_enabled()
            print('PASS: infinite-loop execution is stopped and the editor remains usable.', flush=True)
            page.fill('#python-editor', 'import js\ntry:\n    await js.fetch(' + repr(PythonPathTests.base + '/api/session') + ')\n    print("UNEXPECTED PORTAL ACCESS")\nexcept Exception:\n    print("PORTAL ACCESS BLOCKED")')
            page.click('#python-run')
            wait(page, "document.querySelector('#python-output')?.textContent.includes('PORTAL ACCESS BLOCKED')", timeout=20000)
            assert 'UNEXPECTED PORTAL ACCESS' not in page.locator('#python-output').inner_text()
            print('PASS: learner Python cannot fetch the portal session API.', flush=True)
            page.set_viewport_size({'width': 390, 'height': 844})
            page.screenshot(path=str(output / 'workshop-mobile.png'), full_page=True)
            assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
            assert not errors, errors
            (output / 'report.json').write_text(json.dumps({'pythonExecution': True, 'savedDraft': True, 'serverQuiz': True, 'timeout': True, 'portalIsolation': True, 'mobileOverflow': False, 'pageErrors': errors}, indent=2))
            browser.close()
    finally:
        PythonPathTests.tearDownClass()


if __name__ == '__main__':
    main()
