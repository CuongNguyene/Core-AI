# Roadmap triển khai refactor LMS Core

**Trạng thái:** Phase 1A và 1B đã triển khai, sẵn sàng review kỹ thuật; Phase 1C chưa bắt đầu
**Nguồn backlog:** `LMS_Feature_Tracker_Cuong_Khanh.xlsx` (`LMS-P1-*`, `LMS-P2-*`)
**Baseline nghiệp vụ:** [BRD – Learning Management System Enhancement](./BRD%20%E2%80%93%20Learning%20Management%20System%20Enhancement.md)
**Thiết kế Phase 1:** [PHASE_1_LEARNING_OPERATIONS_TECHNICAL_DESIGN.md](./PHASE_1_LEARNING_OPERATIONS_TECHNICAL_DESIGN.md)

## 1. Mục tiêu và nguyên tắc

Roadmap này chỉ bao gồm **LMS Core / Learning Operations**. `AI-P0-*`, PAI,
Competency, Skill Intelligence, Talent/Performance và HRMS rule tự động không thuộc scope này.

Các nguyên tắc không được phá vỡ:

1. `LMS Learning Assignment` là lớp quản lý **nghĩa vụ học**; không phải một hệ enrollment mới.
2. Tái sử dụng `LMS Enrollment` cho course progress và `LMS Batch Enrollment` cho membership Batch.
   Không xóa hay đổi nghĩa `Cohort*`/`LMS Enrollment` legacy khi chưa có migration riêng.
3. Status, completion, overdue và quyền phải được tính ở backend; frontend chỉ hiển thị.
4. Mọi API mutation phải có permission/ownership check tường minh. Instructor chỉ thao tác
   trên course mình phụ trách; Moderator/System Manager có scope LMS rộng hơn.
5. Không merge nguyên MR !42. Department/Designation rule chỉ được đưa vào sau khi Assignment
   service ổn định và chỉ là nguồn target, không được auto-create enrollment trực tiếp.
6. PDF compliance không dùng screenshot/export từ trang Statistics. XLSX và PDF phải dùng chung
   dataset/filter server-side, tránh lỗi CSS `oklch` của export cũ.

## 2. Tổng quan phase

| Phase | Mục tiêu bàn giao | Tracker liên quan | Điều kiện hoàn tất |
| --- | --- | --- | --- |
| 0 | Chốt baseline, contract và test matrix | Chuẩn bị cho `LMS-P1-*` | **Ready for review** — xem [Phase 0 safety gate](./PHASE_0_LEARNING_OPERATIONS_SAFETY_GATE.md). |
| 1A | Learning Assignment core và enrollment orchestration | `LMS-P1-001` đến `006` | **Ready for Review** — giao/hủy Course hoặc Batch idempotent, không tạo enrollment trùng. Xem [ghi nhận triển khai 1A](./PHASE_1A_LEARNING_ASSIGNMENT_IMPLEMENTATION.md). |
| 1B | Deadline, trạng thái, reminder và My Learning | `LMS-P1-007` đến `010` | **Ready for Review** — learner thấy trạng thái/deadline từ backend; reminder không trùng. Xem [ghi nhận triển khai 1B](./PHASE_1B_MY_LEARNING_IMPLEMENTATION.md). |
| 1C | Batch Sync, Bulk Assignment và Compliance | `LMS-P1-011` đến `016` | Sync có lựa chọn rõ ràng; import/report/export được kiểm thử. |
| 2A | Learner Assessment experience | `LMS-P2-001` đến `003` | Quiz Hub, quiz scope mới và review tự luận chạy end-to-end. |
| 2B | Certificate lifecycle | `LMS-P2-004` đến `006` | Eligibility, auto/bulk issue và revoke có audit/history. |

Phase chỉ chuyển tiếp khi acceptance criteria của phase trước đạt. Không chạy song song phần
mutation của 1A/1B/1C vì chúng cùng chạm enrollment, progress và Batch.

## 3. Phase 0 — Discovery và safety gate

### Mục tiêu

Chốt cách thay đổi mà không phá ba hệ enrollment đang cùng tồn tại.

### Công việc

- Rà `LMS Enrollment`, `LMS Batch Enrollment`, `Cohort*`, progress, lesson completion,
  exercise submission và certificate liên quan.
- Chốt schema `LMS Learning Assignment`, child `LMS Learning Assignment Item` và reminder log.
- Chốt service duy nhất `ensure_learning_enrollment(learner, course, batch=None)`;
  inventory các call site batch hiện tạo enrollment trực tiếp.
- Lập permission matrix cho System Manager, Moderator, Instructor và Learner.
- Lập test matrix: duplicate/retry, owner isolation, late completion, cancel/history,
  Batch sync, import partial failure và export filter parity.
- Xác nhận cách migrate/backfill: **không backfill assignment cho mọi enrollment cũ** nếu chưa
  có business source xác định đó là mandatory assignment.

