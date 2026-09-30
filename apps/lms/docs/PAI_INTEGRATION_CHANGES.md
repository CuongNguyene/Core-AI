# Thay đổi tích hợp PAI và Frappe LMS

Ngày cập nhật: 24/09/2026
Phạm vi: bản sao PAI trong WSL, custom Frappe app `pai_frappe` và frontend LMS.
Không thay đổi: `C:\Projects\BrainHub\ct_brain_hub`.

## 1. Kiến trúc hiện tại

```text
Vue LMS (/lms/pai-studio)
        -> Frappe API (pai_frappe)
        -> HTTP signed actor context
PAI FastAPI (~/workspace/pai-backend)
        -> PAI database / AI model / PAI worker
```

`pai_frappe` không chứa hoặc chạy source FastAPI. App này là lớp bridge: kiểm tra
quyền LMS, lưu audit record tại LMS, ký actor context rồi mới gọi PAI.

## 2. Thay đổi tại `~/frappe-bench/apps/lms`

| File | Thay đổi |
| --- | --- |
| `frontend/src/pages/PAIStudio.vue` | Trang AI Course Studio mới tại `/lms/pai-studio`. Nhập course brief có cấu trúc và hiển thị các bước: tạo request, kiểm tra/xác nhận brief, tạo plan, review/xác nhận plan, generate draft. Không tự publish course. Moderator/System Manager có thể chọn Instructor nhận bản nháp khi import; Instructor thường chỉ import về tài khoản tạo request. |
| `frontend/src/router.js` | Thêm route `PAIStudio` tại `/pai-studio`. |
| `frontend/src/utils/index.js` | Thêm mục sidebar `PAI Studio`. |
| `frontend/src/components/AppSidebar.vue` | Chỉ hiển thị PAI Studio cho System Manager, Moderator hoặc Instructor. |
| `frontend/src/components/MobileLayout.vue` | Áp dụng cùng điều kiện ẩn/hiện trên giao diện mobile. |
| `lms/public/frontend/` và `lms/www/lms.html` | Được sinh lại bởi `yarn build`; không chỉnh trực tiếp. |

## 3. Thay đổi tại `~/frappe-bench/apps/pai_frappe`

### 3.1 Cấu trúc custom app

| Thành phần | Mục đích |
| --- | --- |
| `pai_frappe/api.py` | Các API Vue gọi. Có guard role, ownership check, validation request và proxy các bước course-authoring sang PAI. |
| `pai_frappe/client.py` | HTTP client server-to-server. Đọc secret qua Frappe Password field, tạo Ed25519 signed actor context và không đưa secret xuống browser. |
| `pai_frappe/pai_backend/doctype/pai_settings/` | Singleton `PAI Settings`: enable flag, service URL, timeout, organization UUID, signing key ID, PAI API key và private key. Secret dùng kiểu `Password`; không cho bật khi URL, UUID, timeout hoặc private key Ed25519 không hợp lệ. |
| `pai_frappe/pai_backend/doctype/pai_user_identity/` | `PAI User Identity`: map một `User` LMS với PAI actor UUID; chỉ System Manager quản lý. |
| `pai_frappe/pai_backend/doctype/pai_request/` | `PAI Request`: audit record cục bộ cho request course authoring, trạng thái, PAI request ID và payload. Instructor chỉ xem request sở hữu; record chỉ đọc ở Desk và API bridge mới được tạo/cập nhật, tránh sửa audit trực tiếp. |
| `pai_frappe/pai_backend/doctype/pai_course_import/` | `PAI Course Import`: provenance bất biến theo `result_ref`, version/checksum, người import và LMS Course được tạo. Một PAI result chỉ có thể map tới một LMS Course. |
| `pai_frappe/pai_backend/doctype/pai_evidence_case/` | `PAI Evidence Case`: audit projection cho CV/JD/evidence. Chỉ lưu subject, lifecycle và reference/safe summary; không có File, raw CV/JD, URL object storage hay extracted claims. |
| `pai_frappe/pai_backend/doctype/pai_semantic_policy/`, `pai_role_profile/`, `pai_capability_analysis/` | Projection an toàn cho governance role/policy và capability gap; version được pin, không lưu raw evidence. |
| `pai_frappe/pai_backend/doctype/pai_assessment_review/`, `pai_competency_projection/`, `pai_learning_path/` | Projection lifecycle cho assessment/competency/path. Verified competency không thể được set bằng action local; Learning Path không auto-enroll LMS Program. |
| `pai_frappe/pai_backend/doctype/pai_credential_link/` | `PAI Credential Link`: request/review projection và liên kết đến `LMS Certificate`. Local chỉ tạo request, approve/reject; issue/revoke/expire dành cho signed PAI integration. |
| `pai_frappe/pai_backend/doctype/pai_operational_event/`, `pai_privacy_request/` | Phase 8 audit/operations/privacy projection. Chỉ lưu reference/correlation và safe summary; local không thể đánh dấu privacy action hoàn tất hoặc thất bại. |
| `pai_frappe/materialization.py` | Chuyển structured PAI course draft thành LMS Course/Chapter/Lesson. Validate cấu trúc, loại HTML khỏi lesson body và chỉ tạo course ở trạng thái Draft. |
| `pai_frappe/modules.txt` | Module Desk là `Pai Backend`; phải khớp package `pai_backend`. |

