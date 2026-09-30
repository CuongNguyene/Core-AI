# Sổ mapping BrainHub PAI và deferred connections

**Nguồn PAI:** `~/workspace/pai-backend/backend/app`
**Đích port:** `apps/pai_frappe` và `apps/lms`.

## Quy ước thực hiện

Mỗi phase làm theo hai bước: **Port/map** model, permission, lifecycle, UI và audit projection vào
Frappe trước; sau đó mới **nối runtime** qua signed PAI integration API và E2E. Không gọi route
development/internal PAI từ LMS. Raw CV/JD/evidence, prompt và secret không được port vào Frappe.

| Phase | Nguồn BrainHub PAI | Port vào Frappe | Port | Nối runtime |
| --- | --- | --- | --- | --- |
| 0 | `authorization`, `integration` | Settings, User Identity, Request, signed client | Có nền | Chưa cấu hình thật |
| 1 | `course_authoring`, `curriculum_planning`, `course_generation` | Studio, Course Import, LMS Course draft | Có | Chưa E2E |
| 2 | `documents`, `extraction`, `evidence`, `privacy` | Evidence Case raw-data-free, Evidence Center UI | Hoàn tất port | Chưa bắt đầu |
| 3 | `role_registry`, `role_profile_authoring`, `semantic_policy` | Role Profile/Policy projection, Governance UI | Hoàn tất port | Chưa |
| 4 | `candidate`, `matching`, `capability_analysis` | Capability Analysis/Gap Snapshot projection | Hoàn tất port | Chưa |
| 5 | `assessment`, `competency`, `authorization` | Assessment/SME queue/Competency projection | Hoàn tất port | Chưa |
| 6 | `learning_need_profile`, `learning`, `learning_authoring` | Learning Path ↔ LMS Program | Hoàn tất port | Chưa |
| 7 | `credential` | Credential Link ↔ LMS Certificate | Hoàn tất port | Chưa |
| 8 | `audit`, `privacy`, worker recovery | Operational Event và Privacy Request projection | Hoàn tất port | Chưa |

## Danh sách phải nối sau mỗi phase

### Phase 0 — Identity

- Điền service URL, API key, org UUID, signing key trong PAI Settings; map LMS User → PAI actor UUID.
- Deploy PAI API/worker/database ở migration head; cấu hình public signing key ở PAI.
- E2E: guest 403, actor không tồn tại, nonce replay, owner isolation và correlation ID.

### Phase 1 — Course Authoring

- Nối create/read brief, revision, plan/review/confirm, generation/progress/retry, result/approve/ready.
- Bind `PAI Request.pai_request_id` với `course_authoring_request_ref`; result khác owner bị từ chối.
- Materialize chỉ sang LMS draft; không publish, enroll hoặc tạo quiz tự động.
- E2E: idempotency, timeout/retry, worker recovery, trace `result_ref → Course Import → LMS Course`.

### Phase 2 — Document/Evidence/CV/JD

`PAI Evidence Case` chỉ giữ subject, loại CV/JD, lifecycle, PAI reference/profile version và safe
summary/error. Không có File, raw text, extracted claim hay URL object store.

- PAI phải có signed integration endpoints cho upload token/stream, document metadata, start/get/cancel
  extraction, redacted review projection, accept/request-revision/reject.
- PAI scanner/object storage nhận raw file; Frappe không tạo `File` record. Bridge chỉ cập nhật status/reference.
- E2E: file/scanner reject, ownership, reviewer expected-version, retention/delete, raw bytes/text không xuất
  hiện trong response, log hay Frappe database.

### Phase 3 — Role Profile/Semantic Policy

- Nối list/get/version/approve role profile, policy/domain pack binding, policy version pinning và fail-closed.
- E2E: organization isolation; không tự dùng "latest" policy.

### Phase 4 — Capability Gap

- Nối create/get/history/review analysis, approved evidence selection, current/future target, idempotency.
- Chỉ profile/gap đã accepted mới là input cho Learning Path.

### Phase 5 — Assessment/Competency

- Nối template/version, submit/score/assess, request-verify/verify/revoke với scoped delegation.
- LMS Quiz/Assignment là delivery; course completion không tự thành VERIFIED.

### Phase 6 — Learning Path

- Nối create/get/review/approve/regenerate/materialize path version sang LMS Program.
- Assignment, deadline, reminder, enrollment vẫn do LMS quản lý; AI không auto-enroll.

### Phase 7 — Credential

- Đã port `PAI Credential Link`: subject, loại credential, lifecycle request/approved/rejected,
  policy/version, credential reference, LMS Certificate artifact, validity/revoke và audit fields.
  Local API chỉ tạo request và cho Moderator/System Manager approve/reject; không có API cấp,
  revoke hay expire local.
- Nối evaluate/request/approve/issue/revoke/expire/verify.
- LMS gửi completion assertion có provenance; PAI quyết định credential, LMS chỉ delivery PDF.

### Phase 8 — Audit/Privacy/Operations

- Đã port `PAI Operational Event` (audit, health, retry, DLQ, recovery, retention/deletion) và
  `PAI Privacy Request` (retention review/deletion). Schema chỉ có reference và safe summary;
  không có raw evidence, prompt, payload hoặc secret. Local chỉ record/resolve operational event
  và accept/reject privacy request; completion/failure phải do signed PAI integration ghi nhận.
- Nối audit lookup/export, retention/deletion outcome, retry/DLQ/recovery signals và alerting.
- E2E trace LMS → PAI → projection mà không lộ PII.

## Điều kiện đánh dấu hoàn tất

Sau mỗi phase ghi riêng ba trạng thái: **Port**, **Bridge contract**, **E2E**. Một phase không hoàn tất
chỉ vì đã có UI/DocType. Mỗi endpoint nối sau cần PAI contract test, Frappe permission/ownership test
và E2E khi PAI infrastructure sẵn sàng.
