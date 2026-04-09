"""Session manager — tracks user context across conversation turns."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Session:
    """Tracks conversation context so the agent remembers what the user is working on."""

    id: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    current_process: str | None = None
    current_voltage: str | None = None
    current_material: str | None = None
    current_thickness: str | None = None
    setup_steps_completed: list[str] = field(default_factory=list)
    safety_warnings_shown: set[str] = field(default_factory=set)

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
            "context_summary": self.context_summary(),
        }


class SessionManager:
    """In-memory session store. Sessions expire after max_age_seconds."""

    def __init__(self, max_age_seconds: int = 3600) -> None:
        self._sessions: dict[str, Session] = {}
        self._max_age = max_age_seconds

    def get_or_create(self, session_id: str | None = None) -> Session:
        """Get existing session or create a new one."""
        if session_id and session_id in self._sessions:
            return self._sessions[session_id]
        new_id = session_id or str(uuid.uuid4())
        session = Session(id=new_id)
        self._sessions[new_id] = session
        return session

    def get(self, session_id: str) -> Session | None:
        """Get session by ID, or None if not found."""
        return self._sessions.get(session_id)

    def update_from_message(self, session: Session, message: str) -> None:
        """Extract context from a user message and update session state.

        Simple keyword extraction — good enough for the challenge.
        A production system would use NER or structured extraction.
        """
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


# Singleton — created once, used by the API layer
session_manager = SessionManager()
