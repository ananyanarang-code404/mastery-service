"""End-to-end integration tests: full user journeys on a file-backed DB,
including API-level durability across a service restart (mirrors real
process restarts on the production SQLite file)."""

import pytest
import sqlalchemy.orm
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from mastery_service.ai_feedback import AIFeedbackError
from mastery_service.db import Attempt, Base, get_db
from mastery_service.main import FALLBACK_AI_MESSAGE, app

SKILL = "math.fractions.add-subtract"
SKILL2 = "math.algebra.linear-equations"

ANANYA = "token-student-ananya"
ROHAN = "token-student-rohan"
KAVITA = "token-teacher-kavita"


def h(token):
    return {"Authorization": f"Bearer {token}"}


def post(client, token, student_id, skill_id, is_correct=True):
    return client.post(
        f"/students/{student_id}/attempts",
        headers=h(token),
        json={"skill_id": skill_id, "is_correct": is_correct},
    )


class RunningService:
    """A file-backed app instance that can be torn down and restarted on the
    same DB file — the integration-level equivalent of a process restart."""

    def __init__(self, db_url):
        self.db_url = db_url
        self._factory = None
        self._client = None
        self._start()

    def _start(self):
        engine = create_engine(self.db_url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(engine)
        self._factory = sessionmaker(bind=engine, expire_on_commit=False)

        def override_get_db():
            db = self._factory()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self._client = TestClient(app)

    def restart(self):
        self._stop()
        self._start()
        return self._client

    @property
    def client(self):
        return self._client

    def session(self):
        return self._factory()

    def _stop(self):
        if self._client is not None:
            self._client.close()
            self._client = None
        app.dependency_overrides.pop(get_db, None)

    def stop(self):
        self._stop()


@pytest.fixture()
def service(tmp_path):
    db_url = f"sqlite:///{str(tmp_path / 'service.db').replace(chr(92), '/')}"
    svc = RunningService(db_url)
    try:
        yield svc
    finally:
        svc.stop()


def test_student_full_journey_end_to_end(service):
    client = service.client

    post(client, ANANYA, "student-ananya", SKILL, False)
    for _ in range(7):
        post(client, ANANYA, "student-ananya", SKILL, True)
    crossing = post(client, ANANYA, "student-ananya", SKILL, True)
    assert crossing.json()["score"] == 83
    assert crossing.json()["crossed_milestone"] is True

    post(client, ANANYA, "student-ananya", SKILL2, True)

    mastery = client.get("/students/student-ananya/mastery", headers=h(ANANYA))
    assert mastery.status_code == 200
    assert mastery.json() == [
        {"skill_id": SKILL2, "score": 20},
        {"skill_id": SKILL, "score": 83},
    ]

    notifications = client.get("/notifications/student-ananya", headers=h(ANANYA))
    assert notifications.status_code == 200
    assert len(notifications.json()) == 1
    assert notifications.json()[0]["skill_id"] == SKILL
    assert "80" in notifications.json()[0]["message"]

    assert client.get("/students/student-ananya/mastery", headers=h(KAVITA)).status_code == 200
    assert (
        client.get("/students/student-ananya/mastery", headers=h(ROHAN)).status_code == 403
    )

    malformed = client.post(
        f"/students/student-ananya/attempts",
        headers=h(ANANYA),
        json={"skill_id": SKILL},
    )
    assert malformed.status_code == 422
    assert client.get("/students/student-ananya/mastery", headers=h(ANANYA)).json() == [
        {"skill_id": SKILL2, "score": 20},
        {"skill_id": SKILL, "score": 83},
    ]


def test_rate_limit_survives_restart(service):
    client = service.client
    for _ in range(20):
        assert post(client, ANANYA, "student-ananya", SKILL).status_code == 200

    client = service.restart()

    for _ in range(10):
        assert post(client, ANANYA, "student-ananya", SKILL).status_code == 200
    assert post(client, ANANYA, "student-ananya", SKILL).status_code == 429


def test_milestone_durability_survives_restart(service):
    client = service.client
    for _ in range(8):
        post(client, ANANYA, "student-ananya", SKILL, True)

    client = service.restart()

    assert client.get("/students/student-ananya/mastery", headers=h(ANANYA)).json() == [
        {"skill_id": SKILL, "score": 83}
    ]
    notifications = client.get("/notifications/student-ananya", headers=h(ANANYA)).json()
    assert len(notifications) == 1
    assert notifications[0]["skill_id"] == SKILL


def test_crash_before_commit_survives_restart(service, monkeypatch):
    real_commit = sqlalchemy.orm.Session.commit
    commit_count = [0]

    def flaky_commit(self):
        commit_count[0] += 1
        if commit_count[0] == 15:  # the crossing attempt's single transaction
            raise RuntimeError("simulated crash before commit")
        return real_commit(self)

    monkeypatch.setattr(sqlalchemy.orm.Session, "commit", flaky_commit)

    client = service.client
    for _ in range(7):
        post(client, ANANYA, "student-ananya", SKILL, True)
    with pytest.raises(RuntimeError):
        post(client, ANANYA, "student-ananya", SKILL, True)

    client = service.restart()

    assert client.get("/students/student-ananya/mastery", headers=h(ANANYA)).json() == [
        {"skill_id": SKILL, "score": 79}
    ]
    assert client.get("/notifications/student-ananya", headers=h(ANANYA)).json() == []
    with service.session() as s:
        assert s.query(Attempt).count() == 7


def test_ai_failures_inside_rate_limit_window(service, monkeypatch):
    import mastery_service.main as main_module

    def flaky_feedback(skill_id, is_correct):
        if not is_correct:
            raise AIFeedbackError("AI is down")
        return f"Feedback for {skill_id}"

    monkeypatch.setattr(main_module, "get_ai_feedback", flaky_feedback)

    client = service.client
    for i in range(30):
        correct = i % 2 == 0
        resp = post(
            client, ANANYA, "student-ananya", SKILL if correct else SKILL2, correct
        )
        assert resp.status_code == 200
        if correct:
            assert resp.json()["feedback"] == f"Feedback for {SKILL}"
        else:
            assert resp.json()["feedback"] == FALLBACK_AI_MESSAGE

    with service.session() as s:
        assert s.query(Attempt).count() == 30

    assert post(client, ANANYA, "student-ananya", SKILL, True).status_code == 429
    with service.session() as s:
        assert s.query(Attempt).count() == 30


def test_teacher_roster_isolation(service):
    client = service.client
    post(client, ANANYA, "student-ananya", SKILL)
    post(client, ROHAN, "student-rohan", SKILL)
    post(client, ROHAN, "student-rohan", SKILL)

    assert client.get("/students/student-ananya/mastery", headers=h(KAVITA)).status_code == 200
    assert client.get("/students/student-rohan/mastery", headers=h(KAVITA)).status_code == 200
    assert client.get("/notifications/student-rohan", headers=h(KAVITA)).status_code == 200

    assert (
        client.get("/students/student-mei/mastery", headers=h(KAVITA)).status_code == 403
    )
    assert (
        client.get("/students/nobody/mastery", headers=h(KAVITA)).status_code == 403
    )
    assert (
        client.get("/notifications/student-mei", headers=h(KAVITA)).status_code == 403
    )
    assert post(client, KAVITA, "student-ananya", SKILL).status_code == 403
    assert client.get("/students/student-rohan/mastery", headers=h(ANANYA)).status_code == 403