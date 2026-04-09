"""Agent orchestrator using the Claude Agent SDK.

Uses query() + resume=session_id for multi-turn conversation continuity.
Custom tools are exposed via MCP. Built-in Read tool is enabled as a
supplemental capability for broad manual questions.

SDK events are mapped to our frontend SSE contract.
"""
from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    StreamEvent,
    query,
)

from app.agent.prompts import build_system_prompt
from app.agent.tools_mcp import MCP_SERVER_NAME, create_knowledge_mcp_server
from app.core.config import FILES_DIR, settings
from app.session.manager import Session

logger = logging.getLogger(__name__)

_TOOL_LABELS: dict[str, str] = {
    "lookup_specifications": "Looking up specifications",
    "lookup_duty_cycle": "Looking up duty cycle",
    "lookup_polarity": "Checking polarity setup",
    "lookup_troubleshooting": "Checking troubleshooting guidance",
    "lookup_safety_warnings": "Reviewing safety warnings",
    "clarify_question": "Preparing clarification",
    "get_page_image": "Loading manual page",
    "diagnose_weld": "Reviewing weld symptoms",
    "render_artifact": "Generating visual aid",
    "search_manual": "Searching manual",
    "Read": "Reading from manual",
}


def _strip_mcp_prefix(tool_name: str) -> str:
    """Remove MCP server prefix: mcp__welding-knowledge__X -> X"""
    prefix = f"mcp__{MCP_SERVER_NAME}__"
    if tool_name.startswith(prefix):
        return tool_name[len(prefix):]
    return tool_name


def _get_tool_label(tool_name: str) -> str:
    clean = _strip_mcp_prefix(tool_name)
    return _TOOL_LABELS.get(clean, clean)


