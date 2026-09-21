import asyncio
import io
import time
from datetime import datetime, timezone
from email.message import Message
from urllib.error import HTTPError

import pytest
from pydantic import ValidationError

from app import current_procedure as cp
from app.realtime_contract import LookupRequest, LookupResult, official_url

TITLE = "Đăng ký Alpha"
URL = "https://thutuc.dichvucong.gov.vn/p/detail?id=1"
DETAIL = """<h1>Đăng ký Alpha</h1><dl>
<dt>Địa phương:</dt><dd>Phường Mô Phỏng</dd>
<dt>Thời hạn giải quyết:</dt><dd>03 ngày làm việc</dd>
<dt>Cơ quan thực hiện:</dt><dd>UBND Phường Mô Phỏng</dd></dl>"""
INDEX = f'<a href="{URL}">{TITLE}</a>'


def request(**changes):
    return LookupRequest(
        **(
            dict(
                procedure_id="internal-alpha",
                procedure_name=TITLE,
                field="processing_times",
                jurisdiction="Phường Mô Phỏng",
                as_of=datetime.now(timezone.utc).date(),
            )
            | changes
        )
    )


def run(pages=None, **kwargs):
    pages = pages or {cp.ENTRY_URL: INDEX, URL: DETAIL}
    calls = []

    def fetch(url, timeout):
        calls.append(url)
        assert timeout > 0
        return url, pages[url]

    result = asyncio.run(cp.lookup(request(), enabled=True, fetch=fetch, **kwargs))
    return result, calls


def test_found():
    result, calls = run()
    assert result.status == "FOUND"
    assert result.value == "03 ngày làm việc"
    assert result.procedure_id == "internal-alpha"
    assert result.source_url == URL
    assert len(calls) == 2
    assert result.checked_at.tzinfo


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example/dvc",
        "https://dichvucong.gov.vn.evil.example/a",
        "https://dichvucong.gov.vn@evil.example/a",
        "http://dichvucong.gov.vn/a",
        "https://dichvucong.gov.vn:8443/a",
        "https://user@dichvucong.gov.vn/a",
        "https://dichvucong.gov.vn/a#fragment",
        "file:///etc/passwd",
        "https://127.0.0.1/a",
        "https://dichvucong.gov.vn/\na",
        "https://dichvucong.gov.vn\\@evil.example/",
    ],
)
def test_url_allowlist(url):
    with pytest.raises(ValueError):
        official_url(url)


@pytest.mark.parametrize(
    "host",
    [
        "dichvucong.gov.vn",
        "www.dichvucong.gov.vn",
        "thutuc.dichvucong.gov.vn",
        "vpcp.dichvucong.gov.vn",
    ],
)
def test_allowed_hosts(host):
    assert official_url(f"https://{host}/x")


def test_advertised_get_form():
    form = '<form action="/search" method="get"><input name="q" type="search"></form>'
    search = cp.Page(form).search_url(cp.ENTRY_URL, TITLE)
    result, calls = run({cp.ENTRY_URL: form, search: INDEX, URL: DETAIL})
    assert result.status == "FOUND"
    assert calls[1] == search


@pytest.mark.parametrize(
    "change",
    [
        DETAIL.replace("Phường Mô Phỏng", "Phường Khác"),
        DETAIL.replace(TITLE, "Đăng ký Beta"),
        DETAIL.replace("Thời hạn giải quyết", "Nội dung khác"),
    ],
)
def test_wrong_scope_identity_or_field(change):
    result, _ = run({cp.ENTRY_URL: INDEX, URL: change})
    assert result.status == "NOT_FOUND"
    assert result.value is None


def test_ambiguous():
    other = URL + "2"
    result, _ = run(
        {cp.ENTRY_URL: INDEX + f'<a href="{other}">{TITLE}</a>', URL: DETAIL, other: DETAIL}
    )
    assert result.status == "AMBIGUOUS"


def test_js_only():
    result, _ = run({cp.ENTRY_URL: "<script>renderSearch()</script>"})
    assert result.status == "NOT_FOUND"
    assert "JS_SEARCH_REQUIRED" in result.retrieval_note


def test_external_link_not_requested():
    result, calls = run({cp.ENTRY_URL: f'<a href="https://evil.example/x">{TITLE}</a>'})
    assert result.status == "ERROR"
    assert calls == [cp.ENTRY_URL]


