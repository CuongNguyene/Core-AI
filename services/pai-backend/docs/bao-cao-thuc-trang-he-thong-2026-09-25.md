# Báo cáo thực trạng hệ thống PAI Platform

**Thời điểm đánh giá:** 25/09/2026  
**Phạm vi đánh giá:** rà soát mã nguồn, cấu hình và tài liệu trong repository. Báo cáo không xác nhận trạng thái triển khai, dữ liệu hay khả dụng của môi trường production.

## Tóm tắt điều hành

PAI Platform đã vượt qua giai đoạn skeleton và có backend FastAPI theo kiến trúc
modular monolith. Luồng MVP cốt lõi cho CV/JD đã hiện diện: tiếp nhận tài liệu,
trích xuất bằng chứng, human review, matching sơ bộ và capability analysis ở
chế độ `PREVIEW`. Hệ thống cũng có các mô-đun assessment, competency, learning,
credential, tích hợp LMS và course authoring/generation.

Ranh giới quyết định năng lực được thiết kế thận trọng: AI chỉ trích xuất/chuẩn
hóa; matching chỉ tạo giả thuyết; chỉ assessment và SME có thẩm quyền mới được
chuyển năng lực sang `ASSESSED` hoặc `VERIFIED`. Capability analysis không tự
tạo quyết định chính thức, learning path hay credential.

Chất lượng mã nguồn hiện **chưa đạt Definition of Done**: Ruff báo 12 lỗi và
mypy báo 6 lỗi. Bộ `pytest -q` chưa cho kết quả cuối trong lần rà soát này và đã
được dừng sau khi không có tiến trình thêm khoảng 90 giây.

## Căn cứ rà soát

- `MEMORY.md`, `docs/product/mvp-scope.md`, `docs/architecture/system-context.md`
  và `docs/domain/three-layer-assessment.md`.
- Tài liệu an toàn: `docs/security/privacy-gateway.md` và
  `docs/security/authorization.md`.
- ADR-0001 đến ADR-0025, đặc biệt ADR-0019, ADR-0020, ADR-0023, ADR-0024 và
  ADR-0025.
- Cấu hình `backend/pyproject.toml`, migration Alembic, router FastAPI, mã nguồn
  trong `backend/app/` và test trong `backend/tests/`.

## Kiến trúc và phạm vi hiện có

| Hạng mục | Thực trạng |
| --- | --- |
| Backend | FastAPI, Python 3.13+, Pydantic v2, SQLAlchemy async và Alembic. |
| Kiến trúc | Modular monolith; các mô-đun nghiệp vụ tách theo package nhưng chưa tách microservice. |
| Dữ liệu | PostgreSQL là persistence nghiệp vụ; Alembic có một head hiện tại: `20260925_49`. |
| Xử lý bất đồng bộ | Có Redis/ARQ và durable dispatch cho course generation; queue chỉ mang ID opaque, lifecycle authoritative nằm trong PostgreSQL. |
| Lưu tài liệu | MinIO/S3-compatible storage; PDF/DOCX qua format gate; production yêu cầu ClamAV fail-closed. |
| AI và riêng tư | Business module đi qua `ModelGateway`; `PrivacyGateway` áp dụng phân loại, tối thiểu hóa và route. Dữ liệu `RESTRICTED` chỉ xử lý local; external AI mặc định tắt. |
| Frontend | Chỉ là placeholder, chưa có framework/runtime trong repository. |
| DevOps | Có Compose local/integration, CI và runbook. PostgreSQL 18 dùng volume mới; Compose tách service đang ở giai đoạn migration/template adoption. |

## Năng lực nghiệp vụ đã có trong mã nguồn

- Quản lý document, upload, metadata và kiểm soát an toàn tài liệu.
- Extraction CV/JD, worker, structured output, evidence graph và lifecycle review/accept/reject.
- JD quality gate, role registry và role-profile authoring/lineage.
- Preliminary matching theo criterion, allocation evidence và human review.
- Semantic policy registry; policy và domain pack có version/checksum, lifecycle
  `DRAFT → ACTIVE → DEPRECATED`, resolve exact theo từng current/future target.
- Capability-gap portfolio ở chế độ `PREVIEW`, giữ provenance snapshot riêng cho
  từng target và fail-closed khi policy/pack không hợp lệ.
