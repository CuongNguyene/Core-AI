# PAI Integration API v1

This is the PAI-side HTTP boundary consumed by the LMS adapter. It is a projection API: it exposes only versioned integration DTOs and never PAI evidence, raw documents, prompts, provenance graphs, or internal policy metadata.

Base path: `/api/v1/integration`

## Authentication

Every endpoint requires:

```http
Authorization: Bearer <PAI_INTEGRATION_API_KEY>
```

The key is configured through `PAI_INTEGRATION_API_KEY` (or `INTEGRATION_API_KEY`). PAI does not accept the LMS user JWT or a shared user database for this boundary. Missing, malformed, or invalid credentials return `401`.

## Envelope

Every successful request uses the shared envelope:

```json
{
  "schema_version": "v1",
  "data": {}
}
```

## Course Blueprint

`GET /course-blueprints/{blueprint_id}`

Returns the PAI-owned, LMS-safe course projection:

```json
{
  "schema_version": "v1",
  "data": {
    "blueprint_id": "bp-001",
    "version": "1",
    "title": "Python foundations",
    "summary": "...",
    "estimated_duration_minutes": 45,
    "objectives": [{"objective_ref": "obj-1", "title": "...", "sequence": 1}],
    "modules": [{
      "module_ref": "mod-1",
      "title": "Cleaning",
      "order": 1,
      "lessons": [{
        "lesson_ref": "lesson-1",
        "title": "Invalid values",
        "order": 1,
        "delivery_type": "TEXT",
        "objective_refs": ["obj-1"]
      }]
    }],
    "assessment_references": []
  }
}
```

The implementation can project an existing PAI learning-path blueprint into this DTO. It does not return the learning path snapshot itself.

## Learning Result

`POST /learning-results`

The LMS sends a v1 envelope whose `data` contains `submission_id`, `learner_reference`, `course_reference`, `activity_reference`, and `completion_status`. `completion_status` must be `COMPLETED`.

The response is:

```json
{
  "schema_version": "v1",
  "data": {"status": "ACCEPTED", "evaluation_reference": "eval-001"}
}
```

`ACCEPTED` means PAI accepted the exchange and assigned an evaluation reference. It does not mean competency verified, learner passed competency, or evidence validated. PAI deduplicates by `submission_id`; retries return the original evaluation reference.

## Competency Result Reference

`GET /competency-results/{result_id}`

Returns only a safe status/reference projection:

```json
{
  "schema_version": "v1",
  "data": {"status": "PENDING", "evaluation_reference": "eval-001"}
}
```

The response intentionally excludes evidence, raw evaluation chains, provenance, raw documents, prompts, and policy metadata.

## Ownership boundary

PAI remains authoritative for competency, evidence, capability, assessment intelligence, and evaluation lifecycle. LMS remains authoritative for course delivery, enrollment, progress, completion, and certificates. The integration API does not create LMS models, foreign keys, or database coupling. A learning result is an accepted integration event, not a competency decision.

## Persistence

Learning-result idempotency is stored in PAI's `integration_learning_results` table, owned by the PAI Alembic migration stream. This table stores only the exchange references and request references needed for deduplication; it is not an LMS state table and contains no evidence or raw document content.
