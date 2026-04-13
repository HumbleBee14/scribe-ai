# Prox - ProductManualQnA Platform

> Turn any manual into a smart agent.

A production-grade multimodal reasoning platform that transforms product manuals into AI-powered Q&A assistants. Upload any PDF manual, and the system builds a knowledge base that answers questions with exact data, visual references, and page citations.

Built for the Prox Founding Engineer Challenge using the **Claude Agent SDK**.

**Live demo:** [prox.dineshyadav.com](https://prox.dineshyadav.com)

---

## Quick Start (< 2 minutes)

```bash
git clone <repo-url>
cd multimodal-prox-challenge
cp .env.example .env          # Add your ANTHROPIC_API_KEY
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.cargo/bin:$PATH"
make                           # Installs everything + starts backend
# OR (once installation setup done), start Backend:
make backend

# In another terminal, start Frontend:
make frontend                  # Starts Next.js on localhost:3000
```

The Vulcan OmniPro 220 manual comes pre-ingested with all 51 pages analyzed. Open `localhost:3000` and start chatting immediately.

---

## Architecture Overview

```
                                    +------------------+
                                    |   Next.js UI     |
                                    |  (SSE streaming)  |
                                    +--------+---------+
                                             |
                                    +--------v---------+
                                    |   FastAPI Backend |
                                    +--------+---------+
                                             |
                         +-------------------+-------------------+
                         |                                       |
              +----------v----------+                 +----------v----------+
              |  Claude Agent SDK   |                 |  Ingestion Pipeline |
              |  (reasoning loop)   |                 |  (one-time per doc) |
              +----------+----------+                 +----------+----------+
                         |                                       |
              +----------v----------+              Stage 1: Render (PyMuPDF)
              |    MCP Tool Server  |              Stage 2: OCR (Claude Vision)
              |  search_manual      |              Stage 3: Embed (MiniLM)
              |  get_page_text      |                        |
              |  get_page_image     |              +---------v---------+
              |  calculate          |              |     SQLite DB     |
              |  clarify_question   |              |  FTS5 + sqlite-vec|
              |  update_memory      |              +-------------------+
              +---------------------+
```

---

## How It Works: The Full Pipeline

### Phase 1: Document Ingestion

When a user uploads a PDF manual, it goes through a 3-stage pipeline. Each page is processed independently, so failures on one page don't block others.

```
PDF uploaded
  |
  v
+------------------------------------------+
| Stage 1: RENDER (local, ~2s for 48 pages)|
|  PyMuPDF converts each page to PNG       |
|  at 200 DPI. Stored on disk.             |
|  Status: pending                         |
+--------------------+---------------------+
                     |
                     v
+------------------------------------------+
| Stage 2: OCR (Claude Vision API)         |
|  Each page PNG sent to Claude Sonnet     |
|  with a detailed extraction prompt.      |
|                                          |
|  Extracts per page:                      |
|    - summary (2-3 sentences)             |
|    - detailed_text (full content)        |
|    - keywords (searchable terms)         |
|    - is_toc (table of contents flag)     |
|                                          |
|  Prompt caching: static system prompt    |
|  cached after page 1, ~90% savings on    |
|  pages 2+.                               |
|                                          |
|  Tables -> markdown format               |
|  Images -> detailed descriptions         |
|  Steps -> exact numbering preserved      |
|  Warnings -> level + full text           |
|                                          |
|  Status: ocr                             |
+--------------------+---------------------+
                     |
                     v
+------------------------------------------+
| Stage 3: EMBED (local, ~5s total)        |
|  sentence-transformers (MiniLM-L6-v2)    |
|  generates 384-dim vector per page.      |
|  Stored in SQLite via sqlite-vec.        |
|  Status: done                            |
+------------------------------------------+
```

**Why Claude Vision OCR instead of text extraction?**

PyMuPDF text extraction fails on complex layouts: multi-column pages, text overlapping images, tables with merged cells. Claude Vision sees the page as a human would and extracts content accurately, including describing diagrams and converting tables to clean markdown. The one-time API cost (~$1 for a 48-page manual) is worth the accuracy gain.

**Why page-level granularity?**

Each page in a product manual is typically a self-contained topic (a spec table, a procedure section, a diagram). Page-level chunking preserves this natural structure. The OCR summary tells the agent what each page contains, the detailed_text gives full content, and keywords enable search.

### Phase 2: Knowledge Storage

Everything lives in a single SQLite database file (`data/local.db`):

| Table | Purpose |
|-------|---------|
| `products` | Product profiles (name, description, status) |
| `categories` | Product tags (up to 3) |
| `sources` | Uploaded PDF files with per-source processing status |
| `page_analysis` | OCR results: summary, detailed_text, keywords, is_toc per page |
| `page_embeddings` | 384-dim float vectors per page (for semantic search) |
| `page_vec` | sqlite-vec virtual table for native vector similarity |
| `page_fts` | FTS5 virtual table for BM25 keyword search |
| `toc_entries` | Extracted table of contents with section -> page mapping |
| `memories` | Per-product user preferences (persisted across sessions) |
| `conversations` | Chat history with full message persistence |
| `quick_actions` | Preset questions shown on the welcome screen |

**Why SQLite?**

Single file, zero infrastructure, committed to git. Evaluators clone and run -- no database setup, no migrations, no Docker. FTS5 and sqlite-vec are built-in extensions that give us BM25 ranking and vector similarity search without external services.

### Phase 3: Query-Time Retrieval

When a user asks a question, the system runs a hybrid search pipeline BEFORE the agent starts, injecting relevant page content into the system prompt:

```
User query: "What's the duty cycle for MIG at 240V?"
                     |
         +-----------+-----------+
         |                       |
+--------v--------+    +--------v--------+
| FTS5 Keyword    |    | Vector Semantic |
| Search (BM25)   |    | Search          |
|                 |    | (sqlite-vec)    |
| Weighted columns|    |                 |
| keywords: 5x    |    | Embed query     |
| summary:  3x    |    | with MiniLM     |
| text:     1x    |    | L2 distance     |
+---------+-------+    +--------+--------+
          |                      |
          +----------+-----------+
                     |
              +------v------+
              | Hybrid Merge|
              |             |
              | FTS: 0-0.50 |
              | Vec: 0-0.50 |
              | Combined    |
              +------+------+
                     |
              +------v---------+
              | Cross-Encoder  |
              | Reranking      |
              |                |
              | ms-marco-      |
              | MiniLM-L-6-v2  |
              | Scores each    |
              | (query, page)  |
              | pair together  |
              +------+---------+
                     |
              +------v-------+
              | Qualification|
              | Filter       |
              |              |
              |Path A: strong|
              |   semantic   |
              |   alone      |
              | Path B: both |
              |   signals    |
              |   required   |
              +------+-------+
                     |
              +------v------+
              | Score thresh|
              | >= 0.52     |
              | Max 3 pages |
              +------+------+
                     |
                     v
        Top 3 pages full detailed_text
        injected into system prompt
```

**Why this 4-layer pipeline?**

- **FTS5/BM25** catches exact keyword matches: "duty cycle", "240V", "MIG"
- **Embedding search** catches semantic meaning: "my welder keeps stopping" matches "thermal protection shutdown"
- **Cross-encoder reranking** scores each (query, page) pair together for precision -- unlike bi-encoders that encode query and document separately, the cross-encoder sees both simultaneously and produces a more accurate relevance score
- **Qualification filter** requires either strong semantic match alone or both signals together, preventing weak single-signal results from polluting context

### Phase 4: Agent Reasoning Loop

The Claude Agent SDK manages the reasoning loop. The agent receives:

1. **System prompt** with generic instructions
2. **Product info** (name, description)
3. **Document map** -- TOC entries + one-line summary per page (the agent's "table of contents" for the entire manual)
4. **Retrieved context** -- full detailed_text of top 3 most relevant pages (from hybrid search)
5. **Tool definitions** -- 6 MCP tools registered via the SDK

```
Agent receives system prompt + document map + retrieved context
                     |
                     v
            Does retrieved context
            answer the question?
           /                    \
         YES                     NO
          |                       |
    Answer directly          Use tools to
    with citations           gather more
          |                       |
          |              +--------+--------+
          |              |                 |
          |     search_manual        get_page_text
          |     (rephrase +          (specific pages
          |      re-search)          from doc map)
          |              |                 |
          |              +--------+--------+
          |                       |
          |                Need visual?
          |                /           \
          |              YES            NO
          |               |              |
          |        get_page_image   Answer with
          |        (shows to user   text citations
          |         + agent sees)
          |               |
          +------+--------+
                 |
          Generate response
          with citations +
          optional artifacts
          (HTML/Mermaid/SVG)
```

**Key design decision: Document map as the agent's index**

Instead of sending the entire manual or relying solely on search, we send a one-line summary of every page. This gives the agent a "table of contents on steroids" -- it knows what page 7 contains (specifications), what page 23 contains (duty cycle table), what page 45 contains (wiring schematic). The agent uses this to make informed decisions about which pages to read, without us having to predict what it needs.

### Phase 5: Response Delivery

Responses stream to the frontend via SSE (Server-Sent Events):

- **text_delta** -- streamed text tokens
- **tool_start/tool_end** -- shows which tools the agent is using
- **image** -- inline page image from the manual
- **clarification** -- interactive clarification card with clickable options
- **done** -- completion with token usage stats

**Inline artifacts** are detected by parsing `<artifact>` tags from the agent's text response:
- `type="html"` -- rendered in a sandboxed iframe (calculators, comparison tables)
- `type="mermaid"` -- rendered via Mermaid.js in a sandboxed iframe (flowcharts, decision trees)
- `type="svg"` -- rendered directly (diagrams, schematics)

---

## Design Decisions

### 1. Product/Document agnostic platform

The entire system is product-agnostic. The Vulcan OmniPro 220 is the first product example seeded, but the same platform handles any PDF manual. No hardcoded product logic anywhere, works flawlessly with any documents:
- System prompt is generic
- Tools are generic (search, read, show, calculate, clarify, remember)
- Ingestion pipeline works on any PDF
- OCR prompt extracts content without domain assumptions

### 2. Vision-guided OCR over text extraction

We send each page as an image to Claude Vision rather than extracting text with PyMuPDF. This costs more but produces dramatically better results for pages with:
- Complex table layouts (specification matrices, troubleshooting grids)
- Diagrams with labels (wiring schematics, assembly drawings)
- Mixed text/image content (step-by-step procedures with illustrations)
- Multi-column layouts

### 3. SQLite for everything

One file, zero setup. FTS5 for keyword search, sqlite-vec for vector search, regular tables for metadata. Committed to git so evaluators get a pre-built knowledge base. No Docker, no external databases.

### 4. Hybrid retrieval with qualification filtering

Neither keyword search nor semantic search alone is sufficient:
- "duty cycle MIG 240V" needs exact keyword matching
- "my welder keeps shutting off" needs semantic understanding

Our hybrid pipeline merges both signals with a qualification filter that requires either strong semantic match alone or both signals together, preventing weak results from polluting the agent's context.

### 5. Safe calculator to prevent hallucinated math

LLMs are notoriously unreliable at arithmetic. When a user asks "If duty cycle is 30% at 175A, how long can I weld in 10 minutes?", the agent should not guess -- it should compute. The `calculate` tool uses Python's AST module to safely evaluate math expressions without `eval()`. Only whitelisted operations (arithmetic, sqrt, trig, log, round, etc.) are allowed. No code injection possible.

This ensures the agent never interpolates or hallucinates numerical values. It either finds the exact value in the manual, or computes it deterministically with the calculator.

### 6. Persistent user memory

The agent can learn and remember user preferences across conversations via the `update_memory` tool:

- **Agent adds automatically** -- if the user mentions "I'm a beginner" or "I usually work with 240V", the agent saves it without being asked
- **User adds manually** -- the sidebar has a Preferences section where users can type and add their own context
- **Agent or user can delete** -- outdated preferences are removable from either side
- **Max 6 per product** -- keeps context focused, auto-evicts oldest if full
- **Injected every conversation** -- memories are loaded from the database and included in the system prompt, so the agent personalizes from the first message

This means the agent gets better over time. A returning user doesn't need to re-explain their setup, experience level, or typical use case.

### 7. Multi-page reasoning across independent sources

Complex questions often span multiple manual sections. The agent handles this naturally:

- The document map shows what every page contains across all uploaded documents
- The agent makes multiple independent tool calls to gather pieces from different pages
- For "Walk me through MIG setup" -- it fetches pages 10-14 (wire setup), page 8 (controls), and page 14 (polarity), then synthesizes a complete walkthrough
- For "Compare MIG vs TIG specs" -- it fetches the MIG specs page and the TIG specs page independently, then builds a comparison table as an HTML artifact
- Each tool call is independent -- fetching page 7 doesn't affect fetching page 24

The agent doesn't need us to pre-select pages or build a context window. It reads the document map, identifies which pages it needs, fetches them, and combines the information.

### 8. Dynamic interactive artifacts

The agent proactively generates interactive visual content when it helps understanding:

- **HTML artifacts** -- duty cycle calculators, settings configurators, specification comparison tables with styled headers and interactive elements
- **Mermaid flowcharts** -- troubleshooting decision trees, setup procedure flows, process selection guides
- **SVG diagrams** -- connection diagrams, layout illustrations

Artifacts are rendered inline in the chat in sandboxed iframes. Users can expand them to full screen. The agent decides when a visual would explain better than text -- it's not forced to generate artifacts on every response, only when the answer genuinely benefits from visual representation.

### 9. Custom system prompts per product

Each product workspace has an optional custom system prompt field. Users can add product-specific instructions:

- "Always mention safety warnings before any procedure"
- "This user base is primarily beginners, explain terms simply"
- "When discussing settings, always include the recommended range from the manual"

If set, the custom prompt is appended to the default generic instructions. The document map, tools, and retrieval context are always included regardless. This lets users tune the agent's behavior for their specific product without modifying code.

### 10. Web search for external knowledge

The agent has access to WebSearch (built into the Agent SDK) for questions that go beyond the manual:

- "Is this welder compatible with a 30A breaker?" -- manual may not cover electrical compatibility
- "What's the best argon mix for aluminum?" -- general industry knowledge
- "Where can I buy replacement tips?" -- availability, pricing

The system prompt enforces strict guardrails: the manual is always the source of truth for product specifications, procedures, and safety. Web search is only used when the documents genuinely don't cover the topic. When web results are used, the agent explicitly cites them as external sources.

### 11. Agent decides, not us

We inject the document map and initial context, but the agent decides what to do:
- If the context answers the question, it responds directly (no unnecessary tool calls)
- If it needs more, it calls search_manual with rephrased terms
- If it needs visuals, it calls get_page_image (which shows to the user AND the agent sees it too for visual analysis)
- If the question is ambiguous, it asks for clarification
- If the question requires math, it uses the safe calculator tool
- If the manual doesn't cover the topic, it can search the web

We don't build a rigid pipeline -- we give the agent the right tools and let it reason.

---

## Tools

| Tool | Purpose |
|------|---------|
| `search_manual` | Hybrid FTS5 + vector search across all pages. Returns ranked summaries. |
| `get_page_text` | Full detailed text for specific pages (max 5 per call). |
| `get_page_image` | Shows page PNG to user AND delivers base64 to agent for visual analysis. |
| `calculate` | Safe math evaluator (AST-based, no eval). Prevents hallucinated math -- agent computes exact values instead of guessing. |
| `clarify_question` | Asks user for more info with optional clickable choices. |
| `update_memory` | Persists user preferences across conversations (max 6 per product). |

Plus built-in Agent SDK tools:
- **Read** -- agent can read any file, including page images for vision analysis
- **WebSearch** -- for questions outside the manual's scope (used sparingly)

---

## Frontend Features

- **Product dashboard** -- create, edit, delete product workspaces with categories, logo, and custom system prompt
- **Real-time tool transparency** -- users see what the agent is doing as it works: "Searching manual...", "Read pages 7, 19, 23", "Loaded page 45", "Calculated: 175 * 0.30". Tool calls are collapsible with success/failure indicators
- **Inline artifacts** -- HTML calculators, Mermaid flowcharts, SVG diagrams rendered in-chat with expand-to-fullscreen
- **Manual preview** -- tabbed PDF viewer per document, scrollable, text-selectable, browser-cached
- **Image upload** -- paste from clipboard, file picker, or mobile camera capture. Agent analyzes uploads with Vision and cross-references manual pages
- **Voice mode** -- browser-native STT + TTS with hands-free conversational loop. Per-message replay button. Smart filtering strips emoji, markdown, artifacts for clean speech
- **Chat persistence** -- conversations stored in SQLite with editable titles, survive page reloads
- **User memories** -- persistent preferences in sidebar, editable by user or auto-added by agent

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 15, TypeScript, React, Tailwind CSS v4 |
| Backend | Python, FastAPI, Claude Agent SDK |
| Database | SQLite + FTS5 + sqlite-vec |
| OCR | Claude Vision API (Sonnet 4.6) with prompt caching |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2, local, free) |
| Cross-encoder | ms-marco-MiniLM-L-6-v2 (reranking, local) |
| Vector search | sqlite-vec (native C extension, pip installable) |
| PDF rendering | PyMuPDF |
| Artifacts | Mermaid.js, sandboxed iframes |
| Voice | Web Speech API (browser-native STT + TTS) |

---

## Project Structure

```
multimodal-prox-challenge/
  backend/
    app/
      agent/
        orchestrator.py      # Agent SDK runtime, SSE event mapping
        prompts.py           # System prompt builder with document map
        tools/
          tools.py           # Tool definitions + hybrid search + execution
          tools_mcp.py       # MCP wrappers for Agent SDK
          calculator.py      # Safe AST-based math evaluator
      api/
        chat.py              # SSE streaming chat endpoint
        products.py          # Product CRUD, upload, assets
      core/
        bootstrap.py         # App factory, lifespan, logging
        database.py          # SQLite schema, CRUD, FTS5, sqlite-vec
        config.py            # Settings from .env
      ingest/
        pipeline.py          # 3-stage per-page orchestrator
        ocr_vision.py        # Claude Vision OCR with prompt caching
        build_embeddings.py  # Local sentence-transformers embeddings
        render_pages.py      # PDF to PNG rendering
        jobs.py              # Background job management
      packs/
        registry.py          # Product file management
        models.py            # ProductManifest, ProductRuntime
      session/
        manager.py           # Minimal session for SDK resume
  frontend/
    src/
      app/                   # Next.js pages (dashboard, workspace)
      components/
        chat/                # Message bubble, input, welcome screen
        artifacts/           # Mermaid, SVG, HTML viewers + modal
        products/            # Dashboard, workspace, dialogs
        evidence/            # Source viewer, memories
      lib/
        api.ts               # Backend API client
        use-chat.ts          # SSE streaming hook
        use-voice.ts         # STT + TTS hook
        artifacts.ts         # Artifact tag parser
  data/
    products/                # Product files + page images
    local.db                 # SQLite database (pre-seeded)
```

---

## What Makes This Submission Different

1. **Generic platform** -- not hardcoded to one product. Upload any manual and it works.
2. **Vision-guided OCR** -- Claude Vision reads each page as a human would, not just text extraction.
3. **Hybrid retrieval** -- FTS5 keyword + semantic vector search with qualification filtering.
4. **Document map architecture** -- agent gets a full index of the manual, decides what to read.
5. **Agent autonomy** -- we provide context and tools, the agent reasons about what to do.
6. **Production features** -- voice mode, dark theme, chat persistence, user memories, manual preview.
7. **Zero infrastructure** -- SQLite for everything, single `make` command to run.
