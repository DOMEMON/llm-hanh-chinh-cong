#!/usr/bin/env python3
"""Generate a G4-01 coverage brief for the demo10 corpus."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

FIELDS = [
    "receiving_authority",
    "submission_methods",
    "required_documents",
    "fees",
    "processing_times",
]

COMMON_MISSING = [
    "applicant_scope",
    "effective_dates",
    "issuing_authority",
    "jurisdiction",
    "legal_bases",
    "procedure_code",
    "public_url",
    "steps",
]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows


def field_coverage(rows: list[dict[str, Any]]) -> dict[str, int]:
    coverage: dict[str, int] = {}
    for field in FIELDS:
        coverage[field] = sum(1 for r in rows if r.get(field))
    return coverage


def missing_summary(rows: list[dict[str, Any]]) -> list[tuple[str, int]]:
    counter: Counter[str] = Counter()
    for row in rows:
        for field in row.get("missing_fields", []):
            counter[field] += 1
    return sorted(counter.items(), key=lambda item: (-item[1], item[0]))


def ambiguous_summary(rows: list[dict[str, Any]]) -> list[tuple[str, str, str]]:
    findings: list[tuple[str, str, str]] = []
    markers = ("không quy định", "0.0", "05", "3–5", "điều kiện")
    for row in rows:
        for field in ("fees", "processing_times", "receiving_authority"):
            raw = " ".join(str(item) for item in row.get(field, []))
            if any(marker in raw.casefold() for marker in markers):
                findings.append((row.get("procedure_id", ""), field, raw[:180]))
    return findings


def procedure_table(rows: list[dict[str, Any]]) -> str:
    lines = [
        "| # | Thủ tục | Category | receiving_authority | submission_methods | required_documents | fees | processing_times | Missing |",
        "|---|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for index, row in enumerate(rows, 1):
        title = row.get("title", "")
        category = row.get("category_label", "")
        fields = {
            "receiving_authority": bool(row.get("receiving_authority")),
            "submission_methods": bool(row.get("submission_methods")),
            "required_documents": bool(row.get("required_documents")),
            "fees": bool(row.get("fees")),
            "processing_times": bool(row.get("processing_times")),
        }
        missing = ", ".join(row.get("missing_fields", [])[:4])
        lines.append(
            f"| {index} | {title} | {category} | {'✅' if fields['receiving_authority'] else '⚠️'} | {'✅' if fields['submission_methods'] else '⚠️'} | {'✅' if fields['required_documents'] else '⚠️'} | {'✅' if fields['fees'] else '⚠️'} | {'✅' if fields['processing_times'] else '⚠️'} | {missing or '—'} |"
        )
    return "\n".join(lines)


def build_markdown(rows: list[dict[str, Any]], dataset_version: str, source_count: int) -> str:
    counts = field_coverage(rows)
    missing = missing_summary(rows)
    ambiguous = ambiguous_summary(rows)
    sections = [
        "# Báo cáo coverage G4-01 – phần Tú",
        "",
        f"- Dataset: `{dataset_version}`",
        f"- Số thủ tục: {len(rows)}",
        f"- Số nguồn gốc: {source_count}",
        "- Trạng thái: demo10 đã được phê duyệt cho demo nội bộ; không coi là production-ready.",
        "",
        "## 1. Coverage theo field",
        "",
        "| Field | Có dữ liệu | Tỷ lệ |",
        "|---|---:|---:|",
    ]
    for field in FIELDS:
        value = counts[field]
        pct = value / len(rows) * 100 if rows else 0
        sections.append(f"| {field} | {value}/{len(rows)} | {pct:.1f}% |")

    sections.extend([
        "",
        "## 2. Danh sách thủ tục demo10",
        "",
        procedure_table(rows),
        "",
        "## 3. Missing fields lặp lại",
        "",
        "| Field | Số thủ tục |",
        "|---|---:|",
    ])
    if missing:
        for field_name, count in missing:
            sections.append(f"| {field_name} | {count} |")
    else:
        sections.append("| — | 0 |")

    sections.extend([
        "",
        "## 4. Nhận xét nghiệp vụ",
        "",
        "- `receiving_authority`, `required_documents`, `fees`, `processing_times` là các field trọng tâm cho 10 thủ tục demo; các field còn thiếu chủ yếu thuộc metadata thủ tục (`applicant_scope`, `effective_dates`, `issuing_authority`, `jurisdiction`, `legal_bases`, `procedure_code`, `public_url`) và `steps`.",
        "- `submission_methods` có đầy đủ trên hầu hết thủ tục nên thích hợp làm baseline cho retrieval theo field và intent gắn với điều kiện nộp.",
        "- `fees` và `processing_times` đôi khi có định dạng rời rạc hoặc mơ hồ (`0.0`, `“không quy định cụ thể”`, `“3–5 ngày làm việc”`); cần review chốt trước khi dùng trong TEST_V2 để tránh đánh giá nhầm ý nghĩa.",
        "- Với G4-01, không mở rộng dữ liệu bằng cách gán nhãn máy mà không có reviewer thứ hai; các ca mơ hồ phải giữ trạng thái `PENDING_REVIEW` hoặc `INSUFFICIENT_DATA` thay vì tự pass.",
        "",
        "## 5. Danh sách ambiguous cần review",
        "",
        "| Procedure ID | Field | Dữ liệu cần làm rõ |",
        "|---|---|---|",
    ])
    if ambiguous:
        for procedure_id, field, value in ambiguous:
            sections.append(f"| `{procedure_id}` | `{field}` | {value} |")
    else:
        sections.append("| — | — | Không phát hiện theo marker hiện tại |")

    sections.extend([
        "",
        "## 6. Kế hoạch DEV/TEST_V2 theo `scenario_group_id`",
        "",
        "- Tách theo `procedure_family` + `field_intent` + `ambiguity_pattern`, không chia ngẫu nhiên paraphrase.",
        "- Mục tiêu: 80 DEV và 40 TEST_V2 trong khoảng 120 scenario, với ít nhất 20 scenario nhiều lượt.",
        "- Mỗi scenario nên bao gồm: `scenario_group_id`, `procedure_id`, `requested_field`, `expected_status`, `gold_fragment_ids`, `must_include`, `must_exclude`, `conversation_turns`.",
        "",
        "### Nhóm scenario gợi ý",
        "- G-01: `receiving_authority` — nơi nộp, nơi làm, cơ quan tiếp nhận.",
        "- G-02: `fees` — được miễn, có phí, mức phí theo trường hợp, điều kiện áp dụng.",
        "- G-03: `processing_times` — số ngày làm việc, điều kiện tính từ ngày nào.",
        "- G-04: `required_documents` — thành phần hồ sơ và điều kiện bổ sung.",
        "- G-05: `submission_methods` — trực tiếp / qua mạng / bưu chính / hỗn hợp.",
        "- G-06: hội thoại ngắn — `hồ sơ → nơi nộp → lệ phí`, `còn lệ phí?`, `bao lâu?`.",
        "- G-07: thiếu dữ kiện / sai phạm vi — không suy đoán khi không có evidence.",
        "",
        "### Lưu ý split",
        "- DEV chứa các biến thể học thuật + multi-turn clarifying; dùng để chốt prompt và threshold.",
        "- TEST_V2 khóa cùng manifest/hash, không được dùng để chỉnh prompt hoặc retrieval sau khi khóa.",
        "- Duyệt chéo bởi reviewer thứ hai trước khi đóng gói.",
        "",
        "## 7. Đề xuất action tiếp theo",
        "",
        "1. Duyệt 10 thủ tục demo theo 6 field: hồ sơ, phí, thời gian, nơi tiếp nhận, hình thức nộp và bước xử lý.",
        "2. Chốt danh sách `scenario_group_id` dựa trên 7 nhóm trên, rồi phân 80/40 cho DEV/TEST_V2.",
        "3. Lưu ý 20+ scenario nhiều lượt để test hội thoại ngắn và context carry-over.",
        "4. Báo cáo missing/conflict đến Minh và Hoan trước khi mở rộng dữ liệu.",
    ])
    return "\n".join(sections) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the G4-01 coverage report for the demo10 corpus.")
    parser.add_argument("--procedures", type=Path, default=Path("02_private_output/company-tthc-9c38dde8-v1-demo10-v1/normalized/procedures.jsonl"))
    parser.add_argument("--dataset-version", default="company-tthc-9c38dde8-v1-demo10-v1")
    parser.add_argument("--source-count", type=int, default=10)
    parser.add_argument("--output", type=Path, default=Path("03_docs/05-bao-cao-g4-01-tu.md"))
    args = parser.parse_args()

    rows = load_jsonl(args.procedures)
    markdown = build_markdown(rows, args.dataset_version, args.source_count)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(markdown, encoding="utf-8")
    print(f"Wrote report: {args.output}")
    print(f"Procedures: {len(rows)}")
    # Quick summary for console.
    for field in FIELDS:
        value = sum(1 for row in rows if row.get(field))
        print(f"{field}: {value}/{len(rows)}")


if __name__ == "__main__":
    main()
