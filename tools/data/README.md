# Công cụ dữ liệu G3/G4

- `validate_dataset.py --mode preflight`: kiểm tra kỹ thuật draft; cảnh báo các
  gate review/phạm vi còn thiếu nhưng vẫn trả exit code 0 nếu cấu trúc nhất quán.
- `validate_dataset.py --mode publish`: cùng các kiểm tra trên nhưng biến review,
  độ đầy đủ và phạm vi 2–3 thủ tục/30–50 câu thành lỗi chặn publish.
- `build_synthetic_dataset.py`: tạo lại deterministic corpus D0 gồm 3 thủ tục,
  24 fragment và 33 câu hỏi; không truy cập Internet.
- `crawl_or_download.py`: chỉ tải một URL HTTPS thuộc allowlist, tôn trọng
  `robots.txt`, giới hạn dung lượng và không ghi đè snapshot cũ.
- `g3_pipeline`: parser, validator và gold-draft builder cho workbook công ty G3.
  Công cụ chỉ chạy local, output luôn nằm ở vùng `data/company_private/` bị ignore.
  Xem [hướng dẫn phần Tú](../../docs/giai-doan-3/04-huong-dan-pipeline-data-tu.md).
- `g4_tu_scenarios.py`: tạo và kiểm tra bundle evaluation G4 từ demo10. Tool tách
  procedure theo DEV/TEST_V2, tạo gold label/fragment, kiểm tra multi-turn và hash.

Không công cụ nào tự chuyển `review_status` sang `APPROVED`. Việc đó cần người
review thứ hai và mentor xác nhận phạm vi sử dụng.

Khi kiểm tra dữ liệu D0, phải truyền rõ:

```text
--dataset data/demo_synthetic --classification D0_SYSTEM_SMOKE
```

## G4-01 local workflow

Chạy từ repository root bằng package module, không chạy trực tiếp `validator.py`:

```powershell
uv run --project 04_pipeline/tools/data python -m g3_pipeline.g4_tu_scenarios
uv run --project 04_pipeline/tools/data pytest 04_pipeline/tools/data/tests/test_g4_tu_scenarios.py
uv run --project 04_pipeline/tools/data python -m g3_pipeline.validator `
  --dataset "02_private_output/company-tthc-9c38dde8-v1-demo10-v1" `
  --schema "03_docs/data-contract-v1.schema.json" `
  --mode preflight
```

G4 output nằm trong vùng private `02_private_output/.../g4_eval/` và gồm:

- `scenario_dev.jsonl`: 80 scenario dùng để sửa hệ thống;
- `scenario_test_v2.jsonl`: 40 scenario chỉ mở sau khi release chốt;
- `scenario_manifest.json`: dataset version, split procedure, review status và SHA-256.

TEST_V2 không được đưa vào prompt, retrieval tuning, model tuning hoặc serving index.
Chỉ reviewer được chỉ định nhận gold TEST_V2; Minh chỉ dùng DEV, schema và tool đánh giá.
