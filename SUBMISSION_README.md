# Vulcan OmniPro 220 Multimodal Agent

A production-grade multimodal reasoning agent for the Vulcan OmniPro 220 welding system built directly on the Claude Agent SDK with an MCP-backed knowledge engine.

## Quickstart

```bash
git clone <repo>
cd multimodal-prox-challenge
cp .env.example .env   # Add your ANTHROPIC_API_KEY
make setup             # Install backend + frontend dependencies
make backend           # Start backend (terminal 1)
make frontend          # Start frontend (terminal 2)
# Open http://localhost:3000
```

Or without Make:

```bash
cd backend && uv venv && uv pip install -e ".[dev]" && uv run python run_server.py
cd frontend && npm install && npm run dev
```

No Docker required. No database to install. SQLite is created automatically.

## What This Agent Does

Ask it anything about the Vulcan OmniPro 220 and it will:

- **Answer with exact data**: duty cycles, polarity setups, specifications. Values come from pre-verified structured JSON, never hallucinated.
- **Draw diagrams**: polarity/wiring diagrams rendered as SVG, troubleshooting flowcharts as Mermaid, comparison tables as interactive HTML.
- **Show manual pages**: references the actual manual with page numbers and images.
- **Diagnose welds**: upload a photo of your weld and get a diagnosis with reference to the manual's weld diagnosis guide.
- **Remember context**: tracks your selected process, voltage, and material across the conversation.
- **Surface safety warnings**: proactively warns about electrical, fire, fume, and arc ray hazards when discussing procedures.
- **Ask for clarification**: when a question is ambiguous (missing process or voltage), asks before guessing.

## Architecture

```
Frontend (Next.js 16)          Backend (Python FastAPI)
+------------------+           +-------------------------------+
| Chat UI          |   SSE     | Claude Agent SDK runtime     |
| Artifact viewers | <-------> | + MCP welding knowledge      |
| Session sidebar  |           | + Built-in Read tool         |
| Image upload     |           | + Streaming event mapper     |
+------------------+           |                               |
                               | Knowledge Engine:            |
                               | - Structured JSON            |
                               | - BM25 retrieval             |
                               | - Validation module          |
                               +-------------------------------+
```

### Runtime Strategy

The backend uses the Claude Agent SDK as the single orchestration runtime. Product-specific capabilities are exposed as MCP tools, and the SDK's built-in `Read` tool handles broader manual access.

Why this design:
- One orchestration stack is easier to reason about, test, and extend.
- MCP tools preserve exact-data lookups and deterministic validation.
- The SDK provides native sessions, partial streaming events, and prompt-caching benefits without maintaining a second custom tool loop.

### Knowledge Engine: Three Retrieval Paths

**Path 1: Exact-data tools** (highest confidence)
- 5 grounded lookup tools backed by verified JSON, plus helper tools for clarification, page images, artifacts, and weld diagnosis routing
- Duty cycles, polarity, specs, troubleshooting, safety warnings
- Deterministic validation compares proposed answers against ground truth
- Zero hallucination risk on critical technical values

**Path 2: BM25 retrieval** (open-ended questions)
- 53 text chunks indexed with BM25Okapi
- Query profile routing (troubleshooting, visual, safety, etc.)
- Section-based score boosting
- Sentence-level compression (~60% token savings)
- Exact-tool precedence enforced: duty cycle/polarity queries redirect to exact tools

**Path 3: Built-in Read access** (broad manual access)
- The Claude Agent SDK reads targeted portions of the owner manual on demand
- Supplements (does not replace) exact-data tools
- Keeps broad-question retrieval inside the same SDK runtime and tool loop

### Artifact System

When text is not enough, the agent generates visual content:

| Type | Renderer | Example |
|------|----------|---------|
| Polarity diagrams | SVG (sandboxed iframe) | Cable connection maps with red=positive, blue=negative |
| Troubleshooting flows | Mermaid | Decision trees for diagnosing weld problems |
| Spec comparisons | HTML (sandboxed iframe) | Interactive comparison tables |
| Settings matrices | HTML | Process/material/thickness recommendations |

All artifacts include source page references linking back to the manual.

### Session Management

The agent tracks conversation context:
- Current welding process (MIG, TIG, Stick, Flux-Cored)
- Input voltage (120V, 240V)
- Material and thickness
- Safety warnings already shown (avoids repeating)
- Setup steps completed

