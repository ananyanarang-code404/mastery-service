"""Unit tests for token resolution and access-control rules."""

import pytest
from fastapi import HTTPException

from mastery_service.access import (
    authorize_read_access,
    authorize_student_self,
    resolve_identity,
)

STUDENT_ANANYA = {"role": "STUDENT", "user_id": "student-ananya"}
STUDENT_MEI = {"role": "STUDENT", "user_id": "student-mei"}
TEACHER_KAVITA = {"role": "TEACHER", "user_id": "teacher-kavita"}


def test_resolve_identity_valid_tokens():
    assert resolve_identity("Bearer token-student-ananya") == STUDENT_ANANYA
    assert resolve_identity("Bearer token-teacher-kavita") == TEACHER_KAVITA


def test_resolve_identity_missing_token():
    with pytest.raises(HTTPException) as exc:
        resolve_identity("")
    assert exc.value.status_code == 401


def test_resolve_identity_unknown_token():
    with pytest.raises(HTTPException) as exc:
        resolve_identity("Bearer not-a-real-token")
    assert exc.value.status_code == 401


@pytest.mark.parametrize("identity,target", [
    ({"role": "STUDENT", "user_id": "student-rohan"}, "student-rohan"),
])
def test_authorize_read_access_student_self_allowed(identity, target):
    authorize_read_access(identity, target)


def test_authorize_read_access_student_other_blocked():
    with pytest.raises(HTTPException) as exc:
        authorize_read_access(STUDENT_ANANYA, "student-rohan")
    assert exc.value.status_code == 403


def test_authorize_read_access_teacher_roster_allowed():
    authorize_read_access(TEACHER_KAVITA, "student-ananya")
    authorize_read_access(TEACHER_KAVITA, "student-rohan")


@pytest.mark.parametrize("target", ["student-mei", "student-missing", "nobody"])
def test_authorize_read_access_teacher_non_roster_blocked(target):
    with pytest.raises(HTTPException) as exc:
        authorize_read_access(TEACHER_KAVITA, target)
    assert exc.value.status_code == 403


def test_authorize_student_self_allowed():
    authorize_student_self(STUDENT_ANANYA, "student-ananya")


def test_authorize_student_self_other_student_blocked():
    with pytest.raises(HTTPException) as exc:
        authorize_student_self(STUDENT_ANANYA, "student-mei")
    assert exc.value.status_code == 403


def test_authorize_student_self_teacher_blocked():
    with pytest.raises(HTTPException) as exc:
        authorize_student_self(TEACHER_KAVITA, "student-ananya")
    assert exc.value.status_code == 403