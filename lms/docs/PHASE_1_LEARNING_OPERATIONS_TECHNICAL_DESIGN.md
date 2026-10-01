# Phase 1 — Learning Operations: phạm vi, mapping và technical design

**Trạng thái:** Thiết kế Phase 1 đã được dùng để triển khai Phase 1A/1B; Phase 1C vẫn chờ review/UAT
**Ngày:** 25/09/2026
**Baseline nghiệp vụ:** [BRD – Learning Management System Enhancement](./BRD%20%E2%80%93%20Learning%20Management%20System%20Enhancement.md)

## 1. Mục tiêu và ranh giới Phase 1

Phase 1 xây dựng lớp **Learning Operations** để giao và theo dõi nghĩa vụ học tập:

- giao khóa học hoặc Batch cho learner;
- deadline, overdue và nhắc hạn;
- My Learning tách rõ khóa được giao/đang học/hoàn thành/quá hạn;
- đồng bộ Batch có kiểm soát;
- giao hàng loạt CSV/XLSX;
- báo cáo tuân thủ và export.

**Không thuộc Phase 1:** PAI, Competency, Skill Intelligence, Talent/Succession, 9-box, skill gap, career recommendation và PAI Course Generation. Các hạng mục này không được đưa vào model, UI, migration hoặc API của Phase 1.

`LMS Assignment` hiện có là bài tập/assessment trong khóa học. Tên DocType mới phải là **LMS Learning Assignment** để không nhầm với bài tập của learner.

## 2. Mapping BRD với source hiện tại

| BRD | Hiện trạng/source có thể tái sử dụng | Phân loại | Scope xử lý Phase 1 |
|---|---|---|---|
| FR-01 — Learning Assignment | `LMS Enrollment` là bản ghi learner–course và vẫn được luồng lesson/submission sử dụng; `LMS Batch Enrollment` là membership Batch hiện hành. | **Làm mới**, nhưng tái sử dụng enrollment | Thêm `LMS Learning Assignment` là nghĩa vụ học, không phải enrollment. Mọi giao học đều ensure/reuse enrollment hiện hữu. |
| FR-02 — Deadline & Overdue | Enrollment đã có `progress`; chưa có deadline, overdue hay completed-late. | **Làm mới** | Due datetime, trạng thái derive phía server và cờ hoàn thành muộn. |
| FR-03 — Reminder | `LMS Notification` và `make_lms_notification_logs()` đã hỗ trợ inbox/realtime/email; `hooks.py` đã có daily scheduler. | **Tái sử dụng + sửa** | Thêm daily job và log idempotent 7/3/1 ngày, dùng notification hiện có. |
| FR-04 — My Learning | `StudentHome.vue` gọi `get_courses_in_progress`; `LMS Enrollment.progress` là nguồn tiến độ. Chưa phân tách assignment và public discovery. | **Sửa** | API/page riêng theo `LMS Learning Assignment`; giữ khu khám phá public độc lập. |
| FR-05 — Batch Assignment & Batch Sync | `LMSBatchEnrollment.validate_course_enrollment()` tạo `LMS Enrollment` khi thêm learner; `LMSBatch.validate_membership()` tạo enrollment khi thêm course cho Batch đã có learner. | **Sửa** | Chuẩn hóa thành service ensure enrollment; UI/endpoint Batch phải preview và yêu cầu lựa chọn Sync Existing Learners hoặc Không sync, không chạy ngầm. |
| FR-06 — Learning Compliance Report | `get_department_report()` và `get_learning_recognition()` có report phòng ban nhưng phụ thuộc DocType `Employee`; Statistics từng lỗi nếu site không cài HRMS. | **Làm mới**, chỉ tái sử dụng pattern filter/report | Report dựa vào Assignment + Enrollment, không bắt buộc HRMS. Department chỉ là filter tùy chọn khi DocType tồn tại. |
| FR-07 — Bulk CSV/XLSX | Không có import assignment; Excel hiện chủ yếu phục vụ quiz/import-export khác. | **Làm mới** | Upload, validate/preview, xác nhận, background job và file lỗi. |
| FR-08 — Export XLSX/PDF | Statistics có export PDF nhưng không ổn định do CSS `oklch`; chưa có XLSX compliance. | **Sửa + làm mới** | XLSX là output chuẩn Phase 1; PDF dùng template export riêng với CSS an toàn, không dùng snapshot UI Statistics. |

### Phát hiện quan trọng về enrollment

