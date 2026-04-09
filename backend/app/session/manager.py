"""Session manager — tracks user context across conversation turns."""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


@dataclass
class Session:
    """Tracks conversation context so the agent remembers what the user is working on."""

    id: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    current_process: str | None = None
    current_voltage: str | None = None
    current_material: str | None = None
    current_thickness: str | None = None
    setup_steps_completed: list[str] = field(default_factory=list)
    safety_warnings_shown: set[str] = field(default_factory=set)
    message_history: list[dict[str, str]] = field(default_factory=list)
    sdk_session_id: str | None = None  # Claude Agent SDK session ID for resume

    def context_summary(self) -> str:
        """Build a natural-language summary for system prompt injection."""
        parts: list[str] = []
        if self.current_process:
            parts.append(f"The user is currently working with {self.current_process} welding.")
        if self.current_voltage:
            parts.append(f"Input voltage: {self.current_voltage}.")
        if self.current_material:
            parts.append(f"Material: {self.current_material}.")
        if self.current_thickness:
            parts.append(f"Thickness: {self.current_thickness}.")
        if self.setup_steps_completed:
            done = ", ".join(self.setup_steps_completed)
            parts.append(f"Setup steps completed: {done}.")
        if self.safety_warnings_shown:
            warnings = ", ".join(sorted(self.safety_warnings_shown))
            parts.append(f"Safety topics already shown: {warnings}.")
        if not parts:
            return "No process or setup context established yet."
        return " ".join(parts)

    def to_dict(self) -> dict:
        """Serialize for API responses."""
        return {
            "id": self.id,
            "current_process": self.current_process,
            "current_voltage": self.current_voltage,
            "current_material": self.current_material,
            "current_thickness": self.current_thickness,
            "setup_steps_completed": self.setup_steps_completed,
            "safety_warnings_shown": sorted(self.safety_warnings_shown),
            "context_summary": self.context_summary(),
        }

    def touch(self) -> None:
        self.last_seen_at = datetime.now(timezone.utc)


class SessionManager:
    """In-memory session store. Sessions expire after max_age_seconds."""

    def __init__(self, max_age_seconds: int = 3600, max_history_messages: int = 12) -> None:
        self._sessions: dict[str, Session] = {}
        self._max_age = max_age_seconds
        self._max_history_messages = max_history_messages

    def _is_expired(self, session: Session) -> bool:
        return datetime.now(timezone.utc) - session.last_seen_at > timedelta(seconds=self._max_age)

    def _trim_history(self, session: Session) -> None:
        if len(session.message_history) > self._max_history_messages:
            session.message_history = session.message_history[-self._max_history_messages :]

    def get_or_create(self, session_id: str | None = None) -> Session:
        """Get existing session or create a new one."""
        if session_id and session_id in self._sessions:
            existing = self._sessions[session_id]
            if self._is_expired(existing):
                del self._sessions[session_id]
            else:
                existing.touch()
                return existing
        new_id = session_id or str(uuid.uuid4())
        session = Session(id=new_id)
        self._sessions[new_id] = session
        return session

    def get(self, session_id: str) -> Session | None:
        """Get session by ID, or None if not found."""
        session = self._sessions.get(session_id)
        if session is None:
            return None
        if self._is_expired(session):
            del self._sessions[session_id]
            return None
        session.touch()
        return session

    def update_from_message(self, session: Session, message: str) -> None:
        """Extract context from a user message and update session state.

        Simple keyword extraction — good enough for the challenge.
        A production system would use NER or structured extraction.
        """
        session.touch()
        msg = message.lower()

        # Process detection
        process_keywords = {
            "mig": "mig",
            "flux-cored": "flux_cored",
            "flux cored": "flux_cored",
            "fcaw": "flux_cored",
            "tig": "tig",
            "gtaw": "tig",
            "stick": "stick",
            "smaw": "stick",
        }
        for keyword, process in process_keywords.items():
            if keyword in msg:
                session.current_process = process
                break

        # Voltage detection
        if "240" in msg:
            session.current_voltage = "240v"
        elif "120" in msg:
            session.current_voltage = "120v"

        # Material detection
        material_keywords = {
            "mild steel": "mild_steel",
            "stainless": "stainless_steel",
            "aluminum": "aluminum",
            "chrome moly": "chrome_moly",
        }
        for keyword, material in material_keywords.items():
            if keyword in msg:
                session.current_material = material
                break

        thickness_match = re.search(
            r"\b(\d+\s*ga|\d+/\d+\s*(?:inch|in)?|\d+(?:\.\d+)?\s*(?:mm|inch|in))\b",
            msg,
        )
        if thickness_match:
            session.current_thickness = thickness_match.group(1).replace(" ", "")

    def append_turn(self, session: Session, user_message: str, assistant_message: str) -> None:
        """Persist a bounded chat history for follow-up questions."""
        session.touch()
        session.message_history.extend(
            [
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": assistant_message},
            ]
        )
        self._trim_history(session)

    def get_message_history(self, session: Session) -> list[dict[str, str]]:
        session.touch()
        return list(session.message_history)

    def record_safety_warning(self, session: Session, category: str) -> None:
        session.touch()
        session.safety_warnings_shown.add(category)


# Singleton — created once, used by the API layer
session_manager = SessionManager()
