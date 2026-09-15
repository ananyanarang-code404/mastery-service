"""Foundational tests for the persistence model."""

import pytest
from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError

from mastery_service.db import Attempt, Mastery, Notification, utcnow


def test_attempt_defaults(session):
    attempt = Attempt(student_id="student-ananya", skill_id="math.fractions.add-subtract", is_correct=True)
    session.add(attempt)
    session.commit()

    assert attempt.id is not None
    assert attempt.ai_feedback is None
    assert attempt.created_at is not None


def test_attempt_roundtrips_feedback(session):
    attempt = Attempt(
        student_id="student-mei",
        skill_id="science.physics.newtons-laws",
        is_correct=False,
        ai_feedback="review the last step",
    )
    session.add(attempt)
    session.commit()

    stored = session.get(Attempt, attempt.id)
    assert stored.ai_feedback == "review the last step"


def test_mastery_defaults(session):
    mastery = Mastery(student_id="student-rohan", skill_id="math.algebra.linear-equations")
    session.add(mastery)
    session.commit()

    assert mastery.score == 0
    assert mastery.milestone_notified is False
    assert mastery.updated_at is not None


def test_mastery_composite_pk_unique(session):
    session.add(Mastery(student_id="student-ananya", skill_id="math.fractions.add-subtract"))
    session.commit()

    with pytest.raises(IntegrityError):
        session.execute(
            insert(Mastery).values(
                student_id="student-ananya",
                skill_id="math.fractions.add-subtract",
            )
        )
        session.commit()
    session.rollback()


def test_notification_roundtrip(session):
    notification = Notification(
        student_id="student-ananya",
        skill_id="math.fractions.add-subtract",
        message="You just crossed 80% into mastery!",
    )
    session.add(notification)
    session.commit()

    stored = session.get(Notification, notification.id)
    assert stored.student_id == "student-ananya"
    assert stored.message.startswith("You just crossed 80%")
    assert stored.created_at is not None


def test_utcnow_returns_tz_aware_utc():
    now = utcnow()
    assert now.tzinfo is not None
    assert now.utcoffset().total_seconds() == 0