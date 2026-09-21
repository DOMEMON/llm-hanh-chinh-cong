# Bàn giao phần Minh — MCP tra cứu thông tin hiện hành

## Trạng thái bàn giao

Đã triển khai tool MCP riêng, client backend, xác nhận nhiều lượt, fallback,
feature flag mặc định tắt và test offline. Bản gốc là archive commit
`b019701fcd1f18b24e5e7afc7552467fdd2965ab` anh gửi.

**Chưa xác nhận tra cứu thành công trên Cổng DVC thật.** Khi thử truy cập, trang
chính trả timeout/502 và trang thutuc trả 503. Adapter hiện hỗ trợ HTML và form GET
được chính trang chính thức công bố, không đoán API hay tham số tìm kiếm. Nếu cổng
chỉ render kết quả bằng JavaScript hoặc thay đổi cấu trúc HTML, tool trả NOT_FOUND
và backend dùng local. Cần xác minh trên mạng truy cập được DVC, bổ sung adapter
cho giao diện thực tế nếu cần, trước khi coi đây là bản tích hợp live hoàn tất.

Chưa chạy toàn bộ Docker G5 với model/corpus nội bộ; chưa chạy test tích hợp
PostgreSQL thật; chưa push branch hoặc mở PR trên GitHub.

## Đã thay đổi gì

| File | Vai trò |
| --- | --- |
| `source-service/app/current_procedure.py` | Tải trang chính thức có giới hạn, khám phá form GET, chọn liên kết đúng tên thủ tục, đọc trường theo nhãn và xác minh địa phương. |
| `source-service/app/realtime_contract.py` | Input/output schema, danh sách domain, kiểm tra URL và điều kiện FOUND. |
| `source-service/app/server.py` | Đăng ký tool `lookup_current_procedure`, tách khỏi tool review/publish cũ. |
| `backend/app/rag/g5/realtime_contract.py` | Cùng wire contract, dùng xác minh payload tại backend; test đảm bảo hai bản khớp nhau. |
| `backend/app/rag/g5/source_mcp.py` | Thêm `lookup_current`, kiểm tra schema, identity, trường, địa phương, citation và độ mới của thời điểm kiểm tra. |
| `backend/app/rag/g5/realtime.py` | Tạo lời mời, nhận đồng ý/từ chối rõ ràng, tiêu thụ yêu cầu một lần, hiển thị kết quả hoặc fallback. |
| `backend/app/rag/g5/intent_context.py` | Thêm `pending_realtime` do backend quản lý, không đưa vào state gửi model. |
| `backend/app/chat.py` | Xử lý xác nhận trước intent router; commit việc xóa pending trước khi gọi mạng. |
| `backend/app/rag/catalog_policy.py` | Mời kiểm tra khi hỏi thời gian/nơi tiếp nhận hoặc thiếu trường local, với thủ tục đã xác định. |
| `backend/app/config.py`, `.env.example`, `compose.g5.yaml` | Feature flag riêng cho tra cứu hiện hành, mặc định tắt ở backend và source service. |
| `source-service/tests/`, `backend/tests/test_g5_realtime*.py`, `backend/tests/test_g5_source_mcp.py` | Test tool, transport, schema, nhiều lượt và retry. |

Không đổi dependency/lockfile. Không sửa corpus, model, adapter, dictionary của Tú
hoặc store review/publish. Các test mới dùng dữ liệu thủ tục hư cấu.

## Luồng hoạt động

1. G5 trả câu trả lời từ local như trước.
2. Khi đã có thủ tục, địa phương và trường cần kiểm tra, backend lưu pending và hỏi:
   “Bạn có muốn kiểm tra thông tin hiện tại trên Cổng DVC Quốc gia không?”
3. Lời mời ghi rõ tên thủ tục, địa phương và **một trường** được kiểm tra.
   Nếu hỏi nhiều trường, mỗi lời mời chọn trường đầu tiên đủ điều kiện.
4. Câu “đồng ý”, “có”, “ok”, “kiểm tra đi”… khớp toàn bộ câu mới là chấp thuận.
   “Đồng ý nhưng đổi sang thủ tục khác” không được xem là đồng ý cho yêu cầu cũ.
