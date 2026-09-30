# DEPRECATED

Status: `DEPRECATED`

This document is preserved for historical reference. Do not implement from
this document. Use the canonical v1 contract set:

- `docs/domain/integration/01b-api-contract-design.md`
- `docs/domain/integration/01b-course-blueprint-contract.md`
- `docs/domain/integration/01b-learning-result-contract.md`
- `docs/domain/integration/01b-identity-contract.md`

Canonical version: `v1`

---

# Integration API contract design

This document defines the boundary between PAI Learning source services and
the LMS API. It is a contract design, not an implementation plan.

## Namespaces

PAI-owned endpoints retain source semantics under an explicit namespace:

```text
/api/pai/evidence-documents
/api/pai/extraction-jobs
/api/pai/role-profiles
/api/pai/capability-analysis
/api/pai/development-plans
/api/pai/credentials
```

LMS endpoints remain unchanged:

```text
/api/documents
/api/courses
/api/learning-paths
/api/quizzes
/api/attempts
/api/certificates
```

No handler may silently serve both meanings of a path.

## Envelope

Every adapter response carries:

```json
{
  "data": {},
  "contract": {
    "id": "pai.course-blueprint",
    "version": "0.1",
    "source": "pai_learning",
    "projection": "lms_draft"
  },
  "provenance": {
    "source_ids": [],
    "source_versions": [],
    "generated_at": "2026-01-01T00:00:00Z"
  }
}
```

Errors use stable codes and do not expose raw CV/JD, prompts, or model output.
An adapter must fail closed when the source profile, policy, approval state, or
tenant authorization is missing.

## Lifecycle rules

- A source draft can create only an LMS draft projection.
- `PROVISIONAL` source profiles produce preview projections only.
- `ACTIVE` plus required approvals may produce an official projection.
- A learning result never updates a PAI capability status to `VERIFIED`.
- Idempotency is keyed by `(source_type, source_id, source_version,
  target_type, target_id)`.

## Overlap decisions

`POST /api/documents` is not reused for CV/JD extraction. `POST
/api/learning-paths` is not reused for a source capability development plan.
Adapters expose explicit DTOs and preserve the source IDs rather than copying
unowned semantic fields into LMS entities.
