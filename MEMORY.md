# MEMORY.md — PAI Platform Project Memory

## 1. Mục tiêu sản phẩm

PAI Platform là nền tảng AI đào tạo và phát triển năng lực cá nhân hóa. Sản phẩm không chỉ là LMS mà là hệ thống quản lý vòng đời năng lực:

```text
Role Competency Profile
→ Evidence Profile
→ Preliminary Competency Hypothesis
→ Diagnostic Assessment
→ Verified Competency Profile
→ Skill Gap
→ Development Plan
→ Course/Lesson/Learning Object
→ Formative & Summative Assessment
→ Competency Decision
→ Credential
→ Periodic Reassessment
```

## 2. Quyết định đã thống nhất

- UI/UX đã có thiết kế.
- Định hướng trải nghiệm: Coursera kết hợp thanh tiến độ kiểu Udemy.
- Backend dùng FastAPI.
- Các mô-đun AI cốt lõi do đội dự án phát triển.
- Hạ tầng ưu tiên máy chủ nội bộ.
- Model serving nội bộ dùng vLLM.
- Có thể dùng API mô hình ngoài nếu cân bằng hợp lý:
  - cost;
  - latency;
  - performance/quality;
  - privacy;
  - context length;
  - khả năng xử lý tiếng Việt.
- Không có nguồn dữ liệu chuẩn hóa ban đầu.
- Phải hỗ trợ dữ liệu giả lập, fixture, import và quy trình SME xác thực.
- Mô-đun giai đoạn đầu bổ sung:
  - trích xuất CV;
  - trích xuất JD;
  - đối chiếu CV–JD;
  - hình thành hồ sơ bằng chứng;
  - phân tích khoảng cách sơ bộ;
  - đề xuất assessment.
- Dữ liệu cá nhân mặc định xử lý nội bộ.
- API ngoài chỉ nhận dữ liệu tối thiểu đã được khử định danh và được policy cho phép.
- MCP có thể expose công cụ bảo mật/AI cho agent, nhưng không phải security boundary duy nhất.

## 3. Khung đánh giá ba tầng

### Tầng 1: Thu thập và chuẩn hóa bằng chứng

Input:

- CV;
- JD;
- hồ sơ nhân sự;
- bài làm;
- sản phẩm công việc;
- chứng chỉ;
- đánh giá quản lý/SME.

Output:

- Evidence Profile;
- nguồn trích dẫn;
- trạng thái bằng chứng;
- độ tin cậy extraction;
- dữ liệu thiếu/mâu thuẫn.

### Tầng 2: Đối chiếu và hình thành giả thuyết

Input:

- Evidence Profile;
- Role Competency Profile đã được phê duyệt;
- rubric và policy có version.

Output:

- explicit match;
- inferred match;
- partial match;
- insufficient evidence;
- conflicting evidence;
- preliminary skill gap;
- assessment recommendation.

### Tầng 3: Đánh giá và xác minh

Input:

- assessment task;
- rubric;
- bài làm;
- human/SME review;
- work evidence.

Output:

- assessed/verified competency level;
- competency decision;
- evidence strength;
- validity period;
- reassessment requirement.

## 4. Nguyên tắc nghiệp vụ cốt lõi

- CV ghi một kỹ năng không đồng nghĩa năng lực đã được xác minh.
- `Unknown` khác `Level 0`.
- Không có bằng chứng khác với không có năng lực.
- Điểm phù hợp vị trí khác điểm năng lực.
- Độ tin cậy là cổng quyết định, không phải điểm thưởng.
- Một bằng chứng không được tính đầy đủ lặp lại ở nhiều tiêu chí.
- Role Competency Profile phải được SME/HR phê duyệt trước matching production.
- JD thô phải qua JD Quality Gate.
- Mỗi kỹ năng cần:
  - cấp độ;
  - hành vi quan sát được;
  - nguồn bằng chứng hợp lệ;
  - assessment method;
  - rubric.
- Course completion không tự động tăng cấp năng lực.
- Chứng nhận năng lực chỉ cấp khi assessment và competency decision đạt chính sách.

## 5. Phạm vi MVP khuyến nghị

### MVP-A: Evidence & Matching

- Upload CV/JD.
- Parse và lưu tài liệu.
- PII classification.
- CV extraction.
- JD extraction.
- Role requirement normalization.
- Evidence profile.
- Preliminary match.
- Human review/correction.
- Audit.

### MVP-B: Assessment & Competency

