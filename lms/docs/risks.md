# Rủi ro hệ thống (Risk register)

Liệt kê các rủi ro đã xác minh trong codebase, kèm vị trí file:line để kiểm chứng. Sắp xếp theo mức
độ nghiêm trọng. Đọc cùng `docs/data-model.md` và `docs/permissions.md` để hiểu bối cảnh.

## Mức CAO

### R1. Ghi danh — 3 hệ chồng lấn (bẫy lớn nhất của codebase)

Xem chi tiết tại `docs/data-model.md`. Ba hệ cùng tồn tại vì migration chưa xong:

1. **Legacy `Cohort*`** (`Cohort`, `Cohort Subgroup`, `Cohort Staff`, `Cohort Mentor`,
   `Cohort Join Request`) — frontend không dùng nữa, nhưng `delete_course` vẫn phải dọn chúng, và
   các helper `is_mentor`/`is_cohort_staff` (`utils.py:372`, `utils.py:379`) vẫn truy vấn.
2. **Hiện tại: `LMS Batch` + `LMS Batch Enrollment`** (mới 2025) — batch enrollment tự tạo
   `LMS Enrollment` cho mọi course trong batch (`lms_batch_enrollment.py:28`).
3. **`LMS Enrollment` — cũ nhưng vẫn load-bearing**: `Exercise Submission.member` link tới nó (không
   phải `User`), có field CT-riêng `worksuite_task`, và là doctype hiếm hoi có test thật.

**Rủi ro thực tế:**
- Sửa logic ghi danh trên một hệ có thể âm thầm phá hệ khác (ví dụ progress tính qua `LMS
  Enrollment` nhưng dữ liệu học viên nằm ở `LMS Batch Enrollment`).
- Nhìn nhầm một hệ là "chết" rồi xóa/ignore → mất dữ liệu học viên.
- `LMS Enrollment.batch_old` vẫn tham chiếu `LMS Batch Old` ở nhiều file (`lms_enrollment.py`,
  `lms_course.py`, `lms_batch_old.py`, `lms_exercise.py`, `utils.py`) — refactor tên trường/đổi
  model dễ bỏ sót.
- `lms/patches/v2_0/` chứa các migration patch đang hoạt động (mới nhất
  `fix_orphan_course_duration_column.py`, 08/2026) — chứng tỏ quá trình dọn dẹp chưa xong.

**Giảm thiểu:** đọc `docs/data-model.md` trước khi đụng enrollment; test live trên site thật với cả
ba đường ghi danh.

### R2. Cascade delete bypass toàn bộ permission

`delete_course` (`api.py:1599`) dùng `frappe.db.delete` trên ~35 bảng liên quan — không chạy qua
doc permission. **Checkpoint permission duy nhất** là `frappe.has_permission("LMS Course",
"delete", course)` ở `api.py:1606`. Nếu ai đó chèn code trước check này khi refactor, hoặc thêm
endpoint mới tái sử dụng phần cascade mà không copy check, thì **bất kỳ user nào cũng xóa được
khóa học**. Tương tự với `delete_quiz` (`api.py:1700`) và `delete_batch` (`api.py:1718`).

**Giảm thiểu:** giữ nguyên check ở đầu hàm khi sửa; endpoint mới xóa dữ liệu phải có check riêng.

### R3. Quét mã độc SCORM bị vô hiệu hóa

`check_for_malicious_code` có sẵn (`api.py:1800`) nhưng lời gọi bị **comment out** tại
`api.py:1793` — package SCORM do user upload được giải nén thẳng vào `public/scorm/` mà không
scan. Zip có thể chứa file trỏ ra ngoài thư mục (zip-slip) hoặc nội dung script độc.

**Giảm thiểu:** kích hoạt lại scan trước khi bật tính năng SCORM cho user bên ngoài.

## Mức TRUNG BÌNH

### R4. `LMS Notification` — ghi side không có guard

- `mark_as_read` (`api.py:1148`) lấy doc bất kỳ theo `name` rồi `save(ignore_permissions=True)`
  mà không kiểm tra `doc.for_user == frappe.session.user`. Đọc-side được chặn bởi
  `permission_query_conditions` (`lms_notification.py:65`), nhưng whitelist API gọi trực tiếp
  `frappe.get_doc` — không đi qua list-view filter, nên user có thể đánh dấu đã đọc notification
  của người khác nếu biết `name` (name khó đoán nhưng không bất khả xâm phạm).
- Nhiều endpoint khác cũng `insert(ignore_permissions=True)` (time log `api.py:2522`, activity
  log `api.py:2400`, progress) — chấp nhận được vì record gắn session user, nhưng là pattern dễ
  copy sai khi viết endpoint mới.

**Giảm thiểu:** thêm check `for_user` trong `mark_as_read`; không copy pattern
`ignore_permissions` cho endpoint mới mà không cân nhắc.