- Assessment template/submission/scoring, competency decision và scoped
  delegation cho xác minh.
- Learning path, credential workflow, candidate domain và các API tích hợp.
- Course authoring/generation, curriculum planning và instructional-design
  research artifacts. Các phần này không làm thay đổi ranh giới ba tầng.

Repository hiện có 216 tệp kiểm thử tên `test_*.py`; đây là chỉ dấu về độ phủ
theo module, không phải xác nhận toàn bộ test đang xanh.

## Kiểm soát nghiệp vụ, bảo mật và audit

1. Raw CV/JD và tài liệu tải lên được xem là không đáng tin cậy. Nội dung không
   được coi là system instruction.
2. Không log raw document, prompt, token, API key hay access token. API lỗi có
   correlation ID và không echo dữ liệu validation nhạy cảm.
3. Role/organization được resolve từ trusted persistence; không tin context do
   client tự truyền. `ADMIN` không mặc định được xác minh năng lực.
4. `VERIFIED` yêu cầu SME, scoped delegation đúng tổ chức/phạm vi/thời hạn và
   decision history/audit immutable trong cùng transaction.
5. Semantic pack chỉ cung cấp normalization/hints; semantic core vẫn sở hữu
   eligibility, assessment, gap và readiness. Không có latest lookup, tự đoán
   domain hoặc fallback `it_ai@1`.
6. Integration actor context ký số dùng nonce lưu bền trong PostgreSQL để chặn
   replay; document malware scan production fail-closed khi ClamAV lỗi hoặc phát
   hiện malware.

## Kết quả kiểm tra tại thời điểm báo cáo

| Kiểm tra | Kết quả | Chi tiết |
| --- | --- | --- |
| `alembic heads` | Đạt | Một migration head: `20260925_49`. Điều này không xác nhận database runtime đã được migrate. |
| `ruff check .` | Chưa đạt | 12 lỗi có thể tự sửa: 11 lỗi sắp xếp import (`I001`) và 1 import không dùng (`F401`). |
| `ruff format --check .` | Chưa chạy | Chuỗi kiểm tra dừng sau lỗi Ruff. |
| `mypy app` | Chưa đạt | 6 lỗi: 5 nullable `StreamWriter` trong `app/documents/safety.py` và 1 kiểu `WorkerSettings` trong `app/course_generation/runner.py`. |
| `pytest -q` | Chưa có kết quả cuối | Chạy được 15 test đầu, sau đó không có output/progress thêm trong khoảng 90 giây; phiên kiểm tra được dừng chủ động, exit code 130. |

## Rủi ro và điểm cần theo dõi

- Không thể kết luận regression suite xanh cho revision hiện tại cho đến khi xác
  định nguyên nhân test dừng/chậm và chạy hoàn tất.
- Lint/type-check đang chặn Definition of Done của bất kỳ thay đổi mã nguồn nào.
- README có mô tả queue là “Redis + Celery/Dramatiq, lựa chọn sau ADR”, trong
  khi ADR-0016/0025 và dependency hiện tại đã dùng Redis/ARQ. Đây là sai lệch
  tài liệu cần được quyết định/cập nhật riêng, không nên suy diễn kiến trúc từ
  README cũ.
- Runtime topology của tích hợp LMS được ghi là scan-only; chưa nên coi monorepo
  target topology hoặc reverse-proxy route là đã triển khai.
- Frontend chưa có implementation; mọi bổ sung UI cần spec/ADR được phê duyệt.
- Production readiness còn phụ thuộc cấu hình hạ tầng thực tế: PostgreSQL,
  Redis, MinIO, ClamAV, secret injection, backup/retention và migration
  forward-only. Các yếu tố này không được xác minh bằng rà soát repository.

## Kết luận

Nền tảng có nền móng nghiệp vụ và governance tương đối đầy đủ cho MVP dựa trên
bằng chứng, với các guardrail rõ ràng cho AI, dữ liệu cá nhân và quyết định năng
lực. Tuy nhiên, trạng thái hiện tại nên được xem là **đang phát triển và cần
khắc phục chất lượng mã nguồn trước khi xác nhận sẵn sàng triển khai**. Báo cáo
không khuyến nghị mở rộng phạm vi MVP, mở `OFFICIAL` capability decision, hay
tự động hóa `VERIFIED`/credential từ luồng `PREVIEW`.
