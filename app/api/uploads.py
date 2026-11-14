from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.upload import (
    DownloadURLRequest,
    DownloadURLResponse,
    UploadURLRequest,
    UploadURLResponse,
)
from app.services.storage_service import (
    generate_presigned_download_url,
    generate_presigned_upload_url,
)

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post("/presigned-url", response_model=UploadURLResponse)
def create_upload_url(
    payload: UploadURLRequest,
    current_user: User = Depends(get_current_user),
) -> UploadURLResponse:
    return generate_presigned_upload_url(current_user.id, payload)


@router.post(
    "/presigned-download-url",
    response_model=DownloadURLResponse,
)
def create_download_url(
    payload: DownloadURLRequest,
    current_user: User = Depends(get_current_user),
) -> DownloadURLResponse:
    return generate_presigned_download_url(current_user.id, payload.object_key)
