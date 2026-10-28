# Administering ShimentoX Learning

## First administrator

Run `npm start` and use the browser that opens. When no admin exists, a one-time **Set up your admin account** form appears. Enter your full name, email, and password. If that email already exists, use its current password to promote the account without losing records. The setup page is restricted to the server computer and is disabled once an administrator exists.

After signing in, open **Dashboard -> Users -> Create user**. Assign the new user's name, email, role, and temporary password. Account creation happens entirely in the portal; the terminal only starts the server.

## Role access

| Area | Admin | Candidate |
| --- | --- | --- |
| Dashboard | Organization overview | Personal learning overview |
| Courses | Draft/edit/publish/archive and preview | Published courses and own progress |
| Users | Create accounts, reset passwords, enable/disable, inspect records | No access |
| Activity log | Administrator audit history | No access |
| My profile | Own details/password | Own details/password and records |
| Achievements | Available during course preview | Own certificates |

Candidate navigation contains only Dashboard, My courses, My profile, and Achievements. Hidden admin routes also reject requests at the backend. The server reads roles from SQLite on every request rather than trusting a submitted role. A candidate cannot promote themselves.

## Candidate provisioning

1. Open Users and enter the full name and assigned email.
2. Select Candidate (or Administrator for a colleague who should manage the system).
3. Choose or generate a temporary password of at least eight characters.
4. Create the account and share the displayed credentials directly with the account owner. The app does not send email.
5. On first sign-in they must replace the temporary password with a different one. They cannot access course data, records, or management APIs until they do.

Passwords cannot be viewed later. Use Reset password to assign a new temporary password. Resetting revokes all existing sessions, terminates active exams, and repeats the password-change requirement. Disabling an account also revokes sessions and terminates active exams. An administrator cannot disable or reset their own account through these controls; use My profile to change your own password.

## Courses

Manage courses provides a metadata form and a curriculum JSON editor. New courses start as drafts using the included Python curriculum as a template. Replace the template with your actual lesson text, code, video URLs, exercises, and exams before publishing. The editor displays the entire structure; malformed or incomplete content is rejected by the server.

The current course workflow has exactly three sets, six lessons, two exercises with two questions per set, and one four-question exam per set. Each lesson includes `title`, `body`, `code`, `task`, `src`, `duration` (seconds, 1–7200), and optional `captions`. Media can reference an existing `assets/` path or a hosted HTTPS video URL. A video upload service is not included. External captions may require CORS configuration on the media host.

A question uses `[prompt, options, correctOptionIndex]`, with a fourth explanation string for exercises. Correct option indices start at zero. All answer keys remain private to admin endpoints and server-side grading.

Drafts and archived courses are hidden from candidate catalogs. Publish a validated course to make it available. Opening a course creates an independent candidate enrollment with its own progress, three-attempt exam limits, and certificate. Archiving preserves existing learning records. Metadata can be updated, but lesson/question content cannot change after enrollment; create a new course version to preserve assessment history.

### Removing a course

Use **Delete** in the course catalog (admins and HR for any course; trainers for their own courses).

- A course nobody has started is deleted permanently, with its lessons, assessments, assignments and learning-path entries. Scheduled training sessions are kept but no longer linked to it. Packaged courses (Java Full Stack, Python Programming Senior, Generative AI Fundamentals) that you delete are not re-created when the server restarts.
- A course with learner records (enrollments or assessment attempts) cannot be deleted, because that would erase employees' progress and certificates. Delete offers to **archive** it instead: it disappears from catalogs and learning paths, and every record is kept. The catalog shows each course's learner count.
- The starter course "PYTHON PROGRAMMING" cannot be deleted, because every new employee is enrolled in it. Archive it to hide it.

Every deletion and archive is recorded in the audit log.

### Course page layout and lesson text

Every lesson-based course uses the same course page: a progress header, a lesson view with a title block, and a "Course content" sidebar. This includes courses built in Manage Courses and packaged courses such as Java Full Stack and Generative AI. The builder's Preview step shows lessons in the same layout. Courses with knowledge checks or module assessments call their units "modules"; others call them "lessons".

Lesson text supports a small, safe Markdown subset; anything else shows as plain text:

