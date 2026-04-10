from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ContextChunk:
    page: int
    section: str
    text: str
    score: float | None = None
    source_id: str | None = None


@dataclass(slots=True)
class ContextBundle:
    product_id: str
    strategy: str
    session_summary: str = ""
    exact_tool_candidates: list[str] = field(default_factory=list)
    retrieved_chunks: list[ContextChunk] = field(default_factory=list)
    knowledge_map_path: str | None = None
    notes: list[str] = field(default_factory=list)

    def to_prompt_section(self) -> str:
        lines: list[str] = [f"Context strategy: {self.strategy}."]
        if self.session_summary:
            lines.append(f"Session summary: {self.session_summary}")
        if self.exact_tool_candidates:
            lines.append(
                "Exact-tool candidates: " + ", ".join(self.exact_tool_candidates) + "."
            )
        if self.knowledge_map_path:
            lines.append(f"Knowledge-map artifact: {self.knowledge_map_path}.")
        if self.retrieved_chunks:
            lines.append("Retrieved context:")
            for chunk in self.retrieved_chunks:
                prefix = f"- Page {chunk.page}"
                if chunk.section:
                    prefix += f" ({chunk.section})"
                snippet = " ".join(chunk.text.split())
                lines.append(f"{prefix}: {snippet[:280]}")
        if self.notes:
            lines.append("Notes: " + " ".join(self.notes))
        return "\n".join(lines)

