# Final Canonical Implementation Plan

**Date:** 2026-04-09

**Project:** `multimodal-prox-challenge`

This is the implementation plan that matches `final/FINAL_DESIGN.md`.

It is intentionally:
- merged from both prior proposals
- reduced to one canonical path
- optimized for correctness first
- optimized for local evaluator setup second
- still production-aware

---

## Final Build Order

We should not try to build everything at once. The fastest path to the strongest final product is:

1. scaffold the app with the final architecture
2. ingest and verify the manual into structured data + page assets
3. implement exact-data tools and validation first
4. implement full-context mode early
5. implement the Agent SDK runtime and streaming
6. implement source/evidence UI
7. implement hybrid retrieval as the generalization layer
8. implement artifacts and advanced multimodal flows

This keeps the most important risk under control: exact technical correctness.

---

## Phase 1: Scaffold The Final Architecture

### Goal
Create the repo structure and runtime foundations without changing the agreed architecture later.

### Create
- `frontend/` Next.js app
- `backend/` FastAPI app
- `data/document-packs/vulcan-omnipro-220/`
- `scripts/`
- `tests/`
- `final/` already created for canonical docs

### Required foundations
- local `.env.example`
- SQLite local database bootstrap
- backend config module
- frontend shell
- health endpoints
- local run scripts

### Deliverable
A local app shell runs with:
- frontend
- backend
- SQLite auto-created
- no Docker required

---

## Phase 2: Ingestion And Ground Truth

### Goal
Turn the Vulcan documents into trustworthy assets and exact-data stores.

### Inputs
- owner manual
- quick-start guide
- selection chart

### Build
- `pack.yaml` document-pack manifest
- page PNG rendering via PyMuPDF
- figure/region crop extraction
- manifest metadata
- structured JSON extraction for:
  - duty cycles
  - polarity
  - specifications
  - troubleshooting
  - settings
  - safety warnings

### Important rule
Every structured JSON file must be manually verified against the manual.

### Also add
- optional vision pre-cache for diagram-heavy pages
- eval seed questions file

### Deliverable
A verified knowledge base exists before the main agent logic relies on it.

---

## Phase 3: Evidence Model, Storage, And Full-Context Readiness

### Goal
Implement the canonical evidence model and local/prod storage abstraction, then make the manual ready for full-context use.

### Build
- evidence object types
- SQLite schema for local mode
- Postgres-compatible schema for production mode
- asset-path conventions for pages and crops
- full-manual context packaging
- prompt-caching-ready manual injection payload

### Core evidence fields
- `document`
- `page`
- `type`
- `bbox`
- `crop_url`
- `exactness`
- `confidence`
- `source_refs`

### Important decision
Use SQLite locally by default.

Do not make Qdrant or any extra vector database mandatory for local runs.

### Deliverable
The backend can store and return typed evidence objects consistently, and the full manual is ready to be used as a cached context artifact.

---

## Phase 4: Exact-Data Tools First

### Goal
Ship the highest-confidence answer path before broad retrieval.

### Implement tools
- `lookup_specifications`
- `lookup_duty_cycle`
- `lookup_polarity`
- `lookup_troubleshooting`
- `lookup_settings`
- `lookup_safety_warnings`
- `clarify_question`

### Tool rules
- enum-constrained inputs where possible
- deterministic JSON-backed outputs
- no interpolation for exact values
- structured return payloads only

### Add validation module
Create a separate validation service that:
- compares proposed exact answers against structured ground truth
- rejects mismatches
- forces correction before final response

### Deliverable
The system can already answer the challenge’s most critical exact questions safely and accurately.

---

## Phase 5: Full-Context Mode

### Goal
Exploit the fact that the challenge corpus is small enough to fit in context and use this as the primary broad-question path.

### Implement
- optional full-context manual mode
- prompt caching
- citations-aware full-document injection
- fallback control so exact-data tools still win for high-risk factual claims

### Rule
Full-context mode complements structured exact-data tools. It does not replace validation or grounded evidence packaging.

### Deliverable
The system can now answer a large fraction of broad manual questions accurately before the hybrid retrieval layer is finished.

---

## Phase 6: Agent Runtime And Streaming

### Goal
Implement the real orchestration layer on top of exact-data tools and early full-context mode.

### Build
- Claude Agent SDK-based runtime
- tool-use loop
- SSE streaming API
- clarification gate
- query router
- session manager
- system prompt specification
- follow-up suggestion format
- tool progress labels during streaming

### Session state should track
- process
- voltage
- material
- thickness
- setup state
- safety warnings shown

### Add
- parallel tool execution for independent calls
- safe tool-result caching
- conversation trimming
- artifact open/close detection during streaming

### System prompt must explicitly include
- expert welding technician persona
- safety-conscious tone
- always-use-tools rule for factual claims
- never-interpolate rule
- artifact-type mapping
- follow-up suggestion format
- citation and source-linking rules
- session-context injection rules

