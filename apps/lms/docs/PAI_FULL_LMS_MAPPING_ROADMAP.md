# Roadmap map toàn bộ PAI sang Frappe LMS

**Trạng thái:** Port/map theo domain trước; signed runtime integration và E2E làm sau từng phase.
**Ngày:** 28/09/2026

## 1. Boundary cố định

PAI vẫn là service riêng tại `~/workspace/pai-backend`; `pai_frappe` là adapter duy nhất
giữa PAI và Frappe LMS. Không chép FastAPI vào `apps/lms`. Chi tiết phần port trước/nối sau theo
từng phase xem [sổ mapping và deferred connections](PAI_BRAINHUB_PORT_AND_DEFERRED_CONNECTIONS.md).

```text
Vue LMS → pai_frappe (role, ownership, audit)
        → signed actor context → PAI integration API
        → PAI database / worker / ModelGateway / PrivacyGateway
```

- Browser chỉ gọi Frappe; không nhận API key hay private signing key.
- PAI sở hữu AI, raw CV/JD, raw evidence, competency decision và worker.
- Frappe LMS sở hữu account LMS, course delivery, enrollment/progress và UI.
- Course completion không tự chuyển competency thành `VERIFIED`.
- PAI draft/path/recommendation không tự publish hoặc auto-enroll learner.
- Generic FastAPI API không được gọi thẳng từ LMS. Domain chưa có signed integration API
  phải bổ sung adapter PAI trước khi tạo API Frappe/UI.

## 2. Ma trận map domain

| Phase | PAI domain | Map Frappe LMS | Endpoint test bắt buộc | Trạng thái |
|---|---|---|---|---|
| 0 | Identity, signed actor context, nonce replay | `PAI Settings`, `PAI User Identity`, `PAI Request`, readiness | Guest 403; role/owner guard; replay; settings thiếu không 500 | Có nền tảng |
| 1 | Course authoring, curriculum planning, generation | PAI Studio, `PAI Course Import`, LMS Course/Chapter/Lesson Draft | create/get/clarify/confirm/plan/review/generate/progress/result/import/retry | Đã code; chờ E2E PAI |
| 2 | Documents, CV/JD extraction, evidence profile/review | `PAI Evidence Case`, restricted reference, Evidence Center UI | upload/ref, extraction status, review, accept/reject | Port hoàn tất; deferred integration |
| 3 | Role registry, role profile, semantic policy/domain pack | `PAI Role Profile`, `PAI Semantic Policy`, Governance UI | role list/get/version/approve; policy bind; fail-closed | Port hoàn tất; deferred integration |
| 4 | Preliminary matching, capability gap/portfolio | `PAI Capability Analysis`, `PAI Gap Snapshot` projection | create/get analysis; current/future target; review; idempotency | Port hoàn tất; deferred integration |
| 5 | Assessment, rubric, decision, delegation, competency | `PAI Assessment` link, LMS assessment adapter, SME queue | template/get/submit/score/assess/request-verify/verify | Port hoàn tất; deferred integration |
| 6 | Learning need, learning path, authoring/content generation | `PAI Learning Path` link ↔ LMS Program, recommendation UI | create/get/review/approve/regenerate/materialize | Port hoàn tất; deferred integration |
| 7 | Credential policy, request, issue, revoke/expire | `PAI Credential Link` ↔ LMS Certificate, verify page | evaluate/request/approve/issue/verify/revoke/expire | Port hoàn tất; deferred integration |
| 8 | Audit, retention, monitoring, recovery | Operational Event/Privacy Request projection | permission matrix, retry, worker recovery, E2E | Port hoàn tất; deferred integration |

## 3. Thiết kế các phase

### Phase 1 — PAI draft → LMS Course có kiểm duyệt

Thêm `PAI Course Import`: `pai_request_id`, `result_ref`, version/checksum, `lms_course`,
status, imported_by/at và safe error. Instructor chọn một PAI result version để import;
Frappe tạo `LMS Course`, Chapter, Lesson ở **Draft**. Instructor chỉnh tay, Moderator publish.

- Import idempotent theo `result_ref`; import lần hai trả lại LMS Course đã tạo.
- Create authoring request idempotent theo browser retry key: LMS ghi local intent `Creating` trước,
  retry dùng cùng key với PAI và chỉ hoàn thiện một `PAI Request` audit record.
- Không overwrite course đã chỉnh tay.
- Không auto-publish, auto-assign hoặc auto-enroll.
- PAI result phải thuộc đúng `PAI Request`, đã `READY_FOR_MATERIALIZATION`, và target phải có
  role Instructor. Moderator/System Manager mới được chọn Instructor khác owner request.
