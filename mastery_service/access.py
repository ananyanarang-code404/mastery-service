"""Auth and authorization: token resolution plus student/teacher access
rules. Routes call these helpers; violations raise HTTPException(401/403).
"""

from fastapi import HTTPException

from mastery_service.seed_data import TEACHER_ROSTERS, TOKENS


def resolve_identity(authorization: str = "") -> dict:
    """Resolve the Authorization header into {"role", "user_id"}.

    The token map in seed_data.TOKENS is the entire auth system for this
    exercise. A missing or unknown token raises 401.
    """
    token = authorization.removeprefix("Bearer ").strip()
    identity = TOKENS.get(token)
    if identity is None:
        raise HTTPException(status_code=401, detail="Invalid or missing token")
    return identity


def authorize_read_access(identity: dict, target_student_id: str) -> None:
    """Allow a student to read only their own data and a teacher to read
    only students on their roster. Everything else is 403.
    """
    if identity["role"] == "STUDENT":
        if identity["user_id"] != target_student_id:
            raise HTTPException(
                status_code=403,
                detail="Students may only access their own data",
            )
        return

    if target_student_id not in TEACHER_ROSTERS.get(identity["user_id"], []):
        raise HTTPException(
            status_code=403,
            detail="Teacher may only access students on their own roster",
        )


def authorize_student_self(identity: dict, target_student_id: str) -> None:
    """Only the student themselves may submit their own attempts."""
    if identity["role"] != "STUDENT" or identity["user_id"] != target_student_id:
        raise HTTPException(
            status_code=403,
            detail="Only the student may submit their own attempts",
        )