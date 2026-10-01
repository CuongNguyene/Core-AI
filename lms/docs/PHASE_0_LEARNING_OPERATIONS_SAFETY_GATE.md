# Phase 0 — Learning Operations safety gate

**Trạng thái:** Ready for review
**Mục đích:** chốt baseline kỹ thuật trước Phase 1A; **không thay đổi schema, dữ liệu hay hành vi runtime**.
**Roadmap:** [LMS_REFACTOR_IMPLEMENTATION_ROADMAP.md](./LMS_REFACTOR_IMPLEMENTATION_ROADMAP.md)
**Thiết kế chi tiết:** [PHASE_1_LEARNING_OPERATIONS_TECHNICAL_DESIGN.md](./PHASE_1_LEARNING_OPERATIONS_TECHNICAL_DESIGN.md)

## 1. Quyết định đã chốt

| Quyết định | Lý do / bằng chứng source | Hệ quả Phase 1 |
| --- | --- | --- |
| Không tạo enrollment thứ tư | `LMS Enrollment` còn load-bearing cho progress và Exercise Submission; `LMS Batch Enrollment` là membership Batch hiện hành; `Cohort*` chưa thể xóa. | `LMS Learning Assignment` chỉ là obligation layer; mỗi item link tới enrollment hiện có. |
| Không dùng `LMS Assignment` hiện hữu | Doctype này là assignment/bài tập nằm trong lesson, không phải lệnh giao học. | Dùng tên mới `LMS Learning Assignment` và `LMS Learning Assignment Item`. |
| Có một enrollment service chung | Cả `LMSBatch.validate_membership()` và `LMSBatchEnrollment.validate_course_enrollment()` đang tự tạo `LMS Enrollment`. | Phase 1A tách `ensure_learning_enrollment()` trước khi thêm assignment/bulk/sync. |
| Assignment là nguồn deadline/status | `LMS Enrollment` hiện chỉ có progress/current lesson; không có người giao, due date hay completed late. | Không thêm due date/status vào Enrollment. |
| Batch sync phải explicit | Batch hiện tự sync course mới tới existing member trong `validate_membership()`. | Phase 1C thay bằng preview + lựa chọn Sync/Không sync, không thay đổi lịch sử cũ. |
| Department là optional filter | Report cũ join `Employee` và lỗi khi site không có HRMS. | Compliance report phải chạy được không có Employee; chỉ thêm filter Department khi doctype tồn tại. |
| MR !42 không merge nguyên khối | Rule hiện auto-create enrollment/batch enrollment và scope Skill/HRMS vượt Phase 1. | Hold MR !42; sau Phase 1C chỉ port rule như nguồn target của Assignment service. |

## 2. Inventory enrollment và call site cần refactor có kiểm soát

| Khu vực | Hành vi hiện tại | Cách xử lý ở Phase 1 |
| --- | --- | --- |
| `lms/lms/doctype/lms_batch/lms_batch.py` — `validate_membership` | Khi Batch có learner, thêm course sẽ tự tạo `LMS Enrollment` còn thiếu. | Thay bằng call service chung sau khi UI/API đã nhận explicit sync decision. |
| `lms/lms/doctype/lms_batch_enrollment/lms_batch_enrollment.py` — `validate_course_enrollment` | Khi thêm learner vào Batch, tự tạo course enrollment cho mọi Batch Course. | Giữ semantics enrollment, nhưng chuyển call sang service chung; chỉ tạo Assignment Item nếu active Batch Assignment tồn tại. |
| `lms/lms/utils.py` — `enroll_in_course` | Learner tự enroll course, có guard duplicate. | Không đổi trong Phase 1; service Assignment phải reuse record do flow này tạo. |
| `lms/lms/utils.py` — `enroll_in_batch` | Learner tự tạo Batch Enrollment; hook/controller tạo course enrollment. | Không đổi ownership/payment semantics; service Assignment không giả định mọi Batch Enrollment là mandatory assignment. |
| `LMS Enrollment` progress/current lesson | Nguồn progress và completion hiện tại. | Status resolver chỉ đọc server-side; không cho client ghi Assignment completion/status. |
| `Exercise Submission` / `Exercise Latest Submission` | `member` link tới `LMS Enrollment`. | Không xóa/recreate enrollment khi cancel Assignment hoặc remove course khỏi Batch. |

## 3. Model boundary được duyệt để code Phase 1A

```text
LMS Learning Assignment (obligation; target Course hoặc Batch)
  └─ LMS Learning Assignment Item (mỗi course phải học)
       └─ LMS Enrollment (quyền học + progress hiện hữu)

LMS Batch Enrollment (membership Batch)
  └─ LMS Enrollment (course enrollment hiện hữu)
```

- Assignment theo Course có một item; assignment theo Batch materialize một item mỗi course tại thời
  điểm giao.
- Assignment Item không sở hữu progress; nó cache/projection dữ liệu progress để report/UI nếu cần.
- Cancel Assignment chỉ đổi lifecycle assignment/item. Không delete `LMS Enrollment`, submission,
  lesson progress hoặc certificate.
- Không backfill toàn bộ Enrollment cũ thành Assignment. Chỉ tạo Assignment mới qua Manual, Bulk,
  Batch Sync hoặc Rule (sau Phase 1C) có business source xác định.

## 4. Permission matrix bắt buộc

| Action | System Manager | Moderator | Instructor | Learner |
| --- | --- | --- | --- | --- |
| Create/cancel Course Assignment | Có | Có | Chỉ course mình phụ trách | Không |
| Create/cancel Batch Assignment | Có | Có | Chỉ khi kiểm soát được toàn bộ course của Batch; nếu không từ chối | Không |
| Sync Batch existing learners | Có | Có | Cùng giới hạn Batch/course | Không |
| Bulk import | Có | Có | Không trong Phase 1 | Không |
| Compliance report/export | Có | Có | Chỉ course scope của mình | Chỉ My Learning của mình |
| My Learning/status | Có scope admin | Có scope admin | Có scope course | Chỉ dữ liệu của mình |

