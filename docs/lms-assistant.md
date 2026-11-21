# LMS assistant

A floating assistant on every signed-in page answers questions about learning in the LMS. It is **rule-based**, like the Timesheet assistant. Typed questions are matched to an *intent* with keywords and regular expressions, and every answer is read from the portal's own APIs. It uses no AI service, no external API, no embeddings and no stored answers.

## Using it

Select the gold chat button at the bottom right. The panel has:

- **Suggested questions** for your role.
- **Message bubbles** for you and the assistant, with a typing indicator while an answer loads.
- **Buttons** on each answer. Every button does something real: it runs a follow-up question, opens a page or course, or acts on the open course. Only the newest answer's buttons are shown.
- **Header controls**: **New chat** (start again with a greeting), **Clear chat** (empty the conversation and show the suggestions), **Minimise** (keep the panel as a header bar), and **Close** (hide it; the conversation is kept).

Type `menu` or `start over` at any time to return to the main options.

The conversation is kept for the current browser session only, per user, and is deleted when you sign out. Nothing is stored on the server, because answers are always re-read from live data.

The assistant is hidden during exams and assessments, and until a temporary password has been changed.

## What it can answer

| Role | Questions |
| --- | --- |
| Everyone | My assigned, pending (all or mandatory only), completed and overdue courses; my progress; upcoming deadlines; my certificates; my assessments, their results and deadlines; finding courses by area; training sessions; course details, duration, category, level and content; learning materials; training policies; how to use the LMS |
| Manager | Team learning progress, pending and overdue training, and team training requirements, for direct reports only |
| HR and admin | Training compliance, training by department, one employee's training, course assignments, course management, reports, step-by-step guidance. Team questions cover the whole organisation |
| Trainer | Courses I teach, my learners' progress, materials, reports |

Questions outside the LMS (leave, timesheets, pay, weather) get a plain explanation instead of a guess. Unrecognised questions get the fallback reply, with **My Courses**, **Learning Progress**, **Training Deadlines** and **Help** buttons.

### Example flows

- **"Show my pending courses"** asks whether you want all pending courses or only mandatory training, with **All Pending Courses**, **Mandatory Training** and **Upcoming Deadlines** buttons. The list shows real course names, progress and deadlines, each with a **Start / Continue** button.
- **"Help me find courses"** offers the learning areas that have courses, with counts, then lists that area's courses.
- **"Where can I find my certificates?"** says where they are and offers **Open Certificates**.
- **A manager's "pending courses"** is ambiguous, so the assistant asks: your own, or your team's?

## On a course page

The course page's **Course assistant** panel opens the assistant with that course in context. This replaces the former AI panel. Its four actions read the course's own lessons and your own results:

- **Summarise**: the course description, modules and lessons, or one lesson's "Learning objectives" / "Key takeaways" points.
- **Explain a concept**: finds where a word or phrase is explained in the course's lessons, with a link to each lesson.
- **Practice**: the course's own exercises, quizzes, coding practice and knowledge checks, with your status in each. It does not generate new questions, and answers are never shown.
- **What to revise**: checks you have not passed (best score against the pass mark), modules whose exam is not yet passed, and lessons not yet completed.

Locked lessons stay locked: their text is not sent to the browser, so it is never searched or summarised.

## How a question is understood

The detector is in `frontend/public/scripts/chatbot-intents.js`; its configuration is in `chatbot-config.js`.

1. **Normalise**: lower case, common misspellings corrected (`cource`, `certficate`, `assesment`, `deadine` and others), punctuation removed.
2. **Score**: each intent has weighted regular expressions with word boundaries, so short or generic words ("in", "my", "do") never match on their own.
3. **Scope**: personal intents have team twins. Team words ("team", "employees", "who …") choose the team intent. For managers, HR and admins, a question with neither "my" nor team words is clarified.
4. **Choose**: scores below 4 are unknown. Near ties (within one point) go to the higher priority, for example "where are my certificates" opens the page. Exact ties are clarified. Intents outside the role are preferred only when they are clearly stronger, so the answer can say plainly that they are not available.
5. **Courses** are recognised by matching significant title words against the user's own course list. A course name on its own asks for that course's details.

## Data and permissions

The assistant calls only existing endpoints (`chatbot-data.js`), as the signed-in user:

| Answer | Endpoint |
| --- | --- |
| Own courses, deadlines, progress | `GET /api/courses` |
| Certificates | `GET /api/certificates` |
| Assessments | `GET /api/me/assessments` |
| Training sessions | `GET /api/me/calendar` |
| Team, compliance, department, one employee | `GET /api/manage/compliance` (direct reports for managers; everyone for HR and admins; 403 otherwise) |
| Course management, trainer's courses | `GET /api/admin/courses` (trainers: their own courses) |
| Assignments | `GET /api/manage/assignments` |
| Trainer's learners | `GET /api/manage/reports?type=enrollments` (trainers: their own courses) |

Identity comes from the session cookie. The browser sends no user or role ID, and the server applies its own permissions, so the assistant can never show more than the page it summarises. The browser-side role checks only decide which questions and buttons to offer. A question outside the role is answered with what *is* available, without calling the server. `backend/tests/test_assistant_data_access.py` pins these permissions.

## Files

| File | Purpose |
| --- | --- |
| `chatbot-config.js` | Intents, patterns, spelling corrections, suggestions, fallback (chatbotConfig) |
| `chatbot-intents.js` | Intent detection, course recognition, term and name extraction (intentDetector) |
| `chatbot-data.js` | API access and role checks (chatbotDataService, chatbotPermissions) |
| `chatbot-responses.js` | Answers, flows, guidance and course actions (chatbotResponseService) |
| `chatbot.js` | Launcher, panel, messages, input and conversation storage (LMSChatbot, conversationService) |
| `styles/chatbot.css` | Panel styles; `styles/dark/chatbot.css` is generated by `npm run theme:dark` |

The LMS is plain JavaScript without a build step, so these are script files, not React components. The structure follows the Timesheet assistant: conversation steps return text and buttons, and typed text goes through ordered keyword and regex rules.

## Testing

```
node frontend/tests/check.cjs        # all frontend tests, including frontend/tests/chatbot.test.cjs
python -m unittest discover -s backend/tests -p test_assistant_data_access.py -v
```

To try it locally, run `npm start`, sign in, and select the chat button.
