"""Hybrid retrieval service with BM25 and query profile routing.

Provides the search_manual tool with ranked, relevant text chunks
from the product manual. Uses BM25 for lexical matching with
optional sentence-level compression to reduce token cost.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from rank_bm25 import BM25Okapi

from app.packs.registry import get_active_product

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "knowledge" / "data"


@dataclass
class QueryProfile:
    """Classified query type for retrieval routing."""

    is_duty_cycle: bool = False
    is_polarity: bool = False
    is_troubleshooting: bool = False
    is_settings: bool = False
    is_visual: bool = False
    is_safety: bool = False

    @classmethod
    def classify(cls, query: str) -> QueryProfile:
        """Detect query type from keywords."""
        q = query.lower()
        return cls(
            is_duty_cycle=(
                "duty cycle" in q
                or "how long can i weld" in q
                or "rest time" in q
                or "continuous" in q and "amp" in q
            ),
            is_polarity=any(
                w in q
                for w in ["polarity", "socket", "cable", "dcep", "dcen", "which socket"]
            ),
            is_troubleshooting=any(
                w in q
                for w in [
                    "porosity", "spatter", "jamming", "unstable", "not feeding",
                    "bird's nest", "problem", "troubleshoot", "doesn't work",
                    "not working", "won't start", "burn through",
                ]
            ),
            is_settings=any(
                w in q
                for w in ["settings", "wire feed speed", "what voltage", "what amp"]
            ),
            is_visual=any(
                w in q
                for w in [
                    "show me", "diagram", "schematic", "picture", "photo",
                    "what does", "where is", "front panel", "controls",
                ]
            ),
            is_safety=any(
                w in q
                for w in ["safety", "danger", "warning", "protective", "ppe", "gloves"]
            ),
        )

    @property
    def routes_to_exact_tool(self) -> bool:
        """Whether this query should go to exact-data tools instead of search."""
        return self.is_duty_cycle or self.is_polarity


class RetrievalService:
    """BM25-based retrieval over manual text chunks.

    Loads chunks from chunks.json at initialization. Provides search()
    with section boosting based on query profile.
    """

    def __init__(self, data_dir: Path = DATA_DIR) -> None:
        self._chunks: list[dict] = []
        self._bm25: BM25Okapi | None = None
        self._load_chunks(data_dir)

    def _load_chunks(self, data_dir: Path) -> None:
        chunks_path = data_dir / "chunks.json"
        if not chunks_path.exists():
            logger.warning("chunks.json not found at %s, search will be empty", chunks_path)
            return

        with open(chunks_path, encoding="utf-8") as f:
            self._chunks = json.load(f)

        if not self._chunks:
            return

        # Build BM25 index
        tokenized = [self._tokenize(c["text"]) for c in self._chunks]
        self._bm25 = BM25Okapi(tokenized)
        logger.info("Loaded %d chunks for BM25 retrieval", len(self._chunks))

    @property
    def chunk_count(self) -> int:
        return len(self._chunks)

    @staticmethod
    def classify_query(query: str) -> QueryProfile:
        """Classify a query for routing decisions."""
        return QueryProfile.classify(query)

    def search(
        self,
        query: str,
        max_results: int = 5,
        compress: bool = True,
    ) -> list[dict]:
        """Search chunks by BM25 relevance.

        Returns list of dicts with: text, page, section, score.
        Optionally compresses results to most relevant sentences.
        """
        if not query.strip() or self._bm25 is None:
            return []

        profile = QueryProfile.classify(query)
        tokens = self._tokenize(query)
        scores = self._bm25.get_scores(tokens)

        # Apply section boosts based on query profile
        boosted_scores = self._apply_section_boosts(scores, profile)

        # Rank and select top results
        scored_chunks = [
            (i, score) for i, score in enumerate(boosted_scores) if score > 0
        ]
        scored_chunks.sort(key=lambda x: x[1], reverse=True)

        results: list[dict] = []
        for idx, score in scored_chunks[:max_results]:
            chunk = self._chunks[idx]
            text = chunk["text"]

            # Optional sentence-level compression.
            # Never compress safety sections to avoid dropping warnings.
            is_safety_chunk = "safety" in chunk.get("section", "").lower()
            if compress and not is_safety_chunk:
                text = self._compress_to_relevant(text, query)

            results.append({
                "text": text,
                "page": chunk["page"],
                "section": chunk["section"],
                "source_id": chunk.get("source_id"),
                "score": round(score, 4),
            })

        return results

    def _apply_section_boosts(
        self,
        scores: list[float],
        profile: QueryProfile,
    ) -> list[float]:
        """Boost scores based on query profile and chunk section."""
        boosted = list(scores)
        for i, chunk in enumerate(self._chunks):
            section = chunk.get("section", "").lower()

            if profile.is_troubleshooting and "troubleshooting" in section:
                boosted[i] *= 1.5
            elif profile.is_troubleshooting and "welding tips" in section:
                boosted[i] *= 1.3

            if profile.is_visual and "controls" in section:
                boosted[i] *= 1.4

            if profile.is_safety and "safety" in section:
                boosted[i] *= 1.5

            if profile.is_settings and "welding" in section:
                boosted[i] *= 1.2

        return boosted

    def _compress_to_relevant(
        self,
        text: str,
        query: str,
        max_sentences: int = 6,
    ) -> str:
        """Keep only the most query-relevant sentences from a chunk.

        Reduces token cost by ~60% while preserving relevant content.
        """
        sentences = re.split(r"(?<=[.!?])\s+", text)
        if len(sentences) <= max_sentences:
            return text

        query_words = set(self._tokenize(query))

        # Score each sentence by query word overlap
        scored: list[tuple[int, float, str]] = []
        for i, sentence in enumerate(sentences):
            sent_words = set(self._tokenize(sentence))
            overlap = len(query_words & sent_words)
            scored.append((i, overlap, sentence))

        # Keep top sentences, preserve original order
        scored.sort(key=lambda x: x[1], reverse=True)
        top_indices = sorted(s[0] for s in scored[:max_sentences])
        return " ".join(sentences[i] for i in top_indices)

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Simple word tokenization for BM25."""
        return re.findall(r"\w+", text.lower())


# Factory
_services: dict[str, RetrievalService] = {}


def get_retrieval_service(data_dir: Path | None = None) -> RetrievalService:
    """Get or create the retrieval service singleton."""
    if data_dir is None:
        data_dir = get_active_product().index_dir
    key = str(data_dir.resolve())
    if key not in _services:
        _services[key] = RetrievalService(data_dir)
    return _services[key]


def reset_retrieval_service() -> None:
    """Reset for tests."""
    _services.clear()