Source hiện tại đã có ba lớp lịch sử: `Cohort*` (legacy), `LMS Batch` + `LMS Batch Enrollment` (Batch hiện hành) và `LMS Enrollment` (course enrollment, vẫn load-bearing cho progress và Exercise Submission). Phase 1 **không tạo hệ enrollment thứ tư** và không xóa/đổi nghĩa của các bản ghi này.

## 3. Technical design đề xuất

### 3.1 Learning Assignment model

Thêm DocType cha **LMS Learning Assignment** và child table **LMS Learning Assignment Item**.

**LMS Learning Assignment** là đơn giao/obligation, có các trường chính:

| Nhóm | Trường |
|---|---|
| Đối tượng | `learner` (User), `target_type` (Course/Batch), `course` hoặc `batch` |
| Quản trị | `assigned_by`, `assigned_on`, `source` (Manual/Bulk/Rule/Batch Sync), `mandatory`, `due_at`, `note` |
| Trạng thái | `status`, `completed_at`, `completed_late`, `cancelled_at`, `cancelled_by`, `cancel_reason`, `last_activity_at` |
| Kiểm soát | `track_changes`, audit event/reminder log liên kết assignment |

**LMS Learning Assignment Item** materialize các course phải học:

- Assignment theo **Course** có đúng một item.
- Assignment theo **Batch** có một item cho mỗi course của Batch tại thời điểm giao.
- Item giữ `course`, `lms_enrollment` (Link, nếu đã có), `progress`, `status`, `completed_at` và `source_batch`.

Thiết kế cha–con giữ đúng target gốc mà BRD yêu cầu: learner có thể nhận một Course trực tiếp và một Batch riêng; báo cáo vẫn drill-down theo từng course. Không cần tạo enrollment mới để biểu diễn Batch assignment.

Validation backend:

- một active assignment duy nhất cho cùng `learner + target_type + target`;
- Course/Batch phải published và learner phải hợp lệ;
- `due_at` dùng timezone hệ thống, deadline ngày được chuẩn hóa thành cuối ngày;
- huỷ chỉ đổi Assignment; không xóa enrollment hoặc lịch sử học;
- không cho client tự ghi `status`, `progress`, `completed_at`.

### 3.2 Tích hợp với Enrollment hiện tại

Tạo service nội bộ duy nhất, ví dụ `ensure_learning_enrollment(learner, course, batch=None)`, được dùng bởi Assignment, Batch sync và Bulk import.

| Tình huống | Cách xử lý |
|---|---|
| Giao Course | Tìm `LMS Enrollment(member, course)`; có thì reuse, chưa có thì tạo bằng service. Tạo Item liên kết enrollment đó. |
| Giao Batch | Ensure `LMS Batch Enrollment(batch, member)`, rồi reuse luồng Batch để ensure `LMS Enrollment` cho từng course; tạo Item cho từng course. |
| Thêm learner vào Batch | Giữ hành vi có enrollment hiện nay, nhưng gọi chung service để tránh logic trùng. Chỉ materialize Item nếu learner có active Batch Assignment tương ứng. |
| Thêm course vào Batch đã có learner | Endpoint/UI phải trả preview số learner/course ảnh hưởng. Người vận hành chọn **Sync Existing Learners** hoặc **Không sync**. Khi sync: ensure enrollment và thêm Item cho active Batch Assignment. Khi không sync: giữ lịch sử, không tạo enrollment/item mới. |
| Xóa course khỏi Batch | Không xóa enrollment, Assignment Item hay lịch sử. Item được đánh dấu `removed_from_batch_at`/archived để báo cáo còn truy vết. |

Completion của Assignment lấy từ dữ liệu completion server-side của Enrollment/course requirement, không tin giá trị do frontend gửi. Course Assignment hoàn thành khi item hoàn thành; Batch Assignment hoàn thành khi toàn bộ item bắt buộc hoàn thành.

### 3.3 Status và permission flow

```text
Create/activate → Assigned → In Progress → Completed
                       └────→ Overdue ───→ Completed (completed_late = 1)
Any active state ─────────────────────────→ Cancelled
```

- `Assigned`: chưa có hoạt động và chưa complete.
- `In Progress`: có progress/lesson activity nhưng chưa complete.
- `Overdue`: `now > due_at` và chưa complete.
- `Completed`: đã đạt điều kiện completion; nếu sau deadline, giữ `completed_late = 1` thay vì giữ trạng thái Overdue.
- `Cancelled`: hành động quản trị có lý do; dừng reminder nhưng không phá enrollment/history.

Daily job chạy theo timezone hệ thống để reconcile trạng thái và gửi reminder 7/3/1 ngày. Bảng log reminder có unique key `assignment + reminder_code`; retry không gửi trùng. Notification dùng `make_lms_notification_logs()` và link về course/My Learning, không link nhầm vào quiz.

