"""Session manager - minimal session for Agent SDK multi-turn resume."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


@dataclass
class Session:
    """Tracks Agent SDK session state for multi-turn resume."""

    id: str = ""
    product_id: str = ""
    product_name: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    message_history: list[dict[str, str]] = field(default_factory=list)
    sdk_session_id: str | None = None

    def context_summary(self) -> str:
        return ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "product_id": self.product_id,
        }

    def touch(self) -> None:
        self.last_seen_at = datetime.now(timezone.utc)


class SessionManager:
    """In-memory session store for Agent SDK resume."""

    def __init__(self, max_age_seconds: int = 3600) -> None:
        self._sessions: dict[str, Session] = {}
        self._max_age = max_age_seconds

    def get_or_create(
        self,
        session_id: str | None = None,
        *,
        product_id: str = "",
        product_name: str | None = None,
    ) -> Session:
        if session_id and session_id in self._sessions:
            existing = self._sessions[session_id]
            if datetime.now(timezone.utc) - existing.last_seen_at > timedelta(seconds=self._max_age):
                del self._sessions[session_id]
            else:
                existing.touch()
                return existing
        new_id = session_id or str(uuid.uuid4())
        session = Session(id=new_id, product_id=product_id, product_name=product_name)
        self._sessions[new_id] = session
        return session

    def get(self, session_id: str) -> Session | None:
        session = self._sessions.get(session_id)
        if session is None:
            return None
        if datetime.now(timezone.utc) - session.last_seen_at > timedelta(seconds=self._max_age):
            del self._sessions[session_id]
            return None
        session.touch()
        return session

    def append_turn(self, session: Session, user_message: str, assistant_message: str) -> None:
        session.touch()
        session.message_history.extend([
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": assistant_message},
        ])
        if len(session.message_history) > 12:
            session.message_history = session.message_history[-12:]


session_manager = SessionManager()
