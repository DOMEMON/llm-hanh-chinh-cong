import hashlib
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.rag.g5.source_mcp import (
    MCPSourceUpdateClient,
    PublishedSourceUpdate,
    apply_source_updates,
)
from app.rag.schemas import Evidence, EvidenceBundle


def _bundle():
    return EvidenceBundle(
        request_id=uuid4(),
        evidence_bundle_id=uuid4(),
        corpus_version="fixture-v1",
        data_classification="D2_COMPANY_REAL",
        query="Lệ phí thủ tục alpha?",
        evidence=[
            Evidence(
                fragment_id="old-fee",
                source_id="old-source",
                procedure_id="procedure-alpha",
                section_type="FEES",
                title="Nguồn cũ",
                url=None,
                text="Không thu phí.",
                score=1,
                validity_status="CURRENT",
                metadata={"source_type": "COMPANY_INTERNAL_WORKBOOK"},
            )
        ],
    )


class FakeSourceClient:
    def __init__(self, update):
        self.update = update

    async def get_update(self, **_kwargs):
        return self.update


@pytest.mark.asyncio
async def test_published_update_replaces_field_and_manifest_atomically():
    text = "Lệ phí mới: 10.000 đồng."
    update = PublishedSourceUpdate(
        snapshot_id="g5-snapshot-" + "a" * 32,
        version="g5-source-v000001",
        procedure_id="procedure-alpha",
        field="fees",
        section_type="FEES",
        text=text,
        title="Nguồn phí mới",
        source_url="https://example.invalid/source",
        effective_from="2026-01-01",
        effective_to=None,
        content_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        status="PUBLISHED",
        created_at=datetime.now(timezone.utc),
        reviewed_at=datetime.now(timezone.utc),
        reviewer="Hoan",
        published_at=datetime.now(timezone.utc),
    )
    bundle, manifest = await apply_source_updates(
        _bundle(),
        fields=["fees"],
        field_evidence={"fees": ["old-fee"]},
        client=FakeSourceClient(update),
    )
    assert [item.fragment_id for item in bundle.evidence] == [update.snapshot_id]
    assert bundle.evidence[0].metadata["source_version"] == update.version
    assert manifest["fees"] == [update.snapshot_id]


@pytest.mark.asyncio
async def test_future_update_is_not_served():
    text = "Nội dung tương lai."
    update = PublishedSourceUpdate(
        snapshot_id="g5-snapshot-" + "a" * 32,
        version="g5-source-v000001",
        procedure_id="procedure-alpha",
        field="fees",
        section_type="FEES",
        text=text,
        title="Nguồn tương lai",
        source_url=None,
        effective_from="2099-01-01",
        effective_to=None,
        content_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        status="PUBLISHED",
        created_at=datetime.now(timezone.utc),
        reviewed_at=datetime.now(timezone.utc),
        reviewer="Hoan",
        published_at=datetime.now(timezone.utc),
    )
    bundle, manifest = await apply_source_updates(
        _bundle(),
        fields=["fees"],
        field_evidence={"fees": ["old-fee"]},
        client=FakeSourceClient(update),
    )
    assert bundle.evidence[0].fragment_id == "old-fee"
    assert manifest["fees"] == ["old-fee"]


@pytest.mark.asyncio
async def test_tampered_update_is_rejected_before_it_can_replace_evidence():
    now = datetime.now(timezone.utc)
    with pytest.raises(ValueError, match="G5_SOURCE_CONTENT_HASH_MISMATCH"):
        PublishedSourceUpdate(
            snapshot_id="g5-snapshot-" + "a" * 32,
            version="g5-source-v000001",
            procedure_id="procedure-alpha",
            field="fees",
            section_type="FEES",
            text="Ná»™i dung Ä‘Ã£ bá»‹ thay Ä‘á»•i.",
            title="Nguá»“n",
            source_url=None,
            effective_from="2026-01-01",
            effective_to=None,
            content_sha256="b" * 64,
            status="PUBLISHED",
            created_at=now,
            reviewed_at=now,
            reviewer="Hoan",
            published_at=now,
        )


def test_mcp_source_client_rejects_untrusted_endpoint():
    with pytest.raises(ValueError, match="G5_SOURCE_MCP_URL_NOT_ALLOWED"):
        MCPSourceUpdateClient(url="https://example.com/mcp")
    with pytest.raises(ValueError, match="G5_SOURCE_MCP_ENDPOINT_REQUIRED"):
        MCPSourceUpdateClient(url="http://localhost:8091/not-mcp")


@pytest.mark.parametrize(
    "patch",
    [
        {},
        {"procedure_id": "wrong"},
        {"field": "fees"},
        {"jurisdiction": "other"},
        {"source_url": "https://evil.example"},
        {"source_title": "other"},
        {"checked_at": "2000-01-01T00:00:00Z"},
        {"extra_key": True},
    ],
)
async def test_current_lookup_validates_wire_payload(monkeypatch, patch):
    from types import SimpleNamespace

    from app.rag.g5 import source_mcp
    from app.rag.g5.realtime_contract import LookupRequest

    request = LookupRequest(
        procedure_id="alpha",
        procedure_name="Alpha",
        field="processing_times",
        jurisdiction="Test Ward",
        as_of=datetime.now(timezone.utc).date(),
    )
    payload = (
        dict(
            status="FOUND",
            procedure_id="alpha",
            field="processing_times",
            value="3 days",
            source_title="Alpha",
            source_url="https://dichvucong.gov.vn/a",
            jurisdiction="Test Ward",
            checked_at=datetime.now(timezone.utc).isoformat(),
            retrieval_note="fixture",
        )
        | patch
    )

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def call_tool(self, name, args, **kwargs):
            assert name == "lookup_current_procedure"
            assert args == request.model_dump(mode="json")
            return SimpleNamespace(is_error=False, structured_content={"result": payload})

    monkeypatch.setattr(source_mcp, "Client", FakeClient)
    client = MCPSourceUpdateClient(url="http://source-service:8091/mcp")
    result = await client.lookup_current(request)
    assert (result is not None) == (not patch)


async def test_current_client_transport_timeout_falls_back(monkeypatch):
    import asyncio

    from app.rag.g5 import source_mcp
    from app.rag.g5.realtime_contract import LookupRequest

    class SlowClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            await asyncio.sleep(1)

        async def __aexit__(self, *args):
            pass

    monkeypatch.setattr(source_mcp, "Client", SlowClient)
    client = MCPSourceUpdateClient(url="http://source-service:8091/mcp", timeout_seconds=0.001)
    assert (
        await client.lookup_current(
            LookupRequest(
                procedure_id="a",
                procedure_name="A",
                field="fees",
                jurisdiction="ward",
                as_of=datetime.now(timezone.utc).date(),
            )
        )
        is None
    )
