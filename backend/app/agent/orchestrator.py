"""Agent orchestrator — Claude SDK agentic loop with tool use and streaming.

This is the core runtime: it sends messages to Claude, handles tool calls,
and streams results back via SSE events.
"""
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import anthropic

from app.agent.prompts import build_system_prompt
from app.agent.tools import execute_tool, get_active_tools
from app.core.config import settings
from app.knowledge.full_context import FullContextProvider
from app.session.manager import Session

logger = logging.getLogger(__name__)

MAX_TOOL_TURNS = 10


class AgentOrchestrator:
    """Runs the Claude agentic loop: message → tool_use → execute → repeat."""

    def __init__(self) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._model = settings.model_name
        self._tools = get_active_tools()
        self._full_context = FullContextProvider()

    async def run(
        self,
        user_message: str,
        session: Session,
        images: list[dict] | None = None,
    ) -> AsyncIterator[dict]:
        """Run the agent and yield SSE events.

        Yields dicts like:
            {"event": "text_delta", "data": {"content": "..."}}
            {"event": "tool_start", "data": {"tool": "...", "input": {...}}}
            {"event": "artifact", "data": {...}}
            {"event": "done", "data": {"usage": {...}}}
        """
        # Build message content
        content: list[dict[str, Any]] = []

        # Add images if provided (multimodal input)
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

        # Build messages array
        messages: list[dict[str, Any]] = [{"role": "user", "content": content}]

        # System prompt with session context
        system_prompt = build_system_prompt(session.context_summary())

        # Full-context: inject manual PDF as first user message content
        system_content: list[dict[str, Any]] = [{"type": "text", "text": system_prompt}]

        # Agentic loop
        for turn in range(MAX_TOOL_TURNS):
            try:
                response = await self._client.messages.create(
                    model=self._model,
                    max_tokens=8096,
                    system=system_content,
                    tools=self._tools,
                    messages=self._build_messages_with_context(messages),
                )
            except anthropic.APIError as e:
                yield {"event": "error", "data": {"message": str(e)}}
                return

            # Process response content blocks
            tool_calls: list[dict] = []
            for block in response.content:
                if block.type == "text":
                    yield {
                        "event": "text_delta",
                        "data": {"content": block.text},
                    }
                elif block.type == "tool_use":
                    yield {
                        "event": "tool_start",
                        "data": {"tool": block.name, "input": block.input},
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
                        "usage": {
                            "input_tokens": response.usage.input_tokens,
                            "output_tokens": response.usage.output_tokens,
                        },
                        "turns": turn + 1,
                    },
                }
                return

            # Execute tools in parallel
            assistant_content = [
                b.model_dump() if hasattr(b, "model_dump") else {
                    "type": b.type,
                    **({"text": b.text} if b.type == "text" else {}),
                    **({"id": b.id, "name": b.name, "input": b.input}
                       if b.type == "tool_use" else {}),
                }
                for b in response.content
            ]
            messages.append({"role": "assistant", "content": assistant_content})

            tool_results = await self._execute_tools_parallel(tool_calls)

            # Emit tool results and check for artifacts
            tool_result_content: list[dict] = []
            for tc, result in zip(tool_calls, tool_results):
                result_str = json.dumps(result) if isinstance(result, (dict, list)) else str(result)
                tool_result_content.append({
                    "type": "tool_result",
                    "tool_use_id": tc["id"],
                    "content": result_str,
                })

                # Emit special events for certain tool results
                if tc["name"] == "render_artifact" and isinstance(result, dict):
                    yield {"event": "artifact", "data": result}
                elif tc["name"] == "get_page_image" and isinstance(result, dict):
                    yield {
                        "event": "image",
                        "data": {
                            "page": result.get("page"),
                            "url": result.get("image_url"),
                        },
                    }
                elif tc["name"] == "clarify_question" and isinstance(result, dict):
                    yield {
                        "event": "clarification",
                        "data": {
                            "question": result.get("question", ""),
                            "options": result.get("options"),
                        },
                    }
                elif tc["name"] == "lookup_safety_warnings" and isinstance(result, dict):
                    yield {
                        "event": "safety_warning",
                        "data": {
                            "level": result.get("level", "warning"),
                            "content": "; ".join(result.get("items", [])),
                        },
                    }

            messages.append({"role": "user", "content": tool_result_content})

        # Exhausted max turns
        yield {
            "event": "error",
            "data": {"message": f"Agent exceeded {MAX_TOOL_TURNS} tool turns"},
        }

    def _build_messages_with_context(
        self, messages: list[dict]
    ) -> list[dict]:
        """Inject full manual context into the first user message if available."""
        if not settings.full_context_mode or not self._full_context.is_available():
            return messages

        # Prepend the PDF document block to the first user message
        result = list(messages)
        if result and result[0]["role"] == "user":
            first_msg = dict(result[0])
            original_content = first_msg["content"]
            if isinstance(original_content, list):
                doc_block = self._full_context.build_document_block()
                first_msg["content"] = [doc_block, *original_content]
            result[0] = first_msg
        return result

    async def _execute_tools_parallel(
        self, tool_calls: list[dict]
    ) -> list[dict]:
        """Execute multiple tool calls in parallel."""

        async def _run_one(tc: dict) -> dict:
            # Run in thread pool since tool execution is sync
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, execute_tool, tc["name"], tc["input"]
            )

        return await asyncio.gather(*[_run_one(tc) for tc in tool_calls])