- Assessment template.
- Practical/quiz/case assessment.
- Rubric scoring.
- SME review.
- Competency decision.
- Verified competency profile.

### MVP-C: Learning & Development

- Skill gap.
- Learning path.
- Course blueprint.
- Lesson và learning object.
- Formative/summative assessment.
- Progress tracking.
- Credential policy.

## 6. Những nội dung chưa chốt

Các mục sau phải được xác nhận qua ADR/product decision:

- Product Owner nghiệp vụ.
- Đội ngũ và vai trò cụ thể.
- Quy mô người dùng và SLA.
- PostgreSQL/Redis/MinIO có phải lựa chọn production chính thức không.
- Celery hay Dramatiq/Arq.
- SSO/Identity Provider.
- Multi-tenant hay single-tenant.
- Danh sách model nội bộ.
- Nhà cung cấp API ngoài được phép.
- Chính sách retention CV/hồ sơ.
- Chính sách cấp, hết hạn và thu hồi chứng nhận.
- Bộ Role Competency Profile đầu tiên.
- Rubric và golden dataset đầu tiên.
- GPU/VRAM và concurrency mục tiêu.
- Có dùng dữ liệu người dùng cho fine-tuning hay không.
- Cơ chế phê duyệt SME.

## 9. Authorization MVP (PR-006)

- Internal actor identity dùng UUID; development header chỉ là authentication
  adapter và không mang role/organization authority.
- Minimal subject persistence gồm User, Organization, Membership và Role
  Assignment; mỗi development user có đúng một active organization membership.
- Basic roles là ADMIN, SME, REVIEWER, LEARNER. ADMIN không mặc định có quyền
  chuyên môn hoặc verify.
- `competency.verify` cần SME có scoped delegation active, đúng organization,
  competency scope và thời hạn. Không dùng role ghép `admin+sme`.

## 10. Repository layout

- `backend/` owns the Python modular monolith, Alembic migrations, tests,
  `pyproject.toml`, `uv.lock` and backend environment example.
- `frontend/` is a tracked placeholder only; no frontend framework is chosen.
- `devops/` owns local Compose, GitLab pipeline implementation and CI helper
  scripts.
- Root keeps governance documentation and host-mandated CI entrypoints:
  `.gitlab-ci.yml` and `.github/workflows/ci.yml`.

Không tự quyết định các mục này trong code nếu chưa có ADR.

## 7. Ưu tiên kỹ thuật đầu tiên

1. Repository + CI.
2. FastAPI skeleton.
3. PostgreSQL + migration.
4. Document upload metadata.
5. Worker abstraction.
6. ModelGateway interface.
7. Local vLLM provider.
8. PrivacyGateway interface.
9. Evidence schema.
10. CV/JD extraction contracts.
11. Audit events.
12. Golden dataset harness.

## 8. Anti-goals

- Không xây 10 microservice ngay.
- Không xây toàn bộ LMS trước Evidence/Competency core.
- Không cho LLM tự quyết định điểm cuối mà không có rule/rubric.
- Không cấp credential dựa trên completion đơn thuần.
- Không dùng prompt làm hàng rào authorization.
- Không gửi raw CV ra API ngoài mặc định.

## 11. Semantic policy và domain-pack governance (P2, 2026-08-10)

- Capability matching dùng semantic core trung lập theo domain; domain pack chỉ
  cung cấp normalization và evidence hints, không được quyết định eligibility,
  assessment status, gap, readiness hoặc `VERIFIED`.
- Role profile mới muốn chạy capability analysis phải bind
  `semantic_policy_ref` exact gồm `policy_id` và `policy_version`. Không có
  latest lookup, automatic domain detection hoặc implicit `it_ai@1` fallback.
- `SemanticPolicy` lifecycle là `DRAFT → ACTIVE → DEPRECATED`; policy version,
  pack binding và checksum đã phát hành là immutable.
- Current/future role resolve độc lập. Portfolio lưu snapshot immutable gồm
  policy, core version, pack refs/checksum và target provenance cho từng track.
- Profile lịch sử thiếu semantic policy vẫn readable qua compatibility mapping,
  không backfill tự động. Thiếu policy/pack exact thì analysis fail closed.
- Migration `20260810_23` thêm policy registry, lifecycle audit và role binding;
  cần `uv run alembic upgrade head` trước khi dùng governance API ở database mới.
- P2 chỉ củng cố governance và PREVIEW safety; chưa mở OFFICIAL tự động,
  `VERIFIED`, final competency decision, learning path hoặc ontology expansion.
