# Final Canonical Design

**Date:** 2026-04-09

**Project:** `multimodal-prox-challenge`

## Goal
Build the strongest possible multimodal product-support agent for the Vulcan OmniPro 220 challenge while establishing a reusable architecture for future document-heavy product assistants.

This final design intentionally merges:
- the strongest parts of the existing `multimodal-prox-challenge` design
- the strongest parts of the alternate proposal in `docs/superpowers`
- the most valuable learnings from competitor reviews and research

This document is the canonical architecture to review and finalize.

---

## Final Decision Summary

### Canonical stack
- `Frontend`: Next.js + TypeScript + React + Tailwind
- `Backend`: Python + FastAPI
- `Agent runtime`: Anthropic Claude Agent SDK as the official orchestration foundation
- `Parsing`: PyMuPDF as primary, Docling as optional enhancement/fallback
- `Local storage`: SQLite + FTS5 + optional `sqlite-vec`
- `Production storage`: Postgres + pgvector
- `Assets`: local filesystem in dev, object storage in prod

### Core strategy
- use **structured exact-data tools** for all high-risk factual answers
- use **full-context mode early** for broad manual understanding in this single-manual challenge
- use **hybrid retrieval** for broader manual understanding
- use **visual retrieval** for diagrams, photos, schematics, and page previews
- use **typed evidence objects** with `bbox`, `cropUrl`, and `exactness`
- use **typed artifacts** with mandatory source references
- support **full-context mode** for this challenge because the manual fits in the model context window

### Explicit anti-patterns
- no interpolation for exact technical values
- no claiming image-input support unless it is fully wired
- no Docker-only local path
- no page-number-only grounding when better region-level evidence exists

---

## Why This Is The Final Direction

This architecture is chosen because it best balances:
- challenge compliance
- answer accuracy
- multimodal depth
- evaluator setup speed
- production readiness
- future generalization

It avoids the biggest weakness in many competitor submissions:
- raw Messages API instead of the Agent SDK
- weak or page-only grounding
- overclaiming user-image multimodality
- heavy local setup friction

It also avoids over-engineering:
- no mandatory Qdrant for local runs
- no GraphRAG for a 48-page manual
- no unnecessary multi-service local infrastructure

---

## High-Level Architecture

