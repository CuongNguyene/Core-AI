# ADR-0009: Preliminary Match Ownership, Evidence Allocation và Audit

## Status

Accepted.

## Context

MVP cần so khớp CV–role để tạo giả thuyết năng lực, skill gap sơ bộ và đề xuất
assessment. CV/JD là untrusted evidence; role profile phải được phê duyệt, và
một evidence không được tính quyết định nhiều lần. Kết quả không được trở thành
quyết định tuyển dụng hoặc competency verification.

## Decision

- Thêm module matching trong modular monolith, dùng rule engine deterministic;
  không gọi LLM, ModelGateway hay provider.
- Input chính thức bắt buộc gồm CV extraction profile `ACCEPTED` và Role
  Competency Profile `ACTIVE`. Role profile có stable ID và immutable version;
  persistence không ghi đè bản cũ, chỉ cho phép một version `ACTIVE` cho mỗi
  stable ID. Role profile truy vết đến JD
  extraction profile `ACCEPTED`; không match với JD payload thô. Các guard nằm
  trong application service và fail closed cho mọi caller.
- Role requirement có criterion dimension, classification (`LEGAL_MANDATORY`,
  `ROLE_CRITICAL`, `TRAINABLE_MANDATORY`, `PREFERRED`, `OPTIONAL`), evidence
  terms, confidence threshold, assessment recommendation và rule/rubric version.
- Evidence identity được canonical từ profile ID, profile version, source
  locator và normalized claim identity. Một identity chỉ được allocated làm
  decisive evidence cho tối đa một requirement, với ưu tiên theo classification:
  legal mandatory, role critical, trainable mandatory, preferred, optional.
  Evidence có thể được tham chiếu giải thích ở criterion khác nhưng không được
  cộng hoặc quyết định lần thứ hai.
- Kết quả có criterion results, không có overall score duy nhất. Mỗi result có
  status `matched`, `partial`, `insufficient` hoặc `conflicting`, evidence,
  confidence, mandatory status, recommended assessment và
  `human_review_required`. Toàn bộ preliminary match mặc định
  `human_review_required=true` và lifecycle `CREATED`, `COMPLETED`, `REVIEWED`,
  `SUPERSEDED`, `FAILED`; `REVIEWED` không là quyết định tuyển dụng.
- API development-only gồm `POST /preliminary-matches` và
  `GET /preliminary-matches/{match_id}`. Owner/reviewer access dùng cùng adapter
  ADR-0007; request không mang raw CV/JD hay actor ID.
- Persistence/audit lưu CV/JD source/role profile ID và version, rule-set,
  policy version, actor/service, correlation ID, outcome safe, criterion result
  và allocation. Không lưu raw CV/JD, prompt, response model hoặc PII trong
  audit. `MATCHING_STARTED` và `MATCHING_COMPLETED` được append trong cùng
  transaction với result; audit failure rollback result. Input bị từ chối ghi
  event append-only không có raw data, gồm `MATCHING_REJECTED_INPUT_NOT_ACCEPTED`
  hoặc `MATCHING_REJECTED_INPUT_INELIGIBLE`.

## Alternatives considered

- Một overall score: loại bỏ vì che giấu mandatory gap, evidence strength và
  conflict; không hỗ trợ human review đúng ngữ cảnh.
- LLM semantic matching: loại bỏ ở MVP vì giảm reproducibility và mở rộng risk
  surface; semantic mapping cần ADR/policy/rubric riêng.
- Preview và official match dùng chung endpoint/response: loại bỏ vì dễ dùng
  nhầm dữ liệu chưa reviewed. Preview chưa thuộc PR-005.
- Auto reject/accept ứng viên: loại bỏ vì vượt tầng 2 và MVP scope.

## Consequences

- PR-005 chỉ chạy sau PR-004.1, và phải persist input versions để rerun/audit.
- Active role profiles fixture-backed trong MVP; workflow SME/HR authoring và
  approval production cần PR/ADR riêng nhưng `ACTIVE` guard vẫn bắt buộc.
- Assessment recommendation là đề xuất assessment, không cập nhật competency
  sang assessed/verified và không tạo credential.

## Migration

PR-005 tạo bảng role competency profile/requirement, preliminary match,
criterion result, evidence allocation và append-only matching audit event.
Migration `20260803_07` thay khóa vật lý role profile bằng record ID, giữ unique
`(stable ID, version)` để các revision tồn tại đồng thời. Không migrate hay sao
chép raw CV/JD.
