from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ImageContentType = Literal["image/jpeg", "image/png", "image/webp"]


class UploadURLRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_name: str = Field(min_length=1, max_length=255)
    content_type: ImageContentType
    file_size: int = Field(gt=0, le=5 * 1024 * 1024)


class UploadURLResponse(BaseModel):
    upload_url: str
    object_key: str
    expires_in: int


class DownloadURLRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    object_key: str = Field(min_length=1, max_length=512)


class DownloadURLResponse(BaseModel):
    download_url: str
    expires_in: int
