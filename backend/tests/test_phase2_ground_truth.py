from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SPECS_PATH = REPO_ROOT / "backend" / "app" / "knowledge" / "data" / "specs.json"
PACK_PATH = REPO_ROOT / "data" / "document-packs" / "vulcan-omnipro-220" / "pack.yaml"
EVALS_PATH = (
    REPO_ROOT / "data" / "document-packs" / "vulcan-omnipro-220" / "eval_questions.yaml"
)


def _load_processes_from_pack() -> list[str]:
    text = PACK_PATH.read_text(encoding="utf-8")
    in_processes = False
    processes: list[str] = []

    for line in text.splitlines():
        if line.startswith("processes:"):
            in_processes = True
            continue
        if in_processes and re.match(r"^[a-z_]+:", line):
            break
        if in_processes and line.strip().startswith("- "):
            processes.append(line.strip().removeprefix("- ").strip())

    return processes


def _eval_block(question_id: str) -> str:
    text = EVALS_PATH.read_text(encoding="utf-8")
    match = re.search(
        rf"^- id: {re.escape(question_id)}\n(?P<body>.*?)(?=^- id: |\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert match is not None, f"missing eval block for {question_id}"
    return match.group("body")


def test_specs_cover_all_supported_processes() -> None:
    specs = json.loads(SPECS_PATH.read_text(encoding="utf-8"))
    actual = {key for key in specs.keys() if key != "product" and not key.startswith("_")}
    expected = set(_load_processes_from_pack())
    assert expected.issubset(actual)


def test_flux_cored_porosity_eval_does_not_expect_gas_flow() -> None:
    block = _eval_block("flux-porosity-troubleshoot")
    assert "gas flow" not in block.lower()


def test_eval_tool_names_match_canonical_contract() -> None:
    text = EVALS_PATH.read_text(encoding="utf-8")
    tool_names = re.findall(r"^\s*expected_tool:\s*([a-z_]+)\s*$", text, flags=re.MULTILINE)
    allowed = {
        "lookup_duty_cycle",
        "lookup_polarity",
        "lookup_troubleshooting",
        "lookup_settings",
        "lookup_specifications",
        "lookup_safety_warnings",
        "diagnose_weld",
        "search_manual",
        "get_page_image",
        "clarify_question",
    }
    assert set(tool_names).issubset(allowed)
