# FRAPPE-AI-01A Deterministic Brief Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a deterministic GOAL_DRIVEN brief workspace to Frappe LMS that creates a Core-AI request, edits immutable brief revisions, handles stale revisions, and confirms the latest eligible revision.

**Architecture:** The Vue page calls only existing Frappe whitelisted methods. `pai_frappe` remains the server-side authentication and Core-AI boundary; Core-AI remains the source of truth for requests, revisions, readiness, and confirmation. The page keeps transient form/loading/error state locally and does not add a brief DocType or conversation/model path.

**Tech Stack:** Vue 3, Vue Router, frappe-ui `createResource`/`toast`, Frappe whitelisted Python APIs, existing LMS Vitest/Cypress conventions, Core-AI v1 course-authoring API.

**Spec:** The approved FRAPPE-AI-01A task brief in the conversation; this checked-in plan is the reproducible implementation reference.

## Global Constraints

- Do not call `/conversation/respond`.
- Do not add a Frappe brief/revision DocType.
- Do not modify Core-AI business logic or contract.
- Do not call curriculum planning, generation, materialization, MinIO, ClamAV, or workers.
- Browser calls only Frappe whitelisted methods; no Core-AI credentials or URLs in Vue.
- Use Core-AI revision status, not `CourseAuthoringRequest.status`, for confirmation truth.
- Do not connect this feature to Learning Assignment, Batch Enrollment, My Learning, or compliance.
- Preserve English translation fallback and light-theme conventions.

## Review Focus

- Role visibility: ordinary learners must not see or open authoring UI; test route/sidebar gating.
- Idempotent create: duplicate submit must be disabled in-flight and use the existing wrapper's canonical retry-key mechanism; test one server call per intentional operation.
- Canonical latest: reload revisions after clarify/revise/confirm and select highest Core-AI version; test stale local ordering.
- Stale revision: HTTP 409 must refresh without overwriting unsaved edits; test safe recoverable state.
- Safe failures: map known backend codes without exposing upstream details; test unavailable/access-denied/validation states.

---

### Task 1: Revalidate the existing bridge contract (read-only)

**Files:**
- Read-only: `../Core-AI/apps/pai_frappe/pai_frappe/api.py`
- Read-only: `../Core-AI/apps/pai_frappe/pai_frappe/client.py`
- Test: existing `../Core-AI/apps/pai_frappe/pai_frappe/tests/test_client.py`

**Interfaces:**
- Consumes: existing `pai_frappe.api` methods `create_course_authoring_request`, `get_course_authoring_request`, `list_authoring_brief_revisions`, `clarify_authoring_brief`, `revise_authoring_brief`, `confirm_authoring_brief`.
- Produces: verified wrapper signatures, role authorization, safe errors, and idempotency behavior; no Core-AI/pai_frappe file changes.

- [ ] Step 1: Inspect all existing wrapper signatures, return shapes, and `_require_authoring_access()` behavior.
- [ ] Step 2: Verify ordinary learners are rejected server-side when calling authoring methods; do not rely on route/sidebar hiding.
- [ ] Step 3: Run the existing focused `pai_frappe` tests without modifying Core-AI.
- [ ] Step 4: If a wrapper is insufficient, stop with `BLOCKED_BY_BRIDGE_WRAPPER` rather than adding a wrapper in this milestone.

### Task 2: Add route, authoring navigation, and role guard

**Files:**
- Modify: `frontend/src/router.js`
- Modify: `frontend/src/components/AppSidebar.vue`
- Test: frontend route/sidebar test following current repository conventions.

**Interfaces:**
- Consumes: existing `userResource` role flags and sidebar insertion helpers.
- Produces: route name `AICoursePlanning`, path `/ai-course-planning/:requestId?`, visible only to authoring roles.

- [ ] Step 1: Add a failing route/visibility test for an authoring user and ordinary learner.
- [ ] Step 2: Run the focused test and verify it fails because the route/menu is absent.
- [ ] Step 3: Add the lazy route and one existing-style sidebar entry guarded by Instructor/Moderator/System Manager.
- [ ] Step 4: Run the focused test and verify both visibility cases pass.
- [ ] Step 5: Confirm no Learning Operations sidebar links or routes changed semantically.

### Task 3: Build local deterministic brief workspace state

**Files:**
- Create: `frontend/src/pages/AICoursePlanning.vue`
- Create: `frontend/src/utils/authoringBrief.js` only if a narrowly scoped pure helper is needed.
- Test: focused component/page tests in the existing frontend test location.

**Interfaces:**
- Consumes: `frappe-ui` resources calling `pai_frappe.api.create_course_authoring_request`, `get_course_authoring_request`, `list_authoring_brief_revisions`, and `clarify_authoring_brief`.
- Produces: create state, loading states, safe error state, request summary, canonical latest revision, deterministic clarification display.

