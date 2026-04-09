"""Chat API endpoint — SSE streaming from agent orchestrator."""
from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agent.orchestrator import AgentOrchestrator
from app.session.manager import session_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])

# Lazy singleton — created on first request to avoid import-time API calls
_orchestrator: AgentOrchestrator | None = None


def _get_orchestrator() -> AgentOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator()
    return _orchestrator


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str
    images: list[dict] | None = Field(
        default=None,
        description="Optional images as [{media_type, data (base64)}]",
    )


async def _event_stream(request: ChatRequest) -> AsyncIterator[str]:
    """Generate SSE events from the agent orchestrator."""
    orchestrator = _get_orchestrator()

    # Get or create session
    session = session_manager.get_or_create(request.session_id)

    # Update session context from user message
    session_manager.update_from_message(session, request.message)

    # Yield session info
    yield _sse_event("session_update", session.to_dict())

    # Run agent and stream events
    async for event in orchestrator.run(
        user_message=request.message,
        session=session,
        images=request.images,
    ):
        yield _sse_event(event["event"], event["data"])


def _sse_event(event_type: str, data: dict | list | str) -> str:
    """Format a Server-Sent Event."""
    payload = json.dumps(data, default=str)
    return f"event: {event_type}\ndata: {payload}\n\n"


@router.post("/stream")
async def stream_chat(request: ChatRequest) -> StreamingResponse:
    """Stream agent responses as Server-Sent Events."""
    return StreamingResponse(
        _event_stream(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/session/{session_id}")
async def get_session(session_id: str) -> dict:
    """Get session state for frontend sidebar."""
    session = session_manager.get(session_id)
    if session is None:
        return {"error": "Session not found"}
    return session.to_dict()
