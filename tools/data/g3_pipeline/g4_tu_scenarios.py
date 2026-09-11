#!/usr/bin/env python3
"""Build and validate the private G4-01 evaluation bundle."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .common import scan_sensitive_record

FIELD_ORDER = [
    "receiving_authority",
    "required_documents",
    "fees",
    "processing_times",
    "submission_methods",
    "steps",
]
FIELD_INFO = {
    "receiving_authority": ("RA", "nộp hồ sơ ở đâu, cơ quan nào tiếp nhận", "nơi tiếp nhận"),
    "required_documents": ("DOC", "cần chuẩn bị giấy tờ gì", "thành phần hồ sơ"),
    "fees": ("FEE", "lệ phí và điều kiện thu", "lệ phí"),
    "processing_times": ("TIME", "thời gian giải quyết và điều kiện tính", "thời gian"),
    "submission_methods": ("METHOD", "có thể nộp bằng hình thức nào", "hình thức nộp"),
    "steps": ("STEPS", "trình tự thực hiện", "bước thực hiện"),
}
SECTION_TYPES = {
    "receiving_authority": "RECEIVING_AUTHORITY",
    "required_documents": "REQUIRED_DOCUMENTS",
    "fees": "FEES",
    "processing_times": "PROCESSING_TIME",
    "submission_methods": "SUBMISSION_METHODS",
    "steps": "STEPS",
}
REQUIRED_FIELDS = {
    "scenario_id", "dataset_version", "split", "scenario_group_id", "procedure_id",
    "procedure_title", "field_expected", "question", "expected_status", "gold_fragment_ids",
    "gold_label", "gold_answer", "must_include", "must_exclude", "is_multiturn",
    "conversation_turns", "turns",
}
VARIANT_CONTEXTS = [
    "Tôi cần câu trả lời để chuẩn bị hồ sơ lần đầu.",
    "Tôi đang kiểm tra điều kiện áp dụng trước khi nộp.",
    "Tôi cần phân biệt thông tin bắt buộc với thông tin tham khảo.",
    "Tôi muốn biết nguồn có đủ căn cứ hay cần hỏi lại.",
    "Tôi cần câu trả lời ngắn gọn nhưng phải giữ nguyên điều kiện.",
    "Tôi đang đối chiếu nội dung này với checklist nội bộ.",
    "Tôi cần tránh nhầm field này với phí, thời gian hoặc hồ sơ.",
    "Tôi chỉ muốn nhận thông tin có trong fragment được dẫn.",
    "Tôi cần biết trường hợp của mình có thuộc điều kiện nêu trong nguồn không.",
    "Tôi đang kiểm tra một hồ sơ đã đủ giấy tờ hay chưa.",
    "Tôi cần biết thông tin này áp dụng trước hay sau khi hồ sơ hợp lệ.",
    "Tôi muốn giữ nguyên các ngoại lệ và điều kiện trong câu trả lời.",
    "Tôi đang so sánh cách nộp hồ sơ nhưng không cần suy luận ngoài nguồn.",
    "Tôi cần một câu trả lời có thể đối chiếu lại bằng fragment.",
    "Tôi muốn xác định dữ liệu đang thiếu thay vì đoán thêm.",
    "Tôi đang kiểm tra câu trả lời cho một người nộp hồ sơ cụ thể.",
    "Tôi cần tách thông tin của field này khỏi các field lân cận.",
    "Tôi muốn biết có thể trả lời chắc chắn hay phải yêu cầu bổ sung nguồn.",
    "Tôi đang rà soát chất lượng dữ liệu trước khi dùng cho phát hành.",
    "Tôi cần giữ đúng phạm vi thủ tục và không trộn với thủ tục khác.",
]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def hash_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def first_fragment(proc: dict[str, Any], field: str) -> list[str]:
    evidence = proc.get("field_evidence", {}).get(field, [])
    return [str(fragment_id) for fragment_id in evidence]


def gold_answer(proc: dict[str, Any], field: str) -> list[Any]:
    value = proc.get(field)
    if isinstance(value, list):
        return value
    return [value] if value is not None else []


def status_for(proc: dict[str, Any], field: str) -> str:
    return "ANSWER" if proc.get(field) else "INSUFFICIENT_DATA"


def question_for(proc: dict[str, Any], field: str, split: str, variant: int, multi: bool) -> str:
    title = proc["title"]
    _, intent, _ = FIELD_INFO[field]
    if split == "DEV":
        forms = [
            f"{title}: {intent}?",
            f"Tôi cần làm thủ tục {title}; {intent} thế nào?",
            f"Cho tôi biết {intent} của thủ tục {title}.",
            f"Trong hồ sơ của thủ tục {title}, tôi muốn kiểm tra {intent}.",
        ]
    else:
        forms = [
            f"Khi đối chiếu thủ tục {title}, nguồn có ghi rõ {intent} không?",
            f"Với thủ tục {title}, hãy xác định {intent} từ nguồn được cung cấp.",
            f"Tôi cần kiểm tra độc lập: thủ tục {title} có thông tin về {intent} nào?",
            f"Đọc đúng nguồn của {title} và cho biết {intent}; không suy đoán nếu thiếu.",
        ]
    question = forms[variant % len(forms)]
    variant_context = VARIANT_CONTEXTS[variant % len(VARIANT_CONTEXTS)]
    question += f" {variant_context}"
    if multi:
        question += " Tôi muốn tiếp tục trao đổi theo đúng thủ tục này và kiểm tra điều kiện áp dụng."
    elif variant >= len(forms):
        question += f" Đây là biến thể kiểm tra số {variant}."
    return question


def make_turns(proc: dict[str, Any], field: str, split: str, variant: int) -> list[dict[str, str]]:
    title = proc["title"]
    _, intent, _ = FIELD_INFO[field]
    if split == "DEV":
        first = f"Tôi đang làm thủ tục {title}. Trước hết, {intent} thế nào?"
        follow = [
            "Cảm ơn. Với đúng thủ tục này, còn thông tin đó có điều kiện gì không?",
            "Nếu hồ sơ của tôi hợp lệ thì thông tin vừa nêu được áp dụng ra sao?",
        ][variant % 2]
    else:
        first = f"Tôi cần xác minh thủ tục {title}. Nguồn cho biết {intent} thế nào?"
        follow = [
            "Nếu nguồn không ghi rõ phần này, hãy nói rõ là chưa đủ căn cứ.",
            "Hãy chỉ dùng fragment của đúng thủ tục này và nêu điều kiện nếu có.",
        ][variant % 2]
    return [
        {"role": "user", "text": first},
        {"role": "assistant", "text": f"Tôi đã xác định yêu cầu về {intent}; cần đối chiếu evidence của thủ tục này."},
        {"role": "user", "text": follow},
        {"role": "assistant", "text": "Tôi sẽ đối chiếu fragment đúng thủ tục trước khi trả lời."},
    ]


def make_scenario(proc: dict[str, Any], field: str, split: str, index: int, variant: int, multi: bool) -> dict[str, Any]:
    group_code, _, label = FIELD_INFO[field]
    status = status_for(proc, field)
    fragments = first_fragment(proc, field)
    if status == "INSUFFICIENT_DATA":
        fragments = []
    answer = gold_answer(proc, field)
    question = question_for(proc, field, split, variant, multi)
    turns = make_turns(proc, field, split, variant) if multi else [{"role": "user", "text": question}]
    return {
        "scenario_id": f"g4-{split.lower()}-{index:03d}",
        "dataset_version": proc["dataset_version"],
        "split": split,
        "scenario_group_id": f"G4-01-{group_code}-{proc['procedure_id']}",
        "procedure_id": proc["procedure_id"],
        "procedure_title": proc["title"],
        "field_expected": field,
        "question": question,
        "expected_status": status,
        "gold_fragment_ids": fragments,
        "gold_label": {
            "procedure_id": proc["procedure_id"],
            "field": field,
            "status": status,
            "fragment_ids": fragments,
        },
        "gold_answer": answer,
        "must_include": [label] if status == "ANSWER" else ["nêu rõ chưa đủ căn cứ"],
        "must_exclude": ["suy đoán", "thông tin ngoài nguồn"],
        "is_multiturn": multi,
        "conversation_turns": len(turns),
        "turns": turns,
    }


def validate_bundle(out_dir: Path, procedures_path: Path, schema_path: Path | None = None) -> dict[str, Any]:
    dev = load_jsonl(out_dir / "scenario_dev.jsonl")
    test = load_jsonl(out_dir / "scenario_test_v2.jsonl")
    rows = dev + test
    procedures = load_jsonl(procedures_path)
    procedure_map = {row["procedure_id"]: row for row in procedures}
    fragments = load_jsonl(procedures_path.parent / "fragments.jsonl")
    fragment_map = {row["fragment_id"]: row for row in fragments}
    manifest = json.loads((out_dir / "scenario_manifest.json").read_text(encoding="utf-8"))
    errors: list[str] = []
    if len(dev) != 80 or len(test) != 40:
        errors.append("COUNT")
    if sum(row["is_multiturn"] for row in rows) < 20:
        errors.append("MULTI_TURN_COUNT")
    ids = [row.get("scenario_id") for row in rows]
    if len(ids) != len(set(ids)):
        errors.append("DUPLICATE_SCENARIO_ID")
    if any(not REQUIRED_FIELDS <= row.keys() for row in rows):
        errors.append("REQUIRED_FIELDS")
    if any(row.get("procedure_id") not in procedure_map for row in rows):
        errors.append("PROCEDURE_REFERENCE")
    dev_procedures = {row["procedure_id"] for row in dev}
    test_procedures = {row["procedure_id"] for row in test}
    if dev_procedures & test_procedures:
        errors.append("PROCEDURE_SPLIT_LEAKAGE")
    for row in rows:
        if schema_path:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            if list(Draft202012Validator(schema).iter_errors(row)):
                errors.append("SCHEMA")
        if scan_sensitive_record(row):
            errors.append("PII")
        proc = procedure_map.get(row["procedure_id"])
        expected_fragments = set(proc.get("field_evidence", {}).get(row["field_expected"], [])) if proc else set()
        for fragment_id in row["gold_fragment_ids"]:
            fragment = fragment_map.get(fragment_id)
            if not fragment or fragment.get("procedure_id") != row["procedure_id"] or fragment_id not in expected_fragments:
                errors.append("GOLD_FRAGMENT_REFERENCE")
            if fragment and fragment.get("section_type") != SECTION_TYPES[row["field_expected"]]:
                errors.append("GOLD_FRAGMENT_SECTION")
        if row["gold_label"]["fragment_ids"] != row["gold_fragment_ids"] or row["gold_label"]["status"] != row["expected_status"]:
            errors.append("GOLD_LABEL_MISMATCH")
        if row["is_multiturn"]:
            turns = row["turns"]
            if row["conversation_turns"] != len(turns) or len(turns) < 3 or turns[0]["role"] != "user" or turns[1]["role"] != "assistant" or turns[2]["role"] != "user":
                errors.append("MULTI_TURN_STRUCTURE")
        if any(
            other is not row
            and other["procedure_id"] == row["procedure_id"]
            and other["field_expected"] == row["field_expected"]
            and difflib.SequenceMatcher(None, row["question"], other["question"]).ratio() >= 0.92
            for other in rows
        ):
            errors.append("NEAR_DUPLICATE_QUESTION")
            break
    for filename, key in (("scenario_dev.jsonl", "dev"), ("scenario_test_v2.jsonl", "test_v2")):
        if hash_bytes((out_dir / filename).read_bytes()) != manifest["sha256"][key]:
            errors.append(f"HASH_{key.upper()}")
    if manifest.get("review_status") != "PENDING_REVIEW":
        errors.append("REVIEW_STATUS")
    return {"status": "PASS" if not errors else "FAIL", "errors": sorted(set(errors)), "dev_count": len(dev), "test_v2_count": len(test), "multi_turn_count": sum(row["is_multiturn"] for row in rows)}


def generate_bundle(dataset_path: Path, out_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    procedures = load_jsonl(dataset_path)
    ordered = sorted(procedures, key=lambda row: row["procedure_id"])
    dev_procs = ordered[:8]
    test_procs = ordered[8:]
    dev: list[dict[str, Any]] = []
    test: list[dict[str, Any]] = []
    index = 1
    for proc in dev_procs:
        for field_index, field in enumerate(FIELD_ORDER):
            dev.append(make_scenario(proc, field, "DEV", index, field_index, multi=False))
            index += 1
        for extra in range(4):
            field = FIELD_ORDER[extra % len(FIELD_ORDER)]
            dev.append(make_scenario(proc, field, "DEV", index, extra + 1, multi=extra < 2))
            index += 1
    index = 1
    for proc in test_procs:
        for extra in range(20):
            field = FIELD_ORDER[extra % len(FIELD_ORDER)]
            test.append(make_scenario(proc, field, "TEST_V2", index, extra + 1, multi=extra < 10))
            index += 1
    out_dir.mkdir(parents=True, exist_ok=True)
    dev_path = out_dir / "scenario_dev.jsonl"
    test_path = out_dir / "scenario_test_v2.jsonl"
    dev_path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in dev) + "\n", encoding="utf-8")
    test_path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in test) + "\n", encoding="utf-8")
    manifest = {
        "dataset_version": procedures[0]["dataset_version"],
        "scenario_set": "G4-01-evaluation-v3",
        "generated_at": "2026-09-11T00:00:00+07:00",
        "review_status": "PENDING_REVIEW",
        "test_v2_lock": {"status": "PENDING_REVIEW", "recipient": "Hoan only", "do_not_use_for": ["prompt_tuning", "retrieval_tuning", "model_tuning", "serving_index"]},
        "procedure_count": len(procedures),
        "dev_procedure_ids": [row["procedure_id"] for row in dev_procs],
        "test_v2_procedure_ids": [row["procedure_id"] for row in test_procs],
        "dev_count": len(dev),
        "test_v2_count": len(test),
        "multi_turn_count": sum(row["is_multiturn"] for row in dev + test),
        "files": {"dev": "g4_eval/scenario_dev.jsonl", "test_v2": "g4_eval/scenario_test_v2.jsonl"},
        "sha256": {"dev": hash_bytes(dev_path.read_bytes()), "test_v2": hash_bytes(test_path.read_bytes())},
    }
    (out_dir / "scenario_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return dev, test, manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--procedures", type=Path, default=Path("02_private_output/company-tthc-9c38dde8-v1-demo10-v1/normalized/procedures.jsonl"))
    parser.add_argument("--output-dir", type=Path, default=Path("02_private_output/company-tthc-9c38dde8-v1-demo10-v1/g4_eval"))
    parser.add_argument("--schema", type=Path, default=Path("03_docs/g4-scenario-v1.schema.json"))
    args = parser.parse_args()
    generate_bundle(args.procedures, args.output_dir)
    result = validate_bundle(args.output_dir, args.procedures, args.schema)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