Hardening bổ sung ngày 28/09/2026:

- `pyproject.toml` khai báo tường minh `cryptography` và `requests`; deploy mới không còn phụ thuộc dependency gián tiếp của Bench.
- HTTP client đặt `allow_redirects=False`; bridge không chuyển tiếp request đã ký sang URL redirect bất ngờ.
- `PAI User Identity` kiểm tra `PAI Actor UUID` ngay khi lưu cấu hình.
- Có regression test độc lập cho redirect guard và UUID validation.
- Studio readiness kiểm tra đủ URL, organization UUID, signing key ID, API key và private key; chỉ System Manager thấy tên cấu hình còn thiếu, không thấy giá trị secret.
- `check_pai_runtime_health` gọi server-side `PAI /health/ready` không theo redirect, ghi một `PAI Operational Event` redacted và chỉ trả cờ readiness. Check này không cần bật integration, nhưng vẫn cần Service URL và mạng nội bộ tới PAI.

Hardening bổ sung ngày 29/09/2026:

- `PAI Request` không còn lưu nguyên `training_brief`/prompt/author notes tại Frappe. Bản ghi chỉ
  lưu **Safe Request Summary** gồm title, language và các count/cờ metadata; patch
  `redact_pai_request_payloads` thay toàn bộ payload cũ bằng summary redacted khi migrate.
- PAI HTTP bridge fail-closed nếu upstream không trả integration envelope `schema_version: v1` có
  `data`; body lỗi từ upstream không được đưa nguyên trạng đến browser LMS.
- Materialization neutralize các marker plugin LMS như `{{ Embed }}`/`{{ Quiz }}` trong nội dung AI.
  AI draft vẫn là Markdown/text để Instructor review, không thể tự tạo iframe, quiz hay embedded
  block khi import.
- Khi integration được bật, PAI Service URL bắt buộc là `https://`; mỗi bridge/health call có
  `X-Request-ID` và correlation ID cuối cùng được lưu redacted trên `PAI Request` hoặc health event.
- Ngay cả trước khi bật integration, một Service URL đã nhập cũng phải qua validation HTTPS/loopback
  và timeout phải hợp lệ. Điều này giữ health check pre-enable trong đúng boundary cấu hình, thay vì
  cho phép một URL sai hoặc có credentials chỉ vì checkbox Enable chưa bật.
- Ngoại lệ local chỉ dành cho `developer_mode`: System Manager phải bật rõ `Allow Insecure Local
  PAI URL`; khi đó chỉ chấp nhận `http://localhost`, `http://127.0.0.1` hoặc `http://[::1]`.
  Site staging/production và mọi host khác vẫn bắt buộc `https://`.
- Studio có bước **Revise brief**: Instructor thấy các clarification question từ PAI, sửa goal,
  outcomes, prerequisites và time constraints, rồi tạo version brief mới ở PAI. LMS không giữ
  payload revision đó.
- Studio có bước **Review draft**: nội dung course/module/lesson được lấy lại qua endpoint
  ownership-bound trước khi nút Approve draft được mở. Nội dung được render bằng Vue interpolation,
  không dùng `v-html`; import vẫn chỉ tạo LMS Course ở Draft.
- Khi mở lại một authoring request hoặc bấm Refresh, Studio lấy lại curriculum plan đã tồn tại từ
  PAI. Vì vậy Instructor không bị mất bước review/xác nhận plan chỉ vì reload trang.
- Import có guard cạnh tranh theo `PAI Course Import.result_ref`: một result chỉ tạo tối đa một LMS
  Course. Request đồng thời nhận lại course đã import hoặc trạng thái đang import, không tạo cây
  course/chapter/lesson thứ hai.
- Trước materialization, bridge kiểm tra chặt schema generated course: số module/lesson/section,
  title/text, kiểu section, thứ tự dương duy nhất và list steps/success criteria. Draft không hợp lệ
  được đánh dấu `Failed` với mã lỗi redacted; lỗi tạo LMS cũng rollback savepoint và lưu trạng thái
  `Failed` để có thể retry an toàn.
