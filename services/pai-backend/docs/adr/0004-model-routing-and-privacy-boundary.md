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

## Amendment — OpenAI for existing Gemini-backed ModelGateway flows (2026-10-08)

The product owner explicitly approved OpenAI external processing for every
existing shared ModelGateway flow that previously used Gemini, including the
restricted CV/JD/document extraction inputs used by those flows. The approved
provider/model for the current migration is OpenAI Responses API with
`gpt-6-luna`.

- The approval supersedes the earlier statement that no external provider is
  approved, but only for existing Gemini-backed ModelGateway consumers. Jev /
  SystemOne and unrelated data flows are not covered by this approval.
- `PrivacyGateway.inspect` remains mandatory and runs before routing/transport.
  Restricted inputs reach OpenAI only when both `EXTERNAL_AI_ENABLED=true` and
  `EXTERNAL_RESTRICTED_DATA_APPROVED=true`; denied/failed inspection and disabled
  routing remain fail-closed.
- Requests use the OpenAI Responses API with strict Structured Outputs for
  registered schemas, followed by the existing application-side Pydantic
  validation. Responses are requested with `store=false`; credentials, prompts,
  CV/JD content, raw documents, and full SDK response objects are not logged.
- The configured OpenAI reasoning model rejects the shared gateway's
  `temperature` parameter at its default reasoning effort. The adapter omits
  that unsupported parameter; it does not approximate it with reasoning effort.
- There is no Gemini, CTPAI, local-model, or Jev fallback when OpenAI fails.
  Runtime provider selection is explicit through `MODEL_PROVIDER=openai` and
  model selection through `MODEL_NAME=gpt-6-luna`.
- The Gemini adapter remains in source for compatibility/regression and
  historical scripts. It is no longer the selected provider in the approved
  local runtime configuration after rollout.

This amendment adds no public route or database migration. Any change in data
categories, provider scope, or retention behavior requires a new approval.
