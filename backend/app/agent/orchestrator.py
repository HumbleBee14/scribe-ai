"""Agent orchestrator using the Claude Agent SDK only."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    StreamEvent,
)

from app.agent.prompts import (
    _build_memories_section,
    _build_static_prompt,
    build_initial_search_context,
    build_system_prompt,
)
from app.agent.tools import MCP_SERVER_NAME, create_knowledge_mcp_server
from app.core.config import settings
from app.packs.models import ProductRuntime
from app.packs.registry import get_product_registry, use_product_runtime
from app.session.manager import Session

logger = logging.getLogger(__name__)
MAX_AGENT_TURNS = 10

_TOOL_LABELS: dict[str, str] = {
    "search_manual": "Searching manual",
    "get_page_text": "Reading page content",
    "get_page_image": "Loading page image",
    "clarify_question": "Asking for clarification",
    "calculate": "Calculating",
    "update_memory": "Updating memory",
    "WebSearch": "Searching the web",
    "Read": "Reading file",
}


def _strip_mcp_prefix(tool_name: str) -> str:
    """Remove MCP server prefix: mcp__product-knowledge__X -> X"""
    prefix = f"mcp__{MCP_SERVER_NAME}__"
    if tool_name.startswith(prefix):
        return tool_name[len(prefix):]
    return tool_name


def _get_tool_label(tool_name: str, tool_input: dict | None = None) -> str:
    """Build a human-readable label for a tool call.

    When tool_input is provided (at tool_end), include context like
    page numbers or search queries. Without input (at tool_start),
    return the static label.
    """
    clean = _strip_mcp_prefix(tool_name)
    base = _TOOL_LABELS.get(clean, clean)

    if not tool_input:
        return base

    if clean == "search_manual":
        query = tool_input.get("query", "")
        if query:
            short = query[:50] + ("..." if len(query) > 50 else "")
            return f"Searched for '{short}'"

    if clean == "get_page_text":
        pages = tool_input.get("pages", [])
        if pages:
            if len(pages) == 1:
                return f"Read page {pages[0]}"
            return f"Read pages {', '.join(str(p) for p in pages)}"

    if clean == "get_page_image":
        page = tool_input.get("page")
        if page:
            return f"Loaded page {page}"

    if clean == "calculate":
        expr = tool_input.get("expression", "")
        if expr:
            short = expr[:40] + ("..." if len(expr) > 40 else "")
            return f"Calculated: {short}"

    if clean == "update_memory":
        action = tool_input.get("action", "add")
        return "Saved to memory" if action == "add" else "Removed from memory"

    if clean == "WebSearch":
        query = tool_input.get("query", "")
        if query:
            short = query[:50] + ("..." if len(query) > 50 else "")
            return f"Web search: '{short}'"

    return base


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
    """Runs the Claude Agent SDK and maps events to our SSE contract.

    Creates one SDK client per product and keeps it alive across messages
    to avoid subprocess cold-start latency on every request.
    """

    def __init__(self) -> None:
        self._mcp_server = create_knowledge_mcp_server()
        self._model = settings.llm_model
        # Persistent clients keyed by product_id
        self._clients: dict[str, ClaudeSDKClient] = {}
        self._client_options: dict[str, ClaudeAgentOptions] = {}

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

    async def _get_or_create_client(self, product_id: str, options: ClaudeAgentOptions) -> ClaudeSDKClient:
        """Get an existing client or create a new one for a product.

        The client subprocess stays alive between messages. Since query()
        doesn't support updating the system prompt, we create the client
        with the STATIC prompt (instructions + product + doc map) and pass
        the dynamic search context as part of the user message.

        Only recreates when: first message, or client died from error.
        """
        existing = self._clients.get(product_id)
        if existing is not None:
            print(f"[AGENT] Reusing existing SDK client for {product_id}", flush=True)
            return existing

        client = ClaudeSDKClient(options=options)
        await client.connect()
        self._clients[product_id] = client
        print(f"[AGENT] Created new SDK client for {product_id}", flush=True)
        return client

    async def _run_with_agent_sdk(
        self,
        user_message: str,
        session: Session,
        runtime: ProductRuntime,
        images: list[dict[str, str]] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Run via the Claude Agent SDK."""
        t0 = time.time()
        def _ts(label: str) -> None:
            print(f"[TIMING] {label}: {time.time() - t0:.3f}s", flush=True)

        self.__init_stream_state()
        _ts("STEP 1 - init stream state")

        # Static prompt (cached in client): instructions + product + doc map
        static_prompt = _build_static_prompt(runtime.id)

        memories_section = _build_memories_section(runtime.id)
        
        if memories_section:
            static_prompt = f"{static_prompt}\n{memories_section}"
        _ts("STEP 2 - build static prompt + memories")

        # Dynamic search context (changes per query, prepended to user message)
        search_context = build_initial_search_context(runtime.id, user_message)
        _ts("STEP 3 - build search context (hybrid search + cross-encoder + DB)")

        if search_context:
            augmented_prompt = f"{search_context}\n\n---\nUser question: {user_message}"
        else:
            augmented_prompt = user_message

        print(f"\n[AGENT] Static prompt + memories: {len(static_prompt)} chars, search context: {len(search_context)} chars", flush=True)
        print(f"\n{'='*60}", flush=True)
        print(f"[SYSTEM PROMPT] ({len(static_prompt)} chars)", flush=True)
        print(f"{'='*60}", flush=True)
        print(static_prompt, flush=True)
        print(f"{'='*60}\n", flush=True)
        if search_context:
            print(f"{'='*60}", flush=True)
            print(f"[SEARCH CONTEXT] ({len(search_context)} chars)", flush=True)
            print(f"{'='*60}", flush=True)
            print(search_context, flush=True)
            print(f"{'='*60}\n", flush=True)

        # Build options with STATIC prompt only (for client creation/reuse)
        options = ClaudeAgentOptions(
            model=self._model,
            system_prompt=static_prompt,
            mcp_servers={MCP_SERVER_NAME: self._mcp_server},
            max_turns=MAX_AGENT_TURNS,
            permission_mode="bypassPermissions",
            include_partial_messages=True,
            thinking={"type": "adaptive"} if settings.enable_thinking else None,
            allowed_tools=[
                "Read",
                "WebSearch",
                f"mcp__{MCP_SERVER_NAME}__*",
            ],
            env={"ANTHROPIC_API_KEY": settings.anthropic_api_key} if settings.anthropic_api_key else {},
        )
        _ts("STEP 4 - build options")

        if session.sdk_session_id:
            options.resume = session.sdk_session_id

        # Use augmented prompt (search context + user question) as the message
        if images:
            final_prompt: Any = self._build_multimodal_prompt(augmented_prompt, images)
        else:
            final_prompt = augmented_prompt

        clarification_requested = False
        has_error = False
        first_token_logged = False

        try:
            with use_product_runtime(runtime):
                client = await self._get_or_create_client(runtime.id, options)
                _ts("STEP 5 - get/create SDK client")

                await client.query(
                    prompt=final_prompt,
                    session_id=session.sdk_session_id or session.id,
                )
                _ts("STEP 6 - client.query() sent")

                async for event in client.receive_response():
                        if not first_token_logged:
                            _ts("STEP 7 - FIRST EVENT received from SDK")
                            first_token_logged = True

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

        except asyncio.CancelledError:
            print("[AGENT] Request cancelled (client disconnected or timeout)", flush=True)
            return
        except Exception:
            logger.exception("Agent SDK runtime error")
            # Client may be dead, remove so next request creates a fresh one
            self._clients.pop(runtime.id, None)
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
        # Reset timing flags
        self._first_text_logged = False
        self._first_thinking_logged = False
        self._stream_start = time.time()

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

        # Log first text/thinking token timing
        if not hasattr(self, '_first_text_logged'):
            self._first_text_logged = False
            self._first_thinking_logged = False
            self._stream_start = time.time()

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
            elif cb_type == "thinking":
                results.append({
                    "event": "thinking_start",
                    "data": {},
                })

        elif evt_type == "content_block_delta":
            delta = evt.get("delta", {})
            delta_type = delta.get("type", "")
            idx = evt.get("index", -1)

            if delta_type == "text_delta":
                text = delta.get("text", "")
                if text:
                    if not self._first_text_logged:
                        print(f"[TIMING] FIRST TEXT TOKEN: {time.time() - self._stream_start:.3f}s from stream start", flush=True)
                        self._first_text_logged = True
                    results.append({
                        "event": "text_delta",
                        "data": {"content": text},
                    })

            elif delta_type == "thinking_delta":
                thinking_text = delta.get("thinking", "")
                if thinking_text:
                    if not self._first_thinking_logged:
                        print(f"[TIMING] FIRST THINKING TOKEN: {time.time() - self._stream_start:.3f}s from stream start", flush=True)
                        self._first_thinking_logged = True
                    results.append({
                        "event": "thinking_delta",
                        "data": {"content": thinking_text},
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

        if tool_name == "clarify_question":
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
                "label": _get_tool_label(tool_name, tool_input),
                "ok": ok,
            },
        })

        return results