- Sau import thành công, Studio hiển thị link mở trực tiếp LMS Course Draft để Instructor tiếp tục
  biên tập/review. Không có hành động publish hoặc enrollment ngầm.
- Tạo authoring request dùng một browser retry key và local create intent duy nhất. Nếu response bị
  mất sau khi PAI đã tạo request, lần retry gửi đúng cùng `Idempotency-Key` tới PAI và hoàn thiện audit
  record cũ thay vì tạo request AI thứ hai. `PAI Request` chỉ cho phép thiếu remote ID ở trạng thái
  ngắn hạn `Creating`.

### 3.2 API bridge đang có

- `get_pai_studio_status`: trả trạng thái enable/service/identity mà không lộ URL hoặc secret.
- `list_lms_instructors`: chỉ Moderator/System Manager gọi để chọn Instructor nhận LMS draft; endpoint
  trả về các User còn enabled có role Instructor, còn materialization luôn validate lại server-side.
- `create_course_authoring_request`, `list_course_authoring_requests`, `get_course_authoring_request`.
- `list_authoring_brief_revisions`, `clarify_authoring_brief`, `confirm_authoring_brief`.
- `revise_authoring_brief`: tạo version brief mới ở PAI sau khi validate ownership và shape/size;
  không ghi revision text vào DocType LMS.
- `plan_course_authoring_request`, `get_course_authoring_plan`, `review_course_authoring_plan`, `confirm_course_authoring_plan`.
- `generate_course_authoring_request`, `get_course_generation_progress`, `list_course_authoring_results`.
- `get_course_authoring_result`, `approve_course_authoring_result`,
  `mark_course_authoring_result_ready`, `materialize_course_authoring_result`.

UI gọi `get_course_authoring_result` để preview structured draft trước khi chấp nhận; không dùng
result ID độc lập ngoài local `PAI Request` đã kiểm tra ownership.

LMS browser chỉ gọi Frappe. Frappe mới gọi PAI với `Authorization`, `X-PAI-Actor-Context`, key ID, chữ ký Ed25519 và request ID.

## 4. Thay đổi tại `~/workspace/pai-backend`

Đây là bản sao làm việc của PAI FastAPI trong WSL; không phải thư mục BrainHub.

| Khu vực | Thay đổi |
| --- | --- |
| `app/integration/capability_gap_api.py` | Các endpoint integration sử dụng signed actor context thay cho development actor. |
| `app/integration/content_generation_api.py` | Các endpoint tạo/lấy content generation yêu cầu signed actor context. |
| `app/integration/course_authoring_api.py` | Bổ sung kiểm tra actor được phép truy cập request cha trước khi đọc/review/revise/confirm curriculum plan theo `plan_id`. |
| `app/curriculum_planning/revision_service.py` | Thêm hàm đọc plan để API layer xác định request cha trước khi authorize. |
| `tests/test_curriculum_planning_api.py` | Seed authoring request thuộc đúng actor cho test plan API sau khi áp dụng ownership check. |
| `app/integration/nonce_store.py` và migration `20260925_47_actor_context_replay_nonces.py` | Nonce trong signed actor context được consume atomically trong PAI database, do đó replay bị chặn giữa nhiều FastAPI instance thay vì chỉ chặn trong RAM của một process. |
| `app/integration/actor_context.py` | Tách xác minh chữ ký khỏi consume nonce để dependency FastAPI dùng shared store; fallback in-memory chỉ dành cho fixture test không có database. |
| `tests/test_course_authoring_api.py` | Bổ sung regression test: gửi lại cùng signed context bị trả `ACTOR_CONTEXT_REPLAYED` / HTTP 401. |
| `app/documents/safety.py`, `app/documents/api.py`, `app/shared/config.py` | Thêm ClamAV `INSTREAM` scanner fail-closed. Production phải đặt `DOCUMENT_SCANNER=clamav`; PDF/DOCX vẫn qua format gate trước khi gửi scan. |
| `app/course_generation/dispatch.py`, `app/course_generation/runner.py`, `app/course_generation/dispatcher.py` và migrations `20260925_48`/`20260925_49` | Course generation dùng durable dispatch record, atomic database lease và ARQ worker. Mỗi dispatch lưu rõ các lesson được chạy (`PENDING` hoặc `FAILED`) và có được assemble thành course draft hay không, nên retry không chạy nhầm lesson và module smoke không assemble cả khóa. Worker quét lại job queued/lease hết hạn sau gián đoạn. |
| `devops/backend/docker-compose.yml` | Thêm service `course-generation-worker`; queue chỉ chứa opaque plan ID, trạng thái/actor/phạm vi chạy vẫn nằm trong PAI database. |

