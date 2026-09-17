"""Tests for the read endpoints: GET /students/{id}/mastery and
GET /notifications/{id} — same access rules as everything else.
"""

SKILL = "math.fractions.add-subtract"
SKILL_2 = "math.algebra.linear-equations"


def h(token):
    return {"Authorization": f"Bearer {token}"}


def post_attempt(client, token, student_id, skill_id, is_correct=True):
    return client.post(
        f"/students/{student_id}/attempts",
        headers=h(token),
        json={"skill_id": skill_id, "is_correct": is_correct},
    )


def test_student_reads_own_mastery(client):
    post_attempt(client, "token-student-ananya", "student-ananya", SKILL)
    post_attempt(client, "token-student-ananya", "student-ananya", SKILL_2, False)

    resp = client.get("/students/student-ananya/mastery", headers=h("token-student-ananya"))
    assert resp.status_code == 200
    assert resp.json() == [
        {"skill_id": SKILL_2, "score": 0},
        {"skill_id": SKILL, "score": 20},
    ]


def test_student_with_no_attempts_gets_empty_list(client):
    resp = client.get("/students/student-rohan/mastery", headers=h("token-student-rohan"))
    assert resp.status_code == 200
    assert resp.json() == []


def test_student_cannot_read_another_student(client):
    resp = client.get("/students/student-rohan/mastery", headers=h("token-student-ananya"))
    assert resp.status_code == 403


def test_teacher_reads_roster_student_mastery(client):
    post_attempt(client, "token-student-ananya", "student-ananya", SKILL)
    resp = client.get("/students/student-ananya/mastery", headers=h("token-teacher-kavita"))
    assert resp.status_code == 200
    assert resp.json() == [{"skill_id": SKILL, "score": 20}]


def test_teacher_cannot_read_outside_roster(client):
    resp = client.get("/students/student-mei/mastery", headers=h("token-teacher-kavita"))
    assert resp.status_code == 403


def test_teacher_cannot_read_unknown_student(client):
    resp = client.get("/students/no-such-student/mastery", headers=h("token-teacher-kavita"))
    assert resp.status_code == 403


def test_unknown_token_rejected(client):
    resp = client.get("/students/student-ananya/mastery", headers=h("bogus"))
    assert resp.status_code == 401


def test_notifications_returned_after_milestone(client):
    for _ in range(8):
        post_attempt(client, "token-student-ananya", "student-ananya", SKILL)

    resp = client.get("/notifications/student-ananya", headers=h("token-student-ananya"))
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["skill_id"] == SKILL
    assert "80" in body[0]["message"]


def test_notifications_empty_for_teacher_before_milestone(client):
    resp = client.get("/notifications/student-rohan", headers=h("token-teacher-kavita"))
    assert resp.status_code == 200
    assert resp.json() == []


def test_notifications_newest_first(client):
    for _ in range(8):
        post_attempt(client, "token-student-ananya", "student-ananya", SKILL)
    for _ in range(8):
        post_attempt(client, "token-student-ananya", "student-ananya", SKILL_2)

    resp = client.get("/notifications/student-ananya", headers=h("token-student-ananya"))
    body = resp.json()
    assert [n["skill_id"] for n in body] == [SKILL_2, SKILL]


def test_notifications_access_rules(client):
    post_attempt(client, "token-student-rohan", "student-rohan", SKILL, True)
    assert client.get("/notifications/student-rohan", headers=h("token-student-ananya")).status_code == 403
    assert client.get("/notifications/student-mei", headers=h("token-teacher-kavita")).status_code == 403
    assert client.get("/notifications/student-ananya", headers=h("bogus")).status_code == 401
    assert client.get("/notifications/student-rohan", headers=h("token-teacher-kavita")).status_code == 200