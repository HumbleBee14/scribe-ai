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
- Use the search_manual tool to find relevant pages by keywords.
- Use the get_page_text tool to read the full content of specific pages.
- Use the get_page_image tool to show diagrams, tables, or visual content to the user.
- Use the clarify_question tool if the user's question is ambiguous.

## Rules
1. NEVER guess technical values. Always verify using tools before stating facts.
2. ALWAYS cite the source document and page number (e.g., "see Owner Manual, page 7").
3. If you cannot find the answer in the documents, say so honestly.
4. When showing visual content (diagrams, schematics), use get_page_image and reference the page.
5. For complex comparisons or calculations, generate inline artifacts:

<artifact type="TYPE" title="TITLE">
CONTENT
</artifact>

Supported types: svg, mermaid, html (self-contained, dark-themed, mobile-responsive).

6. Optionally suggest follow-up questions at the end of your response in a ```followups block.
"""


def build_document_map(product_id: str) -> str:
    """Build the document map string from DB (TOC + page summaries)."""
    parts: list[str] = []

    # TOC entries
    toc = db.get_toc(product_id)
    if toc:
        parts.append("### Table of Contents")
        for entry in toc:
            end = f"-{entry['end_page']}" if entry.get("end_page") else ""
            parts.append(f"- {entry['title']} ... page {entry['start_page']}{end} [{entry['source_id']}]")
        parts.append("")

    # Page summaries grouped by source
    summaries = db.get_all_page_summaries(product_id)
    if summaries:
        parts.append("### Page Summaries")
        current_source = None
        for s in summaries:
            if s["source_id"] != current_source:
                current_source = s["source_id"]
                parts.append(f"\n**{current_source}:**")
            summary = s["summary"][:200] if s["summary"] else "(pending)"
            parts.append(f"  Page {s['page']}: {summary}")
        parts.append("")

    return "\n".join(parts)


def build_initial_search_context(product_id: str, user_message: str) -> str:
    """Run hybrid search on user query and format top results as initial context.

    This runs BEFORE the agent starts, so the agent has relevant page content
    from the very first turn without needing to call tools.
    """
    from app.agent.tools import _hybrid_search

    results = _hybrid_search(product_id, user_message, limit=5)
    if not results:
        return ""

    parts = ["## Relevant Pages (from your query)"]
    parts.append("These pages were found by searching your question against the manual:\n")
    for r in results:
        parts.append(f"**[{r['source_id']}] Page {r['page']}** (relevance: {r.get('score', 0):.2f})")
        if r.get("summary"):
            parts.append(f"  {r['summary'][:300]}")
        parts.append("")

    parts.append("Use get_page_text to read the full content of any page listed above.")
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
