# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:** Phùng Quốc Việt
- **MSSV:** 2A202602456
- **Lớp:** K4-L3B
- **Repository URL:** <https://github.com/vietdezet2004/K4-L3B-Day13-PhungQuocViet-2A202602456-Monitoring-LLMOps.git>
- **Commit SHA cuối:**
- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-2a202602456`

## 2. Evidence index

Điền đúng đường dẫn tới evidence thực tế. Có thể đổi tên hoặc dùng nhiều ảnh nếu cần.

| Evidence | Đường dẫn |
| --- | --- |
| Pytest cuối | `evidence/01-pytest.png` |
| Log validator | `evidence/02-log-validator.png` |
| Dashboard validator | `evidence/03-dashboard-validator.png` |
| Structured log | `evidence/04-structured-log.png` |
| PII redaction | `evidence/05-pii-redaction.png` |
| Trace list | `evidence/06-trace-list.png` |
| Trace waterfall | `evidence/07-trace-waterfall.png` |
| Trace metadata | `evidence/08-trace-metadata.png` |
| Prompt versions | `evidence/09-prompt-versions.png` |
| Prompt rollback | `evidence/10-prompt-rollback.png` |
| Dashboard runtime | `evidence/11-dashboard-overview.png` |
| Incident metric | `evidence/12-incident-metric.png` |
| Incident log | `evidence/13-incident-log.png` |
| Incident trace | `evidence/14-incident-trace.png` |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
| --- | --- | --- | --- |
| `validate_logs.py` | 30/100 | 100/100 | Đạt toàn bộ 4 tiêu chí: JSON schema, correlation ID propagation, enrichment context, PII scrubbing |
| `validate_dashboard.py` | HỢP LỆ: 6/6 panel | HỢP LỆ: 6/6 panel | Đầy đủ 6 panel theo dashboard contract: latency, traffic, errors, cost, tokens, quality |
| `pytest` | 22 passed in 1.44s | 22 passed in 1.68s | Toàn bộ 22/22 unit và contract test đều pass xanh |
| Số traces hợp lệ | 0 | 23+ | Traces đẩy lên Langfuse Cloud với đầy đủ span tree 3 tầng |
| Số PII leak | 0 | 0 | 100% không phát hiện rò rỉ email, số điện thoại, thẻ tín dụng trong log và trace |
| Latency P95 / TTFT P95 | 663.0ms / 50ms | 3436.4ms / 50ms | P95 latency phản ánh workload có retrieval và LLM generation thực tế |
| Retrieval success rate | 100% | 100% | RAG retrieval hoạt động ổn định và tìm thấy tài liệu phù hợp |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:**
  Được triển khai trong `app/middleware.py`: Trích xuất header `x-request-id` từ HTTP request gửi đến; nếu không có hoặc không hợp lệ, middleware tự động sinh mới với định dạng `req-<8-hex>` (`f"req-{secrets.token_hex(4)}"`). Correlation ID được lưu vào ContextVar thông qua `structlog.contextvars.bind_contextvars(correlation_id=corr_id)` để tự động đính kèm vào mọi log entry phát sinh trong suốt vòng đời của request. Đồng thời được gán vào `request.state.correlation_id` và trả ngược về client trong response header `x-request-id` cùng `x-response-time-ms`.
- **Các metadata được ghi vào structured log:**
  Các trường metadata bao gồm: `ts` (ISO 8601 UTC timestamp), `event` (`request_received`, `response_sent`, `request_failed`), `service` ("api" hoặc tên service), `correlation_id` (ID truy vết xuyên suốt), `user_id_hash` (mã băm SHA256 12 ký tự của user_id), `session_id`, `feature` (vd: "qa", "summary"), `model` ("claude-sonnet-4-5"), `env` ("dev"), `latency_ms` (tổng thời gian xử lý), `ttft_ms` (time to first token), `tokens_in`, `tokens_out`, `cost_usd`, `tool_name` ("retrieval"), `tool_success` (bool), và payload tóm tắt (không chứa PII).
- **Cách bảo đảm PII được scrub trước khi ghi:**
  Triển khai bộ lọc `scrub_event` đệ quy trong `app/logging_config.py` được đăng ký trong chuỗi xử lý structlog (`processors`) trước khi log được ghi ra file hoặc console. Sử dụng Regex pattern nhận diện số điện thoại VN (10 chữ số), email (`[\w\.-]+@[\w\.-]+\.\w+`), số CMND/CCCD (9 hoặc 12 chữ số), và thẻ tín dụng (16 chữ số chia cụm 4), thay thế lần lượt bằng `[REDACTED_PHONE]`, `[REDACTED_EMAIL]`, `[REDACTED_ID]`, `[REDACTED_CARD]`. Dữ liệu nhạy cảm được quét sâu qua cả string, list, dict và các trường lồng nhau.
- **Cách kiểm chứng kết quả:**
  Chạy `python scripts/validate_logs.py` kiểm tra toàn bộ file `data/logs.jsonl`. Kết quả đạt điểm tuyệt đối 100/100, xác nhận 0 missing fields, 0 missing enrichment context, và 0 potential PII leaks. Đồng thời gửi request thử nghiệm chứa email và số điện thoại giả qua `scripts/load_test.py`, đối soát log trong `data/logs.jsonl` thấy chuỗi PII đã được thay thế hoàn toàn bằng token redacted.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:**
  Trong file `.env`, cấu hình `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` lấy trực tiếp từ project cá nhân `day13-k4-l3b-2a202602456` trên Langfuse Cloud (`https://cloud.langfuse.com`). Khi gửi request, metadata của trace gắn `user_id_hash`, `tags=["lab", feature, self.model]`, `environment="dev"`, và tên project hiển thị rõ ràng trên góc trên bên trái của Langfuse dashboard.
