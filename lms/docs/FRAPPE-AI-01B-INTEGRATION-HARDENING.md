# FRAPPE-AI-01B Integration Hardening

The LMS route is `/lms/ai-course-planning/:requestId?`. The sidebar entry and
all bridge calls are restricted to `Instructor`, `Moderator`, and `System
Manager`. The Frappe `pai_frappe` wrappers remain the authorization and
Core-AI boundary; the browser never receives Core-AI credentials or calls its
URL directly.

The supported lifecycle is:

`create → load → clarify → edit → create immutable revision → clarify the new revision → confirm → resume`

The latest revision is selected by canonical revision `version`. Creating a
revision invalidates the prior readiness decision. The UI keeps Confirm
disabled for the complete mutation interval, including the reload-to-clarify
window, and enables it only for the canonical latest revision with
`READY_FOR_CONFIRMATION`.

Resume uses the local Frappe `PAI Request.name` in the route. Reload fetches
the request and revision history again; local Vue state is not the source of
truth. A stale revision refreshes canonical data while preserving unsaved
editor values where possible. Create retries reuse one idempotency key for the
same intentional operation.

The 01B result artifacts are under
`test/results/frappe-ai-01b/`. Static implementation checks, the fresh
35-test `pai_frappe` bridge suite, and the canonical Bench production build
pass. The LMS route and Core-AI readiness endpoints return HTTP 200, and the
relevant containers are healthy. The canonical Linux Cypress runner is the
dedicated `cypress/included:14.5.4` container, separate from the Frappe runtime.
The exact `cypress/e2e/ai_course_planning.cy.js` run passed 1/1 against the
current stack. The host build remains non-canonical because it lacks Bench's
`sites/common_site_config.json`; no fake configuration was created. Native
macOS Cypress remains unsupported but is not required for acceptance. The
Learning Operations follow-up specs exposed pre-existing test-fixture issues:
`batch_course_sync.cy.js` receives an SSR 500 for nonexistent
`BATCH-SYNC-UAT`, while `course_creation.cy.js` times out at its existing
instructor selector. Neither failure is in the AI route. MinIO and ClamAV were
not used by the authoring flow. No Core-AI source was changed by this
milestone.
