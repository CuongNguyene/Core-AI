# PR-004 CV/JD Extraction Vertical Slice Design

## Goal

Build a reviewable, fixture-backed CV/JD extraction slice:

```text
fixture document ID
→ extraction job
→ separate worker
→ ModelGateway structured output
→ evidence-backed profile
→ human correction/version
```

The slice produces preliminary evidence only. It never verifies competency,
stores raw document content, or accepts document upload.

## API

All routes are development-only and use the identity boundary in ADR-0007.

- `POST /extraction-jobs` accepts `document_id` and `document_kind`; returns a
  queued job owned by `X-PAI-Actor-ID`.
- `GET /extraction-jobs/{job_id}` returns the owner job state and safe failure
  category.
- `GET /extraction-profiles/{profile_id}` returns the owner profile and its
  source-backed claims.
- `POST /extraction-profiles/{profile_id}/corrections` requires
  `X-PAI-Actor-Role: reviewer`, validates every replacement claim has a source
  locator, and creates a new profile version in `CORRECTED` state.

No request body accepts raw CV/JD, actor ID, model prompt or arbitrary schema.

## Data model

`ExtractionJob` contains job ID, fixture document ID/kind, owner actor ID,
status (`queued`, `running`, `succeeded`, `failed`), correlation ID and safe
error category.

`CVExtractionProfile` contains candidate claims such as experience, skill and
education. `JDExtractionProfile` contains role requirement claims such as
required skill and responsibility. Every claim has `value`, `confidence`,
`evidence_status` (`supported`, `unknown`, `insufficient`) and `SourceLocator`.
`SourceLocator` carries fixture document ID, section and character span. A claim
without source evidence cannot be persisted as supported.

Profiles have immutable version, owner, state (`PENDING_REVIEW`, `CORRECTED`,
`ACCEPTED`) and safe model/template/schema/policy audit metadata. They have no
competency decision field.

## Execution

`DocumentSource` resolves trusted fixture IDs to simulated CV/JD text. The web
route writes a job and returns. `ExtractionWorker` claims a queued job, chooses
the registered prompt/schema by document kind and invokes `ModelGateway`.
Success creates a pending-review profile; error creates a failed job with an
error category only.

For this PR, repositories have an in-memory implementation for deterministic
tests and a SQLAlchemy persistence adapter/schema for the local PostgreSQL
stack. The worker remains a separate application entry point; tests may invoke
its `run_once()` method directly.

## Prompt and structured output

Fixture templates are trusted, versioned registry entries. Document text is
rendered only into the user message and the system instruction explicitly says
to treat it as untrusted data. The existing ModelGateway verifies Pydantic
schema ID/version and re-validates model output. CV/JD schemas forbid unknown
fields; model omission is represented by explicit `unknown`/`insufficient`
claims rather than guessed values.

## Golden harness

Golden fixtures contain no real PII and define expected normalized claims plus
source locators. The harness executes mock gateway output through the worker and
compares profiles with fixtures. It is an initial regression baseline, not a
quality metric for production model selection.

## Security and audit

All endpoints use existing safe error envelope. API ownership is checked before
job/profile access. Audit records contain provider, model, template/schema/
policy versions, correlation ID, routing decision, latency/token usage and
actor/action. Raw prompt, document, payload and raw output do not enter audit
or logs.

## Non-goals

- Upload/object-storage/retention of real CV/JD.
- External AI provider.
- Production identity, tenancy or RBAC.
- Automatic human acceptance, competency verification, matching or assessment.

## Implementation follow-up

PR-004 implementation left the `ACCEPTED` transition and SQLAlchemy runtime
repository incomplete. ADR-0008 defines PR-004.1 as the blocking follow-up;
official matching remains out of scope until that PR is complete.