```text
+----------------------------------------------------------------------------------+
|                                   FRONTEND                                       |
|----------------------------------------------------------------------------------|
| Next.js                                                                          |
| - Chat pane                                                                      |
| - Artifact pane                                                                  |
| - Evidence pane                                                                  |
| - Source viewer                                                                  |
| - Highlight overlays                                                             |
| - Image upload for weld/machine photos                                           |
+-----------------------------------------+----------------------------------------+
                                          |
                                          | HTTPS / SSE
                                          v
+----------------------------------------------------------------------------------+
|                                 BACKEND API                                      |
|----------------------------------------------------------------------------------|
| FastAPI                                                                          |
| - Chat streaming endpoint                                                        |
| - Session endpoint                                                               |
| - Evidence/source endpoints                                                      |
| - Image/page/crop endpoints                                                      |
| - Ingest/admin/eval endpoints                                                    |
+-----------------------------------------+----------------------------------------+
                                          |
                                          v
+----------------------------------------------------------------------------------+
|                              AGENT ORCHESTRATION                                 |
|----------------------------------------------------------------------------------|
| Claude Agent SDK                                                                 |
| - tool-use loop                                                                  |
| - clarification gate                                                             |
| - query routing                                                                  |
| - retrieval orchestration                                                        |
| - grounded synthesis                                                             |
| - artifact planning                                                              |
| - session updates                                                                |
+-------------------+------------------------+------------------------+-------------+
                    |                        |                        |
                    v                        v                        v
     +---------------------------+  +-----------------------+  +-------------------+
     | Retrieval Engine          |  | Artifact Planner      |  | Session Manager   |
     | - exact-data routing      |  | - typed specs         |  | - process         |
     | - hybrid search           |  | - source refs         |  | - voltage         |
     | - rerank                  |  | - UI-safe outputs     |  | - material        |
     | - compression             |  |                       |  | - setup state     |
     +-------------+-------------+  +-----------+-----------+  +-------------------+
                   |                            |
                   v                            v
+----------------------------------------------------------------------------------+
|                              KNOWLEDGE + EVIDENCE                                |
|----------------------------------------------------------------------------------|
| Structured facts + evidence objects                                              |
| - text blocks                                                                    |
| - tables                                                                         |
| - figures                                                                        |
| - page regions                                                                   |
| - crops                                                                          |
| - exactness labels                                                               |
| - FTS / vectors                                                                  |
+-------------------+----------------------------------------+---------------------+
                    |                                        |
                    v                                        v
     +-------------------------------+         +----------------------------------+
     | Data Store                    |         | Asset Store                      |
     | Local: SQLite + FTS5          |         | Local: filesystem               |
     | Prod: Postgres + pgvector     |         | Prod: object storage            |
     +-------------------------------+         +----------------------------------+
                    ^
                    |
+-------------------+----------------------------------------------------------------+
|                               INGESTION LAYER                                       |
|-------------------------------------------------------------------------------------|
| Source PDFs / images                                                                 |
| - source registration                                                                |
| - page rendering                                                                     |
| - structured extraction                                                              |
| - chunking / indexing                                                                |
| - crop generation                                                                    |
| - optional vision pre-cache                                                          |
| - eval fixture generation                                                            |
+-------------------------------------------------------------------------------------+
```

---

## Final Retrieval Strategy

This is the merged retrieval strategy and should be treated as canonical.

### Path 1: Exact-data path
Used for:
- duty cycle
- polarity
- specifications
- settings
- troubleshooting matrix
- safety warnings

Implementation:
- query classifier routes to structured tools first
- tool returns exact values from verified structured data
- deterministic validation checks that the proposed answer matches the stored answer

### Path 2: Full-context path
Used for:
- broad manual questions
- explanatory questions
- cross-section questions
- questions where manual-wide recall matters more than narrow lookup

Implementation:
- provide the full manual context to Claude with prompt caching
- keep citations enabled
- still route exact factual claims to structured tools first
- still return evidence payloads and grounded artifacts

This is the primary broad-question path for this challenge corpus.

### Path 3: Hybrid retrieval path
Used for:
- explanatory questions
- setup walkthroughs
- cross-page questions
- “how/why” questions

Implementation:
- FTS/BM25-style search
- optional vector retrieval
- weighted fusion
- reranking
- sentence-level compression

### Path 4: Visual retrieval path
Used for:
- diagrams
- control panels
- wire feed mechanism
- weld diagnosis images
- page-layout-dependent answers

Implementation:
- page image retrieval
- figure crop retrieval
- optional vision pre-cache on high-value pages
- evidence payload includes page, region, crop, and exactness

## Final Evidence Model

This is one of the most important differentiators and should not be weakened.

Every answer should be backed by evidence objects such as:
- `TextBlockEvidence`
- `TableEvidence`
- `FigureEvidence`
- `PageRegionEvidence`
- `StructuredFactEvidence`

Minimum evidence fields:
- `document`
- `page`
- `type`
- `bbox`
- `cropUrl`
- `exactness`
- `confidence`
- `sourceRefs`

Representative payload:

```json
{
  "answer": "For TIG on this machine, connect the torch to the negative output and the ground clamp to the positive output.",
  "citations": [
    {
      "document": "owner-manual",
      "page": 18,
      "type": "page_region",
      "bbox": [72, 166, 452, 518],
      "cropUrl": "/assets/crops/owner-manual-p18-polarity.png",
      "exactness": "native_pdf",
      "sourceRefs": [{ "page": 18, "description": "TIG polarity setup diagram" }]
    }
  ],
  "artifact": {
    "type": "diagram",
    "renderer": "react-svg",
    "spec": {
      "diagramKind": "polarity_setup",
      "process": "tig"
    }
  }
}
```

