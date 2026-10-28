"""Real-browser verification of the Java course and its secured checkpoint UI; isolated data only."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend/tests'))
from test_java_course import JavaCourseTests, COURSE, DATA
from check_python_browser import wait
from playwright.sync_api import sync_playwright


def main():
    output = ROOT / '.openai/java-full-stack'
    output.mkdir(parents=True, exist_ok=True)
    JavaCourseTests.setUpClass()
    try:
        fixture = JavaCourseTests()
        learner = fixture.employee('Java Browser Learner')
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path='C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless=True)
            page = browser.new_page(viewport={'width':1440,'height':1050})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(JavaCourseTests.base + '/#login')
            wait(page,'portalReady')
            page.evaluate('''async ({email,course})=>{
                const result=await api('auth/login',{email,password:'Learning123!'});
                currentUser=result.user;csrfToken=result.csrfToken;
                await loadCandidate();await loadCourse(course);render();
            }''', {'email':learner.email,'course':COURSE})
            page.wait_for_selector('#lesson-quiz-form')
            assert page.locator('#python-editor').count()==0
            assert page.locator('video').count()==0
            assert page.locator('.structured-lesson h3').count()>=8
            assert 'public class Hello' in page.locator('.structured-lesson').inner_text()
            assert page.locator('.structured-lesson table').count()>=2 and page.locator('.structured-lesson h4').count()>=3
            page.click('.lesson-outline summary')
            page.click('.lesson-outline button:has-text("Variables, data types and operators")')
            assert page.evaluate("document.activeElement.textContent.includes('Variables, data types and operators')")
            assert page.evaluate("location.hash==='#course'")
            page.evaluate('window.scrollTo(0,0)')
            page.wait_for_timeout(400)
            page.screenshot(path=str(output/'java-module-desktop.png'),full_page=True)
            print('PASS: the Java Basics module renders headings, subheadings, tables and code examples.',flush=True)
            for number, question in enumerate(DATA['lessons'][0]['quiz']):
                page.check(f'input[name="lesson-quiz-{number}"][value="{question[2]}"]')
            page.click('#lesson-quiz-form button[type="submit"]')
            wait(page,'id=>Boolean(learning.run.lessons[id])',f'{COURSE}-module-01')
            page.wait_for_selector('#start-checkpoint')
            page.evaluate('window.scrollTo(0,0)')
            page.screenshot(path=str(output/'java-assessment-desktop.png'),full_page=True)
            page.click('#start-checkpoint')
            page.wait_for_selector('#checkpoint-form')
            assert page.locator('#checkpoint-form fieldset').count()==8
            page.evaluate("window.dispatchEvent(new Event('blur'))")
            wait(page,"learning.run.checkpoints[0].attempts[0].status==='terminated'")
            wait(page,"!examFinishing")
            print('PASS: the knowledge check unlocks the module assessment; window blur terminates and saves the attempt.',flush=True)
            page.click('#start-checkpoint')
            page.wait_for_selector('#checkpoint-form')
            identity=page.evaluate('activeExam.attempt.id')
            answers=fixture.answers({'id':identity})
            for number, answer in enumerate(answers):
                page.check(f'input[name="checkpoint-{number}"][value="{answer}"]')
            page.click('#checkpoint-form button[type="submit"]')
            wait(page,"learning.run.checkpoints[0].passed && !examFinishing && currentCourseExtras.courseLessons[1].locked===false")
            page.click(f'[data-act="lesson-select"][data-id="{COURSE}-module-02"]')
            assert 'Object Oriented Programming' in page.locator('article.lesson-content h2').inner_text()
            print('PASS: a passing server-graded module assessment unlocks module two.',flush=True)
            page.set_viewport_size({'width':390,'height':844})
            page.wait_for_timeout(400)
            page.screenshot(path=str(output/'java-module-mobile.png'),full_page=True)
            assert not page.evaluate('document.documentElement.scrollWidth>innerWidth'), page.evaluate("[...document.querySelectorAll('body *')].filter(e=>e.getBoundingClientRect().right>innerWidth+1).slice(0,8).map(e=>({tag:e.tagName,class:e.className,width:e.getBoundingClientRect().width}))")
            assert not errors, errors
            (output/'report.json').write_text(json.dumps({'structuredLesson':True,'quizWithoutPythonEditor':True,'blurTermination':True,'assignmentUnlock':True,'mobileOverflow':False,'pageErrors':errors},indent=2))
            browser.close()
    finally:
        JavaCourseTests.tearDownClass()


if __name__=='__main__':
    main()
