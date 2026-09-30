# ADR-0002: Ranh giới hạ tầng development và production

## Status

Accepted.

## Context

Scaffold cần một môi trường chạy cục bộ để kiểm thử FastAPI, migration và
readiness. `MEMORY.md` chưa chốt PostgreSQL, Redis và MinIO là lựa chọn
production chính thức; worker và queue provider cũng chưa được chọn.

## Decision

- Docker Compose tiếp tục cung cấp PostgreSQL, Redis và MinIO **chỉ cho local
  development và integration testing**.
- PR-001 dùng PostgreSQL async làm boundary cho database session và Alembic;
  không đưa logic nghiệp vụ, schema miền hay worker provider vào foundation.
- Toàn bộ endpoint và credential hạ tầng đi qua biến môi trường. Giá trị trong
  `.env.example` chỉ là development defaults, không phải secret production.
- Redis, MinIO và queue provider không được khởi tạo hoặc phụ thuộc bởi code
  application ở PR-001.
- Lựa chọn production, HA, backup, retention và queue worker phải có ADR riêng
  trước khi triển khai.

## Alternatives considered

- Chốt PostgreSQL/Redis/MinIO cho production ngay: loại bỏ vì năng lực vận hành,
  SLA và tenancy chưa được quyết định.
- Dùng SQLite cho foundation: loại bỏ vì sẽ làm sai boundary PostgreSQL async và
  khiến migration không phản ánh môi trường integration.
- Khởi tạo Celery/Dramatiq ngay: loại bỏ vì provider queue chưa có quyết định.

## Consequences

- Developer có thể chạy local stack bằng Docker Compose và migration bằng
  Alembic.
- `ready` kiểm tra database thông qua abstraction, nên test không cần database
  thật.
- Triển khai production vẫn bị chặn cho đến khi có ADR về hạ tầng, queue,
  identity, storage/retention và observability.

## Migration

Không có dữ liệu hoặc schema miền cần migrate. PR-001 thêm một baseline Alembic
rỗng (`20260731_01`); khi chạy, nó chỉ quản lý metadata version của Alembic và
chưa tạo bảng nghiệp vụ.
