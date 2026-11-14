from fastapi import HTTPException, status
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.models.note import Note
from app.models.user import User
from app.schemas.note import NoteCreate, NoteUpdate
from app.utils.datetime import utc_now


def create_note(db: Session, user: User, payload: NoteCreate) -> Note:
    note = Note(
        user_id=user.id,
        title=payload.title,
        content=payload.content,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


def list_notes(
    db: Session,
    user_id: int,
    limit: int,
    offset: int,
    q: str | None = None,
) -> tuple[list[Note], int]:
    filters = [Note.user_id == user_id, Note.deleted_at.is_(None)]
    search_term = q.strip() if q else ""

    if search_term:
        escaped_term = _escape_like_pattern(search_term)
        contains_pattern = f"%{escaped_term}%"
        title_match = Note.title.ilike(contains_pattern, escape="\\")
        content_match = Note.content.ilike(contains_pattern, escape="\\")
        filters.append(or_(title_match, content_match))
        title_priority = case(
            (func.lower(Note.title) == search_term.lower(), 0),
            (
                Note.title.ilike(f"{escaped_term}%", escape="\\"),
                1,
            ),
            (title_match, 2),
            else_=3,
        )
        ordering = (title_priority, Note.updated_at.desc())
    else:
        ordering = (Note.updated_at.desc(),)

    items = list(
        db.scalars(
            select(Note)
            .where(*filters)
            .order_by(*ordering)
            .limit(limit)
            .offset(offset)
        ).all()
    )
    total = db.scalar(
        select(func.count()).select_from(Note).where(*filters)
    ) or 0
    return items, total


def _escape_like_pattern(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def get_note(db: Session, user_id: int, note_id: int) -> Note:
    note = db.scalar(
        select(Note).where(
            Note.id == note_id,
            Note.user_id == user_id,
            Note.deleted_at.is_(None),
        )
    )
    if note is None:
        raise _not_found()
    return note


def update_note(db: Session, user_id: int, note_id: int, payload: NoteUpdate) -> Note:
    note = db.scalar(
        select(Note).where(
            Note.id == note_id,
            Note.user_id == user_id,
            Note.deleted_at.is_(None),
        )
    )
    if note is None:
        raise _not_found()
    note.title = payload.title
    note.content = payload.content
    note.updated_at = utc_now()
    db.commit()
    db.refresh(note)
    return note


def delete_note(db: Session, user_id: int, note_id: int) -> None:
    note = db.scalar(
        select(Note).where(
            Note.id == note_id,
            Note.user_id == user_id,
            Note.deleted_at.is_(None),
        )
    )
    if note is None:
        raise _not_found()
    note.deleted_at = utc_now()
    note.updated_at = note.deleted_at
    db.commit()


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Note not found",
    )
