"""Run evaluation questions against the agent and report results.

Usage: cd backend && uv run python scripts/run_eval.py

Requires ANTHROPIC_API_KEY in .env.
"""
from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass, field
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


@dataclass(slots=True)
class EvalCase:
    id: str
    question: str
    expected_answer: str = ""
    expected_mode: str = ""
    expected_tool: str = ""
    notes: str = ""


@dataclass(slots=True)
class EvalObservation:
    answer: str
    tools_called: list[str] = field(default_factory=list)
    has_artifact: bool = False
    has_clarification: bool = False
    has_image: bool = False


@dataclass(slots=True)
class EvalResult:
    status: str
    issues: list[str] = field(default_factory=list)


def load_eval_cases(path: Path = EVAL_PATH) -> list[EvalCase]:
    if not path.exists():
        raise FileNotFoundError(f"eval questions not found at {path}")

    with open(path, encoding="utf-8") as f:
        raw_questions = yaml.safe_load(f) or []

    return [
        EvalCase(
            id=item["id"],
            question=item["question"],
            expected_answer=item.get("expected_answer", ""),
            expected_mode=item.get("expected_mode", ""),
            expected_tool=item.get("expected_tool", ""),
            notes=item.get("notes", ""),
        )
        for item in raw_questions
    ]


def _expected_terms(expected_answer: str) -> list[str]:
    parts = [part.strip().lower() for part in expected_answer.split(",") if part.strip()]
    return parts or ([expected_answer.strip().lower()] if expected_answer.strip() else [])


def evaluate_case(case: EvalCase, observation: EvalObservation) -> EvalResult:
    issues: list[str] = []
    status = "passed"
    answer = observation.answer.strip()
    tools_called = [tool for tool in observation.tools_called if tool]
    unique_tools = list(dict.fromkeys(tools_called))

    if case.expected_mode == "clarification":
        if not observation.has_clarification:
            return EvalResult(
                status="failed",
                issues=["Expected clarification flow, but the agent answered directly."],
            )
        return EvalResult(status="passed")

    if not answer:
        return EvalResult(status="failed", issues=["Agent returned an empty answer."])

    if case.expected_tool and case.expected_tool not in unique_tools:
        issues.append(f"Expected tool `{case.expected_tool}` was not called.")
        status = "failed"

    if case.expected_mode in {"diagram", "comparison_table"} and not observation.has_artifact:
        issues.append(f"Expected a rendered artifact for mode `{case.expected_mode}`.")
        status = "failed"

    if case.expected_mode == "image_retrieval" and not observation.has_image:
        issues.append("Expected a manual page image to be returned.")
        status = "failed"

    if case.expected_mode == "multi_tool" and len(unique_tools) < 2:
        issues.append("Expected multiple tool calls for this cross-reference query.")
        status = "failed"

    if case.expected_answer:
        answer_lower = answer.lower()
        missing_terms = [
            term
            for term in _expected_terms(case.expected_answer)
            if term not in answer_lower
        ]
        if missing_terms:
            if status != "failed":
                status = "needs_review"
            issues.append(f"Answer is missing expected terms: {missing_terms}")

    return EvalResult(status=status, issues=issues)


def exit_code_for_results(*, failed: int, needs_review: int) -> int:
    return 1 if failed > 0 or needs_review > 0 else 0


async def run_eval() -> None:
    try:
        questions = load_eval_cases()
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)

    orchestrator = AgentOrchestrator()
    passed = 0
    failed = 0
    needs_review = 0

    for case in questions:
        qid = case.id
        question = case.question

        print(f"\n{'='*60}")
        print(f"[{qid}] {question}")
        print(f"  Expected mode: {case.expected_mode}")
        if case.expected_tool:
            print(f"  Expected tool: {case.expected_tool}")
        if case.expected_answer:
            print(f"  Expected answer contains: {case.expected_answer[:80]}")

        session = Session(id=f"eval-{qid}")
        text_chunks: list[str] = []
        tools_called: list[str] = []
        has_artifact = False
        has_clarification = False
        has_image = False

        try:
            async for event in orchestrator.run(question, session):
                evt = event["event"]
                if evt == "text_delta":
                    text_chunks.append(event["data"].get("content", ""))
                elif evt == "tool_start":
                    tools_called.append(event["data"].get("tool", ""))
                elif evt == "artifact":
                    has_artifact = True
                elif evt == "image":
                    has_image = True
                elif evt == "clarification":
                    has_clarification = True
                elif evt == "error":
                    print(f"  ERROR: {event['data'].get('message', '')}")

            observation = EvalObservation(
                answer="".join(text_chunks).strip(),
                tools_called=tools_called,
                has_artifact=has_artifact,
                has_clarification=has_clarification,
                has_image=has_image,
            )
            result = evaluate_case(case, observation)

            print(f"  Answer length: {len(observation.answer)} chars")
            print(f"  Tools called: {tools_called}")

            if result.status == "passed":
                print("  PASS")
                passed += 1
            elif result.status == "needs_review":
                print("  NEEDS REVIEW")
                for issue in result.issues:
                    print(f"  - {issue}")
                print(f"  Answer preview: {observation.answer[:200]}")
                needs_review += 1
            else:
                print("  FAIL")
                for issue in result.issues:
                    print(f"  - {issue}")
                print(f"  Answer preview: {observation.answer[:200]}")
                failed += 1

        except Exception as e:
            print(f"  ERROR: {e}")
            failed += 1

    print(f"\n{'='*60}")
    print(f"RESULTS: {passed} passed, {failed} failed, {needs_review} needs review")
    print(f"Total: {len(questions)} questions")

    sys.exit(exit_code_for_results(failed=failed, needs_review=needs_review))


if __name__ == "__main__":
    asyncio.run(run_eval())
