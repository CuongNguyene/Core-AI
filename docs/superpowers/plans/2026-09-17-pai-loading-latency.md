# 2026-09-17 — PAI Loading Latency Plan

## Mục đích

Giảm thời gian load dữ liệu trên UI của PAI backend. Nguyên nhân gốc đã xác định:

- Backend gọi LLM đồng bộ ngay trong request path (conversation, curriculum plan, khởi
  tạo course generation), với Gemini timeout 200s + retry ×2 + repair ×2.
- Không có cache: Redis được cấu hình nhưng chưa được dùng ở bất kỳ đâu.
- List endpoints fetch toàn bộ bảng rồi lọc/slice trong Python (không LIMIT/OFFSET).
- `review_projection` rebuild toàn bộ evidence index mỗi request.
- N+1 query ở extraction-status; `_profile_from_record` re-parse toàn bộ payload.
- Frontend: `staleTime: 0` (refetch mỗi mount), filter/debounce thiếu.

## Phạm vi

- P1 (read-path, thắng lớn nhất, không đổi schema).
- P2 (giảm tải profile/list, thay đổi nhỏ).
- P3 (LLM ra khỏi request path, cần ADR).
- Cache dùng Redis thật theo ADR-0016.

## Nguyên tắc

- Cache entries không phải nguồn dữ liệu chính (non-authoritative), TTL có giới hạn,
  không chứa raw CV/JD/prompt/answer/credential evidence, invalidation trên mutation.
- Redis down → fail-open (bỏ qua cache, vẫn trả dữ liệu DB), log safe operational failure;
  không fallback chạy LLM inline.
- Không đổi contract API; B1 giữ tham số `cursor`/`limit` và `next_cursor` tương thích.
- Mỗi item: pytest + Ruff + mypy strict + `git diff --check`.

## Thứ tự triển khai

### Giai đoạn A — Nền tảng cache Redis

- **A1.** Thêm dependency `redis` + `arq` vào `pyproject.toml`; tạo
  `app/shared/cache.py`: Redis client, `CacheError` đóng gói lỗi kết nối,
  decorator `@cached(ttl=...)` (fail-open), hàm `invalidate(prefix)`.
- **A2.** Wire vào `create_app`: khởi tạo `app.state.cache`, close trong lifespan.
- **A3.** `.env`: thêm `REDIS_CACHE_URL`, `REDIS_PASSWORD`; xác nhận
  `devops/redis/docker-compose.yml` chạy.

### Giai đoạn B — Read-path

- **B1.** Pagination thật cho `GET /candidates`: đẩy ORDER BY/LIMIT/OFFSET xuống
  `list_candidates`; giữ cursor encode/decode ở service.
- **B2.** Cache `review_projection` cho `GET /capability-analyses/{id}`
  (và tạo analysis): key gồm `analysis_id`, `current_target_version`,
  `cv_profile_version`, policy checksum; TTL bounded; invalidate khi analysis mới.
- **B3.** `GET /jd-extraction-profiles`: bỏ rebuild sha256 per-item mỗi GET;
  cache projection theo `(profile_id, version, created_at)` TTL bounded.

  `file:extraction/jd_review_projection.py`

### Giai đoạn C — Đọc profile + list

- **C1.** `_profile_from_record`: ưu tiên đọc thẳng `_candidate_profile` đã lưu khi
  document_kind là CV (bỏ re-parse toàn bộ `normalized_output`); fallback re-parse
  nếu thiếu.
- **C2.** `GET /candidates/{id}/extraction-status`: gom latest job bằng 1 query
  (JOIN/group-by) thay vì 1 query/document.
- **C3.** `GET /course-authoring/requests`: thêm filter/limit trong SQL.
- **C4.** Pool DB: `create_async_engine(..., pool_size, max_overflow)` từ settings.

### Giai đoạn D — LLM ra khỏi request path

- **D1.** ARQ worker nhận job cho `conversation/respond`, `/plan`, `/generate`.
  API trả 202 + job ref; frontend poll `progress` (đã có sẵn).
- **D2.** Reconciliation command re-enqueue theo ADR-0016.
- **D3.** ADR mới ghi nhận background model inference; sau khi background hóa có thể
  hạ `MODEL_TIMEOUT_SECONDS`.

## Docs tạo mới

- `docs/superpowers/plans/2026-09-17-pai-loading-latency.md` (file này).
- `docs/adr/0023-background-model-inference-in-async-request-boundary.md` (ở D3).

## Out of scope

- Ontology/semantic recall optimization.
- Thay đổi chất lượng model hay prompt.
- Frontend refactor (chỉ đề cập, không làm trong plan này).