from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_user
from app.models import User
from app.services import junior_memory as memory

router = APIRouter(prefix="/junior", tags=["junior-memory"])


class MemoryIn(BaseModel):
    markdown: str = Field(default="", max_length=memory.MEMORY_SAVE_CHARS)


class MemoryAppendIn(BaseModel):
    text: str = Field(default="", max_length=memory.MEMORY_SAVE_CHARS)


@router.get("/memory")
def get_memory(db: Session = Depends(get_db), user: User = Depends(require_user)) -> dict:
    row = memory.get_row(db, user.id)
    return {
        "markdown": (row.markdown if row else "") or "",
        "updated_at": row.updated_at.isoformat() if row and row.updated_at else None,
    }


@router.post("/memory")
def post_memory(
    payload: MemoryAppendIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> dict:
    """Append to the standing note. The original text stays. Replay uses this POST, not PUT."""
    row = memory.append_markdown(db, user, payload.text)
    db.commit()
    return {
        "markdown": row.markdown or "",
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


@router.put("/memory")
def put_memory(
    payload: MemoryIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> dict:
    row = memory.save_markdown(db, user, payload.markdown)
    db.commit()
    return {
        "markdown": row.markdown or "",
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
