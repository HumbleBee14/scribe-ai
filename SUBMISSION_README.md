# Vulcan OmniPro 220 Multimodal Agent

A production-grade multimodal reasoning agent for the Vulcan OmniPro 220 welding system, built on the **Claude Agent SDK**.

## Quickstart

```bash
git clone <repo>
cd multimodal-prox-challenge
cp .env.example .env   # Add your ANTHROPIC_API_KEY

# Backend
cd backend
uv venv && uv pip install -e ".[dev]"
uv run uvicorn app.main:app --reload --port 8000

# Frontend (new terminal)
cd frontend
npm install
npm run dev

# Open http://localhost:3000
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
+------------------+           +------------------------+
| Chat UI          |   SSE     | Claude Agent SDK       |
| Artifact viewers | <-------> | (query + resume)       |
| Session sidebar  |           |                        |
| Image upload     |           | Custom MCP Tools (10)  |
+------------------+           | Built-in Read tool     |
                               |                        |
                               | Knowledge Engine:      |
                               | - Structured JSON      |
                               | - BM25 retrieval       |
                               | - Validation module    |
                               +------------------------+
```

### Foundation: Claude Agent SDK

The agent uses `claude-agent-sdk` (the official Agent SDK, not the raw Anthropic client) as its orchestration foundation. The SDK handles:
- The agentic tool loop (message, tool_use, execute, repeat)
- Token-level streaming
- Session persistence and multi-turn resume

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

**Path 3: Built-in Read** (broad manual access)
- SDK's native Read tool can access the PDF directly
- Supplements (does not replace) exact-data tools
- Used for questions that don't map to structured data

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

Multi-turn conversations use the SDK's built-in session resume.

### Evidence Model

Every answer is backed by typed evidence:
- `document`, `page`, `type` (text_block, table, figure, page_region)
- `bbox` coordinates and `cropUrl` for region-level grounding
- `exactness` label: `native_pdf` or `vision_ocr`

## Design Decisions

### Why Claude Agent SDK (not raw Anthropic client)?
The challenge requires the Agent SDK as the foundation. The SDK provides the agent loop, session management, and MCP tool integration. Our custom tools are exposed via MCP, and the SDK handles tool discovery and execution.

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
      api/           # FastAPI routes (chat streaming, session)
      knowledge/     # Evidence model, structured store, full-context
      retrieval/     # BM25 search, query profiles, compression
      session/       # Session manager (process/voltage/material tracking)
      validation/    # Deterministic answer validation
    scripts/         # Page rendering, chunk extraction, eval runner
    tests/           # 97 tests
  frontend/
    src/
      components/
        artifacts/   # Mermaid, SVG, HTML renderers
        chat/        # Message bubble, input, welcome screen
        evidence/    # Session sidebar, source viewer
      lib/           # SSE client, useChat hook
      types/         # Typed SSE event contracts
  data/
    document-packs/  # Product manifests, eval questions
  knowledge/
    images/          # 48 page PNGs at 200 DPI
    figures/         # Cropped diagrams
  files/
    owner-manual.pdf
    quick-start-guide.pdf
    selection-chart.pdf
```

## Testing

```bash
# Unit tests (97 passing)
cd backend && uv run pytest tests/ -v

# Lint
cd backend && uv run ruff check app/ tests/
cd frontend && npm run lint

# Live API evaluation (requires ANTHROPIC_API_KEY)
cd backend && uv run python scripts/test_live_agent.py

# Full eval suite (16 live cases; exits non-zero on failures or needs review)
cd backend && uv run python scripts/run_eval.py
```

## Generalizing to Other Products

The architecture is designed as a reusable document-intelligence platform:

1. Create a document pack: `data/document-packs/<product>/pack.yaml`
2. Run page rendering: `uv run python scripts/render_pages.py`
3. Extract structured data (Claude batch API or manual verification)
4. Run chunk extraction: `uv run python scripts/extract_chunks.py`
5. The agent serves the new product with the same tools and UI

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Agent | Claude Agent SDK (`claude-agent-sdk`) |
| Model | Claude Sonnet 4.6 |
| Backend | Python, FastAPI, Pydantic |
| Frontend | Next.js 15, TypeScript, React 19, Tailwind CSS |
| Search | BM25 (rank-bm25) |
| PDF processing | PyMuPDF |
| Artifacts | Mermaid.js, sandboxed iframes |
| Local storage | SQLite + filesystem |
| Production | Postgres + pgvector (optional) |