Multi-turn conversations persist bounded chat history in the app session manager.

### Evidence Model

Every answer is backed by typed evidence:
- `document`, `page`, `type` (text_block, table, figure, page_region)
- `bbox` coordinates and `cropUrl` for region-level grounding
- `exactness` label: `native_pdf` or `vision_ocr`

## Design Decisions

### Why Claude Agent SDK as the only runtime?
The challenge explicitly asks for the Anthropic Claude Agent SDK, and using it directly keeps the product aligned with that requirement. A single runtime also avoids maintaining duplicate orchestration logic for tools, multimodal input, streaming, and session handling.

### Why structured JSON for exact data?
The challenge tests exact technical values. "What's the duty cycle for MIG at 200A on 240V?" must return exactly "25%". Semantic search over text chunks risks returning paraphrased or adjacent values. Pre-verified JSON with deterministic validation ensures exact answers.

### Why BM25 over vector search?
For a single 48-page manual, BM25 provides strong retrieval quality with zero infrastructure (no vector DB, no embedding model). The system is designed to add vector retrieval via optional pgvector for production scaling to multiple products.

### Why sandboxed iframes for artifacts?
SVG and HTML from an LLM can contain XSS vectors (onload handlers, javascript: URLs, foreignObject). Rendering in sandboxed iframes (allow-scripts only) prevents cross-origin attacks while still allowing interactive content.

### Why SQLite locally?
Evaluators should be running within 2 minutes. No Docker, no database setup. SQLite is created automatically. The architecture supports Postgres + pgvector for production.

## Project Structure

```
multimodal-prox-challenge/
  backend/
    app/
      agent/         # Orchestrator, tools, MCP wrappers, system prompt
      api/           # FastAPI routes (chat, products, assets)
      core/          # Config, database, bootstrap, seed
      context/       # Context assembler and routing
      ingest/        # Background ingestion pipeline
      knowledge/     # Structured store
      packs/         # Product registry and manifest models
      retrieval/     # BM25 search, query profiles
      session/       # Session manager
      validation/    # Deterministic answer validation
    scripts/         # Page rendering, chunk extraction, seed, eval
    tests/
  frontend/
    src/
      components/
        artifacts/   # Mermaid, SVG, HTML renderers
        chat/        # Message bubble, input, welcome screen
        evidence/    # Session sidebar, source viewer
        products/    # Dashboard, workspace, create/edit dialog
      lib/           # SSE client, useChat hook, product API
      types/         # Typed event contracts
  data/
    products/        # All product data lives here
      vulcan-omnipro-220/
        pack.yaml          # Product manifest
        files/             # Source PDFs + logo
        assets/pages/      # Rendered page PNGs
        assets/figures/    # Cropped diagrams
        structured/        # Extracted JSON (specs, duty cycles, etc.)
        index/             # Chunks, search indexes
        graph/             # Knowledge map artifacts
        jobs/              # Ingestion status
        conversations/     # Chat state
    local.db         # SQLite database (pre-seeded, committed to git)
```

## Testing

```bash
make test              # Unit tests (104 passing)
make lint              # Backend + frontend lint
make eval              # Full eval suite (16 live cases, needs API key)
```

Or without Make:

```bash
cd backend && uv run pytest tests/ -v
cd backend && uv run ruff check app/ tests/
cd frontend && npm run lint
cd backend && uv run python scripts/run_eval.py
```

## Generalizing to Other Products

The architecture is designed as a reusable document-intelligence platform:

1. Create a product via the dashboard UI or API (`POST /api/products`)
2. Upload PDF manuals (files stored in `data/products/<id>/files/`)
3. Processing runs automatically (page rendering, chunk extraction, indexing)
4. The agent serves the new product with the same tools and UI
5. Each product is fully isolated: its own files, indexes, conversations, and database records

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Agent runtime | Claude Agent SDK (`claude-agent-sdk`) |
| Model | Claude Sonnet 4.6 |
| Backend | Python, FastAPI, Pydantic |
| Frontend | Next.js 16, TypeScript, React 19, Tailwind CSS |
| Search | BM25 (rank-bm25) |
| PDF processing | PyMuPDF |
| Artifacts | Mermaid.js, sandboxed iframes |
| Local storage | SQLite + filesystem |
| Production | Postgres + pgvector (optional) |
