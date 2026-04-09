"""Tests for hybrid retrieval service."""
from app.retrieval.service import QueryProfile, RetrievalService

# --- Query profile detection ---


def test_query_profile_duty_cycle() -> None:
    profile = QueryProfile.classify("What's the duty cycle for MIG at 240V?")
    assert profile.is_duty_cycle
    assert not profile.is_polarity


def test_query_profile_polarity() -> None:
    profile = QueryProfile.classify("What polarity do I need for TIG?")
    assert profile.is_polarity


def test_query_profile_troubleshooting() -> None:
    profile = QueryProfile.classify("I'm getting porosity in my welds")
    assert profile.is_troubleshooting


def test_query_profile_visual() -> None:
    profile = QueryProfile.classify("Show me the front panel controls")
    assert profile.is_visual


def test_query_profile_general() -> None:
    profile = QueryProfile.classify("How do I check wire feed tension?")
    assert not profile.is_duty_cycle
    assert not profile.is_polarity
    assert not profile.is_troubleshooting


# --- Retrieval service ---


def test_retrieval_service_loads() -> None:
    service = RetrievalService()
    assert service.chunk_count > 0


def test_retrieval_search_returns_results() -> None:
    service = RetrievalService()
    results = service.search("wire feed tension")
    assert len(results) > 0
    assert "text" in results[0]
    assert "page" in results[0]
    assert "score" in results[0]


def test_retrieval_search_respects_max_results() -> None:
    service = RetrievalService()
    results = service.search("welding", max_results=3)
    assert len(results) <= 3


def test_retrieval_search_returns_page_numbers() -> None:
    service = RetrievalService()
    results = service.search("polarity setup")
    for r in results:
        assert isinstance(r["page"], int)
        assert 1 <= r["page"] <= 48


def test_retrieval_empty_query_returns_empty() -> None:
    service = RetrievalService()
    results = service.search("")
    assert results == []


# --- Exact-tool precedence ---


def test_search_manual_redirects_duty_cycle_query() -> None:
    """search_manual should redirect duty cycle queries to exact tools."""
    from app.agent.tools import execute_tool

    result = execute_tool("search_manual", {"query": "What is the duty cycle for MIG?"})
    assert result.get("redirect") is True
    assert "lookup_duty_cycle" in result.get("note", "")


def test_search_manual_redirects_polarity_query() -> None:
    from app.agent.tools import execute_tool

    result = execute_tool("search_manual", {"query": "What polarity for TIG?"})
    assert result.get("redirect") is True
    assert "lookup_polarity" in result.get("note", "")


def test_search_manual_does_not_redirect_general_query() -> None:
    from app.agent.tools import execute_tool

    result = execute_tool("search_manual", {"query": "How do I check wire feed tension?"})
    assert result.get("redirect") is not True
    assert len(result.get("results", [])) > 0


# --- Section boosting ---


def test_troubleshooting_query_boosts_troubleshooting_section() -> None:
    service = RetrievalService()
    results = service.search("porosity in my welds", max_results=3)
    sections = [r["section"] for r in results]
    # At least one result should be from troubleshooting or welding tips
    assert any("Troubleshooting" in s or "Welding Tips" in s for s in sections)


# --- Safety compression protection ---


def test_safety_chunks_not_compressed() -> None:
    """Safety section chunks should not be compressed to avoid dropping warnings."""
    service = RetrievalService()
    results = service.search("safety electrical shock", max_results=5, compress=True)
    safety_results = [r for r in results if "Safety" in r["section"]]
    for r in safety_results:
        # Safety chunks should retain more content than compressed chunks
        assert len(r["text"]) > 50


def test_query_profile_routes_to_exact_tool() -> None:
    profile = QueryProfile.classify("What's the duty cycle?")
    assert profile.routes_to_exact_tool

    profile2 = QueryProfile.classify("How do I adjust the feed tensioner?")
    assert not profile2.routes_to_exact_tool
