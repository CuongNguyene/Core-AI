# Frontend consistency guardrails

Read this before adding or editing a Vue component. Same underlying `frappe-ui` conventions as the
sibling `helpdesk` app (semantic Tailwind tokens, `createResource`-family data fetching), but this
app's file organization differs in a couple of ways worth knowing before you start.

## Reuse before you build

`frontend/src/components/` is flat (~50 files) and, **unlike `helpdesk`, has no `index.ts`
re-export** — every consumer imports each component by its full path
(`import CourseCard from '@/components/CourseCard.vue'`). Check this list before writing something
new:

- **Course/lesson**: `CourseCard.vue`, `CourseCardOverlay.vue`, `CourseOutline.vue`,
  `CourseResources.vue`, `CourseReviews.vue`, `CourseInstructors.vue`, `CreateOutline.vue`,
  `LessonContent.vue`, `LessonHelp.vue`, `RelatedCourses.vue`, `CertificationLinks.vue`
- **Batch/cohort**: `BatchCard.vue`, `BatchCourses.vue`, `BatchDashboard.vue`, `BatchFeedback.vue`,
  `BatchOverlay.vue` (modal), `BatchStudents.vue`, `ScheduleCalendar.vue`
- **Assessment**: `Assessments.vue`, `AssessmentPlugin.vue`, `Assignment.vue`, `Quiz.vue`,
  `QuizBlock.vue`
- **Avatars/identity**: `UserAvatar.vue`, `UserDropdown.vue`
- **Layout/shell**: `DesktopLayout.vue`, `MobileLayout.vue`, `NoSidebarLayout.vue`, `AppSidebar.vue`,
  `SidebarLink.vue`
- **Skeletons/empty states**: `CardSkeleton.vue`, `DetailSkeleton.vue`, `FormSkeleton.vue`,
  `ListRowSkeleton.vue`, `ProfileSkeleton.vue`, `Skeleton.vue`, `EmptyState.vue`, `NoPermission.vue`,
  `NotPermitted.vue`
- **Misc**: `Leaderboard.vue`, `RecognitionPanel.vue`, `StudentHeatmap.vue`,
  `IntegrityWarningBanner.vue`, `Tags.vue`, `ProgressBar.vue`, `JobCard.vue`, `ProgramCard.vue`,
  `UnsplashImageBrowser.vue`
- **`components/Controls/`** (form inputs, separate subfolder): `Autocomplete.vue`,
  `ChildTable.vue`, `Code.vue`, `CodeEditor.vue`, `ColorSwatches.vue`, `IconPicker.vue`, `Link.vue`,
  `MultiSelect.vue`, `Rating.vue`, `Uploader.vue`

## Styling: same semantic-token convention as `helpdesk`

Confirmed across `Courses.vue`, `UserAvatar.vue`, `LessonForm.vue`, `BatchOverlay.vue` — all use
`bg-surface-*`/`text-ink-gray-*`/`border-outline-gray-*`, zero raw hex or `gray-N` classes. One
exception, see anti-pattern below.

## Rich content editing (EditorJS / CodeMirror / Ace)

Not unique to `helpdesk`-style apps — this is LMS-specific and non-obvious if you haven't looked at
it before. EditorJS is instantiated **directly** (no shared wrapper component) in two places:

- `frontend/src/pages/Lesson.vue` (~line 743) — the learner-facing read view
- `frontend/src/pages/LessonForm.vue` (~line 177) — the instructor edit view

Registered plugins: `@editorjs/header`, `paragraph`, `checklist`, `nested-list`, `table`, `code`,
`embed`, `inline-code`, `simple-image`, plus custom blocks `AudioBlock.vue`, `VideoBlock.vue`,
`UploadPlugin.vue`, `QuizBlock.vue`, `AssessmentPlugin.vue`. If you need to add a new lesson-content
block type, both `Lesson.vue` and `LessonForm.vue` need updating — there's no single registration
point.

CodeMirror/Ace power the separate standalone code-editing controls — `components/Controls/Code.vue`
and `components/Controls/CodeEditor.vue` — used e.g. from `Settings/SettingDetails.vue`. Don't
confuse these with the EditorJS `code` plugin above; different library, different purpose (a
dedicated code-input field vs. a code block inside rich lesson content).

## Data fetching

Same as `helpdesk`: `createResource`/`createListResource`/`createDocumentResource` from
`frappe-ui`. Zero axios usage anywhere in `frontend/src`. `frontend/src/utils/index.js` wraps the
raw `call()` helper for exactly two endpoints (`get_meta_info`/`update_meta_info`) — it's not a
general API abstraction, don't route new calls through it by default.

## Routing has no role guard — checks happen in the page component

`frontend/src/router.js` is a flat route table. `router.beforeEach` only handles auth redirect (to
`/login`) and a chunk-load-error auto-reload — there's no `meta.role`-based guard. Student/
instructor/admin branching happens *inside* each page component via store checks. If you add a page
that should be restricted, follow that pattern (check the relevant `docs/permissions.md` helper or
role inside the component / its data-fetch guard), don't expect the router to do it for you.

## Known anti-pattern — don't copy this file's patterns

`frontend/src/pages/PersonaForm.vue` (154 lines, the persona/role-selection screen shown right after
login) uses raw Tailwind gray classes throughout (`sm:bg-gray-50`, `text-gray-900`, `text-gray-700`,
`bg-white`) instead of semantic tokens — the only sampled page/component that does this. Treat it as
a cautionary example, not a template.
