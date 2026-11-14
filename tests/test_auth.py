from datetime import timedelta

import jwt

from app.core.config import settings
from app.core.security import create_access_token
from app.services import auth_service
from app.utils.datetime import utc_now


def test_google_login_registers_and_returns_application_token(
    client, monkeypatch
):
    claims = {
        "sub": "google-new",
        "email": "New.User@Example.com",
        "email_verified": True,
        "name": "New User",
        "picture": "https://example.com/avatar.png",
    }
    monkeypatch.setattr(auth_service, "verify_google_token", lambda token: claims)

    response = client.post("/auth/google", json={"id_token": "verified"})

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == settings.jwt_expire_minutes * 60
    assert body["user"]["email"] == "new.user@example.com"
    assert jwt.decode(
        body["access_token"],
        settings.jwt_secret_key.get_secret_value(),
        algorithms=["HS256"],
    )["type"] == "access"


def test_google_login_rejects_an_existing_email_from_another_google_account(
    client, users, monkeypatch
):
    monkeypatch.setattr(
        auth_service,
        "verify_google_token",
        lambda token: {
            "sub": "different-google-id",
            "email": users[0].email,
            "email_verified": True,
        },
    )

    response = client.post("/auth/google", json={"id_token": "verified"})

    assert response.status_code == 409


def test_google_login_rejects_invalid_or_unverified_identity(client, monkeypatch):
    def invalid_google_token(token, request, audience):
        raise ValueError("invalid token")

    monkeypatch.setattr(
        auth_service.id_token,
        "verify_oauth2_token",
        invalid_google_token,
    )
    assert client.post("/auth/google", json={"id_token": "invalid"}).status_code == 401

    monkeypatch.setattr(
        auth_service.id_token,
        "verify_oauth2_token",
        lambda token, request, audience: {
            "sub": "google-unverified",
            "email": "unverified@example.com",
            "email_verified": False,
        },
    )
    assert client.post("/auth/google", json={"id_token": "unverified"}).status_code == 401


def test_expired_and_invalid_jwts_are_rejected(client):
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
