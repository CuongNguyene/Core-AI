# CLAUDE.md

This file is auto-loaded by Claude Code at the start of every session in this repo. Keep it short —
it's read every time regardless of task, so only high-signal, repo-specific material belongs here.
Everything else lives in `docs/` and gets read on demand.

## What this repo is

Frappe LMS: a learning-management app on Frappe Framework (Python backend, `lms/`) + Vue 3
(frontend, `frontend/` — note the different folder name from the sibling `helpdesk` app in this
bench, which uses `desk/`). Fork of upstream Frappe LMS, customized by this org. No `AGENTS.md`
exists here (unlike `helpdesk`) — this file stands alone.

## Before you start certain kinds of work, read the matching doc

| You're about to...                                              | Read first |
|-------------------------------------------------------------------|------------|
| Touch course/batch/cohort/enrollment data or any doctype relationship | [`docs/data-model.md`](docs/data-model.md) |
| Add or change a permission check, or figure out who can do what  | [`docs/permissions.md`](docs/permissions.md) |
| Add or edit a Vue component / page                               | [`docs/frontend-guardrails.md`](docs/frontend-guardrails.md) |
| Refactor for complexity/quality, or need to verify a change actually works | [`docs/dev-workflow.md`](docs/dev-workflow.md) |

These aren't loaded automatically — open the relevant one before starting so you're not
re-discovering the same things (and re-spending the same tokens) a previous session already
figured out.

## High-signal gotchas (worth knowing even if you don't open the docs above)

- **Three overlapping enrollment systems exist, only one is current.** Legacy `Cohort`/
  `Cohort Subgroup`/`Cohort Staff`/`Cohort Mentor`, the current `LMS Batch`/`LMS Batch Enrollment`,
  and `LMS Enrollment` — an older doctype that unifies both and is **still actively referenced**
  (e.g. `Exercise Submission.member` links to it, not to `User`). Don't assume any one of these is
  dead without checking `docs/data-model.md` first — deleting/ignoring the "legacy-looking" one is
  a real way to break something still in use. `lms/patches/v2_0/` has active migration patches
  between these systems (most recent: `fix_orphan_course_duration_column.py`), so this is
  in-progress, not settled history.
- **`lms/lms/utils.py` is not just utilities — it's also a real API surface** (multiple
  `@frappe.whitelist()` endpoints alongside the permission-check helpers). Don't assume "utils.py"
  means "no whitelisted endpoints here."
- **Permission checks here work differently than in `helpdesk`.** This app barely uses declarative
  `has_permission`/`permission_query_conditions` hooks — role grants in doctype JSON are broad, and
  real scoping happens imperatively inside whitelisted functions via helpers in `lms/lms/utils.py`
  (`has_course_instructor_role`, `is_instructor`, `is_cohort_staff`, etc.) plus inline
  `frappe.only_for(...)` guards in `lms/lms/api.py`. See `docs/permissions.md` — don't port the
  `helpdesk` mental model over by default.
- **Don't pattern-match UI off `frontend/src/pages/PersonaForm.vue`.** It uses raw Tailwind gray
  classes instead of the semantic tokens (`bg-surface-*`/`text-ink-*`) every other page uses. See
  `docs/frontend-guardrails.md` for what to copy instead.
- `Certification` (a child table for a user's external credentials) and `LMS Certificate` (a
  course-completion certificate) are unrelated doctypes with confusingly similar names — check
  which one you actually mean before editing.
