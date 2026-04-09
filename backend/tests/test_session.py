"""Tests for session management."""
from app.session.manager import Session, SessionManager


def test_session_default_state() -> None:
    session = Session(id="test-1")
    assert session.current_process is None
    assert session.current_voltage is None
    assert "No process" in session.context_summary()


def test_session_context_summary() -> None:
    session = Session(
        id="test-2",
        current_process="mig",
        current_voltage="240v",
        current_material="mild_steel",
    )
    summary = session.context_summary()
    assert "mig" in summary
    assert "240v" in summary
    assert "mild_steel" in summary


def test_session_to_dict() -> None:
    session = Session(id="test-3", current_process="tig")
    d = session.to_dict()
    assert d["id"] == "test-3"
    assert d["current_process"] == "tig"
    assert "context_summary" in d


def test_session_manager_creates_new() -> None:
    mgr = SessionManager()
    session = mgr.get_or_create("s1")
    assert session.id == "s1"


def test_session_manager_returns_existing() -> None:
    mgr = SessionManager()
    s1 = mgr.get_or_create("s1")
    s1.current_process = "mig"
    s2 = mgr.get_or_create("s1")
    assert s2.current_process == "mig"


def test_session_manager_update_from_message() -> None:
    mgr = SessionManager()
    session = mgr.get_or_create("s1")
    mgr.update_from_message(session, "I want to set up MIG welding on 240V with mild steel")
    assert session.current_process == "mig"
    assert session.current_voltage == "240v"
    assert session.current_material == "mild_steel"


def test_session_manager_detects_tig() -> None:
    mgr = SessionManager()
    session = mgr.get_or_create("s2")
    mgr.update_from_message(session, "How do I set up TIG?")
    assert session.current_process == "tig"


def test_session_manager_detects_flux_cored() -> None:
    mgr = SessionManager()
    session = mgr.get_or_create("s3")
    mgr.update_from_message(session, "I'm using flux-cored wire at 120V")
    assert session.current_process == "flux_cored"
    assert session.current_voltage == "120v"
