from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import JuniorDocument, User

DEMO_EMAIL = "steve@storykeep.local"
OWNER_EMAIL = "angry.tune8751@fastmail.com"

_LEDGER_TEXT = """# Junior ledger

| Field | Value |
| --- | --- |
| last finished | 80 |
| last merged | cursor/80-junior-ledger |
| next item | (not named) |
"""


def _seed_owner_ledger(db: Session) -> None:
    from app.services.demo_lock import is_locked

    user = db.scalar(select(User).where(User.email == OWNER_EMAIL))
    if user is None or is_locked(user):
        return
    existing = db.scalar(
        select(JuniorDocument).where(
            JuniorDocument.user_id == user.id,
            JuniorDocument.slug == "junior-ledger",
        )
    )
    if existing is not None:
        return
    db.add(
        JuniorDocument(
            user_id=user.id,
            slug="junior-ledger",
            title="Junior ledger",
            text=_LEDGER_TEXT,
            summary=None,
        )
    )


def seed_demo(db: Session) -> User | None:
    """Keep any legacy demo row locked; never create or enable demo login."""
    if settings.env == "production":
        return None
    if not settings.seed_demo:
        return None
    user = db.scalar(select(User).where(User.email == DEMO_EMAIL))
    if not user:
        return None
    user.is_demo_locked = True
    db.commit()
    return user
