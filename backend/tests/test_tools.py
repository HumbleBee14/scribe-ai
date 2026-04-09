"""Tests for agent tools — exact-data lookups and validation."""
import app.agent.tools as tools_module
from app.agent.tools import (
    DEFERRED_TOOL_DEFINITIONS,
    TOOL_DEFINITIONS,
    execute_tool,
    get_active_tools,
)

# --- Tool registry tests ---


def test_active_tools_have_working_backends() -> None:
    """Active tools should all have real execution handlers, not stubs."""
    active = get_active_tools()
    active_names = [t["name"] for t in active]
    expected_active = [
        "lookup_specifications",
        "lookup_duty_cycle",
        "lookup_polarity",
        "lookup_troubleshooting",
        "lookup_safety_warnings",
        "clarify_question",
        "get_page_image",
        "diagnose_weld",
        "render_artifact",
    ]
    for name in expected_active:
        assert name in active_names, f"Missing active tool: {name}"
    # search_manual should NOT be in active tools (deferred)
    assert "search_manual" not in active_names


def test_deferred_tools_exist() -> None:
    """Deferred tools are defined but not exposed to the agent yet."""
    deferred_names = [t["name"] for t in DEFERRED_TOOL_DEFINITIONS]
    assert "search_manual" in deferred_names
    assert "lookup_settings" in deferred_names


def test_tool_definitions_have_enums() -> None:
    """Verify enum constraints on tool inputs (prevents invalid Claude calls)."""
    for tool in TOOL_DEFINITIONS:
        if tool["name"] == "lookup_duty_cycle":
            props = tool["input_schema"]["properties"]
            assert "enum" in props["process"], "lookup_duty_cycle.process must have enum"
            assert "enum" in props["voltage"], "lookup_duty_cycle.voltage must have enum"
        if tool["name"] == "lookup_polarity":
            props = tool["input_schema"]["properties"]
            assert "enum" in props["process"], "lookup_polarity.process must have enum"


# --- Exact-data tool execution tests ---

def test_lookup_duty_cycle_mig_240v() -> None:
    result = execute_tool("lookup_duty_cycle", {"process": "mig", "voltage": "240v"})
    assert result["rated"]["duty_cycle_percent"] == 25
    assert result["rated"]["amperage"] == 200
    assert result["rated"]["weld_minutes"] == 2.5


def test_lookup_duty_cycle_tig_120v() -> None:
    result = execute_tool("lookup_duty_cycle", {"process": "tig", "voltage": "120v"})
    assert result["rated"]["duty_cycle_percent"] == 40
    assert result["rated"]["amperage"] == 125


def test_lookup_polarity_tig() -> None:
    result = execute_tool("lookup_polarity", {"process": "tig"})
    assert result["polarity_type"] == "DCEN"
    assert result["ground_clamp_cable"] == "positive"
    assert result["tig_torch_cable"] == "negative"


def test_lookup_polarity_flux_cored() -> None:
    result = execute_tool("lookup_polarity", {"process": "flux_cored"})
    assert result["polarity_type"] == "DCEN"
    assert result["wire_feed_power_cable"] == "negative"
    assert result["ground_clamp_cable"] == "positive"


def test_lookup_specifications_mig_240v() -> None:
    result = execute_tool("lookup_specifications", {"process": "mig", "voltage": "240v"})
    assert result["welding_current_range"] == "30-220A"


def test_lookup_troubleshooting_porosity() -> None:
    result = execute_tool(
        "lookup_troubleshooting", {"problem": "porosity", "process": "mig_flux"}
    )
    assert len(result) > 0
    assert "Porosity" in result[0]["problem"]


def test_lookup_settings_is_not_active_until_grounded() -> None:
    active_names = [tool["name"] for tool in get_active_tools()]
    assert "lookup_settings" not in active_names


def test_lookup_safety_electrical() -> None:
    result = execute_tool("lookup_safety_warnings", {"category": "electrical"})
    assert result["level"] == "danger"


def test_lookup_invalid_returns_error() -> None:
    result = execute_tool("lookup_duty_cycle", {"process": "plasma", "voltage": "240v"})
    assert "error" in result


# --- Validation tests ---

def test_validation_rejects_wrong_duty_cycle() -> None:
    from app.validation.service import validate_exact_answer

    result = validate_exact_answer(
        query_type="duty_cycle",
        proposed={"duty_cycle_percent": 30},
        ground_truth={"duty_cycle_percent": 25},
    )
    assert result["valid"] is False


def test_validation_accepts_correct_polarity() -> None:
    from app.validation.service import validate_exact_answer

    result = validate_exact_answer(
        query_type="polarity",
        proposed={"polarity_type": "DCEN"},
        ground_truth={"polarity_type": "DCEN"},
    )
    assert result["valid"] is True


def test_execute_tool_runs_validation_for_exact_duty_cycle(monkeypatch) -> None:
    calls: list[tuple[str, dict, dict]] = []

    def fake_validate(query_type: str, proposed: dict, ground_truth: dict) -> dict:
        calls.append((query_type, proposed, ground_truth))
        return {"valid": True, "reason": "ok", "mismatches": []}

    monkeypatch.setattr(tools_module, "validate_exact_answer", fake_validate, raising=False)
    tools_module._execute_cached.cache_clear()

    result = execute_tool("lookup_duty_cycle", {"process": "mig", "voltage": "240v"})

    assert result["rated"]["duty_cycle_percent"] == 25
    assert calls
    assert calls[0][0] == "duty_cycle"


def test_execute_tool_runs_validation_for_exact_polarity(monkeypatch) -> None:
    calls: list[tuple[str, dict, dict]] = []

    def fake_validate(query_type: str, proposed: dict, ground_truth: dict) -> dict:
        calls.append((query_type, proposed, ground_truth))
        return {"valid": True, "reason": "ok", "mismatches": []}

    monkeypatch.setattr(tools_module, "validate_exact_answer", fake_validate, raising=False)
    tools_module._execute_cached.cache_clear()

    result = execute_tool("lookup_polarity", {"process": "tig"})

    assert result["polarity_type"] == "DCEN"
    assert calls
    assert calls[0][0] == "polarity"
