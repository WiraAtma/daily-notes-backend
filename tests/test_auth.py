from datetime import timedelta

import jwt

from app.core.config import settings
from app.core.security import create_access_token
from app.models.user import User
from app.services.auth_service import password_hash
from app.utils.datetime import utc_now


def test_register_creates_user_and_returns_application_token(client, db_session):
    response = client.post(
        "/auth/register",
        json={
            "name": "  New User  ",
            "email": " New.User@Example.com ",
            "password": "secure-password",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == settings.jwt_expire_minutes * 60
    assert body["user"]["name"] == "New User"
    assert body["user"]["email"] == "new.user@example.com"
    assert "password_hash" not in body["user"]
    assert jwt.decode(
        body["access_token"],
        settings.jwt_secret_key.get_secret_value(),
        algorithms=["HS256"],
    )["type"] == "access"

    user = db_session.query(User).filter_by(email="new.user@example.com").one()
    assert password_hash.verify("secure-password", user.password_hash)


def test_register_rejects_duplicate_email_case_insensitively(client):
    payload = {
        "name": "New User",
        "email": "user@example.com",
        "password": "secure-password",
    }
    assert client.post("/auth/register", json=payload).status_code == 201

    payload["email"] = "USER@example.com"
    response = client.post("/auth/register", json=payload)

    assert response.status_code == 409


def test_login_returns_application_token(client):
    client.post(
        "/auth/register",
        json={
            "name": "New User",
            "email": "user@example.com",
            "password": "secure-password",
        },
    )

    response = client.post(
        "/auth/login",
        json={"email": "USER@example.com", "password": "secure-password"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["email"] == "user@example.com"
    assert body["token_type"] == "bearer"
    assert jwt.decode(
        body["access_token"],
        settings.jwt_secret_key.get_secret_value(),
        algorithms=["HS256"],
    )["type"] == "access"


def test_login_returns_same_error_for_unknown_email_and_bad_password(client):
    client.post(
        "/auth/register",
        json={
            "name": "New User",
            "email": "user@example.com",
            "password": "secure-password",
        },
    )

    unknown_email = client.post(
        "/auth/login",
        json={"email": "unknown@example.com", "password": "secure-password"},
    )
    wrong_password = client.post(
        "/auth/login",
        json={"email": "user@example.com", "password": "wrong-password"},
    )

    assert unknown_email.status_code == 401
    assert wrong_password.status_code == 401
    assert unknown_email.json() == wrong_password.json()


def test_register_rejects_invalid_email_and_short_password(client):
    invalid_email = client.post(
        "/auth/register",
        json={
            "name": "New User",
            "email": "not-an-email",
            "password": "secure-password",
        },
    )
    short_password = client.post(
        "/auth/register",
        json={
            "name": "New User",
            "email": "user@example.com",
            "password": "short",
        },
    )

    assert invalid_email.status_code == 422
    assert short_password.status_code == 422


def test_expired_and_invalid_jwts_are_rejected(client, users):
    expired = jwt.encode(
        {
            "sub": "1",
            "type": "access",
            "iat": utc_now() - timedelta(hours=2),
            "exp": utc_now() - timedelta(hours=1),
        },
        settings.jwt_secret_key.get_secret_value(),
        algorithm="HS256",
    )
    for token in (expired, "not-a-jwt"):
        assert client.get(
            "/notes",
            headers={"Authorization": f"Bearer {token}"},
        ).status_code == 401


def test_private_endpoint_requires_existing_authenticated_user(client, users):
    assert client.get("/notes").status_code == 401
    unknown_user_token = create_access_token(999999)
    assert client.get(
        "/notes",
        headers={"Authorization": f"Bearer {unknown_user_token}"},
    ).status_code == 401
