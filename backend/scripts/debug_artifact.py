"""Debug: trace exactly what happens when render_artifact is called."""
from __future__ import annotations

import asyncio
import json

from app.agent.orchestrator import AgentOrchestrator
from app.session.manager import Session


async def main() -> None:
    orch = AgentOrchestrator()
    session = Session(id="debug-artifact")

    query = "Show me the MIG polarity wiring diagram as an SVG artifact"

    print(f"\nQuery: {query}")
    print("=" * 60)

    artifact_count = 0
    all_events: list[dict] = []

    async for event in orch.run(query, session):
        evt_type = event["event"]
        all_events.append(event)

        if evt_type == "text_delta":
            print(event["data"]["content"], end="", flush=True)
        elif evt_type == "tool_start":
            print(f"\n  [TOOL_START] {event['data']['tool']}: {event['data']['label']}")
        elif evt_type == "tool_end":
            print(f"  [TOOL_END] {event['data']['tool']} ok={event['data']['ok']}")
        elif evt_type == "artifact":
            artifact_count += 1
            d = event["data"]
            print(f"\n  [ARTIFACT #{artifact_count}]")
            print(f"    renderer: {d.get('renderer')}")
            print(f"    title: {d.get('title')}")
            print(f"    code length: {len(d.get('code', ''))}")
            print(f"    code preview: {d.get('code', '')[:200]}")
            print(f"    source_pages: {d.get('source_pages')}")
        elif evt_type == "done":
            print(f"\n  [DONE] status={event['data'].get('status')}")
        elif evt_type == "error":
            print(f"\n  [ERROR] {event['data']['message']}")
        elif evt_type == "safety_warning":
            print(f"\n  [SAFETY] {event['data']['level']}")
        elif evt_type == "session_update":
            pass  # skip noise

    print(f"\n\n{'=' * 60}")
    print(f"Total events: {len(all_events)}")
    print(f"Artifacts emitted: {artifact_count}")

    # Dump all non-text events for debugging
    print(f"\nAll non-text events:")
    for e in all_events:
        if e["event"] != "text_delta":
            compact = {
                k: (v[:100] + "..." if isinstance(v, str) and len(v) > 100 else v)
                for k, v in e["data"].items()
            }
            print(f"  {e['event']}: {json.dumps(compact, default=str)}")


if __name__ == "__main__":
    asyncio.run(main())
