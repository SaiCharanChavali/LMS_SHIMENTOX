# AI-powered learning and development: gap analysis and roadmap

**Status:** analysis and plan only. No source code or database was changed to produce it.
**Update, 12 November 2026:** skills, competencies, goals, skill assessments and learning paths were removed from the portal (schema version 11 drops their tables). Every part of this plan that builds on them, including skill-gap recommendations, Individual Development Plans, skill-based adaptive assessments and skills analytics, is out of date and needs re-planning before use.
**Analysed:** `main` at commit `ffdca07` (identical to GitHub `SaiCharanChavali/LMS_SHIMENTOX`), 10 November 2026.
**Data snapshot:** the development database on the analyst's machine (`backend/data/lms.sqlite3`, read-only). Production data may differ; re-run the counts in [Appendix A](#appendix-a-how-to-re-check-the-data-snapshot) before planning sprints.

## 1. Summary

ShimentoX already has most of the building blocks for an AI-powered learning platform. The two biggest gaps are not AI:

1. **The skills, goals and learning-path features have working APIs but no screens.** The frontend tests confirm `#skills` and `#paths` now redirect to My Learning, and no page calls `/api/me/skills`, `/api/me/paths`, `/api/manage/skills` or `/api/manage/paths`.
2. **There is no skills data.** The snapshot has 0 skills, 0 job roles, 0 role competencies, 0 goals and 0 learning paths. The recommendation engine, skill-gap report and goal tracking all depend on these, so today they have nothing to work with.

AI is already integrated through Claude (`assistant.py`, `course_generator.py`), but it is off by default and, per [ai-assistant.md](ai-assistant.md), has never been run against the live API in this repository (`assistant_usage` has 0 rows).

| # | Feature | Classification | One-line reason |
|---|---|---|---|
| 1 | AI-powered personalised recommendations | **Partially implemented** + **requires runtime validation** | A transparent rule-based engine exists and is shown on the employee dashboard. It is not AI-driven, and its inputs (skills, role targets, goals) are empty and have no UI. |
| 2 | Individual Development Plans (IDP) | **Partially implemented** | Goals, skill evidence, role targets, training-hour targets and development records exist. There is no plan, no manager agreement, no review cycle and no screen. |
| 3 | Adaptive assessments and targeted practice | **Partially implemented** + **requires runtime validation** | Random question draw, shuffling, server scoring, skill-assessment evidence, and AI practice/revision modes exist. Nothing adapts: questions have no difficulty or topic, and AI practice is neither saved nor scored. |
| 4 | Company Knowledge Assistant (approved internal documents) | **Not implemented** (reusable parts exist) | The assistant answers only from one course's lesson text. Uploaded PDFs and documents are never read. There is no document library or approval workflow. |
| 5 | Training Effectiveness Analytics | **Partially implemented** | Completion, compliance, assessment pass rate, skills-gap and training-hour reporting exist. There is no pre/post gain, learner feedback, skill uplift or on-the-job follow-up. |