### Exactness policy

Two exactness classes are required:
- `native_pdf`
- `vision_ocr`

This distinction must be visible in both backend metadata and frontend rendering.

---

## Final Tool Strategy

The final architecture should use a concrete tool catalog, not only abstract “classification → retrieval → synthesis.”

Canonical tool families:
- `search_manual`
- `get_page_image`
- `lookup_specifications`
- `lookup_duty_cycle`
- `lookup_polarity`
- `lookup_troubleshooting`
- `lookup_settings`
- `lookup_safety_warnings`
- `diagnose_weld`
- `render_artifact`
- `clarify_question`

### Tool design rules
- use enums wherever possible
- return structured payloads, not prose blobs
- require `sourceRefs` / `source_pages` on artifact generation
- cache deterministic tool results safely
- allow parallel tool execution where results are independent

---

## Final System Prompt Specification

The system prompt is one of the most important files in the project and should be treated as a first-class artifact.

It must include:
- expert welding technician persona
- patient, encouraging, safety-conscious tone
- explicit instruction to use tools for factual claims
- explicit instruction never to guess exact technical values
- explicit instruction to ask clarifying questions before unsafe or ambiguous guidance
- artifact mapping rules:
  - `SVG` for polarity and wiring diagrams
  - `Mermaid` for troubleshooting flows
  - `React` for calculators and configurators
  - `HTML/table` for structured comparisons and settings views
- follow-up suggestion format
- session-context injection template
- safety warning rules
- citation and source-linking rules

### Diagram visual language
Use consistent wiring colors across polarity/setup diagrams:
- positive: `#e74c3c`
- negative: `#3498db`
- neutral/dark panel background: `#1a1a2e`

This consistency improves trust and legibility.

---

## Final Artifact Strategy

Artifacts are mandatory for this challenge, not optional decoration.

Supported artifact types:
- `diagram`
- `calculator`
- `configurator`
- `flowchart`
- `comparison-table`
- `step-guide`
- `annotated-image`

Rendering choices:
- `React` for interactive widgets
- `SVG` for precise wiring and technical diagrams
- `Mermaid` for simpler procedural flows
- `HTML` when richer self-contained displays are best

### Required artifact grounding
Every artifact must include:
- source pages
- evidence references
- safe/typed spec for rendering

### Required artifact streaming behavior
- never render incomplete artifacts mid-stream
- detect incomplete artifact blocks during streaming and show a placeholder such as `Generating diagram...`
- only render the final artifact once the block is structurally complete

This is a proven UX pattern and avoids broken HTML/SVG during SSE streaming.

---

## Final UX Requirements

These are not optional polish details; they materially improve evaluator understanding and real usability.

### Welcome state
The first screen should include:
- short welcome copy
- quick actions such as:
  - `Set up MIG`
  - `Set up TIG`
  - `Troubleshoot`
  - `View Specs`

### Follow-up suggestions
After each answer, show 2-3 contextual follow-up actions or chips generated in a parseable format by the model.

### Source cards
Source cards should:
- show a page thumbnail or crop preview
- show page number and evidence type
- link to the source viewer
- link back to related artifacts where possible

### Mobile and theme requirements
- dark mode should be the default
- the app must remain usable on mobile or narrow screens
- the split-pane desktop design should gracefully collapse for phones

These requirements align with a real garage-side usage context.

---

## Final Session Strategy

Session state should be first-class, not vague “memory.”

Track:
- selected process
- input voltage
- material
- thickness
- wire diameter
- setup steps completed
- safety warnings already shown
- recent cited pages

