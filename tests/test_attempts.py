"""HTTP tests for POST /students/{student_id}/attempts.

Rate limiting, AI feedback, and milestone durability are covered in later
phases; this phase verifies validation, authorization, and scoring.
"""

import pytest

from mastery_service.db import Attempt, Mastery

SKILL = "math.fractions.add-subtract"


def headers(token: str = "token-student-ananya") -> dict:
    return {"Authorization": f"Bearer {token}"}


def post(client, student_id="student-ananya", *, token="token-student-ananya", **body):
    return client.post(
        f"/students/{student_id}/attempts",
        headers=headers(token),
        json=body,
    )


def test_student_submits_own_attempt(client):
    resp = post(client, skill_id=SKILL, is_correct=True)
    assert resp.status_code == 200
    body = resp.json()
    assert body["student_id"] == "student-ananya"
    assert body["skill_id"] == SKILL
    assert body["is_correct"] is True
    assert body["score"] == 20
    assert body["attempt_id"] == 1


def test_attempts_accumulate_mastery(client):
    post(client, skill_id=SKILL, is_correct=True)
    post(client, skill_id=SKILL, is_correct=True)
    resp = post(client, skill_id=SKILL, is_correct=True)
    assert resp.json()["score"] == 49


def test_wrong_attempt_lowers_score(client):
    post(client, skill_id=SKILL, is_correct=True)
    post(client, skill_id=SKILL, is_correct=True)
    resp = post(client, skill_id=SKILL, is_correct=False)
    assert resp.json()["score"] == 29


def test_first_attempt_creates_mastery_row(client, session):
    post(client, skill_id=SKILL, is_correct=True)
    row = session.get(Mastery, ("student-ananya", SKILL))
    assert row is not None
    assert row.score == 20
    assert row.milestone_notified is False
    assert session.query(Attempt).count() == 1


def test_student_cannot_submit_for_another_student(client):
    resp = post(client, student_id="student-rohan", skill_id=SKILL, is_correct=True)
    assert resp.status_code == 403


def test_teacher_cannot_submit_at_all(client):
    resp = post(
        client,
        token="token-teacher-kavita",
        skill_id=SKILL,
        is_correct=True,
    )
    assert resp.status_code == 403


def test_missing_token_rejected(client):
    resp = client.post(
        f"/students/student-ananya/attempts",
        json={"skill_id": SKILL, "is_correct": True},
    )
    assert resp.status_code == 401


def test_unknown_token_rejected(client):
    resp = post(client, token="not-a-real-token", skill_id=SKILL, is_correct=True)
    assert resp.status_code == 401


def test_unknown_skill_rejected_without_rows(client, session):
    resp = post(client, skill_id="does.not.exist", is_correct=True)
    assert resp.status_code == 422
    assert session.query(Attempt).count() == 0
    assert session.query(Mastery).count() == 0


@pytest.mark.parametrize("body", [
    {"skill_id": SKILL},
    {"is_correct": True},
    {"skill_id": SKILL, "is_correct": "yes"},
    {"skill_id": 123, "is_correct": True},
    {},
])
def test_malformed_body_rejected_without_rows(client, session, body):
    resp = post(client, **body)
    assert resp.status_code == 422
    assert session.query(Attempt).count() == 0
    assert session.query(Mastery).count() == 0