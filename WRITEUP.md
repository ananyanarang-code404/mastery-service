<!--
Fill this in and submit it alongside your code. Answer in your own words —
these are the questions we'll also ask you about in the follow-up
conversation, so they should match what your code actually does.
-->

# Writeup

## 1. Mastery scoring

What formula/approach did you use to turn a sequence of correct/incorrect
attempts into a 0-100 mastery score? Why this one, and what does it get
wrong that a better version would fix?

I used an Exponential Moving Average (EMA) with α = 0.2 for the mastery score.

For every attempt, the score moves a little towards 100 if the answer is correct and towards 0 if it is wrong:

new_score = round(old_score + 0.2 × (target - old_score))

The result is kept between 0 and 100.

I chose EMA because I wanted recent attempts to have more effect on the score without making one wrong answer completely reset the student's progress. For example, starting from 0, eight consecutive correct attempts take the score above 80.

One limitation is that the score does not have any time-based decay. So if a student reaches a high score and then stops practicing, the score will still remain high. If I had more time, I would add a decay mechanism for skills that have not been practiced for some time.


## 2. The flaky AI dependency

How does your `/attempts` endpoint behave when `get_ai_feedback` is slow?
When it raises `AIFeedbackError`? What would a student actually see in each
case?

I treated the attempt and mastery update as the important part, and the AI feedback as an additional feature.

The attempt is saved to the database before the AI feedback call is made. The AI call is made inline because the API is expected to return feedback along with the attempt response.

The provided AI service is deliberately slow and can also fail. If it raises AIFeedbackError, I return a normal 200 response with a fallback message instead of making the whole attempt fail. The attempt remains saved and ai_feedback stays NULL because no actual feedback was generated.

This also means that an AI failure does not undo the mastery update, consume the student's work, or give them a free attempt outside the rate limit.

I chose this approach because I felt the student's submitted attempt should not depend on whether the external AI service happens to be available at that moment.


## 3. The crash-durability requirement

Walk through what happens, step by step, if the process crashes right after
a student's mastery crosses 80 for a skill but before the milestone
notification is recorded. What guarantees does your design actually give,
and what would you still worry about?

For the milestone requirement, I wanted the attempt, mastery update, and notification to be part of the same database transaction.

They are committed together, so there isn't a separate step where the mastery score can be updated successfully but the notification fails to get recorded.

The database is file-backed SQLite, so the committed data also survives a process restart.

I added tests for this as well. One test simulates a failure before the transaction is committed and checks that there is no partial state. The integration tests also restart the service and verify that the already-committed attempt, mastery score, and milestone are still present.

I also keep a milestone_notified flag for each student/skill. This makes the milestone a first-time event: if the score goes above 80, then later falls below it and crosses 80 again, another notification is not created.

## 4. Rate limiting

How does your 30-attempts/24h limit work? What happens right at the
boundary (attempt #30, attempt #31, a request that fails validation)?

I implemented the limit as 30 attempts per student in a rolling 24-hour window, across all skills.

Before accepting an attempt, I count that student's attempts from the previous 24 hours. The 30th attempt is accepted, while the 31st is rejected with a 429.

I also made validation happen before the rate-limit check. This was important because the assignment says invalid requests should not consume the student's quota. So a malformed request or an unknown skill returns 422 without increasing the attempt count.

The rate limit is based on submitted attempts, so an attempt still counts even if the AI feedback call later fails.

I also added tests around the 30/31 boundary and invalid requests at the limit.

## 5. If you had another 3 days

What would you build or fix next, in priority order?

If I had three more days, I would focus on:

Notification delivery — currently the milestone is stored reliably, but there is no actual UI/push/inbox system for delivering it to the student.
Mastery decay — reduce mastery when a skill has not been practiced for a long time.
Concurrency improvements — the current implementation is designed around a single-process SQLite setup. I would look at SQLite locking/WAL and the rate-limit behavior with multiple workers.
Teacher roster summary — add the stretch-goal endpoint for viewing summary information across a teacher's students.
Better scoring — support partial credit instead of only correct/incorrect attempts.

I would prioritize these based on whether the service was going to remain a small local service or be used by multiple users in production.

## 6. Least confident about

Which part of this submission are you least sure is correct or
well-designed? (This isn't a trick question — we'd rather you tell us than
we find out later.)

The area I'm least confident about is concurrency at a larger scale.

For the current assignment, I designed and tested the service around a single-process SQLite setup. The transaction handles the important durability requirement, but multiple workers making requests at the same time would need more consideration, especially around SQLite locking and rate-limit races.

I would be comfortable explaining and defending the current implementation, but if this were being moved to a larger production setup, concurrency is the first area I would investigate further.


## 7. AI tool use

Which parts, if any, did you use an AI coding assistant for? What did you
have to fix, reject, or rework from what it gave you?

I used GitHub Copilot and OpenCode during development to help me understand the starter repository, break the assignment into smaller phases, and work through the implementation. I reviewed the proposed approaches, made the implementation decisions, and implemented and tested each phase separately.

I used an AI coding assistant throughout the implementation for debugging, code review, and identifying edge cases. It helped identify issues such as create_tables() not being connected to FastAPI startup, the non-atomic rate-limit check allowing concurrent requests to exceed the limit, and the second database commit potentially returning 500 after an attempt was already recorded. I reviewed and verified these findings against the requirements and tests, rather than accepting the AI output blindly.