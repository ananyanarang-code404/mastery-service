"""
STARTER FILE — build the actual service here (or restructure into more
files/modules if you prefer; this single-file skeleton is just a starting
point, not a requirement).

See PROBLEM.md for the full spec. Summary of what needs to exist by the end:

  POST /students/{student_id}/attempts
      Body: {"skill_id": str, "is_correct": bool}
      - Only the student themselves may submit their own attempts.
      - Updates that student's mastery score (0-100) for that skill using a
        scoring approach YOU design and justify in WRITEUP.md.
      - Calls get_ai_feedback() (see ai_feedback.py) to get a feedback
        string for the response. That call is slow and sometimes fails —
        your endpoint must still behave well when it does.
      - Enforces: max 30 attempts per student per rolling 24h. A request
        that fails validation (bad skill_id, malformed body, etc.) must NOT
        count against that limit.
      - If this attempt takes the student's mastery for that skill above 80
        for the first time, a milestone notification must be durably
        recorded — including surviving a crash between "mastery updated"
        and "notification recorded."

  GET /students/{student_id}/mastery
      - A student may view their own mastery.
      - A teacher may view mastery for any student on their own roster
        (see seed_data.TEACHER_ROSTERS), and no one else's.
      - Returns current mastery per skill for that student.

  GET /notifications/{student_id}
      - Same access rule as above. Returns the milestone notifications
        recorded for that student.

Everything below this docstring is scaffolding, not a solution — feel free
to delete, restructure, or heavily rewrite it.
"""

from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, StrictBool
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from mastery_service.access import authorize_read_access, authorize_student_self, resolve_identity
from mastery_service.ai_feedback import AIFeedbackError, get_ai_feedback
from mastery_service.db import Attempt, Mastery, Notification, get_db
from mastery_service.mastery import apply_attempt
from mastery_service.seed_data import SKILL_IDS

app = FastAPI(title="GenEd Mastery Service — Take-Home")

RATE_LIMIT_ATTEMPTS = 30
RATE_LIMIT_WINDOW = timedelta(hours=24)
FALLBACK_AI_MESSAGE = "We couldn't generate personalized feedback for this attempt — keep practicing!"


class AttemptRequest(BaseModel):
    skill_id: str
    is_correct: StrictBool


def count_recent_attempts(db: Session, student_id: str, now: datetime | None = None) -> int:
    """Number of attempts for a student in the last 24h (window inclusive).

    `now` is injectable so tests can check the exact window boundary
    deterministically; production uses the real clock.
    """
    cutoff = (now or datetime.now(timezone.utc)) - RATE_LIMIT_WINDOW
    return db.scalar(
        select(func.count())
        .select_from(Attempt)
        .where(
            Attempt.student_id == student_id,
            Attempt.created_at >= cutoff,
        )
    ) or 0


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/students/{student_id}/attempts")
def submit_attempt(
    student_id: str,
    payload: AttemptRequest,
    db: Session = Depends(get_db),
    authorization: str = Header(default=""),
) -> dict:
    identity = resolve_identity(authorization)
    authorize_student_self(identity, student_id)

    if payload.skill_id not in SKILL_IDS:
        raise HTTPException(status_code=422, detail="Unknown skill_id")

    if count_recent_attempts(db, student_id) >= RATE_LIMIT_ATTEMPTS:
        raise HTTPException(
            status_code=429,
            detail="Attempt limit reached: 30 per rolling 24 hours",
        )

    mastery = db.get(Mastery, (student_id, payload.skill_id))
    if mastery is None:
        mastery = Mastery(
            student_id=student_id,
            skill_id=payload.skill_id,
            score=0,
            milestone_notified=False,
        )
        db.add(mastery)

    mastery.score = apply_attempt(mastery.score, payload.is_correct)
    crossed_milestone = False
    if mastery.score > 80 and not mastery.milestone_notified:
        mastery.milestone_notified = True
        crossed_milestone = True
        db.add(
            Notification(
                student_id=student_id,
                skill_id=payload.skill_id,
                message=f"You crossed the 80% mastery milestone for {payload.skill_id}!",
            )
        )

    attempt = Attempt(
        student_id=student_id,
        skill_id=payload.skill_id,
        is_correct=payload.is_correct,
    )
    db.add(attempt)
    db.commit()

    try:
        feedback = get_ai_feedback(payload.skill_id, payload.is_correct)
        attempt.ai_feedback = feedback
        db.commit()
    except AIFeedbackError:
        feedback = FALLBACK_AI_MESSAGE

    return {
        "attempt_id": attempt.id,
        "student_id": student_id,
        "skill_id": payload.skill_id,
        "is_correct": payload.is_correct,
        "score": mastery.score,
        "crossed_milestone": crossed_milestone,
        "feedback": feedback,
    }


@app.get("/students/{student_id}/mastery")
def get_mastery(
    student_id: str,
    db: Session = Depends(get_db),
    authorization: str = Header(""),
):
    identity = resolve_identity(authorization)
    authorize_read_access(identity, student_id)
    rows = db.execute(
        select(Mastery)
        .where(Mastery.student_id == student_id)
        .order_by(Mastery.skill_id)
    ).scalars().all()
    return [{"skill_id": row.skill_id, "score": row.score} for row in rows]


@app.get("/notifications/{student_id}")
def get_notifications(
    student_id: str,
    db: Session = Depends(get_db),
    authorization: str = Header(""),
):
    identity = resolve_identity(authorization)
    authorize_read_access(identity, student_id)
    rows = db.execute(
        select(Notification)
        .where(Notification.student_id == student_id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
    ).scalars().all()
    return [
        {
            "id": row.id,
            "skill_id": row.skill_id,
            "message": row.message,
            "created_at": row.created_at,
        }
        for row in rows
    ]
