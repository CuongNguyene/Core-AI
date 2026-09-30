# ADR-0006: Fixture Document Source và Retention Boundary cho Extraction Slice

## Status

Accepted.

For real PDF/DOCX ingestion, the storage and retention boundary in this ADR is
superseded by ADR-0014. Fixture-backed extraction remains supported for tests.

## Context

PR-002 Document & Evidence Core chưa được triển khai. Storage production,
malware scanning, retention và quyền truy cập raw CV/JD chưa có product decision.
PR-004 vẫn cần dữ liệu CV/JD mô phỏng, source locator và golden dataset để kiểm
thử extraction end-to-end.

## Decision

- PR-004 chỉ đọc CV/JD giả lập qua `DocumentSource` internal protocol và fixture
  repository versioned trong source control; không nhận upload hay raw document
  từ public API.
- API create job nhận fixture `document_id` đã biết cùng `document_kind` (`cv`
  hoặc `jd`). Unknown ID bị từ chối.
- Fixture không chứa PII thật. Source locator có `document_id`, section/field và
  character offset hoặc line range để claim truy xuất được.
- PR-004 không ghi original document, prompt hay raw model response vào database,
  log hoặc audit. Chỉ normalized extracted profile/evidence và metadata an toàn
  được persist.
- MinIO trong Docker Compose không được dùng bởi extraction slice. Real document
  upload, object storage, anti-malware, access control và retention cần PR/ADR
  Document Storage riêng trước khi nhận CV/JD thật.

## Alternatives considered

- Lưu raw text CV/JD trực tiếp vào PostgreSQL: loại bỏ vì chưa có retention,
  authorization hoặc encrypted storage policy.
- Dùng MinIO development ngay cho raw upload: loại bỏ vì không giải quyết scan,
  lifecycle và production authorization.
- Bỏ source locator: loại bỏ vì claim không thể review hoặc audit.

## Consequences

- PR-004 là vertical slice có thể test lặp lại nhưng không phải upload feature.
- Fixture IDs là contract tạm thời; PR-002 sẽ cung cấp adapter thay thế mà không
  đổi extraction domain boundary.
- Không có migration raw document. Chỉ extraction job/profile/evidence metadata
  được migrate ở PR-004.

## Migration

Không có dữ liệu cũ. PR-004 thêm fixture registry và schema metadata, không thêm
object storage bucket hoặc raw-document table.