| Vai trò | Quyền Phase 1 |
|---|---|
| System Manager | Toàn quyền Assignment, Bulk, Sync, report/export và cancel. |
| Moderator | Tạo/sửa/cancel assignment, Batch sync, bulk và report trong phạm vi LMS. |
| Instructor | Chỉ giao/đọc báo cáo cho course mình là instructor. Với Batch nhiều course ngoài phạm vi, backend từ chối thay vì tin UI. |
| Learner | Chỉ xem My Learning, deadline/tiến độ và lịch sử của chính mình; không sửa assignment/status. |

Permission luôn kiểm tra trong whitelisted API/service bằng helper hiện có (`has_course_moderator_role`, `is_instructor`, kiểm tra instructor của course), không dựa riêng vào DocType JSON hoặc route guard frontend.

### 3.4 Cách xử lý MR !42

MR !42 (`8df9cd5`) gộp hai phạm vi khác nhau:

1. Skill/HRMS refactor — **không thuộc Phase 1**, không merge theo work này.
2. `LMS Course Assignment Rule` — rule theo Department/Designation, hiện auto-create Enrollment/Batch Enrollment trực tiếp qua employee hook và daily reconciliation.

Phần Rule không được dùng làm Learning Assignment model vì hiện thiếu deadline, mandatory, assignment audit, My Learning, compliance và idempotency reminder. Auto-enroll trực tiếp cũng làm mất thông tin “ai giao, giao khi nào, hạn bao lâu”.

Quyết định đề xuất:

- **Hold MR !42** khỏi Phase 1 branch; không cherry-pick toàn MR.
- Giữ thiết kế Rule như một **nguồn tạo Assignment trong giai đoạn sau của Phase 1 hoặc Phase 1.1**, sau khi service `create_learning_assignment()` đã ổn định.
- Khi port lại Rule, thay `create_membership()`/`enroll_in_batch_target()` bằng service Assignment trung tâm. Rule chỉ quyết định *ai* và *target nào*; Assignment service quyết định enrollment, due date, audit, notification và chống trùng.
- Chỉ bật Department/Designation rule khi site có Employee/HRMS. Manual, Batch và Bulk Phase 1 phải chạy được trên site không có HRMS.

## 4. Kế hoạch thực hiện sau khi được duyệt

1. Tạo DocType/migration và Assignment service; thêm unit/verification script cho duplicate, course/batch target và reuse enrollment.
2. Thêm deadline reconcile, reminder log/job và notification template.
3. Làm My Learning + Assignment management + Batch sync preview/confirmation.
4. Làm Bulk CSV/XLSX theo luồng validate → preview → confirm → background result/error file.
5. Làm compliance report và export XLSX/PDF template riêng; kiểm thử trên site **có và không có HRMS**.

Mỗi bước phải kiểm tra migration, permission backend, hành vi Batch cũ và không sửa trực tiếp các file PAI/Competency/Skill Intelligence.

## 5. Điểm cần review/chốt

1. Duyệt model cha–con: một Assignment Batch có các Item course để giữ target gốc và báo cáo theo course.
2. Duyệt nguyên tắc sync Batch: không sync im lặng; chọn rõ Sync Existing Learners hoặc Không sync.
3. Duyệt quyền: Moderator là vai trò L&D mặc định, Instructor chỉ trong phạm vi course sở hữu.
4. Duyệt hướng xử lý MR !42: giữ lại, tách phần Skill/HRMS; chỉ port lại Rule sau khi Assignment service hoàn thành.

Sau khi bốn điểm này được duyệt mới bắt đầu code Phase 1.

## 6. Cập nhật thực tế triển khai Phase 1A (28/09/2026)

Đã triển khai phần core theo mục 3.1–3.3: `LMS Learning Assignment`, child item, service
ensure/reuse `LMS Enrollment`, permission scope backend, chống trùng, cancel có audit, resolver
deadline/status, reminder log/job và My Learning UI/API. Bulk, compliance và Batch Sync **chưa được
triển khai**; các phần này vẫn thuộc Phase 1C.

Chi tiết endpoint, validation và bằng chứng kiểm tra nằm tại
[PHASE_1A_LEARNING_ASSIGNMENT_IMPLEMENTATION.md](./PHASE_1A_LEARNING_ASSIGNMENT_IMPLEMENTATION.md).

Chi tiết Phase 1B nằm tại
[PHASE_1B_MY_LEARNING_IMPLEMENTATION.md](./PHASE_1B_MY_LEARNING_IMPLEMENTATION.md).
