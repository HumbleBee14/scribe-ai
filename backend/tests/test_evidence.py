"""Tests for evidence model and structured data access."""
from app.knowledge.evidence import Citation, EvidencePayload
from app.knowledge.structured import StructuredStore


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


def test_citation_minimal() -> None:
    citation = Citation(document="owner-manual", page=7, type="text_block")
    assert citation.page == 7
    assert citation.bbox is None
    assert citation.exactness is None


def test_evidence_payload_shape() -> None:
    payload = EvidencePayload(
        answer="For TIG, use DCEN polarity.",
        citations=[
            Citation(document="owner-manual", page=24, type="page_region")
        ],
    )
    assert len(payload.citations) == 1
    assert payload.artifact is None


def test_evidence_payload_with_artifact() -> None:
    payload = EvidencePayload(
        answer="Here is the polarity diagram.",
        citations=[Citation(document="owner-manual", page=24, type="figure")],
        artifact={
            "type": "diagram",
            "renderer": "svg",
            "spec": {"diagramKind": "polarity_setup", "process": "tig"},
            "source_pages": [{"page": 24, "description": "TIG polarity setup"}],
        },
    )
    assert payload.artifact is not None
    assert payload.artifact["type"] == "diagram"


def test_structured_store_loads_specs() -> None:
    store = StructuredStore()
    specs = store.get_specs("mig", "240v")
    assert specs is not None
    assert specs["welding_current_range"] == "30-220A"


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
