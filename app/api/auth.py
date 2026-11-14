from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token
from app.db.session import get_db
from app.schemas.auth import GoogleLoginRequest, TokenResponse
from app.schemas.user import UserRead
from app.services.auth_service import authenticate_google_user

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/google", response_model=TokenResponse)
def google_login(
    payload: GoogleLoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    user = authenticate_google_user(db, payload.id_token)
    return TokenResponse(
        access_token=create_access_token(user.id),
        expires_in=settings.jwt_expire_minutes * 60,
        user=UserRead.model_validate(user),
    )
