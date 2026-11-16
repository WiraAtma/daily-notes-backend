from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AIModel = Literal[
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash-lite",
    "gemini-4-hydrogen",
    "gemini-3.8-flash",
]
DEFAULT_AI_MODEL: AIModel = "gemini-3.1-flash-lite"
MAX_AI_IMAGES = 10


class AIModelOption(BaseModel):
    value: AIModel
    label: str


class AIModelsResponse(BaseModel):
    default_model: AIModel
    models: list[AIModelOption]


class AIGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=1, max_length=20_000)
    model: AIModel = DEFAULT_AI_MODEL
    image_object_keys: list[str] = Field(default_factory=list, max_length=MAX_AI_IMAGES)


class AIGenerateResponse(BaseModel):
    model: AIModel
    output_text: str