"""Tests for the rolling 24h / 30-attempt rate limit."""

from datetime import datetime, timedelta, timezone

from mastery_service.db import Attempt
from mastery_service.main import count_recent_attempts

SKILL = "math.fractions.add-subtract"
OTHER_SKILL = "math.algebra.linear-equations"

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


def user_headers(token: str = "token-student-ananya") -> dict:
    return {"Authorization": f"Bearer {token}"}


def post(client, student_id="student-ananya", *, token="token-student-ananya", **body):
    return client.post(
        f"/students/{student_id}/attempts",
        headers=user_headers(token),
        json=body,
    )


def seed_attempts(session, n, student_id="student-ananya", skill_id=SKILL, created_at=None):
    for _ in range(n):
        session.add(
            Attempt(
                student_id=student_id,
                skill_id=skill_id,
                is_correct=True,
                created_at=created_at,
            )
        )
    session.commit()


def test_30th_accepted_31st_rejected(client, session):
    seed_attempts(session, 29)
    assert post(client, skill_id=SKILL, is_correct=True).status_code == 200
    resp = post(client, skill_id=SKILL, is_correct=True)
    assert resp.status_code == 429
    assert session.query(Attempt).count() == 30


def test_rejected_attempt_is_not_recorded(client, session):
    seed_attempts(session, 30)
    resp = post(client, skill_id=SKILL, is_correct=True)
    assert resp.status_code == 429
    assert session.query(Attempt).count() == 30


def test_old_attempts_fall_out_of_window(client, session):
    old = datetime.now(timezone.utc) - timedelta(hours=25)
    seed_attempts(session, 29, created_at=old)
    assert post(client, skill_id=SKILL, is_correct=True).status_code == 200
    assert post(client, skill_id=SKILL, is_correct=True).status_code == 200


def test_different_skills_share_the_same_bucket(client, session):
    seed_attempts(session, 29, skill_id=OTHER_SKILL)
    assert post(client, skill_id=SKILL, is_correct=True).status_code == 200
    assert post(client, skill_id=SKILL, is_correct=True).status_code == 429


def test_invalid_requests_do_not_consume_quota(client, session):
    seed_attempts(session, 29)
    malformed = client.post(
        f"/students/student-ananya/attempts",
        headers=user_headers(),
        json={"skill_id": SKILL},
    )
    assert malformed.status_code == 422

    unknown = post(client, skill_id="does.not.exist", is_correct=True)
    assert unknown.status_code == 422

    assert post(client, skill_id=SKILL, is_correct=True).status_code == 200
    assert post(client, skill_id=SKILL, is_correct=True).status_code == 429
    assert session.query(Attempt).count() == 30


def test_at_cap_invalid_requests_still_422_not_429(client, session):
    seed_attempts(session, 30)
    malformed = client.post(
        f"/students/student-ananya/attempts",
        headers=user_headers(),
        json={"skill_id": SKILL, "is_correct": "not-a-bool"},
    )
    assert malformed.status_code == 422
    unknown = post(client, skill_id="does.not.exist", is_correct=True)
    assert unknown.status_code == 422
    assert session.query(Attempt).count() == 30


def test_rate_limit_is_per_student(client, session):
    seed_attempts(session, 30, student_id="student-ananya")

    resp = client.post(
        "/students/student-rohan/attempts",
        headers=user_headers("token-student-rohan"),
        json={"skill_id": SKILL, "is_correct": True},
    )
    assert resp.status_code == 200

    resp = post(client, skill_id=SKILL, is_correct=True)
    assert resp.status_code == 429


def test_window_cutoff_is_inclusive(session):
    cutoff = NOW - timedelta(hours=24)
    session.add(
        Attempt(
            student_id="student-ananya",
            skill_id=SKILL,
            is_correct=True,
            created_at=cutoff,
        )
    )
    session.add(
        Attempt(
            student_id="student-ananya",
            skill_id=SKILL,
            is_correct=True,
            created_at=cutoff - timedelta(microseconds=1),
        )
    )
    session.commit()
    assert count_recent_attempts(session, "student-ananya", now=NOW) == 1