- [ ] Step 1: Write failing render tests for new state, loading state, request metadata, and revision status.
- [ ] Step 2: Run the focused test and verify it fails because the page does not exist.
- [ ] Step 3: Implement the page shell using current Learning Operations layout, empty state, `createResource`, and translation conventions.
- [ ] Step 4: Add create form with `title`, `training_brief.goal`, explicit `mode: "GOAL_DRIVEN"`, and supported basic fields only.
- [ ] Step 5: Use the existing wrapper's canonical idempotency mechanism; if a frontend key is required, generate it once per intentional create and reuse it only for retries of that operation.
- [ ] Step 6: On create success, retain the returned local `PAI Request` reference and navigate with the canonical request reference in `/ai-course-planning/:requestId?`.
- [ ] Step 7: On direct route load, fetch request and revisions from Core-AI through Frappe and reconstruct the workspace entirely from canonical data.
- [ ] Step 8: Add deterministic clarify action and render returned questions/readiness without hard-coded rule duplication.
- [ ] Step 9: Run focused component tests and verify the page renders all states.

### Task 4: Add structured revision editor and canonical reload

**Files:**
- Modify: `frontend/src/pages/AICoursePlanning.vue`
- Test: same focused frontend component test file.

**Interfaces:**
- Consumes: `list_authoring_brief_revisions` response fields `version`, `status`, `payload`, `clarification`, `created_at`, `confirmed_at`.
- Produces: revision payload accepted by `revise_authoring_brief`.

- [ ] Step 1: Write failing tests for supported field rendering, revision save, and version refresh.
- [ ] Step 2: Run them and verify they fail before editor/save behavior exists.
- [ ] Step 3: Render only current supported fields: goal, outcomes, prerequisites, constraints, horizon, effort, excluded scope, emphasis, and feedback.
- [ ] Step 4: Convert repeatable list fields to the existing simple control conventions; do not create a generic schema framework.
- [ ] Step 5: Submit edits through `revise_authoring_brief`, never mutate historical local revision data as persisted truth.
- [ ] Step 6: Reload revision history and derive latest by maximum `version`.
- [ ] Step 7: After creating and reloading the new canonical latest revision, call deterministic clarify for that latest revision before evaluating confirmation eligibility.
- [ ] Step 8: Verify the focused tests pass and unsaved form state is not silently overwritten by refresh.

### Task 5: Add confirmation and stale/error UX

**Files:**
- Modify: `frontend/src/pages/AICoursePlanning.vue`
- Test: same focused frontend component test file.

**Interfaces:**
- Consumes: `confirm_authoring_brief` and existing `frappe-ui` error response shape.
- Produces: confirmation panel, disabled/non-disabled confirm state, stale refresh behavior, safe user-facing messages.

- [ ] Step 1: Write failing tests for READY_FOR_CONFIRMATION, non-ready, CONFIRMED, `revision_not_latest`, and safe backend errors.
- [ ] Step 2: Run them and verify the expected failures.
- [ ] Step 3: Enable confirm only for canonical latest status `READY_FOR_CONFIRMATION`.
- [ ] Step 4: Call `confirm_authoring_brief` with the latest revision ID and reload canonical data only after success.
- [ ] Step 5: On `revision_not_latest`, refresh revisions and preserve unsaved edits where practical; never force overwrite.
- [ ] Step 6: Map known error codes to actionable messages without raw stack traces.
- [ ] Step 7: Run focused tests and verify confirmed state shows version/time and disables confirmation.
- [ ] Step 8: Add a resume test that loads `/ai-course-planning/:requestId` for a confirmed request and renders the canonical confirmed revision after fetching again.

### Task 6: Translation, responsive/theme polish, and regression tests

**Files:**
- Modify: `frontend/src/translation.js` only for new visible strings, preserving English fallback.
- Modify: `frontend/src/pages/AICoursePlanning.vue` for existing spacing/theme/responsive conventions.
- Test: focused frontend tests and existing Learning Operations smoke tests.

**Interfaces:**
- Consumes: existing `__()` translation helper, light/dark-compatible tokens, existing empty/error/loading components.
- Produces: accessible deterministic workspace on desktop/mobile without changing Learning Operations semantics.

- [ ] Step 1: Add failing assertions for translated labels and key empty/loading/error states.
- [ ] Step 2: Implement translations through current dictionary conventions and use `__()` for every visible string.
- [ ] Step 3: Verify light default and existing theme tokens remain intact.
- [ ] Step 4: Run route/page tests for `/my-learning`, `/learning-assignments`, and Statistics regression.
- [ ] Step 5: Run frontend lint, production build, `git diff --check`, and focused backend bridge tests.

### Task 7: Live deterministic integration smoke and final verification

**Files:**
- No new product files; use existing local runtime and development data only.

**Interfaces:**
- Consumes: running Frappe LMS, Core-AI backend, configured `pai_frappe` actor bridge.
- Produces: evidence for create → revisions → clarify → revision → confirm → reload.

- [ ] Step 1: Verify Frappe/Core-AI health and that MinIO/ClamAV/workers remain stopped.
- [ ] Step 2: Execute one real GOAL_DRIVEN create through the browser/Frappe server path.
- [ ] Step 3: Fetch revisions and run deterministic clarify; do not call conversation/respond.
- [ ] Step 4: Create a valid structured revision, reload it, clarify that new revision, confirm the resulting latest eligible revision, and reload the page via its request URL.
- [ ] Step 5: Verify confirmed state survives reload and capture non-secret IDs.
- [ ] Step 6: Inspect network/code paths for no browser-to-Core-AI call and no model/provider call.
- [ ] Step 7: Run the complete applicable verification commands and report any failures explicitly.
