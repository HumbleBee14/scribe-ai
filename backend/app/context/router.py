from __future__ import annotations

from dataclasses import dataclass

from app.packs.models import ProductRuntime
from app.retrieval.service import RetrievalService


@dataclass(slots=True)
class ContextRoute:
    strategy: str
    exact_tool_candidates: list[str]
    notes: list[str]


def select_context_route(
    user_message: str,
    runtime: ProductRuntime,
    retrieval: RetrievalService | None = None,
) -> ContextRoute:
    if runtime.status != "ready":
        return ContextRoute(
            strategy="pending_ingestion",
            exact_tool_candidates=[],
            notes=["This product is not fully ingested yet."],
        )

    if retrieval is None:
        return ContextRoute(strategy="tool_only", exact_tool_candidates=[], notes=[])

    profile = retrieval.classify_query(user_message)
    candidates: list[str] = []
    if profile.is_duty_cycle:
        candidates.append("lookup_duty_cycle")
    if profile.is_polarity:
        candidates.append("lookup_polarity")
    if profile.is_troubleshooting:
        candidates.append("lookup_troubleshooting")
    if profile.is_safety:
        candidates.append("lookup_safety_warnings")
    if profile.is_settings:
        candidates.append("lookup_settings")

    if candidates:
        return ContextRoute(
            strategy="exact_tool",
            exact_tool_candidates=candidates,
            notes=["Use grounded exact-data tools before broader retrieval."],
        )

    return ContextRoute(
        strategy="retrieval",
        exact_tool_candidates=[],
        notes=[],
    )

