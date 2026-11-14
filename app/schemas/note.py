from datetime import datetime

import bleach
from pydantic import BaseModel, ConfigDict, Field, field_validator

ALLOWED_TAGS = {
    "a", "blockquote", "br", "caption", "code", "del", "div", "em", "h1", "h2",
    "h3", "h4", "hr", "i", "img", "input", "li", "ol", "p", "pre", "s",
    "strong", "table", "tbody", "td", "th", "thead", "tr", "u", "ul",
}
ALLOWED_ATTRIBUTES = {
    "a": ["href", "title"],
    "img": ["src", "alt", "title", "width", "height"],
    "input": lambda tag, name, value: name in {"checked", "disabled"}
    or (name == "type" and value == "checkbox"),
    "td": ["colspan", "rowspan"],
    "th": ["colspan", "rowspan"],
}


def sanitize_note_html(value: str) -> str:
    return bleach.clean(
        value,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols={"http", "https", "mailto"},
        strip=True,
    )


class NoteFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=255)
    content: str = Field(default="", max_length=200_000)

    @field_validator("content")
    @classmethod
    def sanitize_content(cls, value: str) -> str:
        return sanitize_note_html(value)


class NoteCreate(NoteFields):
    pass


class NoteUpdate(NoteFields):
    pass


class NoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    title: str
    content: str
    created_at: datetime
    updated_at: datetime


class NoteList(BaseModel):
    items: list[NoteRead]
    total: int
    limit: int
    offset: int