5. Backend xóa pending và commit trong khóa conversation hiện có trước khi gọi tool.
   Gửi lại cùng `client_message_id` trả lại câu trả lời đã lưu, không gọi lần hai.
6. FOUND hiển thị thêm kết quả web, URL và thời điểm UTC. Dữ liệu web được ghi rõ
   chưa qua review nội bộ, không thay thế evidence bundle local.
7. ERROR, NOT_FOUND, AMBIGUOUS, payload sai hoặc địa phương không xác minh được:
   thông báo chưa xác minh và hiển thị lại local đã duyệt.
8. Từ chối không gọi tool. Đổi câu hỏi/filter, tắt flag, thay corpus, quá 15 phút
   hoặc sang ngày UTC mới thì không tái sử dụng lời mời cũ.

Lưu ý: registry MCP đọc snapshot PUBLISHED sẵn có vẫn là luồng nội bộ cũ.
Cổng xác nhận mới kiểm soát tool tra cứu web `lookup_current_procedure`.

## Giới hạn tra cứu được chủ động áp dụng

- HTTPS và chỉ 4 hostname: `dichvucong.gov.vn`, `www.dichvucong.gov.vn`,
  `thutuc.dichvucong.gov.vn`, `vpcp.dichvucong.gov.vn`.
- Kiểm tra domain trước mỗi request và mỗi redirect; không search Internet chung.
- Chỉ tên thủ tục trùng chính xác sau chuẩn hóa khoảng trắng/chữ hoa thường;
  ID nội bộ được giữ nguyên, không giả định bằng mã thủ tục của DVC.
- Phải thấy địa phương trong nhãn địa phương/cơ quan của nội dung thủ tục;
  không dùng menu/footer để suy ra địa phương. Không tự suy tỉnh từ tên phường.
- Đọc giá trị cạnh nhãn hoặc đúng cột bảng; bảng gộp ô không xác định được thì bỏ qua.
- Không có locality xác nhận trong state: không mời tra cứu; tiếp tục luồng hỏi rõ
  địa phương của G5. Không tự đoán địa phương mặc định.
- Chỉ xác minh ngày hiện tại UTC, không khẳng định thông tin lịch sử/tương lai.
- Tối đa 6 liên kết ứng viên; nhiều kết quả hợp lệ thì AMBIGUOUS.
- Body tối đa 1 MiB; giới hạn cây HTML và redirect; socket timeout tối đa 4 giây,
  deadline tool 6 giây, backend mặc định 8 giây. Request chạy trong thread có thể
  hoàn tất socket read sau khi deadline phía async đã trả fallback.
- Text web không đưa vào prompt model, được escape khi hiển thị.
- Tên gần giống/alias, trang JavaScript hoặc nhãn không nhận diện được sẽ bị từ chối
  thay vì suy đoán. Đây là giới hạn cần đánh giá bằng smoke test thật.

## Chạy test offline

Tại thư mục source-service:

```powershell
Set-Location source-service
uv sync --frozen --group dev
uv run pytest -q
Set-Location ..
```

Tại backend:

```powershell
Set-Location backend
uv sync --frozen --group dev
uv run pytest -q tests/test_g5_realtime.py tests/test_g5_realtime_chat.py tests/test_g5_source_mcp.py tests/test_g5_intent_context.py tests/test_config.py
Set-Location ..
```

Kết quả kiểm tra trong môi trường bàn giao: **38 test source-service + 78 test
backend = 116 test passed**. Ruff đạt, `git diff --check` đạt.

Hai test chat gọi hàm `send_message` thật nhưng thay DB bằng in-memory double,
thay intent/RAG bằng fixture; chúng kiểm tra thứ tự commit, không gọi trước đồng ý,
từ chối không gọi, giữ đúng procedure/field và retry cùng message không gọi lại.
Chúng không thay thế test transaction PostgreSQL hoặc full Docker runtime.

## Bật/tắt

Mặc định:

```dotenv
G5_REALTIME_MCP_ENABLED=false
G5_REALTIME_MCP_TIMEOUT_SECONDS=8
```

