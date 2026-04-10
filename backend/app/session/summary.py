from __future__ import annotations

import json

from app.packs.models import ProductRuntime
from app.session.manager import Session
from app.session.models import SessionSummaryRecord


def build_session_summary(session: Session) -> str:
    return session.context_summary()


def persist_session_summary(runtime: ProductRuntime, session: Session) -> SessionSummaryRecord:
    runtime.conversations_dir.mkdir(parents=True, exist_ok=True)
    record = SessionSummaryRecord(
        session_id=session.id,
        product_id=runtime.id,
        summary=build_session_summary(session),
        message_count=len(session.message_history),
    )
    output_path = runtime.conversations_dir / f"{session.id}.summary.json"
    output_path.write_text(
        json.dumps(
            {
                "session_id": record.session_id,
                "product_id": record.product_id,
                "summary": record.summary,
                "message_count": record.message_count,
                "updated_at": record.updated_at,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return record

