"""Agent orchestrator using the Claude Agent SDK.

This replaces the custom tool loop with the official Agent SDK's query() function.
The SDK handles:
- The agentic loop (message -> tool_use -> execute -> repeat)
- Tool discovery via MCP
- Session management
- Token-level streaming

Our code maps SDK events to the frontend's SSE contract.
"""
from __future__ import annotations

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
from app.core.config import settings
from app.session.manager import Session

logger = logging.getLogger(__name__)

# Tool name mapping: Agent SDK prefixes MCP tool names with mcp__{server}__{tool}
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
}


def _strip_mcp_prefix(tool_name: str) -> str:
    """Remove MCP server prefix from tool name.

    e.g., 'mcp__welding-knowledge__lookup_duty_cycle' -> 'lookup_duty_cycle'
    """
    prefix = f"mcp__{MCP_SERVER_NAME}__"
    if tool_name.startswith(prefix):
        return tool_name[len(prefix):]
    return tool_name


def _get_tool_label(tool_name: str) -> str:
    """Get a user-friendly label for a tool call."""
    clean_name = _strip_mcp_prefix(tool_name)
    return _TOOL_LABELS.get(clean_name, clean_name)


class AgentOrchestrator:
    """Runs the Claude Agent SDK and maps events to our SSE contract.

    The SDK handles the tool loop. We focus on:
    1. Building the query options (system prompt, tools, model)
    2. Mapping SDK events to frontend SSE events
    3. Tracking session state updates from tool results
    """

    def __init__(self) -> None:
        self._mcp_server = create_knowledge_mcp_server()
        self._model = settings.llm_model

    async def run(
        self,
        user_message: str,
        session: Session,
        images: list[dict[str, str]] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Run the agent and yield SSE events for the frontend."""

        # Build prompt with optional images
        prompt = user_message
        # Note: image input via Agent SDK would need MCP or separate handling
        # For now, images are described in the text prompt

        # Build Agent SDK options
        options = ClaudeAgentOptions(
            model=self._model,
            system_prompt=build_system_prompt(session.context_summary()),
            mcp_servers={MCP_SERVER_NAME: self._mcp_server},
            max_turns=10,
            permission_mode="bypassPermissions",
            include_partial_messages=True,
        )

        try:
            async for event in query(prompt=prompt, options=options):
                async for sse_event in self._map_event(event, session):
                    yield sse_event
        except Exception:
            logger.exception("Agent SDK error")
            yield {
                "event": "error",
                "data": {"message": "Agent runtime error. Please try again."},
            }

    async def _map_event(
        self,
        event: Any,
        session: Session,
    ) -> AsyncIterator[dict[str, Any]]:
        """Map a single Agent SDK event to zero or more SSE events."""

        if isinstance(event, StreamEvent):
            for sse in self._map_stream_event(event, session):
                yield sse

        elif isinstance(event, AssistantMessage):
            # Complete assistant message (after streaming is done)
            for block in event.content:
                block_type = getattr(block, "type", None) or type(block).__name__

                if block_type == "text" and hasattr(block, "text") and block.text:
                    # Only emit if we didn't already stream this text
                    pass  # Text was already streamed via StreamEvent

                elif block_type == "tool_use" and hasattr(block, "name"):
                    tool_name = _strip_mcp_prefix(block.name)
                    # Check for special tool results
                    for sse in self._check_tool_result(
                        tool_name, block.input, session
                    ):
                        yield sse

        elif isinstance(event, ResultMessage):
            status = "completed"
            if event.is_error:
                yield {
                    "event": "error",
                    "data": {"message": event.result or "Agent error"},
                }
                return

            yield {
                "event": "done",
                "data": {
                    "status": status,
                    "usage": event.usage or {},
                    "turns": event.num_turns,
                    "cost_usd": event.total_cost_usd,
                },
            }

    def _map_stream_event(
        self,
        event: StreamEvent,
        session: Session,
    ) -> list[dict[str, Any]]:
        """Map a StreamEvent to SSE events."""
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

        elif evt_type == "message_delta":
            stop = evt.get("delta", {}).get("stop_reason")
            if stop == "tool_use":
                # Tool call about to execute (SDK handles it)
                pass

        return results

    def _check_tool_result(
        self,
        tool_name: str,
        tool_input: Any,
        session: Session,
    ) -> list[dict[str, Any]]:
        """Emit special SSE events based on which tool was called."""
        results: list[dict[str, Any]] = []

        if tool_name == "lookup_safety_warnings":
            category = tool_input.get("category") if isinstance(tool_input, dict) else None
            if category:
                session.safety_warnings_shown.add(category)
                results.append({"event": "session_update", "data": session.to_dict()})

        elif tool_name == "clarify_question":
            question = tool_input.get("question", "") if isinstance(tool_input, dict) else ""
            options = tool_input.get("options") if isinstance(tool_input, dict) else None
            results.append({
                "event": "clarification",
                "data": {"question": question, "options": options},
            })

        elif tool_name == "get_page_image":
            page = tool_input.get("page") if isinstance(tool_input, dict) else None
            if page:
                results.append({
                    "event": "image",
                    "data": {
                        "page": page,
                        "url": f"/assets/images/page_{page:02d}.png",
                    },
                })

        elif tool_name == "render_artifact":
            if isinstance(tool_input, dict):
                results.append({
                    "event": "artifact",
                    "data": {
                        "id": f"art_{hash(tool_input.get('title', '')) % 100000:05d}",
                        "type": tool_input.get("type", ""),
                        "title": tool_input.get("title", ""),
                        "code": tool_input.get("code", ""),
                        "source_pages": tool_input.get("source_pages", []),
                    },
                })

        # Emit tool_end for all tools
        results.append({
            "event": "tool_end",
            "data": {
                "tool": tool_name,
                "label": _get_tool_label(tool_name),
                "ok": True,
            },
        })

        return results
