# ProductManualQnA - Architecture & Status

**Last updated: 2026-04-11**

## What This Project Is

A **generic product manual Q&A platform** where users upload PDF manuals for any product and get an AI assistant that answers questions with exact data, diagrams, and page references.

Originally built for the Prox Founding Engineer Challenge ($200k + 1% equity) around the Vulcan OmniPro 220 welding manual, now architected as a **general-purpose platform** that works with any product manual.

## Tech Stack

- **Frontend:** Next.js 15 + TypeScript + React + Tailwind CSS v4
- **Backend:** Python + FastAPI + Claude Agent SDK
- **Database:** SQLite with FTS5 (full-text search) + sqlite-vec (vector search)
- **OCR/Vision:** Anthropic Claude Vision API (client SDK, with prompt caching)
- **Embeddings:** sentence-transformers local model (all-MiniLM-L6-v2, 384 dims)
- **Agent:** Claude Agent SDK with MCP tools, streaming SSE to frontend

## Architecture Overview

```
User uploads PDF
    |
    v
[Stage 1: Render] PyMuPDF -> page PNGs (local, instant)
    |
    v
[Stage 2: OCR] Each page PNG -> Claude Vision -> summary + detailed_text + keywords
    - Prompt caching: static system prompt cached, saves ~90% on pages 2+
    - Retry: 2 attempts per page on failure
    - JSON quote fixer for unescaped inner quotes
    - Extracts: text, tables (markdown), image descriptions, TOC detection
    |
    v
[Stage 3: Embed] detailed_text -> sentence-transformers -> 384-dim vector
    - Local model, zero API cost
    - Stored as BLOB in page_embeddings + vec0 table for native search
    |
    v
Status per page in DB: pending -> ocr -> done
All data in SQLite. Agent queries via tools at chat time.
```

## Database Schema (SQLite)

```sql
-- Product metadata
products (id, name, description, domain, status, ...)
categories (product_id, name)
sources (product_id, source_id, filename, path, processing_status, pages, ...)
quick_actions (product_id, label, message)

-- Page intelligence (from ingestion)
page_analysis (product_id, source_id, page, filename, summary, detailed_text, keywords, is_toc, processing_status)
page_embeddings (product_id, source_id, page, embedding BLOB)
page_vec (embedding float[384])  -- sqlite-vec virtual table for native vector search
toc_entries (product_id, source_id, title, start_page, end_page, level)

-- FTS5 virtual table (auto-indexed from page_analysis)
page_fts (summary, detailed_text, keywords)
```

## Folder Structure

```
data/
  products/<product-id>/
    pack.yaml
    files/              # Uploaded PDFs + logo
    assets/pages/       # Rendered page PNGs per source
      <source-id>/
        page_01.png ...
  local.db              # SQLite database
```

## What Is COMPLETE And Working

### Product Platform UI
- [x] Product dashboard (create, edit, delete products)
- [x] Categories (up to 3 tags)
- [x] File upload (immediate to backend, per-file tracking)
- [x] File delete with cascade cleanup
- [x] Edit dialog with inline file management + existing docs shown
- [x] SQLite database with full CRUD
- [x] Dark mode, mobile responsive

### Ingestion Pipeline (TESTED, WORKING)
- [x] Stage 1: PDF page rendering (PyMuPDF -> PNG)
- [x] Stage 2: Claude Vision OCR with prompt caching + 2x retry + JSON quote fixer
- [x] Stage 3: Embedding generation (sentence-transformers, local)
- [x] Per-page status tracking (pending -> ocr -> done)
- [x] Background job with per-document locks
- [x] Auto-trigger on file upload
- [x] Console logging per step per page
- [x] File logging to data/server.log
- [x] Successfully processed: Vulcan OmniPro 220 (48 pages), Quick Start Guide (2 pages), Selection Chart (1 page) = 51 pages total

### Chat UI (built, needs agent wiring)
- [x] SSE streaming from Agent SDK
- [x] Inline artifacts (Mermaid, SVG, HTML)
- [x] Follow-up suggestions, image upload, chat history
- [x] Source viewer sidebar, copy button, tool calls

### Agent Tools (code written, NOT yet wired to search data)
- [x] search_manual - calls db.search_pages_fts() but hybrid search not implemented
- [x] get_page_text - calls db.get_page_detailed_text()
- [x] get_page_image - returns page PNG URL
- [x] clarify_question - asks user for clarification
- [x] MCP wrappers registered

### Database Functions Ready
- [x] `db.search_pages_fts(product_id, query)` - FTS5 keyword search
- [x] `db.search_by_embedding(product_id, query_blob)` - sqlite-vec vector search
- [x] `db.get_all_page_summaries(product_id)` - for document map
- [x] `db.get_toc(product_id)` - for TOC injection
- [x] `db.get_page_detailed_text(product_id, source_id, pages)` - for agent reads

---

## What NEEDS To Be Done (in order of priority)

### 1. Wire Hybrid Search Into search_manual Tool
**File:** `backend/app/agent/tools.py` -> `execute_tool("search_manual", ...)`

