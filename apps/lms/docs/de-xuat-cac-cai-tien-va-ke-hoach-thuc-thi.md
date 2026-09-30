# Đề xuất các cải tiến và kế hoạch thực thi LMS

> Mục tiêu: chuyển LMS từ mô hình course mở/lớp học theo Batch sang mô hình đào tạo nội bộ có giao việc, hạn hoàn thành, theo dõi tuân thủ và báo cáo nhất quán.
>
> Phạm vi tài liệu: đề xuất và kế hoạch thực thi; không phải đặc tả API hay kế hoạch migration chi tiết.

## 1. Tóm tắt hiện trạng

LMS hiện có nền tảng đào tạo đầy đủ: Course → Chapter → Lesson, Batch, ghi danh, tiến độ, quiz, certificate, Program, tài liệu, notification và báo cáo. Các khả năng nổi bật gồm SCORM, live class, quiz có kiểm soát thời gian, assignment, thảo luận và báo cáo theo phòng ban.

Tuy nhiên, các luồng đào tạo nội bộ còn thiếu lớp điều phối: ai được giao học gì, hạn bao lâu, ai quá hạn, và báo cáo tuân thủ theo từng đối tượng. Một số chức năng hiện có cũng mới đáp ứng một phần yêu cầu.

| Nhóm | Hiện trạng đã có | Giới hạn cần xử lý |
| --- | --- | --- |
| Giao học | Admin/Instructor có thể thêm learner vào Batch; learner được enroll vào các course đã có trong Batch | Không có deadline, overdue, người giao, reminder; thêm course sau khi Batch đã có learner không tự sync enrollment |
| My Learning | Có danh sách đang học và chưa bắt đầu | Chưa có trạng thái Assigned/Completed/Overdue, deadline, last access; course public có thể xuất hiện cùng khu vực course của learner |
| Quiz | Có quiz sau lesson, giới hạn attempt, timer, open-ended và chấm tay cơ bản | Chưa có learner Quiz Hub, quiz cuối chapter/final quiz, Pending Review/rubric/queue chấm rõ ràng |
| Certificate | Có Print Format/PDF, learner lấy certificate khi course đạt 100%, bulk generate theo Batch | Chưa tự cấp theo điều kiện backend, bulk chưa lọc theo điều kiện hoàn thành, chưa revoke/final score/XLSX |
| Program | Có danh sách course, member, thứ tự và khóa course sau trên UI | Thêm member vào Program không tự enroll các course; không deadline, reminder hay notification assignment |
| Báo cáo | Có Statistics, report phòng ban và export PDF | Chưa export XLSX cho progress, quiz, completion, deadline và certificate |

## 2. Nguyên tắc thiết kế

1. **Không tạo hệ enrollment thứ tư.** App đang có `LMS Enrollment`, `LMS Batch Enrollment` và các dữ liệu legacy liên quan. Feature giao học phải là lớp điều phối phía trên các enrollment hiện có.
2. **Quy tắc hoàn thành và cấp certificate phải kiểm tra ở backend.** Không dựa chỉ vào việc frontend ẩn/hiện nút.
3. **Phân quyền phải được kiểm tra tường minh ở endpoint.** Instructor chỉ được thao tác với course/batch thuộc phạm vi của họ; Moderator/System Manager có phạm vi rộng hơn.
4. **Batch vẫn là lớp học/đợt đào tạo.** Course Assignment không thay Batch; nó bổ sung deadline, nguồn giao, reminder và báo cáo tuân thủ.
5. **Triển khai theo phase.** Các màn My Learning, report và import phải dùng chung dữ liệu Assignment để không phân tán trạng thái.

## 3. Các cải tiến đề xuất

### 3.1. Mandatory Course Assignment và deadline

**Mục tiêu:** Admin/Manager/Instructor giao course hoặc Batch cho learner, có hạn hoàn thành và theo dõi trạng thái.

Thông tin cần quản lý:

