# INTEGRATION-06E Evidence Retrieval Contract

## Purpose

Candidate review must explain an extracted claim through a PAI-owned evidence
chain. The LMS receives evidence through the contract below; it does not
search raw documents or infer source spans.

```text
Claim
  |
  +-- Evidence Reference
        |
        +-- Source Document Reference
              |
              +-- Source Span / Locator
              |
              +-- Policy-approved excerpt
```

## Evidence identity

### Claim

```json
{
  "claim_id": "uuid",
  "candidate_id": "uuid",
  "profile_version": 2,
  "value": "Built ETL pipelines using Python",
  "evidence_type": "work_experience",
  "evidence_status": "supported",
  "evidence_refs": ["uuid"]
}
```

`claim_id` is a Candidate domain identity. It is not an array index or an
extraction profile ID.

### Evidence reference

```json
{
  "evidence_id": "uuid",
  "claim_id": "uuid",
  "source_document": {
    "document_reference": "opaque-pai-document-reference",
    "kind": "cv"
  },
  "source_locator": {
    "section": "experience",
    "start_offset": 1200,
    "end_offset": 1240,
    "page": 2
  },
  "excerpt": "Built ETL pipelines using Python",
  "evidence_type": "work_experience",
  "context": "used_in_employment",
  "confidence": 0.95,
  "provenance": {
    "profile_version": 2,
    "source": "cv_extraction",
    "locator_status": "resolved"
  }
}
```

The exact page field is optional for text-only sources; offsets/section are the
canonical locator fields already used by PAI extraction. If the source locator
cannot be resolved, the evidence must be returned as unavailable/unresolved,
not silently repaired or presented as confirmed.

## Retrieval endpoint

```http
GET /api/v1/candidates/{candidate_id}/claims/{claim_id}/evidence
```

Response:

```json
{
  "candidate_id": "uuid",
  "claim_id": "uuid",
  "items": [
    {
      "evidence_id": "uuid",
      "source_document": {
        "document_reference": "opaque-pai-document-reference",
        "kind": "cv"
      },
      "source_locator": {
        "section": "experience",
        "start_offset": 1200,
        "end_offset": 1240
      },
      "excerpt": "Built ETL pipelines using Python",
      "provenance": {
        "profile_version": 2,
        "source": "cv_extraction",
        "locator_status": "resolved"
      }
    }
  ]
}
```

## Privacy and disclosure rules

- PAI checks candidate, organization, claim, and document authorization before
  returning evidence.
- Raw document bytes are not part of the normal response. A future explicit
  download contract may return a short-lived authorized reference.
- Excerpts are bounded and policy-approved; raw provider prompt/model output is
  never returned.
- Storage object keys, internal database IDs, actor IDs, and audit internals
  are not exposed by default.
- A missing/expired/revoked document yields an explicit unavailable state while
  preserving the historical claim/provenance record.

## Evidence status semantics

```text
resolved       locator and source span are available
unresolved     claim exists but source mapping needs review
unavailable    source is no longer retrievable under retention/access policy
conflicting    multiple evidence records disagree and need review
```

`unresolved` and `unavailable` must not be rendered as confirmed absence of the
candidate capability. The LMS should show the safe state and reviewer note.

## Provenance requirements

Every returned evidence item must retain:

- claim and evidence IDs;
- candidate and profile version;
- source document reference;
- source locator/span;
- extraction evidence type/context;
- confidence and locator status;
- policy-safe source/provenance metadata.

The contract deliberately preserves the distinction between a claim, its
source evidence, and the technical extraction workflow that produced it.