class AgentOrchestrator:
    """Runs the Claude Agent SDK and maps events to our SSE contract.

    Multi-turn: captures SDK session_id from ResultMessage, stores it on
    our app Session, and passes resume=sdk_session_id on subsequent turns.

    Images: when the user uploads images, uses AsyncIterable prompt format
    to send image content blocks alongside text.

    Built-in tools: Read is enabled for broad manual questions. Custom MCP
    tools handle exact factual lookups.
    """

    def __init__(self) -> None:
        self._mcp_server = create_knowledge_mcp_server()
        self._model = settings.llm_model
        self._manual_path = str(FILES_DIR / "owner-manual.pdf")

    async def run(
        self,
        user_message: str,
        session: Session,
        images: list[dict[str, str]] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Run the agent and yield SSE events for the frontend."""

        # Build prompt: either string (no images) or AsyncIterable (with images)
        if images:
            prompt: Any = self._build_multimodal_prompt(user_message, images)
        else:
            prompt = user_message

        # Build options
        options = ClaudeAgentOptions(
            model=self._model,
            system_prompt=build_system_prompt(
                session.context_summary(),
                manual_path=self._manual_path,
            ),
            mcp_servers={MCP_SERVER_NAME: self._mcp_server},
            max_turns=10,
            permission_mode="bypassPermissions",
            include_partial_messages=True,
            # Built-in tools: Read for broad manual questions
            allowed_tools=[
                "Read",
                f"mcp__{MCP_SERVER_NAME}__*",  # all custom MCP tools
            ],
        )

        # Multi-turn: resume previous SDK session if available
        if session.sdk_session_id:
            options.resume = session.sdk_session_id

        # Track state for SSE event mapping
        clarification_requested = False
        has_error = False

        try:
            async for event in query(prompt=prompt, options=options):
                # Map each SDK event to our SSE events
                if isinstance(event, StreamEvent):
                    for sse in self._map_stream_event(event, session):
                        if sse["event"] == "clarification":
                            clarification_requested = True
                        yield sse

                elif isinstance(event, AssistantMessage):
                    for sse in self._map_assistant_message(event, session):
                        if sse["event"] == "clarification":
                            clarification_requested = True
                        yield sse

                elif isinstance(event, ResultMessage):
                    # Capture SDK session ID for multi-turn resume
                    if event.session_id:
                        session.sdk_session_id = event.session_id

                    if event.is_error:
                        has_error = True
                        yield {
                            "event": "error",
                            "data": {
                                "message": event.result or "Agent error",
                            },
                        }
                    else:
                        status = (
                            "clarification_required"
                            if clarification_requested
                            else "completed"
                        )
                        yield {
                            "event": "done",
                            "data": {
                                "status": status,
                                "usage": event.usage or {},
                                "turns": event.num_turns,
                                "cost_usd": event.total_cost_usd,
                            },
                        }

        except Exception:
            logger.exception("Agent SDK runtime error")
            if not has_error:
                yield {
                    "event": "error",
                    "data": {
                        "message": "Agent runtime error. Please try again.",
                    },
                }

    async def _build_multimodal_prompt(
        self,
        text: str,
        images: list[dict[str, str]],
    ) -> Any:
        """Build an AsyncIterable prompt with image content blocks."""

        async def _generate():
            content: list[dict[str, Any]] = []
            for img in images:
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": img.get("media_type", "image/jpeg"),
                        "data": img["data"],
                    },
                })
            content.append({"type": "text", "text": text})
            yield {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": content,
                },
            }

        return _generate()

    def _map_stream_event(
        self,
        event: StreamEvent,
        session: Session,
    ) -> list[dict[str, Any]]:
        """Map StreamEvent to SSE events."""
        evt = event.event
        evt_type = evt.get("type", "")
        results: list[dict[str, Any]] = []

        if evt_type == "content_block_start":
            cb = evt.get("content_block", {})
            cb_type = cb.get("type", "")
            if cb_type == "tool_use":
                tool_name = cb.get("name", "")
                # Skip internal ToolSearch calls
                if tool_name != "ToolSearch":
                    results.append({
                        "event": "tool_start",
                        "data": {
                            "tool": _strip_mcp_prefix(tool_name),
                            "input": {},
                            "label": _get_tool_label(tool_name),
                        },
                    })

        elif evt_type == "content_block_delta":
            delta = evt.get("delta", {})
            delta_type = delta.get("type", "")
            if delta_type == "text_delta":
                text = delta.get("text", "")
                if text:
                    results.append({
                        "event": "text_delta",
                        "data": {"content": text},
                    })

        return results

    def _map_assistant_message(
        self,
        msg: AssistantMessage,
        session: Session,
    ) -> list[dict[str, Any]]:
        """Map a complete AssistantMessage to SSE events."""
        results: list[dict[str, Any]] = []

        for block in msg.content:
            block_type = getattr(block, "type", None) or type(block).__name__

            if block_type == "tool_use" and hasattr(block, "name"):
                tool_name = _strip_mcp_prefix(block.name)
                tool_input = getattr(block, "input", {}) or {}

                # Skip ToolSearch (internal SDK tool)
                if block.name == "ToolSearch":
                    continue

                results.extend(
                    self._emit_tool_specific_events(tool_name, tool_input, session)
                )

            elif block_type == "tool_result" and hasattr(block, "content"):
                # Tool result came back. Check for safety warnings in results.
                content_str = ""
                if isinstance(block.content, str):
                    content_str = block.content
                elif isinstance(block.content, list):
                    for cb in block.content:
                        if hasattr(cb, "text"):
                            content_str += cb.text

                # Try to parse and detect safety warnings in results
                if content_str:
                    try:
                        data = json.loads(content_str)
                        if isinstance(data, dict) and "level" in data and "items" in data:
                            results.append({
                                "event": "safety_warning",
                                "data": {
                                    "level": data.get("level", "warning"),
                                    "content": "; ".join(data.get("items", [])),
                                },
                            })
                    except (json.JSONDecodeError, TypeError):
                        pass

        return results

    def _emit_tool_specific_events(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        session: Session,
    ) -> list[dict[str, Any]]:
        """Emit specialized SSE events based on which tool was called."""
        results: list[dict[str, Any]] = []

        if tool_name == "lookup_safety_warnings":
            category = tool_input.get("category")
            if category:
                session.safety_warnings_shown.add(category)
                results.append({
                    "event": "session_update",
                    "data": session.to_dict(),
                })

        elif tool_name == "clarify_question":
            question = tool_input.get("question", "")
            options = tool_input.get("options")
            results.append({
                "event": "clarification",
                "data": {"question": question, "options": options},
            })

        elif tool_name == "get_page_image":
            page = tool_input.get("page")
            if page:
                results.append({
                    "event": "image",
                    "data": {
                        "page": page,
                        "url": f"/assets/images/page_{page:02d}.png",
                    },
                })

        elif tool_name == "render_artifact":
            renderer = tool_input.get("type", "")
            results.append({
                "event": "artifact",
                "data": {
                    "id": f"art_{hash(tool_input.get('title', '')) % 100000:05d}",
                    "renderer": renderer,
                    "type": renderer,  # kept for backwards compat
                    "title": tool_input.get("title", ""),
                    "code": tool_input.get("code", ""),
                    "source_pages": tool_input.get("source_pages", []),
                },
            })

        # Emit tool_end for all recognized tools
        results.append({
            "event": "tool_end",
            "data": {
                "tool": tool_name,
                "label": _get_tool_label(tool_name),
                "ok": True,
            },
        })

        return results
