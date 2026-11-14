import base64
import io

import pytest
from fastapi import HTTPException
from pydantic import SecretStr

from app.schemas.ai import DEFAULT_AI_MODEL
from app.services import ai_service, storage_service


class FakeInteractions:
    def __init__(self, output_text="Generated response"):
        self.calls = []
        self.output_text = output_text

    def create(self, model, input):
        self.calls.append({"model": model, "input": input})
        return type("Interaction", (), {"output_text": self.output_text})()


class FakeGeminiClient:
    def __init__(self, api_key):
        self.api_key = api_key
        self.interactions = FakeInteractions()


class FakeS3:
    def __init__(self, response=None):
        self.response = response
        self.calls = []

    def get_object(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


def test_model_list_returns_dropdown_values_and_default(client, auth_headers):
    headers, _ = auth_headers

    response = client.get("/ai/models", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["default_model"] == DEFAULT_AI_MODEL
    assert body["models"][0] == {
        "value": "gemini-3.1-flash-lite",
        "label": "Gemini 3.1 Flash Lite",
    }
    assert len(body["models"]) == 4


def test_text_generation_uses_default_model_and_text_only_input(
    client, auth_headers, monkeypatch
):
    headers, _ = auth_headers
    monkeypatch.setattr(
        ai_service.settings, "gemini_api_key", SecretStr("test-api-key")
    )
    fake_client = FakeGeminiClient("test-api-key")
    monkeypatch.setattr(ai_service.genai, "Client", lambda api_key: fake_client)
    monkeypatch.setattr(
        ai_service,
        "get_user_image_data",
        lambda user_id, key: (_ for _ in ()).throw(AssertionError("unexpected image")),
    )

    response = client.post(
        "/ai/generate",
        headers=headers,
        json={"prompt": "Generate a short note"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "model": DEFAULT_AI_MODEL,
        "output_text": "Generated response",
    }
    assert fake_client.interactions.calls == [
        {
            "model": DEFAULT_AI_MODEL,
            "input": [{"type": "text", "text": "Generate a short note"}],
        }
    ]


def test_multimodal_generation_preserves_multiple_owned_images(
    client, auth_headers, monkeypatch
):
    headers, _ = auth_headers
    monkeypatch.setattr(
        ai_service.settings, "gemini_api_key", SecretStr("test-api-key")
    )
    fake_client = FakeGeminiClient("test-api-key")
    monkeypatch.setattr(ai_service.genai, "Client", lambda api_key: fake_client)
    images = {
        "users/1/notes/first.png": (b"first-image", "image/png"),
        "users/1/notes/second.jpg": (b"second-image", "image/jpeg"),
    }
    monkeypatch.setattr(
        ai_service,
        "get_user_image_data",
        lambda user_id, key: images[key],
    )

    response = client.post(
        "/ai/generate",
        headers=headers,
        json={
            "prompt": "Describe these images",
            "model": "gemini-4-hydrogen",
            "image_object_keys": list(images),
        },
    )

    assert response.status_code == 200
    sent_input = fake_client.interactions.calls[0]["input"]
    assert sent_input == [
        {"type": "text", "text": "Describe these images"},
        {
            "type": "image",
            "data": base64.b64encode(b"first-image").decode("utf-8"),
            "mime_type": "image/png",
        },
        {
            "type": "image",
            "data": base64.b64encode(b"second-image").decode("utf-8"),
            "mime_type": "image/jpeg",
        },
    ]
    assert fake_client.interactions.calls[0]["model"] == "gemini-4-hydrogen"


def test_generation_rejects_unknown_model(client, auth_headers):
    headers, _ = auth_headers

    response = client.post(
        "/ai/generate",
        headers=headers,
        json={"prompt": "Generate text", "model": "unknown-model"},
    )

    assert response.status_code == 422


def test_generation_requires_gemini_api_key(client, auth_headers, monkeypatch):
    headers, _ = auth_headers
    monkeypatch.setattr(ai_service.settings, "gemini_api_key", None)

    response = client.post(
        "/ai/generate",
        headers=headers,
        json={"prompt": "Generate text"},
    )

    assert response.status_code == 503


def test_storage_image_read_checks_owner_size_and_actual_format(monkeypatch):
    image = b"\x89PNG\r\n\x1a\nimage"
    fake_s3 = FakeS3(
        {
            "ContentLength": len(image),
            "Body": io.BytesIO(image),
            "ContentType": "image/png",
        }
    )
    monkeypatch.setattr(storage_service, "_get_s3_client", lambda: fake_s3)

    data, mime_type = storage_service.get_user_image_data(
        1, "users/1/notes/image.png"
    )

    assert data == image
    assert mime_type == "image/png"
    assert fake_s3.calls[0]["Key"] == "users/1/notes/image.png"

    with pytest.raises(HTTPException) as error:
        storage_service.get_user_image_data(1, "users/2/notes/private.png")
    assert error.value.status_code == 404
    assert len(fake_s3.calls) == 1


def test_storage_image_read_rejects_non_image_object(monkeypatch):
    data = b"not an image"
    fake_s3 = FakeS3(
        {
            "ContentLength": len(data),
            "Body": io.BytesIO(data),
            "ContentType": "image/png",
        }
    )
    monkeypatch.setattr(storage_service, "_get_s3_client", lambda: fake_s3)

    with pytest.raises(HTTPException) as error:
        storage_service.get_user_image_data(1, "users/1/notes/fake.png")

    assert error.value.status_code == 422
