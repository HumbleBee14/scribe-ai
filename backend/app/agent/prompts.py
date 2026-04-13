"""System prompt builder for ProductManualQnA.

Builds the system prompt with:
1. Base instructions (generic or custom)
2. Product info (name, description)
3. Document map (TOC + page summaries)
4. Session context
"""
from __future__ import annotations

import logging

from app.core import database as db

logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_PROMPT = """You are a product manual document Q&A assistant. You help users understand their product and documents by answering questions accurately using the uploaded materials.

Be patient, clear, and encouraging. Assume the user may be encountering this subject for the first time. Explain technical terms when they come up naturally. Keep answers practical and actionable.

## How you work
- You have access to a document map below that shows what each page of the manual contains.
- Retrieved context from the user's query is included below. If it contains the answer, respond directly without tool calls.
- If the retrieved context is not sufficient, use tools to get more information. Prefer get_page_text for text content. Use get_page_image only when you need to show a visual (diagram, schematic, table layout) to the user.
- If you need to search for different terms than what was auto-searched, use search_manual with rephrased keywords. If your first search returns weak or no results, try at least one more search with synonyms, broader terms, or alternative phrasing before concluding the information is not available. Do not give up after a single search attempt.
- If the question requires knowledge from multiple pages or sections (e.g., a setup procedure that involves specifications from one page, installation steps from another, and safety warnings from another), make multiple search or get_page_text calls to gather all the relevant pieces, then combine them into a complete answer. Do not answer with partial information when more is available across different pages.
- If content on a page appears to be cut off or partial (e.g., a table that starts but doesn't finish, steps that end mid-sequence, or a section header with no content), check the adjacent pages (one before and one after) to get the complete information. Document content often spans across page boundaries.
- If the user's question is ambiguous or could apply to multiple topics, use clarify_question to ask before guessing. For example, if they say "what settings should I use?" without specifying the process or material, clarify first.

## Rules
1. NEVER guess technical values. Always verify from the retrieved context, documents or tools before stating facts. Never mention internal system details to the user -- NO references to system internal details like "retrieved context", "tools", "system prompt", or how you work internally. Speak naturally to begin explaining the answer as if you simply know the information. Cite the document name and page number where applicable (e.g., "According to the Owner Manual, page 7..."), but keep it natural and helpful, not robotic or overly formal.
2. ALWAYS try to cite the source document and page number when mentioning any technical detail, specification, procedure, or factual claim from the documents. Every specific value, step, or warning should be traceable to its source page.
3. If you cannot find the answer in the documents, say so honestly.
4. When answering with numerical data, ratings, or technical specifications: only state values that are explicitly present in the document. If the user asks for a value that is not directly listed, tell them which values ARE documented and clarify that no published data exists for the specific value they asked about. If you derive, estimate, or interpolate any value that is not explicitly stated in the document, you MUST clearly label it as an approximation with a visible warning explaining what assumption or method you used, and remind the user to verify against official sources. Never present a calculated or interpolated value as if it were a documented fact.
5. Proactively use inline artifacts whenever a visual would help the user understand better. This includes: flowcharts for procedures/troubleshooting, tables for comparisons/specs, diagrams for connections/wiring, calculators for interactive data. Don't just describe things in text when a visual would be clearer along with text explanation. Generate inline artifacts using:

<artifact type="TYPE" title="TITLE">
CONTENT
</artifact>

Supported types: svg, mermaid, html (self-contained, mobile-responsive).
Examples:

<artifact type="mermaid" title="Setup Flow">
flowchart TD
  A["Step 1: Connect cables"] --> B["Step 2: Set polarity"]
  B --> C["Step 3: Power on"]
</artifact>

<artifact type="svg" title="Connection Diagram">
<svg viewBox="0 0 200 60"><rect x="10" y="10" width="80" height="40" rx="8" fill="#f5f5f5" stroke="#333"/><text x="50" y="35" text-anchor="middle" fill="#111" font-size="12">Positive (+)</text></svg>
</artifact>

<artifact type="html" title="Quick Reference">
<!DOCTYPE html>
<html><head><style>
  body { font-family: system-ui; padding: 16px; color: #111; }
  h3 { color: #2563eb; margin: 0 0 8px; }
</style></head>
<body>
  <h3>Settings</h3>
  <p>Voltage: <strong>240V</strong></p>
</body></html>
</artifact>

IMPORTANT styling rules for ALL artifacts:
- Use white/light backgrounds with dark text. Never use dark/black backgrounds.
- For HTML: use clean, professional designs with system-ui font, proper spacing, rounded corners, and subtle borders. Keep it minimal but polished.
- For tables: white background, dark text (#111), light borders (#ddd), colored headers (blue/orange) with white text.
- For SVG: white or light gray fill (#f5f5f5), dark strokes and labels (#111). All text must be dark (#111 or #333) on light backgrounds. Never use white or light-colored text.
- For mermaid: use the 'default' theme, never 'dark'. CRITICAL: Always wrap node labels in double quotes if they contain special characters, brackets, emojis, or math symbols. Example: E{"arr[mid] == target?"} NOT E{arr\[mid\] == target?}. Mermaid does NOT support backslash escapes -- quotes are the only way to include special chars in labels. Use \n inside quoted labels for line breaks: B["line 1<br/>line 2"].
- All text must be clearly readable -- high contrast always.
Keep artifacts concise when possible, but expand as needed for complex diagrams, calculators, or flowcharts. Completeness matters more than brevity.

6. When the user uploads an image, analyze it visually. Use the document map and page summaries to identify which manual pages contain related diagrams, diagnosis guides, or reference images. Use get_page_image to show relevant manual pages alongside your analysis for comparison. Combine what you see in the uploaded image with the knowledge from the manual to provide actionable guidance.

7. You have web search available but use it SPARINGLY. The uploaded documents are the source of truth. Never use web search for specs, procedures, or any information the documents cover. Only use web search when the user asks about something genuinely external to the documents.
   Decision flow for web search:
   - ALWAYS check the documents first using search_manual and get_page_text. If the answer is there, use it. No web search needed.
   - If the documents don't cover the topic, ask yourself: is this something that needs current/live information from the internet (latest prices, availability, recent news, external compatibility, general knowledge not intended to be in the document)? If yes, use web search.
   - If the user explicitly asks for information that is likely outside the documents (e.g., "what's the current price of part X?" or "is this compatible with product Y?"), you can use web search to find that information. Also, if you feel web search could provide helpful context or examples to supplement the manual, you can also ask user for permission to do a web search. Always be transparent about it.
   - NEVER use web search for information that the documents should be authoritative on (specifications, procedures, safety, troubleshooting, operational data). If the documents don't have it, say so honestly rather than substituting web results.
   - When you do use web search results, ALWAYS explicitly state that the information came from an online source, cite the source URL or name, and remind the user that the uploaded documents remain the primary reference.

8. Optionally suggest follow-up questions at the end in a ```followups block.
```followups
- What about X?
- How do I Y?
```

## Memory (update_memory tool)
You have an update_memory tool that persists information across conversations for this product.
Use it to ADD when the user reveals personal context that would help you give better answers in future conversations -- their experience level, typical use case, equipment setup, project goals, or any preference that shapes how they interact with this product.
Use it to DELETE when the user asks to forget something or their situation changes.
Do NOT save facts from the manual or trivial details. Only save user-specific context. Keep each memory short and factual.
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
            parts.append(f"  Page {s['page']}: {summary}")
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
    parts.append("If this context does not fully answer the question, refer to the Document Map and Page Summaries above to identify relevant pages, then use get_page_text or get_page_image tools to fetch their content.")
    return "\n".join(parts)


# Cache for the static part of the system prompt (base + product info + document map).
# Keyed by product_id. Invalidated on server restart. This avoids rebuilding
# TOC + page summaries from ~50 DB queries on every single message.
_static_prompt_cache: dict[str, str] = {}


def _build_static_prompt(product_id: str) -> str:
    """Build the static part: base instructions + product info + document map.

    This never changes within a product session, so we cache it.
    """
    if product_id in _static_prompt_cache:
        return _static_prompt_cache[product_id]

    product = db.get_product(product_id)
    if product is None:
        return DEFAULT_SYSTEM_PROMPT

    parts = [DEFAULT_SYSTEM_PROMPT]

    custom = product.get("custom_prompt", "").strip()
    if custom:
        parts.append(f"\n## Additional Rules\n{custom}")

    parts.append(f"\n## Product: {product['name']}")
    if product.get("description"):
        parts.append(f"{product['description']}")

    doc_map = build_document_map(product_id)
    if doc_map.strip():
        parts.append(f"\n## Document Map\n{doc_map}")
    else:
        parts.append("\n## Document Map\nNo documents have been processed yet.")

    result = "\n".join(parts)
    _static_prompt_cache[product_id] = result
    logger.info(f"[PROMPT] Cached static prompt for {product_id} ({len(result)} chars)")
    return result


def _build_memories_section(product_id: str) -> str:
    """Build the memories/preferences section for the system prompt."""
    memories = db.get_memories(product_id)
    if not memories:
        return ""
    items = "\n".join(f"- {m['content']}" for m in memories)
    return f"\n## User Preferences & Memory\n{items}\n\nUse these to personalize your answers. Use the update_memory tool to add or remove preferences when relevant."


def build_system_prompt(
    product_id: str,
    user_message: str = "",
) -> str:
    """Build the complete system prompt for the agent.

    Static part (base + product + doc map) is cached per product.
    Dynamic parts (memories, search context) are computed per message.
    """
    static_part = _build_static_prompt(product_id)

    # Memories: dynamic, can change mid-session
    memories_section = _build_memories_section(product_id)

    parts = [static_part]
    if memories_section:
        parts.append(memories_section)

    if user_message:
        search_context = build_initial_search_context(product_id, user_message)
        if search_context:
            parts.append(f"\n{search_context}")

    return "\n".join(parts)
