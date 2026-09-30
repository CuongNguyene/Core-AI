# PAI Platform

Nền tảng AI đào tạo và phát triển năng lực cá nhân hóa dựa trên bằng chứng.

## Trạng thái hiện tại

MVP đã có vertical slice extraction → review → capability analysis PREVIEW.
Nền tảng semantic hiện đi qua core trung lập theo domain và policy được version
hóa; chưa mở OFFICIAL/VERIFIED tự động. Phạm vi đang được khóa:

1. Nhập và xử lý CV/JD.
2. Trích xuất bằng chứng có cấu trúc.
3. Đối chiếu CV–JD và tạo giả thuyết năng lực.
4. Đánh giá chẩn đoán để xác minh năng lực.
5. Tạo khoảng cách năng lực và lộ trình phát triển.
6. Tạo khóa học, bài học, học liệu và bài đánh giá.
7. Cập nhật hồ sơ năng lực và cấp chứng nhận theo chính sách.

Luồng capability hiện tại:

```text
Accepted CandidateProfile
→ semantic-preserving EvidenceIndex
→ domain-neutral semantic core
→ exact SemanticPolicy + DomainKnowledgePack
→ target-specific assessment
→ PREVIEW portfolio snapshot
```

`45` current-role gaps trên fixture hiện tại là evidence gaps
(`NOT_FOUND_IN_EVIDENCE`/`INSUFFICIENT`/`CONTEXT_MISMATCH`), không phải xác nhận ứng viên thiếu năng lực. PREVIEW không tạo final competency decision và không chuyển capability sang `VERIFIED`.

## Kiến trúc định hướng

- Backend: FastAPI.
- Kiểu kiến trúc: modular monolith, worker riêng.
- Cơ sở dữ liệu: PostgreSQL.
- Hàng đợi: Redis + Celery/Dramatiq, lựa chọn sau ADR.
- Lưu trữ tài liệu: S3-compatible object storage.
- AI nội bộ: vLLM.
- API ngoài: chỉ qua Model Gateway và Privacy Gateway.
- Giao diện: thiết kế đã có, định hướng trải nghiệm Coursera kết hợp progress bar kiểu Udemy.
- Mô hình đánh giá: ba tầng dựa trên bằng chứng.

## Nền tảng PR-001

- `/health/live` xác nhận process đang phục vụ; không gọi database.
- `/health/ready` kiểm tra kết nối PostgreSQL; khi chưa sẵn sàng trả HTTP 503
  với error contract an toàn.
- Mỗi response có `X-Request-ID`. Có thể gửi UUID hợp lệ trong header này để
  liên kết request với log/audit sau này.
- Lỗi trả về `error.code`, `error.message` và `error.correlation_id`; validation
  không echo input nhận được.
- Logging là JSON và redacts các field có tên nhạy cảm. Không log CV/JD, prompt,
  token hoặc secret.
- PostgreSQL, Redis và MinIO trong Docker Compose là local development services,
  không phải quyết định production. Xem ADR-0002 và ADR-0003.

## Model và Privacy Gateway

- Chỉ `LocalVLLMProvider` gọi HTTP OpenAI-compatible của vLLM nội bộ. Domain
  module phải gọi `ModelGateway`, không gọi provider trực tiếp.
- `RESTRICTED` luôn route local. External AI mặc định tắt; chưa có external
  provider được hỗ trợ, kể cả khi bật `EXTERNAL_AI_ENABLED`.
- Structured output cần một Pydantic schema nội bộ được đăng ký theo ID/version.
  Client không được gửi JSON Schema. Raw prompt, payload và model response không
  được log hoặc nằm trong audit metadata.
- `VLLM_TIMEOUT_SECONDS`, `VLLM_MAX_RETRIES` và
  `STRUCTURED_OUTPUT_REPAIR_RETRIES` kiểm soát retry. Privacy failure không
  retry hoặc fallback.
- Xem ADR-0004 để biết policy đầy đủ; `MockProvider` chỉ phục vụ test.

PR-007 bổ sung learning path và course blueprint metadata từ verified competency,
target profile ACTIVE và preliminary gap đã human-review. Slice này không nhận
raw CV/JD, không sinh nội dung chưa duyệt, không cập nhật competency khi học
xong và không phát hành credential.

PR-008 bổ sung credential policy và workflow evaluate → approval → issue →
expire/revoke → public verify. Completion và learning-achievement credential
chỉ dùng authoritative assertion provider; khi provider chưa có, kết quả là
`NOT_EVALUABLE`. Competency credential yêu cầu competency `VERIFIED`, evidence/rubric reference còn hiệu lực và scoped delegation; course completion không tự cấp competency credential.

## Semantic policy và domain-pack governance (P2)

Role profile mới muốn chạy capability analysis phải bind một
`semantic_policy_ref` cụ thể (`policy_id` + `policy_version`). Resolver chỉ nhận đúng version và kiểm tra
đúng `core_version`, `pack_id`, `pack_version` và checksum. Không có lookup
`latest`, tự đoán domain hoặc fallback ngầm sang `it_ai@1`.

