# GenEd Backend Take-Home Project

## Skill Mastery Tracker 

A small service, built the way we actually build things here.

## Why we're doing it this way

We'd rather see how you actually work than how you answer questions about working. This project is a small, self-contained version of a real problem we deal with at GenEd: tracking what a student has mastered, dealing with an AI provider that's slow and occasionally fails, and making sure something as important as a milestone alert doesn't silently vanish if a server hiccups at the wrong moment.

It's scoped to be doable in about 3 days of focused part-time work — we are not expecting a production system. We're looking at how you think, what you prioritize, and whether your explanation of your own code holds up, not whether you produce the single "correct" answer (there isn't one).

## The scenario

Every time a student answers a practice question on GenEd, we update our estimate of how well they've mastered that specific skill. When a student crosses a mastery milestone, we want to reliably record that so it can be surfaced to them (and eventually a parent or teacher). Generating personalized feedback on each attempt goes through an AI provider that is not always fast or reliable. Your job is to build the backend service that makes all of this work.

## What you're given

A starter repo (separate zip) with:

- `mastery_service/ai_feedback.py` — a stand-in for our real AI feedback provider. It deliberately sleeps 0.5–5 seconds and fails about 15% of the time. Do not rewrite it to be faster or more reliable — your service needs to handle it as-is.
- `mastery_service/seed_data.py` — a fake auth token map (STUDENT / TEACHER roles) and a small student/teacher roster. There is no signup or password flow to build.
- `mastery_service/main.py` — a FastAPI skeleton with the routes stubbed as TODOs, and a working health check + auth resolver so you have something running on minute one.
- A README with setup/run/test instructions.

## What you need to build

### 1. Submit a practice attempt

`POST /students/{student_id}/attempts`

Request body:

```json
{
  "skill_id": "str",
  "is_correct": true
}
```

Requirements:

- Only the student themselves may submit their own attempts.
- Update that student's mastery score (0–100) for that skill.
- The scoring approach is yours to design — a simple moving average, a streak-based system, spaced-repetition-style decay, anything defensible.
- Document your choice and its trade-offs in `WRITEUP.md`.
- Call `get_ai_feedback()` to get a feedback string to return alongside the result.
- This call is slow and sometimes fails — your endpoint needs to behave sensibly either way. "Sensibly" is for you to define and justify.
- Enforce a limit of 30 attempts per student per rolling 24 hours. The 31st attempt in that window should be rejected.
- A request that fails validation (bad `skill_id`, malformed body) must NOT count against that limit.
- If this attempt takes the student's mastery for that skill above 80 for the first time, durably record a milestone notification — including surviving a crash between the mastery update and the notification being recorded.
- We've shipped bugs before where a crash between two steps like this silently dropped an alert — we want to see how you reason about it, not just "add a try/except."

### 2. Check current mastery

`GET /students/{student_id}/mastery`

Requirements:

- A student may view their own mastery.
- A teacher may view mastery for any student on their own roster (see `TEACHER_ROSTERS` in `seed_data.py`) — and no one else's.
- Returns current mastery per skill for that student.

### 3. Check milestone notifications

`GET /notifications/{student_id}`

Requirements:

- Same access rule as above.
- Returns the milestones recorded for that student.

## Stretch goals

Optional — pick what interests you, not all of them:

- Mastery decay for skills a student hasn't practiced in a while.
- A teacher-facing roster summary endpoint.
- A test suite covering the crash-during-notification case, the rate-limit boundary, and the flaky dependency. You'll likely want to monkeypatch/wrap `ai_feedback` for this — no need to actually wait 5 seconds per test.
- A Dockerfile / docker-compose for a one-command run.
- Structured logging.

## Constraints

Please don't build past these:

- SQLite (or even a clearly-documented in-memory store) is fine. No need to stand up Postgres or Redis.
- No real signup/password flow — use the given token map as-is.
- No frontend needed. The interactive docs FastAPI generates for you (`/docs`), curl, or Postman are enough.
- We're not grading on deployment, CI, or infra polish — a service that runs locally and does the right thing is the bar.

## On using AI coding tools

Use them if you want to — most engineers do, and we're not going to pretend otherwise. What we care about is whether you understand and can defend every decision in what you submit.

Part of your writeup (below) asks directly what you used AI help for and what you changed from what it gave you, and we'll ask you to walk through specific parts of your own code afterward.

Submissions that read like no one who wrote them could explain them are a bigger problem for us than which tools you used.

## What to submit

- Your code (a git repo with normal incremental commits is preferred over one giant commit at the end — we're genuinely interested in how you got there, not just the destination).
- `WRITEUP.md`, filled in (template included in the starter repo) — covers:
  - Your mastery-scoring approach
  - How you handled the flaky AI call
  - How you reasoned about the crash-durability requirement
  - How your rate limit behaves at the boundary
  - What you'd do next with more time
  - What you're least confident about
  - Your AI-tool usage
- Instructions to run it, if they differ from the starter README.

Send it back to us as a zip or a link to a repo (private is fine — just make sure we have access) within 3 days of receiving this.

If something is ambiguous, make a reasonable call and write down why in `WRITEUP.md` — figuring out what to do with an underspecified requirement is itself part of what we're evaluating.

## After you submit

We'll follow up with a short (15–20 min) conversation about your specific submission — walking through a couple of the decisions above in your own words.

This isn't a second interview so much as making sure the writeup and the conversation match what the code actually does.
