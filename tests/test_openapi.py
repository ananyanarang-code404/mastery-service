"""Tests for the OpenAPI security definition and the Swagger-friendly
Bearer auth plumbing.

Swagger UI can't attach plain `Header` params to "Try it out" requests, which
is why the endpoints authenticate through an HTTPBearer security scheme. These
tests lock in that the generated OpenAPI schema advertises the scheme and that
the auth contract is unchanged (valid token -> 200, missing/bad -> 401).
"""

from mastery_service.main import app

SKILL = "math.fractions.add-subtract"

PROTECTED_PATHS = [
    ("POST", "/students/{student_id}/attempts"),
    ("GET", "/students/{student_id}/mastery"),
    ("GET", "/notifications/{student_id}"),
]


def named_bearer_scheme() -> str:
    schemes = app.openapi()["components"]["securitySchemes"]
    for name, spec in schemes.items():
        if spec.get("type") == "http" and spec.get("scheme") == "bearer":
            return name
    raise AssertionError(f"no HTTP bearer security scheme in {schemes}")


def test_openapi_advertises_bearer_security():
    scheme = named_bearer_scheme()
    assert scheme


def test_all_protected_paths_declare_security():
    scheme = named_bearer_scheme()
    openapi = app.openapi()
    for method, path in PROTECTED_PATHS:
        operation = openapi["paths"][path][method.lower()]
        assert operation.get("security") == [{scheme: []}], (method, path)


def test_payload_params_do_not_expose_authorization_header():
    operation = app.openapi()["paths"]["/students/{student_id}/attempts"]["post"]
    header_params = [
        p for p in operation.get("parameters", []) if p.get("in") == "header"
    ]
    assert all(p.get("name") != "Authorization" for p in header_params)


def test_identity_dependency_accepts_bearer_token(client):
    resp = client.post(
        f"/students/student-ananya/attempts",
        headers={"Authorization": "Bearer token-student-ananya"},
        json={"skill_id": SKILL, "is_correct": True},
    )
    assert resp.status_code == 200


def test_identity_dependency_rejects_missing_token(client):
    resp = client.get("/students/student-ananya/mastery")
    assert resp.status_code == 401


def test_identity_dependency_rejects_bad_token(client):
    resp = client.get(
        "/students/student-ananya/mastery",
        headers={"Authorization": "Bearer bogus-token"},
    )
    assert resp.status_code == 401