"""Spike v4: test streaming events from claude-agent-sdk for SSE mapping."""
from __future__ import annotations

import asyncio
import json
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    StreamEvent,
    SystemMessage,
    UserMessage,
    create_sdk_mcp_server,
    query,
    tool,
)


def _mcp_result(data: Any) -> dict[str, Any]:
    text = json.dumps(data) if not isinstance(data, str) else data
    return {"content": [{"type": "text", "text": text}]}


@tool(
    "lookup_duty_cycle",
    "Look up exact duty cycle for a welding process at a given voltage.",
    {
        "type": "object",
        "properties": {
            "process": {"type": "string", "enum": ["mig", "flux_cored", "tig", "stick"]},
            "voltage": {"type": "string", "enum": ["120v", "240v"]},
        },
        "required": ["process", "voltage"],
    },
)
async def lookup_duty_cycle(args: dict[str, Any]) -> dict[str, Any]:
    return _mcp_result({
        "rated": {"duty_cycle_percent": 25, "amperage": 200,
                  "weld_minutes": 2.5, "rest_minutes": 7.5},
        "continuous": {"duty_cycle_percent": 100, "amperage": 115},
    })


async def main() -> None:
    mcp_server = create_sdk_mcp_server(
        name="welding",
        tools=[lookup_duty_cycle],
    )

    options = ClaudeAgentOptions(
        model="claude-sonnet-4-6",
        system_prompt="You are a welding expert. Use tools for facts.",
        mcp_servers={"welding": mcp_server},
        max_turns=5,
        permission_mode="bypassPermissions",
        include_partial_messages=True,  # Get streaming events
    )

    print("Testing streaming events...")
    print("=" * 60)

    async for event in query(
        prompt="What is the duty cycle for MIG at 240V? Be brief.",
        options=options,
    ):
        event_type = type(event).__name__

        if isinstance(event, StreamEvent):
            evt = event.event
            evt_type = evt.get("type", "?")
            if evt_type == "content_block_delta":
                delta = evt.get("delta", {})
                delta_type = delta.get("type", "")
                if delta_type == "text_delta":
                    print(delta.get("text", ""), end="", flush=True)
                elif delta_type == "input_json_delta":
                    pass  # Tool input being built
            elif evt_type == "content_block_start":
                cb = evt.get("content_block", {})
                cb_type = cb.get("type", "")
                if cb_type == "tool_use":
                    print(f"\n[TOOL_START] {cb.get('name', '?')}")
                elif cb_type == "thinking":
                    print(f"\n[THINKING_START]")
            elif evt_type == "content_block_stop":
                pass
            elif evt_type == "message_start":
                pass
            elif evt_type == "message_delta":
                stop = evt.get("delta", {}).get("stop_reason")
                if stop:
                    print(f"\n[STOP: {stop}]")
            else:
                print(f"\n[STREAM: {evt_type}] {json.dumps(evt)[:120]}")

        elif isinstance(event, AssistantMessage):
            print(f"\n[ASSISTANT_MSG] blocks={len(event.content)}")

        elif isinstance(event, ResultMessage):
            print(f"\n[DONE] turns={event.num_turns}, cost=${event.total_cost_usd}")

        elif isinstance(event, (UserMessage, SystemMessage)):
            pass  # Skip system/user echoes


if __name__ == "__main__":
    asyncio.run(main())
