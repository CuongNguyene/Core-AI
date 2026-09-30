# ADR-0011: RBAC + Scoped Delegation cho Xác minh Năng lực

## Status

Accepted.

## Context

Tầng 3 phải cho SME tạo assessment decision nhưng không được cho mọi SME hay
ADMIN xác minh năng lực. MVP cần kiểm tra quyền được tái sử dụng bởi API, worker,
CLI và internal caller, có scope tổ chức/chuyên môn/thời hạn, và audit bất biến.

## Decision

- Dùng RBAC + scoped delegation, không triển khai ABAC/OPA/Cedar tổng quát.
- Basic roles: `ADMIN`, `SME`, `REVIEWER`, `LEARNER`. `ADMIN` quản trị role,
  organization và delegation trong scope nhưng không mặc định score, assess hay
  verify. `SME` score/review và mark `ASSESSED`; `REVIEWER` chỉ extraction/
  matching review; `LEARNER` submit/read resource của mình.
- `competency.verify` là permission không gắn mặc định với role nào. Verify chỉ
  allowed khi actor có `SME`, delegation `ACTIVE` đúng organization, competency
  scope và validity window; actor khác subject; state hợp lệ; không conflict of
  interest; và policy separation-of-duties đạt.
- Delegation lifecycle `DRAFT`, `ACTIVE`, `SUSPENDED`, `EXPIRED`, `REVOKED` dùng
  optimistic locking `expected_version`. Transition và append-only audit cùng
  transaction; delegation từng được dùng không hard-delete.
- `CompetencyAuthorizationPolicy` chạy ở application layer. Nó trả safe
  `AuthorizationDecision` gồm allowed, reason code, policy version, matched role,
  delegation ID và scope match; service phải gọi policy, router không đủ.
- Competency lifecycle: `UNKNOWN → DECLARED → ASSESSED →
  PENDING_VERIFICATION → VERIFIED`; `PENDING_VERIFICATION → RETURNED_FOR_REVIEW
  → ASSESSED`; `VERIFIED → REQUIRES_REASSESSMENT → EXPIRED`; `VERIFIED →
  REVOKED`. Completion không transition state.
- Risk policy versioned: `LOW_RISK` cho phép assessor=verifier nếu delegation
  hợp lệ; `HIGH_RISK` bắt buộc khác actor. Verification lưu delegation/policy/
  rubric/evidence references và actor UUID.
- Assessment template/rubric immutable theo version. Scorer interface/mock chỉ
  đề xuất score; AI scorer tương lai đi qua ModelGateway + PrivacyGateway và
  human-review policy. Credential issuance không thuộc PR.

## Alternatives considered

- Role `admin+sme`: loại bỏ vì admin không là authority chuyên môn và audit mơ
  hồ.
- Gắn `competency.verify` mặc định cho SME/ADMIN: loại bỏ vì không có scope/time
  control.
- General ABAC engine: loại bỏ vì vượt MVP và thiếu policy governance.
- LLM quyết định authorization/verification: loại bỏ vì không deterministic và
  không phải security boundary.

## Consequences

- Delegation, decision transition và denial đều có safe immutable audit.
- Verification cũ giữ nguyên khi delegation bị revoke/expired về sau.
- Credential, committee approval, full IAM và multi-org context là future work.

## Migration

Thêm role/delegation, assessment/decision/competency/audit tables và index active
delegation lookup. Không persist raw answer, prompt, token hoặc API key vào audit.
