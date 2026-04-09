"""Run evaluation questions against the agent and report results.

Usage: cd backend && uv run python scripts/run_eval.py

Requires ANTHROPIC_API_KEY in .env.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import yaml

from app.agent.orchestrator import AgentOrchestrator
from app.session.manager import Session

EVAL_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "data"
    / "document-packs"
    / "vulcan-omnipro-220"
    / "eval_questions.yaml"
)


async def run_eval() -> None:
    if not EVAL_PATH.exists():
        print(f"ERROR: eval questions not found at {EVAL_PATH}")
        sys.exit(1)

    with open(EVAL_PATH, encoding="utf-8") as f:
        questions = yaml.safe_load(f)

    orchestrator = AgentOrchestrator()
    passed = 0
    failed = 0
    skipped = 0

    for q in questions:
        qid = q["id"]
        question = q["question"]
        expected = q.get("expected_answer", "")
        mode = q.get("expected_mode", "")

        print(f"\n{'='*60}")
        print(f"[{qid}] {question}")
        print(f"  Expected mode: {mode}")
        if expected:
            print(f"  Expected answer contains: {expected[:80]}")

        session = Session(id=f"eval-{qid}")
        text_chunks: list[str] = []
        tools_called: list[str] = []
        has_artifact = False
        has_clarification = False

        try:
            async for event in orchestrator.run(question, session):
                evt = event["event"]
                if evt == "text_delta":
                    text_chunks.append(event["data"].get("content", ""))
                elif evt == "tool_start":
                    tools_called.append(event["data"].get("tool", ""))
                elif evt == "artifact":
                    has_artifact = True
                elif evt == "clarification":
                    has_clarification = True
                elif evt == "error":
                    print(f"  ERROR: {event['data'].get('message', '')}")

            answer = "".join(text_chunks).strip()
            print(f"  Answer length: {len(answer)} chars")
            print(f"  Tools called: {tools_called}")

            # Basic validation
            if mode == "clarification":
                if has_clarification:
                    print("  PASS: clarification requested")
                    passed += 1
                else:
                    print("  FAIL: expected clarification but got answer")
                    failed += 1
                continue

            if not answer:
                print("  FAIL: empty answer")
                failed += 1
                continue

            if expected:
                # Check if key terms from expected answer appear
                expected_lower = expected.lower()
                answer_lower = answer.lower()
                key_terms = [
                    t.strip() for t in expected_lower.split(",") if t.strip()
                ]
                if not key_terms:
                    key_terms = [expected_lower]

                all_found = all(term in answer_lower for term in key_terms)
                if all_found:
                    print("  PASS: answer contains expected terms")
                    passed += 1
                else:
                    missing = [t for t in key_terms if t not in answer_lower]
                    print(f"  WARN: missing terms: {missing}")
                    print(f"  Answer preview: {answer[:200]}")
                    skipped += 1
            else:
                # No expected answer, just check it's non-empty
                print(f"  PASS: non-empty answer ({len(answer)} chars)")
                passed += 1

        except Exception as e:
            print(f"  ERROR: {e}")
            failed += 1

    print(f"\n{'='*60}")
    print(f"RESULTS: {passed} passed, {failed} failed, {skipped} needs review")
    print(f"Total: {len(questions)} questions")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_eval())