Mỗi whitelisted mutation phải gọi guard tường minh, không dựa vào DocType JSON hoặc router:

- Moderator: `has_course_moderator_role()` hoặc `frappe.only_for("Moderator")` theo phạm vi.
- Instructor: `can_create_courses(course, member)` / `is_instructor(course)` cho **từng course**.
- Learner: so `assignment.learner == frappe.session.user` tại server.

## 5. Status contract cho Phase 1B

```text
Create/activate → Assigned → In Progress → Completed
                       └────→ Overdue ───→ Completed (completed_late = 1)
Any active state ─────────────────────────→ Cancelled
```

| Status | Server-side rule |
| --- | --- |
| Assigned | Active, chưa có activity/progress, chưa complete. |
| In Progress | Có lesson activity hoặc progress > 0, chưa complete. |
| Overdue | `now > due_at`, chưa complete và chưa cancelled. |
| Completed | Requirement completion đạt; nếu `completed_at > due_at` thì `completed_late = 1`. |
| Cancelled | Admin action có reason; dừng reminder, giữ lịch sử. |

Không đưa `Completed Late` thành status thứ sáu; đó là cờ report để tránh learner đã hoàn thành vẫn
thấy Overdue.

## 6. Scheduler và notification contract

`hooks.py` hiện đã có daily scheduler và `make_lms_notification_logs()` đã gửi inbox/realtime/email.
Phase 1B thêm một daily reconcile job độc lập với các job Batch/Payment/Live class hiện có.

| Job | Input | Idempotency | Không được làm |
| --- | --- | --- | --- |
| Reconcile assignment status | Active assignment + Enrollment/progress | Safe khi chạy lặp | Không sửa progress/enrollment. |
| Deadline reminder D-7/D-3/D-1 | Active assignment có `due_at` | Unique `assignment + reminder_code` | Không gửi Completed/Cancelled, không gửi trùng. |
| Bulk processing | Bulk request đã Confirmed | Row-level idempotency key | Không rollback các dòng hợp lệ vì một dòng lỗi. |

Notification deadline phải link tới My Learning hoặc Course. Không dùng link quiz mặc định.

## 7. Test matrix trước khi code

| Nhóm | Case tối thiểu | Evidence cần có |
| --- | --- | --- |
| Enrollment reuse | Course Assignment với learner đã có `LMS Enrollment`. | Assignment Item trỏ đúng enrollment cũ; không tăng record count. |
| Enrollment create | Learner mới, Course và Batch Assignment. | Một enrollment/course; đúng Batch Enrollment khi target Batch. |
| Duplicate/retry | Gửi cùng mutation hai lần. | Một active Assignment, một enrollment/item; response idempotent. |
| Cancel/history | Cancel assignment sau khi learner có progress/submission. | Assignment cancelled; enrollment/progress/submission còn nguyên. |
| Permission | Learner mutation; Instructor course khác; Moderator; System Manager. | 403 cho role/scope sai; chỉ đúng scope thành công. |
| Status/deadline | Before due, overdue, completed before/after due, cancelled. | Resolver trả canonical status + completed_late đúng. |
| Reminder | Job chạy lặp ở D-7/D-3/D-1 và assignment completed/cancelled. | Mỗi code chỉ một log; không có log bị cấm. |
| Batch sync | Add course khi Batch đã có learner, chọn sync / no-sync. | No-sync không mutation; sync không duplicate; removal giữ history. |
| Bulk | User thiếu, target sai, duplicate, row hợp lệ. | Preview/result theo dòng; row hợp lệ vẫn xử lý. |
| Compliance/export | Có/không có Employee; cùng filter UI/XLSX/PDF. | Không lỗi không-HRMS; parity count và total. |

Các test backend chạy bằng `bench --site <site> run-tests --app lms`; trước đó dùng
`python3 -m py_compile` cho file sửa. Với enrollment cần thêm verify script tạm thời qua
`bench execute` trên site test và xóa script sau khi xác minh.

## 8. Migration, rollout và rollback

1. Migration chỉ **thêm** DocType/index/child table; không rewrite hay delete enrollment cũ.
2. Không chạy backfill Assignment tự động.
3. Feature flag/permission gate giữ UI mutation chưa mở cho learner đến khi 1A–1B đạt UAT.
4. Rollback ứng dụng phải không làm orphan Assignment Item; nếu đã migrate schema thì rollback code
   vẫn giữ schema additive, không drop table trong production.
5. Trước production: migrate trên database clone, smoke test Course enrollment, Batch enrollment,
   Exercise Submission, progress và certificate.

## 9. Gate để bắt đầu Phase 1A

Phase 1A chỉ bắt đầu sau khi BA/SA xác nhận:

- [ ] Tên/field của `LMS Learning Assignment` và Item.
- [ ] Chính sách target Batch: course thêm sau khi giao xử lý ở Phase 1C, không retroactive ngầm.
- [ ] Deadline timezone/end-of-day và định nghĩa completion của course.
- [ ] Instructor scope với Batch nhiều course.
- [ ] Không backfill toàn bộ enrollment lịch sử.
- [ ] MR !42 vẫn hold, Skill/HRMS không vào branch Phase 1.

Khi review xong, cập nhật tracker: Phase 0 safety gate là **Done**; `LMS-P1-001` chuyển
**In Progress** khi bắt đầu schema/service của Phase 1A.
