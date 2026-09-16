"""Tests for durable "crossed above 80" milestone notifications."""

import pytest
import sqlalchemy.orm
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from mastery_service.db import Attempt, Base, Mastery, Notification

SKILL = "math.fractions.add-subtract"


def user_headers(token: str = "token-student-ananya") -> dict:
    return {"Authorization": f"Bearer {token}"}


def attempt(client, is_correct):
    return client.post(
        f"/students/student-ananya/attempts",
        headers=user_headers(),
        json={"skill_id": SKILL, "is_correct": is_correct},
    )


def test_no_notification_below_or_at_80(client, session):
    last = None
    for _ in range(7):
        last = attempt(client, True)
    assert last.json()["score"] == 79
    assert last.json()["crossed_milestone"] is False
    assert session.query(Notification).count() == 0


def test_milestone_created_on_first_crossing_above_80(client, session):
    for _ in range(7):
        attempt(client, True)
    resp = attempt(client, True)
    assert resp.json()["score"] == 83
    assert resp.json()["crossed_milestone"] is True

    notification = session.query(Notification).one()
    assert notification.student_id == "student-ananya"
    assert notification.skill_id == SKILL


def test_no_second_notification_while_above_80(client, session):
    for _ in range(8):
        attempt(client, True)
    assert session.query(Notification).count() == 1

    resp = attempt(client, True)
    assert resp.json()["crossed_milestone"] is False
    assert session.query(Notification).count() == 1


def test_recrossing_after_dip_does_not_re_notify(client, session):
    for _ in range(8):
        attempt(client, True)
    assert session.query(Notification).count() == 1

    score = 83
    while score > 80:
        resp = attempt(client, False)
        score = resp.json()["score"]
    assert score < 80

    while score <= 80:
        resp = attempt(client, True)
        score = resp.json()["score"]
    assert score > 80
    assert resp.json()["crossed_milestone"] is False
    assert session.query(Notification).count() == 1
    assert session.get(Mastery, ("student-ananya", SKILL)).milestone_notified is True


def test_crash_before_commit_leaves_no_partial_state(client, session, monkeypatch):
    """Simulate the process dying at the commit that would persist the score
    bump AND the milestone notification. The single-transaction design means
    nothing is partially written: no attempt, no score change, no notification.
    """
    real_commit = sqlalchemy.orm.Session.commit
    commit_count = [0]

    def flaky_commit(self):
        commit_count[0] += 1
        if commit_count[0] == 15:
            raise RuntimeError("simulated crash before commit")
        return real_commit(self)

    monkeypatch.setattr(sqlalchemy.orm.Session, "commit", flaky_commit)

    for _ in range(7):
        attempt(client, True)

    with pytest.raises(RuntimeError):
        attempt(client, True)

    assert session.query(Attempt).count() == 7
    assert session.get(Mastery, ("student-ananya", SKILL)).score == 79
    assert session.query(Notification).count() == 0


def test_committed_transaction_survives_restart(tmp_path):
    """A committed transaction (attempt + mastery + notification) must survive
    a process restart — here simulated by tearing down and reopening the
    file-backed engine, mirroring how the production DB persists across runs.
    """
    db_path = tmp_path / "restart.db"
    url = f"sqlite:///{db_path}"
    engine = create_engine(url)
    Base.metadata.create_all(engine)

    first = sessionmaker(bind=engine, expire_on_commit=False)()
    first.add(
        Mastery(student_id="student-ananya", skill_id=SKILL, score=83, milestone_notified=True)
    )
    first.add(Attempt(student_id="student-ananya", skill_id=SKILL, is_correct=True))
    first.add(Notification(student_id="student-ananya", skill_id=SKILL, message="milestone"))
    first.commit()
    first.close()
    engine.dispose()

    reopened = sessionmaker(bind=create_engine(url), expire_on_commit=False)()
    assert reopened.query(Attempt).count() == 1
    assert reopened.query(Mastery).count() == 1
    assert reopened.query(Notification).count() == 1
    reopened.close()