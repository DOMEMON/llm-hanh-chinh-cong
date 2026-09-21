"""Backend-owned one-shot consent. No model can authorize a current lookup."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import quote

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.rag.catalog_policy import needs_realtime_offer
from app.rag.g5.realtime_contract import LookupRequest

OFFER = "Bạn có muốn kiểm tra thông tin hiện tại trên Cổng DVC Quốc gia không?"
YES = {
    "có",
    "co",
    "đồng ý",
    "dong y",
    "ok",
    "okay",
    "kiểm tra đi",
    "kiem tra di",
    "có kiểm tra đi",
    "yes",
    "vâng",
    "vang",
    "ừ",
    "ừ kiểm tra đi",
}
NO = {"không", "khong", "không cần", "khong can", "thôi", "thoi", "no"}
FIELD_LABELS = {
    "processing_times": "thời hạn giải quyết",
    "receiving_authority": "cơ quan tiếp nhận",
    "submission_methods": "cách thức nộp",
    "required_documents": "thành phần hồ sơ",
    "fees": "phí/lệ phí",
    "steps": "trình tự thực hiện",
    "legal_bases": "căn cứ pháp lý",
    "applicant_scope": "đối tượng thực hiện",
}


class PendingLookup(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request: LookupRequest
    offered_at: AwareDatetime
    local_answer: str = Field(max_length=40000)
    local_grounding: dict | None = None


def decision(text: str) -> str | None:
    clean = " ".join(text.casefold().strip().strip(".!? ").split())
    return "yes" if clean in YES else "no" if clean in NO else None


def consume(state, text, filters, *, enabled):
    """Consume before any I/O; unknown replies/topic/filter changes invalidate the offer."""
    pending = state.pending_realtime
    state.pending_realtime = None
    if not pending or not enabled:
        return None, None
    age = (datetime.now(timezone.utc) - pending.offered_at).total_seconds()
    if not 0 <= age <= 900 or pending.request.as_of != datetime.now(timezone.utc).date():
        return None, None
    if (
        filters.procedure_id
        and filters.procedure_id != pending.request.procedure_id
        or filters.jurisdiction
        and filters.jurisdiction != pending.request.jurisdiction
        or filters.as_of
        and filters.as_of != pending.request.as_of
    ):
        return None, None
    action = decision(text)
    return (action, pending) if action else (None, None)


def offer(state, data, answer, grounding, *, enabled):
    state.pending_realtime = None
    if not enabled or not state.procedure_id or not grounding:
        return answer
    procedure = data.procedures.get(state.procedure_id)
    if not procedure or not state.jurisdiction:
        return answer
    today = datetime.now(timezone.utc).date()
    if state.as_of and state.as_of != today:
        return answer
    requested = list(state.field_intents)
    present = {x.get("field") for x in grounding.get("checklist") or [] if isinstance(x, dict)}
    missing = set(requested) - present
    if not needs_realtime_offer(state.procedure_id, set(requested), local_missing=bool(missing)):
        return answer
    candidates = [
        f
        for f in requested
        if f in FIELD_LABELS and (f in {"processing_times", "receiving_authority"} or f in missing)
    ]
    if not candidates:
        return answer
    selected = candidates[0]
    state.pending_realtime = PendingLookup(
        request=LookupRequest(
            procedure_id=state.procedure_id,
            procedure_name=procedure["title"],
            field=selected,
            jurisdiction=state.jurisdiction,
            as_of=today,
        ),
        offered_at=datetime.now(timezone.utc),
        local_answer=answer,
        local_grounding=grounding,
    )
    return (
        answer + f"\n\nMục cần kiểm tra: {FIELD_LABELS[selected]} — "
        f"{procedure['title']} ({state.jurisdiction}).\n" + OFFER
    )


def literal(text):
    # Remote text is displayed as data, never sent into the model or rendered as raw HTML.
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return re.sub(r"([\\`*_{}\[\]()#+.!|>~-])", r"\\\1", text)


async def resolve(pending, action, client):
    if action == "no":
        return "Đã bỏ qua kiểm tra trực tuyến.\n\n" + pending.local_answer, pending.local_grounding
    result = await client.lookup_current(pending.request) if client is not None else None
    if result is None or result.status != "FOUND":
        return (
            "Chưa xác minh được thông tin hiện tại trên Cổng DVC Quốc gia. "
            "Thông tin local đã duyệt vẫn được giữ nguyên:\n\n" + pending.local_answer,
            pending.local_grounding,
        )
    answer = (
        pending.local_answer + "\n\nThông tin vừa tra cứu trên Cổng DVC Quốc gia "
        "(chưa qua review nội bộ):\n"
        + literal(result.value)
        + "\n\n"
        + f"Nguồn: [{literal(result.source_title)}]({quote(result.source_url, safe=':/?=&%')})"
        + f"\nĐịa phương: {literal(result.jurisdiction)}"
        + f"\nThời điểm kiểm tra: {result.checked_at.isoformat()}"
    )
    # Keep the local evidence bundle intact; the web citation is explicit in the text.
    return answer, pending.local_grounding
