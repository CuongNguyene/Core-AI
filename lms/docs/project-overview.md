# Tổng quan dự án — Frappe Learning (LMS)

Tài liệu tổng hợp kiến trúc và toàn bộ tính năng của hệ thống. Fork của upstream
[Frappe Learning](https://github.com/frappe/lms), được org tùy biến mở rộng (viết tắt CT).
Đọc thêm: `data-model.md` (quan hệ dữ liệu), `permissions.md` (phân quyền),
`frontend-guardrails.md` (quy ước Vue), `risks.md` (rủi ro hệ thống).

---

## 1. Architecture tổng thể

### 1.1. Stack công nghệ

| Tầng | Công nghệ | Ghi chú |
|---|---|---|
| Framework | **Frappe Framework** (Python 3.10+) / Frappe v15 | Model-driven, queues, scheduler, translation, website routing |
| Backend app | App `frappe_lms`, module `lms/` | 82 DocTypes + 2 file API lớn |
| Frontend | **Vue 3** (Composition API) + Pinia + Vue Router 4 | SPA tại `/lms` |
| UI library | **frappe-ui 0.1.204** | Token semantic `bg-surface-*`/`text-ink-*` |
| Build | **Vite 5** + frappe-ui vite plugin + `vite-plugin-pwa` | |
| Styles | **Tailwind CSS 3.4** | |
| Charts | ApexCharts, Chart.js | `Statistics.vue` |
| Video | **Plyr** | Player trong Lesson |
| Editor nội dung | **EditorJS** + CodeMirror/Ace | Block-based lesson content |
| Realtime | **socket.io-client** (port 9000) | Notification, discussion |
| Telemetry | **PostHog** (tùy chọn) | |

### 1.2. Cấu trúc thư mục

```
lms/                                  # Backend Python (app root ~/frappe-bench/apps/lms)
├── hooks.py                          # Trung tâm cấu hình: doc_events, scheduler, routes, overrides
├── lms/
│   ├── api.py                        # ~72 endpoint @frappe.whitelist() — API chính (2698 dòng)
│   ├── utils.py                      # ~137 hàm: helpers PHÂN QUYỀN + ~40 endpoint whitelist (2988 dòng)
│   ├── payments.py                   # Tạo payment + payment link (Razorpay...)
│   ├── user.py                       # sign_up, validate username, on_login (self-heal role)
│   ├── unsplash.py                   # Ảnh bìa course từ Unsplash
│   ├── activation.py / telemetry.py / plugins.py / page_renderers.py
│   ├── doctype/<doctype>/            # 82 DocTypes + controller + test_*.py
│   ├── job/                          # Module Jobs (Job Opportunity, Job Settings, Job Application)
│   └── patches.txt + patches/        # 120 patches migration (v2_0 đang hoạt động)
├── overrides/web_template.py         # CustomWebTemplate — override Web Template
├── www/                              # Chỉ 2 trang server-rendered:
│   ├── lms.py / lms.html             # Shell SPA + SEO meta động theo route
│   ├── certificate.py                # Redirect tải PDF chứng chỉ
│   └── new-sign-up.html              # Đăng ký tùy chỉnh
└── job_wiki/

frontend/src/                         # Vue 3 SPA
├── main.js                           # Entry: Pinia, frappe-ui, $user/$socket/$dialog provides
├── App.vue                           # Layout động: Mobile / Desktop / NoSidebar (?fromLesson)
├── router.js                         # Route phẳng, LAZY, KHÔNG role guard
├── socket.js                         # initSocket() — frappe realtime
├── stores/                           # user.js, session.js, settings.js, sidebar.js (Pinia)
├── pages/                            # ~45 trang (~15.000 dòng)
├── components/                       # Phẳng ~50 file (KHÔNG index.ts) + Controls/ Modals/ Settings/ Notes/
├── composables/                      # useExamGuards.js, useVisibilityLog.js
└── utils/                            # index.js, dayjs.js, dialogs.js, editorjs blocks...

cypress/e2e/                          # E2E: chỉ batch_creation.cy.js + course_creation.cy.js
docs/                                 # data-model.md, permissions.md, frontend-guardrails.md, dev-workflow.md, risks.md
```

### 1.3. Luồng request kiến trúc

```
Browser  ──►  Frappe webserver (port 8000, /lms SPA shell)  ──►  Vue SPA
                                     │
                         @frappe.whitelist() REST API
                                     │
                              api.py / utils.py
                          (phân quyền imperative ở đây)
                                     │
                        DocType controllers + Frappe ORM
                                     │
                                   MariaDB
                                   Redis (queue/cache/realtime)
                                   scheduler (hourly/daily)
```

**Điểm mấu chốt:** gần như toàn bộ UI là SPA Vue điều hướng theo `/lms/<path>`; server chỉ render shell
(`www/lms.py`) và cấp SEO meta động. Business logic nằm ở whitelist endpoints, không dùng REST controller
chuẩn.

### 1.4. Kiến trúc dữ liệu (cốt lõi)

```
LMS Course ◄── chapters ──► Course Chapter ◄── lessons ──► Course Lesson
     │                                             │            └── completion_quiz → LMS Quiz
     ├── instructors (Course Instructor)
     ├── evaluators (Course Evaluator + schedule)
     └── related_courses / category / currency     LMS Enrollment ── course, cohort, batch_old, member

Ghi danh = 3 hệ song song (xem data-model.md):
   1. Cohort*          (legacy, vẫn được delete_course dọn)
   2. LMS Batch + LMS Batch Enrollment   (HIỆN TẠI)
   3. LMS Enrollment   (cũ nhưng VẪN load-bearing — Exercise Submission.member trỏ vào)
```

### 1.5. Mô hình phân quyền (tóm tắt — xem permissions.md)

- **Declarative rất ít:** chỉ `permission_query_conditions` cho LMS Notification + `has_website_permission`
  cho LMS Certificate / Certificate Evaluation.
- **Doctype-JSON grant RỘNG** (VD: Instructor full CRUD mọi course, không if_owner) → scoping thật nằm
  trong code imperative: helpers `utils.py` (`can_create_courses`, `has_course_moderator_role`,
  `get_report_department_scope` — CT-specific) + `frappe.only_for(...)` trong `api.py`.
- **Roles:** System Manager > Moderator (admin toàn app) > Instructor (per-course thực tế) > LMS Student
  (tự gán khi insert/on_login); cohort roles chỉ là field value trên Cohort Staff/Mentor.

---

## 2. Danh mục tính năng chi tiết

### 2.1. Khóa học & nội dung học (học viên)

| Feature | Cách hoạt động | Vị trí chính |
|---|---|---|
| Câu trúc 3 cấp Course → Chapter → Lesson | Child tables `Chapter Reference`/`Lesson Reference`; kéo thả sắp xếp | `api.py:1241,1300` |
| Soạn nội dung block EditorJS | Lesson content = JSON block; blocks: header, paragraph, video, audio, quiz, assignment, code, markdown, embed, pdf, upload | `LessonForm.vue`, `Lesson.vue` |
| Hỗ trợ SCORM 1.2/2004 | Upload zip → giải nén sitemap `imsmanifest.xml`, chạy qua `SCORMRenderer` + `SCORMChapter.vue` | `api.py:1760`, `page_renderers.py` |
| Ghi danh course | Self-enroll; chặn nếu `disable_self_learning`; guest có thể xem course outline | `LMS Enrollment.create_membership` |
| Progress engine | Lesson "Complete" khi: quiz đạt % pass + assignment nộp đủ + video xem ≥ 90% (cấu hình) + đủ reading time | `save_progress`, `course_lesson.py:50` |
| Reading time enforcement | Ngưỡng phút đọc/bài; trừ thời gian tab ẩn; bỏ qua với bài có video | `utils.py:1370` |
| Video thông minh | Theo dõi thời gian xem, cap theo wall-clock chống tua lừa; chống skip video (`preventSkippingVideos`) | `api.py:2336` |
| Notes & highlights | Ghi chú cá nhân trong lesson, lưu theo block | `Notes/Notes.vue`, `LMS Lesson Note` |
| Discussion | Thread theo lesson + reply + @mention → LMS Notification | `Discussions.vue` |
| Review & rating | Học viên đánh giá course sau khi học | `LMS Course Review` |
| Heatmap & streak | Lịch hoạt động học tập theo ngày + chuỗi ngày học liên tục | `get_heatmap_data`, `get_streak_info` |
| Sequential learning | Chặn mở bài sau nếu chưa hoàn thành bài trước (tùy chọn) | `get_lesson` |
| Course resources & related courses | File đính kèm + gợi ý khóa liên quan, bookmark | `CourseResources.vue` |

### 2.2. Batch & lớp học trực tiếp

| Feature | Cách hoạt động | Vị trí chính |
|---|---|---|
| LMS Batch | Seats, paid batch, assessment, evaluation window; validate chồng chéo | `lms_batch.py:26` |
| Live class qua Zoom | OAuth server-to-server + tạo meeting trực tiếp từ UI | `lms_batch.py:224`, `lms_live_class.py` |
| Live class qua MS Teams | Graph API | `lms_live_class.py` |
| Timetable | Lịch theo ngày (Lesson/Quiz/Assignment/Live Class), template + legend; gộp tự động | `get_batch_timetable`, `ScheduleCalendar.vue` |
| Điểm danh tự động | Hourly job lấy attendance từ Zoom/Teams API | `update_attendance`, `lms_live_class.py:115` |
| Batch dashboard | Tiến độ học viên theo batch, feedback sau khóa | `BatchDashboard.vue`, `BatchFeedback.vue` |
| Nhắc nhở tự động | Email nhắc batch bắt đầu ngày mai + live class trong ngày | `lms_batch.py:459`, `lms_live_class.py:75` |

### 2.3. Quiz, assignment, bài tập lập trình

| Feature | Cách hoạt động | Vị trí chính |
|---|---|---|
| Quiz đa dạng | Single/multiple choice, input, open-ended; marks mỗi câu | `LMS Quiz`, `LMS Question` |
| Randomize & giới hạn | Shuffle câu hỏi, giới hạn số câu hỏi/quiz; marks đồng đều | `lms_quiz.py:138` |
| Chống lộ đề | `get_quiz` KHÔNG trả bảng câu hỏi; server parse lại toàn bộ | `lms_quiz.py:100` |
| Anti-gian lận thời gian | Đồng hồ server-side, grace 60s, resume attempt | `lms_quiz.py:223,313` |
| Chống nộp trùng | Atomic claim attempt (conditional UPDATE — xử lý snapshot isolation) | `lms_quiz.py:273` |
| Chấm điểm server-side | Bỏ qua `is_correct` từ client; negative marking; chấm lại lúc nộp | `lms_quiz.py:390` |
| Open-ended nộp ảnh | Lưu base64 ảnh câu trả lời | `lms_quiz.py:415` |
| Chống gian lận môi trường | Chặn copy/cut/contextmenu; phát hiện DevTools; log tab ẩn + concurrent session | `useExamGuards.js`, `api.py:2404` |
| Assignment | Nộp file/URL, hạn chế attachment riêng tư, chống nộp trùng; chấm điểm | `LMS Assignment Submission`, `grade_assignment` |
| Programming exercise | Test cases tự động chấm bài code | `LMS Programming Exercise`, `LMS Test Case` |
| Màn hình chấm bài | Instructor chấm submission, đối chiếu quiz kết quả | `QuizSubmission.vue`, `AssignmentSubmissionList.vue` |

### 2.4. Chứng chỉ & đánh giá tay nghề

| Feature | Cách hoạt động | Vị trí chính |
|---|---|---|
| LMS Certificate | Cấp khi hoàn thành course/batch, autoname = hash không đoán được, publish, expiry | `lms_certificate.py` |
| Template chứng chỉ | Print format tùy biến; tải PDF qua `/certificate.py` | `www/certificate.py` |
| Verification công khai | Trang certified participants + URL hash verify | `CertifiedParticipants.vue` |
| Certification có evaluator | Đặt lịch slot 1-1, auto-chọn evaluator, chống trùng slot/quá hạn | `lms_certificate_request.py` |
| Google Meet tích hợp | Tự tạo calendar event + Meet link khi đặt lịch; timezone tự động | `lms_certificate_request.py:176` |
| Đánh giá định kỳ | Hourly đánh dấu evaluation hết hạn; rating 0–5 điều kiện hoàn tất | `lms_certificate_request.py:268` |
| Email tự động | Email chúc mừng khi cấp chứng chỉ (template tùy chỉnh LMS Settings) | `lms_certificate.py` |

### 2.5. Chương trình học (Program)
- Gom nhiều course thành lộ trình; progress = **trung bình cộng** tiến độ các course (`update_program_progress` — `lms_enrollment.py:98`)
- Enroll theo program; chỉ Moderator publish; chống trùng course/member
- Trang `Programs.vue`, `ProgramForm.vue`, `ProgramCard.vue`

### 2.6. Thanh toán

| Feature | Cách hoạt động | Vị trí chính |
|---|---|---|
| Mua course/batch trả phí | Tạo LMS Payment + link gateway; tự enroll khi thanh toán thành công | `payments.py:21`, `utils.py:2100` |
| Gateway | Razorpay create_order riêng; kiến trúc cho phép plugin gateway | `payments.py` |
| GST & đa tiền tệ | Áp GST theo quốc gia (Payment Country child), quy đổi tiền tệ, đơn hàng | `utils.py:937,980,1003` |
| Kiểm tra quyền mua | Chặn: đã enrolled / batch sold out / batch đã bắt đầu / guest | `api.py:180` |
| Nhắc thanh toán | Daily job nhắc payment < 24h chưa nhận tiền | `lms_payment.py:15` |
| Giao diện | `Billing.vue` + order summary, transaction list trong Settings | |

### 2.7. Cộng đồng & gamification

| Feature | Cách hoạt động | Vị trí chính |
|---|---|---|
| Badge engine | Rule chạy trên `doc_events["*"]` on_change — mọi doc save đều được đánh giá | `lms_badge.py`, `hooks.py:100` |
| Thông báo | Doctype riêng (tránh lẫn Notification Log của Frappe): realtime + email + push mobile (ctg_custom) | `lms_notification.py` |
| Leaderboard | Xếp hạng học viên theo giờ học + chứng chỉ | `get_leaderboard`, `Leaderboard.vue` |
| Learning recognition | Top learners + ranking phòng ban; điểm có trọng số (completion×10, cert×15, giờ×1) | `api.py:642`, `RecognitionPanel.vue` |
| Jobs (module phụ) | Job Opportunity, ứng tuyển, hạn nộp tự đóng (route frontend đang tắt) | `job/` |

### 2.8. Báo cáo & thống kê (fork CT nổi bật)

| Feature | Cách hoạt động | Vị trí chính |
|---|---|---|
| Dashboard tổng | Enrollments, courses, users, completions, time spent | `get_chart_details`, `Statistics.vue` |
| **Department report (CT)** | Báo cáo theo phòng ban, join bảng `Employee` của HR; scope theo department của user | `api.py:563`, `get_report_department_scope` |
| Time tracking | Log thời gian học mỗi ngày (UPSERT theo member+course+date); permission xem của người khác | `api.py:2494`, `LMS Course Time Log` |
| Chuỗi thời gian | Tổng theo ngày/tuần/tháng (`Period` param) | `get_time_spent_summary` |
| Phân bố tiến độ | Histogram tiến độ học viên trong course | `get_course_progress_distribution` |
| Xem thời gian người khác | Quyền giới hạn: moderator, instructor của course, manager phòng ban | `can_view_other_members_time` |

### 2.9. Hồ sơ & người dùng
- Profile với kỹ năng (User Skill), học vấn, kinh nghiệm, chức năng/ngành mong muốn, chứng chỉ ngoài (`Certification` child — KHÔNG phải LMS Certificate)
- Persona selection sau login (`PersonaForm.vue`)
- Role tự gán cho user mới + tự heal khi login; Moderator quản lý role user
- Sidebar personal: ghim các item tùy chỉnh (`LMS Sidebar Item`)

### 2.10. Quản trị & Settings (UI đầy đủ)
`components/Settings/` gồm các tab: Members, Badges, Categories, Payment Gateways, Zoom & Teams
accounts, Email Templates, Evaluators, Transactions, Brand (logo/favicon), SEO.

- Duyệt course/batch: Moderator duyệt nội dung mới; email thông báo chủ sở hữu
- LMS Settings (Single): guest access, sidebar item, contact (CT), video threshold, email content
- Web templates trang chủ: `CustomWebTemplate` override render (course card, testimonials...)

### 2.11. Hạ tầng & nền tảng

| Feature | Cách hoạt động |
|---|---|
| PWA | Manifest + service worker auto-update, `InstallPrompt` |
| Realtime | socket.io (port 9000) cho notification + discussion; reconnect 5 lần |
| SEO meta động | `www/lms.py` render title/description theo route (course, batch, profile...) |
| i18n | Locale Tiếng Việt có sẵn (`translations/`), crowdin.yml |
| Telemetry | PostHog kích hoạt sau khi load user info |
| Unsplash | Chọn ảnh bìa từ Unsplash (`unsplash.py`) |
| Worksuite integration (CT) | Tạo + sync task khi LMS Enrollment created/updated (`lms_enrollment.py:24-44`) |
| Mobile push (CT) | Gửi push qua app `ctg_custom` nếu được cài |
| Anti-cheat tổng hợp | Quiz timing server-side + atomic claim + video wall-clock cap + activity log (tab hidden, devtools, concurrent sessions) + integrity banner |

---

## 3. Scheduler (background jobs)

**Hourly** (`hooks.py:113-126`):
- `schedule_evals` — tạo Google Calendar event cho evaluation sắp tới (`lms_certificate_request.py:159`)
- `update_course_statistics` — lessons/enrollments/rating của course (`api.py:1554`)
- `mark_eval_as_completed` — evaluation hết hạn (`lms_certificate_request.py:268`)
- `update_attendance` — điểm danh Zoom/Teams (`lms_live_class.py:115`)

**Daily**:
- `update_job_openings` — đóng job quá hạn (`job_opportunity.py:26`)
- `send_payment_reminder` — nhắc payment 24h (`lms_payment.py:15`)
- `send_batch_start_reminder` — nhắc batch ngày mai (`lms_batch.py:459`)
- `send_live_class_reminder` — nhắc lớp hôm nay (`lms_live_class.py:75`)

---

## 4. Luồng người dùng chính

**Học viên:**
Login → Persona → Home/StudentHome → Courses → CourseDetail (enroll) → Lesson
(`/lms/courses/:course/learn/X-Y`: video plyr, quiz block, notes, discussion) → Quiz (exam-guarded)
→ Assignment → Certificate/Profile.

**Instructor/Moderator:**
Home tab instructor (AdminHome) → CourseForm → LessonForm (EditorJS) → BatchForm + Batch dashboard →
chấm quiz/assignment submissions → Statistics → duyệt course/batch → Settings.

**Phân quyền:** router KHÔNG có role guard; từng trang tự kiểm tra `user.data.is_moderator/
is_instructor` (store `user.js`) hoặc render `NotPermitted.vue`.

---

## 5. Build & chạy

- `yarn dev` — Vite dev (proxy bench).
- `yarn build` — build và ghi HTML entry vào `../lms/www/lms.html` (cấu hình trong
  `frontend/vite.config.js`); **cần rebuild để SPA cập nhật**.
- `bench start` — chạy từ bench dir.
- `bench --site <site> run-tests --app lms` — test server (chạy qua Frappe runner, không pytest).
- `bench --site <site> run-ui-tests lms --headless` — Cypress (chỉ 2 spec).
- `pre-commit run --all-files` — Ruff + Prettier + ESLint.

## 6. Bẫy & lưu ý khi làm việc (tóm tắt — xem docs tương ứng)

1. Ghi danh 3 hệ song song — đọc `data-model.md` TRƯỚC (R1 trong risks.md).
2. `delete_course` cascade bypass permission — giữ check duy nhất `api.py:1606` (R2).
3. SCORM scan mã độc đang bị comment out (`api.py:1793`) (R3).
4. Whitelist-decorator trap khi chèn hàm mới trên hàm đã có decorator (xem `dev-workflow.md`).
5. `utils.py` vừa là helpers vừa là API surface.
6. Endpoint mới phải tự gọi helper phân quyền — không có middleware tự làm.
7. EditorJS 2 điểm đăng ký — sửa lesson block phải update cả read + edit view.
8. `Certification` (chứng chỉ ngoài) ≠ `LMS Certificate` (chứng chỉ khóa học).