This helps:
- clarify questions better
- avoid repeated safety warnings
- generate more useful artifacts
- feel like a practical garage-side assistant

---

## Final Input/Output Multimodality

### Inputs
- text questions
- image upload for weld diagnosis or machine setup questions

### Outputs
- grounded text
- cited page previews
- figure crops
- generated diagrams
- calculators/configurators
- troubleshooting flows

This must be real end-to-end multimodality, not only “manual image surfacing.”

---

## Final Validation Policy

For any answer involving exact technical values:
- do not trust model prose alone
- validate against structured data
- reject or correct mismatches before the final answer is emitted

Validation is required for:
- duty cycle
- polarity
- exact settings tables
- specification lookups
- any future hard constraints

---

## Final Local vs Production Story

### Local default
- no Docker required
- SQLite local mode
- filesystem assets
- one `.env`
- frontend + backend processes only

### Optional local Docker
- allowed, but not required
- helpful for full-stack parity or deployment rehearsal

### Production
- Postgres + pgvector
- object storage
- background jobs for ingestion
- hosted frontend and backend

This is the strongest evaluator experience while still demonstrating production thinking.

---

## Final Caching Policy

Caching in this challenge should be pragmatic, not infrastructure-heavy.

### Keep
- precomputed document assets:
  - page PNGs
  - crops
  - structured JSON
  - optional vision summaries
- prompt caching for full-context mode
- small safe caches for deterministic tool outputs

### Do not prioritize
- full response replay caches
- distributed cache systems
- multi-user cache infrastructure

This project is not optimizing for massive repeated-user traffic. The valuable caches are document and prompt caches, not generic answer caching.

---

## Structured Data Access Policy

For read-only exact-data domains such as:
- duty cycles
- polarity
- specifications
- troubleshooting
- safety

use verified JSON loaded into memory as Python dicts.

Use database/ORM-backed storage only where it adds real value:
- FTS and optional vectors
- evidence index
- sessions
- metadata and production persistence

This keeps exact lookups simple, fast, and reliable.

---

## Final Parsing Decision

Primary parser:
- `PyMuPDF`

Optional enhancement:
- `Docling`

Reason:
- PyMuPDF is simpler and sufficient for this digital manual
- Docling remains useful if we later need more sophisticated layout recovery across varied document types

So the final v1 decision is:
- **PyMuPDF-first**
- **Docling-optional**

---

## Final Differentiators

This final architecture should outperform most submissions because it combines:
- strict exact-data validation
- stronger evidence grounding
- real multimodal input/output
- artifact-first responses
- low-friction local setup
- production-aware storage design
- optional full-context mode
- reusable document-pack structure

---

## Final Borrow / Avoid / Outperform

| Area | Borrow | Avoid | Outperform |
|---|---|---|---|
| Setup | precomputed assets, obvious quickstart | Docker-required local flow | zero-infra local run with production path |
| Retrieval | hybrid search, reranking, compression | one-method retrieval | evidence-aware hybrid + exact-data routing |
| Grounding | source cards, source viewer, highlights | page-number-only citations | region-level evidence with exactness |
| Artifacts | typed specs, streaming-safe rendering | raw unvalidated generated markup | source-backed diagrams and widgets |
| Accuracy | deterministic tools, validation | prompt-only truthfulness | exact-data routing + validation |
| Multimodality | manual image surfacing, visual retrieval | fake image support claims | true text + image input and output |
| Architecture | strong separation of concerns | monolithic shortcuts that block scale | reusable document-pack platform |

---

## Final Recommendation

This is the final merged direction:

- keep the evidence-first, low-friction, SQLite-local architecture
- adopt the alternate proposal’s stronger tool design, retrieval shaping, and full-context option
- keep deterministic validation
- keep region-level evidence
- keep local simplicity as a hard requirement
- move full-context mode earlier in implementation
- require explicit prompt and UX standards from day one

This gives us the strongest combined architecture to take into implementation and final review.
