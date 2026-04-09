"""Live test: verify the Agent SDK orchestrator works end-to-end.

Requires ANTHROPIC_API_KEY in .env.
"""
from __future__ import annotations

import asyncio

from app.agent.orchestrator import AgentOrchestrator
from app.session.manager import Session


async def main() -> None:
    orchestrator = AgentOrchestrator()
    session = Session(id="test-live")

    queries = [
        "What is the duty cycle for MIG welding at 200A on 240V?",
        "What polarity do I need for TIG welding?",
    ]

    for q in queries:
        print(f"\n{'='*60}")
        print(f"Q: {q}")
        print(f"{'='*60}")

        text_chunks: list[str] = []
        tools_called: list[str] = []

        async for event in orchestrator.run(q, session):
            evt_type = event["event"]

            if evt_type == "text_delta":
                chunk = event["data"]["content"]
                text_chunks.append(chunk)
                print(chunk, end="", flush=True)

            elif evt_type == "tool_start":
                tool = event["data"]["tool"]
                label = event["data"]["label"]
                tools_called.append(tool)
                print(f"\n  [TOOL] {label}")

            elif evt_type == "tool_end":
                ok = event["data"]["ok"]
                print(f"  [TOOL_END] ok={ok}")

            elif evt_type == "safety_warning":
                print(f"\n  [SAFETY] {event['data']['level']}: {event['data']['content'][:80]}")

            elif evt_type == "image":
                print(f"\n  [IMAGE] Page {event['data']['page']}")

            elif evt_type == "artifact":
                print(f"\n  [ARTIFACT] {event['data']['title']} ({event['data']['type']})")

            elif evt_type == "clarification":
                print(f"\n  [CLARIFY] {event['data']['question']}")

            elif evt_type == "done":
                cost = event["data"].get("cost_usd")
                turns = event["data"].get("turns")
                print(f"\n  [DONE] turns={turns}, cost=${cost}")

            elif evt_type == "error":
                print(f"\n  [ERROR] {event['data']['message']}")

        print(f"\n\nTools called: {tools_called}")
        answer = "".join(text_chunks).strip()
        print(f"Answer length: {len(answer)} chars")

        # Basic validation
        if "duty cycle" in q.lower():
            assert "25%" in answer or "25" in answer, f"Expected 25% in answer but got: {answer[:200]}"
            print("PASS: Duty cycle answer contains 25%")

        if "polarity" in q.lower() and "tig" in q.lower():
            assert "DCEN" in answer or "dcen" in answer.lower(), "Expected DCEN in answer"
            print("PASS: TIG polarity answer contains DCEN")


if __name__ == "__main__":
    asyncio.run(main())
