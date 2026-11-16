import base64
import logging

from fastapi import HTTPException, status
from google import genai
from google.genai.errors import APIError

from app.core.config import settings
from app.schemas.ai import AIGenerateRequest, AIGenerateResponse, AIModel
from app.services.storage_service import get_user_image_data

logger = logging.getLogger(__name__)

FALLBACK_ORDER: tuple[AIModel, ...] = (
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash-lite",
    "gemini-3.8-flash",
    "gemini-4-hydrogen",
)

RETRYABLE_STATUS_CODES = {429, 500, 503}


def _is_retryable(exc: APIError) -> bool:
    code = getattr(exc, "code", None)
    status_text = str(getattr(exc, "status", "") or "").upper()
    return code in RETRYABLE_STATUS_CODES or status_text in {
        "RESOURCE_EXHAUSTED",
        "UNAVAILABLE",
        "INTERNAL",
    }


def _model_chain(requested: AIModel) -> list[AIModel]:
    return [requested, *(m for m in FALLBACK_ORDER if m != requested)]


def generate_text(user_id: int, request: AIGenerateRequest) -> AIGenerateResponse:
    api_key = settings.gemini_api_key
    if api_key is None or not api_key.get_secret_value().strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gemini API is not configured",
        )

    interaction_input: list[dict[str, str]] = [
        {"type": "text", "text": request.prompt}
    ]
    for object_key in request.image_object_keys:
        image_bytes, mime_type = get_user_image_data(user_id, object_key)
        interaction_input.append(
            {
                "type": "image",
                "data": base64.b64encode(image_bytes).decode("utf-8"),
                "mime_type": mime_type,
            }
        )

    client = genai.Client(api_key=api_key.get_secret_value())
    last_error: APIError | None = None

    for model in _model_chain(request.model):
        try:
            interaction = client.interactions.create(
                model=model,
                input=interaction_input,
            )
        except APIError as exc:
            last_error = exc
            if _is_retryable(exc):
                logger.warning("Model %s limited/unavailable, trying next", model)
                continue
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Gemini provider request failed",
            ) from exc

        output_text = interaction.output_text
        if not isinstance(output_text, str) or not output_text.strip():
            logger.warning("Model %s returned empty output, trying next", model)
            continue

        return AIGenerateResponse(model=model, output_text=output_text)

    if last_error is not None and _is_retryable(last_error):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="All AI models are currently rate limited. Please try again later.",
        ) from last_error

    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="Gemini provider returned no text output",
    ) from last_error