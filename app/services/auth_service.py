from typing import Any

import google.auth.exceptions
from google.auth.transport.requests import Request
from google.oauth2 import id_token
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token
from app.models.user import User
from app.utils.datetime import utc_now


def verify_google_token(token: str) -> dict[str, Any]:
    try:
        claims = id_token.verify_oauth2_token(
            token,
            Request(),
            audience=settings.google_client_id,
        )
    except (ValueError, google.auth.exceptions.GoogleAuthError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google ID token",
        ) from exc

    if (
        not claims.get("sub")
        or not claims.get("email")
        or claims.get("email_verified") is not True
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google account must have a verified email",
        )
    return claims


def authenticate_google_user(db: Session, token: str) -> User:
    claims = verify_google_token(token)
    google_id = str(claims["sub"])
    email = str(claims["email"]).strip().lower()

    user = db.scalar(select(User).where(User.google_id == google_id))
    if user is not None:
        user.name = str(claims.get("name") or user.name)[:255]
        user.email = email
        user.avatar = claims.get("picture")
        user.updated_at = utc_now()
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Google account conflicts with an existing user",
            ) from exc
        db.refresh(user)
        return user

    existing_email_user = db.scalar(select(User).where(User.email == email))
    if existing_email_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already associated with another Google account",
        )

    user = User(
        google_id=google_id,
        name=str(claims.get("name") or email.split("@", 1)[0])[:255],
        email=email,
        avatar=claims.get("picture"),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        concurrent_user = db.scalar(select(User).where(User.google_id == google_id))
        if concurrent_user is not None:
            return concurrent_user
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Google account conflicts with an existing user",
        ) from exc
    db.refresh(user)
    return user
