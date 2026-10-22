# Báo cáo IEEE

| Báo cáo | Nội dung | PDF |
| --- | --- | --- |
| RP1 — Hệ thống tư vấn pháp lý: Hỗ trợ tra cứu thủ tục hành chính | Kiến trúc, multi-intent, hội thoại nhiều lượt, bằng chứng nguồn và thực nghiệm trên thủ tục hành chính | [Đọc / tải RP1](RP1_he-thong-tu-van-phap-ly.pdf) |
| RP2 — Hệ thống tự động tạo package từ dữ liệu dạng bảng cho hệ thống LLM | CSV/Excel → khảo sát bảng → metadata/mapping → package → kiểm chứng và sử dụng | [Đọc / tải RP2](RP2_he-thong-tu-dong-tao-package.pdf) |

Tác giả: Bùi Xuân Hoan, Phạm Lê Minh, Phan Văn Tú — FPT University.
Hai PDF được sao chép nguyên bản từ bản thảo đã biên dịch; các liên kết Fig./Table
trong PDF được giữ nguyên. Hình kiến trúc có tại [LLM tư vấn pháp lý](../assets/he-thong-llm-tu-van-phap-ly.png)
và [LLM Reusable](../assets/he-thong-llm-reusable.png).

## Đối chiếu với source cập nhật ngày 22/10/2026

Số liệu trong bài gắn với phiên bản và bộ đo được trình bày trong từng PDF.
Source mới bổ sung các sửa lỗi sau giai đoạn viết bài. Kết quả hồi quy mới
được ghi dưới đây để đối chiếu, không thay số liệu trong PDF.

| Kiểm tra bản xuất bản | Kết quả |
| --- | ---: |
| LLM tư vấn pháp lý: kiểm thử backend offline | 223/223 |
| LLM Reusable: kiểm thử package/runtime/API offline | 180/180 |
| LLM Reusable: yêu cầu API hoàn tất trên 11 dataset | 221/221 |
| LLM Reusable: khớp đủ kết quả, trạng thái và tiêu chí bằng chứng | 218/221 |
| LLM Reusable: DEV, gồm multi-intent và hội thoại nhiều lượt | 176/176 |
| LLM Reusable: tra cứu cơ bản lấy mẫu | 11/11 |
| LLM Reusable: gợi ý câu hỏi UI | 28/31 |
| LLM Reusable: câu tái hiện / đổi cách diễn đạt lỗi người dùng | 3/3 |

Kiểm tra API dùng 11 dataset: hành chính, Auto MPG, Penguins, Bike Daily, Wine
Quality, Synthetic Office, Transfer Assets, Transfer Courses, Travel, Equipment,
Recipes. Có 1/2/3/5/7/8 intent, ngữ cảnh hai bản ghi, trường thiếu và giới hạn
capability. Giữ nguyên 221 câu, gold và scorer của lượt trước sửa; SHA-256 của
`cases.json`: `41dddb27067e34dfbfb70607b35b78b1f1f77764cb9c8584f1255afa09fcf2d1`.

Ba ca chưa khớp scorer được giữ lại trong kết quả 218/221:

- Liệt kê timestamp/email của bảng hành chính và name/access của bảng du lịch:
  giá trị trả về khớp nguồn, nhưng trạng thái là `partial` vì có ô thiếu;
  gold cũ yêu cầu `answer`.
- Liệt kê hai cột Wine Quality: nguồn có 1.599 dòng, API trả tối đa 1.000 dòng
  và báo `partial`, trong khi gold yêu cầu toàn bộ danh sách.

Không có timeout hoặc lỗi HTTP trong lượt cuối. Đây là kiểm thử hồi quy sau
phân tích lỗi, không phải tập holdout độc lập hoặc benchmark tốc độ mới.
Test offline dùng model giả lập; số lượng test offline khác số câu đánh giá
LLM thật. Dữ liệu, credential và log hội thoại kiểm thử không kèm trong repo.

Hướng dẫn chạy source: [LLM tư vấn pháp lý](../He-thong-LLM-tu-van-phap-ly/README.md),
[LLM Reusable](../He-thong-LLM-reusable/README.md).
