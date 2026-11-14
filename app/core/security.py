from datetime import timedelta

import jwt
from fastapi import HTTPException, status
from jwt.exceptions import InvalidTokenError

from app.core.config import settings
from app.utils.datetime import utc_now


def create_access_token(user_id: int) -> str:
    now = utc_now()
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> int:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub", "type"]},
        )
        if payload.get("type") != "access":
            raise InvalidTokenError("Unexpected token type")
        return int(payload["sub"])
    except (InvalidTokenError, TypeError, ValueError, KeyError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