### Gate review

- Review `docs/data-model.md`, `docs/permissions.md` và technical design trước khi tạo DocType.
- MR !42 vẫn hold; không cherry-pick Skill/HRMS refactor.

## 4. Phase 1A — Learning Assignment core

### Tracker

`LMS-P1-001` Assign Course, `002` Assign Batch, `003` Cancel Assignment,
`004` Duplicate Guard, `005` Reuse Existing Enrollment, `006` Create Missing Enrollment.

### Bàn giao

- DocType `LMS Learning Assignment` và `LMS Learning Assignment Item`, có audit/track changes.
- Service tạo assignment theo Course/Batch, validate learner/target và giữ thông tin
  `assigned_by`, `assigned_on`, `mandatory`, `due_at`, `note`, `source`.
- Duplicate guard cho active `learner + target_type + target`; request retry trả lại kết quả
  idempotent thay vì tạo bản ghi mới.
- `ensure_learning_enrollment` reuse `LMS Enrollment` có sẵn hoặc tạo bằng flow hiện hữu;
  Batch assignment đảm bảo cả `LMS Batch Enrollment` và course enrollment cần thiết.
- Cancel chỉ đổi Assignment/Item và audit reason; không xóa enrollment, progress hay submission.

### Không làm trong phase này

- Reminder, overdue UI, Batch sync choice, bulk import, report/export.
- Rule Department/Designation và auto skill sync từ MR !42.

### Acceptance criteria

1. Giao cùng Course/Batch hai lần cho cùng learner không tạo active Assignment/enrollment trùng.
2. Giao lại learner đã enrolled liên kết đúng enrollment cũ.
3. Hủy assignment vẫn giữ progress và history.
4. Learner không thể tạo/sửa/hủy assignment qua API; Instructor bị chặn nếu course ngoài scope.

### Kết quả triển khai 28/09/2026

- Đã thêm schema, service và API cho Course/Batch assignment; migration đã chạy trên `lms.test`.
- Đã xác minh live: tạo Course assignment, retry cùng idempotency key, cancel giữ nguyên
  `LMS Enrollment`, sau đó tự dọn dữ liệu test.
- `LMS-P1-001` đến `LMS-P1-006` nên chuyển sang **Ready for Review**, chưa phải **Done** cho đến
  khi BA/SA review, UAT role và deploy môi trường mục tiêu hoàn tất.
- Chưa đổi hai hook Batch cũ đang auto-enroll. Việc thay bằng Sync/Không sync có chủ đích thuộc
  Phase 1C, tránh thay đổi behavior production không có màn hình xác nhận.

## 5. Phase 1B — Deadline, reminder và My Learning

### Tracker

`LMS-P1-007` đến `LMS-P1-010`.

### Bàn giao

- Canonical status resolver: `Assigned`, `In Progress`, `Completed`, `Overdue`, `Cancelled`;
  cờ `completed_late` tách khỏi status.
- Daily reconcile job theo timezone hệ thống; status lấy từ progress/completion server-side.
- Reminder D-7/D-3/D-1 với unique log `assignment + reminder_code`; không gửi khi completed/cancelled.
- My Learning API và Vue page/tab: Được giao, Đang học, Quá hạn, Đã hoàn thành, Khám phá.
- Card hiển thị deadline, mandatory, progress, activity gần nhất và Continue Learning.

### Acceptance criteria

1. Qua hạn chưa hoàn thành thành Overdue; hoàn thành muộn thành Completed + completed_late.
2. Chạy job nhiều lần không tạo reminder trùng.
3. Public/discovery course không nằm trong các tab assignment bắt buộc.
4. Learner chỉ đọc dữ liệu của mình; report/status không tin payload frontend.

### Kết quả triển khai 28/09/2026

- Đã thêm resolver backend cho `Assigned`, `In Progress`, `Completed`, `Overdue`, `Cancelled`,
  cùng `completed_late`, progress và last activity derive từ `LMS Enrollment`.
- Đã thêm daily reconciliation và reminder `D-7/D-3/D-1` có reminder log unique; notification
  dẫn về `/lms/my-learning`.
- Đã thêm API My Learning chỉ scope theo session learner và Vue page/tab Được giao, Đang học,
  Quá hạn, Hoàn thành. Khóa public `/courses` vẫn là luồng riêng.
- `LMS-P1-007` đến `LMS-P1-010` nên chuyển sang **Ready for Review**, chưa phải **Done** trước UAT
  role, scheduler và deploy môi trường mục tiêu.

## 6. Phase 1C — Batch, bulk và compliance

### Tracker

`LMS-P1-011` đến `LMS-P1-016`.

### Bàn giao

- Khi thêm course vào Batch đã có learner: preview tác động và lựa chọn rõ
  **Sync Existing Learners** hoặc **Không sync**. Không còn auto-sync âm thầm.
