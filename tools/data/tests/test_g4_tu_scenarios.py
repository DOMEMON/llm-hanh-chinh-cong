import json
from pathlib import Path

from jsonschema import Draft202012Validator

from g3_pipeline.g4_tu_scenarios import generate_bundle, validate_bundle

ROOT = Path(__file__).parents[4]
PROCEDURES = ROOT / "02_private_output/company-tthc-9c38dde8-v1-demo10-v1/normalized/procedures.jsonl"
SCHEMA = ROOT / "03_docs/g4-scenario-v1.schema.json"


def test_generated_bundle_has_locked_shape(tmp_path: Path) -> None:
    dev, test_v2, _ = generate_bundle(PROCEDURES, tmp_path)
    assert len(dev) == 80
    assert len(test_v2) == 40
    assert sum(row["is_multiturn"] for row in dev + test_v2) >= 20
    assert {row["procedure_id"] for row in dev}.isdisjoint({row["procedure_id"] for row in test_v2})
    assert validate_bundle(tmp_path, PROCEDURES)["status"] == "PASS"


def test_each_scenario_matches_g4_schema(tmp_path: Path) -> None:
    generate_bundle(PROCEDURES, tmp_path)
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    for filename in ("scenario_dev.jsonl", "scenario_test_v2.jsonl"):
        rows = [json.loads(line) for line in (tmp_path / filename).read_text(encoding="utf-8").splitlines()]
        for row in rows:
            errors = list(validator.iter_errors(row))
            assert not errors, (filename, row["scenario_id"], errors)
            if row["is_multiturn"]:
                assert [turn["role"] for turn in row["turns"]] == ["user", "assistant", "user", "assistant"]
                assert "gold answer" not in row["turns"][-1]["text"].casefold()
