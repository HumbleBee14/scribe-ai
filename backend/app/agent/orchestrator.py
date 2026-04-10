"""Agent orchestrator with Agent SDK support and Anthropic fallback.

The preferred path uses the Claude Agent SDK when the local Claude CLI is
available. For evaluator-friendly zero-setup environments, the orchestrator
automatically falls back to the raw Anthropic tool loop.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import AsyncIterator
from typing import Any

import anthropic
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    StreamEvent,
    query,
)

from app.agent.prompts import build_system_prompt
from app.agent.tools import execute_tool, get_active_tools
from app.agent.tools_mcp import MCP_SERVER_NAME, create_knowledge_mcp_server
from app.core.config import FILES_DIR, settings
from app.knowledge.full_context import FullContextProvider
from app.session.manager import Session

logger = logging.getLogger(__name__)
MAX_TOOL_TURNS = 10

_TOOL_LABELS: dict[str, str] = {
    "lookup_specifications": "Looking up specifications",
    "lookup_duty_cycle": "Looking up duty cycle",
    "lookup_polarity": "Checking polarity setup",
    "lookup_troubleshooting": "Checking troubleshooting guidance",
    "lookup_safety_warnings": "Reviewing safety warnings",
    "clarify_question": "Preparing clarification",
    "get_page_image": "Loading manual page",
    "diagnose_weld": "Reviewing weld symptoms",
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
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._mcp_server = create_knowledge_mcp_server()
        self._model = settings.llm_model
        self._manual_path = str(FILES_DIR / "owner-manual.pdf")
        self._tools = get_active_tools()
        self._full_context = FullContextProvider()
        self._agent_sdk_disabled = False

    async def run(
        self,
        user_message: str,
        session: Session,
        images: list[dict[str, str]] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Run the agent and yield SSE events for the frontend."""
        # Images go directly to the Anthropic client loop.
        # The Agent SDK subprocess transport does not handle large base64
        # payloads reliably and will hang without error.
        if images:
            async for event in self._run_with_anthropic_loop(user_message, session, images):
                yield event
            return

        if self._should_use_agent_sdk():
            logger.warning(
                "[agent-runtime] request started via Claude Agent SDK (session=%s)",
                session.id,
            )
            emitted_any = False
            try:
                async for event in self._run_with_agent_sdk(user_message, session, images):
                    emitted_any = True
                    yield event
                logger.warning(
                    "[agent-runtime] request completed via Claude Agent SDK (session=%s)",
                    session.id,
                )
                return
            except Exception:
                self._agent_sdk_disabled = True
                logger.exception(
                    "[agent-runtime] Claude Agent SDK failed; "
                    "switching to Anthropic client fallback"
                )
                if emitted_any:
                    yield {
                        "event": "error",
                        "data": {
                            "message": (
                                "Agent SDK failed after starting a response. "
                                "Please retry this request."
                            ),
                        },
                    }
                    return

        logger.warning(
            "[agent-runtime] request started via Anthropic client fallback (session=%s)",
            session.id,
        )
        async for event in self._run_with_anthropic_loop(user_message, session, images):
            yield event
        logger.warning(
            "[agent-runtime] request completed via Anthropic client fallback (session=%s)",
            session.id,
        )

    def _should_use_agent_sdk(self) -> bool:
        """Use Agent SDK unless explicitly disabled or already failed in-process."""
        if os.getenv("DISABLE_CLAUDE_AGENT_SDK", "").lower() in {"1", "true", "yes"}:
            return False
        if os.getenv("FORCE_CLAUDE_AGENT_SDK", "").lower() in {"1", "true", "yes"}:
            return True
        return not self._agent_sdk_disabled

    async def _run_with_agent_sdk(
        self,
        user_message: str,
        session: Session,
        images: list[dict[str, str]] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Run via Claude Agent SDK when local CLI transport is available."""
        # Reset per-request streaming state
        self.__init_stream_state()

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

    async def _run_with_anthropic_loop(
        self,
        user_message: str,
        session: Session,
        images: list[dict[str, str]] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Run the custom Anthropic tool loop used for evaluator-friendly setups."""
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
        messages: list[dict[str, Any]] = [
            *session.message_history,
            {"role": "user", "content": content},
        ]

        system_prompt = build_system_prompt(session.context_summary())

        for turn in range(MAX_TOOL_TURNS):
            try:
                response = await self._client.messages.create(
                    model=self._model,
                    max_tokens=16384,
                    system=system_prompt,
                    tools=self._tools,
                    messages=self._build_messages_with_context(messages),
                )
            except anthropic.APIError as exc:
                yield {"event": "error", "data": {"message": str(exc)}}
                return

            tool_calls: list[dict[str, Any]] = []
            for block in response.content:
                if block.type == "text":
                    yield {
                        "event": "text_delta",
                        "data": {"content": block.text},
                    }
                elif block.type == "tool_use":
                    yield {
                        "event": "tool_start",
                        "data": {
                            "tool": block.name,
                            "input": block.input,
                            "label": _get_tool_label(block.name),
                        },
                    }
                    tool_calls.append({
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    })

            if response.stop_reason == "end_turn" or not tool_calls:
                yield {
                    "event": "done",
                    "data": {
                        "status": "completed",
                        "usage": {
                            "input_tokens": response.usage.input_tokens,
                            "output_tokens": response.usage.output_tokens,
                        },
                        "turns": turn + 1,
                    },
                }
                return

            assistant_content = [
                b.model_dump() if hasattr(b, "model_dump") else {
                    "type": b.type,
                    **({"text": b.text} if b.type == "text" else {}),
                    **(
                        {"id": b.id, "name": b.name, "input": b.input}
                        if b.type == "tool_use"
                        else {}
                    ),
                }
                for b in response.content
            ]
            messages.append({"role": "assistant", "content": assistant_content})

            tool_results = await self._execute_tools_parallel(tool_calls)
            tool_result_content: list[dict[str, Any]] = []
            clarification_requested = False

            for tool_call, result in zip(tool_calls, tool_results):
                result_str = (
                    json.dumps(result) if isinstance(result, (dict, list)) else str(result)
                )
                tool_result_content.append({
                    "type": "tool_result",
                    "tool_use_id": tool_call["id"],
                    "content": result_str,
                })

                ok = not (isinstance(result, dict) and "error" in result)
                for event in self._emit_tool_specific_events(
                    tool_call["name"],
                    tool_call["input"],
                    session,
                    ok=ok,
                ):
                    if event["event"] == "clarification":
                        clarification_requested = True
                    yield event

            if clarification_requested:
                yield {
                    "event": "done",
                    "data": {
                        "status": "clarification_required",
                        "turns": turn + 1,
                    },
                }
                return

            messages.append({"role": "user", "content": tool_result_content})

        yield {
            "event": "error",
            "data": {"message": f"Agent exceeded {MAX_TOOL_TURNS} tool turns"},
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

    def _build_messages_with_context(
        self,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Inject the full manual PDF into the first user turn when enabled."""
        if not settings.full_context_mode or not self._full_context.is_available():
            return messages

        result = list(messages)
        if result and result[0]["role"] == "user":
            first_msg = dict(result[0])
            original_content = first_msg["content"]
            doc_block = self._full_context.build_document_block()
            if isinstance(original_content, list):
                first_msg["content"] = [doc_block, *original_content]
            else:
                first_msg["content"] = [doc_block, {"type": "text", "text": str(original_content)}]
            result[0] = first_msg
        return result

    async def _execute_tools_parallel(
        self,
        tool_calls: list[dict[str, Any]],
    ) -> list[Any]:
        """Execute multiple tool calls in parallel."""

        async def _run_one(tool_call: dict[str, Any]) -> Any:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                None,
                execute_tool,
                tool_call["name"],
                tool_call["input"],
            )

        return await asyncio.gather(*[_run_one(tool_call) for tool_call in tool_calls])

    def __init_stream_state(self) -> None:
        """Reset per-request streaming state for tool input accumulation."""
        # Track in-progress tool blocks by index
        # {block_index: {"name": "tool_name", "input_json": ""}}
        self._active_tool_blocks: dict[int, dict[str, str]] = {}

    def _map_stream_event(
        self,
        event: StreamEvent,
        session: Session,
    ) -> list[dict[str, Any]]:
        """Map StreamEvent to SSE events.

        Accumulates tool input JSON from delta events and emits artifact/image/etc
        events when the content block finishes.
        """
        evt = event.event
        evt_type = evt.get("type", "")
        results: list[dict[str, Any]] = []

        if evt_type == "content_block_start":
            cb = evt.get("content_block", {})
            cb_type = cb.get("type", "")
            idx = evt.get("index", -1)
            if cb_type == "tool_use":
                tool_name = cb.get("name", "")
                # Track this block so we can accumulate its input JSON
                self._active_tool_blocks[idx] = {
                    "name": tool_name,
                    "input_json": "",
                }
                # Skip internal ToolSearch calls for UI
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
            idx = evt.get("index", -1)

            if delta_type == "text_delta":
                text = delta.get("text", "")
                if text:
                    results.append({
                        "event": "text_delta",
                        "data": {"content": text},
                    })

            elif delta_type == "input_json_delta":
                # Accumulate tool input JSON chunks
                partial = delta.get("partial_json", "")
                if idx in self._active_tool_blocks:
                    self._active_tool_blocks[idx]["input_json"] += partial

        elif evt_type == "content_block_stop":
            idx = evt.get("index", -1)
            if idx in self._active_tool_blocks:
                block = self._active_tool_blocks.pop(idx)
                tool_name = _strip_mcp_prefix(block["name"])

                # Parse the accumulated JSON
                tool_input: dict[str, Any] = {}
                if block["input_json"]:
                    try:
                        tool_input = json.loads(block["input_json"])
                    except json.JSONDecodeError:
                        print(
                            f"[WARN] Failed to parse tool input for {tool_name}: "
                            f"{block['input_json'][:200]}",
                            flush=True,
                        )

                # Now emit tool-specific events (artifact, image, safety, etc)
                if tool_name != "ToolSearch" and tool_input:
                    print(
                        f"[TOOL-COMPLETE] {tool_name}: "
                        f"keys={list(tool_input.keys())}, "
                        f"code_len={len(tool_input.get('code', ''))}",
                        flush=True,
                    )
                    results.extend(
                        self._emit_tool_specific_events(
                            tool_name, tool_input, session
                        )
                    )

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

                keys = list(tool_input.keys()) if isinstance(tool_input, dict) else "?"
                print(f"[SDK-TOOL] {tool_name}: keys={keys}", flush=True)

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
        ok: bool = True,
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

        # Emit tool_end for all recognized tools
        results.append({
            "event": "tool_end",
            "data": {
                "tool": tool_name,
                "label": _get_tool_label(tool_name),
                "ok": ok,
            },
        })

        return results
