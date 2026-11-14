import base64

from fastapi import HTTPException, status
from google import genai
from google.genai.errors import APIError

from app.core.config import settings
from app.schemas.ai import AIGenerateRequest, AIGenerateResponse
from app.services.storage_service import get_user_image_data


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

    try:
        client = genai.Client(api_key=api_key.get_secret_value())
        interaction = client.interactions.create(
            model=request.model,
            input=interaction_input,
        )
    except APIError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Gemini provider request failed",
        ) from exc

    output_text = interaction.output_text
    if not isinstance(output_text, str) or not output_text.strip():
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Gemini provider returned no text output",
        )
    return AIGenerateResponse(model=request.model, output_text=output_text)
