# ADR-0013: Credential Policy, Eligibility, Approval, Issuance and Verification

## Status

Accepted.

## Context

PAI phân biệt completion, learning achievement và competency. PR-006 có chuỗi
assessment/competency decision đến `VERIFIED`; PR-007 chỉ có learning blueprint
metadata, chưa có learning delivery, progress hay completion/outcome owner.
Không được suy diễn completion từ learning path hoặc achievement từ mọi
assessment result. Credential cần có policy version, nguồn bằng chứng truy xuất
được, review của con người, trạng thái hiệu lực và audit bất biến.

## Decision

- Credential types là `COMPLETION`, `LEARNING_ACHIEVEMENT` và `COMPETENCY`.
  Chúng dùng workflow/persistence/audit chung nhưng có evaluator riêng; không
  dùng một evaluator với nhánh `if credential_type` mở rộng không kiểm soát.
- `CredentialPolicy` immutable theo `(policy_id, version)`, chỉ policy `ACTIVE`
  mới dùng để evaluate. PR-008 đăng ký policy fixture-backed/runtime; không mở
  public API authoring policy hay tạo LMS domain tạm. Sửa policy tạo version mới
  và supersede version cũ.
- `CompletionCredentialEvaluator` chỉ đọc `CourseCompletionAssertion` từ
  provider authoritative đã đăng ký. `LearningAchievementCredentialEvaluator`
  chỉ đọc `LearningOutcomeAssertion` từ provider authoritative đã đăng ký.
  Runtime production của PR-008 dùng unavailable providers và trả
  `NOT_EVALUABLE`; fake providers chỉ tồn tại trong unit/golden test.
- `CompetencyCredentialEvaluator` đọc competency/decision repository thật. Nó
  chỉ trả `ELIGIBLE` khi record cùng subject/organization có trạng thái
  `VERIFIED`, chưa hết hạn, đúng competency/level policy, decision/evidence/rubric
  reference tồn tại và không bị revoked, verifier delegation hợp lệ tại thời
  điểm verify, và duplicate active credential policy không bị cấm.
- Evaluation status là `ELIGIBLE`, `INELIGIBLE`, `NOT_EVALUABLE` hoặc
  `REQUIRES_REVIEW`. Thiếu assertion authoritative không đồng nghĩa learner
  không đạt và phải là `NOT_EVALUABLE`.
- Client chỉ gửi policy ID/version, subject ID và optional source-reference ID.
  Source reference chỉ là lookup key; evaluator phải resolve qua provider đã
  đăng ký, rồi kiểm tra type, subject, organization và policy scope. Client
  không được gửi completion, outcome, competency, rubric hoặc evidence JSON.
- Eligibility `ELIGIBLE` tạo credential request `PENDING_APPROVAL`. Chỉ request
  `APPROVED` mới được issue. Lifecycle là
  `PENDING_APPROVAL → APPROVED | REJECTED`, `APPROVED → ISSUED`, và
  `ISSUED → EXPIRED | REVOKED`. Credential hết hạn theo `valid_until` không còn
  valid ngay cả trước khi sweep ghi transition; sweep/expiry transition append
  audit khi persist state `EXPIRED`.
- Các permission scoped delegation mới là `credential.approve`,
  `credential.issue`, `credential.revoke`. Policy chạy application-layer, yêu
  cầu delegation `ACTIVE`, đúng organization/scope/thời hạn và không cho
  ADMIN/SME bypass. Approver không được là requester; issuer không được là
  requester. Policy version có thể yêu cầu approver và issuer khác nhau; MVP
  mặc định yêu cầu khác nhau cho competency credential.
- Credential snapshot references policy/version, subject/organization, evaluator
  version, competency/assessment/rubric/evidence reference IDs (không raw
  evidence), approval/issuance/revocation actor và delegation IDs, issued/valid
  dates, correlation ID và safe outcome. Audit append-only không chứa raw answer,
  document, prompt, PII hay API key. Mutation và audit nằm trong một database
  transaction; audit insertion failure rollback transition.
- `GET /credentials/{credential_id}/verify` là endpoint verification công khai
  tối thiểu: chỉ trả identifier, credential type, issuer organization, status,
  validity và policy version. Nó không trả evidence, assessment, PII hay audit;
  credential unknown/revoked/expired trả outcome an toàn và không disclose
  subject identity.

## Alternatives considered

- Cấp competency credential thẳng từ course completion: loại vì completion
  không là competency verification.
- Fixture-backed completion/outcome tables trong runtime: loại vì tạo owner LMS
  tạm và làm fixture bị hiểu nhầm là nguồn authoritative production.
- Cho client submit assertion inline: loại vì client có thể tự khai completion
  hoặc achievement.
- Cho ADMIN/SME issue mặc định: loại vì quyền chuyên môn/credential authority
  phải explicit và audit được.
- Một credential boolean không lifecycle: loại vì không hỗ trợ approval,
  expiration, revocation hay verification đáng tin cậy.

## Consequences

- Chỉ competency credential có production-ready authoritative input trong phạm
  vi domain hiện có trước PR-008. Completion và achievement vẫn có contract,
  fake-provider test và fail-closed runtime behavior.
- Full LMS delivery/progress, outcome ownership, policy authoring governance,
  renewal automation, public cryptographic credential/QR và external registry
  là future ADR/PR.
- Authorization delegation contract mở rộng permission enum nhưng giữ một
  persistence/lifecycle/audit implementation của PR-006.

## Migration

PR-008 thêm tables policy version, credential request, credential snapshot và
append-only credential audit. Unique/index gồm `(policy_id, version)`, active
policy lookup, request status/subject/organization lookup và active duplicate
credential prevention theo policy/subject/source scope. Không migrate raw LMS
data, evidence payload hoặc credential cũ.
