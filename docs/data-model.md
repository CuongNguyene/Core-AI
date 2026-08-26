# Data model reference

Read this before touching course, batch, cohort, or enrollment logic. This app has 85 doctypes and
— unlike a clean single-model app — **three overlapping ways to represent "who's enrolled in
what"** that coexist because a migration between them is still in progress. This is the map so you
don't build on the wrong one or delete something that looks legacy but isn't.

## Course structure (stable, no traps here)

`LMS Course` → child table `chapters` (wraps `Course Chapter` via `Chapter Reference`) →
`Course Chapter` has its own child table `lessons` (wraps `Course Lesson` via `Lesson Reference`) →
`Course Lesson` links back to both `chapter` and `course`, plus optionally a `completion_quiz`
(`LMS Quiz`). `Course Instructor` and `Course Evaluator` are thin wrappers around a `User` link
(Evaluator adds a schedule child table). `LMS Course` also links `LMS Category`, `Currency`, and has
a `related_courses` child table.

## Enrollment — three systems, know which is current

1. **Legacy: `Cohort`.** `Cohort` (links `course`, `instructor`), `Cohort Subgroup` (links `cohort`
   + `course`), `Cohort Staff`/`Cohort Mentor` (link `cohort` + `email` + `course`, with a `role`
   field: Admin/Manager/Staff), `Cohort Join Request` (`cohort` + `subgroup` + `email`, status
   Pending/Accepted/Rejected).
2. **Current: `LMS Batch`.** `LMS Batch` (child tables: `instructors` via `Course Instructor`,
   `Batch Course`, a generic polymorphic `LMS Assessment` via `assessment_type`/`assessment_name`,
   `LMS Batch Timetable`). `LMS Batch Enrollment` links `member` (User) + `batch` + `payment` +
   `source`.
3. **`LMS Enrollment` — older, but still load-bearing, don't treat as dead.** Unifies both worlds:
   links `course`, `cohort`, `subgroup`, `batch_old` (→ `LMS Batch Old`), `member_type`
   (Student/Mentor/Staff), `certificate`, plus the CT-specific `worksuite_task` field (see below).
   `Exercise Submission`/`Exercise Latest Submission` link their `member` field to **`LMS
   Enrollment`, not to `User` directly** — that's the tell that this doctype is still in the active
   path, not just legacy data. It's also the one doctype with real test coverage
   (`lms/lms/doctype/lms_course/test_lms_course.py`), which cascades deletes through `Exercise
   Submission` → `LMS Enrollment` → `Course Lesson` in `tearDown`.

`lms/patches/v2_0/` contains hand-written migration patches between these systems
(`move_batch_instructors_to_evaluators.py`, `migrate_batch_student_data.py`,
`fix_orphan_course_duration_column.py` — matches the recent `c29be10` "auto-heal orphaned duration
column" commit). If you're touching enrollment logic, skim this folder first — it's evidence of
what's still shifting, not settled history.

## Assignments, exercises, badges

- **`LMS Assignment`** is embedded directly in lesson content (not a standalone list a student
  browses). **`LMS Assignment Submission`** links `lesson` + `assignment` + `member` + `course` +
  `evaluator`.
- **`Exercise Submission`** / **`Exercise Latest Submission`** link `exercise` (`LMS Exercise`) +
  `course` + `lesson` + `member` (→ `LMS Enrollment`, see above). `Exercise Latest Submission` also
  denormalizes `member_cohort`/`member_subgroup` for faster reporting queries.
- **`LMS Badge`** is a small rule engine: fields `reference_doctype`, `event` (New / Value Change /
  Auto Assign), `condition`. Auto-processed on every doc save via `hooks.py:104-108`
  (`doc_events["*"]["on_change"]` → `lms.lms.doctype.lms_badge.lms_badge.process_badges`) — so
  adding fields to *any* doctype can interact with badge conditions if one references it.
  `LMS Badge Assignment` links `member` + `badge`.

## Naming trap: `Certification` vs. `LMS Certificate`

`Certification` is a **child table** (`istable: 1`) representing a user's *external* professional
credentials (e.g. an AWS cert they already hold) — unrelated to course completion. `LMS Certificate`
is the *course-completion* certificate this app issues, and has its own `has_website_permission`
hook (`hooks.py:216`). Check which one a task actually means before editing either.

## CT-specific: Worksuite integration

`lms/lms/worksuite_integration.py` + `LMS Enrollment.create_worksuite_task`/`sync_worksuite_task`
(`lms/lms/doctype/lms_enrollment/lms_enrollment.py:24-44`) integrate with the same external
"Worksuite" task system that the sibling `helpdesk` app's `custom_worksuite_task_id` field also
talks to — not an upstream Frappe LMS feature, a CT-org addition. `override_doctype_class =
{"Web Template": "lms.overrides.web_template.CustomWebTemplate"}` (`hooks.py:98-100`,
`lms/overrides/web_template.py`) is the only doctype-class override in the app.
