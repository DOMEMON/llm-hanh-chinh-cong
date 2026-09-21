"""Bounded, read-only official HTML lookup; never publishes or changes corpus.

Only GET forms actually advertised by the official page are submitted. No undocumented
API or guessed search parameter is used. JS-only pages fail closed, pending a verified
adapter. Exact titles and explicit locality labels are required for FOUND.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.error import HTTPError
from urllib.parse import urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from app.realtime_contract import LookupRequest, LookupResult, official_url

ENTRY_URL = "https://dichvucong.gov.vn/p/home/dvc-tthc-category.html"
MAX_BYTES = 1_048_576
LABELS = {
    "processing_times": ("Thời hạn giải quyết", "Thời gian giải quyết"),
    "receiving_authority": ("Cơ quan thực hiện", "Cơ quan có thẩm quyền", "Cơ quan tiếp nhận"),
    "submission_methods": ("Cách thức thực hiện", "Hình thức nộp"),
    "required_documents": ("Thành phần hồ sơ",),
    "fees": ("Phí", "Lệ phí", "Phí, lệ phí"),
    "steps": ("Trình tự thực hiện",),
    "legal_bases": ("Căn cứ pháp lý",),
    "applicant_scope": ("Đối tượng thực hiện",),
}


def norm(text):
    return " ".join(text.casefold().split()).strip(" :")


@dataclass(eq=False)
class Node:
    tag: str
    attrs: dict = field(default_factory=dict)
    children: list = field(default_factory=list)
    parent: Node | None = None

    def text(self):
        if self.tag in {"script", "style", "noscript", "template", "nav", "footer"}:
            return ""
        return " ".join(
            value.text() if isinstance(value, Node) else value for value in self.children
        ).strip()

    def nodes(self):
        if self.tag in {"script", "style", "noscript", "template", "nav", "footer"}:
            return
        for child in self.children:
            if isinstance(child, Node):
                yield child
                yield from child.nodes()


class Page(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = Node("root")
        self.current = self.root
        self.node_count = 0
        self.depth = 0
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.node_count += 1
        if self.node_count > 12000 or self.depth > 64:
            raise ValueError("DVC_HTML_COMPLEXITY_LIMIT")
        node = Node(tag, dict(attrs), parent=self.current)
        self.current.children.append(node)
        if tag not in {"input", "br", "hr", "meta", "link", "img", "source", "wbr", "area"}:
            self.current = node
            self.depth += 1

    def handle_endtag(self, tag):
        node = self.current
        depth = self.depth
        while node.parent:
            if node.tag == tag:
                self.current = node.parent
                self.depth = depth - 1
                return
            node = node.parent
            depth -= 1

    def handle_data(self, data):
        self.current.children.append(data)

    def labelled(self, labels):
        """Read adjacent labelled content, never search a whole-page text blob."""
        keys = {norm(label) for label in labels}
        found = []
        for node in self.root.nodes():
            if node.tag not in {
                "dt",
                "th",
                "td",
                "label",
                "h2",
                "h3",
                "h4",
                "strong",
                "b",
                "span",
                "div",
                "p",
            }:
                continue
            if norm(node.text()) not in keys or node.parent is None:
                continue
            # Prefer the outer label wrapper, avoiding extraction of the same value twice.
            if norm(node.parent.text()) in keys:
                continue
            if node.tag in {"th", "td"} and node.parent.tag == "tr":
                cells = [
                    n for n in node.parent.children if isinstance(n, Node) and n.tag in {"th", "td"}
                ]
                # A column heading must read the matching column, not the next heading.
                if len(cells) > 1 and all(n.tag == "th" for n in cells):
                    table = node.parent
                    while table.parent and table.tag != "table":
                        table = table.parent
                    column = cells.index(node)
                    for row in table.nodes():
                        if row.tag != "tr" or row is node.parent:
                            continue
                        values = [
                            n for n in row.children if isinstance(n, Node) and n.tag in {"td", "th"}
                        ]
                        if len(values) != len(cells) or any(
                            n.attrs.get("rowspan", "1") != "1" or n.attrs.get("colspan", "1") != "1"
                            for n in values
                        ):
                            continue
                        value = values[column].text()
                        if value:
                            if column:
                                value = values[0].text() + ": " + value
                            if value not in found:
                                found.append(value)
                    continue
            siblings = node.parent.children
            after = siblings[siblings.index(node) + 1 :]
            parts = []
            for sibling in after:
                if isinstance(sibling, Node):
                    if sibling.tag in {"dt", "h1", "h2", "h3", "h4", "label"}:
                        break
                    parts.append(sibling.text())
                    if node.tag in {"th", "td"}:
                        break
                else:
                    parts.append(sibling)
            value = " ".join(" ".join(parts).split()).strip(" :")
            if value and value not in found:
                found.append(value)
        return found

    def links(self, base, name):
        return list(
            dict.fromkeys(
                urljoin(base, n.attrs["href"])
                for n in self.root.nodes()
                if n.tag == "a" and n.attrs.get("href") and norm(n.text()) == norm(name)
            )
        )

    def search_url(self, base, name):
        for form in self.root.nodes():
            if form.tag != "form" or form.attrs.get("method", "get").lower() != "get":
                continue
            inputs = [n for n in form.nodes() if n.tag == "input" and n.attrs.get("name")]
            queries = [
                n for n in inputs if n.attrs.get("type", "text").lower() in {"text", "search"}
            ]
            if len(queries) != 1:
                continue
            action = official_url(urljoin(base, form.attrs.get("action") or base))
            params = {
                n.attrs["name"]: n.attrs.get("value", "")
                for n in inputs
                if n.attrs.get("type") == "hidden"
            }
            params[queries[0].attrs["name"]] = name
            p = urlsplit(action)
            return urlunsplit((p.scheme, p.netloc, p.path, urlencode(params), ""))
        return None


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch_html(url: str, timeout: float = 4) -> tuple[str, str]:
    """Check every hop BEFORE request; limit redirects, body size, and socket wait."""
    opener = build_opener(NoRedirect())
    for _ in range(4):
        official_url(url)
        try:
            response = opener.open(
                Request(
                    url,
                    headers={
                        "User-Agent": "HCC-CurrentProcedure/1.0",
                        "Accept": "text/html",
                    },
                ),
                timeout=timeout,
            )
        except HTTPError as exc:
            if exc.code in {301, 302, 303, 307, 308}:
                location = exc.headers.get("Location")
                exc.close()
                if not location:
                    raise ValueError("DVC_REDIRECT_MISSING_LOCATION") from None
                url = official_url(urljoin(url, location))
                continue
            raise
        with response:
            if response.headers.get_content_type() not in {"text/html", "application/xhtml+xml"}:
                raise ValueError("DVC_UNSUPPORTED_CONTENT")
            data = response.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise ValueError("DVC_RESPONSE_TOO_LARGE")
            return official_url(response.geturl()), data.decode(
                response.headers.get_content_charset() or "utf-8", errors="strict"
            )
    raise ValueError("DVC_TOO_MANY_REDIRECTS")


def extract(page: Page, request: LookupRequest, url: str) -> dict | None:
    titles = page.labelled(("Tên thủ tục", "Tên thủ tục hành chính"))
    titles += [n.text() for n in page.root.nodes() if n.tag in {"h1", "h2"}]
    if not any(norm(t) == norm(request.procedure_name) for t in titles):
        return None
    localities = page.labelled(
        (
            "Địa phương",
            "Phạm vi thực hiện",
            "Cơ quan thực hiện",
            "Cơ quan có thẩm quyền",
            "Cơ quan tiếp nhận",
        )
    )
    # Entire locality phrase must occur with boundaries; never accept a missing locality.
    locality = norm(request.jurisdiction)
    if not any(
        re.search(r"(?<!\w)" + re.escape(locality) + r"(?!\w)", norm(v)) for v in localities
    ):
        return None
    values = page.labelled(LABELS[request.field])
    if not values:
        return None
    return dict(value="\n".join(values), source_title=request.procedure_name, source_url=url)


async def lookup(request: LookupRequest, *, enabled=False, timeout=6, fetch=fetch_html):
    def result(status, note, **kwargs):
        return LookupResult(
            status=status,
            procedure_id=request.procedure_id,
            field=request.field,
            jurisdiction=request.jurisdiction,
            checked_at=datetime.now(timezone.utc),
            retrieval_note=note,
            **kwargs,
        )

    if not enabled:
        return result("ERROR", "DVC_REALTIME_DISABLED")
    if request.as_of != datetime.now(timezone.utc).date():
        return result("NOT_FOUND", "DVC_CURRENT_ONLY_NO_HISTORICAL_OR_FUTURE_ASSERTION")
    try:
        async with asyncio.timeout(timeout):

            async def read(url):
                official_url(url)
                final_url, html = await asyncio.to_thread(fetch, url, min(timeout, 4))
                official_url(final_url)
                return final_url, Page(html)

            base, page = await read(ENTRY_URL)
            urls = page.links(base, request.procedure_name)
            if not urls:
                search_url = page.search_url(base, request.procedure_name)
                if search_url:
                    base, page = await read(search_url)
                    urls = page.links(base, request.procedure_name)
            if not urls:
                return result("NOT_FOUND", "DVC_NO_EXACT_HTML_RESULT_OR_JS_SEARCH_REQUIRED")
            if len(urls) > 6:
                return result("AMBIGUOUS", "DVC_TOO_MANY_EXACT_TITLE_RESULTS")
            matches = {}
            for url in urls:
                final_url, detail = await read(url)
                match = extract(detail, request, final_url)
                if match:
                    matches[final_url] = match
            if len(matches) > 1:
                return result("AMBIGUOUS", "DVC_MULTIPLE_PROCEDURE_LOCALITY_MATCHES")
            if not matches:
                return result("NOT_FOUND", "DVC_FIELD_OR_LOCALITY_NOT_VERIFIED")
            return result(
                "FOUND",
                "DVC_HTML_EXACT_TITLE_AND_EXPLICIT_LOCALITY; UNREVIEWED_WEB",
                **next(iter(matches.values())),
            )
    except TimeoutError:
        return result("ERROR", "DVC_TIMEOUT")
    except Exception:
        # Never leak remote response bodies or transport secrets into chat.
        return result("ERROR", "DVC_FETCH_OR_SCHEMA_ERROR")