| Trường nghiệp vụ | Ý nghĩa |
| --- | --- |
| Đối tượng giao | Course hoặc Batch |
| Người nhận | User, Batch hoặc Department (sau khi xác định scope quyền) |
| Người giao | User thực hiện giao |
| Ngày giao / hạn hoàn thành | Dùng để hiển thị deadline và tính overdue |
| Bắt buộc | Phân biệt course mandatory với course tự chọn |
| Trạng thái | Assigned, In Progress, Completed, Overdue, Cancelled |
| Reminder log | Ghi nhận reminder 7/3/1 ngày để không gửi trùng |

Luồng đề xuất:

```text
Admin giao Course/Batch
→ tạo hoặc liên kết enrollment đúng hệ hiện tại
→ learner nhận notification
→ learner thấy trên My Learning
→ hệ thống nhắc deadline 7/3/1 ngày
→ trạng thái tự cập nhật theo progress và deadline
```

**Yêu cầu đồng thời:** khi thêm course mới vào một Batch đã có learner, hệ thống phải tạo enrollment cho các learner hiện có hoặc hiển thị lựa chọn sync rõ ràng.

### 3.2. My Learning cho learner

Tạo workspace riêng, chỉ dùng dữ liệu enrollment/assignment của learner:

```text
Được giao | Đang học | Đã hoàn thành | Quá hạn | Khám phá khóa học
```

Mỗi course card cần có deadline (nếu có), tiến độ, lần hoạt động gần nhất và nút **Tiếp tục học**. Course featured/public phải nằm ở khu vực **Khám phá khóa học**, không trộn vào danh sách course được giao.

### 3.3. Learner Quiz Hub và assessment lifecycle

Tạo trang **Quiz của tôi** chỉ hiển thị assessment learner có quyền truy cập:

- Lọc theo course và vị trí assessment.
- Trạng thái: chưa làm, đạt, không đạt, chờ chấm, hết lượt.
- Xem toàn bộ attempt cá nhân.

Chuẩn hóa phạm vi quiz:

| Phạm vi | Hiện trạng | Cải tiến |
| --- | --- | --- |
| Sau lesson | Đã có | Giữ nguyên và chuẩn hóa required/pass condition |
| Cuối chapter | Chưa có entity riêng | Bổ sung chapter-final quiz |
| Cuối course | Chưa có entity riêng | Bổ sung final quiz |

Course chỉ được coi là hoàn thành khi toàn bộ lesson và toàn bộ quiz bắt buộc ở các phạm vi trên đã đạt.

### 3.4. Workflow chấm tự luận

Hiện đã có câu hỏi open-ended và chấm tay cơ bản. Cần bổ sung workflow rõ ràng:

```text
Learner nộp tự luận
→ Pending Review
→ Trainer thấy trong hàng đợi chấm
→ Trainer chấm theo rubric và để feedback
→ learner nhận notification
→ quiz chuyển Pass hoặc Fail
```

### 3.5. Certificate workflow hoàn chỉnh

Hiện learner có thể bấm lấy certificate khi course đạt 100%; Batch cũng có bulk generate thủ công.

Cải tiến đề xuất:

- Backend tự cấp certificate khi learner thỏa điều kiện đã định.
- Bulk issue theo Course hoặc Batch nhưng chỉ gồm learner đủ điều kiện.
- Revoke certificate với người thu hồi, thời điểm và lý do.
- Lưu final score/quiz score phù hợp trên certificate.
- Export XLSX danh sách certificate theo filter.

### 3.6. Report export XLSX

Mở rộng Statistics/Report hiện có để export PDF và XLSX theo cùng bộ filter.

Các nhóm báo cáo ưu tiên:

- Learner progress theo Course, Batch, Department.
- Completion và overdue của assignment.
- Quiz attempt, score, pass/fail và Pending Review.
- Assignment submission.
- Certificate đã cấp, revoked và hết hạn.

