# Repository Guidelines

Fork of upstream Frappe LMS (Python/Frappe backend + Vue 3 frontend), customized by this org. Backend lives in `lms/` (whitelisted APIs in `lms/lms/api.py` and `lms/lms/utils.py`, DocTypes in `lms/lms/doctype/<doctype>/`, routes in `lms/www/`, migrations in `lms/patches/`). Frontend lives in `frontend/src/`. E2E specs in `cypress/e2e/`. Do not hand-edit `lms/public/dist/`.

Read the matching doc before sensitive work — they encode hard-won context, not generic advice:

| You're about to... | Read first |
|---|---|
| Touch course/batch/cohort/enrollment data or doctype relationships | `docs/data-model.md` |
| Add/change a permission check, or figure out who can do what | `docs/permissions.md` |
| Add or edit a Vue component/page | `docs/frontend-guardrails.md` |
| Refactor or verify a change actually works | `docs/dev-workflow.md` |
| Assess known system risks before/while making a change | `docs/risks.md` |

## Build, Test, and Development Commands

Run from the app root unless noted:

- `yarn dev` — Vite dev server (proxied to bench).
- `yarn build` — build frontend; **writes the HTML entry to `../lms/www/lms.html`** (configured in `frontend/vite.config.js` via `frappeui.buildConfig.indexHtmlPath`). Rebuild after frontend changes or the served SPA is stale.
- `bench start` — run from the bench directory (e.g. `~/frappe-bench`), not the app root.
- `bench --site <site> run-tests --app lms` — server tests via Frappe's runner (no pytest/conftest; don't use raw pytest).
- `bench --site <site> run-ui-tests lms --headless` — Cypress suite; only `batch_creation.cy.js` and `course_creation.cy.js` exist.
- `pre-commit run --all-files` — Ruff (lint + import sort + format), Prettier, ESLint.

Order: format/lint before tests; for backend edits, `python3 -m py_compile <file>` first to catch syntax errors fast.

## Testing reality — check before assuming coverage exists

Most of the 66 `test_*.py` files are empty auto-generated stubs (`class TestX: pass`) that assert nothing. Only two have real coverage: `lms/lms/doctype/lms_course/test_lms_course.py` (useful reference for cascading test-data cleanup) and `lms/lms/doctype/lms_quiz/test_lms_quiz.py`. Open the file before assuming a doctype is covered.

For live verification, write a throwaway script with a `run()` at `lms/verify_<topic>.py` (inside the `lms` Python package, not app root — `bench execute` imports it as `lms.verify_<topic>.run`), print `[OK]`/`[FAIL]`, and delete it when done.

## Backend gotchas

- **Three overlapping enrollment systems coexist; only one is current.** Legacy `Cohort*` doctypes, current `LMS Batch` + `LMS Batch Enrollment`, and older `LMS Enrollment` which is **still load-bearing** (`Exercise Submission.member` links to it, not `User`). Don't delete or ignore the legacy-looking ones without checking `docs/data-model.md`. `lms/patches/v2_0/` holds active migration patches between them.
- **`lms/lms/utils.py` is also an API surface** (~40 `@frappe.whitelist()` endpoints alongside helper functions), not just utilities.
- **Permissions are imperative, not declarative.** Doctype-JSON role grants are broad (any Instructor can edit any course at the JSON level); real scoping happens via explicit checks in whitelisted functions: helpers in `utils.py` (`can_create_courses`, `has_course_moderator_role`, ...) and inline `frappe.only_for(...)` in `api.py`. New endpoints must call these explicitly.
- **Whitelist-decorator trap:** when inserting a new function directly above an existing one in `api.py`/`utils.py`, check for a decorator (`@frappe.whitelist()`) immediately above the target first — otherwise the decorator silently moves onto your new helper. See `docs/dev-workflow.md`.
- `Certification` (child table for a user's *external* credentials) and `LMS Certificate` (course-completion certificate) are unrelated — check which one you mean.
- Cascade deletes (`delete_course` in `api.py`) use `frappe.db.delete` and bypass doc permissions; permission is checked once at the top — preserve that check if editing.

## Frontend gotchas

- EditorJS is instantiated directly in two places — `pages/Lesson.vue` (read view) and `pages/LessonForm.vue` (edit view). Adding a lesson-content block type requires updating **both**.
- `router.js` has **no role guard** — `beforeEach` only handles auth redirect. Student/instructor branching happens inside each page component via store checks.
- Data fetching is `createResource`/`createListResource` from frappe-ui only — no axios.
- Styling uses semantic Tailwind tokens (`bg-surface-*`, `text-ink-*`); **don't copy `pages/PersonaForm.vue`** — it's the one file using raw gray classes and is a known anti-pattern.

## Coding Style

Python 3.10+, tabs, double quotes, Ruff (110-char lines): `ruff format` + Ruff import sorting. DocType dirs snake_case (`lms_course`); Vue files PascalCase (`CourseDetail.vue`). Prettier frontend settings: single quotes, no semicolons.

## Commits & PRs

Conventional Commit subjects are enforced in CI (`feat:`, `fix:`, `refactor:`...). Keep commits focused. Flag migrations, permission changes, and backward-compatibility concerns explicitly in PRs.
