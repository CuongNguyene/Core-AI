# ADR-0007: Extraction Review Lifecycle và Development API Ownership

## Status

Accepted.

## Context

PR-004 cần API tạo job, xem trạng thái/profile và submit correction, nhưng SSO,
role model, tenancy và production authorization chưa có ADR. CV/JD extraction
chỉ tạo evidence/profile sơ bộ và không được xác minh competency.

## Decision

- PR-004 dùng development-only identity adapter: request phải có
  `X-PAI-Actor-ID`; endpoint review/correction còn phải có
  `X-PAI-Actor-Role: reviewer`. Adapter chỉ hoạt động khi `APP_ENV=development`;
  môi trường khác fail closed cho đến khi có Identity Provider ADR.
- Job và profile lưu `owner_actor_id`. Owner chỉ đọc job/profile của mình;
  reviewer được đọc và submit correction. API không nhận actor ID trong body.
- Review lifecycle: extraction thành công tạo profile `PENDING_REVIEW`.
  Reviewer submit correction tạo version profile mới `CORRECTED`; reviewer có
  thể accept phiên bản không đổi thành `ACCEPTED`. `FAILED` job không có profile.
- Mỗi corrected claim phải giữ source locator và source excerpt/reference từ
  fixture. Claim thiếu source evidence bị reject; thiếu thông tin biểu diễn bằng
  `unknown` hoặc `insufficient`, không tự suy diễn.
- Audit record immutable chứa actor, action, job/profile version, provider,
  model, template version, schema version, policy version và correlation ID.
  Nó không chứa raw CV/JD, prompt hoặc raw output.
- Không có state nào trong PR-004 biểu thị `ASSESSED` hay `VERIFIED` competency.

## Alternatives considered

- Bỏ authorization vì development: loại bỏ vì vi phạm endpoint authorization
  rule và làm khó thay thế identity adapter sau này.
- Dùng client body actor ID: loại bỏ vì client có thể mạo nhận owner/reviewer.
- Sửa profile tại chỗ: loại bỏ vì mất audit trail và evidence versioning.
- Tự động accept output model: loại bỏ vì CV/JD chỉ là untrusted evidence.

## Consequences

- API có ownership boundary kiểm thử được ở development nhưng không được deploy
  production cho đến khi có ADR SSO/tenant/RBAC.
- Human review trở thành mandatory control point trước khi profile được dùng cho
  matching production.
- PR-004 cần migration job/profile/review/audit metadata và test authorization,
  state transitions, source evidence và versioning.

## Migration

PR-004 thêm các bảng extraction và audit metadata mới. Không có user/document
dữ liệu cũ để migrate.
