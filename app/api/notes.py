from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.note import NoteCreate, NoteList, NoteRead, NoteUpdate
from app.services.note_service import (
    create_note,
    delete_note,
    get_note,
    list_notes,
    update_note,
)

router = APIRouter(prefix="/notes", tags=["notes"])


@router.post("", response_model=NoteRead, status_code=status.HTTP_201_CREATED)
def create_note_endpoint(
    payload: NoteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NoteRead:
    return NoteRead.model_validate(create_note(db, current_user, payload))


@router.get("", response_model=NoteList)
def list_notes_endpoint(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NoteList:
    items, total = list_notes(db, current_user.id, limit, offset)
    return NoteList(items=items, total=total, limit=limit, offset=offset)


@router.get("/{note_id}", response_model=NoteRead)
def get_note_endpoint(
    note_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NoteRead:
    return NoteRead.model_validate(get_note(db, current_user.id, note_id))


@router.put("/{note_id}", response_model=NoteRead)
def update_note_endpoint(
    note_id: int,
    payload: NoteUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NoteRead:
    note = update_note(db, current_user.id, note_id, payload)
    return NoteRead.model_validate(note)


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note_endpoint(
    note_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    delete_note(db, current_user.id, note_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
