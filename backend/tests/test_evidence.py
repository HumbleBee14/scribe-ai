"""Tests for evidence model and structured data access."""
import pytest

from app.knowledge.evidence import (
    ArtifactSpec,
    Citation,
    EvidencePayload,
    SourceRef,
)
from app.knowledge.structured import StructuredStore, StructuredStoreError

# --- Evidence model tests ---


def test_citation_supports_page_region() -> None:
    citation = Citation(
        document="owner-manual",
        page=18,
        type="page_region",
        bbox=[72, 166, 452, 518],
        crop_url="/assets/crops/p18-polarity.png",
        exactness="native_pdf",
    )
    assert citation.type == "page_region"
    assert citation.exactness == "native_pdf"
    assert citation.bbox == [72, 166, 452, 518]


def test_citation_with_typed_source_refs() -> None:
    citation = Citation(
        document="owner-manual",
        page=24,
        type="figure",
        source_refs=[SourceRef(page=24, description="TIG polarity diagram")],
    )
    assert citation.source_refs is not None
    assert citation.source_refs[0].page == 24
    assert citation.source_refs[0].description == "TIG polarity diagram"


def test_citation_minimal() -> None:
    citation = Citation(document="owner-manual", page=7, type="text_block")
    assert citation.page == 7
    assert citation.bbox is None
    assert citation.exactness is None


def test_artifact_spec_typed() -> None:
    artifact = ArtifactSpec(
        id="art_12345",
        renderer="svg",
        title="TIG Polarity Setup",
        code="<svg>...</svg>",
        source_pages=[SourceRef(page=24, description="TIG polarity setup")],
    )
    assert artifact.renderer == "svg"
    assert artifact.title == "TIG Polarity Setup"
    assert artifact.source_pages[0].page == 24


def test_evidence_payload_shape() -> None:
    payload = EvidencePayload(
        answer="For TIG, use DCEN polarity.",
        citations=[
            Citation(document="owner-manual", page=24, type="page_region")
        ],
    )
    assert len(payload.citations) == 1
    assert payload.artifact is None


def test_evidence_payload_with_typed_artifact() -> None:
    payload = EvidencePayload(
        answer="Here is the polarity diagram.",
        citations=[Citation(document="owner-manual", page=24, type="figure")],
        artifact=ArtifactSpec(
            id="art_00001",
            renderer="svg",
            title="TIG Polarity Setup",
            code="<svg>...</svg>",
            source_pages=[SourceRef(page=24, description="TIG polarity setup")],
        ),
    )
    assert payload.artifact is not None
    assert payload.artifact.renderer == "svg"
    assert payload.artifact.source_pages[0].page == 24


# --- Structured store tests ---


def test_structured_store_loads_specs() -> None:
    store = StructuredStore()
    specs = store.get_specs("mig", "240v")
    assert specs is not None
    assert specs["welding_current_range"] == "30-220A"


def test_structured_store_specs_include_process_metadata() -> None:
    """Fix 4: get_specs merges process-level metadata into voltage-specific result."""
    store = StructuredStore()
    specs = store.get_specs("mig", "240v")
    assert specs is not None
    assert "weldable_materials" in specs
    assert "Mild Steel" in specs["weldable_materials"]


def test_structured_store_loads_duty_cycle() -> None:
    store = StructuredStore()
    dc = store.get_duty_cycle("mig", "240v")
    assert dc is not None
    assert dc["rated"]["duty_cycle_percent"] == 25
    assert dc["rated"]["amperage"] == 200
    assert dc["rated"]["weld_minutes"] == 2.5
    assert dc["rated"]["rest_minutes"] == 7.5


def test_structured_store_loads_polarity() -> None:
    store = StructuredStore()
    pol = store.get_polarity("tig")
    assert pol is not None
    assert pol["polarity_type"] == "DCEN"
    assert pol["ground_clamp_cable"] == "positive"


def test_structured_store_loads_troubleshooting() -> None:
    store = StructuredStore()
    problems = store.get_troubleshooting("mig_flux")
    assert problems is not None
    assert len(problems) > 0
    assert any("Porosity" in p["problem"] for p in problems)


def test_structured_store_loads_safety() -> None:
    store = StructuredStore()
    warnings = store.get_safety("electrical")
    assert warnings is not None
    assert warnings["level"] == "danger"
    assert len(warnings["items"]) > 0


def test_structured_store_fuzzy_troubleshooting() -> None:
    store = StructuredStore()
    matches = store.search_troubleshooting("porosity", "mig_flux")
    assert len(matches) > 0
    assert "Porosity" in matches[0]["problem"]


def test_structured_store_returns_none_for_invalid() -> None:
    store = StructuredStore()
    assert store.get_specs("plasma", "240v") is None
    assert store.get_duty_cycle("plasma", "240v") is None
    assert store.get_polarity("plasma") is None


def test_structured_store_health_check() -> None:
    store = StructuredStore()
    health = store.health_check()
    assert health["healthy"] is True
    assert "specs.json" in health["loaded"]
    assert len(health["missing_required"]) == 0


def test_structured_store_fails_fast_on_missing_required(tmp_path: pytest.TempPathFactory) -> None:
    """Fix 1: Missing required files must raise, not silently return empty dicts."""
    empty_dir = tmp_path / "empty"  # type: ignore[operator]
    empty_dir.mkdir()
    with pytest.raises(StructuredStoreError, match="Required knowledge file missing"):
        StructuredStore(data_dir=empty_dir)
