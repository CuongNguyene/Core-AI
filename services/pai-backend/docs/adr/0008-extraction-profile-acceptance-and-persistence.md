# ADR-0008: Acceptance và Persistence cho Extraction Profile

## Status

Accepted.

## Context

ADR-0007 đã đặt lifecycle review nhưng implementation PR-004 chỉ có repository
in-memory cho test; chưa có transition `ACCEPTED`, optimistic concurrency hay
transaction ghi audit. Preliminary matching không được sử dụng profile chưa
được reviewer xác nhận, nên cần hoàn tất persistence boundary này trước PR-005.

## Decision

- Thêm endpoint development-only `POST /extraction-profiles/{profile_id}/accept`.
  Body bắt buộc có `expected_version`; actor dùng adapter development của
  ADR-0007 và phải có role `reviewer`.
- Chỉ `PENDING_REVIEW` và `CORRECTED` được chuyển sang `ACCEPTED`. Các state
  còn lại fail closed với error contract an toàn. `ACCEPTED` không được sửa tại
  chỗ.
- Acceptance đọc profile theo `id` và `version == expected_version` trong cùng
  transaction. Không có row khớp là stale/superseded request và bị từ chối,
  không retry ngầm.
- Trước khi accept, service xác nhận source document fixture còn resolve được,
  đúng `document_kind` và source eligibility không bị deny. Fixture MVP không
  có quarantine state; adapter tương lai phải trả deny cho source bị quarantine
  hoặc bị retention/access policy chặn. Không xác định được eligibility là lỗi
  fail closed.
- SQLAlchemy repository là runtime adapter cho API/worker. Repository in-memory
  chỉ dùng unit test hoặc test adapter. Acceptance update profile, accepted
  metadata và insert immutable audit event `EXTRACTION_PROFILE_ACCEPTED` trong
  một transaction. Audit insert thất bại làm rollback acceptance.
- Profile lưu extracted payload, optional reviewed payload và effective payload
  được xác định bởi reviewed payload nếu có. Matching chỉ đọc effective payload
  của profile `ACCEPTED`.
- Correction sau acceptance tạo profile revision mới, `CORRECTED`, trỏ
  `supersedes_profile_id` đến accepted profile. Revision mới có version tăng;
  profile cũ và mọi matching đã dùng nó vẫn immutable/truy xuất được.
- Migration thêm `accepted_at`, `accepted_by`, `supersedes_profile_id`, payload
  review/effective metadata cần thiết, ràng buộc unique `(job_id, version)`, và
  index cho `(supersedes_profile_id)` cùng các lookup state/owner. Audit table
  chỉ append; không có update/delete qua repository application.

## Alternatives considered

- Accept chỉ trong memory: loại bỏ vì mất state sau process restart và không
  thể đảm bảo audit cùng transaction.
- Cho `CORRECTED` làm input matching: loại bỏ vì correction chưa là phiên bản
  cuối được người có thẩm quyền xác nhận.
- Sửa `ACCEPTED` tại chỗ: loại bỏ vì phá auditability và khiến match cũ đổi nghĩa.
- So sánh version chỉ ở router: loại bỏ vì worker/CLI/internal caller có thể
  bypass; guard thuộc application service/repository transaction.

## Consequences

- PR-004.1 là blocker-fix trước matching production-safe.
- Development identity vẫn không phải production RBAC; thay Identity Provider
  cần ADR mới nhưng phải giữ semantic role `reviewer`.
- Document source production/quarantine/retention vẫn thuộc Document Storage
  ADR tương lai; adapter hiện tại chỉ cung cấp fixture eligibility an toàn.

## Migration

Backfill profile cũ: `accepted_at`, `accepted_by`, `supersedes_profile_id` là
nullable. Không tự đánh dấu profile cũ là `ACCEPTED`; chúng giữ state hiện có và
phải qua transition có audit nếu cần được dùng để matching.
