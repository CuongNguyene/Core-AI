# Phase 1A — Learning Assignment: ghi nhận triển khai

**Trạng thái:** Ready for Review kỹ thuật
**Ngày triển khai:** 28/09/2026
**Tracker áp dụng:** `LMS-P1-001` đến `LMS-P1-006`

## Phạm vi đã hoàn thành

Phase này bổ sung lớp quản lý **nghĩa vụ học** mà không tạo thêm một hệ enrollment. Bản ghi
`LMS Learning Assignment` là nguồn audit cho việc giao/hủy; `LMS Enrollment` vẫn là nguồn quyền
học, tiến độ và liên kết với bài nộp.

| Hạng mục | Kết quả |
| --- | --- |
| Giao Course | Tạo một assignment và một item; reuse `LMS Enrollment` nếu learner đã enrolled, nếu chưa thì tạo enrollment hiện hữu. |
| Giao Batch | Ensure `LMS Batch Enrollment`, materialize một item cho mỗi course của Batch và ensure enrollment từng course. |
| Chống trùng | Một active assignment duy nhất theo learner + loại target + target; retry cùng `idempotency_key` trả về bản ghi cũ. |
| Hủy giao | Chuyển trạng thái sang `Cancelled`, bắt buộc lý do/người hủy/thời điểm; không xóa enrollment, progress hoặc submission. |
| Phân quyền | System Manager/Moderator có LMS scope; Instructor chỉ được thao tác target mà mình phụ trách; learner không có quyền mutation. |

## Thành phần nguồn

- `lms/lms/doctype/lms_learning_assignment/`: DocType cha, audit và active unique key.
- `lms/lms/doctype/lms_learning_assignment_item/`: child item liên kết Course, `LMS Enrollment`
  và Batch nguồn.
- `lms/lms/learning_assignment.py`: domain service, validation, scope permission, idempotency và
  orchestration enrollment.
- `lms/lms/learning_assignment_api.py`: API whitelisted cho mutation.
- `lms/lms/test_learning_assignment.py`: test đơn vị cho tạo/reuse, duplicate và cancel.

## API Phase 1A

Các mutation không cấp quyền ghi DocType trực tiếp; caller dùng API và backend tự kiểm tra scope.

| Endpoint | Tham số chính | Hành vi |
| --- | --- | --- |
| `lms.lms.learning_assignment_api.create_learning_assignment` | `learner`, `target_type` (`Course`/`Batch`), `target`, `due_at`, `mandatory`, `note`, `idempotency_key` | Giao nghĩa vụ học; trả assignment cùng item/enrollment được reuse/tạo. |
| `lms.lms.learning_assignment_api.cancel_learning_assignment` | `name`, `reason` | Hủy assignment có audit; không xóa dữ liệu học. |

## Kiểm tra đã chạy

- `bench --site lms.test migrate`: đã sync hai DocType vào site test.
- `python3 -m py_compile ...`: đạt cho service, API, controller và test.
- `python3 -m unittest lms.lms.test_learning_assignment`: **5/5 đạt**.
- Live verification trên `lms.test`: tạo Course assignment, retry bằng cùng idempotency key, thử
  duplicate active assignment, cancel; sau đó giao Batch hai course để xác minh Batch Enrollment,
  reuse Enrollment có sẵn và tạo Enrollment còn thiếu. Dữ liệu tạm đã được xóa sau kiểm thử.
- Frappe runner chưa chạy được vì site đang đặt `allow_tests=false`; không tự thay cấu hình site.

## Cố ý để lại cho phase sau

- `LMSBatchEnrollment.validate_course_enrollment()` đã chuyển sang dùng service
  `ensure_learning_enrollment()` chung; `LMSBatch.validate_membership()` không còn auto-enroll khi
  sửa Batch. Chính sách UI **Sync Existing Learners** hoặc **Không sync** vẫn thuộc Phase 1C.
- Chưa có deadline resolver, overdue, reminder, My Learning UI, bulk import, compliance report/XLSX
  hay Department/Designation rule. Đây lần lượt là Phase 1B/1C.
- UI quản trị Assignment và My Learning đã được đưa vào Phase 1B; multi-learner selection trong một
  thao tác vẫn cần được bổ sung trước khi chốt UAT của `LMS-P1-001`.

## Điều kiện chuyển sang Phase 1B

1. BA/SA review xác nhận semantics Course/Batch assignment và policy cancel.
2. UAT tối thiểu với System Manager, Moderator, Instructor trong scope và Learner ngoài scope.
3. Migration được thử trên bản sao dữ liệu trước khi đưa vào môi trường production.
