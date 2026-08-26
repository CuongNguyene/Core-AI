# Permission model reference

Read this before adding a new `@frappe.whitelist()` endpoint or changing who can do what. **This
app's permission model works differently from the sibling `helpdesk` app** — if you've worked in
`helpdesk` recently, don't port that mental model over by default; read this first.

## Roles in play

- `System Manager` — full access everywhere, as usual for Frappe.
- `Moderator` — the LMS-wide admin/staff role. Broad CRUD on course-related doctypes at the
  doctype-JSON level.
- `Instructor` — course-owner-level access, scoped in practice by whether the user is actually
  listed as an instructor on the specific course (checked imperatively, see below — the doctype-JSON
  role grant itself is broad, not course-scoped).
- `LMS Student` — the learner role.
- Cohort-level roles (`Admin`/`Manager`/`Staff`) live as a **field value** on `Cohort Staff`/
  `Cohort Mentor` rows, not as real Frappe roles — don't confuse these with the four above.

## Why you won't find much in `hooks.py`

Unlike `helpdesk`, this app barely uses Frappe's declarative permission hooks. The entire
`permission_query_conditions` dict is just `{"LMS Notification": ...}` (`hooks.py:78-79`), and
`has_website_permission` only covers `LMS Certificate Evaluation`/`LMS Certificate`
(`hooks.py:214-216`). There is no `has_permission` hook registered for any doctype. Doctype-JSON
role permissions for `LMS Course` etc. grant broad, full-CRUD access to
`System Manager`/`Moderator`/`Instructor` with no `if_owner` restriction
(`lms/lms/doctype/lms_course/lms_course.json:357-390` for an example) — the JSON-level grant alone
would let any Instructor edit any course, which is not the actual intended behavior.

## Where the real scoping happens: imperative checks in `lms/lms/utils.py`

The actual "can this specific user touch this specific course/cohort" logic lives in shared helper
functions, called explicitly at the top of whitelisted functions:

| Helper | Purpose |
|---|---|
| `has_course_instructor_role(member=None)` (`utils.py:492`) | Is this user an Instructor at all (role check). |
| `can_create_courses(course, member=None)` (`utils.py:500`) | Is this user listed as an instructor on *this* course (checks `Course Instructor` child rows) — the actual per-course scoping. |
| `has_course_moderator_role(member=None)` (`utils.py:527`) | Is this user a Moderator. |
| `has_student_role(member=None)` (`utils.py:561`) | Is this user an `LMS Student`. |
| `is_instructor(course)` (`utils.py:433`) | Per-course instructor check (alternate entry point to the same relationship as `can_create_courses`). |
| `is_mentor(course, email)` (`utils.py:372`) | Cohort-mentor check via `LMS Course Mentor Mapping`. |
| `is_cohort_staff(course, user_email)` (`utils.py:379`) | Cohort-staff check via `Cohort Staff`/`Cohort Mentor`. |
| `get_report_department_scope(user=None)` (`utils.py:535`) | **CT-specific.** Scopes reporting queries to an HR `Department` the manager belongs to — no equivalent in upstream Frappe LMS. |

If you add a new endpoint that should be instructor/moderator/student-scoped, call the matching
helper explicitly — there's no decorator or middleware that does it for you.

## The other convention: inline `frappe.only_for(...)` in `lms/lms/api.py`

Many endpoints instead (or additionally) guard with Frappe's built-in `frappe.only_for(...)`, e.g.
`frappe.only_for("Instructor")` (`api.py:1015`), `frappe.only_for(["Moderator", "Instructor"])`
(`api.py:1135`), `frappe.only_for("Moderator")` (`api.py:1474,2132,2151,2173`),
`frappe.only_for("System Manager")` (`api.py:2182`). This raises `frappe.PermissionError` if the
current user lacks the role — a simpler, coarser check than the `utils.py` helpers (role-only, not
course-scoped). Occasional explicit `frappe.has_permission("LMS Course", "delete", course)` calls
also appear (`api.py:1606-1607`) for delete operations specifically.

**Net picture**: no single central guard pattern — pick whichever of `frappe.only_for(...)` (role
only) or the `utils.py` helpers (role + course/cohort scoping) matches what the endpoint actually
needs, matching the style already used by neighboring endpoints in the same file.

## API surface location

Both `lms/lms/api.py` (2698 lines) and `lms/lms/utils.py` (2988 lines) host `@frappe.whitelist()`
endpoints — `utils.py` is not just a helpers file, see `CLAUDE.md`'s gotcha list.
