# Báo cáo coverage G4-01 – phần Tú

- Dataset: `company-tthc-9c38dde8-v1-demo10-v1`
- Số thủ tục: 10
- Số nguồn gốc: 10
- Trạng thái: demo10 đã được phê duyệt cho demo nội bộ; không coi là production-ready.

## 1. Coverage theo field

| Field | Có dữ liệu | Tỷ lệ |
|---|---:|---:|
| receiving_authority | 8/10 | 80.0% |
| submission_methods | 10/10 | 100.0% |
| required_documents | 10/10 | 100.0% |
| fees | 10/10 | 100.0% |
| processing_times | 10/10 | 100.0% |

## 2. Danh sách thủ tục demo10

| # | Thủ tục | Category | receiving_authority | submission_methods | required_documents | fees | processing_times | Missing |
|---|---|---|---:|---:|---:|---:|---:|---|
| 1 | Nội quy lao động | Lao động - Tiền lương | ⚠️ | ✅ | ✅ | ✅ | ✅ | applicant_scope, effective_dates, issuing_authority, jurisdiction |
| 2 | Hỗ trợ chi phí khuyến khích hỏa táng | Văn hóa - Xã hội | ✅ | ✅ | ✅ | ✅ | ✅ | applicant_scope, effective_dates, issuing_authority, jurisdiction |
| 3 | Đăng ký kết hôn có yếu tố nước ngoài | Hộ tịch | ✅ | ✅ | ✅ | ✅ | ✅ | applicant_scope, effective_dates, issuing_authority, jurisdiction |
| 4 | Thủ tục hỗ trợ chi phí khuyến khích hoả táng đối với người dân có hộ khẩu Thành phố Hồ Chí Minh | Văn hóa - Xã hội | ✅ | ✅ | ✅ | ✅ | ✅ | applicant_scope, effective_dates, issuing_authority, jurisdiction |
| 5 | chứng thực chữ ký - chứng thực Hợp đồng giao dịch/Di chúc | Chứng thực - sao y | ✅ | ✅ | ✅ | ✅ | ✅ | applicant_scope, effective_dates, issuing_authority, jurisdiction |
| 6 | Chuyển trường đối với học sinh THCS | giáo dục và đào tạo | ✅ | ✅ | ✅ | ✅ | ✅ | applicant_scope, effective_dates, issuing_authority, jurisdiction |
| 7 | XÁC NHẬN TÌNH TRẠNG NHÀ Ở | Kinh tế - Hạ tầng và đô thị | ⚠️ | ✅ | ✅ | ✅ | ✅ | applicant_scope, effective_dates, issuing_authority, jurisdiction |
| 8 | Tạm ngừng kinh doanh/tiếp tục kinh doanh trước thời hạn đã thông báo của hộ kinh doanh | Kinh tế - Hạ tầng và đô thị | ✅ | ✅ | ✅ | ✅ | ✅ | applicant_scope, effective_dates, issuing_authority, jurisdiction |
| 9 | Thủ tục đăng ký khai sinh | Hộ tịch | ✅ | ✅ | ✅ | ✅ | ✅ | applicant_scope, effective_dates, issuing_authority, jurisdiction |
| 10 | Thủ tục xét, cấp học bổng chính sách | Giáo dục và Đào tạo | ✅ | ✅ | ✅ | ✅ | ✅ | applicant_scope, effective_dates, issuing_authority, jurisdiction |

## 3. Missing fields lặp lại

| Field | Số thủ tục |
|---|---:|
| applicant_scope | 10 |
| effective_dates | 10 |
| issuing_authority | 10 |
| jurisdiction | 10 |
| legal_bases | 10 |
| procedure_code | 10 |
| public_url | 10 |
| steps | 10 |
| receiving_authority | 2 |

## 4. Nhận xét nghiệp vụ

- `receiving_authority`, `required_documents`, `fees`, `processing_times` là các field trọng tâm cho 10 thủ tục demo; các field còn thiếu chủ yếu thuộc metadata thủ tục (`applicant_scope`, `effective_dates`, `issuing_authority`, `jurisdiction`, `legal_bases`, `procedure_code`, `public_url`) và `steps`.
- `submission_methods` có đầy đủ trên hầu hết thủ tục nên thích hợp làm baseline cho retrieval theo field và intent gắn với điều kiện nộp.
- `fees` và `processing_times` đôi khi có định dạng rời rạc hoặc mơ hồ (`0.0`, `“không quy định cụ thể”`, `“3–5 ngày làm việc”`); cần review chốt trước khi dùng trong TEST_V2 để tránh đánh giá nhầm ý nghĩa.
- Với G4-01, không mở rộng dữ liệu bằng cách gán nhãn máy mà không có reviewer thứ hai; các ca mơ hồ phải giữ trạng thái `PENDING_REVIEW` hoặc `INSUFFICIENT_DATA` thay vì tự pass.