Currently just calls `db.search_pages_fts()`. Needs to:
- Embed user query using `embed_text()` from `build_embeddings.py`
- Run FTS5 search: `db.search_pages_fts(product_id, query)`
- Run vector search: `db.search_by_embedding(product_id, query_embedding)`
- Merge results with weighted scoring: `0.5 * embedding_score + 0.3 * fts5_score + 0.2 * keyword_bonus`
- Deduplicate by (source_id, page)
- Return top 5-8 results with summary + source_id + page

### 2. Build Document Map For System Prompt
**File:** `backend/app/agent/prompts.py`

The agent needs to know what the manual contains BEFORE any tool calls. Inject into system prompt:
- TOC entries (from `db.get_toc(product_id)`)
- All page summaries (from `db.get_all_page_summaries(product_id)`)
- This is the "document map" - agent reads it and decides which tools to call

Format example in system prompt:
```
## Document Map

### Table of Contents (Owner Manual)
Safety ... pages 2-6
Specifications ... page 7
Controls ... pages 8-9
MIG/Flux-Cored Wire Welding ... pages 10-23
...

### Page Summaries
[owner-manual] Page 1: Cover page with product name...
[owner-manual] Page 2: Table of Contents + safety warnings...
[owner-manual] Page 7: Specifications table for all processes...
...
```

### 3. Rewrite System Prompt (Generic)
**File:** `backend/app/agent/prompts.py`

Current prompt is welding-specific. Needs to be generic:
- "You are a product manual Q&A assistant"
- "Use search_manual to find relevant pages"
- "Use get_page_text for detailed content"
- "Use get_page_image to show diagrams/tables"
- "Always cite source document and page number"
- "If unsure, use clarify_question"
- Inject document map (from step 2)
- Inject product description and name

### 4. Wire Orchestrator To Pass Product Context
**File:** `backend/app/agent/orchestrator.py`

The orchestrator builds the system prompt and passes it to the Agent SDK. It needs to:
- Load product runtime for the active product
- Build system prompt with document map
- Pass to Agent SDK via `ClaudeAgentOptions.system_prompt`

### 5. Test Full Chat Flow
- User asks "What is the duty cycle for MIG at 120V?"
- Agent gets document map in system prompt
- Agent calls search_manual("duty cycle MIG 120V")
- Hybrid search returns page 7 (specs) as top result
- Agent calls get_page_text("owner-manual", [7]) for details
- Agent answers with exact values + citation

### 6. Optional Enhancements (after core works)
- Intent-aware score boosting (keyword matching on query intent)
- Product-level custom system prompt (user-editable in product settings)
- Session memory (track what user is working on)
- Knowledge graph extraction during ingestion
- Deployment (Railway + Vercel)

---

## Key Files

### Backend Core
- `app/main.py` - 3 lines, delegates to bootstrap
- `app/core/bootstrap.py` - app factory, lifespan, logging, CORS
- `app/core/database.py` - SQLite schema, CRUD, FTS5, sqlite-vec, migrations
- `app/core/config.py` - settings, paths

### Product Management
- `app/packs/models.py` - ProductManifest, ProductRuntime
- `app/packs/registry.py` - product registry, file ops
- `app/api/products.py` - REST API (CRUD, upload, delete, PATCH, assets)

### Ingestion Pipeline
- `app/ingest/pipeline.py` - 3-stage per-page orchestrator with console logging
- `app/ingest/render_pages.py` - PDF to PNG
- `app/ingest/ocr_vision.py` - Claude Vision OCR with prompt caching + retry + JSON fixer
- `app/ingest/build_embeddings.py` - sentence-transformers local embeddings
- `app/ingest/jobs.py` - background job management

### Agent (NEEDS WIRING)
- `app/agent/orchestrator.py` - Agent SDK runtime, SSE event mapping
- `app/agent/tools.py` - 4 generic tools (search, get_text, get_image, clarify)
- `app/agent/tools_mcp.py` - MCP wrappers
- `app/agent/prompts.py` - system prompt (NEEDS document map injection)

### Frontend
- `frontend/src/app/page.tsx` - product dashboard
- `frontend/src/app/products/[productId]/page.tsx` - product workspace
- `frontend/src/components/products/` - dashboard, workspace, create/edit dialog
- `frontend/src/components/chat/` - message bubble, input, welcome screen
- `frontend/src/components/artifacts/` - Mermaid, SVG, HTML viewers
- `frontend/src/lib/api.ts` - backend API client
- `frontend/src/lib/use-chat.ts` - chat hook with SSE streaming

## Design Decisions

1. **SQLite for everything** - single file, zero setup, FTS5 + sqlite-vec built in
2. **Claude Vision OCR over PyMuPDF text** - better quality for tables, images, layout
3. **Document map approach** - agent gets page summaries + TOC always, decides which pages to read
4. **Agent SDK for chat, client API for OCR** - right tool for each job
5. **Local embeddings** - sentence-transformers, no API cost for search
6. **Per-page status tracking** - know exactly what succeeded/failed
7. **Prompt caching on OCR** - static system prompt cached across all pages
8. **sqlite-vec for vector search** - native SQL, no Python loops
9. **JSON quote fixer** - handles LLM producing unescaped quotes in string values