- **Cấu trúc root/retrieval/generation observations:**
  Triển khai cây 3 tầng phân cấp rõ ràng theo chuẩn Langfuse SDK v4 trong `app/agent.py`:
  1. Root Observation: `day13-agent-request` (Trace) chứa observation gốc `@observe(name="lab-agent-run", as_type="agent")`.
  2. Child Observation 1: Span `retrieval` (`as_type="span"`), đo độ trễ RAG vector search, ghi nhận input tóm tắt và output `doc_count`.
  3. Child Observation 2: Generation `generation` (`as_type="generation"`), liên kết với prompt quản lý, ghi nhận token usage (`input`, `output`, `total`), chi phí `cost_details`, và model "claude-sonnet-4-5".
- **Cách nối trace với log:**
  Trong `app/agent.py`, trường `correlation_id` được truyền vào `propagate_attributes(metadata={"correlation_id": correlation_id, ...})`. Nhờ đó, cả `data/logs.jsonl` và Langfuse Trace Metadata đều chia sẻ cùng một giá trị `correlation_id` duy nhất (ví dụ: `req-1db7f351`). Khi gặp sự cố hoặc cần debug, kỹ sư chỉ cần copy `correlation_id` từ log để tìm trực tiếp trace tương ứng trên Langfuse và ngược lại.
- **Prompt name:** `day13-chat`
- **Version/label baseline:** Version 1 (Labels: `baseline`, `production`), template gốc chứa các biến `{{feature}}`, `{{docs}}`, `{{message}}`.
- **Version/label candidate:** Version 2 (Labels: `candidate`), bổ sung hướng dẫn câu trả lời ngắn gọn: `Instruction: Please provide a concise answer.`.
- **Trace ID của mỗi version:**
  - **Trace V1 (Baseline):** Trace ID: `cfd1b2fc2b40a18d8ce8978b1ce54505` (Observation ID: `91227a327c3d783b`, Correlation ID: `req-1db7f351`, Prompt Version: `1`, Label: `production`/`baseline`).
  - **Trace V2 (Candidate):** Trace ID: `d7689276281c3d63b49ae9aa1781ed00` (Observation ID: `d7689276281c3d63b49ae9aa1781ed00`, Correlation ID: `req-5c23cb79`, Prompt Version: `2`, Label: `candidate`).
