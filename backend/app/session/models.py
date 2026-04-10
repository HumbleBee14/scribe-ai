from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(slots=True)
class SessionSummaryRecord:
    session_id: str
    product_id: str
    summary: str
    message_count: int
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

