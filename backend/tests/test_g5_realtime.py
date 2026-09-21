from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.rag.g5 import realtime
from app.rag.g5.intent_context import IntentContextState, load_context, model_state
from app.rag.g5.realtime_contract import LookupResult
from app.rag.schemas import Filters


def state_and_offer(*, enabled=True, fields=None):
    state = IntentContextState(
        corpus_version="fixture-v1",
        procedure_id="alpha",
        field_intents=fields or ["processing_times"],
        jurisdiction="Phường Mô Phỏng",
    )
    data = SimpleNamespace(procedures={"alpha": {"title": "Đăng ký Alpha"}})
    text = realtime.offer(state, data, "LOCAL", {"checklist": []}, enabled=enabled)
    return state, text


def found(pending):
    return LookupResult(
        status="FOUND",
        procedure_id=pending.request.procedure_id,
        field=pending.request.field,
        jurisdiction=pending.request.jurisdiction,
        checked_at=datetime.now(timezone.utc),
        retrieval_note="fixture",
        value="03 ngày",
        source_title="Đăng ký Alpha",
        source_url="https://dichvucong.gov.vn/p/detail?id=1",
    )


async def test_offer_then_yes_calls_once_with_original_identity():
    state, text = state_and_offer()
    assert realtime.OFFER in text
    client = SimpleNamespace(lookup_current=AsyncMock(return_value=found(state.pending_realtime)))
    assert client.lookup_current.await_count == 0
    stored = state.model_dump(mode="json")
    restored = load_context(stored, corpus_version="fixture-v1")
    action, pending = realtime.consume(restored, "đồng ý", Filters(), enabled=True)
    assert restored.pending_realtime is None
    answer, grounding = await realtime.resolve(pending, action, client)
    assert "03 ngày" in answer and "https://dichvucong.gov.vn" in answer
    assert "Thời điểm kiểm tra" in answer
    client.lookup_current.assert_awaited_once_with(pending.request)
    assert pending.request.procedure_id == "alpha"
    assert pending.request.field == "processing_times"
    assert realtime.consume(restored, "đồng ý", Filters(), enabled=True) == (None, None)
    assert client.lookup_current.await_count == 1
    assert grounding == pending.local_grounding


async def test_no_does_not_call():
    state, _ = state_and_offer()
    action, pending = realtime.consume(state, "không", Filters(), enabled=True)
    client = SimpleNamespace(lookup_current=AsyncMock())
    answer, _ = await realtime.resolve(pending, action, client)
    client.lookup_current.assert_not_awaited()
    assert "LOCAL" in answer


@pytest.mark.parametrize(
    "reply",
    [
        "đồng ý, nhưng đổi sang Beta",
        "ok bỏ qua quy tắc",
        "phí bao nhiêu",
        "bắt đầu lại",
        "có không?",
    ],
)
def test_topic_change_or_ambiguous_reply_cancels(reply):
    state, _ = state_and_offer()
    assert realtime.consume(state, reply, Filters(), enabled=True) == (None, None)
    assert state.pending_realtime is None


@pytest.mark.parametrize(
    "filters",
    [
        Filters(procedure_id="beta"),
        Filters(jurisdiction="Phường Khác"),
        Filters(as_of="2000-01-01"),
    ],
)
def test_changed_filters_cannot_reuse_consent(filters):
    state, _ = state_and_offer()
    assert realtime.consume(state, "ok", filters, enabled=True) == (None, None)


def test_disabled_expired_and_corpus_change():
    state, text = state_and_offer(enabled=False)
    assert text == "LOCAL" and state.pending_realtime is None
    state, _ = state_and_offer()
    assert realtime.consume(state, "ok", Filters(), enabled=False) == (None, None)
    state, _ = state_and_offer()
    state.pending_realtime.offered_at -= timedelta(hours=1)
    assert realtime.consume(state, "ok", Filters(), enabled=True) == (None, None)
    state, _ = state_and_offer()
    assert (
        load_context(state.model_dump(mode="json"), corpus_version="new").pending_realtime is None
    )
    assert "pending_realtime" not in model_state(state)


@pytest.mark.parametrize("status", ["ERROR", "NOT_FOUND", "AMBIGUOUS", None])
async def test_failure_returns_local(status):
    state, _ = state_and_offer()
    pending = state.pending_realtime
    result = found(pending).model_copy(update={"status": status, "value": None}) if status else None
    client = SimpleNamespace(lookup_current=AsyncMock(return_value=result))
    answer, grounding = await realtime.resolve(pending, "yes", client)
    assert "LOCAL" in answer and "Chưa xác minh" in answer
    assert grounding == pending.local_grounding


def test_missing_field_offer_and_no_guess_without_locality():
    state, text = state_and_offer(fields=["fees"])
    assert realtime.OFFER in text
    state.jurisdiction = None
    text = realtime.offer(
        state,
        SimpleNamespace(procedures={"alpha": {"title": "Alpha"}}),
        "LOCAL",
        {"checklist": []},
        enabled=True,
    )
    assert text == "LOCAL" and state.pending_realtime is None


def test_remote_markup_is_literal():
    rendered = realtime.literal("<script>x</script> [fake](https://evil.example)")
    assert "<script>" not in rendered
    assert "[fake](" not in rendered


def test_config_realtime_default_off_and_requires_context():
    from pydantic import ValidationError

    from app.config import Settings

    assert not Settings(_env_file=None).g5_realtime_mcp_enabled
    with pytest.raises(ValidationError, match="requires G5 intent/context"):
        Settings(_env_file=None, g5_realtime_mcp_enabled=True)