- **Cách promote và rollback `production`:**
  - *Promote:* Trên giao diện Langfuse UI (Prompts > `day13-chat`), chuyển nhãn `production` từ Version 1 sang Version 2 (hoặc qua SDK bằng `client.update_prompt(name='day13-chat', version=2, new_labels=['candidate', 'production'])`).
  - *Rollback:* Khi phát hiện Version 2 có sự cố hoặc suy giảm chất lượng, thực hiện gán lại nhãn `production` cho Version 1 (Langfuse sẽ tự động gỡ nhãn `production` khỏi Version 2), đưa toàn bộ lưu lượng production lập tức quay trở lại chạy với Version 1 mà không cần redeploy code ứng dụng.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:**
  Được xây dựng trực tiếp tại endpoint `/dashboard` (`http://127.0.0.1:8000/dashboard`) đọc dữ liệu realtime từ `data/logs.jsonl`, hiển thị giao diện dark-mode hiện đại, tự động refresh sau 30s. Bao gồm đủ 6 panel theo `config/dashboard.yaml`:
  1. *Latency percentiles and TTFT:* Hiển thị P50, P95, P99 của `latency_ms` và P95 của `ttft_ms`, có threshold line P95 ≤ 3000ms.
  2. *Request traffic:* Đo tốc độ request theo phút (`rate_per_minute ≥ 1`) và số lượng request đã xử lý.
  3. *Error rate and retrieval success:* Tỉ lệ lỗi (`error_rate_pct ≤ 2%`) và tỉ lệ tìm kiếm tài liệu thành công (`retrieval_success_rate ≥ 90%`).
  4. *Cost over time:* Tổng chi phí USD tích lũy (`total_cost ≤ $2.5 USD`) và chi phí trung bình trên mỗi request.
  5. *Input and output tokens:* Tổng số token in/out (`sum_by_field ≤ 50,000`).
  6. *Quality proxy:* Điểm chất lượng trung bình dựa trên heuristic đánh giá độ đầy đủ của ngữ cảnh và câu trả lời (`mean ≥ 0.75`).
- **SLO và lý do chọn:**
  Dịch vụ cấu hình SLO chính: `fast_successful_requests` với mục tiêu 99.5% trong cửa sổ 28 ngày (`target_percent: 99.5`). Good event được định nghĩa là request trả về thành công và có độ trễ `latency_ms <= 3000ms`. Tổng event là `request_received`.
  *Lý do chọn:* Độ trễ phản hồi dưới 3 giây là tiêu chuẩn trải nghiệm người dùng tối ưu cho AI Assistant tương tác dạng chat. Tỉ lệ 99.5% đảm bảo độ sẵn sàng cao nhưng vẫn cho phép một lượng error budget hợp lý để đội ngũ triển khai tính năng và cải tiến prompt.
- **Cách tính error budget:**
  SLO 99.5% trong 28 ngày nghĩa là error budget 0.5%. Với workload 10,000 requests, tối đa 50 requests được phép lỗi hoặc có độ trễ vượt quá 3000ms (`10,000 * 0.5% = 50`). Nếu số lượng request vi phạm vượt quá ngân sách này, error budget cạn kiệt và đội ngũ kỹ thuật phải ưu tiên ổn định hạ tầng thay vì ra mắt tính năng mới.