## 5. Đã kiểm tra

- `bench --site lms.test migrate`: đã chạy lại để đồng bộ module/DocType `pai_frappe`, bao gồm
  `PAI Course Import`.
- Runtime trên `lms.test`: đã xác nhận `pai_frappe` được cài và bốn DocType bridge tồn tại.
  `get_pai_studio_status` được gọi thành công trong site context, trả đúng ba cờ readiness.
  HTTP Guest bị chặn `403` theo thiết kế; endpoint không dùng `allow_guest`.
- `bench build --app pai_frappe`: thành công.
- `yarn build` tại `apps/lms/frontend`: thành công; bundle `PAIStudio-*.js` được tạo và `lms/www/lms.html` được cập nhật.
- Vue SFC compiler và Prettier cho `PAIStudio.vue`: thành công.
- Bridge endpoint `get_pai_studio_status`: hoạt động.
- Regression test PAI bridge: 34/34 đạt, gồm redirect guard, Actor UUID validation, result
  ownership binding, approve, ready-for-materialization, import idempotent, raw-prompt redaction,
  invalid envelope, untrusted upstream error handling, HTTPS guard, request correlation,
  PAI-owned brief revision, pre-enable Service URL/timeout validation, create retry idempotency và
  reject course draft malformed (duplicate/invalid order, section hay list content sai schema).
- Guest gọi Studio status qua HTTP bị chặn `403`; regression test xác nhận Instructor không đọc được local `PAI Request` của author khác.

Frappe test runner trên `lms.test` hiện bị site tắt (`allow_tests = false`), nên chưa bật cấu hình đó chỉ để chạy test.

PAI backend regression đã chạy với Python 3.13 Linux: nhóm Course Studio hiện tại `36 passed`
cho Course Authoring API/hardening, generation API/hardening và durable dispatch. Ruff
check/format đạt trước đó; Alembic xác nhận `20260929_50` là head. Chưa kiểm thử end-to-end với PAI
database/model gateway thật vì PAI Settings hiện vẫn tắt và chưa có cấu hình service/identity.

Ngày 25/09/2026, migration database PAI thực tế đã được nâng từ `20260917_42` lên
`20260925_49`. Trong quá trình đó phát hiện migration legacy `20260916_43` giả định một snapshot
candidate cố định; đã sửa để chuẩn hóa version profile xác định và remediation pointer có tính
idempotent. Container API hiện hành được build ngày 17/09 và chưa có
`course-generation-worker`; cần deploy lại API/worker từ source PAI hiện tại trước E2E. Chi tiết
xem [PAI_PRODUCTION_READINESS.md](PAI_PRODUCTION_READINESS.md#deployment-consistency-gate).

## 6. Trạng thái cấu hình và việc còn lại

Tại thời điểm kiểm tra, endpoint status trả về:

```json
{
  "enabled": false,
  "service_configured": false,
  "identity_configured": false,
  "missing_configuration": [
    "PAI Service URL",
    "PAI Organization UUID",
    "Actor Signing Key ID",
    "PAI Integration API Key",
    "Actor Signing Private Key"
  ]
}
```

Do đó chưa thể chạy end-to-end sang PAI thật. Để chạy được cần System Manager:

1. Chạy PAI FastAPI từ `~/workspace/pai-backend` với database, worker, model gateway và key signing phù hợp.
2. Điền `PAI Settings`: bật integration, service URL, PAI API key, organization UUID, actor signing key ID và private key.
3. Tạo `PAI User Identity` cho từng người tạo course, map User LMS sang actor UUID đã tồn tại ở PAI.
4. Test luồng tại `/lms/pai-studio` bằng một Instructor/Moderator đã được map identity.

Durable job queue, shared nonce store và production scanner đã có implementation và test; việc
còn lại là deploy/configure chúng trên hạ tầng PAI thật. Materialization có kiểm duyệt từ AI draft
sang `LMS Course` đã được triển khai ở bridge: PAI result phải thuộc đúng request cục bộ, đã ở
`READY_FOR_MATERIALIZATION`, và chỉ tạo course/chapter/lesson ở Draft. Hệ thống cố ý không tự
publish, auto-assign, auto-enroll hoặc tạo quiz từ AI draft.

## 7. Vận hành production

Xem [PAI_PRODUCTION_READINESS.md](PAI_PRODUCTION_READINESS.md) trước khi bật
`Enable PAI Integration`. Tài liệu này là checklist cấu hình, kiểm thử kích
hoạt có kiểm soát, xử lý sự cố và ranh giới trách nhiệm giữa Frappe với service
PAI.
