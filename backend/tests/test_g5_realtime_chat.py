"""Exercise send_message orchestration with an in-memory DB double (no PostgreSQL)."""

from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app import chat
from app.config import get_settings
from app.models import Message
from app.rag.g5.intent_context import IntentContextState
from app.rag.g5.realtime import OFFER
from app.rag.g5.realtime_contract import LookupResult
from app.schemas import MessageInput


@pytest.mark.parametrize("reply, expected_calls", [("đồng ý", 1), ("không", 0)])
async def test_send_message_consent_and_idempotent_retry(monkeypatch, reply, expected_calls):
    conversation = SimpleNamespace(id=uuid4(), rag_context=None, updated_at=None)
    messages = []
    committed_states = []

    class DB:
        def add(self, message):
            message.id = uuid4()
            message.created_at = datetime.now(timezone.utc)
            messages.append(message)

        async def commit(self):
            committed_states.append(deepcopy(conversation.rag_context))

        async def scalar(self, query):
            params = query.compile().params
            if "client_message_id_1" in params:
                return next(
                    (
                        m
                        for m in messages
                        if m.role == "user" and m.client_message_id == params["client_message_id_1"]
                    ),
                    None,
                )
            if "request_id_1" in params:
                return next(
                    (
                        m
                        for m in messages
                        if m.role == "assistant" and m.request_id == params["request_id_1"]
                    ),
                    None,
                )
            return next(m.id for m in reversed(messages) if m.role == "user")

        async def scalars(self, query):
            return SimpleNamespace(all=lambda: list(reversed(messages)))

    db = DB()

    @asynccontextmanager
    async def lock(_):
        yield db

    monkeypatch.setattr(chat, "conversation_lock", lock)
    monkeypatch.setattr(chat, "owned_conversation", AsyncMock(return_value=conversation))
    settings = get_settings()
    for key, value in dict(
        rag_enabled=True,
        g3_d2_enabled=True,
        g5_intent_context_enabled=True,
        g5_realtime_mcp_enabled=True,
        g5_hybrid_enabled=False,
        g5_intent_context_fallback_enabled=False,
        g3_private_dataset_path="fixture",
        rag_corpus_version="fixture-v1",
    ).items():
        monkeypatch.setattr(settings, key, value)
    data = SimpleNamespace(
        version="fixture-v1", accepted={"alpha"}, procedures={"alpha": {"title": "Alpha"}}
    )
    monkeypatch.setattr(chat, "load_active_dataset", lambda *args: data)
    monkeypatch.setattr(
        chat,
        "decide_topic",
        AsyncMock(return_value=SimpleNamespace(action="KEEP", reason="fixture")),
    )

    def prepare(data, query, *args, **kwargs):
        return (
            query,
            IntentContextState(
                corpus_version="fixture-v1",
                procedure_id="alpha",
                field_intents=["processing_times"],
                jurisdiction="Phường Mô Phỏng",
            ),
            None,
        )

    monkeypatch.setattr(chat, "prepare_model_turn", prepare)
    local_grounding = dict(
        request_id=str(uuid4()),
        evidence_bundle_id=str(uuid4()),
        status="ANSWER",
        corpus_version="fixture-v1",
        data_classification="D2_COMPANY_REAL",
        sources=[],
        missing_information=[],
        checklist=[
            dict(
                field="processing_times",
                label="Thời hạn",
                value="LOCAL",
                evidence_ids=["fixture-1"],
            )
        ],
    )
    monkeypatch.setattr(chat, "answer_with_rag", AsyncMock(return_value=("LOCAL", local_grounding)))
    calls = []

    async def lookup(self, request):
        assert committed_states[-1]["pending_realtime"] is None
        calls.append(request)
        return LookupResult(
            status="FOUND",
            procedure_id="alpha",
            field="processing_times",
            jurisdiction="Phường Mô Phỏng",
            checked_at=datetime.now(timezone.utc),
            value="WEB VALUE",
            source_title="Alpha",
            source_url="https://dichvucong.gov.vn/x",
            retrieval_note="fictional fixture",
        )

    monkeypatch.setattr(chat.MCPSourceUpdateClient, "lookup_current", lookup)
    ai = SimpleNamespace(analyze_intent_context=AsyncMock(return_value={}))
    user_id = uuid4()
    first = await chat.send_message(
        conversation.id,
        user_id,
        MessageInput(client_message_id=uuid4(), content="Alpha bao lâu?"),
        uuid4(),
        ai,
    )
    assert OFFER in first.assistant_message.content
    assert len(calls) == 0
    assert conversation.rag_context["pending_realtime"]["request"]["field"] == "processing_times"
    body = MessageInput(client_message_id=uuid4(), content=reply)
    second = await chat.send_message(conversation.id, user_id, body, uuid4(), ai)
    assert len(calls) == expected_calls
    assert ai.analyze_intent_context.await_count == 1
    assert conversation.rag_context["pending_realtime"] is None
    assert "LOCAL" in second.assistant_message.content
    retry = await chat.send_message(conversation.id, user_id, body, uuid4(), ai)
    assert retry.assistant_message.id == second.assistant_message.id
    assert len(calls) == expected_calls
    if calls:
        assert calls[0].procedure_id == "alpha"
        assert calls[0].field == "processing_times"
        assert "WEB VALUE" in second.assistant_message.content
    assert all(isinstance(m, Message) for m in messages)
