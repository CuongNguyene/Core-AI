# Refactor & verification workflow

Read this before doing a refactor or any change you need to actually prove still behaves the same,
not just "looks right on read-through."

## Testing reality — check before assuming coverage exists

66 `test_*.py` files exist, but the overwhelming majority are empty scaffolding stubs
(`class TestX(UnitTestCase): pass`) auto-generated when the doctype was created — they run, they
just don't assert anything. Only two files have real coverage:

- `lms/lms/doctype/lms_course/test_lms_course.py` (98 lines, plain `unittest.TestCase`, manual
  cascading `tearDown` across `Exercise Submission` → `LMS Enrollment` → `Course Lesson` — a useful
  reference for how to clean up test data given the doctype relationships in `docs/data-model.md`)
- `lms/lms/doctype/lms_quiz/test_lms_quiz.py` (196 lines)

No `conftest.py`, no `[tool.pytest]` section in `pyproject.toml` (only `ruff`/`isort` config) — this
runs via Frappe's built-in test runner, not raw pytest:

```bash
bench --site <site> run-tests --app lms
```

Don't assume a doctype has real test coverage just because a `test_*.py` file exists for it — open
the file and check.

## General refactor-safety checklist (Frappe-generic, applies here same as anywhere in the bench)

1. **`python3 -m py_compile <file>`** first — catches syntax errors immediately.
2. **Whitelist-decorator safety audit**, before *and* after editing:
   ```bash
   grep -n "^@" <file> -A1 | grep -B1 "^[0-9]*-def _"
   ```
   Any hit means a decorator (often `@frappe.whitelist()`) sits directly above a private/helper
   function — almost always a sign an edit inserted a new function *between* an existing decorator
   and the function it was meant to decorate, silently moving the whitelisting onto the new helper
   instead. This is a real incident that happened in the sibling `helpdesk` app during a refactor —
   the fix is the same here: before inserting a new function directly above an existing one, check
   for a decorator immediately above the target first, and insert the new function before the
   decorator line if one exists.
   This matters more here than in a typical app because `lms/lms/api.py` and `lms/lms/utils.py` are
   both huge (2698 and 2988 lines) with `@frappe.whitelist()` decorators scattered densely
   throughout — see `docs/permissions.md` for exact line numbers of some of them.
3. **Live-test against a real site** rather than trusting the diff alone, especially for anything
   touching the enrollment-system logic in `docs/data-model.md` — the three-system overlap makes it
   easy for a change to look correct against one enrollment path while silently breaking another.

## Live-testing pattern (bench execute)

Write a throwaway script at `lms/verify_<topic>.py` (inside the actual `lms` Python package
directory, not the app root — `bench execute` imports it as `lms.verify_<topic>.run`). Give it a
`run()` function that prints `[OK]`/`[FAIL]` per assertion and raises if any failed. Run it against
the actual bench/site for this environment, then **delete the script when done** — it's scratch,
not part of the repo. Prefer synthetic/mocked inputs over mutating real enrollment/course data where
the function under test allows it, given how easy it is to leave the three-enrollment-system data
in an inconsistent state by hand.

## When a test "fails," check the test before assuming the code is wrong

If you write a throwaway verification script and an assertion fails, re-check what the *unmodified*
original code actually does for that exact input before concluding you introduced a regression —
it's common for the surprise to be in the test's own assumption (e.g. assuming a hook doesn't run,
assuming a field resolves to what you expect) rather than in the change itself.