### Deliverable
A streaming backend can answer real user questions with tool use and stateful context.

---

## Phase 7: Source Experience And Core Frontend UX

### Goal
Make the product usable and trustworthy before advanced retrieval polish.

### Build
- source cards beneath answers
- source page viewer
- page preview thumbnails
- crop viewer
- highlight overlays from bbox data
- exactness labels in UI
- welcome screen
- quick actions
- mobile-responsive layout
- dark mode default

### Also add
- deep linking to a cited source page
- bidirectional linking between source cards and artifacts where feasible

### Deliverable
Users can inspect where the answer came from, navigate the manual easily, and start using the assistant without prompt anxiety.

---

## Phase 8: Hybrid Retrieval

### Goal
Handle broader and cross-page questions that are not fully covered by exact tools.

### Implement
- FTS/BM25-style lexical retrieval
- optional vector retrieval
- weighted fusion
- reranking
- sentence-level compression
- query-profile routing

### Query-profile examples
- table-heavy
- diagram-heavy
- troubleshooting
- setup/procedure
- general explanatory

### Important rule
Structured exact-data tools should still take precedence when the question clearly maps to them.

### Deliverable
The system can answer broader open-ended questions without weakening exact factual paths.

---

## Phase 9: Artifact System

### Goal
Make multimodal responses a first-class output path.

### Implement artifact contract
Each artifact must include:
- `type`
- `renderer`
- `spec`
- `source_refs`

### Support
- SVG diagrams
- React calculators/configurators
- Mermaid flowcharts
- HTML/table displays
- annotated images

### Frontend behaviors
- inline artifact rendering
- streaming-safe placeholder behavior
- artifact expand/fullscreen support
- artifact-to-source linking
- consistent polarity-diagram color standards
- never render incomplete artifact blocks

### Deliverable
The app now visibly meets the challenge’s “not text-only” bar.

---

## Phase 10: User Image Input

### Goal
Make multimodal input real, not marketing copy.

### Implement
- image upload in frontend
- backend image intake
- weld diagnosis flow
- machine/panel/setup image flow
- evidence-aware responses for image questions

### Important rule
If this is not fully wired, do not claim it in the README as a finished capability.

### Deliverable
The product supports both text and image input credibly.

---

## Phase 11: Evaluation, Regression, And README

### Goal
Make the system trustworthy and easy to evaluate.

### Build
- YAML eval question set
- regression runner
- challenge benchmark cases
- adversarial cases
- setup/run verification
- README with architecture, local mode, production mode, and known tradeoffs

### Evaluate at minimum
- MIG duty cycle at 200A / 240V
- TIG polarity and socket mapping
- flux-cored porosity troubleshooting
- front panel / diagram retrieval
- settings recommendation
- clarification behavior
- artifact generation behavior
- image input path

### Deliverable
A polished, reviewable, reproducible submission package.

---

## Phase 12: Deployment And Demo Packaging

### Goal
Maximize evaluator impression and reduce review friction.

### Build
- optional Docker Compose path
- production deployment for backend
- production deployment for frontend
- hosted demo URL
- 5-8 minute walkthrough video
- final README polish with local and hosted instructions

### Suggested deployment shape
- frontend on Vercel
- backend on Railway or equivalent
- production storage config documented clearly

### Deliverable
A submission package that is not only correct, but easy and attractive to evaluate.

---

## What We Borrowed From The Alternate Proposal

- full-context mode
- concrete tool-first runtime design
- source-linked artifact contract
- stronger SSE/runtime thinking
- query router and retrieval shaping
- vision pre-cache
- earlier full-context mode
- explicit prompt and UX rules

## What We Kept From Our Prior Plan

- SQLite local default
- Postgres production path
- evidence-first model with bbox/exactness/crops
- deterministic validation layer
- generalizable document-pack abstraction
- lower local setup friction

## What We Explicitly Rejected

- mandatory Qdrant for local runs
- interpolation for exact values
- page-number-only grounding
- Docker-only evaluator workflow
- vague “Agent SDK” wording without real SDK usage

---

## Final Priority Order

If time becomes tight, prioritize in this exact order:

1. exact-data tools
2. validation
3. full-context mode
4. streaming runtime
5. source grounding
6. artifact rendering
7. hybrid retrieval
8. image input
9. extra polish

This ensures that even a partially completed system is still technically strong.

---

## Final Go / No-Go Criteria

We should not call the system final unless all of these are true:

- local run works without Docker
- exact lookup questions are correct
- citations are actionable
- at least 3 artifact types work well
- artifact outputs are source-grounded
- no interpolated technical answers are presented as exact
- mobile UI is usable
- dark mode is coherent
- README is clear

---

## Final Recommendation

This plan should be treated as the final implementation path for review.

If another reviewer or agent suggests changes, they should compare against this plan directly and only propose:
- merge-worthy upgrades
- simplifications
- risk reductions

not a completely new architecture unless they can clearly beat this one on:
- correctness
- challenge compliance
- local setup
- multimodal quality
