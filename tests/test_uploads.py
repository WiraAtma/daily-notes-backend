import pytest
from fastapi import HTTPException

from app.schemas.upload import UploadURLRequest
from app.services import storage_service


class FakeS3:
    def __init__(self):
        self.calls = []

    def generate_presigned_url(self, operation, Params, ExpiresIn):
        self.calls.append((operation, Params, ExpiresIn))
        return "https://storage.example/presigned"

    def delete_object(self, **kwargs):
        self.calls.append(("delete_object", kwargs))


def test_upload_url_is_scoped_and_uses_supported_content_type(
    client, auth_headers, monkeypatch
):
    fake_s3 = FakeS3()
    monkeypatch.setattr(storage_service, "_get_s3_client", lambda: fake_s3)
    headers, _ = auth_headers

    response = client.post(
        "/uploads/presigned-url",
        headers=headers,
        json={
            "file_name": "photo.webp",
            "content_type": "image/webp",
            "file_size": 1024,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["object_key"].startswith("users/1/notes/")
    assert body["object_key"].endswith(".webp")
    assert body["expires_in"] == 300
    assert fake_s3.calls[0][0] == "put_object"


@pytest.mark.parametrize(
    "payload",
    [
        {"file_name": "x.svg", "content_type": "image/svg+xml", "file_size": 10},
        {"file_name": "x.png", "content_type": "image/png", "file_size": 5 * 1024 * 1024 + 1},
    ],
)
def test_upload_rejects_unsupported_or_oversized_file(client, auth_headers, payload):
    headers, _ = auth_headers
    response = client.post("/uploads/presigned-url", headers=headers, json=payload)
    assert response.status_code == 422


def test_user_cannot_create_download_url_for_another_users_object(
    client, auth_headers, monkeypatch
):
    fake_s3 = FakeS3()
    monkeypatch.setattr(storage_service, "_get_s3_client", lambda: fake_s3)
    headers_a, _ = auth_headers

    response = client.post(
        "/uploads/presigned-download-url",
        headers=headers_a,
        json={"object_key": "users/2/notes/private.png"},
    )

    assert response.status_code == 404
    assert fake_s3.calls == []


def test_delete_checks_ownership_before_s3_call(monkeypatch):
    fake_s3 = FakeS3()
    monkeypatch.setattr(storage_service, "_get_s3_client", lambda: fake_s3)

    with pytest.raises(HTTPException) as error:
        storage_service.delete_user_object(1, "users/2/notes/private.png")
    assert error.value.status_code == 404
    assert fake_s3.calls == []

    storage_service.delete_user_object(1, "users/1/notes/owned.png")
    assert fake_s3.calls[0][0] == "delete_object"