### 3.7. Bulk Assignment qua CSV/XLSX

Cho phép giao số lượng lớn bằng file gồm tối thiểu:

```text
user | course hoặc batch | deadline | mandatory
```

Luồng thực hiện:

```text
Tải template
→ upload file
→ preview lỗi và bản ghi hợp lệ
→ xác nhận import
→ xử lý nền
→ tải báo cáo thành công/thất bại theo dòng
```

Cần kiểm tra trước khi import: user/course/batch tồn tại, duplicate enrollment/assignment, deadline hợp lệ và quyền người giao.

## 4. Phụ thuộc và thứ tự thực thi

| Phase | Hạng mục | Phụ thuộc | Kết quả bàn giao |
| --- | --- | --- | --- |
| 0 | Khảo sát enrollment, permission và certificate eligibility | Không có | Quyết định data model, quy tắc sync Batch, ma trận quyền và migration plan |
| 1 | Assignment + deadline + reminder + Batch sync | Phase 0 | Giao học bắt buộc và dữ liệu trạng thái chuẩn |
| 2 | My Learning | Phase 1 | Workspace learner không trộn course public với course được giao |
| 3 | Quiz Hub, chapter/final quiz, review tự luận | Phase 1 | Assessment lifecycle và learner self-service hoàn chỉnh |
| 4 | Certificate auto issue/revoke + XLSX report | Phase 1 và 3 | Certificate đáng tin cậy, báo cáo tuân thủ xuất được dữ liệu |
| 5 | Bulk CSV/XLSX assignment | Phase 1 | Giao học hàng loạt có preview và audit |

## 5. Tiêu chí nghiệm thu trọng yếu

### Assignment

- Giao một course/batch cho learner tạo đúng enrollment mà không trùng dữ liệu.
- Learner thấy course trong My Learning ngay sau khi được giao.
- Deadline qua hạn chuyển Overdue theo timezone đã xác định.
- Mỗi loại reminder chỉ được gửi một lần cho mỗi assignment.
- Khi Batch có course mới, learner hiện có được sync enrollment theo chính sách đã chọn.

### Quiz

- Learner không xem được quiz ngoài course/batch được phép.
- Required quiz lesson/chapter/course đều được tính vào điều kiện completion.
- Tự luận không bị đánh giá Pass/Fail trước khi Trainer chấm.
- Learner xem được attempt của chính mình nhưng không xem attempt của người khác.

### Certificate

- Backend từ chối cấp certificate nếu learner không đủ điều kiện.
- Bulk issue bỏ qua và báo lý do cho learner không đủ điều kiện hoặc đã có certificate.
- Certificate revoked không còn tải được và hiển thị trạng thái rõ ràng.

### Import và report

- Import preview phải trả lỗi theo từng dòng, không tạo dữ liệu khi chưa xác nhận.
- XLSX export phải phản ánh đúng filter đang áp dụng trên report.

## 6. Rủi ro và lưu ý

- Enrollment đang có các hệ dữ liệu chồng lấn; không sửa trực tiếp trước khi có quyết định mapping rõ ràng.
- Endpoint mới phải giữ permission check ở backend, không chỉ dựa vào role guard trên UI.
- Certificate auto issue cần idempotent để không cấp hai lần khi progress cập nhật đồng thời.
- Import/bulk issue nên chạy nền và có log kết quả; không gửi hàng trăm email trong request đồng bộ.
- Đối với quiz và course đang học, cần cân nhắc versioning trước khi thay đổi câu hỏi/nội dung đã publish.

## 7. Hạng mục có thể triển khai sau

- Recertification/đào tạo định kỳ và nhắc chứng chỉ sắp hết hạn.
- Manager dashboard cho trưởng phòng.
- Skill matrix, prerequisite và remedial learning khi learner không pass quiz.
- Document library độc lập có search/PDF preview.
- PAI hỗ trợ soạn course/quiz/path dưới dạng draft, có review trước khi publish.