Semantic policy có lifecycle `DRAFT → ACTIVE → DEPRECATED`; version đã phát hành
và domain pack đã bind là immutable. Current role và future role resolve độc lập
và portfolio lưu snapshot provenance riêng cho từng target. Domain pack chỉ cung
cấp normalization/hints; eligibility, assessment, gap và readiness vẫn do
semantic core quyết định.

Migration `20260810_23` tạo registry, audit events và binding nullable cho role
profile. Khi triển khai database mới chạy `uv run alembic upgrade head`; các
profile lịch sử không có policy vẫn đọc được qua compatibility mapping và không được backfill tự động. Migration chưa được apply chỉ có nghĩa database runtime cần chạy bước trên trước khi gọi governance API.

Governance API tối thiểu:

- `POST /semantic-policies` tạo version `DRAFT`;
- `GET /semantic-policies/{policy_id}/versions/{version}` đọc exact version;
- `POST .../activate` và `POST .../deprecate` đổi lifecycle;
- `PUT /role-profiles/{role_profile_id}/semantic-policy` bind exact policy.

Xem [ADR-0019](docs/adr/0019-domain-neutral-capability-semantics.md),
[ADR-0020](docs/adr/0020-semantic-policy-domain-pack-governance.md) và
[P2 plan](docs/superpowers/plans/2026-08-10-semantic-policy-governance.md).

## Chạy thử

### Docker local độc lập (khuyến nghị)

Stack đầy đủ chạy ngay từ repository này, không phụ thuộc BrainHub/LMS cũ:

```bash
cp backend/.env.example backend/.env
cp devops/compose/.env.example devops/compose/.env
docker compose --env-file devops/compose/.env -f devops/compose/docker-compose.local.yml up -d --build
curl http://127.0.0.1:18000/health/ready
```

Xem [hướng dẫn local](docs/local-development.md) để cấu hình placeholder,
truy cập PostgreSQL bằng DBeaver và dừng stack an toàn. Hai file `.env` không
được commit.

### Chạy FastAPI trực tiếp

```bash
cp backend/.env.example backend/.env
docker compose -f devops/compose/docker-compose.yml up -d postgres redis minio
cd backend
uv sync --all-extras --locked
uv run pre-commit install
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

## Kiểm thử

```bash
cd backend
uv run ruff check .
uv run ruff format --check .
uv run mypy app
uv run pytest
```

Harness integration CV thật (dùng target seed, không phải raw CV–JD E2E):
[`docs/testing/real-cv-capability-integration.md`](docs/testing/real-cv-capability-integration.md)

Authoring role profile từ JD extraction:
[`docs/testing/jd-role-profile-authoring.md`](docs/testing/jd-role-profile-authoring.md)

Full raw CV–JD capability E2E:
[`docs/testing/cv-jd-capability-e2e.md`](docs/testing/cv-jd-capability-e2e.md)

Tài liệu kỹ thuật extraction CV/JD từ upload đến review/authoring:
[`docs/architecture/cv-jd-extraction-end-to-end.md`](docs/architecture/cv-jd-extraction-end-to-end.md)

Semantic policy governance tests:
`backend/tests/test_semantic_policy_governance.py`,
`backend/tests/test_semantic_policy_api.py` và
`backend/tests/test_semantic_policy_cross_domain_e2e.py`.

## Cấu trúc repository

- `backend/`: FastAPI modular monolith, Alembic, backend tests và Python tooling.
- `frontend/`: placeholder cho frontend; chưa có framework hay runtime.
- `devops/`: Docker Compose, GitLab pipeline implementation và CI helper scripts.

Root giữ tài liệu governance và các entrypoint CI bị Git host yêu cầu:
`.gitlab-ci.yml` và `.github/workflows/ci.yml`.

## Template delivery migration

PAI Learning đang áp dụng delivery template theo các PR có migration gate, không tạo lại
repository từ đầu. PR-010A thêm các Compose definitions tách theo service tại
`devops/database`, `devops/redis`, `devops/minio`, `devops/backend` và
`devops/nginx`; Compose cũ tại `devops/compose/` vẫn là compatibility stack.

Khởi tạo network trước khi chạy split stack:

```bash
bash devops/scripts/init-network.sh
```

PostgreSQL 18 dùng volume mới. Nếu cần chuyển dữ liệu local/integration từ
PostgreSQL 17, bắt buộc theo
[`devops/database/POSTGRES_17_TO_18.md`](devops/database/POSTGRES_17_TO_18.md)
và giữ volume cũ đến khi restore/test được xác nhận. Không tự động build Docker image; chỉ build khi được yêu cầu rõ.

## Tài liệu bắt buộc đọc

- `AGENTS.md`
- `MEMORY.md`
- `docs/product/mvp-scope.md`
- `docs/architecture/system-context.md`
- `docs/domain/three-layer-assessment.md`
- `docs/security/privacy-gateway.md`
