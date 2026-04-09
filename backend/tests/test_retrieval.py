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
