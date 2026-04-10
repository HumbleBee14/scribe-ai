from __future__ import annotations

from app.context.models import ContextBundle, ContextChunk
from app.context.router import select_context_route
from app.packs.models import ProductRuntime
from app.retrieval.service import RetrievalService, get_retrieval_service
from app.session.manager import Session
from app.session.summary import build_session_summary


class ContextAssembler:
    """Centralizes how product-scoped grounded context is selected per query."""

    def assemble(
        self,
        user_message: str,
        session: Session,
        runtime: ProductRuntime,
    ) -> ContextBundle:
        retrieval: RetrievalService | None = None
        try:
            retrieval = get_retrieval_service(runtime.index_dir)
        except Exception:
            retrieval = None

        route = select_context_route(user_message, runtime, retrieval)
        bundle = ContextBundle(
            product_id=runtime.id,
            strategy=route.strategy,
            session_summary=build_session_summary(session),
            exact_tool_candidates=route.exact_tool_candidates,
            notes=list(route.notes),
            knowledge_map_path=str(runtime.graph_dir / "knowledge-map.json")
            if (runtime.graph_dir / "knowledge-map.json").exists()
            else None,
        )

        if route.strategy == "retrieval" and retrieval is not None:
            for item in retrieval.search(user_message, max_results=3):
                bundle.retrieved_chunks.append(
                    ContextChunk(
                        page=item["page"],
                        section=item["section"],
                        text=item["text"],
                        score=item.get("score"),
                        source_id=item.get("source_id"),
                    )
                )

        return bundle

