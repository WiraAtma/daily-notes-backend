from fastapi import HTTPException, status
from sqlalchemy import func, select
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


def list_notes(db: Session, user_id: int, limit: int, offset: int) -> tuple[list[Note], int]:
    scope = (Note.user_id == user_id, Note.deleted_at.is_(None))
    items = list(
        db.scalars(
            select(Note)
            .where(*scope)
            .order_by(Note.updated_at.desc())
            .limit(limit)
            .offset(offset)
        ).all()
    )
    total = db.scalar(select(func.count()).select_from(Note).where(*scope)) or 0
    return items, total


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