- `## Heading` starts a section; lessons with three or more sections get an "On this page" jump list. The headings **Learning objectives**, **Common mistakes**, **Practice exercise** and **Key takeaways** are shown as coloured callouts.
- `### Subheading`, `-` or `*` bullet lists, `1.` numbered lists, and Markdown tables (a header row followed by a `| --- |` row).
- Fenced code with a language (for example `java`, `sql`, `bash`, `javascript`, `python`) gets a labelled code box with a Copy button.
- Inline `` `code` ``, `**bold**` and `*italic*`.
- Links in the form `[text](https://…)`, which open in a new tab.
- Lessons that use `:::` blocks (acronym cards, flows, examples, notes), `####` headings or nested lists are shown with the extended article formatting used by imported and article-style courses.

To group lessons into sections in the sidebar, start each lesson description with `Section N · Name.` (for example `Section 2 · Database Fundamentals. Design tables with keys.`). The prefix is shown as the section name and removed from the lesson overview.

## Importing a course from a URL

In **Manage Courses**, select **Add a course**, then **Import from URL** (**Create manually** opens the usual builder). Paste the address of a course or article, fill in the title, category, difficulty, department, estimated duration and visibility (title and duration are filled from the source when left blank), and select **Import**. Administrators, HR and trainers can import, the same roles that can create courses.

The importer identifies the site and chooses a strategy:

| Source | Strategy | What is kept |
| --- | --- | --- |
| Microsoft Learn | Learning path → modules → units; module → units; single unit or docs article | Module and unit names and order, unit text, code, tables |
| MIT OpenCourseWare | The course navigation: sections become modules, their sub-pages lessons | Page text, tables, code, links to lecture videos and PDFs, the CC BY-NC-SA licence |
| GeeksforGeeks, freeCodeCamp News | Single article | Heading hierarchy, code with language, lists, tables, figure links |
| Coursera, edX (also treated this way: Udemy, LinkedIn Learning, Pluralsight, Udacity, Skillshare, DataCamp, FutureLearn, O'Reilly) | Reference only | Public title, description and syllabus outline, with links to the course |
| IMS / SCORM `imsmanifest.xml` URL | The package's organisation tree | Modules and lessons from the manifest, each resource page's text |
| Any other public page | schema.org course outline, else a table of contents whose links sit below the page's address, else a single article | As above |

Microsoft Learn, MIT OpenCourseWare, GeeksforGeeks, freeCodeCamp News, Coursera, edX and docs.python.org (generic table of contents) were tested against the live sites. The other enrollment platforms in the table have not been tested; they are only classified as reference-only. Run `python backend/tools/import_smoke.py` to re-check the live sites, because their page layouts can change.

The **preview** shows the detected platform, licence (when the page states one), every module and lesson in the source's order with **Imported**, **Not retrieved** (with the reason) or **Reference** status, and each lesson's section outline. Select **Preview** on a lesson to read it as employees will see it. Nothing is stored until you save.

Choose what to save:

- **Import the lesson content**: requires confirming that ShimentoX may reuse it, under its licence or an agreement with the publisher. Lessons that could not be retrieved are kept in place with their title and a link to the original; no text is written for them.
- **Save as a course reference**: titles and structure with links to the original, no copied content. This is the only option for enrollment platforms and for sites that refuse automated access (sign-in, HTTP 403, robots.txt, CAPTCHA). For those sites, enter the course title yourself.

**Save as draft** or **Publish**. Imports are never published automatically. The course then opens in the course builder, where an **Imported from…** panel lists each lesson's import result, and you can edit lessons and add an assessment as for any course. Every imported lesson keeps a link to its original page, and the employee course page credits the source.

Limits: 40 lesson pages per import, 3 MB per page, 100,000 characters of text per lesson, about 75 seconds per import, two imports at a time. Lessons beyond the page limit are listed with links but not retrieved. Importing the same source again (ignoring tracking parameters and `#` anchors) is refused while a non-archived course from that source exists; archive it first to re-import.

The importer only reads public pages. It does not sign in, send cookies, bypass paywalls, CAPTCHAs or bot protection, or download videos. It only connects to public internet addresses on the standard ports. Local, private-network and cloud-metadata addresses are refused, including when a site redirects to one. It also follows robots.txt.

## Records and migration

View records shows a candidate's runs, video progress, every exercise submission, exams, and certificates. It never returns password hashes or session tokens. Activity log records account provisioning, resets, status changes, course saves, and initial browser setup without passwords.

Startup upgrades version 1 SQLite databases to version 2 automatically. Existing accounts retain their password and learning records and receive the candidate role. Only the one-time local setup page or an existing admin can grant admin access. Existing personalized passwords are not reset during migration.