- Đã có bridge/unit test cho ownership binding, approve, ready-for-import và import idempotent.
  E2E còn thiếu do PAI service chưa được cấu hình.

### Phase 2 — Document/Evidence/CV/JD

PAI cần signed integration endpoint cho lifecycle upload/extraction/review. Frappe chỉ giữ case,
reference và redacted projection; raw PDF/DOCX và evidence payload ở object store PAI sau scan.
Test: file gate/scanner failure, learner isolation, reviewer accept/reject, raw data không trả về LMS.

Đã có `PAI Evidence Case` và trang `/lms/pai-evidence` tại Frappe: subject user, loại CV/JD,
lifecycle, PAI references, safe summary/error và audit. Không có trường `File`, URL object storage,
raw text hay extracted claim. Learner/Instructor chỉ thấy case do chính mình tạo;
Moderator/System Manager có scope rộng.

**Điều kiện để mở upload/UI:** PAI hiện chỉ có `/documents` và `/extraction-*` dùng
`DevelopmentActor`; chưa được Frappe gọi. Cần thêm signed integration contract trước (API key +
`get_signed_actor_context`) cho upload metadata, extraction job/status/profile và review
accept/request-revision/reject. Không được proxy sang development route.

### Phase 3–4 — Role, Skill Intelligence, Capability Gap

PAI là source of truth cho Role Competency Profile, Semantic Policy/Domain Pack, preliminary
match và gap snapshot. Frappe cache projection/version an toàn để hiển thị. Không dùng latest
policy ngầm; chỉ reviewed/approved gap mới được làm input Learning Path.

### Phase 5 — Assessment/Competency

LMS Quiz/Assignment có thể delivery, nhưng PAI decision mới là authority cho `ASSESSED`/`VERIFIED`.
`VERIFY` luôn cần scoped delegation PAI; System Manager/Instructor không bypass. Test workflow
gồm rubric, SME queue, conflict-of-interest, return/revoke/reassessment.

### Phase 6 — AI Learning Path

PAI path versioned được materialize thành `LMS Program` sau review/approval. PAI recommendation
không tạo enrollment; assignment vẫn là domain LMS. Input chỉ từ verified competency hoặc approved
gap snapshot, không dùng raw CV/JD.

### Phase 7 — Credential

PAI policy là authority cho eligibility, approval, issue/revoke/expiry. `LMS Certificate` là
artifact PDF/delivery. Frappe gửi assertion completion có provenance sang PAI; không cấp
Competency Credential chỉ vì course đạt 100%.

Đã có `PAI Credential Link` để giữ projection/audit an toàn: người học, loại credential,
policy/version, PAI credential reference, LMS Certificate artifact, validity và lý do trạng thái.
Frappe chỉ cho tạo request và Moderator/System Manager approve/reject. `Issued`, `Revoked` và
`Expired` không thể được tạo bởi action local; chúng phải đến từ signed PAI integration sau này.

### Phase 8 — Audit/Privacy/Operations

Đã có `PAI Operational Event` cho audit/health/retry/DLQ/recovery và `PAI Privacy Request` cho
retention review/deletion. Cả hai chỉ lưu correlation/reference và safe summary; không có raw
payload, evidence, prompt hay secret. Moderator/System Manager quản lý operational projection;
người dùng chỉ tạo/xem privacy request của mình. Completion/failure của privacy action chỉ có
signed PAI integration được ghi, nên Frappe không thể giả lập xóa dữ liệu PAI.

## 4. Chuẩn test endpoint

Mỗi domain phải có đủ bốn tầng test:

1. **PAI contract test:** signed actor, ownership, validation, idempotency, transition.
2. **Frappe bridge unit test:** role LMS, identity mapping, payload, safe error/no secret/PII.
3. **Frappe endpoint test:** Guest 403, role denial, owner isolation, mutation retry.
4. **E2E:** PAI API/worker thật, correlation ID, UI happy/negative path và audit.

Tên bridge API theo `pai_frappe.api.<domain>_<action>`; PAI route nằm dưới
`/api/v1/integration/...`. Không map internal PAI API trực tiếp vào browser.

## 5. Thứ tự thực thi

1. Activation E2E Phase 0 khi có PAI infrastructure.
2. Course Materialization.
3. Documents/Evidence.
4. Role/Semantic governance → Capability Gap.
5. Assessment/Competency.
6. Learning Path → Credential.
7. Audit, retention, monitoring và production E2E.

## 6. Không được phá vỡ

- Không lưu raw CV/JD, evidence, prompt, API key/private key trong Frappe.
- Không bypass authorization PAI bằng permission Frappe.
- Không biến LMS completion thành competency decision/credential.
- Mọi materialization và assignment phải có người review và audit.
