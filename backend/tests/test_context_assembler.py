from app.context.assembler import ContextAssembler
from app.packs.registry import get_product_registry
from app.session.manager import Session


def test_context_assembler_routes_exact_tool_queries() -> None:
    runtime = get_product_registry().require_product("vulcan-omnipro-220")
    session = Session(id="test", product_id=runtime.id, product_name=runtime.product_name)

    bundle = ContextAssembler().assemble(
        "What is the duty cycle for MIG on 240v?",
        session,
        runtime,
    )

    assert bundle.strategy == "exact_tool"
    assert "lookup_duty_cycle" in bundle.exact_tool_candidates


def test_context_assembler_returns_retrieval_context_for_open_questions() -> None:
    runtime = get_product_registry().require_product("vulcan-omnipro-220")
    session = Session(id="test", product_id=runtime.id, product_name=runtime.product_name)

    bundle = ContextAssembler().assemble(
        "How should I prepare the machine before starting?",
        session,
        runtime,
    )

    assert bundle.strategy == "retrieval"
    assert bundle.retrieved_chunks

