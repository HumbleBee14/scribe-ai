"""Claude Vision OCR for page analysis.

Standalone module - no dependency on Agent SDK.
Uses Anthropic client API directly for single-turn vision requests.
Each page is one API call: send image + prompt, get structured JSON back.
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

# Reusable client instance (thread-safe for sequential use)
_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


# Static system prompt - cached across all page calls (same for every page).
# Uses examples instead of abstract instructions. Verbose is fine because caching
# means we only pay for it once.
SYSTEM_PROMPT = """You analyze a single PDF page (image) and extract structured content for retrieval and embedding.

Return a JSON code block with EXACTLY four fields:
- summary
- detailed_text
- keywords
- is_toc

--------------------------------
CORE PRINCIPLE
--------------------------------
Capture ALL visible information:
- Text
- Layout structure
- Tables
- Lists / steps
- Images / diagrams

Do NOT assume document type.

--------------------------------
SUMMARY (CRITICAL FOR RETRIEVAL)
--------------------------------
The summary determines whether this page will be retrieved.

It MUST:
- Describe ALL major content on the page
- Mention:
  - sections / headings
  - lists or steps (include numbers or ranges if visible)
  - tables (what data they contain)
  - warnings (if present)
- IMAGES:
  - Count total images
  - Give EXACTLY one short line per image

Keep it:
- Dense
- Specific
- No fluff

--------------------------------
DETAILED_TEXT (FULL EXTRACTION)
--------------------------------
- Extract ALL meaningful text content
- Preserve structure and order
- DO NOT summarize
- CLEAN UP formatting noise: remove filler dots (......), leader dots or dashes etc.,
  decorative lines, repeated dashes, or other visual separators that
  add no information. Example: "Safety ...............2" becomes "Safety ... 2" or "Safety - 2".

TABLES:
- Convert to markdown tables

LISTS / STEPS:
- Preserve numbering exactly )

IMAGES:
- For EACH image, add detailed description:
- Remember to describe, because the image content is not visible to retrieval/embedding, hence the description is critical for understanding the image with respect to its context in this page.
  Include:
  - objects/components
  - labels/text
  - arrows/flows if present (explain if relevant to understanding the image)

Format:
Image 1: ...
Image 2: ...

--------------------------------
TABLE OF CONTENTS (IMPORTANT)
--------------------------------
If a Table of Contents appears ANYWHERE:
- Extract it completely
- Place it at the TOP of detailed_text
- Set is_toc = true

Even if other content exists on the same page.

--------------------------------
KEYWORDS
--------------------------------
- Minimum: 3
- Maximum: 10
- Focus on:
  - what a user would search to find this page
- Avoid generic words
- Avoid repetition

