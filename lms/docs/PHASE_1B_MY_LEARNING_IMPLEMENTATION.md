# Phase 1B — Deadline, Reminder và My Learning: ghi nhận triển khai

**Trạng thái:** Ready for Review kỹ thuật
**Ngày triển khai:** 28/09/2026
**Tracker áp dụng:** `LMS-P1-007` đến `LMS-P1-010`

## Phạm vi đã hoàn thành

| Hạng mục | Kết quả |
| --- | --- |
| Canonical status | Backend derive `Assigned`, `In Progress`, `Completed`, `Overdue`, `Cancelled` từ item và `LMS Enrollment.progress`; frontend không tự tính status. |
| Deadline/completion | Assignment lưu `progress`, `last_activity_at`, `completed_at`, `completed_late`. Hoàn thành sau `due_at` có status `Completed` và cờ `completed_late = 1`, không giữ trạng thái Overdue. |
| Daily reconciliation | Scheduler hằng ngày duyệt Assignment active và chỉ lưu khi derived value thay đổi. |
| Reminder | D-7/D-3/D-1 dùng `LMS Learning Assignment Reminder Log` với unique key `assignment + reminder_code`; retry không gửi notification trùng. |
| My Learning API | `lms.lms.learning_assignment_api.get_my_learning` luôn lọc `learner = frappe.session.user`; không nhận learner từ client. |
| My Learning UI | Route `/my-learning`, sidebar learner và bốn tab Được giao/Đang học/Quá hạn/Hoàn thành. Card hiển thị deadline, progress, hoạt động gần nhất và Continue Learning. |

## Nguồn dữ liệu và quy tắc trạng thái

`LMS Enrollment` vẫn là nguồn progress/current lesson. `LMS Learning Assignment` chỉ giữ nghĩa vụ
học và snapshot derived để report/audit sau này.

1. Tất cả item có progress 100 → `Completed`; `completed_at` lấy thời điểm enrollment cuối hoàn tất.
2. Chưa hoàn thành và `now > due_at` → `Overdue`.
3. Chưa overdue nhưng có ít nhất một enrollment progress > 0 → `In Progress`.
4. Còn lại → `Assigned`.
5. `Cancelled` do quản trị đặt và không bị scheduler ghi đè.

Phase 2A sẽ thay điều kiện completion `progress == 100` bằng evaluator đầy đủ lesson + required quiz
và Pending Review. Phase 1B không tự suy diễn quiz completion ở frontend.

## Thành phần nguồn

- `lms/lms/learning_assignment.py`: status resolver, reconcile scheduler, reminder service và
  My Learning read model.
- `lms/lms/doctype/lms_learning_assignment/`: trường derived status/progress/completion.
- `lms/lms/doctype/lms_learning_assignment_reminder_log/`: log reminder idempotent.
- `lms/lms/learning_assignment_api.py`: endpoint My Learning.
- `lms/hooks.py`: daily scheduler entry.
- `frontend/src/pages/MyLearning.vue`: trang learner.

## Kiểm tra đã chạy

- Migration trên `lms.test` đã tạo `LMS Learning Assignment Reminder Log` và sync trường Assignment.
- Unit test hiện có: **5/5 đạt**, bao gồm derive Overdue/Completed Late từ enrollment + due date.
- Live verification trên `lms.test`: tạo user/course assignment tạm → set enrollment 55% → My
  Learning trả In Progress → derive Overdue theo clock test → gửi D-1 hai lần và xác nhận chỉ có
  một reminder log. Dữ liệu tạm tự xóa khi kết thúc.
- `yarn build`: đạt với frontend My Learning; build chỉ cảnh báo font WOFF đã tồn tại từ asset cũ.
- Frappe runner chưa chạy được vì `lms.test` đặt `allow_tests=false`; không tự đổi cấu hình site.

## Ngoài scope / chuyển Phase 1C

- Batch Sync có lựa chọn Sync Existing Learners hoặc Không sync.
- Bulk assignment CSV/XLSX, preview/error file/background job.
- Compliance report và export XLSX/PDF dùng cùng server-side filter.
- Department/Designation rule từ MR !42 và mọi phần HRMS/Skill.

## Điều kiện UAT trước khi đánh dấu Done

1. Kiểm tra scheduler ở timezone production tại các mốc D-7/D-3/D-1 và qua hạn.
2. Learner kiểm tra chỉ thấy assignment bản thân; Instructor/Moderator không có quyền xem sai scope.
3. Kiểm tra completion đúng với course có/không có lesson và với progress update thực tế.
4. Xác nhận wording/translation của page My Learning trước release.