Sau khi hệ thống G5 gốc đã chạy được, đặt `G5_REALTIME_MCP_ENABLED=true` trong
môi trường của **cả backend lẫn source-service**. Compose G5 đã chuyển biến này
vào hai service. Backend cần `G5_INTENT_CONTEXT_ENABLED=true` như overlay G5 hiện có.
Flag này độc lập với `G5_SOURCE_MCP_ENABLED` của registry dữ liệu đã duyệt.

Dùng lại lệnh/script G5 hiện có với model/corpus/token của anh, rebuild source-service
và backend. Nếu dùng `scripts/demo-g5.ps1`, có thể đặt biến process trước khi chạy
lại đúng lệnh demo anh đang dùng:

```powershell
$env:G5_REALTIME_MCP_ENABLED = 'true'
```

Tắt bằng `false` rồi recreate hai container. Không chỉ sửa `.env` mà giữ nguyên
container đang chạy, vì container vẫn giữ giá trị environment cũ.

## Smoke test trên máy truy cập được DVC

1. Chọn một thủ tục thực sự có trong corpus, dùng đúng tên canonical và địa phương.
2. Hỏi thời hạn giải quyết tại địa phương đó; kiểm tra local và lời mời xuất hiện.
3. Chưa trả lời: không được có request `lookup_current_procedure`.
4. Trả lời “đồng ý”: kiểm tra URL thuộc allowlist, đúng tên/trường/địa phương và timestamp.
5. Gửi lại đúng message ID: không được gọi tool lần thứ hai.
6. Lặp với “không”, đổi sang câu hỏi khác, tắt flag, lỗi mạng và địa phương khác.
7. Nếu tool báo `DVC_NO_EXACT_HTML_RESULT_OR_JS_SEARCH_REQUIRED`, cần xem HTML/network
   của cổng chính thức trên máy truy cập được và viết adapter theo endpoint thực tế.
   Không sửa thành FOUND giả, không dùng kết quả báo/blog để lấp dữ liệu.

Có thể gọi tool trực tiếp để xem `retrieval_note`, dùng Python trong môi trường
source-service đã `uv sync` (điền đúng thông tin, chọn ngày UTC hiện tại):

```python
import asyncio
from datetime import datetime, timezone
from mcp import Client

async def main():
    async with Client('http://localhost:8096/mcp') as client:
        result = await client.call_tool('lookup_current_procedure', {
            'procedure_id': 'DIEN_ID_TU_CORPUS',
            'procedure_name': 'DIEN_TEN_CANONICAL',
            'field': 'processing_times',
            'jurisdiction': 'DIEN_DIA_PHUONG',
            'as_of': datetime.now(timezone.utc).date().isoformat(),
        })
        print(result.structured_content)

asyncio.run(main())
```

Đoạn trên là smoke test chủ động do người vận hành chạy, không phải luồng tự động
bỏ qua xác nhận trong chat. Port 8096 là port host mặc định của source-service;
đổi nếu cấu hình local của anh khác.

## Đưa thay đổi vào repository

ZIP có toàn bộ code, báo cáo này và `MINH_REALTIME_MCP.patch`. Không kèm `.git`,
`.venv`, cache hoặc `.env` riêng. File phân công nội bộ không đưa vào ZIP code.

Trên clone thật, checkout baseline và branch làm việc. Nếu đã có branch này thì
chuyển sang branch hiện có, không tạo đè. Kiểm tra working tree sạch trước khi áp patch:

```powershell
git switch -c feature/minh-realtime-mcp b019701fcd1f18b24e5e7afc7552467fdd2965ab
git apply --check 'DUONG_DAN_DEN\MINH_REALTIME_MCP.patch'
git apply 'DUONG_DAN_DEN\MINH_REALTIME_MCP.patch'
```

Chạy test, kiểm tra `git diff`, sau đó commit/push trên clone có quyền của anh.
Chỉ stage file code/config/test liên quan; không stage `.env`, token, model,
dataset nội bộ hoặc tài liệu phân công. Báo cáo này dành cho bàn giao; anh có thể
đọc riêng, không bắt buộc commit cùng code. Patch chỉ chứa code/config/test.
