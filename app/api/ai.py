from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user
from app.models.user import User
from app.schemas.ai import (
    AIModelOption,
    AIModelsResponse,
    AIGenerateRequest,
    AIGenerateResponse,
    DEFAULT_AI_MODEL,
)
from app.services.ai_service import generate_text

router = APIRouter(prefix="/ai", tags=["ai"])

AI_MODELS = AIModelsResponse(
    default_model=DEFAULT_AI_MODEL,
    models=[
        AIModelOption(value="gemini-3.1-flash-lite", label="Gemini 3.1 Flash Lite"),
        AIModelOption(value="gemini-3.5-flash-lite", label="Gemini 3.5 Flash Lite"),
        AIModelOption(value="gemini-4-hydrogen", label="Gemini 4 Hydrogen"),
        AIModelOption(value="gemini-3.8-flash", label="Gemini 3.8 Flash"),
    ],
)


@router.get("/models", response_model=AIModelsResponse)
def list_ai_models(
    current_user: User = Depends(get_current_user),
) -> AIModelsResponse:
    return AI_MODELS


@router.post("/generate", response_model=AIGenerateResponse)
def generate_ai_text(
    payload: AIGenerateRequest,
    current_user: User = Depends(get_current_user),
) -> AIGenerateResponse:
    return generate_text(current_user.id, payload)