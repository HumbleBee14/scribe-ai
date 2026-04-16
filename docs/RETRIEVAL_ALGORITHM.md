# Retrieval Algorithm: Context Building & Hybrid Search

**Last updated: 2026-04-11 — post empirical tuning**
**Files covered:** `app/agent/tools.py`, `app/agent/prompts.py`, `app/core/database.py`

---

## Table of Contents
1. [System Overview](#1-system-overview)
2. [Stop Words — Are They Filtered?](#2-stop-words)
3. [FTS5 Weighted BM25 Scoring](#3-fts5-weighted-bm25-scoring)
4. [Vector (Embedding) Scoring](#4-vector-embedding-scoring)
5. [Hybrid Score Combination](#5-hybrid-score-combination)
6. [Two-Path Context Injection Filter](#6-two-path-context-injection-filter)
7. [Empirical Test Results](#7-empirical-test-results)
8. [End-to-End Flow](#8-end-to-end-flow)
9. [Agent Tool: search_manual](#9-agent-tool-search_manual)
10. [Tuning Reference](#10-tuning-reference)

---

## 1. System Overview

Context building happens in **two phases** before and during the agent's response:

```
User message
    │
    ▼
Phase 1 — Pre-injection (BEFORE agent starts)
    build_system_prompt()
      └── build_initial_search_context()
              └── _hybrid_search(query, limit=3)
                      ├── FTS5 weighted BM25  (keywords=5× summary=3× text=1×)
                      └── Embedding L2 vector search (all-MiniLM-L6-v2)
                  Two-path filter
                    Path A: vec_dist < 0.80  (strong semantic match alone)
                    Path B: fts=Y AND vec≠none AND score ≥ 0.52
                  Inject full detailed_text of qualifying pages
                  into system prompt → agent answers without tool calls
    │
    ▼
Agent starts — has document map + pre-injected context
    │
    ▼
Phase 2 — Tool calls (if Phase 1 is insufficient)
    search_manual(query)
      └── _hybrid_search(query, limit=8)  [same algo, NO threshold]
    get_page_text(source_id, pages)
    get_page_image(source_id, page)
```

---

## 2. Stop Words

**No explicit stop-word list needed. BM25 IDF handles it automatically.**

FTS5 indexes all words, but BM25's IDF formula makes common words contribute near-zero:

```
IDF(term) = log((N - n(term) + 0.5) / (n(term) + 0.5) + 1)

"the"  on all 48 pages → IDF ≈ 0.01  (near zero)
"duty" on 3 pages      → IDF ≈ 2.92  (high)
"IGBT" on 1 page       → IDF ≈ 3.87  (very high — rare, specific)
```

Rare technical terms automatically score high. Common words score near zero.
The 48-page corpus is small enough that even moderately common technical terms
(appearing on 5–8 pages) still have meaningful IDF values.

---

## 3. FTS5 Weighted BM25 Scoring

### Column Weights

```sql
-- Column order in page_fts: (summary=0, detailed_text=1, keywords=2)
ORDER BY bm25(page_fts, 3.0, 1.0, 5.0)
```

| Column | Weight | Rationale |
|---|---|---|
| `keywords` | **5.0** | Claude Vision–extracted key terms. Match here = intentional, precise. |
| `summary` | **3.0** | 1–2 sentence description. Term here = central to the page topic. |
| `detailed_text` | **1.0** | Full OCR text (often 300–800 words). Term can appear incidentally. |

### BM25 Multi-Word Scoring

BM25 **sums** per-term scores. A 4-term query `"duty cycle MIG 240V"` scores:
```
page_score = BM25("duty") + BM25("cycle") + BM25("MIG") + BM25("240V")
```
A page matching all 4 terms in `keywords` scores ~4–8× a page matching 1 term in `detailed_text`.

### Rank Normalization → FTS Score (0.10–0.50)

```python
# BM25 rank is negative: more negative = better
best_abs_rank = abs(fts_results[0]["fts_rank"])      # top result
fts_score = max(0.10, (abs(rank) / best_abs_rank) * 0.50)
```

| Result | Example | FTS Score |
|---|---|---|
| Top BM25 match | 4-term hit in keywords | **0.50** (always) |
| Mid BM25 match | 2-term partial hit | ~0.25–0.35 |
| Weak BM25 match | 1-term in long text blob | **0.10** (floor) |
| Rare term, only 1 page | "IGBT" on 1 page | **0.50** (it IS the top result) |

> **Key insight**: A rare term on only 1 page = top (and only) FTS result = score 0.50.
> IDF rewards rarity. The relative normalization never penalizes unique matches.

---

## 4. Vector (Embedding) Scoring

### Model
- `all-MiniLM-L6-v2` — 384 dimensions, unit-normalized output
- Runs locally (sentence-transformers). No API cost.
- Indexed in sqlite-vec (`page_vec` table, `float[384]`)

### Distance → Score

sqlite-vec returns L2 (Euclidean) distance between unit-normalized vectors:

```
L2 range: [0.0, 2.0]  (0=identical, ~1.41=orthogonal, 2=opposite)

vec_score        = max(0.0, 1.0 - distance / 2.0)
vec_contribution = vec_score * 0.5    (max +0.50 to combined score)
```

| L2 Distance | Cosine Sim | vec_contribution |
|---|---|---|
| 0.0  | 1.00 | **0.50** |
| 0.4  | 0.92 | 0.40 |
| 0.8  | 0.68 | 0.30 |
| 1.0  | 0.50 | 0.25 |
| 1.4  | 0.02 | 0.15 |
| 2.0  | -1.0 | 0.00 |

### Empirically Observed Distances (Vulcan OmniPro 220, 48 pages)

| Query type | Best observed vec_dist | Typical range |
|---|---|---|
| Direct keyword query (e.g., duty cycle) | **0.775** | 0.78–1.05 |
| Troubleshooting query (e.g., porosity) | **0.915** | 0.91–1.05 |
| Irrelevant query (binary search) | n/a (`none`) | > 1.28 or not in top K |

> **Why distances aren't low**: Embeddings are computed on full pages (300–800 words).
> The embedding is an average of all content on the page, diluting topic-specificity.
> This is why even the best match has distance ~0.775, not 0.1–0.3.

---

## 5. Hybrid Score Combination

```
combined_score = fts_score + vec_contribution
              = BM25_normalized(0.10–0.50) + vec_score × 0.5(0.00–0.50)
              max possible = 1.0
```

Pages in both FTS and vector results get additive scores:
```python
if key in seen:           # already scored from FTS
    seen[key]["score"] += vec_contribution
else:                     # new from vector only
    seen[key]["score"] = vec_contribution
```

If a page appears in FTS results only → `vec_distance = None`, `score ≤ 0.50`.
If a page appears in vector results only → `fts_hit = False`, score = vec_contribution only.

---

## 6. Two-Path Context Injection Filter

```python
def _qualifies(r):
    vec_dist = r.get("vec_distance")   # None if not in vec results
    score    = r.get("score", 0)
    fts_hit  = r.get("fts_hit", False)

    # Path A: strong standalone semantic match
    if vec_dist is not None and vec_dist < 0.80:
        return True, "path=A"

    # Path B: both signals present + combined threshold
    if fts_hit and vec_dist is not None and score >= 0.52:
        return True, "path=B"

    return False, "skip"
```

### Path A — Semantic-Driven

| Property | Value |
|---|---|
| Trigger | `vec_dist < 0.80` |
| FTS required? | No |
| Purpose | Catches paraphrase/synonym queries with no keyword overlap |
| Example | "bubbly defects" → page about "porosity, weld discontinuity" |
| Empirical basis | Best observed distance in corpus = 0.775; old threshold 0.40 **never fired once** |

### Path B — Dual-Signal Confirmation

| Property | Value |
|---|---|
| Trigger | `fts_hit AND vec_dist is not None AND score >= 0.52` |
| FTS required? | Yes |
| Vec required? | Yes (explicitly `not None`) |
| Purpose | Both keyword overlap and semantic similarity must agree |
| Why 0.52? | Pure FTS-only score maxes at exactly **0.50** (normalization design). 0.52 is mathematically unreachable without vec contribution. |
| Empirical basis | Porosity relevant pages scored 0.526–0.568; old threshold 0.60 rejected all of them |

### Why the Old Thresholds Were Wrong

| Parameter | Old value | Problem | New value |
|---|---|---|---|
| Path A vec_dist | `< 0.40` | Never fired. Min observed distance in corpus ~0.775 | `< 0.80` |
| Path B score | `>= 0.60` | Rejected genuine relevant pages scoring 0.53–0.57 (porosity) | `>= 0.52` |
| Path B vec check | Missing | Pure FTS hits (score=0.50, no vec) could edge near threshold | Added `vec_dist is not None` |

### What Is Never Injected

| Scenario | Score | Vec | Result |
|---|---|---|---|
| Irrelevant FTS-only hit | ≤ 0.50 | `none` | ✗ `vec=none` blocks Path B |
| Weak FTS + weak vec | ~0.25 | ~1.3 | ✗ score < 0.52 |
| Vec-only, distance = 0.85 | ~0.30 | 0.85 | ✗ above Path A threshold, below score threshold |

---

## 7. Empirical Test Results

Tested on **Vulcan OmniPro 220** product manual (3 sources, 48 pages total).
`limit=3` pages returned per query by `_hybrid_search`.

### Test 1 — Irrelevant Query

**Query:** `"draw binary search algo diagram and explain also"`

| Page | Score | FTS | Vec dist | Result |
|---|---|---|---|---|
| owner-manual p22 | 0.500 | Y | `none` | ✗ skip — no vec signal |
| owner-manual p8 | 0.353 | Y | 1.279 | ✗ skip — score < 0.52 |
| quick-start-guide p2 | 0.179 | N | 1.285 | ✗ skip — no FTS, weak vec |

**Outcome: 0 pages injected ✅** (query is irrelevant — correct)

---

### Test 2 — Domain Query, Synonym Challenge

**Query:** `"I'm getting porosity in my flux-cored welds. What should I check?"`

| Page | Score | FTS | Vec dist | Result |
|---|---|---|---|---|
| owner-manual p37 | 0.568 | Y | 0.915 | ✓ path=B |
| owner-manual p18 | 0.543 | Y | 1.050 | ✓ path=B |
| owner-manual p41 | 0.526 | Y | 1.038 | ✓ path=B |

**Outcome: 3 pages injected ✅** (was 0 before fix — this was the critical failure case)

---

### Test 3 — Direct Technical Query

**Query:** `"What's the duty cycle for MIG welding at 200A on 240V?"`

| Page | Score | FTS | Vec dist | Result |
|---|---|---|---|---|
| selection-chart p1 | 0.759 | Y | 0.964 | ✓ path=B |
| owner-manual p7 | 0.681 | Y | **0.775** | ✓ **path=A** ← only Path A trigger observed |
| owner-manual p19 | 0.616 | Y | 0.820 | ✓ path=B |

**Outcome: 3 pages injected ✅**
`p7` triggered Path A (vec=0.775 < 0.80) — the only empirical Path A trigger seen so far.

---

### Test 4 — Multi-Part Technical Query

**Query:** `"What polarity setup do I need for TIG welding? Which socket does the ground clamp go in?"`

| Page | Score | FTS | Vec dist | Result |
|---|---|---|---|---|
| owner-manual p14 | 0.747 | Y | 1.012 | ✓ path=B |
| owner-manual p13 | 0.725 | Y | 0.970 | ✓ path=B |
| owner-manual p27 | 0.710 | Y | 1.017 | ✓ path=B |

**Outcome: 3 pages injected ✅**

---

### Score Range Summary

| Category | Score range | Vec dist range | Status |
|---|---|---|---|
| Clear relevant (direct tech) | 0.61–0.76 | 0.77–1.02 | ✅ always injected |
| Borderline relevant (domain) | 0.52–0.60 | 0.91–1.06 | ✅ injected via Path B |
| Noise / off-domain | ≤ 0.50 | `none` or > 1.28 | ✅ always rejected |

---

*Raw test logs to be added here by user.*

---

## 8. End-to-End Flow

```
User: "I'm getting porosity in my flux-cored welds. What should I check?"
        │
        ▼ ── Phase 1: build_initial_search_context() ────────────────────────
        │
        │   FTS5 (weighted BM25):
        │     "porosity"   → high IDF (rare term)
        │     "flux-cored" → high IDF (process-specific)
        │     "welds"      → moderate IDF
        │     → ranks p37, p18, p41 (troubleshooting pages) highest
        │
        │   Vector:
        │     p37: dist=0.915  p18: dist=1.050  p41: dist=1.038
        │
        │   Two-path filter:
        │     p37: fts=Y vec=0.915 score=0.568 → path=B ✓ INJECT
        │     p18: fts=Y vec=1.050 score=0.543 → path=B ✓ INJECT
        │     p41: fts=Y vec=1.038 score=0.526 → path=B ✓ INJECT
        │
        │   System prompt gets: [p41 text] [p18 text] [p37 text]
        │   (reversed order — most relevant p37 last for recency bias)
        │
        ▼ ── Agent starts ────────────────────────────────────────────────────
        │
        │   Has 3 troubleshooting pages pre-loaded → answers directly
        │
        │   If needs more detail:
        │     search_manual("porosity causes flux core")
        │     get_page_text("owner-manual", [37])
        ▼
        Agent: "Porosity in flux-cored welds is typically caused by..."
```

---

## 9. Agent Tool: `search_manual`

Uses the same `_hybrid_search()` but **no threshold** — all scored results returned.
The agent sees scores and decides which pages to fetch.

| Score range | Typical agent behavior |
|---|---|
| > 0.70 | Immediate `get_page_text` — high confidence |
| 0.52–0.70 | Read and verify before citing |
| 0.30–0.52 | Try rephrased search first |
| < 0.30 | New search or `clarify_question` |

---

## 10. Tuning Reference

| Parameter | File | Current | Empirical basis |
|---|---|---|---|
| `keywords` BM25 weight | `database.py` | **5.0** | Curated extracted terms = high-signal column |
| `summary` BM25 weight | `database.py` | **3.0** | Short page description = medium-signal |
| `detailed_text` BM25 weight | `database.py` | **1.0** | Baseline — large text blob |
| FTS rank floor | `tools.py` | **0.10** | Weakest BM25 hits get this floor |
| Vec contribution factor | `tools.py` | **× 0.5** | Equal max weight to FTS (both cap at 0.50) |
| Vec normalization divisor | `tools.py` | **/ 2.0** | Unit-norm vectors; L2 range = [0, 2] |
| **Path A: vec_dist threshold** | `prompts.py` | **< 0.80** | Empirical: best match in corpus = 0.775 |
| **Path B: score threshold** | `prompts.py` | **≥ 0.52** | Pure FTS max = 0.50; 0.52 requires vec |
| **Path B: vec required** | `prompts.py` | `is not None` | Explicit dual-signal requirement |
| Pre-search limit | `prompts.py` | `limit=3` | 3 pages pre-injected per query |
| Tool search limit | `tools.py` | `limit=8` | Agent sees 8 candidates per tool call |

### Known Edge Cases & TODO

| Case | Risk level | Status |
|---|---|---|
| Stop-word query + weak random vec hit → passes 0.52 | Low — irrelevant queries produce `vec=none` (confirmed in Test 1) | Monitor |
| Path A threshold 0.80 may be too permissive for larger corpora | Medium — more pages means more with dist < 0.80 | Test with 200+ page manual |
| Short single-word queries ("setup") → vague vec embeddings | Low | No action yet |
| Vec search unavailable (sqlite-vec missing) | Handled — falls back to FTS only; Path A/B require `vec!= None` | Graceful degradation |