### R5. Fork drift với upstream Frappe LMS

Đây là fork tùy biến (Worksuite integration `lms_enrollment.py:24-44`, báo cáo phòng ban join
bảng `Employee` của HR, mobile push qua app `ctg_custom`, field liên hệ trong LMS Settings).
Merge upstream về có nguy cơ cao xung đột và mất patch CT. README.md hiện đang **conflict merge
chưa resolve** (dòng 1 có `<<<<<<< HEAD`) — dấu hiệu quá trình merge đã từng bị bỏ dở.

**Giảm thiểu:** giữ các patch CT tách file riêng (như `worksuite_integration.py`); resolve
README conflict; ghi log các điểm diverge khi merge upstream.

### R6. Phụ thuộc app ngoài không khai báo

- Worksuite integration (bắt lỗi, không chặn — `lms_enrollment.py:24-44`).
- Mobile push gọi thẳng API của app `ctg_custom` nếu có (`lms_notification.py:18`).
- Báo cáo phòng ban join bảng `Employee` — chỉ hoạt động khi app HR (erpnext) cài trên site.

Site thiếu app này sẽ chạy được nhưng tính năng âm thầm mất tác dụng. Không có check cấu hình
tập trung.

### R7. Test coverage hầu như không có

66 file `test_*.py` nhưng đa số là stub rỗng (`class TestX: pass`). Chỉ `test_lms_course.py` và
`test_lms_quiz.py` có assertion thật. Các vùng rủi ro nhất (enrollment 3 hệ, cascade delete,
permission helpers, payment flow) **không được test tự động**. Cypress chỉ có 2 spec:
`batch_creation.cy.js`, `course_creation.cy.js`.

**Giảm thiểu:** dùng pattern `lms/verify_<topic>.py` + `bench execute` để verify live (xem
`docs/dev-workflow.md`); không tin rằng sửa "an toàn vì có test".

### R8. Permission model phân tán, dễ bỏ sót

Không có hook `has_permission` tập trung; scoping thật nằm trong code:
- Helpers `utils.py` (`can_create_courses:500`, `has_course_moderator_role:527`,
  `get_report_department_scope:535` — CT-specific).
- `frappe.only_for(...)` rải rác trong `api.py` (dòng 1015, 1135, 1474, 2132, 2151, 2173, 2182).

Doctype-JSON grant Instructor full CRUD trên `LMS Course` **không if_owner** — nếu viết endpoint
mới mà quên gọi helper, mọi Instructor thao tác được khóa học của người khác ở mức JSON.

**Giảm thiểu:** endpoint mới bắt buộc gọi helper tương ứng ngay đầu hàm; xem
`docs/permissions.md`.

## Mức THẤP / theo dõi

### R9. Anti-cheat chỉ là lớp giảm thiểu, không phải rào cản tuyệt đối

- Video: watch_time bị cap theo wall-clock + playback_rate (`api.py:2336`) nhưng vẫn log từ
  client — client sửa được payload gửi lên.
- Quiz: timing enforce server-side, chấm điểm server-side (`lms_quiz.py`) — tốt; nhưng activity
  log (tab hidden, devtools) do client tự report (`api.py:2404`) — tin được như dữ liệu khai báo.
- `useExamGuards.js` chỉ chặn copy/devtools ở mức UX, không phải kiểm soát server.

**Ý nghĩa:** không dùng các chỉ số này làm bằng chứng duy nhất cho việc gian lận/khen thưởng cao.

### R10. Badge rule engine chạy trên mọi doctype

`doc_events["*"]["on_change"]` → `process_badges` (`hooks.py:100`): mọi doc save đều được đánh giá
điều kiện badge. Thêm field mới vào bất kỳ doctype nào có thể vô tình khớp condition của một badge
còn hiệu lực → trao badge sai.

### R11. Scheduler phụ trợ có thể fail im lặng

Các job hourly/daily (`hooks.py:113-126`): course statistics, Zoom/Teams attendance, payment
reminder, batch/live-class reminder, Google Calendar eval. Lỗi tích hợp ngoài (Zoom token hết hạn,
calendar không kết nối) không có alert tập trung — dữ liệu statistics/attendance âm thầm stale.

### R12. Thanh toán

`LMS Payment` controller rỗng — logic nằm ở `payments.py` + `utils.py`. Flow tự enroll sau
payment (`update_payment_record`, `utils.py:2100`) phải đối chiếu cả 2 hướng: payment thành công
nhưng enroll fail (mất tiền không có khóa học) và enroll qua đường khác không qua payment. Chưa có
reconciliation job.

## Cập nhật register này

Khi phát hiện rủi ro mới trong quá trình làm việc, thêm mục mới với: tên ngắn, mô tả, vị trí
file:line đã xác minh, và cách giảm thiểu. Xóa mục khi rủi ro đã được xử lý (ghi commit liên quan
nếu có).
