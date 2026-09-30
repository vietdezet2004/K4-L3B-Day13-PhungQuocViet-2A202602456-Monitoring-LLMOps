# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert mẫu để tham khảo

Ví dụ dưới đây minh họa mức độ cụ thể cần có. Học viên không cần copy nguyên, nhưng ba alert trong bài nộp nên rõ ràng tương tự: điều kiện là gì, kéo dài bao lâu, ảnh hưởng tới user ra sao và người trực cần kiểm tra gì trước.

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: latency P95 của `response_sent.latency_ms`
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` trong 5 phút
- Ảnh hưởng tới người dùng: người dùng phải chờ lâu hơn trước khi nhận câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard latency để xác nhận P95/P99 và khoảng thời gian tăng.
  2. Lọc `data/logs.jsonl` trong khoảng đó, lấy một `correlation_id` có `latency_ms` cao.
  3. Mở trace cùng `correlation_id` trên Langfuse, so sánh các span chính để xác định bước nào bất thường.
- Mitigation tạm thời: dựa trên evidence thực tế để rollback prompt, khôi phục cấu hình liên quan, tắt practice scenario hoặc giảm tải khi demo.
- Owner: `student-<MSSV>`

## Alert 1

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: `response_sent.latency_ms` (P95)
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` trong 5 phút liên tục
- Ảnh hưởng tới người dùng: Người dùng phải chờ lâu hơn trước khi nhận câu trả lời từ AI Assistant, có nguy cơ vi phạm thỏa thuận dịch vụ (SLO 99.5%).
- Ba bước kiểm tra đầu tiên:
  1. Mở panel Latency trên Dashboard để xác nhận P95/P99 và khoảng thời gian bắt đầu tăng độ trễ.
  2. Mở file `data/logs.jsonl`, lọc các log `response_sent` có `latency_ms > 3000` và trích xuất một `correlation_id` đại diện.
  3. Mở Trace trên Langfuse theo `correlation_id` đó, kiểm tra xem độ trễ nằm ở span `retrieval` (RAG vector search) hay `generation` (LLM call).
- Mitigation tạm thời: Nếu do prompt mới làm câu trả lời quá dài, thực hiện rollback label `production` về version prompt trước đó; nếu do Vector Store quá tải, kiểm tra kết nối mạng hoặc tạm thời chuyển sang cached context.
- Owner: `student-2A202602456`

## Alert 2

- Tên: `HighErrorRate`
- Severity: `critical`
- Duration: `2m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: `count(event == "request_failed") / count(event == "request_received") * 100`
- Điều kiện và thời gian duy trì: `error_rate_pct > 2%` trong 2 phút liên tục
- Ảnh hưởng tới người dùng: Người dùng gặp lỗi HTTP 500, không nhận được câu trả lời từ hệ thống, gây gián đoạn dịch vụ.
- Ba bước kiểm tra đầu tiên:
  1. Mở panel Errors trên Dashboard để kiểm tra tỉ lệ lỗi hiện tại và phân bố loại lỗi (`error_type`).
  2. Lọc file `data/logs.jsonl` tìm các sự kiện `request_failed`, kiểm tra `error_type` (ví dụ `RuntimeError: Vector store timeout`) và thông điệp lỗi trong `payload.detail`.
  3. Mở Trace có `correlation_id` bị lỗi trên Langfuse để xem exception stack trace và quan sát span nào bị fail đỏ.
- Mitigation tạm thời: Khởi động lại dịch vụ phụ thuộc nếu bị treo kết nối; nếu do kịch bản kiểm thử sự cố (incident injection), chạy `python scripts/inject_incident.py --disable`; kích hoạt circuit breaker để fallback sang câu trả lời an toàn.
- Owner: `student-2A202602456`

## Alert 3

- Tên: `LowRetrievalSuccessRate`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: `retrieval_success_rate_pct` (tỉ lệ request tìm thấy tài liệu phù hợp trong Corpus)
- Điều kiện và thời gian duy trì: `retrieval_success_rate_pct < 90%` trong 5 phút liên tục
- Ảnh hưởng tới người dùng: Agent không tìm được tài liệu ngữ cảnh (domain docs) để trả lời, phải dùng câu trả lời chung chung hoặc fallback answer, làm giảm sút chất lượng câu trả lời.
- Ba bước kiểm tra đầu tiên:
  1. Mở panel Errors & Retrieval Success trên Dashboard để xem tỉ lệ tìm kiếm tài liệu thành công.
  2. Mở file `data/logs.jsonl` lọc các log `response_sent` có `tool_name == "retrieval"` và kiểm tra xem `tool_success` có bị `False` hoặc câu trả lời có chứa nhãn cảnh báo không.
  3. Mở Trace trên Langfuse, quan sát span `retrieval` kiểm tra output `doc_count` và các query text của người dùng xem có nằm ngoài phạm vi tri thức hay không.
- Mitigation tạm thời: Kiểm tra trạng thái index của Vector Database; bổ sung tài liệu còn thiếu vào corpus; cập nhật prompt để cải thiện khả năng suy luận khi tài liệu rỗng.
- Owner: `student-2A202602456`