--------------------------------
STRICT RULES
--------------------------------
- Output ONLY JSON inside ```json
- EXACTLY four fields
- Do NOT omit visible content
- Do NOT hallucinate
- Preserve numbers and formatting exactly

--------------------------------
EXAMPLES
--------------------------------

EXAMPLE 1 - Table + Image:

```json
{
  "summary": "Specifications table listing parameters and values. One table showing voltage, current, and power ratings. Image 1: front panel with labeled display and control knobs.",
  "detailed_text": "SPECIFICATIONS\\n\\n| Parameter | Value |\\n|----------|------|\\n| Voltage | 120V |\\n| Current | 10A |\\n| Power | 1200W |\\n\\nImage 1: Front panel of the device showing a rectangular display at the center, a rotary control knob on the right, and two buttons on the left labeled 'Mode' and 'Set'. The display shows numeric values and unit indicators.",
  "keywords": "specifications, voltage, current, power, front panel, controls",
  "is_toc": false
}
```

EXAMPLE 2 - Pure Table of Contents:

```json
{
  "summary": "Table of Contents listing document sections with page numbers including introduction, setup, operation, maintenance, and troubleshooting.",
  "detailed_text": "Table of Contents\\nIntroduction 1\\nSetup 5\\nOperation 10\\nMaintenance 20\\nTroubleshooting 25",
  "keywords": "table of contents, sections, page numbers, navigation",
  "is_toc": true
}
```

EXAMPLE 3 - Steps + Diagram:

```json
{
  "summary": "Procedure steps 1–3 describing device setup and connection process. Three steps covering power connection, cable attachment, and startup. Image 1: diagram showing cable connections and port locations. Image 2: Diagram showing the rear panel on the left with a labeled power socket, and the front panel on the right with a circular cable port.",
  "detailed_text": "SETUP PROCEDURE\\n\\nStep 1: Connect Power\\nPlug the power cable into the rear socket.\\n\\nStep 2: Attach Cable\\nInsert the cable into the front port until it clicks.\\n\\nStep 3: Turn On Device\\nPress the power button on the top panel.\\n\\nImage 1: Diagram showing the rear panel on the left with a labeled power socket, and the front panel on the right with a circular cable port. Arrows indicate cable insertion directions from cable to ports. Image 2: Diagram showing the rear panel on the left with a labeled power socket, and the front panel on the right with a circular cable port.",
  "keywords": "setup steps, power connection, cable attachment, device startup",
  "is_toc": false
}
```
EXAMPLE 4 - MIXED: TOC/Index + CONTENT:

```json
{
  "summary": "Table of Contents listing sections with page numbers followed by safety instructions. TOC includes safety, setup, and operation sections. Additional warning text and general safety guidelines are present.",
  "detailed_text": "Table of Contents\\nSafety ... 2\\nSetup ... 5\\nOperation ... 10\\n\\nIMPORTANT SAFETY INFORMATION\\n\\nWARNING\\nRead all instructions before use. Failure to follow instructions may result in injury.\\n\\nGeneral Safety\\n1. Keep away from children.\\n2. Do not operate while tired.",
  "keywords": "table of contents, safety instructions, warning, general safety",
  "is_toc": true
}
```

Rules:
- Always wrap your JSON in a ```json code block
- For summary, capture ALL major content on the page, including sections/headings, lists/steps, tables and images. Be concise but specific. this Summary is used to determine if the page is retrieved, so it MUST mention all key content. Do NOT omit or summarize content here, but do NOT include minor details or decorative text. For images, give EXACTLY one short line per image describing its content.
- For detailed_text, Extract ALL text verbatim - do not summarize or skip content, but ignore decorative text that does not add meaning to the page, like header, page numbers, footers, or copyright notices or anything.
- Convert tables to markdown table format with pipes and headers
- Describe every image/diagram with labels, part numbers, and spatial relationships, caption, if nothing given, understand the image with surrounding text and give it a descriptive.
- Preserve exact values: voltages, amperages, measurements, part numbers or whatever numeric values you see, do not round or approximate.
- For steps/procedures, preserve exact step numbers
- If content continues from the previous page or to the next page, say so in the summary
- Set is_toc to true ONLY for actual table of contents / index pages"""


MAX_RETRIES = 2


def analyze_page(
    image_path: Path,
    product_id: str,
    source_id: str,
    source_label: str,
    page_number: int,
    total_pages: int,
) -> dict | None:
    """Analyze a single page image via Claude Vision. Stores result in DB.

    Retries up to MAX_RETRIES times on API or parse failures.
    Returns the parsed JSON dict on success, None on failure.
    All errors are logged, never raised.
    """
    if not image_path.exists():
        logger.error("[OCR] Page image not found: %s", image_path)
        return None

    client = _get_client()
    image_data = base64.standard_b64encode(image_path.read_bytes()).decode("utf-8")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.messages.create(
                model=settings.llm_model,
                max_tokens=4096,
                system=[
                    {
                        "type": "text",
                        "text": SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": image_data,
                                },
                            },
                            {
                                "type": "text",
                                "text": f'This is page {page_number} of {total_pages} from "{source_label}". Analyze this page.',
                            },
                        ],
                    }
                ],
            )

            raw = response.content[0].text.strip()

            # Extract JSON from code block
            code_match = re.search(r"```(?:json)?\s*\n([\s\S]*?)\n\s*```", raw)
            json_str = code_match.group(1).strip() if code_match else raw
            result = json.loads(json_str)

            # Store in DB
            db.upsert_page_analysis(
                product_id=product_id,
                source_id=source_id,
                page=page_number,
                summary=result.get("summary", ""),
                detailed_text=result.get("detailed_text", ""),
                keywords=result.get("keywords", ""),
                is_toc=bool(result.get("is_toc", False)),
            )

            if result.get("is_toc"):
                _extract_toc_entries(product_id, source_id, page_number, result.get("detailed_text", ""))

            logger.info(
                "[OCR] %s/%s page %d/%d: OK (%d chars, toc=%s)",
                product_id, source_id, page_number, total_pages,
                len(result.get("detailed_text", "")),
                result.get("is_toc", False),
            )
            return result

        except json.JSONDecodeError:
            logger.error(
                "[OCR] %s/%s page %d: invalid JSON (attempt %d/%d)",
                product_id, source_id, page_number, attempt, MAX_RETRIES,
            )
        except anthropic.APIError as exc:
            logger.error(
                "[OCR] %s/%s page %d: API error (attempt %d/%d) - %s",
                product_id, source_id, page_number, attempt, MAX_RETRIES, exc,
            )
        except Exception:
            logger.exception(
                "[OCR] %s/%s page %d: unexpected error (attempt %d/%d)",
                product_id, source_id, page_number, attempt, MAX_RETRIES,
            )

    logger.error(
        "[OCR] %s/%s page %d: FAILED after %d attempts",
        product_id, source_id, page_number, MAX_RETRIES,
    )
    return None


def _extract_toc_entries(product_id: str, source_id: str, page_number: int, text: str) -> None:
    """Parse TOC page text into structured entries."""
    entries: list[tuple[str, int]] = []
    for line in text.split("\n"):
        match = re.match(r"^(.+?)\s*[.\s]{2,}\s*(\d+)\s*$", line.strip())
        if match:
            title = match.group(1).strip().rstrip(".")
            page = int(match.group(2))
            if title and page > 0:
                entries.append((title, page))

    for i, (title, start_page) in enumerate(entries):
        end_page = entries[i + 1][1] - 1 if i + 1 < len(entries) else None
        db.upsert_toc_entry(product_id, source_id, title, start_page, end_page)

    if entries:
        logger.info("[OCR] Extracted %d TOC entries from page %d", len(entries), page_number)
