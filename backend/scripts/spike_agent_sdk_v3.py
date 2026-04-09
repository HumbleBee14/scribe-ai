"""Spike v3: correct MCP tool return format for claude-agent-sdk."""
from __future__ import annotations

import asyncio
import json
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    create_sdk_mcp_server,
    query,
    tool,
)


def _mcp_result(data: Any) -> dict[str, Any]:
    """Wrap tool output in MCP CallToolResult format."""
    text = json.dumps(data) if not isinstance(data, str) else data
    return {"content": [{"type": "text", "text": text}]}


def _mcp_error(message: str) -> dict[str, Any]:
    """Return an MCP error result."""
    return {"content": [{"type": "text", "text": message}], "is_error": True}


@tool(
    "lookup_duty_cycle",
    "Look up exact duty cycle for a welding process at a given voltage. Returns rated percentage, amperage, weld and rest minutes.",
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
    print(f"  [TOOL] lookup_duty_cycle({args})")
    data = {
        ("mig", "240v"): {
            "rated": {"duty_cycle_percent": 25, "amperage": 200,
                      "weld_minutes": 2.5, "rest_minutes": 7.5},
            "continuous": {"duty_cycle_percent": 100, "amperage": 115},
        },
    }
    key = (args.get("process", ""), args.get("voltage", ""))
    result = data.get(key)
    if result is None:
        return _mcp_error(f"No duty cycle data for {key}")
    return _mcp_result(result)


@tool(
    "lookup_polarity",
    "Look up polarity and cable setup for a welding process. Returns DCEP/DCEN, cable routing, gas requirements.",
    {
        "type": "object",
        "properties": {
            "process": {"type": "string", "enum": ["mig", "flux_cored", "tig", "stick"]},
        },
        "required": ["process"],
    },
)
async def lookup_polarity(args: dict[str, Any]) -> dict[str, Any]:
    print(f"  [TOOL] lookup_polarity({args})")
    data = {
        "tig": {
            "polarity_type": "DCEN",
            "tig_torch_cable": "negative",
            "ground_clamp_cable": "positive",
            "gas": "100% Argon, 10-25 SCFH",
        },
    }
    result = data.get(args.get("process", ""))
    if result is None:
        return _mcp_error(f"No polarity data for {args.get('process')}")
    return _mcp_result(result)


async def main() -> None:
    mcp_server = create_sdk_mcp_server(
        name="welding",
        tools=[lookup_duty_cycle, lookup_polarity],
    )

    options = ClaudeAgentOptions(
        model="claude-sonnet-4-6",
        system_prompt=(
            "You are a Vulcan OmniPro 220 welding expert. "
            "ALWAYS use the lookup tools for factual claims. Never guess values."
        ),
        mcp_servers={"welding": mcp_server},
        max_turns=5,
        permission_mode="bypassPermissions",
    )

    print("Query: What is the duty cycle for MIG at 240V?")
    print("=" * 60)

    final_text = ""
    async for event in query(
        prompt="What is the duty cycle for MIG welding at 200A on 240V?",
        options=options,
    ):
        if isinstance(event, AssistantMessage):
            for block in event.content:
                if hasattr(block, "text") and block.text:
                    final_text = block.text
                elif hasattr(block, "name"):
                    print(f"  [CALL] {block.name}({json.dumps(block.input)[:100]})")

        elif isinstance(event, ResultMessage):
            print(f"\n  [RESULT] turns={event.num_turns}, cost=${event.total_cost_usd}")

    print("\n" + "=" * 60)
    print("FINAL ANSWER:")
    print(final_text)


if __name__ == "__main__":
    asyncio.run(main())
