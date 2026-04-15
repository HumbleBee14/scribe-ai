"""Build structured Table of Contents from tagged TOC pages.

After the main OCR pipeline tags pages as is_toc=True, this module:
1. Collects all TOC-tagged pages for a source document
2. Sends ALL TOC page images to Claude Vision in a single call
3. Gets back a clean structured JSON of sections with page numbers
4. Stores in the toc_entries table

One LLM call per source document (not per page). Uses prompt caching.
If no TOC pages were tagged during OCR, this step is skipped.
"""
from __future__ import annotations

import base64
import json
import logging
import re
from pathlib import Path

import anthropic

from app.core.config import settings
from app.core import database as db

logger = logging.getLogger(__name__)

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


_TOC_SYSTEM_PROMPT = """You extract structured Table of Contents from manual pages.

You will receive one or more page images that contain a Table of Contents, Index, or section listing.
Extract ALL entries into a clean JSON array.

Return a JSON code block with this structure:

```json
[
  {"title": "Safety", "page": 2},
  {"title": "Specifications", "page": 7},
  {"title": "Controls", "page": 8},
  {"title": "MIG/Flux-Cored Wire Welding", "page": 10},
  {"title": "Troubleshooting", "page": 25}
]
```

Rules:
- Each entry has "title" (section name) and "page" (start page number as integer)
- Preserve the exact section titles as written in the document
- Remove filler dots, dashes, or decorative separators between title and page number
- Include ALL entries, even sub-sections if they have page numbers
- Order by page number ascending
- If multiple TOC pages are provided, combine all entries into one list
- Return ONLY the JSON code block, no other text"""


def build_toc_for_source(
    product_id: str,
    source_id: str,
    pages_dir: Path,
) -> int:
    """Build structured TOC from tagged TOC pages.

    Returns the number of TOC entries extracted, or 0 if no TOC pages.
    """
    # Find all pages tagged as TOC during OCR
    toc_pages = []
    summaries = db.get_all_page_summaries(product_id)
    for s in summaries:
        if s["source_id"] == source_id and s.get("is_toc"):
            toc_pages.append(s["page"])

    if not toc_pages:
        logger.info("[TOC] No TOC pages found for %s/%s, skipping", product_id, source_id)
        return 0

    toc_pages.sort()
    logger.info("[TOC] Found %d TOC pages for %s/%s: %s", len(toc_pages), product_id, source_id, toc_pages)

    # Build message with ALL TOC page images
    content: list[dict] = []
    for page_num in toc_pages:
        image_path = pages_dir / f"page_{page_num:02d}.png"
        if not image_path.exists():
            logger.warning("[TOC] Missing image for page %d", page_num)
            continue
        image_data = base64.standard_b64encode(image_path.read_bytes()).decode("utf-8")
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": image_data,
            },
        })

    if not content:
        return 0

    content.append({
        "type": "text",
        "text": f"These are {len(toc_pages)} Table of Contents page(s) from the document. Extract all section entries.",
    })

    # Single LLM call with all TOC images
    client = _get_client()
    try:
        response = client.messages.create(
            model=settings.llm_model,
            max_tokens=2048,
            system=[{
                "type": "text",
                "text": _TOC_SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": content}],
        )

        raw = response.content[0].text.strip()

        # Extract JSON from code block
        code_match = re.search(r"```(?:json)?\s*\n([\s\S]*?)\n\s*```", raw)
        json_str = code_match.group(1).strip() if code_match else raw

        entries = json.loads(json_str)
        if not isinstance(entries, list):
            logger.error("[TOC] Expected list, got %s", type(entries))
            return 0

        # Clear old TOC entries for this source
        db.delete_toc_for_source(product_id, source_id)

        # Store each entry
        for entry in entries:
            title = str(entry.get("title", "")).strip()
            page = entry.get("page")
            if title and isinstance(page, int) and page > 0:
                db.upsert_toc_entry(
                    product_id=product_id,
                    source_id=source_id,
                    title=title,
                    start_page=page,
                )

        count = len([e for e in entries if e.get("title") and isinstance(e.get("page"), int)])
        print(f"[TOC] Extracted {count} entries for {product_id}/{source_id} from {len(toc_pages)} TOC pages", flush=True)
        return count

    except json.JSONDecodeError:
        logger.error("[TOC] Failed to parse JSON from LLM response")
        return 0
    except anthropic.APIError as exc:
        logger.error("[TOC] API error: %s", exc)
        return 0
    except Exception:
        logger.exception("[TOC] Unexpected error building TOC")
        return 0
