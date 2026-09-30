# ADR-0004: Local-only Model Routing và Privacy Boundary

## Status

Accepted.

## Context

CV, JD và payload phục vụ suy luận là dữ liệu không đáng tin cậy, có thể chứa
PII và prompt-injection. MVP cần local vLLM nhưng chưa có approved external
provider ADR, danh sách model production hoặc policy retention cho raw content.

## Decision

- Domain module gọi `ModelGateway`, không gọi HTTP provider trực tiếp.
- PR-003 chỉ đăng ký `local-vllm` và test `mock` provider. External provider
  không có client hay route thực thi.
- `RESTRICTED` luôn route local. External bị deny mặc định, và vẫn bị deny ngay
  cả khi feature setting được bật cho đến khi có ADR approved provider.
- `PrivacyGateway` chạy trước routing. Inspection error, deny hoặc yêu cầu human
  approval fail closed và không fallback/retry qua provider khác.
- Structured output dùng schema Pydantic nội bộ đã đăng ký bằng ID/version;
  application validate lại output provider. Client không được truyền JSON
  Schema tuỳ ý.
- Audit chỉ chứa provider/model/template/schema/policy/correlation/latency/token
  usage/routing/outcome. Prompt, payload, raw response, PII values và API key
  không được log hoặc persist bởi PR-003.
- Transport timeout được retry có giới hạn; privacy, routing, registry và output
  validation failures không retry transport. Structured output được tạo lại tối
  đa một lần với error category an toàn.

## Alternatives considered

- Chỉ yêu cầu JSON object: loại bỏ vì không bảo đảm type, required field hoặc
  rule cơ bản của use case.
- Tin provider-side JSON mode: loại bỏ vì provider không là trust boundary.
- Public API nhận JSON Schema: loại bỏ vì mở rộng attack surface và cost surface.
- External fallback khi local lỗi: loại bỏ vì có thể làm lộ dữ liệu.

## Consequences

- PR-004 có thể truyền CV/JD Pydantic schema đáng tin cậy vào internal gateway.
- Semantic validation và review nghiệp vụ vẫn thuộc future CV/JD services.
- External provider chỉ được thêm sau ADR nêu provider, data minimization,
  approval, audit, retention, operational controls và migration path.

## Migration

Không có database migration hoặc public HTTP API. Đây là internal application
boundary trong modular monolith.
