# INTEGRATION-06E Candidate API v1 Contract

## Status and conventions

This is the frozen PAI Candidate API v1 contract after
`INTEGRATION-06E.1.5`.

Base path: `/api/v1`

Responses should use the repository's versioned envelope convention where the
integration boundary requires it. IDs exposed by this API are opaque PAI
domain references. Internal `job_id`, `profile_id`, storage `object_key`, and
actor IDs are omitted unless a later contract explicitly requires them.

All endpoints are organization-scoped and require an identity context resolved
by PAI. The browser does not send `actor_id`.

## Candidate list

```http
GET /api/v1/candidates?status=active&cursor=...&limit=50&sort=updated_at_desc
```

Response:

```json
{
  "items": [
    {
      "candidate_id": "uuid",
      "status": "active",
      "review_state": "pending_review",
      "version": 2,
      "updated_at": "2026-08-18T10:00:00Z"
    }
  ],
  "next_cursor": "opaque-or-null"
}
```

The list is a review/read model, not a raw extraction-job listing. Filtering,
keyset pagination, deterministic sorting, and organization scope are applied by
PAI. `status` is `active` or `archived`; `sort` is one of
`updated_at_asc`, `updated_at_desc`, `created_at_asc`, or `created_at_desc`.
`limit` is 1..100 and the cursor is opaque.

## Candidate detail

```http
GET /api/v1/candidates/{candidate_id}
```

Response shape:

```json
{
  "candidate_id": "uuid",
  "status": "active",
  "review_state": "pending_review",
  "profile": {
    "version": 2,
    "summary": {
      "skill_count": 12,
      "experience_count": 4,
      "education_count": 2
    }
  },
  "claims": [
    {
      "claim_id": "uuid",
      "value": "Built ETL pipelines using Python",
      "evidence_type": "work_experience",
      "evidence_status": "supported",
      "evidence_refs": ["uuid"]
    }
  ],
  "version": 2
}
```

The detail response may contain claim values and approved semantic metadata,
but not raw document bytes, object-store keys, provider prompts, raw model
output, or internal actor IDs.

## Create candidate and attach a document

Candidate creation establishes the business identity independently from
technical document IDs:

```http
POST /api/v1/candidates
Content-Type: application/json

{}
```

```json
{
  "candidate_id": "uuid",
  "status": "active",
  "review_state": "draft"
}
```

Document association is a separate PAI operation. The current PAI v1 flow is
two-step: create the Candidate, then associate an already-ingested clean CV:

```http
POST /api/v1/candidates/{candidate_id}/documents
Content-Type: application/json

{"document_id": "uuid", "is_primary": true}
```

Response:

```json
{
  "candidate_id": "uuid",
  "document_id": "uuid",
  "candidate_document_id": "uuid"
}
```

PAI does not derive `candidate_id` from `document_id` or `profile_id`.
Duplicate association returns `409 candidate_document_exists`; ownership and
organization checks are enforced server-side.

## Extraction status

```http
GET /api/v1/candidates/{candidate_id}/extraction-status
```

Response:

```json
{
  "candidate_id": "uuid",
  "status": "pending_review",
  "documents": [
    {
      "candidate_document_id": "uuid",
      "kind": "cv",
      "status": "succeeded",
      "review_state": "pending_review",
      "profile_version": 2
    }
  ],
  "latest_error": null
}
```

Workflow IDs remain internal. Error responses may expose a stable safe error
code and correlation ID, but not provider output or raw CV text.

## Evidence retrieval

```http
GET /api/v1/candidates/{candidate_id}/claims/{claim_id}/evidence
```

Response contract is defined in
`06e-evidence-retrieval-contract.md`. The endpoint verifies that the claim
belongs to the candidate and organization before returning source metadata and
policy-approved evidence.

## Review actions

```http
POST /api/v1/candidates/{candidate_id}/accept
POST /api/v1/candidates/{candidate_id}/request-revision
POST /api/v1/candidates/{candidate_id}/reject
```

Request body:

```json
{
  "expected_profile_version": 2,
  "reason": "optional reviewer reason",
  "idempotency_key": "client-generated-unique-key"
}
```

The action is authorized against the PAI-resolved actor and organization. A
stale version returns a conflict. Responses use stable `version` (the
extraction profile version). Repeating the same action with the same
idempotency key returns the same response; reusing a key for another action
returns `409 candidate_review_idempotency_conflict`. `accept` does not mean that every claim is
verified; it means the reviewer accepted the current extraction profile under
the Candidate Review policy.

## Safe error vocabulary

The future API should use stable codes such as:

```text
candidate_not_found
candidate_access_denied
candidate_document_not_eligible
extraction_pending
candidate_profile_version_conflict
candidate_review_state_conflict
candidate_cursor_invalid
candidate_review_idempotency_conflict
claim_not_found
evidence_not_available
identity_context_missing
```

No error should expose SQL details, storage keys, raw prompts, raw model
output, or unredacted CV/JD content.

## Versioning and compatibility

The `/api/v1` contract is additive and independent from the existing technical
extraction endpoints. Existing `/documents`, `/extraction-jobs`, and
`/extraction-profiles` endpoints remain internal/PAI workflow APIs until a
future implementation explicitly decides whether to deprecate or retain
them.