def test_disabled_and_historical():
    def never(*args):
        pytest.fail("must not fetch")

    assert asyncio.run(cp.lookup(request(), fetch=never)).status == "ERROR"
    assert (
        asyncio.run(cp.lookup(request(as_of="2000-01-01"), enabled=True, fetch=never)).status
        == "NOT_FOUND"
    )


def test_timeout():
    def slow(*args):
        time.sleep(0.04)
        return cp.ENTRY_URL, INDEX

    result = asyncio.run(cp.lookup(request(), enabled=True, timeout=0.005, fetch=slow))
    assert result.status == "ERROR"
    assert result.retrieval_note == "DVC_TIMEOUT"


def test_sanitized_failure():
    def broken(*args):
        raise RuntimeError("secret remote response")

    result = asyncio.run(cp.lookup(request(), enabled=True, fetch=broken))
    assert result.status == "ERROR"
    assert "secret" not in result.model_dump_json()


def test_schema():
    result, _ = run()
    for patch in [
        {"source_url": None},
        {"source_url": "https://evil.example"},
        {"unexpected": True},
        {"checked_at": "2026-01-01T00:00:00"},
        {"status": "ERROR"},
    ]:
        with pytest.raises(ValidationError):
            LookupResult.model_validate(result.model_dump() | patch)


def test_redirect_external_blocked_before_request(monkeypatch):
    calls = []

    class Opener:
        def open(self, req, timeout):
            calls.append(req.full_url)
            headers = Message()
            headers["Location"] = "https://evil.example/private"
            raise HTTPError(req.full_url, 302, "redirect", headers, io.BytesIO())

    monkeypatch.setattr(cp, "build_opener", lambda *args: Opener())
    with pytest.raises(ValueError, match="DVC_URL_NOT_ALLOWED"):
        cp.fetch_html(cp.ENTRY_URL)
    assert calls == [cp.ENTRY_URL]


def test_tool_default_off(monkeypatch):
    from app.server import lookup_current_procedure

    monkeypatch.delenv("G5_REALTIME_MCP_ENABLED", raising=False)
    result = asyncio.run(lookup_current_procedure(**request().model_dump(mode="json")))
    assert result.retrieval_note == "DVC_REALTIME_DISABLED"


def test_table_column_extraction_preserves_submission_channel():
    html = """<table><tr><th>Hình thức nộp</th><th>Thời hạn giải quyết</th><th>Lệ phí</th></tr>
    <tr><td>Trực tiếp</td><td>03 ngày</td><td>0 đồng</td></tr>
    <tr><td>Trực tuyến</td><td>02 ngày</td><td>0 đồng</td></tr></table>"""
    assert cp.Page(html).labelled(("Thời hạn giải quyết",)) == [
        "Trực tiếp: 03 ngày",
        "Trực tuyến: 02 ngày",
    ]


def test_complex_html_rejected():
    with pytest.raises(ValueError, match="COMPLEXITY"):
        cp.Page("<div>" * 100)


def test_wire_contract_copies_match():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    assert (root / "source-service/app/realtime_contract.py").read_bytes() == (
        root / "backend/app/rag/g5/realtime_contract.py"
    ).read_bytes()


def test_allowed_redirect_and_body_limit(monkeypatch):
    calls = []

    class Response(io.BytesIO):
        def __init__(self, data):
            super().__init__(data)
            self.headers = Message()
            self.headers["Content-Type"] = "text/html; charset=utf-8"

        def geturl(self):
            return URL

    class Opener:
        def open(self, req, timeout):
            calls.append(req.full_url)
            if len(calls) == 1:
                headers = Message()
                headers["Location"] = URL
                raise HTTPError(req.full_url, 302, "redirect", headers, io.BytesIO())
            return Response(b"x" * (cp.MAX_BYTES + 1))

    monkeypatch.setattr(cp, "build_opener", lambda *args: Opener())
    with pytest.raises(ValueError, match="TOO_LARGE"):
        cp.fetch_html(cp.ENTRY_URL)
    assert calls == [cp.ENTRY_URL, URL]


def test_navigation_locality_is_not_procedure_evidence():
    html = """<h1>Đăng ký Alpha</h1><nav><dl>
    <dt>Địa phương</dt><dd>Phường Mô Phỏng</dd></dl></nav>
    <dl><dt>Thời hạn giải quyết</dt><dd>3 ngày</dd></dl>"""
    assert cp.extract(cp.Page(html), request(), URL) is None
