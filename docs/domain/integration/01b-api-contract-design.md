# INTEGRATION-01B — FastAPI to NestJS API Contract Design

## Decision

Use a **hybrid** boundary: synchronous REST commands/queries for the admin-led blueprint workflow, and asynchronous versioned events for learner delivery results. No integration contract exposes a FastAPI SQLAlchemy model, a Prisma model, or a shared database table.

PAI is the intelligence service and source of truth for course-blueprint, learning-objective, assessment-blueprint, competency, evidence, and policy meaning. The LMS is the delivery service and source of truth for user authentication, course drafts/publication, enrollment, progress, quiz attempts, and course certificates.

## Proposed integration APIs

These endpoints are contract targets; they are **not existing routes** and are not implemented by INTEGRATION-01B.

| Consumer | Proposed API/event | Purpose | Authoritative response |
|---|---|---|---|
| LMS -> PAI | `POST /api/v1/integration/course-blueprint-requests` | Request a generated, approved blueprint from an authorized learning brief. | PAI blueprint request/operation reference. |
| LMS -> PAI | `GET /api/v1/integration/course-blueprints/{blueprint_id}?version=` | Retrieve an approved, immutable `CourseBlueprintContract`. | PAI blueprint projection contract. |
| LMS -> PAI | `POST /api/v1/integration/course-blueprints/{blueprint_id}/projection-acknowledgements` | Record the LMS course-draft projection and source version. | PAI receipt of the LMS-owned projection reference. |
| LMS -> PAI | `POST /api/v1/integration/learning-results` | Receive a delivery result under idempotency/correlation controls. | PAI receipt and evaluation-pending reference, never automatic competency verification. |
| LMS -> PAI | `GET /api/v1/integration/competency-results/{result_id}` | Read an authorized PAI competency evaluation projection. | PAI competency result. |
| PAI -> LMS | `learning.result.completed.v1` / `learning.result.updated.v1` | Logical event names emitted by LMS and consumed by PAI; transport is deferred. | LMS event facts. |

The first four rows describe the PAI boundary that the LMS calls. The event rows name the future event contract, not a broker choice. LMS internal REST routes such as `/courses`, `/quizzes`, and `/progress` remain LMS-only operational APIs.

## MVP flows

### A. Generate Course Blueprint

1. An authenticated LMS administrator/trainer creates a learning brief using LMS identity and organization context.
2. LMS calls PAI with `ActorReference`, `LearningBriefContract`, schema version, correlation ID, and idempotency key.
3. PAI validates the trusted actor scope, learning brief, prerequisite inputs, and policy/quality gates; generation may be asynchronous.
4. PAI returns a request reference and, once available, an approved immutable `CourseBlueprintContract`.
5. LMS reads the approved contract and decides whether to create a delivery draft. LMS cannot overwrite PAI blueprint semantics.

Failures: invalid brief (`400`), untrusted/unauthorized actor (`401`/`403`), tenant scope conflict (`403`), generation or quality-gate rejection (`409`/`422`), unavailable blueprint (`404`), and transient PAI failure (`503`). Responses carry stable public error codes only.

### B. Publish Blueprint into LMS

1. LMS receives or fetches the PAI-approved blueprint version.
2. LMS creates an LMS-owned draft `Course`, then LMS-owned modules, lessons, and optional delivery quiz/activity records.
3. LMS sends a projection acknowledgement containing its `course_instance_id`, blueprint ID/version, projection status, and correlation ID.
4. LMS publishes the draft using its own authorization and publication rules.

Mapping is one-way and versioned:

| PAI blueprint field | LMS projection | Rule |
|---|---|---|
| `title` | `Course.title` | Copied as an initial draft value; later LMS editorial changes do not mutate PAI. |
| presentation summary/duration | `Course.description`, `durationHours` | Optional delivery projection. |
| module title/order | `CourseModule.title`, `order` | LMS creates delivery records. |
| lesson title/type/order/content reference | `Lesson` fields | LMS resolves delivery assets/content independently. |
| assessment delivery guidance | draft `Quiz` or other LMS activity | Optional; LMS owns questions, attempts, scoring, and publication. |

Not copied into LMS persistence by default: competency references, evidence IDs/rules, gap IDs, target competency levels, Bloom/taxonomy metadata, prerequisite reasoning, assessment rubric details, source locators, policy version, model/generation provenance, raw prompts, and PAI internal identifiers other than opaque source references. An authorized opaque evidence display reference is PAI-owned, `display_only`, and `persist_allowed: false`; it cannot become an LMS entity, foreign key, provenance record, or document.

### C. Learning Result Feedback

1. LMS records lesson progress, enrollment completion, and quiz attempts under its own lifecycle.
2. When an agreed delivery milestone occurs, LMS publishes/sends `LearningResultEvent` to PAI.
3. PAI validates contract version, actor/organization scope, LMS course projection reference, idempotency key, and event ordering.
4. PAI stores or evaluates the result as an evidence input only when an explicit PAI policy permits it.
5. PAI may expose a `CompetencyResult` projection. LMS may display it but cannot edit it.

`COMPLETED`, quiz `passed`, or an LMS certificate does **not** mean a PAI competency is `VERIFIED`.

## Error and security boundary

PAI returns public codes such as `invalid_learning_brief`, `quality_gate_rejected`, `blueprint_unavailable`, `unsupported_schema_version`, `tenant_scope_mismatch`, and `duplicate_event`. LMS returns public projection codes such as `lms_user_not_found`, `course_projection_conflict`, and `course_projection_failed`. Neither side returns stack traces, ORM errors, raw evidence, policy internals, prompts, or credentials.

Service calls require service-to-service authentication, audience-bound credentials, short-lived tokens or mutually authenticated transport, correlation IDs, idempotency keys for commands/events, and authorization based on trusted LMS actor/organization references. The target has no demonstrated organization/tenant persistence; therefore tenant authority is a prerequisite decision, not an inferred field mapping.

## Non-goals

- No CV/JD, evidence graph, competency engine, instructional-design engine, or PAI policy persistence is migrated into the LMS database.
- No shared database, cross-service foreign key, or ORM model reuse is allowed.
- No direct mapping makes a PAI `AssessmentBlueprint` an LMS `Quiz` or a PAI credential an LMS certificate.