## 5. Danh sách ambiguous cần review

| Procedure ID | Field | Dữ liệu cần làm rõ |
|---|---|---|
| `d2_title_1e0d3df69ad5` | `fees` | {'amount_vnd': None, 'condition': None, 'raw_text': '10.000 đồng/trường hợp (đối với chứng thực chữ ký) 50.000 đồng/trường hợp (đối với hợp đồng giao dịch/Di chúc)'} |
| `d2_title_2dc6a6a0b92a` | `processing_times` | {'condition': None, 'max_business_days': 5.0, 'min_business_days': 3.0, 'raw_text': '3–5 ngày làm việc kể từ khi nhận đủ hồ sơ hợp lệ.'} |
| `d2_title_30228658fce3` | `fees` | {'amount_vnd': None, 'condition': None, 'raw_text': '0.0'} |
| `d2_title_30228658fce3` | `processing_times` | {'condition': None, 'max_business_days': None, 'min_business_days': None, 'raw_text': '05'} |
| `d2_title_34afa9c1ded0` | `fees` | {'amount_vnd': None, 'condition': None, 'raw_text': '0.0'} |
| `d2_title_ff5c71001a91` | `processing_times` | {'condition': None, 'max_business_days': None, 'min_business_days': None, 'raw_text': 'không quy định cụ thể (chi trả theo học kỳ)'} |

## 6. Kế hoạch DEV/TEST_V2 theo `scenario_group_id`

- Tách theo `procedure_family` + `field_intent` + `ambiguity_pattern`, không chia ngẫu nhiên paraphrase.
- Mục tiêu: 80 DEV và 40 TEST_V2 trong khoảng 120 scenario, với ít nhất 20 scenario nhiều lượt.
- Mỗi scenario gồm: `scenario_group_id`, `procedure_id`, `field_expected`, `expected_status`, `gold_fragment_ids`, `gold_label`, `gold_answer`, `must_include`, `must_exclude`, `conversation_turns`.

### Nhóm scenario gợi ý
- G-01: `receiving_authority` — nơi nộp, nơi làm, cơ quan tiếp nhận.
- G-02: `fees` — được miễn, có phí, mức phí theo trường hợp, điều kiện áp dụng.
- G-03: `processing_times` — số ngày làm việc, điều kiện tính từ ngày nào.
- G-04: `required_documents` — thành phần hồ sơ và điều kiện bổ sung.
- G-05: `submission_methods` — trực tiếp / qua mạng / bưu chính / hỗn hợp.
- G-06: hội thoại ngắn — `hồ sơ → nơi nộp → lệ phí`, `còn lệ phí?`, `bao lâu?`.
- G-07: thiếu dữ kiện / sai phạm vi — không suy đoán khi không có evidence.

### Lưu ý split
- DEV dùng 8 procedure family; TEST_V2 dùng 2 procedure family khác hoàn toàn, không trùng `procedure_id` giữa hai split.
- TEST_V2 hiện ở `PENDING_REVIEW`; sau reviewer duyệt mới chuyển sang `LOCKED` cùng manifest/hash.
- Duyệt chéo bởi reviewer thứ hai trước khi đóng gói; TEST_V2 chỉ gửi Hoan, Minh chỉ nhận DEV/schema/tool.

## 7. Đề xuất action tiếp theo

1. Duyệt 10 thủ tục demo theo 6 field: hồ sơ, phí, thời gian, nơi tiếp nhận, hình thức nộp và bước xử lý.
2. Chốt danh sách `scenario_group_id` dựa trên 7 nhóm trên, rồi phân 80/40 cho DEV/TEST_V2.
3. Lưu ý 20+ scenario nhiều lượt để test hội thoại ngắn và context carry-over.
4. Báo cáo missing/conflict đến Minh và Hoan trước khi mở rộng dữ liệu.
