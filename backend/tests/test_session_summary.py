import json

from app.packs.registry import get_product_registry
from app.session.manager import Session
from app.session.summary import persist_session_summary


def test_persist_session_summary_writes_product_scoped_record() -> None:
    runtime = get_product_registry().require_product("vulcan-omnipro-220")
    session = Session(id="summary-test", product_id=runtime.id, product_name=runtime.product_name)
    session.message_history = [
        {"role": "user", "content": "Help me set up MIG."},
        {"role": "assistant", "content": "Let's walk through MIG setup."},
    ]
    session.current_process = "mig"

    record = persist_session_summary(runtime, session)

    assert record.product_id == runtime.id
    path = runtime.conversations_dir / "summary-test.summary.json"
    assert path.exists()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["product_id"] == runtime.id
    assert "mig" in payload["summary"].lower()

    path.unlink()

