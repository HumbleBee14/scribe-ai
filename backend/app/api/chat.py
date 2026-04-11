"""Chat API endpoint — SSE streaming from agent orchestrator."""
from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agent.orchestrator import AgentOrchestrator
from app.packs.registry import get_product_registry
from app.session.manager import session_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])

# Lazy singleton: Agent SDK orchestrator, created on first request.
_orchestrator: AgentOrchestrator | None = None


def _get_orchestrator() -> AgentOrchestrator:
    global _orchestrator  # noqa: PLW0603
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator()
    return _orchestrator


class ImageInput(BaseModel):
    """A single image uploaded by the user."""

    media_type: str = "image/jpeg"
    data: str  # base64-encoded


class ChatRequest(BaseModel):
    session_id: str | None = None
    product_id: str | None = None
    message: str
    images: list[ImageInput] | None = Field(
        default=None,
        description="Optional images as base64-encoded data",
    )


async def _event_stream(request: ChatRequest) -> AsyncIterator[str]:
    """Generate SSE events from the agent orchestrator."""
    orchestrator = _get_orchestrator()
    runtime = get_product_registry().require_product(request.product_id)

    # Get or create session
    session = session_manager.get_or_create(
        request.session_id,
        product_id=runtime.id,
        product_name=runtime.product_name,
    )

    # Update session context from user message
    session_manager.update_from_message(session, request.message)

    # Yield session info
    yield _sse_event("session_update", session.to_dict())

    # Convert typed images to dicts for orchestrator
    images_raw: list[dict[str, str]] | None = None
    if request.images:
        images_raw = [img.model_dump() for img in request.images]

    # Run agent and stream events
    import time
    req_start = time.time()
    text_chars = 0
    assistant_chunks: list[str] = []
    clarification_question: str | None = None
    async for event in orchestrator.run(
        user_message=request.message,
        session=session,
        images=images_raw,
    ):
        evt_type = event["event"]
        elapsed = f"{time.time() - req_start:.1f}s"
        if evt_type == "text_delta":
            text_chars += len(event["data"].get("content", ""))
        else:
            debug_data = {
                k: (v[:80] + "..." if isinstance(v, str) and len(v) > 80 else v)
                for k, v in event["data"].items()
            }
            extra = f" (text so far: {text_chars} chars)" if evt_type == "done" else ""
            print(f"[{elapsed}] {evt_type}: {debug_data}{extra}", flush=True)
        if evt_type == "text_delta":
            assistant_chunks.append(event["data"].get("content", ""))
        elif event["event"] == "clarification":
            clarification_question = event["data"].get("question")
        elif event["event"] == "done":
            status = event["data"].get("status", "completed")
            assistant_message = "".join(assistant_chunks).strip()
            if status == "completed" and assistant_message:
                session_manager.append_turn(session, request.message, assistant_message)
                pass  # TODO: session summary persistence
            elif status == "clarification_required" and clarification_question:
                session_manager.append_turn(
                    session, request.message, clarification_question
                )
                pass  # TODO: session summary persistence
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