**Recommended order:** foundations first, then **start effectiveness data capture early** (pre/post and feedback only become useful once collected), then recommendations, IDP, adaptive assessments, and the Knowledge Assistant as a parallel track. Details are in [section 9](#9-dependencies-and-implementation-order).

## 2. Constraints this plan follows

- **Branding.** Keep the ShimentoX logo, colours, typography and navigation. New pages reuse existing components: `panel`, `kpi`, `meter`, `tagText`, report filters, and the tabbed layout of Training Compliance.
- **No duplication.** Reuse `skills`, `skill_evidence`, `role_competencies`, `learning_goals`, `learning_paths`, the recommendation engine, the assessment engine, course content and Training Compliance. No second skills framework, path builder or compliance module.
- **Do not rebuild the LMS.** Every change is additive. Database changes are new tables and new nullable columns through the existing migration mechanism in `database.py` (currently schema version 9).
- **Text-based learning only.** No video storage, uploads, hosting or lessons in any new feature. See [section 8.4](#84-text-only-content-policy) for the existing video code this conflicts with.

## 3. What exists today

### 3.1 Modules

| Area | Backend | Frontend |
|---|---|---|
| Auth, sessions, CSRF, roles | `server.py`, `services.py`, `security.py` | `auth.js` |
| Keka SSO and HR sync | `keka.py` | Sign-in button, **Sync from Keka** |
| Courses (3-module and lesson-based), builder, import from URL | `admin.py`, `course_import.py`, `importers/` | `admin.js`, `course-import.js` |
| AI course generator (draft from a link) | `course_generator.py` | Manage Courses → Create from a link with AI |
| Learning player, lessons, checkpoints, exams | `services.py`, `checkpoints.py` | `learning.js`, `development.js` |
| AI learning assistant (course-scoped) | `assistant.py` | Course page panel (`assistantPanel`) |
| Skills, competencies, evidence, goals | `development.py`, `analytics.py` | **No screens** (removed) |
| Learning paths | `development.py` | **No screens** (removed) |
| Assessments and question banks (pre, post, knowledge, skill) | `development.py` | Assessments page |
| Training sessions, calendar, training-hour targets | `development.py` | Training Calendar, Manager View |
| Notifications and deadline reminders | `notifications.py`, `reminders.py` | Bell and notification panel |
| Dashboards and reports | `analytics.py` | Admin Dashboard, Manager View, Reports & Analytics |
| Training Compliance and deadline monitoring | `compliance.py`, `deadlines.py` | Training Compliance |
| Certificates | `services.py` | My Certificates, Certificates |

### 3.2 Database tables relevant to this plan

| Table | Purpose | Rows in snapshot |
|---|---|---|
| `skills` | Skill catalogue (name, category, description) | 0 |
| `course_skills` | Skill and level a course develops | 0 |
| `role_competencies` | Target level per job role and skill | 0 |
| `skill_evidence` | Levels proven by assessment or recorded by a manager or HR | 0 |
| `learning_goals` | Employee goals, optionally tied to a skill, level and date; auto-complete on evidence | 0 |
| `learning_paths`, `learning_path_courses`, `path_assignments` | Ordered course sequences | 0 |
| `assessments`, `assessment_bank`, `assessment_attempts` | Assessment engine (kinds `pre`, `post`, `knowledge`, `skill`) | 36 / 196 / 2 (30 knowledge, 6 post, **0 pre**, **0 skill**) |
| `course_lessons` | Text lessons, documents, exercises, activities | 90 |
| `lesson_activity_attempts`, `lesson_quiz_attempts`, `checkpoint_attempts` | Practice and checkpoint results | — |
| `materials`, `course_resources` | Private uploaded files and links | 0 / 0 |
| `development_records` | Self-reported external learning | 0 |
| `training_targets` | Yearly training-hour target per employee | 0 |
| `assistant_usage` | AI requests per employee (rate limiting only) | 0 |
| `notifications` | In-app notifications | 8 |
| `job_roles` | Roles used by competencies and assignments | **0** |

### 3.3 API endpoints relevant to this plan

All are under `/api`, authenticated, and check permissions on the server.

| Endpoint | Used by a screen today? |
|---|---|
| `GET me/dashboard` (includes `recommendations`) | Yes: My Dashboard |
| `GET me/skills`, `POST me/goals` | **No** |
| `GET me/paths` | **No** |
| `GET/POST manage/skills`, `POST manage/competencies`, `POST manage/skill-evidence` | **No** |
| `GET/POST manage/paths`, `POST manage/paths/{id}/assign`, `GET manage/paths/{id}/progress` | **No** |
| `GET me/assessments`, `POST me/assessments/{id}/start` and `/submit` | Yes |
| `GET/POST manage/assessments`, `GET manage/assessments/{id}/attempts` | Yes |
| `GET/POST me/assistant` | Yes, but the assistant is disabled |
| `GET/POST manage/course-generator` | Yes, but disabled |
| `GET manage/dashboard`, `GET manage/reports?type=` | Yes |
| `GET manage/compliance`, `GET manage/compliance/export` | Yes |
| `POST manage/training-targets` | Yes |

### 3.4 Roles and permissions

`services.PERMISSIONS` defines the matrix; managers are scoped to direct reports (`candidates.manager_id`) and trainers to their own courses.

| Permission | Roles |
|---|---|
| `skills.manage` | admin, hr |
| `competencies.manage` | admin, hr, manager (own department or reports' roles) |
| `skills.record` | admin, hr, manager (direct reports) |
| `paths.manage`, `courses.manage`, `assessments.manage`, `sessions.manage` | admin, hr, trainer (own) |
| `courses.assign` | admin, hr, manager (direct reports, optional only) |
| `reports.view` | admin, hr, manager (reports), trainer (own courses) |
| `audit.view` | admin |

### 3.5 AI integrations

| Integration | What it does | Safeguards already in place | State |
|---|---|---|---|
| `assistant.py` | Ask, summarise, explain, generate practice questions, suggest revision from the employee's own scores, for one published course | Server-only credentials; answer keys never sent; course lesson text as the only source; per-employee hourly limit (`LMS_AI_HOURLY_LIMIT`); friendly errors; refusal fallback (`fallbacks: "default"`); prompt caching of the course material | Off unless `LMS_AI_ENABLED=1`; **never run live** |
| `course_generator.py` | Writes an original draft course from a web page using structured JSON output | Importer blocks private addresses and respects robots.txt; result saved as draft for review; audit log | Off by default; **never run live** |

Both use `claude-opus-5-5` (overridable with `LMS_AI_MODEL`) through the official `anthropic` Python SDK, which is optional so the rest of the portal stays dependency-free.

## 4. Reusable components

| Component | Where | Reused by |
|---|---|---|
| Rule-based recommendation engine with reasons | `analytics.recommendations` | 1, 3 |
| Skill levels, role targets, gaps | `analytics.skill_levels`, `analytics.role_targets`, `my_skills`, `report_skills` | 1, 2, 3, 5 |
| Evidence that raises levels and completes goals | `development.record_evidence` | 2, 3 |
| Goals with skill, level and date | `learning_goals`, `save_goal` | 2 |
| Learning paths with progress | `employee_paths`, `path_progress` | 1, 2 |
| Assessment engine: draw, shuffle, time limit, attempts, server scoring | `development.start_assessment` / `submit_assessment` | 3, 5 |
| Progress, assignments, deadline status | `analytics.progress_index`, `assignment_index`, `deadlines.deadline_status` | 1, 2, 5 |
| Manager scope | `analytics.scope`, `development.team` | 2, 5 |
| Notifications with de-duplication keys | `services.notify` | 2, 3, 4, 5 |
| Reminder scheduler (idempotent passes) | `reminders.py` | 2, 5 |
| Claude client, rate limit, error mapping, refusal fallback, caching | `assistant.py` | 1, 2, 3, 4 |
| Structured JSON output from Claude | `course_generator.write_course` | 1, 2, 3 |
| Private file storage with type and size checks | `development.store_material`, `material_file` | 4 |
| HTML/Markdown text extraction and safe fetching | `importers/` | 4 |
| Safe Markdown renderer for lesson text | `learning.js` | 4 |
| Filter, tabs, KPI cards, charts, CSV/Excel export | `development.js` compliance page, `compliance.py` | 5 |
| Audit log | `admin.audit` | 2, 4, 5 |
| Keka employee number, manager, job title | `keka.py` | 2, 5 |

## 5. Gap analysis by feature

### 5.1 AI-powered personalised learning recommendations: partially implemented

**Already there**

- `analytics.recommendations` scores published courses and explains each pick:
  - next course in a learning path (+4),
  - closes a role skill gap (+3),
  - supports an active goal (+3),
  - revision after a failed skill assessment (+2),
  - built for the employee's department (+1),
  - builds on a completed category (+1).
- It excludes completed, started and assigned courses. Up to six are shown on My Dashboard.
- The assistant's `revision` mode suggests what to revise, from the employee's own scores in one course.

**Missing**

- With no skills, competencies, goals or paths, only the department and category rules can fire. Most employees will see no recommendations.
- There is no screen to maintain those inputs: skills, role targets, evidence and goals.
- No AI. Nothing reads course descriptions or lesson text against an employee's goals, and there is no natural-language explanation beyond the fixed reasons.
- No feedback loop: dismissals and clicks are not recorded, so quality cannot be measured.
- Recommendations only appear on My Dashboard. Employees land on My Learning.

**Runtime validation needed:** what recommendations real employees get once skills data exists, and the AI layer once enabled.

### 5.2 Individual Development Plans: partially implemented

**Already there**

- Goals (`learning_goals`, up to 20 active per employee) that complete automatically when skill evidence reaches the target level.
- Skill evidence recorded by managers and HR or by passing a skill assessment. Completing a course never raises a skill by itself, which is the right rule to keep.
- Role targets (`role_competencies`).
- Yearly training-hour targets set by managers (`training_targets`).
- Self-reported external learning (`development_records`).
- Learning paths and assignments.
- Keka supplies reporting managers and job titles.

**Missing**

- A plan object that ties goals, courses, paths, assessments, sessions and on-the-job actions to a period.
- Draft → manager agreement → active → reviewed workflow, with check-ins and a final review.
- Any screen for goals, skills or plans, for employees or managers.
- AI help to draft a plan from gaps, goals and the catalogue.
- Reminders for plan milestones and reviews.

### 5.3 Adaptive assessments and targeted practice: partially implemented

**Already there**

- Each attempt draws `question_count` questions at random from the bank, shuffles answer positions, and enforces time and attempt limits.
- Scoring happens on the server, with explanations after submission.
- Skill assessments record evidence at a validated level.
- Lesson knowledge checks, checkpoints, and scored lesson activities.
- AI `practice` mode writes 3 new questions on a lesson; `revision` mode suggests what to revise.

**Missing**

- `assessment_bank` has no difficulty, skill or topic, so nothing can adapt.
- Every attempt has the same length and difficulty mix. There is no stop rule, so a confident placement cannot finish early.
- Missed questions are not turned into practice. AI practice questions are shown once as text: not saved, not answerable in the portal, not scored.
- No placement or pre-test that skips content an employee already knows.
- No skill assessments in the snapshot (0 rows), so no evidence can be produced yet.

**Runtime validation needed:** AI practice and revision modes once enabled.

### 5.4 Company Knowledge Assistant: not implemented

**Already there to reuse**

- Claude integration and safeguards (`assistant.py`).
- Private document storage (`materials`), the importer's text extraction, the Markdown renderer.
- Rate limiting and the audit log.
- SQLite on this machine supports **FTS5 full-text search** (SQLite 3.45.1), which allows document search with no new dependency.

**Missing**

- The assistant answers only from one course's lesson text. Uploaded documents and resources are sent as titles only, and nothing outside courses can be asked about.
- No library of approved internal documents. Nothing records owner, approval, version, review date, or which departments may read a document.
- No text extraction from PDF or Office documents. PDF text needs either an optional package (such as `pypdf`) or Claude's PDF input.
- No retrieval, no citations to the source passage, no "not covered by approved documents" behaviour across the library.
- No record of unanswered questions to show which policies are missing.

### 5.5 Training Effectiveness Analytics: partially implemented

**Already there**

- Admin Dashboard and Manager View: active learners, completion rate, certificates, training hours, pending mandatory training, department participation and completion, average assessment score.
- Reports: enrollments, employee progress, department statistics, assessment attempts with pass rate and average score, skills gaps, compliance, certificates.
- Training Compliance: on-time and late completion, overdue courses, department compliance, exports.
- Training-hour targets per employee.

**Missing**

- **Pre/post learning gain.** The `pre` assessment kind exists, but courses have no link to a pre-assessment, there are none in the snapshot, and no report compares pre and post scores.
- **Learner reaction.** No end-of-course rating or comment.
- **Skill uplift.** No report of skill-level change before and after training, by course or department.
- **On-the-job application.** No manager follow-up some weeks after a course.
- **Course quality signals.** No question-level difficulty or discrimination, no lesson drop-off, no time to completion.
- **Video in the hours figure.** Training hours still count verified video watch time (`analytics.training_seconds`), which conflicts with the text-only direction.

## 6. Shared AI foundation (build once, used by features 1–4)

### 6.1 Service module

Extract the client set-up from `assistant.py` into a small shared module (for example `backend/src/ai.py`) without changing the assistant's behaviour. It should hold:

- **Configuration and status:** `LMS_AI_ENABLED`, `LMS_AI_MODEL`, and a per-feature switch such as `LMS_AI_FEATURES=assistant,recommendations,idp,practice,knowledge`.
- **Rate limits and spend caps per employee per feature,** generalising `assistant_usage`.
- **One request helper** that applies the existing conventions: typed error mapping, `refusal` handling, refusal fallback (`server-side-fallback-2026-07-01` with `fallbacks: "default"`), prompt caching, and a timeout.
- **Usage logging:** feature, model, input/output/cache tokens and outcome, for cost reporting.

### 6.2 Model and API choices

- **Model.** Keep the project default `claude-opus-5-5`. Set `output_config.effort` explicitly per feature, because Opus 5.5 defaults to `medium`. Use `low` for short explanations and `medium`/`high` for IDP drafts and question writing. A cheaper model for high-volume routes is a cost decision for the owner; measure quality first.
- **Structured outputs** (`output_config.format` with a JSON schema), as `course_generator.py` already does, for recommendation rationales, IDP drafts and practice questions. The server validates every ID the model returns against the database.
- **Citations** for the Knowledge Assistant: pass retrieved passages as `document` blocks with `citations: {enabled: true}`, so each answer points to the exact approved text. Citations cannot be combined with `output_config.format`, so the Knowledge Assistant returns cited text, not JSON.
- **Message Batches** for nightly recommendation refreshes, at half price. Batches do not accept the `fallbacks` parameter, so batch results must handle `refusal` and fall back to the rule-based list.
- **Prompt caching:** keep stable instructions first and per-request content last, and check `cache_read_input_tokens` in the usage log.
- **No embeddings service is needed initially.** SQLite FTS5 (BM25 ranking) handles document retrieval with no new dependency. Revisit only if search quality measurably falls short.

### 6.3 Data minimisation (applies to every AI call)

- **No direct identifiers.** Never send names, emails, employee numbers or manager names to the API. Send skill levels, goals, course titles and scores keyed by an opaque request ID.
- **No answer keys or bank answers,** except when a trainer is writing questions.
- **No other employees' data.** No AI call may combine more than one employee's records.

## 7. Implementation plan by feature

Each feature below lists business requirements, workflows, UI, APIs, database changes, AI, permissions, security and tests. Route names follow the existing `/api/me/...` and `/api/manage/...` patterns.

### 7.0 Phase 0: foundations (prerequisite for 1–3 and 5)

| Work item | Notes |
|---|---|
| **Restore Skills & Goals screens** on the existing APIs | Employee: My Skills (levels, gaps, evidence, goals) using `GET me/skills` and `POST me/goals`. HR/Admin: skills catalogue, role competencies, evidence using `manage/skills`, `manage/competencies`, `manage/skill-evidence`. Manager: record evidence for reports. **No new backend.** This reverses a UI removal, so confirm why the screens were removed before restoring them. |
| **Restore Learning Paths screens** | Same: `manage/paths`, `me/paths` already exist. |
| **Seed the skills framework** | HR task, not code: create job roles, skills, role targets, and course skill tags (`course_skills`). Optionally import job titles from Keka. AI can propose course skill tags for HR to approve. |
| **Validate the existing AI features live** | Approve cost, enable on a test server, run the assistant and the course generator once each, and record results. This clears the "requires runtime validation" items. |
| **Shared AI module and usage logging** | [Section 6](#6-shared-ai-foundation-build-once-used-by-features-14). |
| **Video policy decision** | [Section 8.4](#84-text-only-content-policy). |

### 7.1 AI-powered personalised recommendations

**Business requirements**

- Every active employee sees relevant, explained course suggestions, including employees with little history.
- Suggestions come only from published courses the employee can open. The existing exclusions stay: completed, started and assigned courses.
- Mandatory and assigned training always comes first. Recommendations never hide it.
- Employees can dismiss a suggestion and say why. Quality is measured.

**Workflows**

| Role | Workflow |
|---|---|
| Employee | Sees "Recommended for you" on My Learning and My Dashboard, with reasons. Opens, enrols, or dismisses ("not relevant", "already know this", "not now"). Recommendations change as skills, goals and results change. |
| Manager | Sees the top recommendations for each direct report in Manager View, and can turn one into an optional assignment through the existing assignment flow. |
| HR | Maintains skills, role targets and course skill tags, which drive the rules. Sees recommendation take-up by department. |
| Admin | Turns the AI layer on or off and sets limits. Without it, rule-based recommendations still work. |

**Design: AI re-ranks, it does not invent**

1. The rule engine produces candidates (raise its limit from 6 to about 30) with scores and reasons.
2. If AI is enabled, Claude receives the employee's anonymised profile and the candidates' titles, descriptions and skill tags. The profile is role, skill levels and gaps, active goals, recent results and completed categories. Claude returns a re-ranked shortlist with a one-sentence reason each, via structured output.
3. The server drops any course ID not in the candidate list and keeps the rule reasons alongside the AI sentence.
4. Results are cached per employee until their inputs change (hash of profile and candidates), and refreshed nightly through Message Batches.
5. If AI is off or fails, the rule-based list is shown unchanged.

**Frontend:** a recommendation strip on My Learning reusing `recommendationCard`, with reason chips and a dismiss menu; a team recommendations panel in Manager View; a take-up chart in Reports.

**Backend APIs**

- `GET me/recommendations`: list with reasons and source (rules, or rules + AI).
- `POST me/recommendations/{courseId}/dismiss` with `{reason}`.
- `POST me/recommendations/{courseId}/opened`: records the click.
- `GET manage/recommendations?employee=`: manager or HR view, scoped.
- `GET manage/reports?type=recommendations`: take-up by department.

**Database changes**

- `recommendation_events(id, employee_id, course_id, source, reasons_json, ai_reason, shown_at, opened_at, dismissed_at, dismiss_reason)`.
- `recommendation_cache(employee_id PRIMARY KEY, inputs_hash, payload_json, model, created_at)`.

**Permissions:** an employee sees only their own. A manager sees direct reports. HR and Admin see everyone. Trainers do not see per-employee recommendations.

**Security**

- No identifiers sent; course IDs validated against the candidate list.
- Department-only courses filtered before the AI sees them.
- Dismiss reasons are a fixed list, with no free text sent to the AI.

**Testing**

- No skills data → department and category rules only, and no errors.
- A gap, a goal and a path each produce the expected reason.
- Completed, started and assigned courses are never recommended.
- An AI response with an unknown course ID is dropped.
- AI disabled or erroring → rule list unchanged.
- A dismissed course stays hidden and its dismissal is counted.
- A manager cannot read a non-report's recommendations.
- The cache refreshes when a goal is added.
- No names or emails appear in the request payload (assert on a stubbed client).

### 7.2 Individual Development Plans

**Business requirements**

- Each employee can have one active plan per period, for example a financial year, plus history.
- A plan contains development goals (reusing `learning_goals`), and actions linked to each goal: courses, learning paths, skill assessments, training sessions, external learning (`development_records`), or on-the-job tasks with a description.
- Plans are agreed with the reporting manager, checked in during the period and reviewed at the end.
- Progress updates automatically from completions, evidence and attendance. Nobody re-enters what the LMS already knows.
- AI can draft a plan; the employee and manager decide.

**Workflows**

| Role | Workflow |
|---|---|
| Employee | Creates a plan, or asks AI to draft one from role gaps, goals and interests. Edits goals and actions, then submits. After approval, works through actions; progress fills in automatically. Adds check-in notes, completes a self-review at period end. |
| Manager | Gets a notification on submission. Reviews, comments, requests changes or approves. Records check-ins and evidence for skills observed on the job. Sees a Team Development view: plan status, overdue actions, goals at risk. Can add optional courses via the existing assignment rules. |
| HR | Sets plan periods and review dates, sees plan coverage and completion across the organisation, can reassign plans when a manager changes (Keka sync), and can read any plan. |
| Admin | Same as HR, plus configuration and audit. |

**Frontend**

- Employee, **My Development**: one page with tabs for Plan, Skills and Goals (the restored Phase 0 screens), and History.
- Manager, **Team Development**: tabs for plans awaiting approval, team progress, and check-ins due.
- HR/Admin: a plan overview with filters and exports, reusing the compliance filter and table patterns.

**Backend APIs**

| Endpoint | Purpose |
|---|---|
| `GET/POST me/plans` | List and create |
| `GET me/plans/{id}` | Read one plan |
| `POST me/plans/{id}/items` | Add an action |
| `POST me/plans/{id}/items/{itemId}` | Edit or complete an action |
| `POST me/plans/{id}/submit` | Send for approval |
| `POST me/plans/{id}/checkins` | Add a check-in note |
| `POST me/plans/draft` | AI draft: returns a proposal and saves nothing |
| `GET manage/plans?status=&department=&employee=` | Scoped list |
| `GET manage/plans/{id}` | Read one plan |
| `POST manage/plans/{id}/approve` | Approve |
| `POST manage/plans/{id}/request-changes` | Send back with comments |
| `POST manage/plans/{id}/checkins` | Manager check-in |
| `POST manage/plans/{id}/review` | Period-end review |
| `GET/POST manage/plan-periods` | HR sets periods and review dates |

**Database changes**

- `development_plans(id, employee_id, period_id, status [draft, submitted, changes_requested, approved, active, closed], manager_id, summary, ai_drafted, submitted_at, approved_by, approved_at, closed_at, created_at, updated_at)`.
- `development_plan_items(id, plan_id, goal_id → learning_goals, kind [course, path, assessment, session, external, task], course_id, path_id, assessment_id, session_id, record_id, title, due_date, status, position)`.
- `development_plan_checkins(id, plan_id, author_id, kind [checkin, self_review, manager_review], note, created_at)`.
- `plan_periods(id, name, starts_on, ends_on, review_due_on)`.

Item status is derived from existing records where possible, not stored twice: completion from `course_runs`, results from `assessment_attempts`, attendance from `session_registrations`.

**AI**

- The draft request sends the anonymised profile, the gaps, active goals, and candidate courses and paths from the recommendation engine.
- Claude returns 2–5 goals, each with actions chosen only from the supplied lists plus free-text on-the-job tasks, through structured output.
- The proposal is shown for editing and saved only when the employee saves. `ai_drafted` is recorded.
- Skill levels and goal completion are never changed by AI.

**Permissions:** new `plans.review` (admin, hr, manager) and `plans.manage` (admin, hr). Managers act only for direct reports. An employee edits only their own plan, and only while it is draft or changes requested.

**Security**

- Plans contain career information: restrict reads to the employee, their current manager, HR and Admin, and audit approvals and manager changes.
- A previous manager loses access after reassignment.
- Free-text notes are never sent to AI unless the employee explicitly includes them in a draft request.

**Testing**

- Status changes: only an approved plan becomes active, and an employee cannot edit an approved plan.
- Completing a linked course or passing a linked skill assessment updates the item.
- Goal auto-completion still works through `record_evidence`.
- A manager cannot approve a non-report's plan.
- A change of manager moves pending approvals.
- The AI draft never references unknown course IDs, and saving nothing writes nothing.
- Period-end reminders are sent once (de-duplicated notifications).

### 7.3 Adaptive assessments and targeted practice

**Business requirements**

- Skill and placement assessments adapt to the employee: harder after correct answers, easier after wrong ones. They stop once a level is clear, giving a reliable level with fewer questions.
- Graded results stay fair: the same pass rules, server scoring, explanations without answer keys, attempt limits and time limits as today.
- Employees get targeted practice from what they got wrong: questions on the same skill or topic, not the same questions again.
- AI-written practice is clearly marked as practice. It never counts towards certificates or skill evidence unless a trainer approves the questions into a bank.

**Workflows**

| Role | Workflow |
|---|---|
| Employee | Takes an adaptive skill assessment and gets a level with explanations. Sees "Practise what you missed" after any assessment or knowledge check. Practice sets mix bank questions on the weak topics with optional AI-written questions; they are scored instantly and never graded. |
| Trainer / HR | Tags bank questions with skill, topic or lesson, and difficulty (1–3). AI can suggest tags for review. Marks an assessment as adaptive with start difficulty and stop rule. Reviews AI-written questions and approves the good ones into the bank. Sees question statistics. |
| Manager | Sees team practice activity and adaptive results as skill evidence, through existing reports. |
| Admin | Configuration and limits. |

**Adaptive algorithm (keep it simple and explainable)**

Use a staircase method, not a statistical model, at first:

1. Start at the configured difficulty.
2. After two consecutive correct answers at a level, move up. After one wrong answer, move down.
3. Stop when the employee has answered enough at one level (for example 3 of 4 correct at level *n* and 2 of 4 wrong at *n*+1), or at the maximum question count.
4. Map the stop level to the skill level: Beginner to Expert. The existing `record_evidence` records it.

**Frontend**

- In the existing assessment player: one question at a time for adaptive assessments, with no "back" button.
- In the question bank editor: tag fields and a difficulty selector.
- After a result: a practice panel with a "Practise what you missed" button.
- A **Practice** tab on My Development.
- For trainers: a review queue for AI-written questions.

**Backend APIs**

- `POST me/assessments/{id}/start`, which already exists, returns the first question for adaptive assessments.
- `POST me/assessments/{id}/answer` with `{attemptId, questionId, answer}` returns the next question or the final result. Scoring stays on the server.
- `POST me/practice` with `{source: attempt | skill | lesson, id}` creates a practice set.
- `GET me/practice/{id}`, `POST me/practice/{id}/submit`.
- `GET/POST manage/question-drafts`, `POST manage/question-drafts/{id}/approve`.
- `GET manage/assessments/{id}/question-stats`.

**Database changes**

- `assessment_bank`: new nullable columns `skill_id`, `topic`, `lesson_id`, `difficulty` (1–3).
- `assessments`: `mode` (`fixed` default, or `adaptive`), `start_difficulty`, `max_questions`.
- `assessment_attempts`: `sequence_json` for adaptive attempts (question, difficulty and correctness per step).
- `practice_sets(id, employee_id, source_kind, source_id, skill_id, items_json, created_at, submitted_at, score)`.
- `question_drafts(id, assessment_id, skill_id, topic, prompt, options_json, correct_option, explanation, difficulty, author [ai, trainer], status [pending, approved, rejected], reviewed_by, reviewed_at)`.

**AI**

- Writes practice questions from lesson text only, with the same no-answer-keys rule the assistant follows.
- Proposes tags and difficulty for existing questions, for trainer approval.
- Structured output with a fixed schema. The answer for AI practice items is kept on the server and checked there, as for bank questions.

**Permissions:** tagging and reviewing drafts follows `assessments.manage` (trainers for their own courses). Practice is the employee's own only.

**Security**

- Adaptive answers are checked one at a time on the server. The next question is chosen on the server, so the client cannot pick easy questions.
- Correct answers are never sent until the attempt ends.
- AI practice can never create skill evidence or certificates.
- Rate-limit practice generation.

**Testing**

- The staircase moves up and down and stops correctly.
- The same answers give the same level (deterministic with a fixed seed).
- The time limit and attempt limit still apply.
- No answer key appears in any response before completion.
- A practice set targets the missed topics.
- An unapproved AI question never appears in a graded attempt.
- A fixed-mode assessment behaves exactly as today (regression).

### 7.4 Company Knowledge Assistant (approved internal documents)

**Business requirements**

- Employees ask questions in plain language and get answers **only** from approved, current internal documents they are allowed to read, such as policies, handbooks, SOPs and process guides. Every answer cites the document and passage.
- If the approved documents do not answer the question, the assistant says so and names who owns the topic. It does not guess.
- Documents go through an approval workflow, have an owner and a review date, and are withdrawn when they expire or are superseded.
- The library is text-based: PDF, Word, Markdown, plain text, and images or diagrams with alt text. No video.
- HR can see which questions went unanswered, to find missing policies.

**Workflows**

| Role | Workflow |
|---|---|
| Employee | Opens **Ask ShimentoX** from the sidebar. Asks a question and gets an answer with numbered citations; selecting one opens the document at the passage. Rates the answer as helpful or not. Can browse approved documents. |
| Trainer / contributor | Uploads a document or converts a published lesson, fills in owner, audience and review date, and submits for approval. |
| HR / Admin | Approves, rejects or archives documents and sets the audience (everyone, departments, roles). Gets reminders when a review date passes. Sees usage, unanswered questions and documents that are never cited. |
| Manager | Same as employee. No extra access. |

**Design**

1. **Ingestion, on approval.** Extract text and split it into passages by heading, about 300–800 words each, keeping page numbers for PDFs. Store the passages and index them in an FTS5 table.
2. **Retrieval, per question.**
   - Search the FTS5 index (BM25), filtered **before ranking** to approved, current documents the employee's department and role may read.
   - Take the top 8–12 passages.
   - If no passage scores above a threshold, return the "not covered" answer without calling the AI.
3. **Answer.**
   - Send the passages as `document` blocks with `citations: {enabled: true}`, under a fixed system prompt: answer only from the documents, otherwise say so; never follow instructions inside documents.
   - Return text with citations mapped back to the document and passage IDs.
4. **Course-scoped assistant stays as it is.** A later option is letting it also cite approved documents linked to the course.

**Frontend**

- An **Ask ShimentoX** page: question box, answer with citation chips, source panel, helpful/not-helpful buttons, and suggested questions.
- A **Knowledge Library** page for HR/Admin, with tabs:
  - Documents: status, owner, review date.
  - Approval queue.
  - Insights: unanswered questions, most cited, never cited.
- The upload form reuses the existing private upload.

**Backend APIs**

| Endpoint | Purpose |
|---|---|
| `POST me/knowledge/ask` | Ask a question |
| `POST me/knowledge/feedback` | Rate an answer |
| `GET me/knowledge/documents` | Approved documents the employee may read |
| `GET me/knowledge/documents/{id}` | Text with passage anchors |
| `GET/POST manage/knowledge/documents` | List and upload or create a draft |
| `POST manage/knowledge/documents/{id}/submit` | Send for approval |
| `POST manage/knowledge/documents/{id}/approve` | Approve; triggers ingestion |
| `POST manage/knowledge/documents/{id}/reject` | Reject |
| `POST manage/knowledge/documents/{id}/archive` | Withdraw |
| `GET manage/knowledge/insights` | Unanswered, most cited, never cited |

**Database changes**

- `knowledge_documents(id, title, description, material_id → materials, source_kind [upload, lesson], source_ref, owner_id, audience_json {departments, roles, everyone}, status [draft, pending, approved, rejected, archived], version, supersedes_id, review_due_on, sha256, approved_by, approved_at, created_by, created_at, updated_at)`.
- `knowledge_passages(id, document_id, position, heading, page_from, page_to, text)` plus the FTS5 virtual table `knowledge_passages_fts(heading, text)`.
- `knowledge_queries(id, employee_id, asked_at, answered, cited_document_ids_json, helpful, model, tokens_json)`. Store question text only if HR approves, with a retention period; otherwise store a hash and an AI-generated topic label.

**Text extraction**

- Markdown and plain text: native.
- DOCX: the standard library's `zipfile` plus XML parsing.
- PDF:
  - **Option A:** add an optional `pypdf` dependency, like `anthropic` today.
  - **Option B:** send the PDF to Claude once at approval to extract text. This avoids the dependency but costs tokens per document.
- Images and diagrams: require alt text or a caption at upload; the text is indexed, not the image.

**Permissions:** new `knowledge.manage` (admin, hr) for approving and archiving, and `knowledge.contribute` (admin, hr, trainer) for drafting. Every signed-in employee can ask, limited to their audience.

**Security**

- **Access control before retrieval:** passages an employee may not read are never sent to the model, so the model cannot leak them.
- **Prompt injection:** documents are data. The system prompt says to ignore instructions inside them, and the answer can only be text with citations; there are no tools.
- **Uploads:** reuse the existing type and size checks, and record a SHA-256 so a document cannot change after approval.
- **Accountability:** audit every approval, rejection and archive. Per-employee rate limits.
- **Questions may contain personal data:** retention limit, and HR sees aggregates by default.
- **Withdrawal:** archived or expired documents disappear from retrieval at once.

**Testing**

- An answer cites only approved, current documents in the employee's audience.
- A department-restricted document is never retrieved for another department.
- No passage above the threshold gives "not covered" with no AI call.
- An injected instruction inside a document is not followed (eval case).
- Archiving removes passages from search immediately.
- Changed file bytes after approval are rejected.
- Feedback is recorded.
- Citation chips open the right passage.
- An eval set of about 50 real questions with expected source documents, scored for correct citation and correct "not covered" behaviour before rollout.

### 7.5 Training Effectiveness Analytics

**Business requirements**

Show whether training works, at four levels, using real records only.

| Level | Measure | Source |
|---|---|---|
| Reaction | Relevance, quality, confidence (1–5) and a comment after completing a course | New end-of-course feedback |
| Learning | Score gain from pre-assessment to post-assessment for the same course and employee | Existing `pre` and `post` assessment kinds, with a course link to its pre-assessment |
| Behaviour | Manager confirms 4–8 weeks later whether the skill is applied on the job | New manager follow-up |
| Results | Skill-level change for the employee, compliance on time, IDP goals achieved | Existing `skill_evidence` and compliance, new IDP |

Results are filterable by course, department, job role, period and trainer, exportable, and need a minimum group size before showing.

**Workflows**

| Role | Workflow |
|---|---|
| Employee | Gets a short optional feedback form after completing a course. Takes the course pre-assessment when the course has one; it is diagnostic and never blocks the course. |
| Manager | Gets a follow-up task some weeks after a report completes a course, and answers in about 30 seconds. Sees team effectiveness in Manager View. |
| Trainer | Sees effectiveness of their own courses: gain, feedback, question statistics, lesson drop-off. |
| HR / Admin | A **Training Effectiveness** page with tabs (Overview, Courses, Departments, Skills, Feedback), filters, exports and an optional AI summary of feedback comments. |

**Frontend:** a new page reusing the Training Compliance layout (header, tabs, filter panel, KPI cards, charts, table, CSV/Excel export). A feedback dialog after course completion. A manager follow-up list in Manager View.

**Backend APIs**

- `GET manage/effectiveness?tab=&course=&department=&jobRole=&trainer=&from=&to=` and `GET manage/effectiveness/export?format=csv|xlsx`.
- `POST me/feedback` with `{courseId, runId, relevance, quality, confidence, comment}`.
- `GET manage/followups` and `POST manage/followups/{id}`.
- `POST manage/effectiveness/feedback-summary`: AI summary of comments for one course.

**Database changes**

- `courses`: new nullable `pre_assessment_id`, matching the existing `post_assessment_id`.
- `course_feedback(id, employee_id, course_id, run_id UNIQUE, relevance, quality, confidence, comment, submitted_at)`.
- `training_followups(id, employee_id, course_id, run_id, manager_id, due_at, applied [yes, partly, no, not_applicable], note, answered_at)`, created by the existing reminder scheduler.
- No figures are stored; everything is calculated at request time, as the rest of the portal does.

**Calculations**

- **Learning gain:** for pairs with both a pre score and a post score, the mean of (post − pre) and the share with any gain. Use the first pre attempt and the best post attempt within the same course run.
- **Skill uplift:** level at period end minus level at period start, from dated `skill_evidence`.
- **Training hours:** text-based completions, sessions, and development records. Shown with and without the legacy video watch time until the video decision is made.

**AI (optional):** summarise the feedback comments for one course into themes, with counts and quotes. Comments are sent with no identifiers and only for groups of at least 5 responses.

**Permissions:** reuse `reports.view` with the existing scope rules. Feedback comments show to HR, Admin and the course trainer, without names by default.

**Security**

- Minimum group size (for example 5) for feedback and gain figures, so individuals cannot be identified.
- Anonymous display of comments.
- Exports audited, as compliance exports are.

**Testing**

- Gain matches hand-calculated data.
- Pre-assessment results never affect certificates.
- One feedback per run.
- Follow-up tasks are created once and only for the current manager.
- Groups below the threshold are hidden.
- A manager sees only direct reports.
- Filters combine correctly, and exports match the screen.
- Figures do not change when video data is excluded, apart from hours.

## 8. Cross-cutting requirements

### 8.1 Roles and permissions summary (new keys only)

| Permission | Admin | HR | Trainer | Manager | Employee |
|---|---|---|---|---|---|
| `plans.review` | ✓ | ✓ | | Reports | |
| `plans.manage` | ✓ | ✓ | | | |
| `knowledge.manage` | ✓ | ✓ | | | |
| `knowledge.contribute` | ✓ | ✓ | ✓ | | |
| `ai.configure` | ✓ | | | | |

Existing keys cover the rest: `skills.manage`, `skills.record`, `competencies.manage`, `assessments.manage`, `reports.view`. All checks stay on the server, as today.

### 8.2 Security and privacy

- **Credentials:** server-side only, as today. Keep `.env` out of git; `.env.example` lists names only.
- **Data sent to the AI provider:** no direct identifiers, no answer keys, no cross-employee data ([section 6.3](#63-data-minimisation-applies-to-every-ai-call)). Document this for employees in a short AI notice.
- **Human decisions stay human:** AI never changes skill levels, goal status, assessment results, certificates or approvals.
- **Audit and cost:** every AI request is logged with feature, tokens and outcome. Per-feature switches, per-employee limits and a monthly organisation cap.
- **Retention:** set periods for knowledge questions, usage logs and feedback comments.
- **Prompt injection:** treat documents, web pages, lesson text and comments as data in every prompt.
- **Data location:** if the company requires it, use the request's `inference_geo` setting where supported.

### 8.3 Notifications (reuse `services.notify` and `reminders.py`)

New notification types:

- plan submitted, approved, or changes requested;
- check-in due and review due;
- follow-up due (manager);
- document review due (owner);
- question drafts awaiting review (trainer).

All use de-duplication keys and stay in-app, like the existing notifications.

### 8.4 Text-only content policy

The direction is a text-based LMS, but the codebase still contains video features:

- the `videos`, `video_progress` and `lesson_watch` tables;
- video URL and file upload in the lesson builder;
- watch-time tracking and video serving (`course_video`);
- `backend/tools/generate_course_videos.py`;
- watch time counted in training hours;
- the original 3-module `python-programming` course, built on 6 videos.

The snapshot has no lesson with a video URL.

**Proposal:**

- None of the five features add or depend on video.
- As a separate decision, hide video options in the course builder and exclude video watch time from new metrics. Keep existing records readable so history is not lost.
- Removing the code is a later clean-up, once no course depends on it.

### 8.5 Testing approach

- Backend tests over real HTTP with an isolated SQLite database, as `backend/tests` does today, plus frontend contract tests in `frontend/tests`.
- **AI calls in automated tests use a stub client:** no network, no cost. Tests assert on request payloads (no identifiers, no answer keys) and on handling of refusal, rate limits, timeouts and malformed output.
- **Before enabling each AI feature:** a small eval set with real examples and expected properties, run against the live API once with cost approval, with results recorded in the docs.
- Browser checks of new pages at desktop, laptop, tablet and mobile widths, as done for Training Compliance.

## 9. Dependencies and implementation order

| Phase | Scope | Depends on | Why this order |
|---|---|---|---|
| **0. Foundations** | Restore Skills, Goals and Paths screens; seed job roles, skills, role targets and course skill tags; shared AI module and usage log; validate existing AI live; video decision | — | Features 1, 2, 3 and 5 depend on skills data that does not exist yet. AI cost and behaviour must be proven once before more is built on it. |
| **1. Effectiveness data capture** | Course pre-assessment link, end-of-course feedback, manager follow-ups (tables, forms, scheduler). Basic effectiveness page with gain and reaction. | 0 (partly) | Gain and reaction data only exist once collection starts, so start early. |
| **2. Recommendations** | Raise candidate limit, feedback events, AI re-ranking with cache and nightly batch, My Learning strip, manager panel | 0 | Biggest visible win once skills data exists. Reuses the existing engine. |
| **3. IDP** | Plans, items, check-ins, approvals, periods, My Development, Team Development, AI draft, reminders | 0, 2 | Builds on goals, skills and recommendations. |
| **4. Adaptive assessments and practice** | Question tagging (AI-assisted), staircase engine, practice sets, question-draft review | 0 | Needs tagged question banks; HR and trainers tag in parallel with phases 2–3. |
| **5. Knowledge Assistant** (parallel track after 0) | Document library and approval, extraction, FTS5 retrieval, cited answers, insights, eval set | 0 (AI module only) | Independent of skills data; can run alongside 1–4 with its own team. Needs a PDF extraction decision and an HR content owner. |
| **6. Effectiveness v2** | Skill uplift, IDP outcomes, recommendation take-up, AI feedback summaries, trainer views | 1, 2, 3 | Needs data from the earlier phases. |

**External dependencies and decisions**

- Approved AI budget and a monthly cap. Claude API credentials on the server.
- HR owner for the skills framework and the Knowledge Library.
- PDF extraction approach: optional `pypdf`, or Claude PDF input.
- Question text retention policy.
- Decision on hiding video options (section 8.4).
- Confirm why the skills and paths screens were removed before restoring them.
- Keka sync configured in production, for reliable managers and job titles.

## 10. Open questions for stakeholders

1. Why were the Skills, Goals and Learning Paths screens removed? Was it a deliberate product decision, or a simplification that can be reversed?
2. What is the plan period: financial year (April–March), calendar year, or per review cycle? Is IDP approval required for every employee or only some roles?
3. Who owns each knowledge area (HR policies, IT, security, finance)? Who approves documents?
4. May employee questions to the Knowledge Assistant be stored in full for HR analysis, and for how long?
5. Is a monthly AI spend cap needed, and at what level? Which features should be switched on first?
6. Should the employee's Keka employee number replace the internal account ID wherever an Employee ID is shown (`candidates.keka_employee_number` is already synced)?

## Appendix A: how to re-check the data snapshot

Read-only; safe on any copy of the database:

```powershell
python -c "import sqlite3; db=sqlite3.connect('file:backend/data/lms.sqlite3?mode=ro', uri=True); [print(t, db.execute(f'select count(*) from {t}').fetchone()[0]) for t in ('job_roles','skills','course_skills','role_competencies','skill_evidence','learning_goals','learning_paths','assessments','assistant_usage')]"
```
