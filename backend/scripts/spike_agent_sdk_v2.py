"""Spike v2: detailed event inspection for claude-agent-sdk."""
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


@tool(
    name="lookup_duty_cycle",
    description="Look up exact duty cycle for a welding process at a given voltage.",
    input_schema={
        "type": "object",
        "properties": {
            "process": {"type": "string", "enum": ["mig", "flux_cored", "tig", "stick"]},
            "voltage": {"type": "string", "enum": ["120v", "240v"]},
        },
        "required": ["process", "voltage"],
    },
)
async def lookup_duty_cycle(params: dict[str, Any]) -> dict[str, Any]:
    print(f"  [TOOL CALLED] lookup_duty_cycle({params})")
    return {
        "rated": {
            "duty_cycle_percent": 25,
            "amperage": 200,
            "weld_minutes": 2.5,
            "rest_minutes": 7.5,
        },
        "continuous": {"duty_cycle_percent": 100, "amperage": 115},
    }


async def main() -> None:
    mcp_server = create_sdk_mcp_server(
        name="welding-knowledge",
        tools=[lookup_duty_cycle],
    )

    options = ClaudeAgentOptions(
        model="claude-sonnet-4-6",
        system_prompt="You are a welding expert. Always use the lookup_duty_cycle tool.",
        mcp_servers={"welding": mcp_server},
        max_turns=5,
        permission_mode="bypassPermissions",
    )

    print("Query: What is the duty cycle for MIG at 240V?")
    print("=" * 60)

    all_events = []
    async for event in query(
        prompt="What is the duty cycle for MIG at 240V?",
        options=options,
    ):
        all_events.append(event)
        event_type = type(event).__name__
        print(f"\n--- {event_type} ---")

        if isinstance(event, AssistantMessage):
            print(f"  stop_reason: {event.stop_reason}")
            print(f"  usage: {event.usage}")
            for i, block in enumerate(event.content):
                block_type = type(block).__name__
                if hasattr(block, "text"):
                    print(f"  [{i}] {block_type}: {block.text[:150]}")
                elif hasattr(block, "name"):
                    print(f"  [{i}] {block_type}: {block.name}({json.dumps(block.input)[:150]})")
                elif hasattr(block, "content"):
                    c = block.content if isinstance(block.content, str) else str(block.content)
                    print(f"  [{i}] {block_type}: {c[:150]}")
                else:
                    print(f"  [{i}] {block_type}: {vars(block) if hasattr(block, '__dict__') else block}")

        elif isinstance(event, ResultMessage):
            print(f"  turns: {event.num_turns}")
            print(f"  cost: ${event.total_cost_usd}")
            print(f"  is_error: {event.is_error}")
            if event.result:
                print(f"  result: {event.result[:300]}")

        elif isinstance(event, StreamEvent):
            evt = event.event
            print(f"  event: {json.dumps(evt)[:200]}")

    print(f"\n\nTotal events: {len(all_events)}")
    print(f"Event types: {[type(e).__name__ for e in all_events]}")


if __name__ == "__main__":
    asyncio.run(main())
