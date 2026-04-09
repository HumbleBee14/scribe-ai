"""Tests for agent tools — exact-data lookups and validation."""
from app.agent.tools import TOOL_DEFINITIONS, execute_tool

# --- Tool registry tests ---

def test_all_tools_registered() -> None:
    names = [t["name"] for t in TOOL_DEFINITIONS]
    expected = [
        "lookup_specifications",
        "lookup_duty_cycle",
        "lookup_polarity",
        "lookup_troubleshooting",
        "lookup_settings",
        "lookup_safety_warnings",
        "clarify_question",
        "search_manual",
        "get_page_image",
        "diagnose_weld",
        "render_artifact",
    ]
    for name in expected:
        assert name in names, f"Missing tool: {name}"


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
