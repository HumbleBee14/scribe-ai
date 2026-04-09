"""Tests for session management."""
from datetime import datetime, timedelta, timezone

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


def test_session_manager_detects_thickness() -> None:
    mgr = SessionManager()
    session = mgr.get_or_create("s4")
    mgr.update_from_message(session, "I am welding mild steel that is 16 ga")
    assert session.current_thickness == "16ga"


def test_session_manager_records_safety_warnings() -> None:
    mgr = SessionManager()
    session = mgr.get_or_create("s5")
    mgr.record_safety_warning(session, "electrical")
    payload = session.to_dict()
    assert payload["safety_warnings_shown"] == ["electrical"]


def test_session_manager_appends_and_trims_history() -> None:
    mgr = SessionManager(max_history_messages=4)
    session = mgr.get_or_create("s6")
    mgr.append_turn(session, "u1", "a1")
    mgr.append_turn(session, "u2", "a2")
    mgr.append_turn(session, "u3", "a3")
    history = mgr.get_message_history(session)
    assert len(history) == 4
    assert history[0]["content"] == "u2"
    assert history[-1]["content"] == "a3"


def test_session_manager_expires_old_sessions() -> None:
    mgr = SessionManager(max_age_seconds=10)
    session = mgr.get_or_create("expired")
    session.last_seen_at = datetime.now(timezone.utc) - timedelta(seconds=20)
    assert mgr.get("expired") is None