- **Ba alert và runbook tương ứng:**
  Cấu hình trong `config/alert_rules.yaml` và tài liệu hóa chi tiết tại `docs/alerts.md`, tuân thủ nguyên tắc symptom-based (dựa trên triệu chứng ảnh hưởng người dùng):
  1. *HighLatencyP95 (Warning):* `p95(latency_ms) > 3000ms` duy trì trong 5m. Triệu chứng: Người dùng đợi lâu. Triage: Check panel Latency -> lọc log tìm `correlation_id` có độ trễ cao -> mở trace Langfuse xác định nghẽn ở `retrieval` hay `generation`. Runbook: `docs/alerts.md#alert-1`.
  2. *HighErrorRate (Critical):* `error_rate_pct > 2%` duy trì trong 2m. Triệu chứng: Request trả về 500, gián đoạn phục vụ. Triage: Check panel Errors -> lọc log `request_failed` lấy `error_type` -> xem trace stack trace. Runbook: `docs/alerts.md#alert-2`.
  3. *LowRetrievalSuccessRate (Warning):* `retrieval_success_rate_pct < 90%` duy trì trong 5m. Triệu chứng: RAG không tìm được tài liệu ngữ cảnh, câu trả lời suy giảm chất lượng. Triage: Check panel Retrieval Success -> lọc log `tool_success == False` -> kiểm tra input/output span `retrieval`. Runbook: `docs/alerts.md#alert-3`.

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`
- **Khoảng thời gian điều tra:** 13:44:50 - 13:46:10 (Asia/Ho_Chi_Minh) / 2026-09-30T06:44:50Z - 2026-09-30T06:46:10Z
- **Triệu chứng từ metrics:** Dashboard và /metrics ghi nhận latency P95 tăng vọt từ 240ms lên 2,652ms (vượt ngưỡng threshold 2,000ms quy định trong challenge). Panel errors không tăng (0% error rate), cho thấy request vẫn thành công nhưng bị suy giảm hiệu năng nghiêm trọng (tail latency spike).
- **Log line và correlation ID liên quan:**
  Dòng log `response_sent`:
  `{"service": "api", "latency_ms": 2652, "ttft_ms": 50, "tokens_in": 36, "tokens_out": 116, "cost_usd": 0.001848, "quality_score": 0.9, "tool_name": "retrieval", "tool_success": true, "payload": {"answer_preview": "Starter answer. You should improve this output logic and add better quality chec..."}, "event": "response_sent", "env": "dev", "model": "claude-sonnet-4-5", "correlation_id": "req-9f875041", "session_id": "k4-l3b-challenge-s04", "feature": "monitoring", "user_id_hash": "c3a24a72d92a", "level": "info", "ts": "2026-09-30T06:44:57.699695Z"}`
  Correlation ID đại diện: `req-9f875041`
- **Trace ID và span gây ảnh hưởng:**
  Trace ID: `41a28d475335b62ffa51943568520659` (khớp correlation_id `req-9f875041`). Mở trace waterfall cho thấy root span `lab-agent-run` mất 2.653s, trong đó span `retrieval` tiêu tốn **2.501s** (chiếm 94.3% tổng latency), trong khi span `generation` chỉ mất 0.151s (151ms).
- **Root cause:** Thành phần RAG Retrieval (`retrieve()`) bị chậm trễ bất thường (latency injection 2.5s) trong quá trình xử lý câu hỏi về chủ đề monitoring, dẫn đến vi phạm SLO P95.
- **Fix action:** Tắt kịch bản incident thông qua lệnh `python scripts/inject_incident.py --disable` để khôi phục tốc độ phản hồi của vector store về mức bình thường (<50ms).
- **Preventive measure:** Áp dụng Client Timeout 1.2s cho bước retrieval kèm cơ chế Fallback sử dụng tài liệu cache cục bộ; bổ sung Circuit Breaker pattern và cấu hình Alert `HighLatencyP95` có runbook xử lý tự động.

> Gợi ý cách viết ngắn, không thay cho evidence thực tế: "Metric cho thấy `[latency/error/cost/quality]` bất thường trong `[khoảng thời gian]`. Log line `[event]` có `correlation_id=[...]` đại diện cho request bị ảnh hưởng. Trace cùng `correlation_id` cho thấy span `[retrieval/generation/prompt/tool]` có dấu hiệu `[chậm/lỗi/token tăng]`. Root cause là `[nguyên nhân suy ra từ evidence]`. Fix action là `[hành động khôi phục]`; preventive measure là `[alert/runbook/test/guardrail để ngăn tái diễn]`."

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:**
  Triển khai cây quan sát 3 tầng (Hierarchical Observation Tree) trong Langfuse: Root (`lab-agent-run`) -> Child Span (`retrieval`) & Child Generation (`generation`). Lý do: Trong hệ thống RAG / LLM Agent, độ trễ tổng thể (end-to-end latency) không thể phản ánh được điểm nghẽn nằm ở khâu tìm kiếm ngữ cảnh (Vector Store RAG) hay khâu suy luận sinh token của LLM. Việc tách riêng span retrieval và generation giúp cô lập chính xác nguyên nhân gốc rễ (bottleneck localization) khi có sự cố hiệu năng.
- **Một lỗi/blocker đã gặp:**
  Khi chạy bộ kiểm thử `pytest tests/test_prompt_management.py`, hàm `load_dotenv(override=True)` đặt bên trong `resolve_prompt` đã vô tình ghi đè các biến môi trường được mock bởi `monkeypatch` (`LANGFUSE_PROMPT_NAME="day13-incident-assistant"`), dẫn đến fail assertion contract.
- **Cách tìm nguyên nhân và xử lý:**
  Phân tích stack trace từ pytest, phát hiện sự sai khác giữa giá trị mong đợi `day13-incident-assistant` và giá trị thực tế `day13-chat` được đọc lại từ file `.env`. Xử lý bằng cách chuyển lệnh `load_dotenv` sang handler endpoint `/chat` trong `app/main.py`, giữ cho module `app/prompt_management.py` thuần túy đọc `os.getenv` để vừa hỗ trợ reload động trên server, vừa tương thích 100% với monkeypatch trong môi trường testing.
- **Cách hiểu luồng Metrics → Logs → Traces:**
  - **Metrics:** Cho biết **"Cái gì đang xảy ra và xảy ra khi nào"** (ví dụ: Panel Latency P95 tăng vọt lên 2,652ms vào lúc 13:44).
  - **Logs:** Cho biết **"Request cụ thể nào bị ảnh hưởng"** (lọc `data/logs.jsonl` tại thời điểm đó, tìm dòng log `response_sent` có `latency_ms=2652` và lấy `correlation_id="req-9f875041"`).
  - **Traces:** Cho biết **"Bước nào bên trong request đó là nguyên nhân gốc rễ"** (tìm trace trên Langfuse theo `correlation_id="req-9f875041"`, mở Waterfall view thấy span `retrieval` mất 2.501s chiếm 94.3% thời gian -> Kết luận Vector Store / RAG bị nghẽn là Root Cause).
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:**
  - *Prompt Version & Rollback:* Giúp kiểm soát rủi ro phát hành (safe deployment); khi prompt v2 làm câu trả lời dài dòng hoặc giảm chất lượng, có thể chuyển label `production` về v1 tức thì trên UI mà không cần sửa code hay redeploy container (zero-downtime rollback).
  - *Token & Cost:* Cho phép theo dõi sát sao ngân sách tài chính và phát hiện sớm các hiện tượng prompt injection hoặc loop vô tận làm bùng nổ chi phí (cost explosion).
  - *SLO & Error Budget:* Thiết lập cam kết chất lượng dịch vụ (ví dụ: 99.5% request nhanh dưới 3s) và là tiêu chuẩn phân xử giữa tốc độ ra tính năng mới với độ ổn định hệ thống.
- **Điều quan trọng nhất đã học:**
  Hiểu sâu sắc tư duy Observability hiện đại cho LLMOps: Không thể vận hành AI agent như phần mềm truyền thống; việc kết hợp chặt chẽ giữa Structured Logging (có correlation ID và PII scrubbing), Distributed Tracing (phân rã span RAG vs LLM) và Symptom-based Alerting là chìa khóa duy nhất để đảm bảo độ tin cậy và an toàn dữ liệu cho hệ thống AI thực chiến.
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:**
  Toàn bộ các yêu cầu kỹ thuật từ CP0 đến CP4 đã hoàn thành 100%. Nếu có thêm thời gian, có thể tích hợp thêm OpenTelemetry Semantic Conventions cho GenAI và mở rộng cơ chế caching ngữ cảnh vector để tự động giảm tải cho bước retrieval.

## 9. Checklist trước khi nộp

- [x] Kết quả và evidence thuộc commit SHA cuối.
- [x] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [x] Incident evidence nối đúng metric → log → trace.
- [x] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [x] Repository chạy lại được theo README.
- [x] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [x] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
