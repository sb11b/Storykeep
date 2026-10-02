from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import User

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
    db.execute(
        sa_text(
            """
            INSERT INTO junior_documents (id, user_id, slug, title, text, summary, created_at, updated_at)
            VALUES (gen_random_uuid(), :user_id, 'junior-ledger', 'Junior ledger', :text, NULL, now(), now())
            ON CONFLICT DO NOTHING
            """
        ),
        {"user_id": str(user.id), "text": _LEDGER_TEXT},
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