- Sync gọi Assignment/enrollment service chung; chỉ thêm Assignment Item khi learner có active
  Batch Assignment. Xóa course khỏi Batch chỉ archive item, không xóa history/enrollment.
- Bulk assignment CSV/XLSX: upload, validate, preview, confirm, background job và file kết quả
  theo từng dòng. Một dòng lỗi không rollback toàn file.
- Compliance dataset/API với filter learner, department (optional khi có Employee), course,
  batch, status; trạng thái gồm Completed Late.
- Export XLSX/PDF dùng cùng query/filter server-side.
- Chỉ sau 1A–1C mới tách phần `LMS Course Assignment Rule` phù hợp từ MR !42 sang nguồn tạo
  Assignment; Skill/HRMS vẫn ngoài scope.

### Acceptance criteria

1. Không sync không tạo enrollment/item mới; sync không duplicate enrollment.
2. Import hiển thị chính xác success/failure/duplicate và có thể retry an toàn.
3. Report không lỗi trên site không cài HRMS.
4. XLSX/PDF có cùng số dòng/tổng số với UI dưới cùng filter.

## 7. Phase 2A — Assessment workflow

### Tracker

`LMS-P2-001` Quiz Hub, `002` Chapter/Course Final Quiz, `003` Open-ended Review.

### Bàn giao

- Learner Quiz Hub chỉ liệt kê assessment learner được phép làm; filter theo course, scope và
  trạng thái attempt.
- Assessment scope: Lesson, Chapter Final, Course Final; `Required/Optional`.
- Course completion evaluator kiểm tra lesson + mọi required assessment; không dựa riêng
  `progress == 100`.
- Open-ended workflow: Submit → Pending Review → Trainer Review → Passed/Failed;
  queue, rubric, feedback và notification kết quả.

### Acceptance criteria

1. Learner không thể xem quiz không thuộc enrollment/assignment của mình.
2. Quiz Chapter/Course chỉ mở khi thỏa prerequisite.
3. Pending Review không được tính pass/completion/certificate trước khi trainer quyết định.

## 8. Phase 2B — Certificate lifecycle

### Tracker

`LMS-P2-004` đến `LMS-P2-006`.

### Bàn giao

- Backend `evaluate_certificate_eligibility()` kiểm tra course completion, required assessment và
  pending review; là nguồn quyết định duy nhất cho issue.
- Issue idempotent cho một learner/course; auto issue khi có cấu hình và bulk preview phân loại
  Eligible / Already Issued / Incomplete / Pending Review.
- Revoke giữ certificate history, `revoked_by`, `revoked_on`, reason; public verification hiển thị
  trạng thái Revoked.
- Certificate lưu final score khi applicable; report/export certificate theo filter.

### Acceptance criteria

1. Learner không đủ điều kiện không thể tự tạo certificate qua API/UI.
2. Bulk issue không cấp nhầm learner incomplete hoặc pending review.
3. Certificate revoked không còn được xác nhận là valid nhưng lịch sử vẫn truy vết được.

## 9. Trình tự MR, test và release

Mỗi phase nên có các MR nhỏ, reviewable:

1. **Schema/migration** — DocType, indexes/unique constraint, migration không phá legacy data.
2. **Service/API** — permission, idempotency, transaction/retry và backend test.
3. **Frontend** — page/flow dùng API đã ổn định; không để UI tự suy luận status/quyền.
4. **Scheduler/background job** — reminder/import/reconcile, logging và retry.
5. **Report/export/UAT** — test filters, data parity, permission và smoke test PDF/XLSX.

Trước release mỗi phase:

- chạy formatter/linter và Frappe server test có liên quan;
- test manual bằng System Manager, Moderator, Instructor, Learner;
- kiểm tra regression course enrollment, Batch enrollment, lesson completion, exercise submission
  và certificate hiện hữu;
- chạy migration trên bản sao dữ liệu trước production;
- ghi trạng thái, GitLab MR, BA/SA Review và UAT vào tracker Excel.

## 10. Cập nhật tracker

Tracker Excel là nguồn tiến độ delivery. Quy ước cập nhật:

- `Not Started`: chưa có code của deliverable tracker.
- `In Progress`: có MR/branch đang phát triển, chưa qua test/gate.
- `Ready for Review`: code + automated checks đạt, chờ BA/SA review.
- `Done`: UAT đạt và đã deploy/migrate môi trường mục tiêu.
- `Blocked`: ghi nguyên nhân, owner xử lý và dependency cụ thể.

Tại thời điểm tạo roadmap, các dòng `LMS-P1-*` và `LMS-P2-*` vẫn là **Not Started**. Các
enrollment, Batch, notification, quiz và certificate đang có chỉ là baseline để reuse; không được
đánh dấu Done thay cho deliverable mới.
