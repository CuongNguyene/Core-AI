# Khung đánh giá năng lực ba tầng

## Tầng 1 — Evidence Acquisition & Normalization

### Trách nhiệm

- Trích xuất dữ liệu.
- Gắn nguồn và vị trí.
- Chuẩn hóa khái niệm.
- Phân loại bằng chứng.
- Phát hiện dữ liệu thiếu/mâu thuẫn.

### Không được làm

- Kết luận người dùng đạt năng lực.
- Gán cấp độ verified.
- Tự động cấp chứng nhận.

## Tầng 2 — Competency Mapping & Hypothesis

### Trách nhiệm

- So sánh với Role Competency Profile.
- Xác định explicit/inferred/partial/insufficient/conflicting evidence.
- Tạo preliminary skill gap.
- Chọn assessment phù hợp.
- Chỉ nhận Evidence Profile đã qua human review `ACCEPTED` và Role Competency
  Profile `ACTIVE` làm input matching chính thức.
- PREVIEW là ngoại lệ có kiểm soát: Role Competency Profile `PROVISIONAL` có thể
  chạy với policy exact đã resolve để tạo hypothesis/evidence portfolio, nhưng
  output phải mang `analysis_mode=PREVIEW`, không phải quyết định chính thức.
- CandidateProfile phải giữ semantics của accepted extraction qua EvidenceIndex:
  `work_experience`, `project_usage`, `explicit_skill`, education và credential
  không được flatten thành cùng một loại mention.
- Giữ allocation evidence truy xuất được; một evidence không được dùng làm bằng
  chứng quyết định lặp lại ở nhiều requirement.
- `retrieved_candidate_count` và `eligible_candidate_count` phải tách biệt; bằng
  chứng liên quan nhưng sai context (ví dụ project deployment cho production
  requirement) có thể retrieved nhưng không eligible.

### Không được làm

- Biến `CV_EXPLICIT_MATCH` thành `VERIFIED`.
- Dùng confidence thấp để kết luận thiếu năng lực.
- Dùng overall score duy nhất, tự động tuyển/loại, hoặc tự động ra quyết định
  downstream không có human review.
- Diễn giải `NOT_FOUND_IN_EVIDENCE`, `INSUFFICIENT` hoặc `CONTEXT_MISMATCH` như
  confirmed capability absence.

## Tầng 3 — Competency Assessment & Verification

### Trách nhiệm

- Thực hiện assessment theo claim–evidence–task.
- Chấm rubric.
- Tổng hợp nhiều bằng chứng.
- Ra competency decision.
- Cập nhật trạng thái assessed/verified.
- Kích hoạt credential policy nếu đủ điều kiện.
- Chỉ SME được tổ chức ủy quyền xác minh năng lực mới có thể transition sang
  `VERIFIED`; ADMIN không tự động có thẩm quyền chuyên môn.
- PREVIEW không tạo final competency decision, không cập nhật capability sang
  `VERIFIED` và không được sinh learning objective/path.

Credential policy nằm sau tầng đánh giá và không thay thế competency decision:

- `COMPLETION` chỉ đọc completion assertion từ learning system có thẩm quyền;
  learning path hoặc lesson metadata không phải completion.
- `LEARNING_ACHIEVEMENT` chỉ đọc learning-outcome assertion đã gắn assessment/
  rubric; assessment bất kỳ không tự động trở thành achievement.
- `COMPETENCY` chỉ đủ điều kiện khi competency record là `VERIFIED`, còn hiệu
  lực và decision/evidence/rubric reference hợp lệ.
- Thiếu nguồn authoritative trả `NOT_EVALUABLE`, không đổi thành
  `INELIGIBLE`. Mọi loại credential đều cần approval và audit trước issuance.

Persistence của tầng này tách assessment decision khỏi competency record.
Assessment decision trỏ về submission, SME review, evidence và rubric/policy
version; competency transition tạo decision history immutable và audit trong
cùng transaction. Completion không tạo competency transition.

Learning Path & Content Blueprint (PR-007) chỉ đọc verified competency profile,
target role profile ACTIVE, preliminary gaps đã REVIEWED/approved và mục tiêu có
thời hạn. Blueprint và learning object chỉ lưu metadata/provenance; hoàn thành
learning không cập nhật competency và không phát hành credential.

## Quy tắc chứng nhận

- Completion certificate: hoàn thành nội dung.
- Learning achievement certificate: đạt learning outcomes.
- Competency certificate: đạt assessment và competency decision theo policy.
