"""Agent orchestrator — agentic loop with tool use and SSE event output.

This is the core runtime: it sends messages to the LLM provider, handles tool
calls, and yields SSE events. It depends on the LLMProvider abstraction, not
on any vendor SDK directly.
"""
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from app.agent.prompts import build_system_prompt
from app.agent.provider import ContentBlock, LLMProvider, ProviderError
from app.agent.tools import execute_tool, get_active_tools
from app.core.config import settings
from app.knowledge.full_context import FullContextProvider
from app.session.manager import Session

logger = logging.getLogger(__name__)

MAX_TOOL_TURNS = 10

TOOL_PROGRESS_LABELS: dict[str, str] = {
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


class AgentOrchestrator:
    """Runs the agentic loop: message → tool_use → execute → repeat.

    Accepts an LLMProvider via constructor injection for testability
    and clean SDK boundaries.
    """

    def __init__(
        self,
        provider: LLMProvider,
        model: str | None = None,
        full_context: FullContextProvider | None = None,
    ) -> None:
        self._provider = provider
        self._model = model or settings.llm_model
        self._tools = get_active_tools()
        self._full_context = full_context or FullContextProvider()

    async def run(
        self,
        user_message: str,
        session: Session,
        images: list[dict[str, str]] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Run the agent and yield SSE events."""
        # Build message content
        content: list[dict[str, Any]] = []

        if images:
            for img in images:
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": img.get("media_type", "image/jpeg"),
                        "data": img["data"],
                    },
                })

        content.append({"type": "text", "text": user_message})

        # Build messages from session history + current user turn
        messages: list[dict[str, Any]] = [
            *session.message_history,
            {"role": "user", "content": content},
        ]

        # System prompt with session context
        system_content: list[dict[str, Any]] = [
            {"type": "text", "text": build_system_prompt(session.context_summary())},
        ]

        # Agentic loop
        for turn in range(MAX_TOOL_TURNS):
            try:
                response = await self._provider.create_message(
                    model=self._model,
                    max_tokens=8096,
                    system=system_content,
                    tools=self._tools,
                    messages=self._inject_full_context(messages),
                )
            except ProviderError as e:
                logger.exception("LLM provider error on turn %d", turn)
                yield {"event": "error", "data": {"message": str(e)}}
                return

            # Process response content blocks
            tool_calls: list[dict[str, Any]] = []
            for block in response.content:
                if block.type == "text":
                    yield {"event": "text_delta", "data": {"content": block.text}}
                elif block.type == "tool_use":
                    yield {
                        "event": "tool_start",
                        "data": {
                            "tool": block.name,
                            "input": block.input,
                            "label": TOOL_PROGRESS_LABELS.get(block.name, block.name),
                        },
                    }
                    tool_calls.append({
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    })

            # If no tool calls, we're done
            if response.stop_reason == "end_turn" or not tool_calls:
                yield {
                    "event": "done",
                    "data": {
                        "status": "completed",
                        "usage": {
                            "input_tokens": response.input_tokens,
                            "output_tokens": response.output_tokens,
                        },
                        "turns": turn + 1,
                    },
                }
                return

            # Append assistant message to conversation
            assistant_content = _blocks_to_dicts(response.content)
            messages.append({"role": "assistant", "content": assistant_content})

            # Execute tools in parallel
            tool_results = await self._execute_tools_parallel(tool_calls)

            # Emit tool results and build tool_result message
            tool_result_content: list[dict[str, Any]] = []
            clarification_requested = False

            for tc, result in zip(tool_calls, tool_results):
                result_str = json.dumps(result) if isinstance(result, (dict, list)) else str(result)
                tool_result_content.append({
                    "type": "tool_result",
                    "tool_use_id": tc["id"],
                    "content": result_str,
                })

                has_error = isinstance(result, dict) and "error" in result
                yield {
                    "event": "tool_end",
                    "data": {
                        "tool": tc["name"],
                        "label": TOOL_PROGRESS_LABELS.get(tc["name"], tc["name"]),
                        "ok": not has_error,
                    },
                }

                # Emit special events for certain tools
                for extra in _emit_tool_specific_events(tc, result, session):
                    yield extra

                if tc["name"] == "clarify_question":
                    clarification_requested = True

            # If clarification was requested, stop and wait for user input
            if clarification_requested:
                yield {
                    "event": "done",
                    "data": {"status": "clarification_required", "turns": turn + 1},
                }
                return

            messages.append({"role": "user", "content": tool_result_content})

        # Exhausted max turns
        yield {
            "event": "error",
            "data": {"message": f"Agent exceeded {MAX_TOOL_TURNS} tool turns"},
        }

    def _inject_full_context(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Prepend the full manual PDF to the first user message if available."""
        if not settings.full_context_mode or not self._full_context.is_available():
            return messages

        result = list(messages)
        if result and result[0]["role"] == "user":
            first_msg = dict(result[0])
            original = first_msg["content"]
            doc_block = self._full_context.build_document_block()
            if isinstance(original, list):
                first_msg["content"] = [doc_block, *original]
            else:
                first_msg["content"] = [doc_block, {"type": "text", "text": str(original)}]
            result[0] = first_msg
        return result

    async def _execute_tools_parallel(
        self, tool_calls: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Execute multiple tool calls in parallel."""

        async def _run_one(tc: dict[str, Any]) -> dict[str, Any]:
            loop = asyncio.get_running_loop()
            try:
                return await loop.run_in_executor(
                    None, execute_tool, tc["name"], tc["input"]
                )
            except Exception:
                logger.exception("Tool execution failed: %s", tc["name"])
                return {"error": f"Tool {tc['name']} failed unexpectedly"}

        return list(await asyncio.gather(*[_run_one(tc) for tc in tool_calls]))


def _blocks_to_dicts(blocks: list[ContentBlock]) -> list[dict[str, Any]]:
    """Convert ContentBlock list to dicts for Anthropic message format."""
    result: list[dict[str, Any]] = []
    for b in blocks:
        if b.type == "text":
            result.append({"type": "text", "text": b.text})
        elif b.type == "tool_use":
            result.append({
                "type": "tool_use",
                "id": b.id,
                "name": b.name,
                "input": b.input,
            })
    return result


def _emit_tool_specific_events(
    tc: dict[str, Any],
    result: Any,
    session: Session,
) -> list[dict[str, Any]]:
    """Emit specialized SSE events for specific tool types."""
    events: list[dict[str, Any]] = []

    if not isinstance(result, dict):
        return events

    if tc["name"] == "render_artifact":
        events.append({"event": "artifact", "data": result})

    elif tc["name"] == "get_page_image":
        events.append({
            "event": "image",
            "data": {"page": result.get("page"), "url": result.get("image_url")},
        })

    elif tc["name"] == "clarify_question":
        events.append({
            "event": "clarification",
            "data": {
                "question": result.get("question", ""),
                "options": result.get("options"),
            },
        })

    elif tc["name"] == "lookup_safety_warnings":
        category = tc["input"].get("category")
        if category:
            session.safety_warnings_shown.add(category)
        events.append({
            "event": "safety_warning",
            "data": {
                "level": result.get("level", "warning"),
                "content": "; ".join(result.get("items", [])),
            },
        })
        events.append({"event": "session_update", "data": session.to_dict()})

    return events
