"""Chat API endpoint -- SSE streaming from agent orchestrator."""
from __future__ import annotations

import base64
import json
import logging
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agent.orchestrator import AgentOrchestrator
from app.core import database as db
from app.core.config import PRODUCTS_DIR
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


def _save_user_image(product_id: str, media_type: str, data_b64: str) -> str:
    """Save a base64 image to disk, return the relative path."""
    ext = media_type.split("/")[-1] if "/" in media_type else "jpg"
    if ext not in ("jpeg", "jpg", "png", "gif", "webp"):
        ext = "jpg"
    filename = f"{uuid.uuid4().hex[:12]}.{ext}"
    uploads_dir = PRODUCTS_DIR / product_id / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    (uploads_dir / filename).write_bytes(base64.b64decode(data_b64))

    # Auto-cleanup: if over 100 files, purge oldest half
    files = sorted(uploads_dir.glob("*"), key=lambda f: f.stat().st_mtime)
    if len(files) > 100:
        for f in files[: len(files) // 2]:
            f.unlink(missing_ok=True)

    return f"uploads/{filename}"


class ImageInput(BaseModel):
    """A single image uploaded by the user."""

    media_type: str = "image/jpeg"
    data: str  # base64-encoded


class ChatRequest(BaseModel):
    conversation_id: str | None = None
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

    # Resolve or create conversation
    conversation_id = request.conversation_id
    if not conversation_id:
        conv = db.create_conversation(runtime.id)
        conversation_id = conv["id"]
        # Send conversation_id to frontend so it can update the URL
        yield _sse_event("conversation_created", {"conversation_id": conversation_id})

    # Save user images to disk, store paths (not base64) in DB
    image_paths: list[str] = []
    if request.images:
        for img in request.images:
            path = _save_user_image(runtime.id, img.media_type, img.data)
            image_paths.append(path)

    user_content: dict = {"text": request.message}
    if image_paths:
        user_content["images"] = image_paths
    db.add_message(conversation_id, "user", user_content)

    # Auto-set conversation title from first user message
    conv_data = db.get_conversation(conversation_id)
    if conv_data and not conv_data["title"]:
        title = request.message[:80].strip()
        if len(request.message) > 80:
            title = title.rsplit(" ", 1)[0] + "..."
        db.update_conversation_title(conversation_id, title)

    # Get or create session (for Agent SDK multi-turn resume)
    session = session_manager.get_or_create(
        request.session_id or conversation_id,
        product_id=runtime.id,
        product_name=runtime.product_name,
    )

    # Convert typed images to dicts for orchestrator
    images_raw: list[dict[str, str]] | None = None
    if request.images:
        images_raw = [img.model_dump() for img in request.images]

    # Run agent and stream events
    import time
    req_start = time.time()
    text_chars = 0
    assistant_chunks: list[str] = []
    tool_calls: list[dict] = []
    source_pages: list[dict] = []
    artifacts: list[dict] = []
    follow_ups: list[str] = []
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

        # Accumulate assistant response parts for DB persistence
        if evt_type == "text_delta":
            assistant_chunks.append(event["data"].get("content", ""))
        elif evt_type == "tool_end":
            tool_calls.append(event["data"])
        elif evt_type == "image":
            source_pages.append(event["data"])
        elif evt_type == "artifact":
            artifacts.append(event["data"])
        elif evt_type == "follow_ups":
            follow_ups = event["data"].get("suggestions", [])
        elif evt_type == "clarification":
            clarification_question = event["data"].get("question")
        elif evt_type == "done":
            # Save assistant message to DB
            assistant_text = "".join(assistant_chunks).strip()
            if assistant_text or tool_calls or artifacts:
                assistant_content: dict = {"text": assistant_text}
                if tool_calls:
                    assistant_content["toolCalls"] = tool_calls
                if source_pages:
                    assistant_content["sourcePages"] = source_pages
                if artifacts:
                    assistant_content["artifacts"] = artifacts
                if follow_ups:
                    assistant_content["followUps"] = follow_ups
                db.add_message(conversation_id, "assistant", assistant_content)

            # Update in-memory session history
            status = event["data"].get("status", "completed")
            if status == "completed" and assistant_text:
                session_manager.append_turn(session, request.message, assistant_text)
            elif status == "clarification_required" and clarification_question:
                session_manager.append_turn(session, request.message, clarification_question)

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
