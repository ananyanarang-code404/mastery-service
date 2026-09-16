"""Tests for resilient handling of the slow/flaky AI feedback provider."""

from mastery_service.ai_feedback import AIFeedbackError
from mastery_service.db import Attempt, Mastery
from mastery_service.main import FALLBACK_AI_MESSAGE
import mastery_service.main as main_module

SKILL = "math.fractions.add-subtract"


def user_headers(token: str = "token-student-ananya") -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_ai_success_saves_and_returns_feedback(client, session, monkeypatch):
    monkeypatch.setattr(main_module, "get_ai_feedback", lambda skill_id, is_correct: "Nice work on fractions!")

    resp = client.post(
        f"/students/student-ananya/attempts",
        headers=user_headers(),
        json={"skill_id": SKILL, "is_correct": True},
    )
    assert resp.status_code == 200
    assert resp.json()["feedback"] == "Nice work on fractions!"

    attempt = session.get(Attempt, resp.json()["attempt_id"])
    assert attempt.ai_feedback == "Nice work on fractions!"


def test_ai_failure_returns_fallback_and_keeps_attempt(client, session, monkeypatch):
    def boom(skill_id, is_correct):
        raise AIFeedbackError("provider timed out")

    monkeypatch.setattr(main_module, "get_ai_feedback", boom)

    resp = client.post(
        f"/students/student-ananya/attempts",
        headers=user_headers(),
        json={"skill_id": SKILL, "is_correct": True},
    )
    assert resp.status_code == 200
    assert resp.json()["feedback"] == FALLBACK_AI_MESSAGE

    assert session.query(Attempt).count() == 1
    attempt = session.query(Attempt).one()
    assert attempt.ai_feedback is None

    mastery = session.query(Mastery).one()
    assert mastery.score == 20


def test_ai_failure_does_not_consume_extra_quota(client, session, monkeypatch):
    def boom(skill_id, is_correct):
        raise AIFeedbackError("provider timed out")

    monkeypatch.setattr(main_module, "get_ai_feedback", boom)

    resp = client.post(
        f"/students/student-ananya/attempts",
        headers=user_headers(),
        json={"skill_id": SKILL, "is_correct": True},
    )
    assert resp.status_code == 200

    monkeypatch.setattr(main_module, "get_ai_feedback", lambda skill_id, is_correct: "ok")
    resp = client.post(
        f"/students/student-ananya/attempts",
        headers=user_headers(),
        json={"skill_id": SKILL, "is_correct": True},
    )
    assert resp.status_code == 200
    assert session.query(Attempt).count() == 2