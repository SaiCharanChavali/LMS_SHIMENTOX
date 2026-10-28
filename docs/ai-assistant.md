# AI learning assistant

The course page includes an optional AI learning assistant. It is **off by default**. While it is off, employees see a short notice instead of the assistant form, and no external calls are made.

## What it does

When enabled, an employee on a published course can:

- ask a question about the course,
- summarise a lesson (or the whole course),
- get a concept explained with an example,
- generate new practice questions,
- get revision suggestions based on their own module-exam and assessment results for that course.

Answers are grounded in the course's approved material: module titles and summaries, lesson text, example code, tasks, and the titles of supplementary resources. Exam and assessment questions and answer keys are never sent. Only published courses can be used, and employees can only ask about published content they can already open.

## Enabling it

1. Approve the cost (see below).
2. On the server, install the official SDK: `pip install anthropic`. The rest of the portal stays dependency-free.
3. Set environment variables before `npm start`:

   ```powershell
   $env:LMS_AI_ENABLED = '1'
   $env:ANTHROPIC_API_KEY = '<your key>'   # stays on the server; never sent to browsers
   # Optional:
   $env:LMS_AI_MODEL = 'claude-opus-5-5'  # default
   $env:LMS_AI_HOURLY_LIMIT = '20'         # requests per employee per hour (default 20)
   ```

4. Restart the server. `GET /api/me/assistant` reports whether the assistant is enabled.

The integration is in `backend/src/assistant.py`. It uses the Claude Messages API with prompt caching of the course material, and the server-side refusal fallback. It has not been exercised against the live API in this repository because no credentials are configured. Run one manual request after enabling it.

## Cost

This is a paid, usage-billed API. At the time of writing, `claude-opus-5-5` costs $4 per million input tokens and $20 per million output tokens. A typical request sends the course material (a few thousand tokens, cached after the first request for that course) plus a short question. Check current pricing on Anthropic's pricing page before enabling. Use `LMS_AI_HOURLY_LIMIT` to cap usage per employee.

## Safeguards

- Credentials are read only on the server.
- Every request is counted, even if it fails, and the per-employee hourly limit is enforced on the server.
- Upstream errors return a friendly message and never include credentials or raw provider errors.
- The UI tells employees that AI answers can be wrong and should be checked against the lesson.
