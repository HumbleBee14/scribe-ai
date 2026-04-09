"""Spike: test claude-agent-sdk with custom tools.

This tests whether the Agent SDK can:
1. Accept custom tools via MCP
2. Handle our exact-data lookup pattern
3. Stream events we can translate to our SSE format
4. Work with a custom system prompt
"""
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


# Define a custom tool using the Agent SDK's @tool decorator
@tool(
    name="lookup_duty_cycle",
    description=(
        "Look up the exact duty cycle for a welding process at a given voltage. "
        "Returns rated duty cycle percentage, amperage, weld minutes, rest minutes."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "process": {
                "type": "string",
                "enum": ["mig", "flux_cored", "tig", "stick"],
            },
            "voltage": {
                "type": "string",
                "enum": ["120v", "240v"],
            },
        },
        "required": ["process", "voltage"],
    },
)
async def lookup_duty_cycle(params: dict[str, Any]) -> dict[str, Any]:
    """Return exact duty cycle data from our structured store."""
    data = {
        ("mig", "240v"): {
            "rated": {"duty_cycle_percent": 25, "amperage": 200,
                      "weld_minutes": 2.5, "rest_minutes": 7.5},
            "continuous": {"duty_cycle_percent": 100, "amperage": 115},
        },
        ("mig", "120v"): {
            "rated": {"duty_cycle_percent": 40, "amperage": 100,
                      "weld_minutes": 4, "rest_minutes": 6},
            "continuous": {"duty_cycle_percent": 100, "amperage": 75},
        },
    }
    key = (params.get("process", ""), params.get("voltage", ""))
    result = data.get(key)
    if result is None:
        return {"error": f"No duty cycle data for {key}"}
    return result


@tool(
    name="lookup_polarity",
    description="Look up polarity and cable setup for a welding process.",
    input_schema={
        "type": "object",
        "properties": {
            "process": {
                "type": "string",
                "enum": ["mig", "flux_cored", "tig", "stick", "spool_gun"],
            },
        },
        "required": ["process"],
    },
)
async def lookup_polarity(params: dict[str, Any]) -> dict[str, Any]:
    data = {
        "tig": {
            "polarity_type": "DCEN",
            "tig_torch_cable": "negative",
            "ground_clamp_cable": "positive",
            "gas": "100% Argon, 10-25 SCFH",
        },
    }
    result = data.get(params.get("process", ""))
    if result is None:
        return {"error": f"No polarity data for {params.get('process')}"}
    return result


async def main() -> None:
    # Create an MCP server with our custom tools
    mcp_server = create_sdk_mcp_server(
        name="welding-knowledge",
        tools=[lookup_duty_cycle, lookup_polarity],
    )

    options = ClaudeAgentOptions(
        model="claude-sonnet-4-6",
        system_prompt="You are a Vulcan OmniPro 220 welding expert. Use tools for factual claims.",
        mcp_servers={"welding": mcp_server},
        max_turns=5,
        permission_mode="bypassPermissions",
    )

    print("Sending query: What's the duty cycle for MIG at 240V?")
    print("=" * 60)

    async for event in query(
        prompt="What's the duty cycle for MIG welding at 200A on 240V?",
        options=options,
    ):
        if isinstance(event, AssistantMessage):
            print(f"\n[ASSISTANT] stop_reason={event.stop_reason}")
            for block in event.content:
                if hasattr(block, "text"):
                    print(f"  TEXT: {block.text[:200]}")
                elif hasattr(block, "name"):
                    print(f"  TOOL_USE: {block.name}({json.dumps(block.input)})")
                elif hasattr(block, "content"):
                    content = block.content if isinstance(block.content, str) else str(block.content)
                    print(f"  TOOL_RESULT: {content[:200]}")

        elif isinstance(event, UserMessage):
            print("\n[USER] (tool results being sent back)")

        elif isinstance(event, SystemMessage):
            print("\n[SYSTEM]")

        elif isinstance(event, ResultMessage):
            print(f"\n[RESULT] turns={event.num_turns}, cost=${event.total_cost_usd}")
            if event.result:
                print(f"  Final: {event.result[:300]}")

        elif isinstance(event, StreamEvent):
            # Granular streaming events
            evt = event.event
            evt_type = evt.get("type", "unknown")
            if evt_type == "content_block_delta":
                delta = evt.get("delta", {})
                if delta.get("type") == "text_delta":
                    print(delta.get("text", ""), end="", flush=True)

    print("\n" + "=" * 60)
    print("Spike complete!")


if __name__ == "__main__":
    asyncio.run(main())
