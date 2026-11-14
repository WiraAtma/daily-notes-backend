from uuid import uuid4

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException, status

from app.core.config import settings
from app.schemas.upload import (
    DownloadURLResponse,
    UploadURLRequest,
    UploadURLResponse,
)

MAX_FILE_SIZE = 5 * 1024 * 1024
URL_EXPIRES_IN = 300
CONTENT_TYPE_EXTENSIONS = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


def _get_s3_client():
    if not all(
        (
            settings.s3_endpoint_url,
            settings.s3_access_key,
            settings.s3_secret_key,
            settings.s3_bucket_name,
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Object storage is not configured",
        )
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key.get_secret_value(),
        aws_secret_access_key=settings.s3_secret_key.get_secret_value(),
        region_name=settings.s3_region,
    )


def generate_presigned_upload_url(
    user_id: int, request: UploadURLRequest
) -> UploadURLResponse:
    if request.file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Image must be 5 MiB or smaller",
        )
    extension = CONTENT_TYPE_EXTENSIONS[request.content_type]
    object_key = f"users/{user_id}/notes/{uuid4()}.{extension}"
    try:
        url = _get_s3_client().generate_presigned_url(
            "put_object",
            Params={
                "Bucket": settings.s3_bucket_name,
                "Key": object_key,
                "ContentType": request.content_type,
            },
            ExpiresIn=URL_EXPIRES_IN,
        )
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to create upload URL",
        ) from exc
    return UploadURLResponse(
        upload_url=url,
        object_key=object_key,
        expires_in=URL_EXPIRES_IN,
    )


def generate_presigned_download_url(
    user_id: int, object_key: str
) -> DownloadURLResponse:
    _require_ownership(user_id, object_key)
    try:
        url = _get_s3_client().generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.s3_bucket_name, "Key": object_key},
            ExpiresIn=URL_EXPIRES_IN,
        )
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to create download URL",
        ) from exc
    return DownloadURLResponse(download_url=url, expires_in=URL_EXPIRES_IN)


def get_user_image_data(user_id: int, object_key: str) -> tuple[bytes, str]:
    _require_ownership(user_id, object_key)
    response = None
    try:
        response = _get_s3_client().get_object(
            Bucket=settings.s3_bucket_name,
            Key=object_key,
        )
        if response["ContentLength"] > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Image must be 5 MiB or smaller",
            )
        image_bytes = response["Body"].read(MAX_FILE_SIZE + 1)
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code")
        if error_code in {"NoSuchKey", "NotFound", "404"}:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Object not found",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to read image from object storage",
        ) from exc
    except BotoCoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to read image from object storage",
        ) from exc
    finally:
        if response is not None:
            response["Body"].close()

    if len(image_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Image must be 5 MiB or smaller",
        )

    if image_bytes.startswith(b"\xff\xd8\xff"):
        mime_type = "image/jpeg"
    elif image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        mime_type = "image/png"
    elif image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP":
        mime_type = "image/webp"
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Object is not a supported image",
        )
    return image_bytes, mime_type


def delete_user_object(user_id: int, object_key: str) -> None:
    _require_ownership(user_id, object_key)
    try:
        _get_s3_client().delete_object(Bucket=settings.s3_bucket_name, Key=object_key)
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to delete object",
        ) from exc


def _require_ownership(user_id: int, object_key: str) -> None:
    if not object_key.startswith(f"users/{user_id}/notes/"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Object not found",
        )
