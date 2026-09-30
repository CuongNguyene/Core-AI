# ADR-0005: Database-backed Extraction Job Queue cho MVP

## Status

Accepted.

## Context

CV/JD extraction có thể gọi model và không được chạy trong HTTP request theo
`AGENTS.md`. `MEMORY.md` chưa quyết định Celery, Dramatiq hoặc Arq; ADR-0002
không coi Redis/PostgreSQL là lựa chọn production chính thức.

## Decision

- PR-004 tạo `ExtractionJob` bền vững trong PostgreSQL development stack và web
  API chỉ enqueue/read job; không gọi `ModelGateway` trực tiếp.
- Một worker process của modular monolith claim và xử lý job. Job có lifecycle
  `queued`, `running`, `succeeded`, `failed` và correlation ID.
- Worker polling database là MVP development/integration queue implementation;
  Redis, Celery, Dramatiq và Arq không được thêm ở PR-004.
- Test dùng in-memory/inline job runner deterministic, nhưng production code
  không có FastAPI BackgroundTask hay inline model execution.
- Job failure lưu error category an toàn và retry count; không lưu prompt, raw
  document hoặc raw model output.

## Alternatives considered

- FastAPI BackgroundTask: loại bỏ vì không có process isolation, retry bền vững
  hoặc vận hành worker độc lập.
- Chọn Celery/Dramatiq/Arq ngay: loại bỏ vì queue provider chưa được đánh giá.
- Gọi vLLM trong router: loại bỏ vì vi phạm ModelGateway/worker boundary.

## Consequences

- API có job status ổn định và extraction không chặn request.
- PR-004 phụ thuộc PostgreSQL local/integration theo ADR-0002; production queue
  và scaling phải có ADR mới trước khi triển khai.
- Worker command, claim strategy, idempotency key và migration được test trong
  PR-004.

## Migration

PR-004 thêm bảng job và migration. Không có dữ liệu cũ cần chuyển đổi.
