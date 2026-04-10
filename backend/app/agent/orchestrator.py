"""Agent orchestrator using the Claude Agent SDK only."""
from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    StreamEvent,
)

from app.agent.prompts import build_system_prompt
from app.agent.tools_mcp import MCP_SERVER_NAME, create_knowledge_mcp_server
from app.context.assembler import ContextAssembler
from app.core.config import settings
from app.packs.models import ProductRuntime
from app.packs.registry import get_product_registry, use_product_runtime
from app.session.manager import Session

logger = logging.getLogger(__name__)
MAX_AGENT_TURNS = 10

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


def _coerce_page_number(value: Any) -> int | None:
    """Normalize page values coming from tool inputs."""
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            page = int(stripped)
        except ValueError:
            return None
        return page if page > 0 else None
    return None


class AgentOrchestrator:
    """Runs the Claude Agent SDK and maps events to our SSE contract."""

    def __init__(self) -> None:
        self._mcp_server = create_knowledge_mcp_server()
        self._model = settings.llm_model
        self._context_assembler = ContextAssembler()

    async def run(
        self,
        user_message: str,
        session: Session,
        images: list[dict[str, str]] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Run the agent and yield SSE events for the frontend."""
        runtime = get_product_registry().require_product(session.product_id)
        logger.warning(
            "[agent-runtime] request started via Claude Agent SDK (session=%s, product=%s)",
            session.id,
            runtime.id,
        )
        async for event in self._run_with_agent_sdk(user_message, session, runtime, images):
            yield event
        logger.warning(
            "[agent-runtime] request completed via Claude Agent SDK (session=%s, product=%s)",
            session.id,
            runtime.id,
        )

    async def _run_with_agent_sdk(
        self,
        user_message: str,
        session: Session,
        runtime: ProductRuntime,
        images: list[dict[str, str]] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Run via the Claude Agent SDK."""
        self.__init_stream_state()

        if images:
            prompt: Any = self._build_multimodal_prompt(user_message, images)
        else:
            prompt = user_message
        context_bundle = self._context_assembler.assemble(user_message, session, runtime)

        options = ClaudeAgentOptions(
            model=self._model,
            system_prompt=build_system_prompt(
                session.context_summary(),
                product_name=runtime.product_name,
                product_description=runtime.manifest.description,
                manual_path=str(runtime.manual_path) if runtime.manual_path else "",
                domain=runtime.domain,
                assembled_context=context_bundle.to_prompt_section(),
            ),
            mcp_servers={MCP_SERVER_NAME: self._mcp_server},
            max_turns=MAX_AGENT_TURNS,
            permission_mode="bypassPermissions",
            include_partial_messages=True,
            allowed_tools=[
                *([ "Read" ] if runtime.manual_path else []),
                *[
                    f"mcp__{MCP_SERVER_NAME}__{tool_name}"
                    for tool_name in runtime.allowed_tool_names
                ],
            ],
        )

        if session.sdk_session_id:
            options.resume = session.sdk_session_id

        clarification_requested = False
        has_error = False

        try:
            with use_product_runtime(runtime):
                async with ClaudeSDKClient(options=options) as client:
                    await client.query(
                        prompt=prompt,
                        session_id=session.sdk_session_id or session.id,
                    )
                    async for event in client.receive_response():
                        if isinstance(event, StreamEvent):
                            for sse in self._map_stream_event(event, session, runtime):
                                if sse["event"] == "clarification":
                                    clarification_requested = True
                                yield sse

                        elif isinstance(event, AssistantMessage):
                            for sse in self._map_assistant_message(event, session, runtime):
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

    def _build_multimodal_prompt(
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

    def __init_stream_state(self) -> None:
        """Reset per-request streaming state for tool input accumulation."""
        # Track in-progress tool blocks by index
        # {block_index: {"name": "tool_name", "input_json": ""}}
        self._active_tool_blocks: dict[int, dict[str, str]] = {}

    def _map_stream_event(
        self,
        event: StreamEvent,
        session: Session,
        runtime: ProductRuntime,
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
                            tool_name, tool_input, session, runtime
                        )
                    )

        return results

    def _map_assistant_message(
        self,
        msg: AssistantMessage,
        session: Session,
        runtime: ProductRuntime,
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
                    self._emit_tool_specific_events(tool_name, tool_input, session, runtime)
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
        runtime: ProductRuntime,
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
            page = _coerce_page_number(tool_input.get("page"))
            if page:
                results.append({
                    "event": "image",
                    "data": {
                        "page": page,
                        "url": runtime.page_image_url(
                            page,
                            source_id=tool_input.get("source_id"),
                        ),
                        "product_id": runtime.id,
                        "source_id": tool_input.get("source_id") or runtime.primary_source_id,
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
