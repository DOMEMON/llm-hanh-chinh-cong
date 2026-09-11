#!/usr/bin/env python3
"""Generate a deterministic G4-01 DEV and TEST_V2 scenario bundle from demo10 procedures."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

FIELD_ORDER = [
    "receiving_authority",
    "required_documents",
    "fees",
    "processing_times",
    "submission_methods",
    "steps",
]

FIELDS = {
    "receiving_authority": {
        "group": "G4-01-RA",
        "prompt": "nộp hồ sơ ở đâu / đến đâu làm / cơ quan nào tiếp nhận",
        "must_include": ["địa điểm", "đơn vị tiếp nhận", "nơi tiếp nhận"],
        "must_exclude": ["mức phí", "người nộp"],
    },
    "required_documents": {
        "group": "G4-01-DOC",
        "prompt": "hồ sơ cần chuẩn bị / cần mang theo giấy tờ gì",
        "must_include": ["thành phần hồ sơ", "giấy tờ bắt buộc", "bản chính"],
        "must_exclude": ["mức phí", "thời gian xử lý"],
    },
    "fees": {
        "group": "G4-01-FEE",
        "prompt": "lệ phí / miễn phí / thu bao nhiêu",
        "must_include": ["lệ phí", "miễn phí", "đồng"],
        "must_exclude": ["địa điểm", "thời gian xử lý"],
    },
    "processing_times": {
        "group": "G4-01-TIME",
        "prompt": "thời gian giải quyết / mất bao lâu / xử lý trong mấy ngày",
        "must_include": ["thời gian xử lý", "ngày làm việc", "số ngày"],
        "must_exclude": ["địa điểm", "giấy tờ"],
    },
    "submission_methods": {
        "group": "G4-01-METHOD",
        "prompt": "nộp trực tiếp / trực tuyến / bưu chính / qua mạng",
        "must_include": ["hình thức nộp", "trực tiếp", "trực tuyến"],
        "must_exclude": ["mức phí", "giấy tờ"],
    },
    "steps": {
        "group": "G4-01-STEPS",
        "prompt": "các bước thực hiện / làm như thế nào / trình tự xử lý",
        "must_include": ["bước thực hiện", "trình tự", "thủ tục"],
        "must_exclude": ["mức phí", "địa điểm"],
    },
}

REQUIRED_SCENARIO_FIELDS = {
    "scenario_id",
    "dataset_version",
    "split",
    "scenario_group_id",
    "procedure_id",
    "field_expected",
    "expected_status",
    "gold_fragment_ids",
    "gold_label",
    "gold_answer",
    "must_include",
    "must_exclude",
    "is_multiturn",
    "conversation_turns",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows


def validate_bundle(out_dir: Path, procedures_path: Path) -> dict[str, Any]:
    """Validate scenario shape, references, split isolation and manifest hashes."""
    dev = load_jsonl(out_dir / "scenario_dev.jsonl")
    test_v2 = load_jsonl(out_dir / "scenario_test_v2.jsonl")
    manifest = json.loads((out_dir / "scenario_manifest.json").read_text(encoding="utf-8"))
    procedures = load_jsonl(procedures_path)
    procedure_ids = {row.get("procedure_id") for row in procedures}
    rows = dev + test_v2
    errors: list[str] = []
    if len(dev) != 80:
        errors.append("DEV_COUNT")
    if len(test_v2) != 40:
        errors.append("TEST_V2_COUNT")
    if sum(bool(row.get("is_multiturn")) for row in rows) < 20:
        errors.append("MULTI_TURN_COUNT")
    if any(not REQUIRED_SCENARIO_FIELDS <= row.keys() for row in rows):
        errors.append("SCENARIO_FIELDS")
    ids = [row.get("scenario_id") for row in rows]
    if len(ids) != len(set(ids)):
        errors.append("SCENARIO_ID_DUPLICATE")
    if any(row.get("split") != "DEV" for row in dev):
        errors.append("DEV_SPLIT")
    if any(row.get("split") != "TEST_V2" for row in test_v2):
        errors.append("TEST_V2_SPLIT")
    if set(row.get("scenario_group_id") for row in dev) & set(row.get("scenario_group_id") for row in test_v2):
        errors.append("GROUP_LEAKAGE")
    if any(row.get("procedure_id") not in procedure_ids for row in rows):
        errors.append("PROCEDURE_REFERENCE")
    if any(
        row.get("gold_label", {}).get("status") != row.get("expected_status")
        or row.get("gold_label", {}).get("fragment_ids") != row.get("gold_fragment_ids")
        for row in rows
    ):
        errors.append("GOLD_LABEL_MISMATCH")
    for filename, manifest_key in (("scenario_dev.jsonl", "dev"), ("scenario_test_v2.jsonl", "test_v2")):
        if hash_bytes((out_dir / filename).read_bytes()) != manifest.get("sha256", {}).get(manifest_key):
            errors.append(f"HASH_{manifest_key.upper()}")
    return {
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "dev_count": len(dev),
        "test_v2_count": len(test_v2),
        "multi_turn_count": sum(bool(row.get("is_multiturn")) for row in rows),
    }


def hash_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def make_question(proc: dict[str, Any], field: str, *, multi_turn: bool = False, split: str = "DEV") -> str:
    title = proc.get("title", "")
    prompt = FIELDS[field]["prompt"]
    if multi_turn:
        if split == "TEST_V2":
            return (
                f"Đối chiếu hồ sơ của thủ tục {title}: cần xác định {prompt}. "
                "Nếu nguồn không ghi rõ, hãy nêu rõ là chưa đủ căn cứ."
            )
        return (
            f"Tôi đang tìm thủ tục {title}. Trước tiên, {prompt}. "
            "Sau đó tôi muốn hỏi tiếp thêm về cùng thủ tục này."
        )
    if split == "TEST_V2":
        return f"Khi kiểm tra thủ tục {title}, nguồn có ghi rõ {prompt} không?"
    return f"{title}. {prompt}?"


def first_fragment(proc: dict[str, Any], field: str) -> list[str]:
    evidence = proc.get("field_evidence", {}).get(field, [])
    if not evidence:
        return []
    return [str(evidence[0])]


def expected_status(proc: dict[str, Any], field: str) -> str:
    if proc.get(field):
        return "ANSWER"
    return "INSUFFICIENT_DATA"


def compact_values(proc: dict[str, Any], field: str) -> list[Any]:
    value = proc.get(field)
    if isinstance(value, list):
        out: list[Any] = []
        for item in value:
            if isinstance(item, (str, dict)):
                out.append(item)
        return out[:3]
    if isinstance(value, str):
        return [value]
    return []


def scenario_from_proc(proc: dict[str, Any], field: str, split: str, idx: int, *, multi_turn: bool) -> dict[str, Any]:
    proc_id = proc.get("procedure_id", "")
    title = proc.get("title", "")
    info = FIELDS[field]
    question = make_question(proc, field, multi_turn=multi_turn, split=split)
    gold_ids = first_fragment(proc, field)
    status = expected_status(proc, field)
    if not gold_ids and field in proc.get("missing_fields", []):
        status = "INSUFFICIENT_DATA"

    turns = [{"role": "user", "text": question}] if not multi_turn else [
        {"role": "user", "text": f"Tôi đang tìm thủ tục {title}. Cho tôi biết {info['prompt']} trước."},
        {"role": "user", "text": "Giờ tôi muốn hỏi tiếp thêm về cùng thủ tục này."},
    ]

    return {
        "scenario_id": f"g4-{split.lower()}-{proc_id}-{field}-{idx:02d}",
        "dataset_version": proc.get("dataset_version", "company-tthc-9c38dde8-v1-demo10-v1"),
        "split": split,
        "scenario_group_id": info["group"] if split == "DEV" else f"{info['group']}-V2",
        "procedure_id": proc_id,
        "procedure_title": title,
        "field_expected": field,
        "question": question,
        "expected_status": status,
        "gold_fragment_ids": gold_ids,
        "gold_label": {
            "status": status,
            "procedure_id": proc_id,
            "field": field,
            "fragment_ids": gold_ids,
        },
        "gold_answer": compact_values(proc, field),
        "must_include": info["must_include"],
        "must_exclude": info["must_exclude"],
        "expected_points": compact_values(proc, field),
        "is_multiturn": multi_turn,
        "conversation_turns": 2 if multi_turn else 1,
        "turns": turns,
    }


def generate_bundle(dataset_path: Path, out_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    procedures = load_jsonl(dataset_path)
    dev: list[dict[str, Any]] = []
    test_v2: list[dict[str, Any]] = []

    for proc_idx, proc in enumerate(procedures):
        for field_idx, field in enumerate(FIELD_ORDER):
            dev.append(scenario_from_proc(proc, field, "DEV", proc_idx * 10 + field_idx + 1, multi_turn=False))
        dev.append(scenario_from_proc(proc, "receiving_authority", "DEV", proc_idx * 10 + 7, multi_turn=True))
        dev.append(scenario_from_proc(proc, "fees", "DEV", proc_idx * 10 + 8, multi_turn=True))

        for field_idx, field in enumerate(FIELD_ORDER[:4]):
            test_v2.append(scenario_from_proc(proc, field, "TEST_V2", proc_idx * 10 + field_idx + 1, multi_turn=False))

    dev = dev[:80]
    test_v2 = test_v2[:40]

    out_dir.mkdir(parents=True, exist_ok=True)
    dev_path = out_dir / "scenario_dev.jsonl"
    test_path = out_dir / "scenario_test_v2.jsonl"
    dev_path.write_text(
        "\n".join(json.dumps(item, ensure_ascii=False, sort_keys=True) for item in dev) + "\n",
        encoding="utf-8",
    )
    test_path.write_text(
        "\n".join(json.dumps(item, ensure_ascii=False, sort_keys=True) for item in test_v2) + "\n",
        encoding="utf-8",
    )

    manifest = {
        "dataset_version": "company-tthc-9c38dde8-v1-demo10-v1",
        "scenario_set": "G4-01-evaluation-v2",
        "generated_at": "2026-09-11T00:00:00+07:00",
        "review_status": "PENDING_SECOND_REVIEW",
        "test_v2_lock": {
            "status": "LOCKED_FOR_RELEASE_EVALUATION",
            "do_not_use_for": ["prompt_tuning", "retrieval_tuning", "model_tuning", "serving_index"],
        },
        "procedure_count": len(procedures),
        "dev_count": len(dev),
        "test_v2_count": len(test_v2),
        "multi_turn_count": sum(1 for item in dev + test_v2 if item.get("is_multiturn")),
        "fields": FIELD_ORDER,
        "files": {"dev": "g4_eval/scenario_dev.jsonl", "test_v2": "g4_eval/scenario_test_v2.jsonl"},
        "sha256": {
            "dev": hash_bytes(dev_path.read_bytes()),
            "test_v2": hash_bytes(test_path.read_bytes()),
        },
    }
    (out_dir / "scenario_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return dev, test_v2, manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate G4-01 evaluation scenarios from demo10 procedures.")
    parser.add_argument(
        "--procedures",
        type=Path,
        default=Path("02_private_output/company-tthc-9c38dde8-v1-demo10-v1/normalized/procedures.jsonl"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("02_private_output/company-tthc-9c38dde8-v1-demo10-v1/g4_eval"),
    )
    args = parser.parse_args()

    dev, test_v2, manifest = generate_bundle(args.procedures, args.output_dir)
    validation = validate_bundle(args.output_dir, args.procedures)
    print(f"DEV={len(dev)} TEST_V2={len(test_v2)} MULTI_TURN={sum(1 for item in dev + test_v2 if item.get('is_multiturn'))}")
    print(f"manifest={args.output_dir / 'scenario_manifest.json'}")
    print(json.dumps(validation, sort_keys=True))


if __name__ == "__main__":
    main()
