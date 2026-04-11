"""System prompt builder for ProductManualQnA.

Builds the system prompt with:
1. Base instructions (generic or custom)
2. Product info (name, description)
3. Document map (TOC + page summaries)
4. Session context
"""
from __future__ import annotations

from app.core import database as db

DEFAULT_SYSTEM_PROMPT = """You are a product manual Q&A assistant. You help users understand their product by answering questions accurately using the uploaded manual documents.

## How you work
- You have access to a document map below that shows what each page of the manual contains.
- Retrieved context from the user's query is included below. If it contains the answer, respond directly without tool calls.
- If the retrieved context is not sufficient, use tools to get more information. Prefer get_page_text for text content. Use get_page_image only when you need to show a visual (diagram, schematic, table layout) to the user.
- If you need to search for different terms than what was auto-searched, use search_manual with rephrased keywords.

## Rules
1. NEVER guess technical values. Always verify from the retrieved context or tools before stating facts.
2. ALWAYS cite the source document and page number (e.g., "see Owner Manual, page 7").
3. If you cannot find the answer in the documents, say so honestly.
4. For complex comparisons or calculations, generate inline artifacts:

<artifact type="TYPE" title="TITLE">
CONTENT
</artifact>

Supported types: svg, mermaid, html (self-contained, dark-themed, mobile-responsive).

5. Optionally suggest follow-up questions at the end in a ```followups block.
"""


def build_document_map(product_id: str) -> str:
    """Build the document map string from DB (TOC + page summaries)."""
    parts: list[str] = []

    # TOC entries grouped by source
    toc = db.get_toc(product_id)
    if toc:
        parts.append("### Table of Contents")
        current_source = None
        for entry in toc:
            if entry["source_id"] != current_source:
                current_source = entry["source_id"]
                parts.append(f"\n[{current_source}]")
            parts.append(f"  {entry['title']} ... page {entry['start_page']}")
        parts.append("")

    # Page summaries grouped by source
    summaries = db.get_all_page_summaries(product_id)
    if summaries:
        parts.append("### Page Summaries")
        current_source = None
        for s in summaries:
            if s["source_id"] != current_source:
                current_source = s["source_id"]
                parts.append(f"\n[{current_source}]")
            summary = s["summary"][:150] if s["summary"] else "(pending)"
            parts.append(f"  p{s['page']}: {summary}")
        parts.append("")

    return "\n".join(parts)


def build_initial_search_context(product_id: str, user_message: str) -> str:
    """Run hybrid search and return full detailed_text for top 4 pages.

    Sends actual page content (not summaries) so the agent can answer
    directly without needing tool calls for most questions.
    Results ordered: least relevant first, most relevant last (recency bias).
    """
    from app.agent.tools import _hybrid_search

    results = _hybrid_search(product_id, user_message, limit=3)
    if not results:
        print(f"[SEARCH] No results for: {user_message}", flush=True)
        return ""

    # Two-path qualification — a page qualifies for context injection if EITHER:
    #
    # Path A — Strong standalone semantic match (vec_distance < 0.80)
    #   For page-level embeddings of a product manual, empirical data shows:
    #     Best relevant match:    vec_dist ≈ 0.75-0.80  (e.g. very on-topic page)
    #     Typical relevant match: vec_dist ≈ 0.85-1.05
    #     Unrelated page:         vec_dist > 1.2
    #   Threshold 0.80 catches genuinely similar pages even if FTS has no keyword hit.
    #   Useful for paraphrase/synonym queries ("bubbly welds" → "porosity").
    #
    # Path B — BOTH signals present + combined score (fts AND vec AND score >= 0.52)
    #   Requires: FTS keyword found + vec match found (not None) + combined >= 0.52.
    #   The explicit vec_dist is not None check prevents pure FTS-only hits
    #   (which cap at 0.50) from passing — they only got FTS, no semantic signal.
    #   0.52 sits above the max FTS-only score (0.50), so it can only be reached
    #   when both signals contribute.
    #
    # Pure FTS-only (vec_dist=None, score≤0.50) → never qualifies.
    def _qualifies(r: dict) -> tuple[bool, str]:
        vec_dist = r.get("vec_distance")
        score = r.get("score", 0)
        fts_hit = r.get("fts_hit", False)
        # Path A: strong standalone semantic match, regardless of FTS
        if vec_dist is not None and vec_dist < 0.80:
            return True, f"path=A"
        # Path B: both signals present + combined score threshold
        if fts_hit and vec_dist is not None and score >= 0.52:
            return True, f"path=B"
        return False, "skip"

    print(f"\n[SEARCH] Query: {user_message[:100]!r}", flush=True)
    filtered = []
    for r in results:
        qualifies, path = _qualifies(r)
        vec_str = f"{r['vec_distance']:.3f}" if r.get("vec_distance") is not None else "none"
        status = f"✓ {path}" if qualifies else "✗ skip"
        print(
            f"  [{r['source_id']}] p{r['page']:>2}  "
            f"score={r.get('score', 0):.3f}  fts={'Y' if r['fts_hit'] else 'N'}  "
            f"vec={vec_str}  → {status}",
            flush=True,
        )
        if qualifies:
            filtered.append(r)

    if not filtered:
        print("[SEARCH] No pages qualified → skipping context injection", flush=True)
        return ""

    injected = [(r["source_id"], r["page"]) for r in filtered]
    print(f"[SEARCH] Injecting {len(injected)} page(s): {injected}", flush=True)

    # Reverse: least relevant first, most relevant last (recency bias)
    filtered = list(reversed(filtered))

    # Fetch full detailed_text for each page
    parts = ["## Retrieved Context (from your query)"]
    for r in filtered:
        page_data = db.get_page_analysis(product_id, r["source_id"], r["page"])
        if page_data and page_data.get("detailed_text"):
            parts.append(f"\n--- [{r['source_id']}] Page {r['page']} ---")
            parts.append(page_data["detailed_text"])
        else:
            # Fallback to summary if detailed_text not available
            if r.get("summary"):
                parts.append(f"\n--- [{r['source_id']}] Page {r['page']} ---")
                parts.append(r["summary"])

    parts.append("\n--- End of retrieved context ---")
    parts.append("If this context is not sufficient, use search_manual or get_page_text tools for more pages.")
    return "\n".join(parts)


def build_system_prompt(
    product_id: str,
    user_message: str = "",
) -> str:
    """Build the complete system prompt for the agent.

    Includes: base instructions + product info + document map + initial search context.
    """
    product = db.get_product(product_id)
    if product is None:
        return DEFAULT_SYSTEM_PROMPT

    # Base prompt: custom or default
    custom = product.get("custom_prompt", "").strip()
    base_prompt = custom if custom else DEFAULT_SYSTEM_PROMPT

    parts = [base_prompt]

    # Product info (always included)
    parts.append(f"\n## Product: {product['name']}")
    if product.get("description"):
        parts.append(f"{product['description']}")

    # Document map (always included)
    doc_map = build_document_map(product_id)
    if doc_map.strip():
        parts.append(f"\n## Document Map\n{doc_map}")
    else:
        parts.append("\n## Document Map\nNo documents have been processed yet.")

    # Initial search context (hybrid search on user query)
    if user_message:
        search_context = build_initial_search_context(product_id, user_message)
        if search_context:
            parts.append(f"\n{search_context}")

    return "\n".join(parts)
